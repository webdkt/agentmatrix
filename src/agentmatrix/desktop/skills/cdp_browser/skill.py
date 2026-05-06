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
- BrowserEventListener 按 agent_name 路由 BrowserSignal 到 agent 的 input_queue
- 每个 tab 关联 agent_name + agent_session_id，前端事件自动附带这些元数据
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
_agent_last_session: dict[str, str] = {}  # agent_name → last known session_id


def _update_current_tab(agent_name: str, target_id: str):
    """更新 agent 的当前活动 tab（由 BrowserEventListener 调用）。"""
    if not _tab_manager or not target_id or not agent_name:
        return
    tab = _tab_manager._tabs.get(target_id)
    if tab:
        _agent_current_tab[agent_name] = tab


def _short_url(url: str) -> str:
    """截取 URL 的 scheme://host/首段路径，超出部分用 /... 表示。"""
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        segments = (parsed.path or "/").strip("/").split("/")
        if segments and segments[0]:
            base += "/" + segments[0]
        if len(url) > len(base):
            base += "/..."
        return base
    except Exception:
        return url[:50] + "..." if len(url) > 50 else url


def _tab_not_found_msg(invalid_id: str) -> str:
    """当 tab_id 不正确时，生成包含所有可用 tab 列表的错误消息。"""
    lines = []
    if _tab_manager:
        for tab in _tab_manager._tabs.values():
            lines.append(f"  - tab_id: {tab.target_id}, url: {_short_url(tab.url)}, title: {tab.title}")
    tab_list = "\n".join(lines) if lines else "  (无可用 tab)"
    return (f"tab_id '{invalid_id}' 不正确。当前可用的 tab：\n"
            f"{tab_list}\n"
            f"(url 仅显示域名和首段路径，完整信息请调用 list_tabs())")


