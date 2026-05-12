"""
CDP Browser Skill — 浏览器自动化，支持前端 Interface 注入和双向事件。

Agent Actions:
- open_url(url)               → 打开 URL（自动注入通信桥接）
- tab_operation(op, target_id?)  → 统一 tab 管理（list / close / switch_to）
- run_automation_script(file_path, str_arg1?) → 按扩展名执行自动化脚本（.json CDP / .js JavaScript / .py Python）
- eval_js(code, tab_id?) → 在当前 tab 直接执行 JavaScript 代码字符串
- cdp_command(method, params?, tab_id?) → 直接发送 CDP 协议指令

CDP 连接对 Agent 完全透明：session 激活时自动建立连接、恢复 tab、注册 agent queue。
无需手动调用 open_browser()。


设计要点：
- Chrome/CDP/TabManager/EventListener 是进程级单例（一个 Chrome 进程）
- Tab 按 agent_name 隔离（多 Agent 各自管理自己的 tabs）
- _agent_current_tab 按 agent_name 索引，跨 MicroAgent 实例保持
- BrowserEventListener 按 agent_name 路由 BrowserSignal 到 agent 的 input_queue
- 每个 tab 关联 agent_name + agent_session_id，前端事件自动附带这些元数据
"""

import ast
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
_agent_sk_callbacks: dict[str, callable] = {}  # agent_name → tab 变化时刷新 site knowledge prompt


def _trigger_sk_callback(agent_name: str):
    """触发 agent 的 site knowledge prompt 刷新回调（如果已注册）。"""
    callback = _agent_sk_callbacks.get(agent_name)
    if callback:
        try:
            callback()
        except Exception as e:
            logger.debug(f"Site knowledge callback failed for '{agent_name}': {e}")


def _update_current_tab(agent_name: str, target_id: str):
    """更新 agent 的当前活动 tab（由 BrowserEventListener 调用）。"""
    if not _tab_manager or not target_id or not agent_name:
        return
    tab = _tab_manager._tabs.get(target_id)
    if tab:
        _agent_current_tab[agent_name] = tab
        _trigger_sk_callback(agent_name)


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


async def _auto_yield_ui(tab: TabInfo):
    """让前端 UI 进入避让模式（半透明 + 穿透 + 冻结）。"""
    js = "(window.__bh_set_automation_mode__ || function(){})(true)"
    try:
        await _cdp_client.send(
            "Runtime.evaluate", {"expression": js},
            session_id=tab.session_id, timeout=3,
        )
    except Exception:
        pass


async def _auto_restore_ui(tab: TabInfo):
    """通知前端 UI 可以恢复（1秒延迟防抖）。"""
    js = "(window.__bh_set_automation_mode__ || function(){})(false)"
    try:
        await _cdp_client.send(
            "Runtime.evaluate", {"expression": js},
            session_id=tab.session_id, timeout=3,
        )
    except Exception:
        pass


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
        # 注册连接状态回调：断线时通知前端，重连时先 resubscribe 再通知前端
        async def _on_cdp_status(connected):
            if connected:
                await _event_listener._on_reconnected()
            else:
                await _event_listener.notify_connection_status(False)
        _cdp_client.on_status_change(_on_cdp_status)
        await _event_listener.start_target_discovery()

        return _cdp_client, _tab_manager, _event_listener


# ── Skill Mixin ───────────────────────────────────────────

