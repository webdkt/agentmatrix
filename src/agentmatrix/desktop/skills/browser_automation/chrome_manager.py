"""
Chrome Process Lifecycle Manager

Starts a Chrome instance with remote debugging via pipes (--remote-debugging-pipe).
Uses file descriptors for CDP communication, bypassing the network stack entirely.
"""

import asyncio
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple

if sys.platform == "win32":
    import msvcrt

logger = logging.getLogger(__name__)

DEFAULT_CDP_SOCKET = "/tmp/agentmatrix_chrome_cdp.sock"
_SOCKET_DIR = "/tmp"
_ID_OFFSET_STEP = 10000


def _find_chrome_executable() -> str:
    """Find Chrome/Chromium executable path based on platform."""
    system = platform.system()

    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
    elif system == "Linux":
        candidates = [
            "google-chrome", "google-chrome-stable",
            "chromium", "chromium-browser",
            "microsoft-edge", "microsoft-edge-stable",
            "brave-browser",
        ]
    elif system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        ]
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
        # Try finding in PATH (macOS/Linux only)
        if system != "Windows":
            try:
                result = subprocess.run(
                    ["which", candidate],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except FileNotFoundError:
                pass

    raise RuntimeError(
        "Chrome/Chromium not found. Install Chrome or set CHROME_PATH env var."
    )


class ChromeManager:
    """
    Manages a shared Chrome instance with remote debugging via pipes.

    Usage:
        manager = ChromeManager(profile_dir="/path/to/profile")
        read_fd, write_fd = await manager.ensure_started()
    """

    def __init__(
        self,
        profile_dir: str,
        port: int = 9222,
        chrome_path: Optional[str] = None,
    ):
        self.profile_dir = Path(profile_dir)
        self.port = port  # kept for API compat, not used in pipe mode
        self.chrome_path = chrome_path or os.environ.get(
            "CHROME_PATH", _find_chrome_executable()
        )
        self.process: Optional[subprocess.Popen] = None
        self._pipe_fds: Optional[Tuple[int, int]] = None  # (read_fd, write_fd)
        self._session_relays: Dict[str, dict] = {}  # session_id → {server, thread, socket_path, ...}
        self._next_id_offset: int = _ID_OFFSET_STEP + 1  # 10001, 20001, 30001...

    async def ensure_started(self) -> Tuple[int, int]:
        """
        Ensure Chrome is running with pipe-based CDP transport.

        Returns:
            (read_fd, write_fd) for pipe transport.
        """
        if self._pipe_fds and self.process and self.process.poll() is None:
            return self._pipe_fds

        self._pipe_fds = await self._launch_chrome()
        return self._pipe_fds

    def start_session_relay(self, session_id: str, cdp_client) -> str:
        """Start a per-session UDS relay. Returns the socket path.

        Each session gets its own socket and ID range so scripts from
        different sessions can run concurrently without ID conflicts.
        """
        # Already have a relay for this session? Return existing socket path.
        if session_id in self._session_relays:
            existing = self._session_relays[session_id]
            if existing["server"].fileno() >= 0:
                return existing["socket_path"]
            # Stale entry, clean up
            self.stop_session_relay(session_id)

        # Assign ID range
        id_offset = self._next_id_offset
        self._next_id_offset += _ID_OFFSET_STEP

        # Socket path: use last 8 chars of session_id to keep it short
        short_id = session_id[-8:] if len(session_id) > 8 else session_id
        sock_path = f"{_SOCKET_DIR}/agentmatrix_cdp_{short_id}.sock"

        # Clean stale socket file
        if os.path.exists(sock_path):
            os.remove(sock_path)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(sock_path)
        server.listen(1)  # backlog 1 — one client at a time per session

        relay_info = {
            "server": server,
            "socket_path": sock_path,
            "id_offset": id_offset,
            "cdp_client": cdp_client,
            "client_conn": None,
            "thread": None,
        }
        self._session_relays[session_id] = relay_info

        def _accept_loop():
            logger.info(f"CDP relay for session {session_id[-8:]} listening on {sock_path}")
            while True:
                try:
                    conn, _ = server.accept()
                except OSError:
                    break
                old_conn = relay_info["client_conn"]
                if old_conn is not None:
                    logger.info(f"Kicking old relay client for session {session_id[-8:]}")
                    try:
                        old_conn.close()
                    except OSError:
                        pass
                    cdp_client.unregister_relay(session_id)
                    relay_info["client_conn"] = None
                relay_info["client_conn"] = conn
                cdp_client.register_relay(session_id, conn, id_offset)
                threading.Thread(
                    target=self._handle_session_client,
                    args=(session_id, conn, cdp_client),
                    daemon=True,
                    name=f"cdp-relay-{short_id}",
                ).start()

        t = threading.Thread(target=_accept_loop, daemon=True, name=f"cdp-accept-{short_id}")
        t.start()
        relay_info["thread"] = t

        logger.info(f"Session relay started: {session_id[-8:]} → {sock_path} (id_offset={id_offset})")
        return sock_path

    def _handle_session_client(self, session_id: str, conn: socket.socket, cdp_client):
        """Handle one UDS client for a session. Data flows through CDPClient (not directly to pipe)."""
        relay_info = self._session_relays.get(session_id)
        try:
            while True:
                try:
                    data = conn.recv(65536)
                except socket.timeout:
                    continue
                if not data:
                    break
                cdp_client.write_from_relay(session_id, data)
        except (OSError, BrokenPipeError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            # 只有当前连接仍是已注册的 relay 时才清理，避免新连接被旧清理误删
            current_relay = cdp_client._relay_sessions.get(session_id)
            if current_relay and current_relay["conn"] is conn:
                cdp_client.unregister_relay(session_id)
                relay_info = self._session_relays.get(session_id)
                if relay_info:
                    relay_info["client_conn"] = None

    def stop_session_relay(self, session_id: str):
        """Stop and clean up a session's relay."""
        relay_info = self._session_relays.pop(session_id, None)
        if not relay_info:
            return

        # Close client connection
        conn = relay_info.get("client_conn")
        if conn:
            try:
                conn.close()
            except OSError:
                pass

        # Close server socket
        server = relay_info.get("server")
        if server:
            try:
                server.close()
            except OSError:
                pass

        # Remove socket file
        sock_path = relay_info.get("socket_path")
        if sock_path and os.path.exists(sock_path):
            try:
                os.remove(sock_path)
            except OSError:
                pass

        # Unregister from CDPClient
        cdp_client = relay_info.get("cdp_client")
        if cdp_client:
            cdp_client.unregister_relay(session_id)

        logger.debug(f"Session relay stopped: {session_id[-8:]}")

    def stop_all_relays(self):
        """Stop all session relays."""
        for sid in list(self._session_relays):
            self.stop_session_relay(sid)

    async def _launch_chrome(self) -> Tuple[int, int]:
        """Launch Chrome with remote debugging pipes, return (read_fd, write_fd)."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        # Create two pipe pairs:
        #   parent_read, child_write  →  Chrome writes CDP responses to child_write
        #   child_read, parent_write  →  Chrome reads CDP commands from child_read
        parent_read, child_write = os.pipe()
        child_read, parent_write = os.pipe()

        common_args = [
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--safebrowsing-disable-auto-update",
        ]

        logger.info(f"Launching Chrome (pipe mode), profile={self.profile_dir}")

        if sys.platform == "win32":
            # Windows: --remote-debugging-io-pipes takes OS handles directly.
            # Convert Python FDs to inheritable Windows handles.
            cr_handle = msvcrt.get_osfhandle(child_read)
            cw_handle = msvcrt.get_osfhandle(child_write)
            os.set_handle_inheritable(cr_handle, True)
            os.set_handle_inheritable(cw_handle, True)

            cmd = [self.chrome_path,
                   f"--remote-debugging-io-pipes={cr_handle},{cw_handle}"] + common_args

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=False,  # must be False for handle inheritance
            )
        else:
            # macOS/Linux: Chrome hardcodes fd 3 = read, fd 4 = write.
            # Use shell redirection to set up FDs, bypassing Python close_fds issues.
            shell_script = f'exec "$0" "$@" 3<&{child_read} 4>&{child_write}'

            cmd = [self.chrome_path, "--remote-debugging-pipe"] + common_args

            self.process = subprocess.Popen(
                ["sh", "-c", shell_script] + cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                pass_fds=(child_read, child_write),
                start_new_session=True,
            )

        # Close child-side fds in parent (they belong to Chrome now)
        for fd in (child_read, child_write):
            try:
                os.close(fd)
            except OSError:
                pass

        # Give Chrome a moment to start up
        await asyncio.sleep(1.0)

        if self.process.poll() is not None:
            raise RuntimeError(
                f"Chrome exited immediately with code {self.process.returncode}"
            )

        logger.info(
            f"Chrome started (pid={self.process.pid}, "
            f"read_fd={parent_read}, write_fd={parent_write})"
        )
        return (parent_read, parent_write)

    def is_running(self) -> bool:
        """Check if Chrome process is alive."""
        return self.process is not None and self.process.poll() is None

    async def stop(self):
        """Stop Chrome process, close pipe fds, and stop all session relays."""
        self.stop_all_relays()
        if self._pipe_fds:
            for fd in self._pipe_fds:
                try:
                    os.close(fd)
                except OSError:
                    pass
            self._pipe_fds = None
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        logger.info("Chrome stopped")

    def __del__(self):
        """Best-effort cleanup."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