async def _get_shared_infra(profile_dir: str, port: int = 9222):
    """获取或创建共享的 Chrome + CDP + TabManager 基础设施。"""
    global _chrome_manager, _cdp_client, _tab_manager, _event_listener

    async with _init_lock:
        if _cdp_client and _cdp_client._connected:
            return _cdp_client, _tab_manager, _event_listener

        # 重连：保留现有 TabManager/EventListener，只重连 CDPClient
        if _cdp_client is not None:
            try:
                await _cdp_client.connect()
                if _event_listener:
                    await _event_listener.resubscribe_all()
                return _cdp_client, _tab_manager, _event_listener
            except Exception as e:
                logger.warning(f"CDP reconnect failed, reinitializing: {e}")

        # 首次初始化
        _chrome_manager = ChromeManager(profile_dir=profile_dir, port=port)
        ws_url = await _chrome_manager.ensure_started()

        _cdp_client = CDPClient(ws_url)
        # 设置 WS URL 解析器（Chrome 重启后 URL 可能变化）
        _cdp_client.set_ws_url_resolver(_chrome_manager.ensure_started)
        await _cdp_client.connect()

        _tab_manager = TabManager(_cdp_client)

        _event_listener = BrowserEventListener(_cdp_client, _tab_manager, on_current_tab_change=_update_current_tab)
        # 注册连接状态回调 → 推送到前端
        _cdp_client.on_status_change(_event_listener.notify_connection_status)
        await _event_listener.start_target_discovery()

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

    def _agent_session_id(self) -> str:
        """获取当前 agent 的 active session_id。"""
        return getattr(self.root_agent, "active_session_id", "") or ""

    async def _set_tab_agent_meta(self, tab: TabInfo):
        """设置 tab 的 agent 元数据（agent_session_id + 前端 __bh_agent_meta__）。"""
        agent_session_id = self._agent_session_id()
        tab.agent_session_id = agent_session_id
        if _event_listener and tab.session_id:
            await _event_listener.set_agent_meta(
                tab.session_id, self._agent_name(), agent_session_id
            )

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
        """确保浏览器已启动，注册当前 agent 的 input_queue。"""
        # 正在重连 → 等待完成
        if _cdp_client and _cdp_client._reconnecting:
            for _ in range(60):  # 最多等 30 秒
                await asyncio.sleep(0.5)
                if _cdp_client._connected:
                    break
            else:
                logger.warning("Timed out waiting for CDP reconnect")

        if _cdp_client and _cdp_client._connected:
            # 已连接 → 只需注册 agent input_queue
            if _event_listener and self.root_agent:
                _event_listener.register_agent_queue(
                    self._agent_name(), self.root_agent.input_queue
                )
                _event_listener.start()
        else:
            agent_name = self._agent_name()

            # 固定 profile 路径，始终同一个，保留登录状态、书签、扩展等
            profile_dir = str(Path.home() / ".agentmatrix" / "cdp_browser_profile")

            port = int(os.environ.get("CDP_BROWSER_PORT", "9222"))

            cdp, tab_mgr, listener = await _get_shared_infra(profile_dir, port)

            # 注册 agent input_queue
            if listener and self.root_agent:
                listener.register_agent_queue(
                    self._agent_name(), self.root_agent.input_queue
                )
                listener.start()

        # Session 切换检测：关闭旧 session 的 tab
        agent_name = self._agent_name()
        current_sid = self._agent_session_id()
        last_sid = _agent_last_session.get(agent_name, "")

        if current_sid and current_sid != last_sid:
            await self._cleanup_old_session_tabs(agent_name, current_sid)
            _agent_last_session[agent_name] = current_sid

    async def _cleanup_old_session_tabs(self, agent_name: str, current_session_id: str):
        """关闭属于该 agent 但来自旧 session 的 tab。"""
        if not _tab_manager:
            return

        tabs = _tab_manager.get_agent_tabs_sync(agent_name)
        to_close = [
            t for t in tabs
            if t.agent_session_id
            and t.agent_session_id != current_session_id
        ]

        if not to_close:
            return

        closed_ids = set()
        for tab in to_close:
            logger.info(
                f"Cleaning old session tab: {tab.target_id} "
                f"(old_session={tab.agent_session_id[:8]}...)"
            )
            await _tab_manager.close_tab(tab.target_id)
            closed_ids.add(tab.target_id)

        # 如果 current_tab 被关了，更新到剩余 tab
        current = _agent_current_tab.get(agent_name)
        if current and current.target_id in closed_ids:
            remaining = _tab_manager.get_agent_tabs_sync(agent_name)
            _agent_current_tab[agent_name] = remaining[0] if remaining else None

        logger.info(
            f"Session cleanup: closed {len(to_close)} old tabs for '{agent_name}'"
        )

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
                await self._set_tab_agent_meta(tab)
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
        """打开 URL。复用当前 tab（如有），否则新建。"""
        await self._ensure_browser()
        agent_name = self._agent_name()

        # 复用当前 tab，而不是每次都新建
        tab = self._get_current_tab()
        if not tab:
            tabs = await _tab_manager.get_agent_tabs(agent_name)
            tab = tabs[0] if tabs else None
        if not tab:
            tab = await _tab_manager.create_tab(agent_name)
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
                await self._set_tab_agent_meta(tab)

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
                "error": _tab_not_found_msg(target_id),
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
                "error": _tab_not_found_msg(target_id),
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

        # 构造调用（__bh_ask_user__ 已由 agent_button.js 自动注入）
        call_js = f"window.__bh_ask_user__({json.dumps({
            'question': question,
            'choices': choices,
            'multi': multi,
        })})"

        # 调用
        if _event_listener:
            await _event_listener.inject_js(tab.session_id, call_js)
        else:
            await _cdp_client.send(
                "Runtime.evaluate",
                {"expression": call_js},
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
    # DOM 探索 (indicator → selector)
    # ==========================================

    @register_action(
        short_desc="find_selector(instruction_text, tab_id) 启动一个临时Agent 在浏览器中探索 DOM，找到目标元素的最佳稳定selector。instruction_text关于要找什么、以及有什么已知信息后者scope的详细描述",
        description="ind_selector(instruction_text, tab_id) 启动一个临时Agent 在浏览器中探索 DOM，找到目标元素的最佳稳定selector。instruction_text关于要找什么、以及有什么已知信息后者scope的详细描述",
        param_infos={
            "additional_info": "用户对该元素的描述文字（从 indicator_result 信号获取）",
            "tab_id": "目标 tab 的 tab_id",
        },
    )
    async def find_selector(self, instruction_text: str, tab_id: str) -> str:
        from agentmatrix.core.micro_agent import MicroAgent

        if not _cdp_client or not _cdp_client._connected:
            return json.dumps({"status": "error", "error": "浏览器未连接"})

        tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
        if not tab:
            return json.dumps({"status": "error", "error": _tab_not_found_msg(tab_id)})

        prompt = (
            "你是一个 DOM 元素定位专家。\n"
            f"你的任务：找到用户需要的元素的稳定定位表达式（CSS selector 或 XPath）。\n"
            "可用工具函数（通过 eval_js 调用，必须传 tab_id）：\n"
            "- __bh_el_info(el) — 获取元素详情，返回 {tag, id, cls, text, rect, attrs}\n"
            "- __bh_tag_path(el) — 获取 CSS 路径\n"
            "- __bh_xpath(el) — 获取 XPath\n"
            "- __bh_test(selector) — 测试 CSS selector 命中数\n"
            "- __bh_test_xpath(xpath) — 测试 XPath 命中数\n\n"
            "要求：为目标元素生成稳定的定位表达式：\n"
            "   - 稳定是指依赖固定、语义的属性和稳定的、固定的结构关系，不依赖动态属性、看上去像变量、哈希值、自增值、随机值的属性值\n"
            "   - 如果 CSS selector 难以表达（如按文本内容），用 XPath\n"
            "   - 好的selector 往往也是短的、含义清晰的selector，并且条件数量少的selector（例如单一属性优于多个属性组合，标签+属性优于纯属性）。"
            "   - 优先考虑元素自身的语义化的属性（如 tag name, id、aria-label、name、data-*）"
            "   - **重要技巧**：元素本身可能会缺乏直接的、稳定的的属性。更聪明的办法是先寻找页面中稳定的结构（例如父元素中具有简单、稳定定位的元素，以其为锚点），在一个稳定的小范围内进行进一步的定位。例如table可能是不唯一的，但是在特定id的div中是唯一的。\n"
            "5. 可以用 __bh_test 或 __bh_test_xpath 验证selector匹配元素的数量"
            "6. 调用 return_selector 返回结果（CSS selector 直接返回，XPath 以 'xpath:' 前缀返回）\n"
        )

        micro = MicroAgent(
            parent=self.root_agent,
            name=f"{self.root_agent.name}_dom_explorer",
            available_skills=["cdp_browser.dom_explorer"],
            system_prompt=prompt,
        )

        try:
            result = await micro.execute(
                run_label="Find Element Selector",
                task= f"用户对于要找的元素的描述: {instruction_text}",
                exit_actions=["return_selector"],
            )
            return json.dumps({
                "status": "ok",
                "selector": result['selector'],
                "description": result['additional_info'],
                "tab_id": tab_id,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
            }, ensure_ascii=False)

    @register_action(
        short_desc="find_unique_selector_by_xy(additional_info, tab_id, x, y) 启动一个临时Agent 在浏览器中探索 DOM，找到用户指向元素的稳定的、唯一的selector。additional_info是额外、帮助Agent定位元素的信息",
        description="find_unique_selector_by_xy(additional_info, tab_id, x, y) 启动一个临时Agent 在浏览器中探索 DOM，找到用户指向元素的稳定的、唯一的selector。additional_info是额外、帮助Agent定位元素的信息",
        param_infos={
            "additional_info": "用户对该元素的描述文字,以及任何有助于定位元素的额外信息",
            "tab_id": "目标 tab 的 tab_id",
            "x": "用户指向的 x 坐标",
            "y": "用户指向的 y 坐标",
        },
    )
    async def find_unique_selector_by_xy(self, additional_info: str, tab_id: str, x: int = 0, y: int = 0) -> str:
        from agentmatrix.core.micro_agent import MicroAgent

        if not _cdp_client or not _cdp_client._connected:
            return json.dumps({"status": "error", "error": "浏览器未连接"})

        tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
        if not tab:
            return json.dumps({"status": "error", "error": _tab_not_found_msg(tab_id)})

        prompt = (
            "你是一个 DOM 元素定位专家。\n"
            f"背景：用户在页面上用指示器指向了一个位置，坐标 x={x}, y={y}。\n"
            "我们用 elementFromPoint 获取了该位置的元素并标记为 __bh_marked__，\n"
            "但 elementFromPoint 返回的是视觉最顶层元素，可能是一个大容器 div 而非用户想指的交互元素。\n"
            "你的任务：找到用户真正想指的那个交互元素的稳定、唯一的定位表达式（CSS selector 或 XPath）。\n"
            "可用工具函数（通过 eval_js 调用，必须传 tab_id）：\n"
            "- __bh_elements_at(x, y) — 获取坐标处从顶到底的所有元素列表（已自动隐藏 UI 层）\n"
            "- __bh_el_info(el) — 获取元素详情，返回 {tag, id, cls, text, rect, attrs}\n"
            "- __bh_tag_path(el) — 获取 CSS 路径\n"
            "- __bh_xpath(el) — 获取 XPath\n"
            "- __bh_test(selector) — 测试 CSS selector 命中数\n"
            "- __bh_test_xpath(xpath) — 测试 XPath 命中数\n\n"
            "工作流程：\n"
            f"1. 用 __bh_elements_at({x}, {y}) 查看坐标处的元素栈\n"
            "2. 结合用户描述（additional_info），从栈中确定目标元素（通常是 button/a/input 等交互元素）\n"
            "3. 为目标元素生成稳定的定位表达式：\n"
            "   - 稳定是指依赖固定、语义的属性和稳定的、固定的结构关系，不依赖动态属性、看上去像变量、哈希值、自增值、随机值的属性值\n"
            "   - 如果 CSS selector 难以表达（如按文本内容），用 XPath\n"
            "   - 好的selector 往往也是短的、含义清晰的selector，并且条件数量少的selector（例如单一属性优于多个属性组合，标签+属性优于纯属性）。"
            "   - 优先考虑元素自身的语义化的属性（如 tag name, id、aria-label、name、data-*）"
            "   - **重要技巧**：交互元素本身往往会缺乏直接的、稳定的、可唯一定位的属性。更聪明的办法是先寻找页面中稳定的结构（例如父元素中具有简单、稳定定位的元素，以其为锚点），在一个稳定的小范围内进行进一步的定位。例如button tag可能是不唯一的，但是在特定id的div中是唯一的。\n"
            "5. 用 __bh_test 或 __bh_test_xpath 验证唯一性（count 必须为 1）\n"
            "6. 不唯一则调整，直到唯一且稳定（不依赖动态、随机的属性、数量关系）\n"
            "7. 调用 return_selector 返回结果（CSS selector 直接返回，XPath 以 'xpath:' 前缀返回）\n"
        )

        micro = MicroAgent(
            parent=self.root_agent,
            name=f"{self.root_agent.name}_dom_explorer",
            available_skills=["cdp_browser.dom_explorer"],
            system_prompt=prompt,
        )

        try:
            result = await micro.execute(
                run_label="Find Element Selector",
                task=(
                    f"用户在页面上指向了一个位置，描述: {additional_info}\n"
                    f"坐标: x={x}, y={y}\n"
                    f"当前页面: {tab.url}\n"
                    f"tab_id: {tab_id}\n\n"
                    "请找到用户想指的交互元素的稳定唯一定位表达式。"
                ),
                exit_actions=["return_selector"],
            )
            return json.dumps({
                "status": "ok",
                "selector": result['selector'],
                "description": result['additional_info'],
                "tab_id": tab_id,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
            }, ensure_ascii=False)

    @register_action(
        short_desc="confirm_element(selector, tab_id)在浏览器中高亮指定 selector 匹配的元素，并弹出确认对话框让用户确认。",
        description="在浏览器中高亮指定 selector 匹配的元素，并弹出确认对话框让用户确认。"
                    "立即返回，用户确认结果通过 element_confirmed 信号异步返回。",
        param_infos={
            "selector": "要确认的 CSS selector 或 XPath（XPath 以 'xpath:' 前缀）",
            "tab_id": "目标 tab 的 target_id（从信号中获取）",
        },
    )
    async def confirm_element(self, selector: str, tab_id: str) -> str:
        if not _cdp_client or not _cdp_client._connected:
            return json.dumps({"status": "error", "error": "浏览器未连接"})

        tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
        if not tab:
            return json.dumps({"status": "error", "error": _tab_not_found_msg(tab_id)})

        js = f"window.__bh_confirm__ ? window.__bh_confirm__({json.dumps(selector)}) : window.__bh_confirm({json.dumps(selector)})"

        try:
            await _cdp_client.send(
                "Runtime.evaluate",
                {"expression": js},
                session_id=tab.session_id,
                timeout=5,
            )
            return json.dumps({
                "status": "ok",
                "message": "已在页面上高亮元素，等待用户确认",
                "selector": selector,
                "tab_id": tab_id,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": str(e),
            }, ensure_ascii=False)

    # ==========================================
    # Cleanup
    # ==========================================

    async def skill_cleanup(self):
        """MicroAgent 执行结束时清理。

        MicroAgent 持久化模式下，不注销 agent input_queue。
        不关闭 tab，不关闭浏览器——这些是跨 MicroAgent 会话保持的。
        """
        # 不注销 agent input_queue — agent 生命周期跨 execute 复用
        logger.info("CDP Browser skill cleanup done (tabs preserved, agent queue kept)")
