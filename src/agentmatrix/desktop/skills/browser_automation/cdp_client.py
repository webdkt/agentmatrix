"""
CDP Client — async Chrome DevTools Protocol client over pipes.

Communicates with Chrome via --remote-debugging-pipe file descriptors.
No network involved, immune to proxies/firewalls.
"""

import asyncio
import json
import logging
import socket
from collections import deque
from typing import Callable, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class CDPClient:
    """Async CDP client over pipe transport."""

    def __init__(
        self,
        pipe_fds: Tuple[int, int],
        event_buffer_size: int = 500,
    ):
        from .cdp_pipe import CDPPipeConnection
        self._pipe = CDPPipeConnection(*pipe_fds)
        self._msg_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._event_buffer: Deque = deque(maxlen=event_buffer_size)
        self._listen_task: Optional[asyncio.Task] = None
        self._connected = False
        self._reconnecting = False
        self._status_callbacks: List[Callable] = []
        self._relay_sessions: Dict[str, dict] = {}  # session_id → {"id_offset": int, "conn": socket}

    async def connect(self):
        """Connect to Chrome's CDP pipe and start listening."""
        if self._connected:
            return
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        await self._pipe.start()
        self._connected = True
        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info("CDP connected via pipe")

    async def close(self):
        """Close the pipe connection."""
        self._connected = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        await self._pipe.close()
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def send(self, method: str, params: dict = None,
                   session_id: str = None, timeout: float = 30) -> dict:
        """
        Send a CDP command and wait for the response.

        Returns:
            The "result" dict from the CDP response.
        """
        if not self._connected:
            raise RuntimeError("CDP client not connected")

        self._msg_id += 1
        msg_id = self._msg_id

        msg = {"id": msg_id, "method": method}
        if params:
            msg["params"] = params
        if session_id:
            msg["sessionId"] = session_id

        fut = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut

        await self._pipe.send(json.dumps(msg))

        try:
            result = await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(msg_id, None)
            raise asyncio.TimeoutError(
                f"CDP timeout: {method} (id={msg_id}, session={session_id})"
            )

        if "error" in result:
            error = result["error"]
            raise RuntimeError(
                f"CDP error: {error.get('message', error)} "
                f"(method={method}, code={error.get('code')})"
            )

        return result.get("result", {})

    async def send_raw(self, method: str, params: dict = None,
                       session_id: str = None, timeout: float = 30) -> dict:
        """Alias for send()."""
        return await self.send(method, params, session_id, timeout)

    # --- Target / Session Management ---

    async def get_targets(self) -> List[dict]:
        result = await self.send("Target.getTargets")
        return result.get("targetInfos", [])

    async def get_pages(self, include_internal: bool = False) -> List[dict]:
        targets = await self.get_targets()
        internal_prefixes = (
            "chrome://", "chrome-untrusted://", "devtools://",
            "chrome-extension://", "about:",
        )
        pages = [t for t in targets if t.get("type") == "page"]
        if not include_internal:
            pages = [
                t for t in pages
                if not t.get("url", "").startswith(internal_prefixes)
            ]
        return pages

    async def create_target(self, url: str = "about:blank") -> str:
        result = await self.send("Target.createTarget", {"url": url})
        return result["targetId"]

    async def attach_to_target(self, target_id: str) -> str:
        result = await self.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True}
        )
        return result["sessionId"]

    async def activate_target(self, target_id: str):
        await self.send("Target.activateTarget", {"targetId": target_id})

    async def close_target(self, target_id: str):
        await self.send("Target.closeTarget", {"targetId": target_id})

    async def detach_from_target(self, session_id: str):
        try:
            await self.send("Target.detachFromTarget", {"sessionId": session_id}, timeout=5)
        except Exception as e:
            logger.debug(f"detach_from_target failed: {e}")

    async def enable_domains(self, session_id: str,
                             domains: List[str] = None):
        if domains is None:
            domains = ["Page", "DOM", "Runtime"]
        for domain in domains:
            try:
                await self.send(f"{domain}.enable", session_id=session_id,
                                timeout=5)
            except Exception as e:
                logger.warning(f"Failed to enable {domain}: {e}")

    # --- Events ---

    def on_event(self, method: str, handler: Callable):
        self._event_handlers.setdefault(method, []).append(handler)

    def drain_events(self, method_filter: str = None) -> List[dict]:
        events = list(self._event_buffer)
        self._event_buffer.clear()
        if method_filter:
            events = [e for e in events if e.get("method") == method_filter]
        return events

    # --- Relay Management (per-session UDS sockets) ---

    def register_relay(self, session_id: str, conn: socket.socket, id_offset: int):
        """Register a session relay. CDP responses with IDs in [id_offset+1, id_offset+9999] will be forwarded to conn."""
        # 写超时 5 秒：客户端不读数据时，sendall 不会永久阻塞
        conn.settimeout(5)
        self._relay_sessions[session_id] = {"id_offset": id_offset, "conn": conn}
        logger.debug(f"Relay registered: session={session_id}, id_offset={id_offset}")

    def unregister_relay(self, session_id: str):
        """Unregister a session relay."""
        self._relay_sessions.pop(session_id, None)
        logger.debug(f"Relay unregistered: session={session_id}")

    def write_from_relay(self, session_id: str, data: bytes):
        """Forward raw CDP data from a UDS client to Chrome pipe, rewriting the message ID.

        Parses the JSON, rewrites 'id' by adding the session's id_offset,
        then writes to the pipe.
        """
        relay_info = self._relay_sessions.get(session_id)
        if not relay_info:
            return

        offset = relay_info["id_offset"]

        # Data may contain multiple null-terminated messages
        for part in data.split(b"\0"):
            if not part:
                continue
            try:
                msg = json.loads(part.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

            # Rewrite id
            original_id = msg.get("id")
            if isinstance(original_id, int):
                msg["id"] = original_id + offset

            self._pipe.write_raw(json.dumps(msg).encode("utf-8") + b"\0")

    # --- Internal ---

    async def _listen_loop(self):
        """Listen for CDP messages (responses + events)."""
        try:
            async for raw in self._pipe:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid CDP message: {raw[:200]}")
                    continue

                # Response to a command
                if "id" in msg:
                    msg_id = msg["id"]
                    fut = self._pending.pop(msg_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                    else:
                        # Check relay sessions — route by ID range
                        for sid, relay_info in dict(self._relay_sessions).items():
                            offset = relay_info["id_offset"]
                            if offset < msg_id < offset + 10000:
                                original_id = msg_id - offset
                                msg["id"] = original_id
                                conn = relay_info["conn"]
                                payload = json.dumps(msg).encode() + b"\0"
                                # sendall 可能阻塞（客户端缓冲区满），必须移出 event loop
                                asyncio.get_event_loop().run_in_executor(
                                    None, self._relay_send, conn, payload
                                )
                                break
                    continue

                # Event
                method = msg.get("method")
                if method:
                    self._event_buffer.append(msg)
                    handlers = self._event_handlers.get(method, [])
                    params = msg.get("params", {})
                    if "sessionId" in msg:
                        params["_sessionId"] = msg["sessionId"]
                    for handler in handlers:
                        try:
                            result = handler(params)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.warning(f"Event handler error ({method}): {e}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"CDP listen loop error: {e}")
        finally:
            was_connected = self._connected
            self._connected = False
            if was_connected:
                await self._notify_status(False)

    # --- Relay send (offloaded from event loop) ---

    @staticmethod
    def _relay_send(conn: socket.socket, data: bytes):
        """Send data to a relay UDS client. Runs in executor to avoid blocking the event loop."""
        try:
            conn.sendall(data)
        except (OSError, BrokenPipeError) as e:
            logger.warning(f"Relay send failed, closing client: {e}")
            try:
                conn.close()
            except OSError:
                pass

    # --- Status ---

    def on_status_change(self, callback: Callable):
        self._status_callbacks.append(callback)

    async def _notify_status(self, connected: bool):
        for cb in self._status_callbacks:
            try:
                result = cb(connected)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"Status callback error: {e}")
