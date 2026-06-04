"""
Shared browser automation infrastructure.

Single source of truth for Chrome/CDP singletons, agent-level state,
and helper functions. Both browser_automation and browser_control
skills import from this module to share one Chrome instance.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional

from .chrome_manager import ChromeManager
from .cdp_client import CDPClient
from .tab_manager import TabManager, TabInfo
from .browser_events import BrowserEventListener

logger = logging.getLogger(__name__)

# ── 进程级单例（一个 Chrome 实例服务所有 Agent）─────────────
# 用 dict 容器持有可变引用，确保 from _shared import infra 后
# 对 infra["cdp_client"] 的修改对所有导入者可见。

infra: dict = {
    "chrome_manager": None,
    "cdp_client": None,
    "tab_manager": None,
    "event_listener": None,
}
_init_lock = asyncio.Lock()

# ── Agent 级状态（按 agent_name 索引，跨 MicroAgent 保持）──

# 每个 agent 的当前 tab
_agent_current_tab: dict[str, TabInfo] = {}
_agent_last_session: dict[str, str] = {}  # agent_name → last known session_id
_agent_env_callbacks: dict[str, callable] = {}  # agent_name → async callable(target_id) 更新 CDP_CURRENT_TAB_ID


def _trigger_env_callback(agent_name: str, target_id: str):
    """触发 agent 的 CDP 环境变量更新回调（如果已注册）。"""
    env_cb = _agent_env_callbacks.get(agent_name)
    if env_cb:
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(env_cb(target_id))
        except RuntimeError:
            pass


async def shutdown_browser_infra():
    """Stop Chrome and clean up all browser automation resources.

    Called during graceful shutdown to ensure Chrome is terminated.
    """
    cdp = infra["cdp_client"]
    mgr = infra["chrome_manager"]

    if cdp:
        try:
            await cdp.close()
        except Exception as e:
            logger.debug(f"CDP client close error: {e}")
        infra["cdp_client"] = None

    if mgr:
        try:
            await mgr.stop()
        except Exception as e:
            logger.debug(f"Chrome manager stop error: {e}")
        infra["chrome_manager"] = None

    logger.info("Browser infrastructure shut down")


def _update_current_tab(agent_name: str, target_id: str):
    """更新 agent 的当前活动 tab（由 BrowserEventListener 调用）。"""
    tab_mgr = infra["tab_manager"]
    if not tab_mgr or not target_id or not agent_name:
        return
    tab = tab_mgr._tabs.get(target_id)
    if tab:
        _agent_current_tab[agent_name] = tab
        _trigger_env_callback(agent_name, target_id)


def _on_tab_removed(target_id: str, agent_name: str):
    """Tab 被销毁且 agent 无剩余 tab 时，清空 current_tab 引用。"""
    current = _agent_current_tab.get(agent_name)
    if current and current.target_id == target_id:
        _agent_current_tab.pop(agent_name, None)
        _trigger_env_callback(agent_name, "")


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
    cdp = infra["cdp_client"]
    if not cdp:
        return
    try:
        await cdp.send(
            "Runtime.evaluate", {"expression": js},
            session_id=tab.session_id, timeout=3,
        )
    except Exception:
        pass


async def _auto_restore_ui(tab: TabInfo):
    """通知前端 UI 可以恢复（1秒延迟防抖）。"""
    js = "(window.__bh_set_automation_mode__ || function(){})(false)"
    cdp = infra["cdp_client"]
    if not cdp:
        return
    try:
        await cdp.send(
            "Runtime.evaluate", {"expression": js},
            session_id=tab.session_id, timeout=3,
        )
    except Exception:
        pass


async def _cdp_send_with_recovery(method: str, params: dict = None,
                                   tab: TabInfo = None,
                                   timeout: float = 30) -> dict:
    """发送 CDP 命令，遇到 session 失效自动 re-attach 并重试一次。

    tab.session_id 会被 recover_session 自动更新。
    """
    cdp = infra["cdp_client"]
    listener = infra["event_listener"]
    try:
        return await cdp.send(method, params, session_id=tab.session_id, timeout=timeout)
    except Exception as e:
        if not listener or not listener.is_session_error(e):
            raise
        if not tab.target_id:
            raise
        logger.warning(f"Session error for {tab.target_id[:12]}: {e}, recovering...")
        new_sid = await listener.recover_session(tab.target_id)
        if not new_sid:
            raise
        # tab.session_id 已被 recover_session 通过 tab_mgr.update_session_id 更新
        return await cdp.send(method, params, session_id=new_sid, timeout=timeout)


def _tab_not_found_msg(invalid_id: str) -> str:
    """当 tab_id 不正确时，生成包含所有可用 tab 列表的错误消息。"""
    lines = []
    tab_mgr = infra["tab_manager"]
    if tab_mgr:
        for tab in tab_mgr._tabs.values():
            lines.append(f"  - tab_id: {tab.target_id}, url: {_short_url(tab.url)}, title: {tab.title}")
    tab_list = "\n".join(lines) if lines else "  (无可用 tab)"
    return (f"tab_id '{invalid_id}' 不正确。当前可用的 tab：\n"
            f"{tab_list}\n"
            f"(url 仅显示域名和首段路径，完整信息请调用 list_tabs())")


async def _get_shared_infra(profile_dir: str, port: int = 9222):
    """获取或创建共享的 Chrome + CDP + TabManager 基础设施。

    通过 --remote-debugging-pipe 用文件描述符与 Chrome 通信，
    不经过网络，不受代理/防火墙影响。
    """
    async with _init_lock:
        cdp = infra["cdp_client"]
        if cdp and cdp._connected:
            return infra["cdp_client"], infra["tab_manager"], infra["event_listener"]

        # 重连：保留现有 TabManager/EventListener，只重连 CDPClient
        if cdp is not None:
            try:
                await cdp.connect()
                if infra["event_listener"]:
                    await infra["event_listener"].resubscribe_all()
                return infra["cdp_client"], infra["tab_manager"], infra["event_listener"]
            except Exception as e:
                logger.warning(f"CDP reconnect failed, reinitializing: {e}")

        # 首次初始化：启动 Chrome + pipe 连接
        chrome_mgr = ChromeManager(profile_dir=profile_dir, port=port)
        pipe_fds = await chrome_mgr.ensure_started()

        cdp = CDPClient(pipe_fds=pipe_fds)
        await cdp.connect()

        tab_mgr = TabManager(cdp)

        listener = BrowserEventListener(
            cdp, tab_mgr,
            on_current_tab_change=_update_current_tab,
            on_tab_removed=_on_tab_removed,
        )
        # 注册连接状态回调：重连时 resubscribe
        async def _on_cdp_status(connected):
            if connected:
                await listener._on_reconnected()
        cdp.on_status_change(_on_cdp_status)
        await listener.start_target_discovery()

        infra["chrome_manager"] = chrome_mgr
        infra["cdp_client"] = cdp
        infra["tab_manager"] = tab_mgr
        infra["event_listener"] = listener

        return cdp, tab_mgr, listener


def _make_env_update_callback(root_agent, sock_path: str):
    """创建异步回调，在 tab 变化时更新 CDP 环境变量（两个都设，覆盖 shell 重启等丢失场景）。"""
    async def _update_cdp_env(target_id):
        local_session = getattr(root_agent, 'local_session', None)
        if not local_session:
            return
        env_cmd = (
            f'export CDP_SOCKET_PATH="{sock_path}"\n'
            f'export CDP_CURRENT_TAB_ID="{target_id}"\n'
        )
        try:
            await asyncio.wait_for(
                asyncio.to_thread(local_session.execute, env_cmd),
                timeout=5,
            )
        except asyncio.TimeoutError:
            logger.debug("Skipped CDP env update: shell busy")
        except Exception:
            logger.debug("Skipped CDP env update: execute failed")
    return _update_cdp_env


# ── Common Browser Skill Mixin ─────────────────────────────
# 所有浏览器相关的 action 实现（无 @register_action 装饰器）。
# 子类 Browser_automationSkillMixin 和 Browser_controlSkillMixin
# 继承此类，并用 @register_action 薄壳包装需要暴露的方法。

class BrowserCommonMixin:
    """浏览器公共 Skill Mixin — 共享基础设施和 action 实现。

    子类应：
    1. 设置 _skill_description 类属性（各自的技能描述）
    2. 用 @register_action 薄壳包装需要暴露的方法
    """

    # ── Internal helpers ────────────────────────────────────

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
        if local_session:
            tab = self._get_current_tab()
            if sock_path:
                env_cmds = (
                    f'export CDP_SOCKET_PATH="{sock_path}"\n'
                    f'export CDP_CURRENT_TAB_ID="{tab.target_id if tab else ""}"\n'
                )
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(local_session.execute, env_cmds),
                        timeout=5,
                    )
                    logger.info(f"CDP env set: SOCK={sock_path}, TAB={tab.target_id[:12] if tab else 'None'}")
                except Exception as e:
                    logger.warning(f"CDP env setup failed: {e}")
                # 注册 tab 变化时自动更新 CDP 环境变量的回调（两个都设）
                _agent_env_callbacks[agent_name] = _make_env_update_callback(self.root_agent, sock_path)
            else:
                logger.warning(f"CDP env skipped: sock_path is None (sid={current_sid[:8] if current_sid else 'None'}, "
                               f"chrome_mgr={bool(infra['chrome_manager'])}, cdp={bool(infra['cdp_client'])})")
        else:
            logger.debug("CDP env skipped: no local_session")

    async def _cleanup_old_session_tabs(self, agent_name: str, current_session_id: str):
        """通过 CDP 查询 Chrome 所有 page，关闭属于该 agent 旧 session 的 tab，收养匹配的 tab。

        对每个 page：
        1. 临时 attach → Runtime.evaluate 读 window.__bh_agent_meta__
        2. agent_name 匹配 且 agent_session_id ≠ 当前 session → 关闭
        3. agent_name 匹配 且 agent_session_id == 当前 session → 收养（注册到 TabManager + 设为 current_tab）
        4. 否则 detach，跳过
        """
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
        adopt_candidates = []  # (target_id, url) 匹配当前 session 的 tab
        for page in pages:
            tid = page.get("targetId", "")
            url = page.get("url", "")
            if not tid:
                continue

            # 临时 attach 读取 __bh_agent_meta__
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

            # 读完立即 detach
            if temp_sid:
                try:
                    await infra["cdp_client"].send(
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
                await infra["cdp_client"].close_target(tid)
                # 同步清理 infra["tab_manager"]
                infra["tab_manager"]._tabs.pop(tid, None)
                for ats in infra["tab_manager"]._agent_tabs.values():
                    ats.discard(tid)
                closed += 1
            except Exception as e:
                logger.warning(f"Failed to close tab {tid[:12]}: {e}")

        # 收养匹配当前 session 的 tab（系统恢复/重启场景）
        if adopt_candidates:
            for tid, url in adopt_candidates:
                if infra["tab_manager"]._tabs.get(tid):
                    continue  # 已在 TabManager 中跟踪，跳过
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

            # 选择 current_tab：优先 active（visibilityState=visible），否则最后一个
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
                logger.info(
                    f"Adopted current_tab: {best.target_id[:12]} "
                    f"(url={best.url[:60]})"
                )

        # 如果 current_tab 被关了，更新到剩余 tab
        current = _agent_current_tab.get(agent_name)
        if current:
            remaining = infra["tab_manager"].get_agent_tabs_sync(agent_name)
            still_exists = any(t.target_id == current.target_id for t in remaining)
            if not still_exists:
                _agent_current_tab[agent_name] = remaining[0] if remaining else None

        if closed:
            logger.info(
                f"Session cleanup: closed {closed} old tabs for '{agent_name}'"
            )

    # ── Action implementations (no @register_action) ───────

    async def open_browser(self) -> str:
        """启动/连接浏览器。"""
        await self._ensure_browser()
        agent_name = self._agent_name()

        # 确保至少有一个 tab
        tabs = await infra["tab_manager"].get_agent_tabs(agent_name)
        if not tabs:
            tab = await infra["tab_manager"].create_tab(agent_name)
            self._set_current_tab(tab)
            if infra["event_listener"]:
                await infra["event_listener"].ensure_bridge(tab.session_id)
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

    async def open_url(self, url: str) -> str:
        """打开 URL。复用当前 tab（如有），否则新建。"""
        await self._ensure_browser()
        agent_name = self._agent_name()

        # 复用当前 tab，而不是每次都新建
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

    async def find_selector(self, instruction_text: str, tab_id: str = None) -> str:
        from agentmatrix.core.sub_agent import SubAgentShell

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
            "- 所以在本身没有稳定属性的情况下，优先找到目标元素层级关系最近的稳定元素，然后在缩小的作用域里进行更简单的定位"
            "- 避免使用无语义、随机生成的属性来作为定位依据"
            "5. 可以用 __bh_test 或 __bh_test_xpath 验证selector匹配元素的数量"
            "6. 用 return_result(result={\"selector\": \"找到的CSS选择器或XPath\", \"additional_info\": \"元素描述\"}) 返回结果（CSS selector 直接返回，XPath 以 'xpath:' 前缀返回）\n"
            "用户完全不懂技术，并且缺乏耐心，所以无论你做什么action，都要用 keep_user_from_bored 来说点什么避免用户长时间等待。可以通俗的解释工作，或者说一些相关话题、有趣又有智慧的评论，避免用户觉得无聊"
        )

        sub = SubAgentShell(
            parent=self.root_agent,
            name=f"{self.root_agent.name}_dom_explorer",
            available_skills=["browser_automation.dom_explorer"],
            system_prompt=prompt,
            result_params={"selector": "CSS选择器或XPath", "additional_info": "元素描述"},
            micro_agent_attrs={"_pinned_tab_id": tab_id},
        )

        try:
            result = await sub.execute(
                task=(
                    f"用户对于要找的元素的描述: {instruction_text}\n"
                    f"当前页面: {tab.url}\n"
                    f"tab_id: {tab_id}\n\n"
                    "请找到用户需要的元素的稳定定位表达式。"
                ),
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
        finally:
            # 清理 SubAgent 可能残留的 overlay
            try:
                if infra["cdp_client"] and infra["cdp_client"]._connected:
                    await infra["cdp_client"].send(
                        "Runtime.evaluate",
                        {"expression": "window.__bh_cleanup_all && __bh_cleanup_all()"},
                        session_id=tab.session_id,
                        timeout=3,
                    )
            except Exception:
                pass

    async def find_unique_selector_by_xy(self, additional_info: str, tab_id: str = None, x: int = 0, y: int = 0) -> str:
        from agentmatrix.core.sub_agent import SubAgentShell

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
            "- 所以在本身没有稳定属性的情况下，优先找到目标元素层级关系最近的稳定元素，然后在缩小的作用域里进行更简单的定位"
            "- 避免使用无语义、随机生成的属性来作为定位依据"
            "4. 用 __bh_test 或 __bh_test_xpath 验证唯一性（count 必须为 1）\n"
            "5. 不唯一则调整，直到唯一且稳定（不依赖动态、随机的属性、数量关系）\n"
            "6. 用 return_result(result={\"selector\": \"找到的CSS选择器或XPath\", \"additional_info\": \"元素描述\"}) 返回结果（CSS selector 直接返回，XPath 以 'xpath:' 前缀返回）\n"
            "用户完全不懂技术，并且缺乏耐心，所以无论你做什么action，都要用 keep_user_from_bored 来说点什么避免用户长时间等待。可以通俗的解释工作，或者说一些相关话题、有趣又有智慧的评论，避免用户觉得无聊"
        )

        sub = SubAgentShell(
            parent=self.root_agent,
            name=f"{self.root_agent.name}_dom_explorer",
            available_skills=["browser_automation.dom_explorer"],
            system_prompt=prompt,
            result_params={"selector": "CSS选择器或XPath", "additional_info": "元素描述"},
            micro_agent_attrs={"_pinned_tab_id": tab_id},
        )

        try:
            result = await sub.execute(
                task=(
                    f"用户在页面上指向了一个位置，描述: {additional_info}\n"
                    f"坐标: x={x}, y={y}\n"
                    f"当前页面: {tab.url}\n"
                    f"tab_id: {tab_id}\n\n"
                    "请找到用户想指的交互元素的稳定唯一定位表达式。"
                ),
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
        finally:
            # 清理 SubAgent 可能残留的 overlay
            try:
                if infra["cdp_client"] and infra["cdp_client"]._connected:
                    await infra["cdp_client"].send(
                        "Runtime.evaluate",
                        {"expression": "window.__bh_cleanup_all && __bh_cleanup_all()"},
                        session_id=tab.session_id,
                        timeout=3,
                    )
            except Exception:
                pass

    async def confirm_element(self, selector: str, tab_id: str = None) -> str:
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

        js = f"window.__bh_confirm__ ? window.__bh_confirm__({json.dumps(selector)}) : window.__bh_confirm({json.dumps(selector)})"

        try:
            await infra["cdp_client"].send(
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

            # 截断过大返回值，防止撑爆 context
            _MAX_RETURN_CHARS = 8000
            if isinstance(value, (dict, list)):
                text = json.dumps(value, ensure_ascii=False)
            else:
                text = str(value)
            if len(text) > _MAX_RETURN_CHARS:
                size_kb = len(text.encode("utf-8", errors="replace")) // 1024
                return (f"eval_js 返回值过大（{size_kb} KB），已截断。"
                        f"请修改代码只返回需要的信息（如 length、特定字段），"
                        f"或用脚本将结果写入文件再处理。"
                        f"前 {_MAX_RETURN_CHARS} 字符预览：\n{text[:_MAX_RETURN_CHARS]}")
            return text
        except Exception as e:
            logger.warning(f"[eval_js] CDP error: {e}")
            return json.dumps({"error": str(e)})

    async def try_cdp_command(self, method: str, params=None, tab_id: str = None) -> str:
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
            tab = infra["tab_manager"]._tabs.get(tab_id) if infra["tab_manager"] else None
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
            "\n"
            "# 从环境变量读取连接信息（系统会自动注入，绝对不可硬编码）\n"
            "SOCK = os.environ.get('CDP_SOCKET_PATH', '')\n"
            "TAB_ID = os.environ.get('CDP_CURRENT_TAB_ID', '')\n"
            "if not SOCK or not TAB_ID:\n"
            "    # 环境变量为空说明 CDP 连接未就绪或 shell 已重启，需先调用 get_cdp_info() 获取连接信息，\n"
            "    # 再通过 bash 执行 export 设置环境变量后重新运行脚本。不要等待或重试旧的空值。\n"
            "    raise RuntimeError('CDP 环境变量未设置，请先调用 get_cdp_info() 并 export 后重试')\n"
            "s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)\n"
            "s.connect(SOCK)\n"
            "\n"
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
            "# 【必须】每次脚本运行都要重新 attach，拿到新的 sessionId，不可省略\n"
            "# 不要硬编码或复用旧的 sessionId\n"
            "# 一个 socket 连接同一时间只能串行执行（发一个请求，等响应，再发下一个）\n"
            "r = cdp('Target.attachToTarget', {'targetId': TAB_ID, 'flatten': True})\n"
            "sid = r['sessionId']  # 后续所有 tab 操作都要传 session_id=sid\n"
            "\n"
            "cdp('Page.enable', session_id=sid)\n"
            "cdp('Page.navigate', {'url': 'https://example.com'}, session_id=sid)\n"
            "r = cdp('Runtime.evaluate', {'expression': 'document.title'}, session_id=sid)\n"
            "print(r.get('result', {}).get('value'))\n"
            "s.close()\n"
        )

        notes = (
            "注意事项：\\n"
            "- 一个 socket 连接同一时间只能有一个未完成的请求（发一个，等响应，再发下一个）\\n"
            "- 操作 tab 必须先 Target.attachToTarget 拿到 sessionId，每次脚本运行都要重新 attach，不可复用旧的 sessionId\\n"
            "- CDP_SOCKET_PATH 和 CDP_CURRENT_TAB_ID 已自动注入环境变量，直接从 os.environ 读取，不要硬编码\\n"
            "- 如果脚本运行时发现环境变量为空或不存在：说明 CDP 连接未就绪或 shell 已重启。应先调用 get_cdp_info() 获取 socket_path 和 target_id，然后通过 bash 执行 export 设置环境变量，再重新运行脚本。不要等待、不要重试旧值\\n"
            "- Chrome 重启后 socket 会重建，脚本重连即可\\n"
            "- 刷新页面：不要用 location.reload()（会触发 beforeunload 弹窗导致 CDP session 阻塞），应使用 CDP 命令 Page.navigate 到当前 URL，或 Page.reload（绕过 beforeunload）"
        )

        return json.dumps({
            "status": "ok",
            "socket_path": sock_path,
            "current_tab": {
                "target_id": tab.target_id,
                "url": tab.url,
                "title": tab.title,
            } if tab else None,
            "example_code": example_code,
            "notes": notes,
        }, ensure_ascii=False, indent=2)

    async def set_work_mode(self, mode: str) -> str:
        """切换工作模式，用新 persona 重建 system prompt。"""
        root = self.root_agent
        profile = root.profile

        mode_content = profile.get(f"{mode}_mode")
        if not mode_content:
            return json.dumps({"error": f"未知模式: {mode}，支持: develop, execute"}, ensure_ascii=False)

        # 用新 persona 重新渲染模板
        template = root.get_prompt_template("SYSTEM_PROMPT")
        self.system_prompt = root.render_template(
            template,
            user_name=root.runtime.user_agent_name,
            agent_name=root.name,
            yellow_pages_section=root.post_office.yellow_page_exclude_me(root.name) or "",
            persona=mode_content,
        )

        # 构建完整 system prompt（注入 action list）并更新 messages[0]
        full_prompt = self._finalize_system_prompt()
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = full_prompt

        root._current_work_mode = mode

        return json.dumps({"status": "ok", "mode": mode}, ensure_ascii=False)

    async def load_site_knowledge(self, site_key: str, process_dir_name: str = None) -> str:
        loader = getattr(self, '_site_knowledge_loader', None)
        if not loader:
            return json.dumps({"error": "site knowledge loader 未初始化"})
        result = loader.set_current_site(site_key, process_dir_name)
        result_data = json.loads(result)
        if result_data.get("error"):
            return result

        # 清除 message history 中所有旧的 <site-knowledge> 块
        from agentmatrix.desktop.browser_collab_agent import BrowserCollabAgent
        BrowserCollabAgent._purge_sk_from_messages(self.messages)
        # 同时清除旧的 <site-knowledge-hint> 块
        BrowserCollabAgent._purge_sk_hints(self.messages)

        # 生成内容并用 tag 包裹
        tab = _agent_current_tab.get(self._agent_name())
        url = tab.url if tab else ""
        content = loader.load(url)
        if not content:
            return json.dumps({"status": "ok", "site_url_prefix": result_data.get("site_url_prefix", site_key)},
                              ensure_ascii=False)
        tagged = f"<site-knowledge>\n{content}\n</site-knowledge>"
        return tagged

    async def skill_cleanup(self):
        """MicroAgent 执行结束时清理。

        MicroAgent 持久化模式下，不注销 agent input_queue。
        不关闭 tab，不关闭浏览器——这些是跨 MicroAgent 会话保持的。
        """
        # 不注销 agent input_queue — agent 生命周期跨 execute 复用
        logger.info("CDP Browser skill cleanup done (tabs preserved, agent queue kept)")