class Browser_automationSkillMixin:
    """
    Browser Automation Skill — 浏览器自动化 

    多 Agent 支持：
    - 所有 agent 共享一个 Chrome 实例
    - tab 按 agent_name 隔离
    - 浏览器事件按 tab 归属路由到正确的 agent signal_queue
    """

    _skill_description = """浏览器自动化：打开页面、管理 tab、运行cdp命令和js, 执行浏览器自动化脚本
    已经学会的网站知识和流程，记录在`~/site_knowledge`目录下。
    ### site_knowledge 的结构
    - index.txt: 已学会的网站列表，每行格式 `url_prefix:说明:子目录名` （整行是一个唯一的site key）
        - url_prefix 可以是域名（如 `www.example.com`）或域名+路径前缀（如 `www.example.com/shop`）
        - url_prefix 可能重复，但说明和子目录名必须不同（因为有些单体站点可能包含多个不同的子系统，结构和元素差异较大）
        - 匹配规则：系统会自动根据hostname 来推荐匹配。但你必须显示的选择正确的site key 来加载对应的知识。系统不会自动加载，除非你明确的选择了一个site key。
        - 使用 load_site_knowledge(site_key) 来加载对应的知识
    - 每个网站(site key)一个子目录，内含：
        - index.md: 网站说明、该站点所有文档和脚本的index。 **MUST HAVE**, **MUST READ**
        - shared_components.md:  站内公用元素的定位说明，所有流程共享
        - 其他 .md 文件: 特定自动化流程（如”登录流程.md”、”购买流程.md”）
        - scripts/ 目录：存放针对该站点的自动化脚本。自动化脚本有3类，.json (cdp命令）.js (注入浏览器执行的js脚本）,.py (python自动化脚本）
        - 其中py脚本 绝对不能通过bash执行。 原因见下面规范说明
    ### site_knowledge 文件规范
    #### Python自动化脚本
    py 自动化脚本**必须**通过 `run_automation_script(file_path, str_arg1?)` 执行，因为Chrome在用户环境而不是你的环境，通过bash直接执行python脚本将无法访问cdp。
    **切记**：Python脚本中绝对不可以直接使用任何硬编码的路径或连接信息，必须通过以下环境变量获取，才能保证脚本在用户环境中正确执行，脚本生成的文件你才能访问。
    脚本通过环境变量获取连接信息和路径：
    - `os.environ["CDP_PORT"]` — Chrome 调试端口（如 9222）
    - `os.environ["CDP_HTTP_ENDPOINT"]` — HTTP 端点（如 http://127.0.0.1:9222）
    - `os.environ["CDP_CURRENT_TAB_ID"]` — 当前 tab 的 target_id
    - `os.environ["CURRENT_TASK_DIR"]` — 当前任务工作目录（对应你的 ~/current_task/）
    - `os.environ["HOME_DIR"]` — home 目录（对应你的 ~/）
    - `os.environ["SITE_KNOWLEDGE_DIR"]` — site_knowledge 目录（对应你的 ~/site_knowledge/）
    - `sys.argv[1]` — 可选的字符串参数。如需传递多个参数，将参数写入文件，传入文件路径
    1. Py脚本只能接受最多一个字符串参数（sys.argv[1]），多参数用参数文件传递(文件路径作为参数传入，文件必须在 ~ （或者其子目录）下面。
    2. 需要保存文件时，使用环境变量中的路径（如 `os.path.join(os.environ["CURRENT_TASK_DIR"], "output.json")`），这样你就可以通过 ~/current_task/output.json 读取
    3. 连接 CDP 时，如果使用 `websocket-client` 库，必须加 `suppress_origin=True`，否则 Chrome 会拒绝连接：
    **绝对不要用bash 直接执行python自动化脚本，否则无法连接用户环境中的Chrome CDP。** 
    #### .js 脚本： No Console Output
    eval_js 和 run_automation_script 都不会返回console的输出。只会返回脚本 return的结果。
    #### 正式脚本 vs 探索脚本
    ~/site_knowledge 下只能存放正式的脚本。探索脚本放在 ~/current_task/tmp 下。
    #### 流程文档 
    - 必须是 .md格式
    - 文件开头部分必须有目录和meta data
    - **必须记录自动化状态**：有没有自动化，哪些步骤自动化了，自动化脚本在哪里
    - 单个文件必须小于500行
    - 要增加任何新流程内容，必须先verify是否已经存在。READ BEFORE MODIFY 
    - 流程知识更新后，执行load_site_knowledge，重新加载知识
  """

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
        """通过 CDP 查询 Chrome 所有 page，关闭属于该 agent 旧 session 的 tab，收养匹配的 tab。

        对每个 page：
        1. 临时 attach → Runtime.evaluate 读 window.__bh_agent_meta__
        2. agent_name 匹配 且 agent_session_id ≠ 当前 session → 关闭
        3. agent_name 匹配 且 agent_session_id == 当前 session → 收养（注册到 TabManager + 设为 current_tab）
        4. 否则 detach，跳过
        """
        if not _cdp_client:
            return

        try:
            pages = await _cdp_client.get_pages(include_internal=False)
        except Exception as e:
            logger.warning(f"Failed to get Chrome pages for cleanup: {e}")
            return

        if not pages:
            return

        closed = 0
        adopt_candidates = []  # (target_id, url) 匹配当前 session 的 tab
        for page in pages:
            tid = page.get("targetId", "")
            url = page.get("url", "")
            if not tid:
                continue

            # 临时 attach 读取 __bh_agent_meta__
            temp_sid = None
            try:
                temp_sid = await _cdp_client.attach_to_target(tid)
                result = await _cdp_client.send(
                    "Runtime.evaluate",
                    {"expression": "window.__bh_agent_meta__ || null",
                     "returnByValue": True},
                    session_id=temp_sid,
                    timeout=5,
                )
                meta = result.get("result", {}).get("value")
            except Exception:
                meta = None

            # 读完立即 detach
            if temp_sid:
                try:
                    await _cdp_client.send(
                        "Target.detachFromTarget",
                        {"sessionId": temp_sid},
                        timeout=5,
                    )
                except Exception:
                    pass

            # 判断是否属于当前 agent 的旧 session
            if not meta:
                continue  # 无 meta（未注入 bridge），跳过
            if meta.get("agent_name") != agent_name:
                continue  # 属于其他 agent，跳过
            tab_sid = meta.get("agent_session_id", "")
            if not tab_sid or tab_sid == current_session_id:
                # 无 session 标记 或 当前 session → 收养候选
                adopt_candidates.append((tid, url))
                continue

            # 关闭旧 session 的 tab
            logger.info(
                f"Cleaning old session tab: {tid[:12]} "
                f"(old_session={tab_sid[:12]}, url={url[:60]})"
            )
            try:
                await _cdp_client.close_target(tid)
                # 同步清理 _tab_manager
                _tab_manager._tabs.pop(tid, None)
                for ats in _tab_manager._agent_tabs.values():
                    ats.discard(tid)
                closed += 1
            except Exception as e:
                logger.warning(f"Failed to close tab {tid[:12]}: {e}")

        # 收养匹配当前 session 的 tab（系统恢复/重启场景）
        if adopt_candidates:
            for tid, url in adopt_candidates:
                if _tab_manager._tabs.get(tid):
                    continue  # 已在 TabManager 中跟踪，跳过
                try:
                    tab = await _tab_manager.adopt_tab(
                        tid, agent_name, current_session_id, url
                    )
                    await self._set_tab_agent_meta(tab)
                    logger.info(
                        f"Adopted matching-session tab: {tid[:12]} (url={url[:60]})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to adopt tab {tid[:12]}: {e}")

            # 选择 current_tab：优先 active（visibilityState=visible），否则最后一个
            adopted_tabs = _tab_manager.get_agent_tabs_sync(agent_name)
            if adopted_tabs and not _agent_current_tab.get(agent_name):
                best = adopted_tabs[-1]
                for t in adopted_tabs:
                    try:
                        res = await _cdp_client.send(
                            "Runtime.evaluate",
                            {"expression": "document.visibilityState",
                             "returnByValue": True},
                            session_id=t.session_id,
                            timeout=3,
                        )
                        if res.get("result", {}).get("value") == "visible":
                            best = t
                            break
                    except Exception:
                        pass
                _agent_current_tab[agent_name] = best
                _trigger_sk_callback(agent_name)
                logger.info(
                    f"Adopted current_tab: {best.target_id[:12]} "
                    f"(url={best.url[:60]})"
                )

        # 如果 current_tab 被关了，更新到剩余 tab
        current = _agent_current_tab.get(agent_name)
        if current:
            remaining = _tab_manager.get_agent_tabs_sync(agent_name)
            still_exists = any(t.target_id == current.target_id for t in remaining)
            if not still_exists:
                _agent_current_tab[agent_name] = remaining[0] if remaining else None
                _trigger_sk_callback(agent_name)

        if closed:
            logger.info(
                f"Session cleanup: closed {closed} old tabs for '{agent_name}'"
            )

    # ==========================================
    # Actions
    # ==========================================

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
        short_desc="tab_operation(op, target_id?) 统一 tab 管理。op='list' 列出 tabs, op='close' 关闭 tab, op='switch_to' 切换 tab",
        description="统一 tab 管理。op='list' 列出当前 agent 的所有 tab（含 tab ID、URL、标题、是否当前 tab）；"
                    "op='close' 关闭指定 tab（关闭后自动切换到剩余 tab）；"
                    "op='switch_to' 切换到指定 tab（激活并注入 bridge）。",
        param_infos={
            "op": "操作类型：'list' / 'close' / 'switch_to'",
            "target_id": "tab 的 target_id（list 不需要，close/switch_to 必填）",
        },
    )
    async def tab_operation(self, op: str, target_id: str = None) -> str:
        await self._ensure_browser()
        agent_name = self._agent_name()

        if op == "list":
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
            return json.dumps({"tab_count": len(result), "tabs": result}, ensure_ascii=False)

        elif op == "close":
            if not target_id:
                return json.dumps({"status": "error", "error": "close 操作需要提供 target_id"}, ensure_ascii=False)
            tab = await _tab_manager.get_tab(target_id)
            if not tab:
                return json.dumps({"status": "error", "error": _tab_not_found_msg(target_id)}, ensure_ascii=False)
            if tab.agent_name != agent_name:
                return json.dumps({"status": "error", "error": f"Tab {target_id} 不属于当前 agent"}, ensure_ascii=False)
            await _tab_manager.close_tab(target_id)
            current = self._get_current_tab()
            if current and current.target_id == target_id:
                tabs = await _tab_manager.get_agent_tabs(agent_name)
                self._set_current_tab(tabs[0] if tabs else None)
            return json.dumps({"status": "ok"}, ensure_ascii=False)

        elif op == "switch_to":
            if not target_id:
                return json.dumps({"status": "error", "error": "switch_to 操作需要提供 target_id"}, ensure_ascii=False)
            tab = await _tab_manager.get_tab(target_id)
            if not tab:
                return json.dumps({"status": "error", "error": _tab_not_found_msg(target_id)}, ensure_ascii=False)
            if tab.agent_name != agent_name:
                return json.dumps({"status": "error", "error": f"Tab {target_id} 不属于当前 agent"}, ensure_ascii=False)
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
                return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)

        else:
            return json.dumps({"status": "error", "error": f"未知操作 '{op}'，支持: list / close / switch_to"}, ensure_ascii=False)

    
    async def deprecated_show_interface(self, name: str) -> str:
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
        short_desc="find_selector(instruction_text, tab_id?) 启动一个临时Agent 在浏览器中探索 DOM，找到目标元素的最佳稳定selector。instruction_text关于要找什么、以及有什么已知信息后者scope的详细描述",
        description="find_selector(instruction_text, tab_id?) 启动一个临时Agent 在浏览器中探索 DOM，找到目标元素的最佳稳定selector。instruction_text关于要找什么、以及有什么已知信息后者scope的详细描述",
        param_infos={
            "additional_info": "用户对该元素的描述文字（从 indicator_result 信号获取）",
            "tab_id": "可选，目标 tab 的 tab_id，不传则使用当前 tab",
        },
    )
    async def find_selector(self, instruction_text: str, tab_id: str = None) -> str:
        from agentmatrix.core.micro_agent import MicroAgent

        await self._ensure_browser()

        if tab_id:
            tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
            if not tab:
                return json.dumps({"status": "error", "error": _tab_not_found_msg(tab_id)})
        else:
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"status": "error", "error": "没有活动的 tab，请先用 open_url() 打开页面"})
            tab_id = tab.target_id

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
            "- 稳定是指依赖固定、语义的属性和稳定的、固定的结构关系，不依赖动态属性、看上去像变量、哈希值、自增值、随机值的属性值"
            "- 好的selector 往往也是短的、含义清晰的selector，并且条件数量少的selector（例如单一属性优于多个属性组合，标签+属性优于纯属性）。"
            "- 优先考虑元素自身的**语义化**的属性"
            "- 如果本身缺少直接的稳定属性，就去寻找元素的上级、下级或相邻结构中的稳定定位元素，以其为锚点，再通过相对关系来定位目标元素。"
            "- 一个属性是否是稳定可靠的selector取决于作用域。例如单纯的<a> tag一般无法直接用于定位。但如果其父节点可以稳定定位，parent > a 就是一个简单稳定的定位手段"
            "- 所以在本身没有稳定属性的情况下，优先找到目标元素“层级关系最近”的稳定元素，然后在缩小的作用域里进行更简单的定位"
            "- 避免使用无语义、随机生成的属性来作为定位依据"
            "5. 可以用 __bh_test 或 __bh_test_xpath 验证selector匹配元素的数量"
            "6. 调用 return_selector 返回结果（CSS selector 直接返回，XPath 以 'xpath:' 前缀返回）\n"
            "用户完全不懂技术，并且缺乏耐心，所以无论你做什么action，都要用 keep_user_from_bored 来说点什么避免用户长时间等待。可以通俗的解释工作，或者说一些相关话题、有趣又有智慧的评论，避免用户觉得无聊"
        )

        micro = MicroAgent(
            parent=self.root_agent,
            name=f"{self.root_agent.name}_dom_explorer",
            available_skills=["browser_automation.dom_explorer"],
            system_prompt=prompt,
        )
        micro._pinned_tab_id = tab_id

        try:
            result = await micro.execute(
                run_label="Find Element Selector",
                task=(
                    f"用户对于要找的元素的描述: {instruction_text}\n"
                    f"当前页面: {tab.url}\n"
                    f"tab_id: {tab_id}\n\n"
                    "请找到用户需要的元素的稳定定位表达式。"
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
        short_desc="find_unique_selector_by_xy(additional_info, tab_id?, x, y) 启动一个临时Agent 在浏览器中探索 DOM，找到用户指向元素的稳定的、唯一的selector。additional_info是额外、帮助Agent定位元素的信息",
        description="find_unique_selector_by_xy(additional_info, tab_id, x, y) 启动一个临时Agent 在浏览器中探索 DOM，找到用户指向元素的稳定的、唯一的selector。additional_info是额外、帮助Agent定位元素的信息",
        param_infos={
            "additional_info": "用户对该元素的描述文字,以及任何有助于定位元素的额外信息",
            "tab_id": "可选，目标 tab 的 tab_id，不传则使用当前 tab",
            "x": "用户指向的 x 坐标",
            "y": "用户指向的 y 坐标",
        },
    )
    async def find_unique_selector_by_xy(self, additional_info: str, tab_id: str = None, x: int = 0, y: int = 0) -> str:
        from agentmatrix.core.micro_agent import MicroAgent

        await self._ensure_browser()

        if tab_id:
            tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
            if not tab:
                return json.dumps({"status": "error", "error": _tab_not_found_msg(tab_id)})
        else:
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"status": "error", "error": "没有活动的 tab，请先用 open_url() 打开页面"})
            tab_id = tab.target_id

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
            "- 稳定是指依赖固定、语义的属性和稳定的、固定的结构关系，不依赖动态属性、看上去像变量、哈希值、自增值、随机值的属性值"
            "- 好的selector 往往也是短的、含义清晰的selector，并且条件数量少的selector（例如单一属性优于多个属性组合，标签+属性优于纯属性）。"
            "- 优先考虑元素自身的**语义化**的属性"
            "- 如果本身缺少直接的稳定属性，就去寻找元素的上级、下级或相邻结构中的稳定定位元素，以其为锚点，再通过相对关系来定位目标元素。"
            "- 一个属性是否是稳定可靠的selector取决于作用域。例如单纯的<a> tag一般无法直接用于定位。但如果其父节点可以稳定定位，parent > a 就是一个简单稳定的定位手段"
            "- 所以在本身没有稳定属性的情况下，优先找到目标元素“层级关系最近”的稳定元素，然后在缩小的作用域里进行更简单的定位"
            "- 避免使用无语义、随机生成的属性来作为定位依据"
            "4. 用 __bh_test 或 __bh_test_xpath 验证唯一性（count 必须为 1）\n"
            "5. 不唯一则调整，直到唯一且稳定（不依赖动态、随机的属性、数量关系）\n"
            "6. 调用 return_selector 返回结果（CSS selector 直接返回，XPath 以 'xpath:' 前缀返回）\n"
            "用户完全不懂技术，并且缺乏耐心，所以无论你做什么action，都要用 keep_user_from_bored 来说点什么避免用户长时间等待。可以通俗的解释工作，或者说一些相关话题、有趣又有智慧的评论，避免用户觉得无聊"
        )

        micro = MicroAgent(
            parent=self.root_agent,
            name=f"{self.root_agent.name}_dom_explorer",
            available_skills=["browser_automation.dom_explorer"],
            system_prompt=prompt,
        )
        micro._pinned_tab_id = tab_id

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
        short_desc="confirm_element(selector, tab_id?) 在浏览器中高亮指定 selector 匹配的元素，并弹出确认对话框让用户确认。",
        description="在浏览器中高亮指定 selector 匹配的元素，并弹出确认对话框让用户确认。"
                    "立即返回，用户确认结果通过 element_confirmed 信号异步返回。",
        param_infos={
            "selector": "要确认的 CSS selector 或 XPath（XPath 以 'xpath:' 前缀）",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def confirm_element(self, selector: str, tab_id: str = None) -> str:
        await self._ensure_browser()

        if tab_id:
            tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
            if not tab:
                return json.dumps({"status": "error", "error": _tab_not_found_msg(tab_id)})
        else:
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"status": "error", "error": "没有活动的 tab，请先用 open_url() 打开页面"})
            tab_id = tab.target_id

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
        
    @register_action(
        short_desc="(file_path, str_arg1?) 按扩展名执行自动化脚本，str_arg1可选仅对 .py 有效"
                    "- .json：按顺序执行 CDP 指令序列（单条对象或数组），每条可含 'tab_id'/'timeout'\n"
                    "- .js：在当前 tab 中执行 JavaScript，可用 __bh_el_info / __bh_test 等工具函数\n"
                    "- .py：在宿主机执行 Python 脚本，自动注入 CDP 连接环境变量，str_arg1 通过 sys.argv[1] 传入\n\n"
                    ,
        description="读取脚本文件并按扩展名执行。\n"
                    "- .json：按顺序执行 CDP 指令序列（单条对象或数组），每条可含 'tab_id'/'timeout'\n"
                    "- .js：在当前 tab 中执行 JavaScript，可用 __bh_el_info / __bh_test 等工具函数\n"
                    "- .py：在宿主机执行 Python 脚本，自动注入 CDP 连接环境变量，str_arg1 通过 sys.argv[1] 传入\n\n"
                    ".json 示例（鼠标点击）：\n"
                    '[\n'
                    '  {"method":"Input.dispatchMouseEvent","params":{"type":"mousePressed","x":100,"y":200,"button":"left","clickCount":1}},\n'
                    '  {"method":"Input.dispatchMouseEvent","params":{"type":"mouseReleased","x":100,"y":200,"button":"left","clickCount":1}}\n'
                    ']\n\n'
                    "路径会自动从容器路径转换为宿主路径。\n"
                    "CDP 文档参考 https://chromedevtools.github.io/devtools-protocol/",
        param_infos={
            "file_path": "脚本文件路径，支持 .json / .js / .py（必须是 ~ 或 ~/current_task 及其子目录下）",
            "str_arg1": "可选，仅对 .py 有效，传递给脚本的字符串参数（脚本通过 sys.argv[1] 读取）",
        },
    )
    async def run_automation_script(self, file_path: str, str_arg1: str = None) -> str:
        await self._ensure_browser()

        # 容器路径 → 宿主路径
        root = self.root_agent
        agent_name = root.name
        task_id = getattr(root, "current_task_id", None) or "default"
        host_path = root.runtime.paths.container_path_to_host(
            file_path, agent_name, task_id
        )
        if host_path is None or not host_path.exists():
            return json.dumps({
                "error": "文件必须在 ~ 或 ~/current_task 及其子目录下",
            }, ensure_ascii=False)

        # 读取文件
        try:
            content = host_path.read_text(encoding="utf-8")
        except Exception as e:
            return json.dumps({"error": f"读取文件失败: {e}"}, ensure_ascii=False)

        ext = host_path.suffix.lower()

        # ── .js → Runtime.evaluate ──
        if ext == ".js":
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"error": "没有活动的 tab，请先用 open_url() 打开页面"})

            try:
                result = await _cdp_client.send(
                    "Runtime.evaluate",
                    {"expression": content, "returnByValue": True, "awaitPromise": True},
                    session_id=tab.session_id,
                    timeout=15,
                )
                res = result.get("result", {})

                if res.get("subtype") == "error":
                    desc = res.get("description", "unknown JS error")
                    logger.warning(f"[run_script] JS exception: {desc}")
                    return json.dumps({"error": desc})

                value = res.get("value")
                type_name = res.get("type", "undefined")

                if type_name == "undefined":
                    return json.dumps({"type": "undefined", "value": None})
                if value is None:
                    return json.dumps({"type": type_name, "value": None})
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False)
                return str(value)
            except Exception as e:
                logger.warning(f"[run_script] JS error: {e}")
                return json.dumps({"error": str(e)})

        # ── .json → CDP 指令序列 ──
        if ext == ".json":
            try:
                cmd = json.loads(content)
            except json.JSONDecodeError as e:
                return json.dumps({"error": f"JSON 解析失败: {e}"}, ensure_ascii=False)

            if isinstance(cmd, dict):
                commands = [cmd]
            elif isinstance(cmd, list):
                commands = cmd
            else:
                return json.dumps({"error": f"JSON 必须是对象或数组，实际: {type(cmd).__name__}"}, ensure_ascii=False)

            results = []
            for i, item in enumerate(commands):
                method = item.get("method")
                if not method:
                    results.append({"index": i, "error": "缺少 'method' 字段"})
                    continue

                params = item.get("params", {})
                timeout = item.get("timeout", 30)
                cmd_tab_id = item.get("tab_id")

                if cmd_tab_id:
                    tab = _tab_manager._tabs.get(cmd_tab_id) if _tab_manager else None
                    if not tab:
                        results.append({"index": i, "method": method, "error": _tab_not_found_msg(cmd_tab_id)})
                        continue
                else:
                    tab = self._get_current_tab()
                    if not tab:
                        results.append({"index": i, "method": method, "error": "没有活动的 tab"})
                        continue

                _is_input = method.startswith("Input.")
                if _is_input:
                    await _auto_yield_ui(tab)
                try:
                    result = await _cdp_client.send(
                        method, params,
                        session_id=tab.session_id,
                        timeout=timeout,
                    )
                    results.append({"index": i, "method": method, "result": result})
                except Exception as e:
                    logger.warning(f"[run_script] {method} error: {e}")
                    results.append({"index": i, "method": method, "error": str(e)})
                finally:
                    if _is_input:
                        await _auto_restore_ui(tab)

            if len(commands) == 1:
                return json.dumps(results[0], ensure_ascii=False, default=str)
            return json.dumps({"status": "ok", "total": len(commands), "results": results}, ensure_ascii=False, default=str)

        # ── .py → 宿主机 Python 脚本 ──
        if ext == ".py":
            # 收集 CDP 信息
            port = int(os.environ.get("CDP_BROWSER_PORT", "9222"))
            http_endpoint = f"http://127.0.0.1:{port}"
            tab = self._get_current_tab()

            # 构建环境变量
            work_dir = root.runtime.paths.get_agent_work_files_dir(agent_name, task_id)
            home_dir = root.runtime.paths.get_agent_home_dir(agent_name)
            env = os.environ.copy()
            env.update({
                "CDP_PORT": str(port),
                "CDP_HTTP_ENDPOINT": http_endpoint,
                "CDP_CURRENT_TAB_ID": tab.target_id if tab else "",
                "CURRENT_TASK_DIR": str(work_dir),
                "HOME_DIR": str(home_dir),
                "SITE_KNOWLEDGE_DIR": str(home_dir / "site_knowledge"),
            })

            # 构建命令
            cmd = ["python3", str(host_path)]
            if str_arg1 is not None:
                cmd.append(str_arg1)

            # 整个 .py 脚本期间 UI 避让（脚本可能做 CDP 操作）
            if tab:
                await _auto_yield_ui(tab)
            try:
                # 执行
                try:
                    proc = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env,
                    )
                    stdout_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=300
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
                    return json.dumps({
                        "status": "timeout",
                        "error": "脚本执行超时（300秒）",
                    }, ensure_ascii=False)
                except Exception as e:
                    return json.dumps({
                        "status": "error",
                        "error": f"脚本执行失败: {e}",
                    }, ensure_ascii=False)
            finally:
                if tab:
                    await _auto_restore_ui(tab)

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            stdout_lines = stdout.count("\n") + (1 if stdout and not stdout.endswith("\n") else 0)
            MAX_INLINE_LINES = 100

            def _save_to_tmp(content: str, suffix: str) -> tuple[str, str]:
                """保存到 ~/current_task/tmp/，返回 (host_path, container_path)。"""
                import time
                tmp_host_dir = work_dir / "tmp"
                tmp_host_dir.mkdir(parents=True, exist_ok=True)
                filename = f"script_{int(time.time())}_{os.getpid()}{suffix}"
                host = tmp_host_dir / filename
                host.write_text(content, encoding="utf-8")
                container = f"~/current_task/tmp/{filename}"
                return str(host), container

            # 构建 result
            result = {
                "status": "ok" if proc.returncode == 0 else "error",
                "exit_code": proc.returncode,
            }

            # stdout: 短输出直接返回，长输出存文件
            if stdout_lines <= MAX_INLINE_LINES:
                result["stdout"] = stdout
            else:
                _, container_path = _save_to_tmp(stdout, ".out")
                result["stdout_file"] = container_path
                result["stdout_lines"] = stdout_lines

            # stderr: 同样处理
            if stderr:
                stderr_lines = stderr.count("\n") + (1 if not stderr.endswith("\n") else 0)
                if stderr_lines <= MAX_INLINE_LINES:
                    result["stderr"] = stderr
                else:
                    _, container_path = _save_to_tmp(stderr, ".err")
                    result["stderr_file"] = container_path
                    result["stderr_lines"] = stderr_lines

            if proc.returncode != 0:
                result["error"] = f"脚本退出码: {proc.returncode}"

            return json.dumps(result, ensure_ascii=False)

        return json.dumps({"error": f"不支持的文件类型 '{ext}'，支持 .json / .js / .py"}, ensure_ascii=False)

    @register_action(
        short_desc="eval_js(code, tab_id?) 在当前 tab 执行 JavaScript，支持 await/Promise",
        description="向当前（或指定）tab 发送 JavaScript 代码并返回执行结果。"
                    "支持返回 Promise / 使用 await，会等待 resolve 后返回最终值。",
        param_infos={
            "code": "要执行的 JavaScript 代码字符串（支持 async/await）",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def eval_js(self, code: str, tab_id: str = None) -> str:
        await self._ensure_browser()

        if tab_id:
            tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
            if not tab:
                return json.dumps({"error": _tab_not_found_msg(tab_id)})
        else:
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"error": "没有活动的 tab，请先用 open_url() 打开页面"})
            tab_id = tab.target_id

        try:
            result = await _cdp_client.send(
                "Runtime.evaluate",
                {
                    "expression": code,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
                session_id=tab.session_id,
                timeout=15,
            )
            res = result.get("result", {})

            # CDP 执行报错
            if res.get("subtype") == "error":
                desc = res.get("description", "unknown JS error")
                logger.warning(f"[eval_js] JS exception: {desc}")
                return json.dumps({"error": desc})

            value = res.get("value")
            type_name = res.get("type", "undefined")

            if type_name == "undefined":
                return json.dumps({"type": "undefined", "value": None})
            if value is None:
                return json.dumps({"type": type_name, "value": None})
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
        except Exception as e:
            logger.warning(f"[eval_js] CDP error: {e}")
            return json.dumps({"error": str(e)})

    @register_action(
        short_desc="cdp_command(method, params?, tab_id?) 直接发送 CDP 协议指令。params 必须是 dict 对象",
        description="向浏览器 tab 发送原始 CDP (Chrome DevTools Protocol) 指令并返回结果。"
                    "可用于执行 Input.dispatchMouseEvent（鼠标事件）、Input.dispatchKeyEvent（键盘事件）、"
                    "Page.captureScreenshot（截图）等任意 CDP 方法。\n\n"
                    "params 必须是 dict 对象，示例：\n"
                    '  cdp_command("Input.dispatchMouseEvent", {"type": "mousePressed", "x": 100, "y": 200, "button": "left", "clickCount": 1})\n'
                    '  cdp_command("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": 100, "y": 200, "button": "left", "clickCount": 1})\n'
                    '  cdp_command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "text": "\\r"})\n\n'
                    "完整文档参考 https://chromedevtools.github.io/devtools-protocol/",
        param_infos={
            "method": "CDP 方法名，如 Input.dispatchMouseEvent",
            "params": "可选，CDP 参数 dict，如 {\"type\":\"mousePressed\",\"x\":100,\"y\":200}",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def cdp_command(self, method: str, params=None, tab_id: str = None) -> str:
        await self._ensure_browser()

        # 兜底：params 可能被框架传成字符串
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (ValueError, SyntaxError):
                try:
                    params = ast.literal_eval(params)
                except (ValueError, SyntaxError):
                    return json.dumps({"error": f"params 无法解析为 dict: {params[:200]}"})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return json.dumps({"error": f"params 必须是 dict，实际类型: {type(params).__name__}"})

        if tab_id:
            tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
            if not tab:
                return json.dumps({"error": _tab_not_found_msg(tab_id)})
        else:
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"error": "没有活动的 tab，请先用 open_url() 打开页面"})

        try:
            # Input.* 事件可能被 UI 拦截，自动进入避让模式
            _is_input = method.startswith("Input.")
            if _is_input:
                await _auto_yield_ui(tab)
            try:
                result = await _cdp_client.send(
                    method,
                    params or {},
                    session_id=tab.session_id,
                    timeout=30,
                )
                return json.dumps(result, ensure_ascii=False, default=str)
            finally:
                if _is_input:
                    await _auto_restore_ui(tab)
        except Exception as e:
            logger.warning(f"[cdp_command] {method} error: {e}")
            return json.dumps({"error": str(e)})

    # ==========================================
    # Site Knowledge
    # ==========================================

    @register_action(
        short_desc="get_cdp_info()",
        description="获取当前 CDP 浏览器连接信息，供外部脚本连接浏览器做自动化。"
                    "返回 WebSocket URL、调试端口、当前 tab 的 target_id 等。",
    )
    async def get_cdp_info(self) -> str:
        """返回 CDP 连接信息，供 Agent 编写 Python 代码直接连接浏览器。"""
        await self._ensure_browser()

        port = int(os.environ.get("CDP_BROWSER_PORT", "9222"))
        ws_url = _chrome_manager.get_ws_url() if _chrome_manager else None
        tab = self._get_current_tab()

        return json.dumps({
            "status": "ok",
            "port": port,
            "ws_url": ws_url,
            "http_endpoint": f"http://127.0.0.1:{port}",
            "current_tab": tab.to_dict() if tab else None,
        }, ensure_ascii=False, indent=2)

    @register_action(
        short_desc="(container_path)，上传文件前必须将容器内路径转换为宿主机路径",
        description="将容器内路径转换为宿主机真实路径。"
                    "浏览器 CDP 文件上传在宿主机执行，Agent 拿到的是容器内路径，"
                    "需要用本 action 转换后才能用于上传。",
        param_infos={"container_path": "容器内文件路径（如 ~/site_knowledge/xxx/readme.md 或 /data/agents/xxx/...）"},
    )
    async def resolve_host_path(self, container_path: str) -> str:
        """将容器内路径转换为宿主机路径，供 CDP 文件上传等场景使用。"""
        root = self.root_agent
        agent_name = root.name
        task_id = getattr(root, "current_task_id", None) or "default"

        host_path = root.runtime.paths.container_path_to_host(
            container_path, agent_name, task_id
        )

        if host_path is None:
            return json.dumps({
                "error": f"无法转换路径: {container_path}（不在容器可映射范围内，必须是home目录或者~/current_task目录下的文件）",
            }, ensure_ascii=False)

        # 检查文件是否存在
        exists = host_path.exists()
        return json.dumps({
            "container_path": container_path,
            "host_path": str(host_path),
            "exists": exists,
        }, ensure_ascii=False)

    @register_action(
        short_desc="(mode)切换工作模式。mode='learning' 进入学习模式，mode='automation' 进入自动化模式。必须根据当前情况切换到合适的模式。",
        description="切换工作模式。mode='learning' 进入学习模式，mode='automation' 进入自动化模式。"
                    "会重建 system prompt（使用 profile 中对应的模式 persona）。",
        param_infos={"mode": "工作模式：'learning' 或 'automation'"},
    )
    async def set_work_mode(self, mode: str) -> str:
        """切换工作模式，用新 persona 重建 system prompt。"""
        root = self.root_agent
        profile = root.profile

        mode_content = profile.get(f"{mode}_mode")
        if not mode_content:
            return json.dumps({"error": f"未知模式: {mode}，支持: learning, automation"}, ensure_ascii=False)

        # 用新 persona 重新渲染模板
        template = root.get_prompt_template("SYSTEM_PROMPT")
        self.system_prompt = root.render_template(
            template,
            user_name=root.runtime.user_agent_name,
            agent_name=root.name,
            yellow_pages_section=root.post_office.yellow_page_exclude_me(root.name) or "",
            persona=mode_content,
        )

        # 构建完整 system prompt（注入 core_prompt）并更新 messages[0]
        full_prompt = self._build_system_prompt()
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = full_prompt

        # 重新注入 site knowledge
        sk_loader = getattr(self, '_site_knowledge_loader', None)
        if sk_loader:
            sk_loader.reload_and_update_prompt(self)

        root._current_work_mode = mode

        return json.dumps({"status": "ok", "mode": mode}, ensure_ascii=False)

    @register_action(
        short_desc="[site_key] 加载指定站点的完整知识, site_key 为 site_key 行内容（url_prefix:desc:dir_name）",
        description="[site_key] 加载指定站点的完整知识, site_key 为注入文本中 site_key 行的完整内容",
        param_infos={"site_key": "站点 site_key（来自注入文本的 site_key 行，格式 url_prefix:desc:dir_name）"},
    )
    async def load_site_knowledge(self, site_key: str) -> str:
        loader = getattr(self, '_site_knowledge_loader', None)
        if not loader:
            return json.dumps({"error": "site knowledge loader 未初始化"})
        result = loader.set_current_site(site_key)

        # 即时更新 system prompt，下次 LLM 调用立即生效
        loader.reload_and_update_prompt(self)

        return result

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
