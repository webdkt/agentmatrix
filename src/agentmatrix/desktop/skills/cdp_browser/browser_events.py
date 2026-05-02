"""
BrowserEventListener — 双向事件引擎（多 Agent 支持）。

前端→后端：
    监听 CDP console 事件，解析 __BH_EVENT__ 前缀，
    根据 tab 归属路由到对应 agent 的 signal_queue。

后端→前端：
    通过 emit_to_browser() 向前端推送事件，
    调用 window.__bh_on_event__(type, data)。

自动行为：
    页面加载完成时自动注入 bridge.js（通信协议）。
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from agentmatrix.core.signals import TextSignal

from .cdp_client import CDPClient
from .tab_manager import TabManager

logger = logging.getLogger(__name__)

# Bridge JS 的文件路径
_BRIDGE_JS_PATH = Path(__file__).parent / "interfaces" / "common" / "bridge.js"


def _load_bridge_js() -> str:
    """加载 bridge.js 内容。"""
    if _BRIDGE_JS_PATH.exists():
        return _BRIDGE_JS_PATH.read_text(encoding="utf-8")
    # 降级：内联最小 bridge
    return """
(function(){
    if(window.__bh_bridge_loaded__)return;
    window.__bh_bridge_loaded__=true;
    window.__bh_emit__=function(t,d){
        var p={type:t,ts:Date.now(),url:location.href,title:document.title};
        if(d)for(var k in d)p[k]=d[k];
        console.log('__BH_EVENT__ '+JSON.stringify(p));
    };
    window.__bh_on_event__=null;
})();
"""


_bridge_js_cache: Optional[str] = None


def _get_bridge_js() -> str:
    global _bridge_js_cache
    if _bridge_js_cache is None:
        _bridge_js_cache = _load_bridge_js()
    return _bridge_js_cache


class BrowserEventListener:
    """
    后台 CDP 事件监听器，支持多 Agent：

    - 按 agent_name 管理 signal_queue
    - 根据 tab 归属路由事件到正确的 agent
    - 自动注入 bridge.js
    - 提供后端→前端事件推送
    """

    def __init__(self, cdp: CDPClient, tab_mgr: TabManager):
        self.cdp = cdp
        self.tab_mgr = tab_mgr
        self.active = False
        self._handlers_registered = False

        # 已注入 bridge 的 session 集合
        self._bridged_sessions: set[str] = set()

        # 按 agent_name 索引的 signal_queue
        self._signal_queues: dict[str, asyncio.Queue] = {}

    # ==========================================
    # 多 Agent signal_queue 管理
    # ==========================================

    def register_queue(self, agent_name: str, queue: asyncio.Queue):
        """注册一个 agent 的 signal_queue。"""
        if queue is not None:
            self._signal_queues[agent_name] = queue
            logger.debug(f"Signal queue registered for agent: {agent_name}")

    def unregister_queue(self, agent_name: str):
        """移除一个 agent 的 signal_queue（MicroAgent 结束时调用）。"""
        self._signal_queues.pop(agent_name, None)

    def _find_queue_for_session(self, session_id: str) -> Optional[asyncio.Queue]:
        """根据 session_id 找到所属 agent 的 signal_queue。"""
        # 遍历 tab_manager 找到这个 session 属于哪个 tab
        for agent_name, queue in self._signal_queues.items():
            if queue is None:
                continue
            tabs = self.tab_mgr.get_agent_tabs_sync(agent_name)
            for tab in tabs:
                if tab.session_id == session_id:
                    return queue
        # 找不到归属，广播到所有活跃 queue
        for queue in self._signal_queues.values():
            if queue is not None:
                return queue
        return None

    # ==========================================
    # 生命周期
    # ==========================================

    def start(self):
        """启动事件监听。"""
        if self.active:
            return
        self.active = True
        self._register_handlers()
        logger.info("BrowserEventListener started")

    def stop(self):
        """停止事件监听。"""
        self.active = False
        logger.info("BrowserEventListener stopped")

    # ==========================================
    # 后端 → 前端
    # ==========================================

    async def emit_to_browser(self, session_id: str, event_type: str, data: dict = None):
        """向前端推送事件，调用 window.__bh_on_event__(type, data)。"""
        js = (
            f"if(window.__bh_on_event__)"
            f"window.__bh_on_event__({json.dumps(event_type)},{json.dumps(data or {})})"
        )
        try:
            await self.cdp.send(
                "Runtime.evaluate",
                {"expression": js},
                session_id=session_id,
            )
        except Exception as e:
            logger.debug(f"emit_to_browser failed: {e}")

    # ==========================================
    # Bridge 注入
    # ==========================================

    async def ensure_bridge(self, session_id: str):
        """确保指定 session 已注入 bridge.js。"""
        if session_id in self._bridged_sessions:
            return
        bridge_js = _get_bridge_js()
        try:
            await self.cdp.send(
                "Runtime.evaluate",
                {"expression": bridge_js},
                session_id=session_id,
            )
            self._bridged_sessions.add(session_id)
            logger.debug(f"Bridge JS injected: {session_id[:12]}...")
        except Exception as e:
            logger.debug(f"Bridge JS inject failed: {e}")

    async def inject_js(self, session_id: str, js: str):
        """注入 JS 到指定 tab。"""
        await self.ensure_bridge(session_id)
        try:
            await self.cdp.send(
                "Runtime.evaluate",
                {"expression": js},
                session_id=session_id,
            )
        except Exception as e:
            logger.warning(f"JS inject failed: {e}")

    # ==========================================
    # CDP 事件处理
    # ==========================================

    def _register_handlers(self):
        """注册 CDP 事件处理器。"""
        if self._handlers_registered:
            return
        self.cdp.on_event("Runtime.consoleAPICalled", self._on_console)
        self.cdp.on_event("Page.loadEventFired", self._on_page_loaded)
        self.cdp.on_event("Target.targetDestroyed", self._on_target_destroyed)
        self._handlers_registered = True

    def _on_console(self, params):
        """处理 console 事件，解析 __BH_EVENT__ → 路由到正确的 agent signal_queue。"""
        if not self.active:
            return

        args = params.get("args", [])
        if not args:
            return

        val = args[0].get("value", "")
        if not isinstance(val, str) or not val.startswith("__BH_EVENT__ "):
            return

        try:
            payload = json.loads(val[len("__BH_EVENT__ "):])
        except (json.JSONDecodeError, KeyError):
            return

        event_type = payload.pop("type", "unknown")
        url = payload.pop("url", "")
        title = payload.pop("title", "")
        ts = payload.pop("ts", 0)

        meta_keys = {"type", "url", "title", "ts"}
        business_data = {k: v for k, v in payload.items() if k not in meta_keys}

        # 根据 session_id 路由到正确的 agent
        session_id = params.get("_sessionId", "")
        queue = self._find_queue_for_session(session_id)
        if not queue:
            logger.debug(f"No queue for browser event {event_type} (session={session_id[:12]}...)")
            return

        text = self._format_signal_text(event_type, url, title, business_data)
        signal = TextSignal(text=text, type_name="browser_event")
        try:
            queue.put_nowait(signal)
            logger.info(f"Browser event → signal: {event_type}")
        except Exception as e:
            logger.warning(f"Signal delivery failed: {e}")

    def _on_page_loaded(self, params):
        """页面加载完成 → 注入 bridge.js。"""
        if not self.active:
            return
        session_id = params.get("_sessionId", "")
        if not session_id:
            return
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.ensure_bridge(session_id))
        except RuntimeError:
            pass

    def _on_target_destroyed(self, params):
        """Tab 关闭 → 清理 bridge 记录。"""
        target_id = params.get("targetId", "")
        if target_id:
            logger.debug(f"Tab closed: {target_id}")

    def _format_signal_text(self, event_type: str, url: str, title: str, data: dict) -> str:
        """格式化浏览器事件为 LLM 可读文本。"""
        lines = [f"[浏览器事件] {event_type}"]
        if url:
            display_url = url[:80] + "..." if len(url) > 80 else url
            lines.append(f"  页面: {display_url}")
        if title:
            lines.append(f"  标题: {title}")
        for k, v in data.items():
            lines.append(f"  {k}: {v}")
        return "\n".join(lines)
