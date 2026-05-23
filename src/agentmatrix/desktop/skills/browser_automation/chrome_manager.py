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
from pathlib import Path
from typing import Optional, Tuple

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
        # Try finding in PATH (Linux)
        result = subprocess.run(
            ["which", candidate],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()

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
        """Launch Chrome with --remote-debugging-pipe, return (read_fd, write_fd)."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        # Create two pipe pairs:
        #   parent_read, child_write  →  Chrome writes CDP responses to child_write (fd 3)
        #   child_read, parent_write  →  Chrome reads CDP commands from child_read (fd 4)
        parent_read, child_write = os.pipe()
        child_read, parent_write = os.pipe()

        cmd = [
            self.chrome_path,
            "--remote-debugging-pipe",
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

        # Chrome expects: fd 3 = write pipe (Chrome → us), fd 4 = read pipe (us → Chrome)
        _fd_map = {3: child_write, 4: child_read}

        def _preexec():
            for target_fd, source_fd in _fd_map.items():
                os.dup2(source_fd, target_fd)
            for fd in (child_write, child_read):
                try:
                    os.close(fd)
                except OSError:
                    pass

        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            pass_fds=(3, 4),
            preexec_fn=_preexec,
            start_new_session=True,
        )

        # Close child-side fds in parent (they've been dup'd in child)
        for fd in (child_write, child_read):
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
