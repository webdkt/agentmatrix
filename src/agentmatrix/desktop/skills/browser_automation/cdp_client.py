"""
CDP WebSocket Client — async raw Chrome DevTools Protocol client.

Connects to Chrome's remote debugging WebSocket and provides
send/receive for CDP commands and events.
"""

import asyncio
import json
import logging
from collections import deque
from typing import Any, Callable, Dict, List, Optional

import websockets

logger = logging.getLogger(__name__)


class CDPClient:
    """Async CDP WebSocket client. One connection to Chrome."""

    def __init__(self, ws_url: str, event_buffer_size: int = 500):
        self.ws_url = ws_url
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._msg_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._event_buffer: deque = deque(maxlen=event_buffer_size)
        self._listen_task: Optional[asyncio.Task] = None
        self._connected = False
        # 自动重连
        self._reconnecting = False
        self._status_callbacks: List[Callable] = []
        self._ws_url_resolver: Optional[Callable] = None

    async def connect(self):
        """Connect to Chrome's CDP WebSocket and start listening."""
        if self._connected:
            return
        # 如果自动重连正在进行，等待它完成
        if self._reconnecting:
            for _ in range(60):
                await asyncio.sleep(0.5)
                if self._connected:
                    return
            # 超时后继续尝试手动连接
        # 清理可能残留的旧 listen task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        self.ws = await websockets.connect(
            self.ws_url,
            max_size=50 * 1024 * 1024,  # 50MB for large DOM dumps
            ping_interval=20,
            ping_timeout=10,
        )
        self._connected = True
        self._listen_task = asyncio.create_task(self._listen_loop())
        logger.info(f"CDP connected: {self.ws_url}")

    async def close(self):
        """Close the WebSocket connection. Cancels any in-progress reconnect."""
        self._reconnecting = False  # 阻止自动重连
        self._connected = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
            self.ws = None
        # Cancel all pending futures
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

    async def send(self, method: str, params: dict = None,
                   session_id: str = None, timeout: float = 30) -> dict:
        """
        Send a CDP command and wait for the response.

        Args:
            method: CDP method name (e.g. "Page.navigate")
            params: Method parameters
            session_id: CDP session ID (for tab-specific commands)
            timeout: Seconds to wait for response

        Returns:
            The "result" dict from the CDP response.

        Raises:
            RuntimeError: If CDP returns an error.
            asyncio.TimeoutError: If no response within timeout.
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

        await self.ws.send(json.dumps(msg))

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
        """Alias for send() — kept for compatibility with browser-harness naming."""
        return await self.send(method, params, session_id, timeout)

    # --- Target / Session Management ---

    async def get_targets(self) -> List[dict]:
        """Get all browser targets (pages, iframes, workers, etc.)."""
        result = await self.send("Target.getTargets")
        return result.get("targetInfos", [])

    async def get_pages(self, include_internal: bool = False) -> List[dict]:
        """Get page targets, optionally filtering out chrome:// internal pages."""
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
        """Create a new tab, return targetId."""
        result = await self.send("Target.createTarget", {"url": url})
        return result["targetId"]

    async def attach_to_target(self, target_id: str) -> str:
        """Attach to a target, return session_id."""
        result = await self.send(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True}
        )
        return result["sessionId"]

    async def activate_target(self, target_id: str):
        """Bring a target to the foreground (visually show the tab)."""
        await self.send("Target.activateTarget", {"targetId": target_id})

    async def close_target(self, target_id: str):
        """Close a target (tab)."""
        await self.send("Target.closeTarget", {"targetId": target_id})

    async def detach_from_target(self, session_id: str):
        """Detach a CDP session from its target."""
        try:
            await self.send("Target.detachFromTarget", {"sessionId": session_id}, timeout=5)
        except Exception as e:
            logger.debug(f"detach_from_target failed: {e}")

    async def enable_domains(self, session_id: str,
                             domains: List[str] = None):
        """Enable CDP domains for a session."""
        if domains is None:
            domains = ["Page", "DOM", "Runtime", "Network"]
        for domain in domains:
            try:
                await self.send(f"{domain}.enable", session_id=session_id,
                                timeout=5)
            except Exception as e:
                logger.warning(f"Failed to enable {domain}: {e}")

    # --- Events ---

    def on_event(self, method: str, handler: Callable):
        """Register an event handler for a CDP event method."""
        self._event_handlers.setdefault(method, []).append(handler)

    def drain_events(self, method_filter: str = None) -> List[dict]:
        """
        Get and clear buffered events.

        Args:
            method_filter: If set, only return events matching this method.

        Returns:
            List of event dicts.
        """
        events = list(self._event_buffer)
        self._event_buffer.clear()
        if method_filter:
            events = [e for e in events if e.get("method") == method_filter]
        return events

    # --- Internal ---

    async def _listen_loop(self):
        """Listen for CDP messages (responses + events)."""
        try:
            async for raw in self.ws:
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
                    continue

                # Event
                method = msg.get("method")
                if method:
                    self._event_buffer.append(msg)
                    handlers = self._event_handlers.get(method, [])
                    # 将 sessionId 注入 params，方便 handler 路由
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

        except websockets.ConnectionClosed:
            logger.info("CDP WebSocket closed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"CDP listen loop error: {e}")
        finally:
            was_connected = self._connected
            self._connected = False
            # 自动重连（除非是显式 close()）
            if was_connected and not self._reconnecting:
                asyncio.ensure_future(self._reconnect())

    # --- Auto-reconnect ---

    def on_status_change(self, callback: Callable):
        """Register a callback for connection status changes: callback(connected: bool)."""
        self._status_callbacks.append(callback)

    def set_ws_url_resolver(self, resolver: Callable):
        """Set an async callable that returns a fresh WS URL (for Chrome restart scenarios)."""
        self._ws_url_resolver = resolver

    async def _notify_status(self, connected: bool):
        """Notify all status callbacks."""
        for cb in self._status_callbacks:
            try:
                result = cb(connected)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.warning(f"Status callback error: {e}")

    async def _reconnect(self):
        """Auto-reconnect with exponential backoff."""
        if self._reconnecting:
            return
        self._reconnecting = True
        logger.info("CDP auto-reconnect starting...")

        # 关闭旧 WebSocket，取消 pending futures
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
        for fut in self._pending.values():
            if not fut.done():
                fut.cancel()
        self._pending.clear()

        await self._notify_status(False)

        backoff = 1.0
        max_backoff = 30.0

        while self._reconnecting:
            try:
                # 获取 WS URL（可能 Chrome 重启了，URL 变了）
                ws_url = self.ws_url
                if self._ws_url_resolver:
                    try:
                        ws_url = await self._ws_url_resolver()
                    except Exception as e:
                        logger.warning(f"WS URL resolver failed: {e}")

                self.ws = await websockets.connect(
                    ws_url,
                    max_size=50 * 1024 * 1024,
                    ping_interval=20,
                    ping_timeout=10,
                )
                self.ws_url = ws_url
                self._connected = True
                self._reconnecting = False
                self._listen_task = asyncio.create_task(self._listen_loop())
                logger.info(f"CDP reconnected: {ws_url}")
                await self._notify_status(True)
                return

            except Exception as e:
                logger.warning(f"CDP reconnect failed: {e}, retrying in {backoff:.0f}s...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

        # _reconnecting 被 close() 设为 False，退出
        logger.info("CDP reconnect cancelled")
