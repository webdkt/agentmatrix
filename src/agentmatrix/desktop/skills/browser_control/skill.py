"""
Browser Control Skill — 浏览器控制操作和自动化（精简版）。

与 browser_automation 共享同一套 Chrome/CDP 基础设施（同一个 Chrome 实例），
仅提供浏览器控制和 DOM 探索相关的 action，不包含自动化脚本执行能力。
"""

import ast
import asyncio
import json
import logging
import os
from typing import Optional
from pathlib import Path

from agentmatrix.core.action import register_action

from agentmatrix.desktop.skills.browser_automation._shared import (
    infra,
    _agent_current_tab, _agent_last_session, _agent_sk_callbacks,
    _trigger_sk_callback, shutdown_browser_infra,
    _update_current_tab, _on_tab_removed,
    _short_url, _auto_yield_ui, _auto_restore_ui,
    _cdp_send_with_recovery, _tab_not_found_msg, _get_shared_infra,
)
from agentmatrix.desktop.skills.browser_automation.tab_manager import TabInfo
from agentmatrix.desktop.skills.browser_automation.interfaces import load_interface, list_interfaces

logger = logging.getLogger(__name__)


# ── Skill Mixin ───────────────────────────────────────────

class Browser_controlSkillMixin:
    """
    Browser Control Skill — 浏览器控制操作和自动化（精简版）

    与 browser_automation 共享同一个 Chrome 实例，
    仅提供控制、探索相关的 action。
    """

    _skill_description = """浏览器控制操作和自动化
    `~/site_knowledge`目录就是你的代码仓库。
    `~/site_knowledge`目录是网站自动化代码仓库。
    ### ~/site_knowledge 的结构
    - 根目录（~/site_knowledge)
        - index.txt: 
            - 网站列表，每行格式 `url_prefix:说明:子目录名` （整行是一个唯一的site key）
            - url_prefix 可能重复，但说明和子目录名必须不同（因为有些单体站点可能包含多个不同的子系统，结构和元素差异较大）
            - 使用 load_site_knowledge(site_key) 来加载对应站点的概览和流程列表
        - 子目录（site 目录）
            - 每个site_key对应一个子目录(site 目录），存放该站点的所有自动化知识和脚本，site目录内有：
            - readme.md: 网站说明、针对该网站的自动化特点的公共说明，流程的介绍和索引。
            - 流程子目录（process 目录），针对特定工作流程的子目录，内含该流程说明和针对该流程的自动化脚本，目录的名称即流程的名称
            - 使用 load_site_knowledge(site_key, process_dir_name) 来加载对应流程的自动化步骤和脚本列表
            - 每个流程子目录的结构
                - readme.md: 业务流程和规则的简要说明
                - step-{{step_index}}-{{step_name}}.md: 每个阶段每个步骤的说明文档，包含该步骤的具体自动化步骤。
                - scripts/ 目录：存放针对该流程的自动化脚本。自动化脚本有3类，.json (cdp命令）.js (注入浏览器执行的js脚本）,.py (python自动化脚本）

    ### site_knowledge 文件规范
    #### Python自动化脚本
    Python 脚本通过 Unix Domain Socket 与 Chrome 通信，协议为 null-terminated JSON（JSON + b'\\0'）。
    环境变量：CDP_SOCKET_PATH（socket路径）、CDP_CURRENT_TAB_ID（当前tab的target_id）。
    脚本示例：

    ```python
    import socket, json, os

    SOCK = os.environ.get("CDP_SOCKET_PATH", "/tmp/agentmatrix_chrome_cdp.sock")
    TAB_ID = os.environ.get("CDP_CURRENT_TAB_ID", "")

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK)

    _msg_id = 0
    def cdp(method, params=None, session_id=None):
        '''发送 CDP 命令并等待响应'''
        global _msg_id; _msg_id += 1
        msg = {"id": _msg_id, "method": method, "params": params or {}}
        if session_id: msg["sessionId"] = session_id
        s.sendall(json.dumps(msg).encode() + b'\\x00')
        buf = b''
        while b'\\x00' not in buf:
            chunk = s.recv(4096)
            if not chunk: raise ConnectionError("socket closed")
            buf += chunk
        resp = json.loads(buf.split(b'\\x00', 1)[0])
        if "error" in resp: raise RuntimeError(resp["error"])
        return resp.get("result", {})

    # 操作 tab 需先 attach
    r = cdp("Target.attachToTarget", {"targetId": TAB_ID, "flatten": True})
    sid = r.get("sessionId", "")
    cdp("Page.enable", session_id=sid)

    # 导航
    cdp("Page.navigate", {"url": "https://example.com"}, session_id=sid)

    # 执行 JS
    r = cdp("Runtime.evaluate", {"expression": "document.title"}, session_id=sid)
    print(r.get("result", {}).get("value"))

    s.close()
    ```

    注意事项：
    - 一个 socket 连接同一时间只能有一个未完成的请求（发一个，等响应，再发下一个），多脚本需串行执行
    - 操作 tab 需要先 Target.attachToTarget，拿到 sessionId 后传入后续命令
    - Chrome 重启后 socket 会重建，脚本重连即可

    #### Javascript: No Console Output
    eval_js 不会返回console的输出。只会返回脚本 return的结果。
    #### 正式脚本 vs 探索脚本
    ~/site_knowledge 下只能存放正式的脚本。探索脚本放在 ~/current_task/tmp 下。
    #### 流程文档 step-{{index}}-{{step_name}}.md
    - 流程文档本质上是一个执行手册，是一份"代码"
    - 流程文档的基本结构
        - Part 1（Code): 带有编号的执行步骤。每个步骤要么是（a）自动化脚本，（b）手动执行的具体js or cdp命令,或者是(c) Agent 进行判断的、分支或者循环的说明。 Part 1 的目的是让任何Agent可以按照步骤完成该流程，无需懂的业务。
        - Part 2 (Doc): 对业务逻辑的补充说明，作为参考供debug, 后续开发和版本review用。
        - Part 3 (可选）：异常处理说明。执行过程中可能出现的、无法被Part 1吸收覆盖的异常情况的说明和处理建议。
    ### 其他开发规范
    - 元素必须使用稳定的、给予语义的定位器
    - 不得进行全局撒网式的探索
    - 必须包含判断所在页面、当前状态的明确规则
    - 操作元素前必须等待其可交互
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
        if infra["event_listener"] and tab.session_id:
            await infra["event_listener"].set_agent_meta(
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
        if infra["cdp_client"] and infra["cdp_client"]._reconnecting:
            for _ in range(60):  # 最多等 30 秒
                await asyncio.sleep(0.5)
                if infra["cdp_client"]._connected:
                    break
            else:
                logger.warning("Timed out waiting for CDP reconnect")

        if infra["cdp_client"] and infra["cdp_client"]._connected:
            # 已连接 → 只需注册 agent input_queue
            if infra["event_listener"] and self.root_agent:
                infra["event_listener"].register_agent_queue(
                    self._agent_name(), self.root_agent.input_queue
                )
                infra["event_listener"].start()
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

        # Session 切换检测：关闭旧 session 的 tab，清理旧 relay
        agent_name = self._agent_name()
        current_sid = self._agent_session_id()
        last_sid = _agent_last_session.get(agent_name, "")

        if current_sid and current_sid != last_sid:
            # 停止旧 session 的 relay
            if last_sid and infra["chrome_manager"]:
                infra["chrome_manager"].stop_session_relay(last_sid)
            await self._cleanup_old_session_tabs(agent_name, current_sid)
            _agent_last_session[agent_name] = current_sid

        # 启动当前 session 的 UDS relay（如果还没有的话）
        sock_path = None
        if current_sid and infra["chrome_manager"] and infra["cdp_client"]:
            sock_path = infra["chrome_manager"].start_session_relay(current_sid, infra["cdp_client"])

        # 自动设置 CDP 环境变量到 Agent 的 bash session
        local_session = getattr(self.root_agent, 'local_session', None)
        if local_session and sock_path:
            tab = self._get_current_tab()
            env_cmds = (
                f'export CDP_SOCKET_PATH="{sock_path}"\n'
                f'export CDP_CURRENT_TAB_ID="{tab.target_id if tab else ""}"\n'
            )
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(local_session.execute, env_cmds),
                    timeout=5,
                )
            except asyncio.TimeoutError:
                logger.debug("Skipped CDP env setup: shell busy")

    async def _cleanup_old_session_tabs(self, agent_name: str, current_session_id: str):
        """通过 CDP 查询 Chrome 所有 page，关闭属于该 agent 旧 session 的 tab，收养匹配的 tab。"""
        if not infra["cdp_client"]:
            return

        try:
            pages = await infra["cdp_client"].get_pages(include_internal=False)
        except Exception as e:
            logger.warning(f"Failed to get Chrome pages for cleanup: {e}")
            return

        if not pages:
            return

        closed = 0
        adopt_candidates = []
        for page in pages:
            tid = page.get("targetId", "")
            url = page.get("url", "")
            if not tid:
                continue

            temp_sid = None
            try:
                temp_sid = await infra["cdp_client"].attach_to_target(tid)
                result = await infra["cdp_client"].send(
                    "Runtime.evaluate",
                    {"expression": "window.__bh_agent_meta__ || null",
                     "returnByValue": True},
                    session_id=temp_sid,
                    timeout=5,
                )
                meta = result.get("result", {}).get("value")
            except Exception:
                meta = None

            if temp_sid:
                try:
                    await infra["cdp_client"].send(
                        "Target.detachFromTarget",
                        {"sessionId": temp_sid},
                        timeout=5,
                    )
                except Exception:
                    pass

            if not meta:
                continue
            if meta.get("agent_name") != agent_name:
                continue
            tab_sid = meta.get("agent_session_id", "")
            if not tab_sid or tab_sid == current_session_id:
                adopt_candidates.append((tid, url))
                continue

            logger.info(
                f"Cleaning old session tab: {tid[:12]} "
                f"(old_session={tab_sid[:12]}, url={url[:60]})"
            )
            try:
                await infra["cdp_client"].close_target(tid)
                infra["tab_manager"]._tabs.pop(tid, None)
                for ats in infra["tab_manager"]._agent_tabs.values():
                    ats.discard(tid)
                closed += 1
            except Exception as e:
                logger.warning(f"Failed to close tab {tid[:12]}: {e}")

        if adopt_candidates:
            for tid, url in adopt_candidates:
                if infra["tab_manager"]._tabs.get(tid):
                    continue
                try:
                    tab = await infra["tab_manager"].adopt_tab(
                        tid, agent_name, current_session_id, url
                    )
                    await self._set_tab_agent_meta(tab)
                    logger.info(
                        f"Adopted matching-session tab: {tid[:12]} (url={url[:60]})"
                    )
                except Exception as e:
                    logger.warning(f"Failed to adopt tab {tid[:12]}: {e}")

            adopted_tabs = infra["tab_manager"].get_agent_tabs_sync(agent_name)
            if adopted_tabs and not _agent_current_tab.get(agent_name):
                best = adopted_tabs[-1]
                for t in adopted_tabs:
                    try:
                        res = await infra["cdp_client"].send(
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

        current = _agent_current_tab.get(agent_name)
        if current:
            remaining = infra["tab_manager"].get_agent_tabs_sync(agent_name)
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

        tabs = await infra["tab_manager"].get_agent_tabs(agent_name)
        if not tabs:
            tab = await infra["tab_manager"].create_tab(agent_name)
            self._set_current_tab(tab)
            if infra["event_listener"]:
                await infra["event_listener"].ensure_bridge(tab.session_id)
                await self._set_tab_agent_meta(tab)
        else:
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

        tab = self._get_current_tab()
        if not tab:
            tabs = await infra["tab_manager"].get_agent_tabs(agent_name)
            tab = tabs[0] if tabs else None
        if not tab:
            tab = await infra["tab_manager"].create_tab(agent_name)
        self._set_current_tab(tab)

        try:
            await _cdp_send_with_recovery("Page.enable", tab=tab, timeout=5)
            await _cdp_send_with_recovery("Page.navigate", {"url": url}, tab=tab, timeout=30)

            await asyncio.sleep(1)

            if infra["event_listener"]:
                await infra["event_listener"].ensure_bridge(tab.session_id)
                await self._set_tab_agent_meta(tab)

            tab = await infra["tab_manager"].refresh_tab_info(tab.target_id)
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
            tabs = await infra["tab_manager"].get_agent_tabs(agent_name)
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
            tab = await infra["tab_manager"].get_tab(target_id)
            if not tab:
                return json.dumps({"status": "error", "error": _tab_not_found_msg(target_id)}, ensure_ascii=False)
            if tab.agent_name != agent_name:
                return json.dumps({"status": "error", "error": f"Tab {target_id} 不属于当前 agent"}, ensure_ascii=False)
            await infra["tab_manager"].close_tab(target_id)
            current = self._get_current_tab()
            if current and current.target_id == target_id:
                tabs = await infra["tab_manager"].get_agent_tabs(agent_name)
                self._set_current_tab(tabs[0] if tabs else None)
            return json.dumps({"status": "ok"}, ensure_ascii=False)

        elif op == "switch_to":
            if not target_id:
                return json.dumps({"status": "error", "error": "switch_to 操作需要提供 target_id"}, ensure_ascii=False)
            tab = await infra["tab_manager"].get_tab(target_id)
            if not tab:
                return json.dumps({"status": "error", "error": _tab_not_found_msg(target_id)}, ensure_ascii=False)
            if tab.agent_name != agent_name:
                return json.dumps({"status": "error", "error": f"Tab {target_id} 不属于当前 agent"}, ensure_ascii=False)
            try:
                await infra["cdp_client"].activate_target(target_id)
                if not tab.session_id:
                    tab.session_id = await infra["cdp_client"].attach_to_target(target_id)
                    await infra["cdp_client"].enable_domains(tab.session_id)
                if infra["event_listener"]:
                    await infra["event_listener"].ensure_bridge(tab.session_id)
                self._set_current_tab(tab)
                tab = await infra["tab_manager"].refresh_tab_info(target_id)
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
            tab = infra["tab_manager"]._tabs.get(tab_id) if infra["tab_manager"] else None
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
            tab = infra["tab_manager"]._tabs.get(tab_id) if infra["tab_manager"] else None
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
        short_desc="(code, tab_id?)探索、试验js代码，不得用于测试，不得用于正式自动化执行，只用于探索和debug",
        description="向当前（或指定）tab 发送 JavaScript 代码并返回执行结果。"
                    "支持返回 Promise / 使用 await，会等待 resolve 后返回最终值。",
        param_infos={
            "code": "要执行的 JavaScript 代码字符串（支持 async/await）",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def try_js_code(self, code: str, tab_id: str = None) -> str:
        await self._ensure_browser()

        if tab_id:
            tab = infra["tab_manager"]._tabs.get(tab_id) if infra["tab_manager"] else None
            if not tab:
                return json.dumps({"error": _tab_not_found_msg(tab_id)})
        else:
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"error": "没有活动的 tab，请先用 open_url() 打开页面"})
            tab_id = tab.target_id

        try:
            result = await _cdp_send_with_recovery(
                "Runtime.evaluate",
                {
                    "expression": code,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
                tab=tab,
                timeout=15,
            )
            res = result.get("result", {})

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
        short_desc="(method, params?, tab_id?) 试验CDP协议指令。params 必须是 dict 对象，不能用于正式执行和测试，只能用于探索试验和debug，不得用于正式自动化执行",
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
    async def try_cdp_command(self, method: str, params=None, tab_id: str = None) -> str:
        await self._ensure_browser()

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
            tab = infra["tab_manager"]._tabs.get(tab_id) if infra["tab_manager"] else None
            if not tab:
                return json.dumps({"error": _tab_not_found_msg(tab_id)})
        else:
            tab = self._get_current_tab()
            if not tab:
                return json.dumps({"error": "没有活动的 tab，请先用 open_url() 打开页面"})

        try:
            _is_input = method.startswith("Input.")
            if _is_input:
                await _auto_yield_ui(tab)
            try:
                result = await _cdp_send_with_recovery(
                    method, params or {}, tab=tab, timeout=30,
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
        short_desc="() 获取cdp连接信息",
        description="获取当前 CDP 浏览器连接信息，供外部脚本连接浏览器做自动化。"
                    "返回 socket 路径、当前 tab 的 target_id、示例代码等。",
    )
    async def get_cdp_info(self) -> str:
        """返回 CDP 连接信息，供 Agent 编写 Python 代码直接连接浏览器。"""
        await self._ensure_browser()

        session_id = self._agent_session_id()
        if not session_id or not infra["chrome_manager"] or not infra["cdp_client"]:
            return json.dumps({
                "status": "error",
                "error": "Chrome 未启动或 CDP 连接未建立。请尝试重启应用。",
            }, ensure_ascii=False)

        sock_path = infra["chrome_manager"].start_session_relay(session_id, infra["cdp_client"])
        tab = self._get_current_tab()
        tab_id = tab.target_id if tab else ""

        example_code = (
            "import socket, json, os\n"
            f"SOCK = os.environ.get('CDP_SOCKET_PATH', '{sock_path}')\n"
            "TAB_ID = os.environ.get('CDP_CURRENT_TAB_ID', '')\n"
            "s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
            "s.connect(SOCK)\n"
            "_msg_id = 0\n"
            "def cdp(method, params=None, session_id=None):\n"
            "    global _msg_id; _msg_id += 1\n"
            "    msg = {'id': _msg_id, 'method': method, 'params': params or {}}\n"
            "    if session_id: msg['sessionId'] = session_id\n"
            "    s.sendall(json.dumps(msg).encode() + b'\\x00')\n"
            "    buf = b''\n"
            "    while b'\\x00' not in buf:\n"
            "        chunk = s.recv(4096)\n"
            "        if not chunk: raise ConnectionError('socket closed')\n"
            "        buf += chunk\n"
            "    resp = json.loads(buf.split(b'\\x00', 1)[0])\n"
            "    if 'error' in resp: raise RuntimeError(resp['error'])\n"
            "    return resp.get('result', {})\n"
            "\n"
            "# attach tab, then send commands\n"
            "r = cdp('Target.attachToTarget', {'targetId': TAB_ID, 'flatten': True})\n"
            "sid = r.get('sessionId', '')\n"
            "cdp('Page.enable', session_id=sid)\n"
            "cdp('Page.navigate', {'url': 'https://example.com'}, session_id=sid)\n"
            "r = cdp('Runtime.evaluate', {'expression': 'document.title'}, session_id=sid)\n"
            "print(r.get('result', {}).get('value'))\n"
            "s.close()\n"
        )

        return json.dumps({
            "status": "ok",
            "socket_path": sock_path,
            "current_tab": tab.to_dict() if tab else None,
            "example_code": example_code,
        }, ensure_ascii=False, indent=2)

    async def set_work_mode(self, mode: str) -> str:
        """切换工作模式，用新 persona 重建 system prompt。"""
        root = self.root_agent
        profile = root.profile

        mode_content = profile.get(f"{mode}_mode")
        if not mode_content:
            return json.dumps({"error": f"未知模式: {mode}，支持: develop, execute"}, ensure_ascii=False)

        template = root.get_prompt_template("SYSTEM_PROMPT")
        self.system_prompt = root.render_template(
            template,
            user_name=root.runtime.user_agent_name,
            agent_name=root.name,
            yellow_pages_section=root.post_office.yellow_page_exclude_me(root.name) or "",
            persona=mode_content,
        )

        full_prompt = self._finalize_system_prompt()
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = full_prompt

        sk_loader = getattr(self, '_site_knowledge_loader', None)
        if sk_loader:
            sk_loader.reload_and_update_prompt(self)

        root._current_work_mode = mode

        return json.dumps({"status": "ok", "mode": mode}, ensure_ascii=False)

    @register_action(
        short_desc="load_site_knowledge(site_key, process_dir_name?) 加载站点知识或具体自动化流程",
        description="加载指定站点的知识。只传 site_key 时加载站点 readme 和流程列表；"
                    "同时传 process_dir_name 时加载具体流程的 readme 和步骤列表。",
        param_infos={
            "site_key": "站点 site_key（来自注入文本的 site_key 行，格式 url_prefix:desc:dir_name）",
            "process_dir_name": "可选，自动化流程子目录名称，加载具体流程的详细知识",
        },
    )
    async def load_site_knowledge(self, site_key: str, process_dir_name: str = None) -> str:
        loader = getattr(self, '_site_knowledge_loader', None)
        if not loader:
            return json.dumps({"error": "site knowledge loader 未初始化"})
        result = loader.set_current_site(site_key, process_dir_name)
        loader.reload_and_update_prompt(self)
        return result

    # ==========================================
    # Cleanup
    # ==========================================

    async def skill_cleanup(self):
        """MicroAgent 执行结束时清理。"""
        logger.info("CDP Browser skill cleanup done (tabs preserved, agent queue kept)")
