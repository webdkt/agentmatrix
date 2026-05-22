"""
Chrome Process Lifecycle Manager

Starts a Chrome instance with remote debugging enabled,
or connects to an already-running one.
"""

import asyncio
import json
import logging
import os
import platform
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional

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


def _is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 1) -> bool:
    """Check if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False


def _get_ws_url_from_port(port: int, timeout: float = 30) -> str:
    """
    Get the WebSocket debugger URL from Chrome's /json/version endpoint.
    Retries until Chrome is ready or timeout is reached.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            url = f"http://127.0.0.1:{port}/json/version"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                ws_url = data.get("webSocketDebuggerUrl")
                if ws_url:
                    return ws_url
        except (urllib.error.URLError, ConnectionRefusedError, socket.timeout):
            pass
        time.sleep(0.5)

    raise RuntimeError(
        f"Chrome did not expose WebSocket URL on port {port} within {timeout}s"
    )


class ChromeManager:
    """
    Manages a shared Chrome instance with remote debugging.

    Usage:
        manager = ChromeManager(profile_dir="/path/to/profile")
        ws_url = await manager.ensure_started()
        # Use ws_url to connect CDPClient
    """

    def __init__(
        self,
        profile_dir: str,
        port: int = 9222,
        chrome_path: Optional[str] = None,
    ):
        self.profile_dir = Path(profile_dir)
        self.port = port
        self.chrome_path = chrome_path or os.environ.get(
            "CHROME_PATH", _find_chrome_executable()
        )
        self.process: Optional[subprocess.Popen] = None
        self._ws_url: Optional[str] = None

    async def ensure_started(self) -> str:
        """
        Ensure Chrome is running with remote debugging.

        Returns:
            WebSocket debugger URL (e.g. "ws://127.0.0.1:9222/devtools/browser/...")
        """
        # Case 1: Already have a ws_url and Chrome is still alive
        if self._ws_url and self.process and self.process.poll() is None:
            return self._ws_url

        # Case 2: Chrome is already running on this port (externally started)
        if _is_port_open(self.port):
            logger.info(f"Chrome already running on port {self.port}")
            self._ws_url = _get_ws_url_from_port(self.port)
            return self._ws_url

        # Case 3: Need to launch Chrome
        self._ws_url = await self._launch_chrome()
        return self._ws_url

    async def _launch_chrome(self) -> str:
        """Launch Chrome with remote debugging."""
        self.profile_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.chrome_path,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--safebrowsing-disable-auto-update",
        ]

        logger.info(f"Launching Chrome: port={self.port}, profile={self.profile_dir}")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Wait for Chrome to be ready
        ws_url = _get_ws_url_from_port(self.port, timeout=30)
        logger.info(f"Chrome started, WebSocket: {ws_url}")
        return ws_url

    def get_ws_url(self) -> Optional[str]:
        """Get the cached WebSocket URL (may be None if not started)."""
        return self._ws_url

    def is_running(self) -> bool:
        """Check if Chrome process is alive."""
        if self.process is None:
            return _is_port_open(self.port)
        return self.process.poll() is None

    async def stop(self):
        """Stop Chrome process if we launched it."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        self._ws_url = None
        logger.info("Chrome stopped")

    def __del__(self):
        """Best-effort cleanup."""
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
