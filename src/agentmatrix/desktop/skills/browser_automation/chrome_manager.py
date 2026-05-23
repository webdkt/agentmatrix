"""
Chrome Process Lifecycle Manager

Starts a Chrome instance with remote debugging via pipes (--remote-debugging-pipe).
Uses file descriptors for CDP communication, bypassing the network stack entirely.
"""

import asyncio
import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

if sys.platform == "win32":
    import msvcrt

logger = logging.getLogger(__name__)


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
        """Stop Chrome process and close pipe fds."""
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
