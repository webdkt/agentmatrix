"""
BasicAgent — Core 层通用 Agent reference implementation。

信号驱动架构：
- input_queue 接收外部信号（任何来源：邮件、浏览器、API、...）
- _main_loop 消费 queue → _route_signal
- _resolve_session(signal) 匹配 session（子类可 override）
- _activate_session 投递信号到 MicroAgent.signal_queue → execute()
- MicroAgent 持久化（首次 activate 创建，之后复用）
- Lazy deactivate（只在切换到不同 session 时）

子类需要：
- 设置 brain, cerebellum（在 __init__ 之后，由 runtime 注入）
- 设置 session_manager
- override _resolve_session() 如果需要自定义路由
- override _get_system_prompt() 提供 system prompt
- override _create_session_store() 提供 session 持久化
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from .agent_shell import AgentShell
from .log_util import AutoLoggerMixin
from .micro_agent import MicroAgent
from .signals import CoreEvent
from .state_manager import StateManagerMixin

logger = logging.getLogger(__name__)


class BasicAgent(AutoLoggerMixin, StateManagerMixin, AgentShell):
    """
    Core 层通用 Agent — 信号驱动 + session 管理 + MicroAgent 持久化。

    提供 reference 实现：
    - 三段信号路由（无 active / 同 session / 不同 session）
    - MicroAgent 创建一次，复用（首次 activate 时创建）
    - Lazy deactivate（只在切换 session 时调用）
    - execute() 保持原有语义（处理当前信号后返回）

    子类通过 override 点添加具体业务逻辑。
    """

    _log_from_attr = "name"

    def __init__(self, profile: dict, profile_path: str = None):
        self.name = profile["name"]
        self.profile = profile
        self.profile_path = profile_path

        # ── 信号路由 ──
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self.event_queue: asyncio.Queue = asyncio.Queue()  # Core → Shell 事件输出
        self.active_session_id: Optional[str] = None
        self.active_micro_agent: Optional[MicroAgent] = None
        self._session_task: Optional[asyncio.Task] = None
        self.waiting_signals: list = []
        self.current_session: Optional[dict] = None

        # ── 组件（子类或 runtime 注入）──
        self.brain = None
        self.cerebellum = None
        self.session_manager = None

        # ── Skills ──
        self.skills: List[str] = profile.get("skills", [])

        # ── 状态管理（pause/resume/stop/checkpoint）──
        self._init_state_manager()

        # ── 事件消费者 ──
        self._event_task: Optional[asyncio.Task] = None

        # ── 任务引用 ──
        self._main_task: Optional[asyncio.Task] = None

        self.logger.info(f"BasicAgent '{self.name}' initialized")

    # ==========================================
    # 生命周期
    # ==========================================

    async def run(self):
        """启动 agent — 开始消费 input_queue。"""
        self._main_task = asyncio.create_task(self._main_loop())
        try:
            await self._main_task
        except asyncio.CancelledError:
            if self._main_task:
                self._main_task.cancel()
            raise

    async def _main_loop(self):
        """消费 input_queue，路由信号。子类可 override 做信号预处理（如 Email 包装）。"""
        while True:
            await self.checkpoint()
            signal = await self.input_queue.get()
            try:
                await self._route_signal(signal)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.exception(f"Error routing signal in {self.name}")
            finally:
                self.input_queue.task_done()

    # ==========================================
    # 信号路由（三段式）
    # ==========================================

    async def _route_signal(self, signal):
        """
        路由信号到正确的 session。

        三种情况：
        1. 无 active session → activate
        2. 同 session → 投递 signal_queue（如 execute 已结束则 re-execute）
        3. 不同 session → 如 execute 已结束则切换，否则暂存

        Args:
            signal: 实现 Signal 协议的对象
        """
        session = await self._resolve_session(signal)
        session_id = session["session_id"]

        if self.active_session_id is None:
            # 情况 1：无 active session → activate
            await self._activate_session(session, signal)

        elif self.active_session_id == session_id:
            # 情况 2：同 session → 投递
            self.active_micro_agent.signal_queue.put_nowait(signal)
            if self._session_task and self._session_task.done():
                # execute 已结束 → 重新跑一次（不做 deactivate）
                self._start_session_task(session)

        else:
            # 情况 3：不同 session
            if self._session_task and self._session_task.done():
                # execute 已结束 → 安全切换
                await self._deactivate_session(self.current_session)
                await self._activate_session(session, signal)
            else:
                # execute 还在跑 → 暂存
                self.waiting_signals.append(signal)
                self.logger.debug(
                    f"Signal queued for session {session_id[:8]} "
                    f"(active: {self.active_session_id[:8]})"
                )

    # ==========================================
    # Session 管理
    # ==========================================

    async def _activate_session(self, session: dict, first_signal):
        """
        激活 session：复用/创建 MicroAgent，投递首条信号，启动 execute。

        MicroAgent 持久化：首次创建，之后复用（不管 session 是否相同）。
        """
        session_id = session["session_id"]
        self.active_session_id = session_id
        self.current_session = session

        # MicroAgent 持久化：首次创建
        if self.active_micro_agent is None:
            self.active_micro_agent = self._create_micro_agent()
            self.logger.info(
                f"MicroAgent created (persistent, skills: {self.skills})"
            )

        # 子类 hook（workspace 切换、container session 等）
        await self._on_activate_session(session, first_signal)

        # 投递首条信号
        self.active_micro_agent.signal_queue.put_nowait(first_signal)

        # 启动 execute
        self._start_session_task(session)

        self.logger.info(f"Session {session_id[:8]} activated")

    async def _deactivate_session(self, session: dict):
        """
        停用 session：保存，清理 active 状态。MicroAgent 不销毁。

        只在切换到不同 session 时调用（lazy deactivate）。
        同 session re-execute 不经过此方法。
        """
        if session is None:
            return

        session_id = session.get("session_id", "unknown")

        # 保存 session
        if self.session_manager:
            try:
                await self.session_manager.save_session(session)
            except Exception as e:
                self.logger.warning(f"Failed to save session on deactivate: {e}")

        # 子类 hook（状态广播、event logging 等）
        await self._on_deactivate_session(session)

        # 清理 active 状态（保留 MicroAgent）
        self.active_session_id = None
        self.current_session = None
        self._session_task = None

        self.logger.info(f"Session {session_id[:8]} deactivated")

        # 处理暂存信号
        if self.waiting_signals:
            next_signal = self.waiting_signals.pop(0)
            await self._route_signal(next_signal)

    def _start_session_task(self, session: dict):
        """启动/重启 execute task。"""
        # 取消正在进行的异步退出验证（有新 signal 来了，验证没必要了）
        if self.active_micro_agent and hasattr(self.active_micro_agent, '_exit_verification_task'):
            task = self.active_micro_agent._exit_verification_task
            if task and not task.done():
                task.cancel()
            self.active_micro_agent._exit_verification_task = None

        self._ensure_event_consumer()
        self._session_task = asyncio.create_task(
            self._run_session(self.active_micro_agent, session)
        )

    def _restart_session_if_idle(self):
        """如果 session task 已完成，重新启动（由异步退出验证调用）。"""
        if self._session_task and self._session_task.done() and self.current_session:
            self._start_session_task(self.current_session)

    async def _run_session(self, micro_agent: MicroAgent, session: dict):
        """
        运行 execute()。结束后不 deactivate，由 _route_signal 决定。

        execute() 会在 idle 时退出（_run_loop 的声明式退出）。
        _route_signal 在下一个信号到来时决定：
        - 同 session → re-execute（不 deactivate）
        - 不同 session → deactivate + activate
        """
        session_id = session["session_id"]

        try:
            result = await micro_agent.execute(
                run_label=self._get_run_label(session),
                task="",
                session_store=self._create_session_store(session),
            )
            await self._on_execute_done(session)
        except asyncio.CancelledError:
            self._handle_session_cancelled(session)
        except Exception as e:
            self.logger.error(f"Session {session_id[:8]} error: {e}")
            await self._handle_session_error(micro_agent, session, e)

        # 注意：不调用 _deactivate_session。
        # _route_signal 会在下一个信号到来时决定是否切换。

    # ==========================================
    # 事件消费者
    # ==========================================

    def _ensure_event_consumer(self):
        """确保 event_consumer task 在运行。"""
        if self._event_task and not self._event_task.done():
            return
        self._event_task = asyncio.create_task(self._consume_events())

    async def _consume_events(self):
        """持续消费 agent 的 event_queue（所有 MicroAgent 共享）。"""
        while True:
            try:
                event = await self.event_queue.get()
            except asyncio.CancelledError:
                break

            session_id = self.active_session_id or "unknown"
            try:
                await self._handle_core_event(event, session_id)
            except Exception as e:
                self.logger.warning(f"Error handling core event: {e}")

    # ==========================================
    # MicroAgent 工厂
    # ==========================================

    def _create_micro_agent(self) -> MicroAgent:
        """创建持久 MicroAgent。子类可 override 自定义配置。"""
        return MicroAgent(
            parent=self,
            name=self.name,
            available_skills=self.skills if self.skills else None,
            system_prompt=self._get_system_prompt(),
        )

    # ==========================================
    # Override 点（子类实现）
    # ==========================================

    async def _resolve_session(self, signal) -> dict:
        """
        根据信号确定 session。Reference 实现：读 signal.session_id。

        子类 override 示例：
        - Desktop: email → reply mapping → session
        - 浏览器: agent_name → 最近 session
        """
        session_id = getattr(signal, 'session_id', None)
        if session_id and self.session_manager:
            return await self.session_manager.get_session_by_id(session_id)
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _resolve_session "
            f"or set session_manager"
        )

    def _get_system_prompt(self) -> str:
        """System prompt 模板。子类 override。"""
        return ""

    def _get_run_label(self, session: dict) -> str:
        """execute() 的 run_label。子类可 override。"""
        return "Process Signal"

    def _create_session_store(self, session: dict):
        """创建 SessionStore。子类 override 以提供持久化。"""
        return None

    async def _on_activate_session(self, session: dict, first_signal=None):
        """Session 激活后的 hook。子类 override（workspace 切换等）。"""
        pass

    async def _on_deactivate_session(self, session: dict):
        """Session 停用前的 hook。子类 override（状态广播等）。"""
        pass

    async def _handle_core_event(self, event: CoreEvent, session_id: str):
        """处理 CoreEvent。子类 override（持久化/广播）。"""
        pass

    def _handle_session_cancelled(self, session: dict):
        """Session 被取消时的处理。子类可 override。"""
        pass

    async def _handle_session_error(
        self, micro_agent: MicroAgent, session: dict, error: Exception
    ):
        """Session 出错时的处理。子类可 override。"""
        pass

    async def _on_execute_done(self, session: dict):
        """execute() 正常结束后的 hook。子类 override（状态更新等）。"""
        pass

    # ==========================================
    # AgentShell 协议 — 部分默认实现
    # ==========================================

    # brain, cerebellum, logger — 通过 __init__ 设置或 runtime 注入
    # get_prompt_template, generate_working_notes, compress_messages — 子类实现
    # checkpoint — 由 StateManagerMixin 提供
    # get_md_skill_prompt, is_llm_available, notify_llm_unavailable, wait_for_llm_recovery — 子类实现
