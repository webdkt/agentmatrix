"""
CDP Browser Skill — 浏览器自动化，支持前端 Interface 注入和双向事件。

Agent Actions:
- open_browser()              → 启动/连接浏览器
- open_url(url)               → 打开 URL（自动注入通信桥接）
- list_tabs()                 → 列出当前 agent 的 tabs
- close_tab(target_id)        → 关闭 tab
- switch_to_tab(target_id)    → 切换 tab
- show_interface(name)        → 注入前端 interface

设计要点：
- Chrome/CDP/TabManager/EventListener 是进程级单例（一个 Chrome 进程）
- Tab 按 agent_name 隔离（多 Agent 各自管理自己的 tabs）
- _agent_current_tab 按 agent_name 索引，跨 MicroAgent 实例保持
- BrowserEventListener 按 agent_name 路由事件到正确的 signal_queue
"""

import asyncio
import json
import logging
import os
from typing import Optional
from pathlib import Path

from agentmatrix.core.action import register_action

from .cdp_client import CDPClient
from .chrome_manager import ChromeManager
from .tab_manager import TabManager, TabInfo
from .browser_events import BrowserEventListener
from .interfaces import load_interface, list_interfaces

logger = logging.getLogger(__name__)

# ── 进程级单例（一个 Chrome 实例服务所有 Agent）─────────────

_chrome_manager: Optional[ChromeManager] = None
_cdp_client: Optional[CDPClient] = None
_tab_manager: Optional[TabManager] = None
_event_listener: Optional[BrowserEventListener] = None
_init_lock = asyncio.Lock()

# ── Agent 级状态（按 agent_name 索引，跨 MicroAgent 保持）──

# 每个 agent 的当前 tab
_agent_current_tab: dict[str, TabInfo] = {}


async def _get_shared_infra(profile_dir: str, port: int = 9222):
    """获取或创建共享的 Chrome + CDP + TabManager 基础设施。"""
    global _chrome_manager, _cdp_client, _tab_manager, _event_listener

    async with _init_lock:
        if _cdp_client and _cdp_client._connected:
            return _cdp_client, _tab_manager, _event_listener

        _chrome_manager = ChromeManager(profile_dir=profile_dir, port=port)
        ws_url = await _chrome_manager.ensure_started()

        _cdp_client = CDPClient(ws_url)
        await _cdp_client.connect()

        _tab_manager = TabManager(_cdp_client)

        _event_listener = BrowserEventListener(_cdp_client, _tab_manager)

        return _cdp_client, _tab_manager, _event_listener


# ── Skill Mixin ───────────────────────────────────────────

