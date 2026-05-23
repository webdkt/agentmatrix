"""
CDP Pipe Transport — communicates with Chrome via pipes instead of WebSocket.

Uses Chrome's --remote-debugging-pipe which communicates over file descriptors,
completely bypassing network. This avoids enterprise proxies that may block
WebSocket connections to localhost.

Protocol: each message is [4-byte little-endian length][JSON payload].
"""

import asyncio
import fcntl
import logging
import os
import struct
from typing import Optional

logger = logging.getLogger(__name__)


class CDPPipeConnection:
    """Async CDP transport over pipes.

    Provides the same interface as websockets.WebSocketClientProtocol,
    so it can be used as a drop-in replacement in CDPClient.
    """

    def __init__(self, read_fd: int, write_fd: int):
        self._rfd = read_fd
        self._wfd = write_fd
        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._read_task: Optional[asyncio.Task] = None
        self._closed = False

    async def start(self):
        """Set up non-blocking I/O and start the read loop."""
        for fd in (self._rfd, self._wfd):
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        self._read_task = asyncio.create_task(self._read_loop())

    async def close(self, code=1000, reason=""):
        """Close both pipe file descriptors."""
        self._closed = True
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
            try:
                await self._read_task
            except asyncio.CancelledError:
                pass
        for fd in (self._rfd, self._wfd):
            try:
                os.close(fd)
            except OSError:
                pass
        self._rfd = self._wfd = -1

    async def send(self, data: str):
        """Send a CDP message (length-prefixed JSON)."""
        encoded = data.encode("utf-8")
        header = struct.pack("<I", len(encoded))
        payload = header + encoded
        # Use run_in_executor to avoid blocking the event loop on write
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._blocking_write, payload)

    def _blocking_write(self, data: bytes):
        """Write all bytes to the pipe (blocking, runs in executor)."""
        while data:
            n = os.write(self._wfd, data)
            data = data[n:]

    def __aiter__(self):
        return self

    async def __anext__(self):
        msg = await self._queue.get()
        if msg is None:
            raise StopAsyncIteration
        return msg

    async def _read_loop(self):
        """Continuously read length-prefixed CDP messages from the pipe."""
        loop = asyncio.get_event_loop()
        try:
            while not self._closed:
                header = await self._async_read(loop, 4)
                if not header:
                    break
                length = struct.unpack("<I", header)[0]
                if length == 0:
                    continue
                if length > 50 * 1024 * 1024:  # sanity check: 50MB
                    logger.error(f"Pipe message too large: {length}")
                    break
                body = await self._async_read(loop, length)
                if not body:
                    break
                await self._queue.put(body.decode("utf-8"))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            if not self._closed:
                logger.debug(f"Pipe read error: {e}")
        finally:
            await self._queue.put(None)

    async def _async_read(self, loop, n: int) -> bytes:
        """Read exactly n bytes from pipe asynchronously using add_reader."""
        result = b""
        while len(result) < n and not self._closed:
            # Try non-blocking read first (data might already be buffered)
            try:
                chunk = os.read(self._rfd, n - len(result))
                if not chunk:
                    return b""
                result += chunk
                continue
            except BlockingIOError:
                pass

            # Wait for data to become available
            future = loop.create_future()
            loop.add_reader(self._rfd, future.set_result, None)
            try:
                await future
            finally:
                loop.remove_reader(self._rfd)

        return result
