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