class Cdp_browserSkillMixin:
    """
    CDP Browser Skill — 浏览器自动化 + 前端 Interface 注入。

    多 Agent 支持：
    - 所有 agent 共享一个 Chrome 实例
    - tab 按 agent_name 隔离
    - 浏览器事件按 tab 归属路由到正确的 agent signal_queue
    """

    _skill_description = "浏览器自动化：打开页面、管理 tab、注入前端 interface，支持双向事件通信"

    def _agent_name(self) -> str:
        return getattr(self.root_agent, "name", "default")

    def _get_current_tab(self) -> Optional[TabInfo]:
        """获取当前 agent 的活动 tab（跨 MicroAgent 保持）。"""
        return _agent_current_tab.get(self._agent_name())

    def _set_current_tab(self, tab: Optional[TabInfo]):
        """设置当前 agent 的活动 tab。"""
        name = self._agent_name()
        if tab:
            _agent_current_tab[name] = tab
        else:
            _agent_current_tab.pop(name, None)

    async def _ensure_browser(self):
        """确保浏览器已启动，注册当前 MicroAgent 的 signal_queue。"""
        if _cdp_client and _cdp_client._connected:
            # 已连接 → 只需注册 signal_queue
            if _event_listener and self.signal_queue:
                _event_listener.register_queue(self._agent_name(), self.signal_queue)
                _event_listener.start()
            return

        agent_name = self._agent_name()
        try:
            workspace = self.root_agent.runtime.paths.get_workspace(agent_name)
            profile_dir = str(Path(workspace) / ".cdp_browser_profile")
        except Exception:
            profile_dir = "/tmp/cdp_browser_profile"

        port = int(os.environ.get("CDP_BROWSER_PORT", "9222"))

        cdp, tab_mgr, listener = await _get_shared_infra(profile_dir, port)

        # 注册 signal_queue
        if listener and self.signal_queue:
            listener.register_queue(self._agent_name(), self.signal_queue)
            listener.start()

    # ==========================================
    # Actions
    # ==========================================

    @register_action(
        short_desc="open_browser()",
        description="启动浏览器并建立 CDP 连接。如果浏览器已在运行则直接连接。"
                    "自动开始监听前端事件。幂等操作，可重复调用。",
    )
    async def open_browser(self) -> str:
        """启动/连接浏览器。"""
        await self._ensure_browser()
        agent_name = self._agent_name()

        # 确保至少有一个 tab
        tabs = await _tab_manager.get_agent_tabs(agent_name)
        if not tabs:
            tab = await _tab_manager.create_tab(agent_name)
            self._set_current_tab(tab)
            if _event_listener:
                await _event_listener.ensure_bridge(tab.session_id)
        else:
            # 恢复之前的 current_tab，或用第一个
            if not self._get_current_tab():
                self._set_current_tab(tabs[0])

        tab = self._get_current_tab()
        return json.dumps({
            "status": "ok",
            "message": "浏览器已就绪",
            "tab_count": len(tabs) if tabs else 1,
            "current_tab": tab.target_id if tab else "",
        }, ensure_ascii=False)

    @register_action(
        short_desc="open_url(url)",
        description="在新的浏览器 tab 中打开指定 URL。"
                    "自动注入通信桥接 JS，使前端能与后端通信。",
        param_infos={"url": "要打开的 URL（如 https://github.com）"},
    )
    async def open_url(self, url: str) -> str:
        """打开 URL。"""
        await self._ensure_browser()
        agent_name = self._agent_name()

        tab = await _tab_manager.create_tab(agent_name, url)
        self._set_current_tab(tab)

        try:
            await _cdp_client.send(
                "Page.enable",
                session_id=tab.session_id,
                timeout=5,
            )
            await _cdp_client.send(
                "Page.navigate",
                {"url": url},
                session_id=tab.session_id,
                timeout=30,
            )

            await asyncio.sleep(1)

            if _event_listener:
                await _event_listener.ensure_bridge(tab.session_id)

            tab = await _tab_manager.refresh_tab_info(tab.target_id)
            if tab:
                self._set_current_tab(tab)

            return json.dumps({
                "status": "ok",
                "target_id": tab.target_id if tab else "",
                "url": tab.url if tab else url,
                "title": tab.title if tab else "",
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
                "target_id": tab.target_id,
            }, ensure_ascii=False)

    @register_action(
        short_desc="list_tabs()",
        description="列出当前 agent 的所有浏览器 tab，包括 tab ID、URL 和标题。",
    )
    async def list_tabs(self) -> str:
        """列出 tabs。"""
        await self._ensure_browser()
        agent_name = self._agent_name()
        tabs = await _tab_manager.get_agent_tabs(agent_name)
        current = self._get_current_tab()

        result = []
        for tab in tabs:
            result.append({
                "target_id": tab.target_id,
                "url": tab.url,
                "title": tab.title,
                "is_current": current and tab.target_id == current.target_id,
            })

        return json.dumps({
            "tab_count": len(result),
            "tabs": result,
        }, ensure_ascii=False)

    @register_action(
        short_desc="close_tab(target_id)",
        description="关闭指定的浏览器 tab。使用 list_tabs() 获取可用的 tab ID。",
        param_infos={"target_id": "要关闭的 tab 的 target_id"},
    )
    async def close_tab(self, target_id: str) -> str:
        """关闭 tab。"""
        await self._ensure_browser()
        agent_name = self._agent_name()

        tab = await _tab_manager.get_tab(target_id)
        if not tab:
            return json.dumps({
                "status": "error",
                "error": f"Tab {target_id} 不存在",
            }, ensure_ascii=False)

        if tab.agent_name != agent_name:
            return json.dumps({
                "status": "error",
                "error": f"Tab {target_id} 不属于当前 agent",
            }, ensure_ascii=False)

        await _tab_manager.close_tab(target_id)

        current = self._get_current_tab()
        if current and current.target_id == target_id:
            tabs = await _tab_manager.get_agent_tabs(agent_name)
            self._set_current_tab(tabs[0] if tabs else None)

        return json.dumps({"status": "ok"}, ensure_ascii=False)

    @register_action(
        short_desc="switch_to_tab(target_id)",
        description="切换到指定的浏览器 tab（激活并设为当前 tab）。"
                    "使用 list_tabs() 获取可用的 tab ID。",
        param_infos={"target_id": "要切换到的 tab 的 target_id"},
    )
    async def switch_to_tab(self, target_id: str) -> str:
        """切换 tab。"""
        await self._ensure_browser()
        agent_name = self._agent_name()

        tab = await _tab_manager.get_tab(target_id)
        if not tab:
            return json.dumps({
                "status": "error",
                "error": f"Tab {target_id} 不存在。使用 list_tabs() 查看可用 tab。",
            }, ensure_ascii=False)

        if tab.agent_name != agent_name:
            return json.dumps({
                "status": "error",
                "error": f"Tab {target_id} 不属于当前 agent",
            }, ensure_ascii=False)

        try:
            await _cdp_client.activate_target(target_id)

            if not tab.session_id:
                tab.session_id = await _cdp_client.attach_to_target(target_id)
                await _cdp_client.enable_domains(tab.session_id)

            if _event_listener:
                await _event_listener.ensure_bridge(tab.session_id)

            self._set_current_tab(tab)

            tab = await _tab_manager.refresh_tab_info(target_id)
            if tab:
                self._set_current_tab(tab)

            return json.dumps({
                "status": "ok",
                "target_id": tab.target_id if tab else target_id,
                "url": tab.url if tab else "",
                "title": tab.title if tab else "",
            }, ensure_ascii=False)

        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
            }, ensure_ascii=False)

    @register_action(
        short_desc="show_interface(name)",
        description="在当前页面注入一个前端 interface。"
                    "Interface 是预置的前端应用，提供各种交互 UI。"
                    "加载后的 interface 会通过事件与后端通信。",
        param_infos={"name": "Interface 名称（如 'browser_learning'）"},
    )
    async def show_interface(self, name: str) -> str:
        """注入前端 interface。"""
        await self._ensure_browser()
        tab = self._get_current_tab()

        if not tab:
            return json.dumps({
                "status": "error",
                "error": "没有活动的 tab。请先使用 open_url() 打开页面。",
            }, ensure_ascii=False)

        js = load_interface(name)
        if not js:
            available = [i["name"] for i in list_interfaces()]
            return json.dumps({
                "status": "error",
                "error": f"Interface '{name}' 不存在",
                "available": available,
            }, ensure_ascii=False)

        if _event_listener:
            await _event_listener.inject_js(tab.session_id, js)
        else:
            await _cdp_client.send(
                "Runtime.evaluate",
                {"expression": js},
                session_id=tab.session_id,
            )

        return json.dumps({
            "status": "ok",
            "message": f"Interface '{name}' 已注入到当前页面",
            "target_id": tab.target_id,
        }, ensure_ascii=False)

    @register_action(
        short_desc="ask_user_and_wait(question, options)",
        description="在浏览器前端弹出对话框向用户提问。"
                    "支持三种模式：纯文本回答、单选、多选。"
                    "用户回答通过事件异步返回，无需轮询。",
        param_infos={
            "question": "要展示给用户的问题文本",
            "options": '可选，JSON 字符串。如 \'{"choices":["A","B","C"]}\' 为单选，'
                       '\'{"choices":["A","B","C"],"multi":true}\' 为多选。不传则为纯文本输入。',
        },
    )
    async def ask_user_and_wait(self, question: str, options: str = "") -> str:
        """在浏览器前端弹出对话框向用户提问。"""
        await self._ensure_browser()
        tab = self._get_current_tab()

        if not tab:
            return json.dumps({
                "status": "error",
                "error": "没有活动的 tab。请先使用 open_url() 打开页面。",
            }, ensure_ascii=False)

        # 解析 options
        choices = []
        multi = False
        if options:
            try:
                opts = json.loads(options)
                choices = opts.get("choices", [])
                multi = opts.get("multi", False)
            except json.JSONDecodeError:
                return json.dumps({
                    "status": "error",
                    "error": f"options JSON 解析失败: {options}",
                }, ensure_ascii=False)

        # 读取 ask_dialog.js
        dialog_js_path = Path(__file__).parent / "interfaces" / "common" / "ask_dialog.js"
        dialog_js = dialog_js_path.read_text(encoding="utf-8")

        # 构造调用
        call_js = f"window.__bh_ask_user__({json.dumps({
            'question': question,
            'choices': choices,
            'multi': multi,
        })})"

        # 注入组件 + 调用
        if _event_listener:
            await _event_listener.inject_js(tab.session_id, dialog_js)
            await _event_listener.inject_js(tab.session_id, call_js)
        else:
            await _cdp_client.send(
                "Runtime.evaluate",
                {"expression": dialog_js + "\n" + call_js},
                session_id=tab.session_id,
            )

        mode = "纯文本" if not choices else ("多选" if multi else "单选")
        return json.dumps({
            "status": "ok",
            "message": f"已向用户提问（{mode}模式），等待回答...",
            "question": question,
            "choices": choices,
            "multi": multi,
        }, ensure_ascii=False)

    # ==========================================
    # Cleanup
    # ==========================================

    async def skill_cleanup(self):
        """MicroAgent 执行结束时清理。

        MicroAgent 持久化模式下，不注销 signal_queue。
        不关闭 tab，不关闭浏览器——这些是跨 MicroAgent 会话保持的。
        """
        # 不注销 signal_queue — MicroAgent 持久化，跨 execute 复用
        # signal_queue 在 MicroAgent 创建时注册，跟随 MicroAgent 生命周期
        logger.info("CDP Browser skill cleanup done (tabs preserved, signal_queue kept)")
