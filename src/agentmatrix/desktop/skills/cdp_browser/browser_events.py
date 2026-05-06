"""
BrowserEventListener — 双向事件引擎（多 Agent 支持）。

前端→后端：
    监听 CDP console 事件，解析 __BH_EVENT__ 前缀，
    根据 tab 归属路由到对应 agent 的 signal_queue。

后端→前端：
    通过 emit_to_browser() 向前端推送事件，
    调用 window.__bh_on_event__(type, data)。

自动行为：
    页面加载完成时自动注入 bridge.js（通信协议）+ agent_button.js（前端 UI）。
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

# JS 文件目录
_JS_COMMON_DIR = Path(__file__).parent / "interfaces" / "common"
_BRIDGE_JS_PATH = _JS_COMMON_DIR / "bridge.js"
_AGENT_BUTTON_CSS_PATH = _JS_COMMON_DIR / "agent_button.css"
_AGENT_BUTTON_JS_FILES = [
    _JS_COMMON_DIR / "agent_button.js",           # IIFE 开头 + 共享状态 + helpers
    _JS_COMMON_DIR / "agent_button_splash.js",     # 发送过渡动画
    _JS_COMMON_DIR / "agent_button_speech.js",     # Agent 说话气泡
    _JS_COMMON_DIR / "agent_button_indicator.js",  # 指示器（十字准心）
    _JS_COMMON_DIR / "agent_button_instruct.js",   # 给AI指示（居中输入框）
    _JS_COMMON_DIR / "agent_button_range.js",      # 范围选择器
    _JS_COMMON_DIR / "agent_button_dialog.js",     # 提问对话框
    _JS_COMMON_DIR / "agent_button_init.js",       # DOM 构建 + 事件绑定 + IIFE 结尾
]


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


def _load_agent_button_js() -> str:
    """加载并拼接 agent_button 全部模块。

    拼接顺序：
    1. CSS → var __bh_css__ = "...";
    2. agent_button.js — IIFE 开头 + 共享状态 + helpers
    3. agent_button_splash.js — 发送过渡动画
    4. agent_button_speech.js — Agent 说话气泡
    5. agent_button_indicator.js — 指示器（十字准心）
    6. agent_button_range.js — 范围选择器
    7. agent_button_dialog.js — 提问对话框
    8. agent_button_init.js — DOM 构建 + 事件绑定 + IIFE 结尾

    所有 JS 文件在同一 IIFE 闭包内共享变量。
    """
    parts = []

    # CSS → JS 变量声明
    if _AGENT_BUTTON_CSS_PATH.exists():
        css_content = _AGENT_BUTTON_CSS_PATH.read_text(encoding="utf-8")
        parts.append(f"var __bh_css__ = {json.dumps(css_content)};")

    # JS 模块文件
    for js_path in _AGENT_BUTTON_JS_FILES:
        if js_path.exists():
            parts.append(js_path.read_text(encoding="utf-8"))

    return "\n".join(parts)


_bridge_js_cache: Optional[str] = None
_agent_button_js_cache: Optional[str] = None


def _get_bridge_js() -> str:
    global _bridge_js_cache
    if _bridge_js_cache is None:
        _bridge_js_cache = _load_bridge_js()
    return _bridge_js_cache


def _get_agent_button_js() -> str:
    global _agent_button_js_cache
    if _agent_button_js_cache is None:
        _agent_button_js_cache = _load_agent_button_js()
    return _agent_button_js_cache


class BrowserEventListener:
    """
    后台 CDP 事件监听器，支持多 Agent：

    - 按 agent_name 管理 agent input_queue
    - 根据 tab 归属路由事件到正确的 agent（BrowserSignal → input_queue）
    - 自动注入 bridge.js
    - 提供后端→前端事件推送
    """

    def __init__(self, cdp: CDPClient, tab_mgr: TabManager,
                 on_current_tab_change=None):
        self.cdp = cdp
        self.tab_mgr = tab_mgr
        self.active = False
        self._handlers_registered = False
        self._on_current_tab_change = on_current_tab_change

        # 按 agent_name 索引的 agent input_queue
        self._agent_queues: dict[str, asyncio.Queue] = {}
        # 已注册自动注入 bridge 的 session 集合
        self._auto_inject_sessions: set = set()
        # 无主 tab（无 openerId 的新 tab，等待分配）
        self._orphan_tabs: set = set()  # target_id 集合
        # orphan tab 的 session_id → target_id 映射（用于回传选择结果）
        self._orphan_sessions: dict[str, str] = {}

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
        """确保指定 session 已注入 bridge.js + agent_button.js。

        双重注入策略：
        1. Page.addScriptToEvaluateOnNewDocument — 注册自动注入，每次新文档加载时 Chrome 自动执行
        2. Runtime.evaluate — 立即注入当前页面（fallback）

        bridge.js 和 agent_button.js 自身都有幂等检查，不会重复执行。
        """
        bridge_js = _get_bridge_js()
        agent_btn_js = _get_agent_button_js()

        # 注册自动注入（每个 session 只注册一次）
        if session_id not in self._auto_inject_sessions:
            try:
                # bridge.js + agent_button.js 合并为一个脚本注册
                combined = bridge_js + "\n" + agent_btn_js if agent_btn_js else bridge_js
                await self.cdp.send(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": combined},
                    session_id=session_id,
                )
                self._auto_inject_sessions.add(session_id)
            except Exception as e:
                logger.debug(f"addScriptToEvaluateOnNewDocument failed: {e}")

        # 立即注入当前页面（fallback，处理页面已加载的情况）
        try:
            await self.cdp.send(
                "Runtime.evaluate",
                {"expression": bridge_js},
                session_id=session_id,
            )
        except Exception as e:
            logger.debug(f"Bridge JS inject failed: {e}")

        # 注入 agent_button.js
        if agent_btn_js:
            try:
                await self.cdp.send(
                    "Runtime.evaluate",
                    {"expression": agent_btn_js},
                    session_id=session_id,
                )
            except Exception as e:
                logger.debug(f"Agent button JS inject failed: {e}")

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
        self.cdp.on_event("Target.targetInfoChanged", self._on_target_info_changed)
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

        # 从 session_id 反查 target_id
        cdp_session = params.get("_sessionId", "")
        target_id = ""
        if cdp_session:
            tab = self.tab_mgr.get_tab_by_session_sync(cdp_session)
            if tab:
                target_id = tab.target_id

        # ── tab_activated: 只更新 current_tab，不进 queue ──
        if event_type == "tab_activated":
            if agent_name and target_id and self._on_current_tab_change:
                self._on_current_tab_change(agent_name, target_id)
                logger.debug(f"tab_activated → {agent_name}: {target_id}")
            return

        # ── tab_assign_choice: orphan tab 分配选择 ──
        if event_type == "tab_assign_choice":
            chosen_agent = business_data.get("agent_name", "")
            # orphan tab 不在 tab_mgr 中，需要从 _orphan_sessions 查找
            if not target_id:
                target_id = self._orphan_sessions.pop(cdp_session, "")
            self._handle_orphan_choice(target_id, chosen_agent)
            return

        # ── 所有其他事件: 更新 current_tab + 进 queue ──
        if agent_name and target_id and self._on_current_tab_change:
            self._on_current_tab_change(agent_name, target_id)

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
            cdp_session_id=cdp_session,
            target_id=target_id,
        )
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
        """页面加载完成的异步处理：注入 bridge + 重新设置 agent meta + 通知 agent。"""
        await self.ensure_bridge(session_id)
        tab = self.tab_mgr.get_tab_by_session_sync(session_id)
        if tab and tab.agent_name:
            await self.set_agent_meta(session_id, tab.agent_name, tab.agent_session_id)
            # 获取页面最新 URL 和 title
            url, title = await self._get_page_info(session_id)
            if url:
                tab.url = url
                tab.title = title
            self._emit_to_agent(tab.agent_name, BrowserSignal(
                agent_name=tab.agent_name,
                agent_session_id=tab.agent_session_id,
                event_type="page_navigated",
                url=url or tab.url,
                title=title or tab.title,
                data={"target_id": tab.target_id},
                cdp_session_id=session_id,
            ))

    def _on_target_destroyed(self, params):
        """Tab 关闭 → 通知 agent + 清理。"""
        target_id = params.get("targetId", "")
        if not target_id:
            return

        # 清理 orphan tab 记录
        self._orphan_tabs.discard(target_id)

        tab = self.tab_mgr._tabs.get(target_id)
        if tab and tab.agent_name:
            agent_name = tab.agent_name
            self._emit_to_agent(agent_name, BrowserSignal(
                agent_name=agent_name,
                agent_session_id=tab.agent_session_id,
                event_type="tab_closed",
                url=tab.url,
                data={"target_id": target_id},
            ))
            # 如果关的是 current_tab，切换到下一个
            if self._on_current_tab_change:
                remaining = self.tab_mgr.get_agent_tabs_sync(agent_name)
                other = [t for t in remaining if t.target_id != target_id]
                if other:
                    self._on_current_tab_change(agent_name, other[0].target_id)
        logger.debug(f"Tab closed: {target_id}")

    # ==========================================
    # 新 Tab 自动继承
    # ==========================================

    def _on_target_created(self, params):
        """处理浏览器创建的新 tab。

        两种情况：
        1. 有 openerId → 自动继承父 tab 的 agent（原有逻辑）
        2. 无 openerId → 记录为 orphan tab，等待分配
        """
        if not self.active:
            return

        info = params.get("targetInfo", {})
        target_id = info.get("targetId", "")
        target_type = info.get("type", "")
        opener_id = info.get("openerId", "")
        url = info.get("url", "")

        # 只处理 page 类型
        if target_type != "page":
            return

        # 跳过已追踪的 tab
        if target_id in self.tab_mgr._tabs:
            return

        # ── 情况 1：有 openerId → 继承父 tab ──
        if opener_id:
            parent_tab = self.tab_mgr._tabs.get(opener_id)
            if parent_tab and parent_tab.agent_name:
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
                return

        # ── 情况 2：无 openerId → orphan tab，记录等待分配 ──
        logger.info(f"Orphan tab detected: {target_id} (url={url}), waiting for navigation")
        self._orphan_tabs.add(target_id)

    async def _adopt_new_tab(
        self, target_id: str, agent_name: str, agent_session_id: str, url: str
    ):
        """异步收养新 tab：attach → 注册 → 注入 bridge + meta + 通知 agent。"""
        try:
            tab = await self.tab_mgr.adopt_tab(
                target_id, agent_name, agent_session_id, url
            )
            await self.ensure_bridge(tab.session_id)
            await self.set_agent_meta(
                tab.session_id, agent_name, agent_session_id
            )
            # 获取新 tab 的实际 URL
            actual_url, title = await self._get_page_info(tab.session_id)
            if actual_url:
                tab.url = actual_url
                tab.title = title
            self._emit_to_agent(agent_name, BrowserSignal(
                agent_name=agent_name,
                agent_session_id=agent_session_id,
                event_type="tab_opened",
                url=actual_url or url,
                title=title or "",
                data={"target_id": target_id},
                cdp_session_id=tab.session_id,
            ))
            logger.info(
                f"New tab adopted: {target_id} → agent '{agent_name}'"
            )
        except Exception as e:
            logger.warning(f"Failed to adopt new tab {target_id}: {e}")

    # ==========================================
    # Orphan tab 分配
    # ==========================================

    def _on_target_info_changed(self, params):
        """Tab URL 变化 → 检测 orphan tab 是否导航到真实页面。"""
        if not self.active:
            return

        info = params.get("targetInfo", {})
        target_id = info.get("targetId", "")
        url = info.get("url", "")

        if target_id not in self._orphan_tabs:
            return

        # 只处理 http/https URL（跳过 about:blank, chrome:// 等）
        if not url.startswith(("http://", "https://")):
            return

        logger.info(f"Orphan tab {target_id} navigated to {url}, triggering assignment")

        # 从 orphan 集合移除（避免重复触发）
        self._orphan_tabs.discard(target_id)

        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._assign_orphan_tab(target_id, url))
        except RuntimeError:
            pass

    async def _assign_orphan_tab(self, target_id: str, url: str):
        """分配 orphan tab：单 agent 自动分配，多 agent 弹出选择对话框。"""
        # 获取活跃 agent 列表
        active_agents = list(self._agent_queues.keys())
        if not active_agents:
            logger.debug(f"No active agents, orphan tab {target_id} unassigned")
            return

        try:
            if len(active_agents) == 1:
                # 单 agent → 自动分配
                agent_name = active_agents[0]
                await self._finalize_orphan_assignment(target_id, agent_name, url)
            else:
                # 多 agent → 注入选择对话框
                await self._show_orphan_assign_dialog(target_id, url, active_agents)
        except Exception as e:
            logger.warning(f"Failed to assign orphan tab {target_id}: {e}")

    async def _show_orphan_assign_dialog(self, target_id: str, url: str, agents: list):
        """在 orphan tab 中注入选择对话框，让用户选择分配给哪个 agent。"""
        # 1. attach 到 tab
        session_id = await self.cdp.attach_to_target(target_id)
        await self.cdp.enable_domains(session_id)
        self._orphan_sessions[session_id] = target_id

        # 2. 构造 agent 列表 JS 变量 + 最小 bridge + 对话框
        agents_json = json.dumps([{"name": name} for name in agents])

        # 最小 bridge（只有 emit 能力）
        minimal_bridge = (
            "if(!window.__bh_emit__){"
            "window.__bh_emit__=function(t,d){"
            "var p={type:t,ts:Date.now()};"
            "if(d)for(var k in d)p[k]=d[k];"
            "console.log('__BH_EVENT__ '+JSON.stringify(p));"
            "};}"
        )

        # 选择对话框 JS
        dialog_js = (
            "(function(){"
            "if(window.__bh_assign_dialog_loaded__)return;"
            "window.__bh_assign_dialog_loaded__=true;"
            "var agents=" + agents_json + ";"
            "var o=document.createElement('div');"
            "o.id='__bh_assign_dialog__';"
            "o.style.cssText='position:fixed;top:0;left:0;width:100%;height:100%;"
            "z-index:2147483646;background:rgba(0,0,0,0.3);display:flex;"
            "align-items:center;justify-content:center;"
            "font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;';"
            "var c=document.createElement('div');"
            "c.style.cssText='background:white;border-radius:16px;padding:24px;"
            "box-shadow:0 8px 32px rgba(0,0,0,0.2);max-width:400px;width:90%;';"
            "c.innerHTML='<h3 style=\"margin:0 0 8px;font-size:16px;color:#1a1a2e;\">"
            "分配此页面</h3>"
            "<p style=\"margin:0 0 16px;font-size:13px;color:#666;\">"
            "选择要分配的 Agent：</p>';"
            "agents.forEach(function(a){"
            "var b=document.createElement('button');"
            "b.textContent=a.name;"
            "b.style.cssText='display:block;width:100%;padding:12px;margin-bottom:8px;"
            "border:1px solid rgba(0,0,0,0.12);border-radius:10px;background:white;"
            "cursor:pointer;font-size:14px;text-align:left;font-family:inherit;';"
            "b.onmouseover=function(){b.style.background='#f0f0ff';};"
            "b.onmouseout=function(){b.style.background='white';};"
            "b.onclick=function(){"
            "window.__bh_emit__('tab_assign_choice',{agent_name:a.name});"
            "o.remove();};"
            "c.appendChild(b);});"
            "var x=document.createElement('button');"
            "x.textContent='不分配';"
            "x.style.cssText='display:block;width:100%;padding:12px;border:none;"
            "border-radius:10px;background:#f5f5f5;cursor:pointer;font-size:13px;"
            "color:#666;font-family:inherit;';"
            "x.onclick=function(){"
            "window.__bh_emit__('tab_assign_choice',{agent_name:''});"
            "o.remove();};"
            "c.appendChild(x);"
            "o.appendChild(c);"
            "document.body.appendChild(o);"
            "})();"
        )

        full_js = minimal_bridge + dialog_js

        # 3. 等页面 ready 再注入（最多等 3 秒）
        for _ in range(6):
            await asyncio.sleep(0.5)
            try:
                result = await self.cdp.send(
                    "Runtime.evaluate",
                    {
                        "expression": "document.readyState",
                        "returnByValue": True,
                    },
                    session_id=session_id,
                    timeout=2,
                )
                ready = result.get("result", {}).get("value", "")
                if ready in ("interactive", "complete"):
                    break
            except Exception:
                pass

        await self.cdp.send(
            "Runtime.evaluate",
            {"expression": full_js},
            session_id=session_id,
        )
        logger.info(f"Orphan assign dialog injected for {target_id}")

    def _handle_orphan_choice(self, target_id: str, chosen_agent: str):
        """处理用户对 orphan tab 的分配选择（由 _on_console 调用）。"""
        if not chosen_agent:
            logger.info(f"User cancelled orphan tab assignment for {target_id}")
            # 清理 orphan_sessions 中对应的条目
            self._orphan_tabs.discard(target_id)
            return

        logger.info(f"User assigned orphan tab {target_id} to agent '{chosen_agent}'")
        try:
            loop = asyncio.get_event_loop()
            # 需要获取 URL，但 orphan tab 不在 tab_mgr 中
            # 从 CDP target info 获取
            loop.create_task(self._finalize_orphan_assignment(target_id, chosen_agent, ""))
        except RuntimeError:
            pass

    async def _finalize_orphan_assignment(self, target_id: str, agent_name: str, url: str):
        """完成 orphan tab 的分配：adopt + 注入 bridge + 设置 meta + 通知 agent。"""
        # 获取该 agent 的最新 session_id（用于继承）
        agent_session_id = ""
        agent_tabs = self.tab_mgr.get_agent_tabs_sync(agent_name)
        if agent_tabs:
            agent_session_id = agent_tabs[0].agent_session_id

        # adopt tab
        tab = await self.tab_mgr.adopt_tab(
            target_id, agent_name, agent_session_id, url
        )

        # 获取实际 URL
        actual_url, title = await self._get_page_info(tab.session_id)
        if actual_url:
            tab.url = actual_url
            tab.title = title

        # 注入 bridge + agent_button + 设置 meta
        await self.ensure_bridge(tab.session_id)
        await self.set_agent_meta(tab.session_id, agent_name, agent_session_id)

        # 更新 current_tab
        if self._on_current_tab_change:
            self._on_current_tab_change(agent_name, target_id)

        # 通知 agent
        self._emit_to_agent(agent_name, BrowserSignal(
            agent_name=agent_name,
            agent_session_id=agent_session_id,
            event_type="tab_opened",
            url=actual_url or url,
            title=title or "",
            data={"target_id": target_id},
            cdp_session_id=tab.session_id,
        ))

        logger.info(f"Orphan tab {target_id} assigned to agent '{agent_name}'")

    # ==========================================
    # 辅助方法
    # ==========================================

    async def _get_page_info(self, session_id: str) -> tuple:
        """获取页面的 URL 和 title。返回 (url, title)。"""
        try:
            result = await self.cdp.send(
                "Runtime.evaluate",
                {
                    "expression": "JSON.stringify({url: location.href, title: document.title})",
                    "returnByValue": True,
                },
                session_id=session_id,
                timeout=5,
            )
            import json as _json
            info = _json.loads(result.get("result", {}).get("value", "{}"))
            return info.get("url", ""), info.get("title", "")
        except Exception:
            return "", ""

    def _emit_to_agent(self, agent_name: str, signal):
        """向指定 agent 的 input_queue 发送信号。"""
        queue = self._find_agent_queue(agent_name)
        if queue:
            try:
                queue.put_nowait(signal)
            except Exception as e:
                logger.warning(f"Signal delivery failed: {e}")

    async def start_target_discovery(self):
        """启用浏览器级 tab 发现，使 Target.targetCreated 事件开始触发。"""
        try:
            await self.cdp.send("Target.setDiscoverTargets", {"discover": True})
            logger.info("Target discovery enabled")
        except Exception as e:
            logger.warning(f"Failed to enable target discovery: {e}")

    # ==========================================
    # 重连后恢复
    # ==========================================

    async def resubscribe_all(self):
        """重连后对所有已知 tab 重新 attach、启用 domain、注入 bridge。"""
        logger.info("Resubscribing all tabs after reconnection...")
        self._auto_inject_sessions.clear()  # 重连后 session_id 全部失效
        self._orphan_tabs.clear()
        self._orphan_sessions.clear()
        await self.start_target_discovery()

        dead_tabs = []
        for target_id, tab in list(self.tab_mgr._tabs.items()):
            try:
                # 重新 attach 获取新 session_id
                new_session_id = await self.cdp.attach_to_target(target_id)
                self.tab_mgr.update_session_id(target_id, new_session_id)
                await self.cdp.enable_domains(new_session_id)
                await self.ensure_bridge(new_session_id)
                if tab.agent_name:
                    await self.set_agent_meta(
                        new_session_id, tab.agent_name, tab.agent_session_id
                    )
                logger.debug(f"Resubscribed tab {target_id}")
            except Exception as e:
                logger.warning(f"Failed to resubscribe tab {target_id}: {e}")
                dead_tabs.append(target_id)

        # 清理失效的 tab
        for target_id in dead_tabs:
            tab = self.tab_mgr._tabs.pop(target_id, None)
            if tab:
                agent_tabs = self.tab_mgr._agent_tabs.get(tab.agent_name)
                if agent_tabs:
                    agent_tabs.discard(target_id)

        if dead_tabs:
            logger.info(f"Removed {len(dead_tabs)} dead tabs after reconnect")
        logger.info(f"Resubscribed {len(self.tab_mgr._tabs)} tabs")

    async def notify_connection_status(self, connected: bool):
        """向所有 tab 前端推送连接状态。"""
        status = "connected" if connected else "disconnected"
        for tab in list(self.tab_mgr._tabs.values()):
            if tab.session_id:
                try:
                    await self.emit_to_browser(
                        tab.session_id,
                        "connection_status",
                        {"connected": connected},
                    )
                except Exception:
                    pass  # 发送失败不影响重连流程
