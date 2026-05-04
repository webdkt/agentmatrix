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

from agentmatrix.desktop.signals import BrowserSignal

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

    - 按 agent_name 管理 agent input_queue
    - 根据 tab 归属路由事件到正确的 agent（BrowserSignal → input_queue）
    - 自动注入 bridge.js
    - 提供后端→前端事件推送
    """

    def __init__(self, cdp: CDPClient, tab_mgr: TabManager):
        self.cdp = cdp
        self.tab_mgr = tab_mgr
        self.active = False
        self._handlers_registered = False

        # 按 agent_name 索引的 agent input_queue
        self._agent_queues: dict[str, asyncio.Queue] = {}

    # ==========================================
    # 多 Agent queue 管理
    # ==========================================

    def register_agent_queue(self, agent_name: str, queue: asyncio.Queue):
        """注册一个 agent 的 input_queue。"""
        if queue is not None:
            self._agent_queues[agent_name] = queue
            logger.debug(f"Agent input_queue registered: {agent_name}")

    def unregister_agent(self, agent_name: str):
        """移除一个 agent 的 input_queue。"""
        self._agent_queues.pop(agent_name, None)

    def _find_agent_queue(self, agent_name: str) -> Optional[asyncio.Queue]:
        """根据 agent_name 找到其 input_queue。"""
        return self._agent_queues.get(agent_name)

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
        """确保指定 session 已注入 bridge.js。

        每次调用都执行注入，bridge.js 自身通过 window.__bh_bridge_loaded__
        做幂等检查，不会重复执行。
        """
        bridge_js = _get_bridge_js()
        try:
            await self.cdp.send(
                "Runtime.evaluate",
                {"expression": bridge_js},
                session_id=session_id,
            )
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

    async def set_agent_meta(self, session_id: str, agent_name: str, agent_session_id: str):
        """设置前端 tab 的 agent 元数据（bridge.js 注入后调用）。"""
        js = (
            f"window.__bh_agent_meta__ = {{"
            f"agent_name: {json.dumps(agent_name)}, "
            f"agent_session_id: {json.dumps(agent_session_id)}"
            f"}};"
        )
        try:
            await self.cdp.send(
                "Runtime.evaluate",
                {"expression": js},
                session_id=session_id,
            )
            logger.debug(f"Agent meta set: {agent_name}/{agent_session_id[:8]}...")
        except Exception as e:
            logger.debug(f"set_agent_meta failed: {e}")

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
        self.cdp.on_event("Target.targetCreated", self._on_target_created)
        self._handlers_registered = True

    def _on_console(self, params):
        """处理 console 事件，解析 __BH_EVENT__ → 路由 BrowserSignal 到 agent input_queue。"""
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

        # 前端元数据（bridge.js 注入时设置）
        agent_name = payload.pop("agent_name", "")
        agent_session_id = payload.pop("agent_session_id", "")

        meta_keys = {"type", "url", "title", "ts", "agent_name", "agent_session_id"}
        business_data = {k: v for k, v in payload.items() if k not in meta_keys}

        # 根据前端元数据或 tab 归属找 agent
        if not agent_name:
            cdp_session_id = params.get("_sessionId", "")
            agent_name = self._find_agent_for_tab(cdp_session_id)

        queue = self._find_agent_queue(agent_name)
        if not queue:
            logger.debug(f"No queue for browser event {event_type} (agent={agent_name})")
            return

        signal = BrowserSignal(
            agent_name=agent_name,
            agent_session_id=agent_session_id,
            event_type=event_type,
            url=url,
            title=title,
            data=business_data,
            cdp_session_id=params.get("_sessionId", ""),
        )
        # 从 session_id 反查 target_id
        cdp_session = params.get("_sessionId", "")
        if cdp_session:
            tab = self.tab_mgr.get_tab_by_session_sync(cdp_session)
            if tab:
                signal.target_id = tab.target_id
        try:
            queue.put_nowait(signal)
            logger.info(f"Browser event → {agent_name}: {event_type}")
        except Exception as e:
            logger.warning(f"Signal delivery failed: {e}")

    def _find_agent_for_tab(self, cdp_session_id: str) -> str:
        """根据 CDP session_id 找到 tab 所属的 agent_name。"""
        for agent_name in self._agent_queues:
            tabs = self.tab_mgr.get_agent_tabs_sync(agent_name)
            for tab in tabs:
                if tab.session_id == cdp_session_id:
                    return agent_name
        return ""

    def _on_page_loaded(self, params):
        """页面加载完成 → 注入 bridge.js + 重新设置 agent meta。

        页面导航后 JS 上下文销毁重建，bridge 和 agent meta 都会丢失，
        需要重新注入。bridge.js 自身有幂等检查，不会重复初始化。
        """
        if not self.active:
            return
        session_id = params.get("_sessionId", "")
        if not session_id:
            return
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._on_page_loaded_async(session_id))
        except RuntimeError:
            pass

    async def _on_page_loaded_async(self, session_id: str):
        """页面加载完成的异步处理：注入 bridge + 重新设置 agent meta。"""
        await self.ensure_bridge(session_id)
        tab = self.tab_mgr.get_tab_by_session_sync(session_id)
        if tab and tab.agent_name:
            await self.set_agent_meta(session_id, tab.agent_name, tab.agent_session_id)

    def _on_target_destroyed(self, params):
        """Tab 关闭 → 清理。"""
        target_id = params.get("targetId", "")
        if target_id:
            logger.debug(f"Tab closed: {target_id}")

    # ==========================================
    # 新 Tab 自动继承
    # ==========================================

    def _on_target_created(self, params):
        """处理浏览器创建的新 tab（如用户点击 target=_blank 链接）。

        通过 openerId 找到父 tab，自动继承其 agent_name 和 agent_session_id，
        然后注入 bridge.js + 设置 agent meta。
        """
        if not self.active:
            return

        info = params.get("targetInfo", {})
        target_id = info.get("targetId", "")
        target_type = info.get("type", "")
        opener_id = info.get("openerId", "")
        url = info.get("url", "")

        # 只处理 page 类型且有 opener 的 tab
        if target_type != "page" or not opener_id:
            return

        # 跳过已追踪的 tab
        if target_id in self.tab_mgr._tabs:
            return

        # 查找父 tab
        parent_tab = self.tab_mgr._tabs.get(opener_id)
        if not parent_tab or not parent_tab.agent_name:
            return

        agent_name = parent_tab.agent_name
        agent_session_id = parent_tab.agent_session_id

        logger.info(
            f"Auto-adopting new tab {target_id} from opener {opener_id} "
            f"(agent={agent_name}, url={url})"
        )

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(
                self._adopt_new_tab(target_id, agent_name, agent_session_id, url)
            )
        except RuntimeError:
            pass

    async def _adopt_new_tab(
        self, target_id: str, agent_name: str, agent_session_id: str, url: str
    ):
        """异步收养新 tab：attach → 注册 → 注入 bridge + meta。"""
        try:
            tab = await self.tab_mgr.adopt_tab(
                target_id, agent_name, agent_session_id, url
            )
            await self.ensure_bridge(tab.session_id)
            await self.set_agent_meta(
                tab.session_id, agent_name, agent_session_id
            )
            logger.info(
                f"New tab adopted: {target_id} → agent '{agent_name}'"
            )
        except Exception as e:
            logger.warning(f"Failed to adopt new tab {target_id}: {e}")

    async def start_target_discovery(self):
        """启用浏览器级 tab 发现，使 Target.targetCreated 事件开始触发。"""
        try:
            await self.cdp.send("Target.setDiscoverTargets", {"discover": True})
            logger.info("Target discovery enabled")
        except Exception as e:
            logger.warning(f"Failed to enable target discovery: {e}")
