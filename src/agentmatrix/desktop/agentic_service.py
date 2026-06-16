"""
AgenticServiceInterface — 内置 Agent 能力的后台服务基类

实现 AgentShell 协议，使后台服务可以拥有自己的 MicroAgent 循环。
服务不是 Agent，但它是一种 Shell——可以作为 MicroAgent 的 parent。

与 BasicAgent 对等的基础设施：
- 自有 event_queue（不再指向 runtime）
- 自有 input_queue（接收外部 signal）
- brain/cerebellum 从 runtime.llm_pool 获取（PoolClient facade）
- _consume_events 事件消费循环
- _signal_loop 信号消费循环
- 事件持久化到 DB + WebSocket 广播

Worker 管理：
- register_worker(worker, group) 注册到命名组（singleton 或 pool）
- dispatch_to_worker(signal, group) 将 signal 翻译为 ServiceTask 并投递给 worker
"""

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from ..core.log_util import AutoLoggerMixin
from ..core.micro_agent import MicroAgent
from ..core.signals import CoreEvent
from .service_worker import ServiceWorker, ServiceTask

logger = logging.getLogger(__name__)


class AgenticServiceInterface(AutoLoggerMixin):
    """内置 Agent 能力的后台服务基类。

    实现 AgentShell 协议，使服务可以创建和运行 MicroAgent。
    子类只需实现 _get_service_skills() 和具体的业务逻辑。

    基础设施：
    - event_queue: 自有的 asyncio.Queue，MicroAgent 的事件发到这里
    - input_queue: 自有的 asyncio.Queue，接收外部 signal
    - brain/cerebellum: 从 runtime.llm_pool 获取的 PoolClient facade
    - _consume_events(): 持续消费事件，持久化到 DB + 广播到前端
    - _signal_loop(): 持续消费 signal，调用 _handle_signal

    使用方式：
        class MyService(AgenticServiceInterface):
            def _get_service_skills(self):
                return ["knowledge_base", "file"]

            async def _handle_signal(self, signal):
                # 自定义信号处理逻辑
                self.dispatch_to_worker(signal, group="my_group")
    """

    # 按 name 创建独立 log 文件（如 WikiMaintenanceService.log），
    # 与 BasicAgent 行为对齐；内部的 MicroAgent 通过 parent.logger 共享同一文件。
    _log_from_attr = "name"

    def __init__(self, runtime):
        self._runtime = runtime
        self.name = self.__class__.__name__
        self.persona = ""

        # 基础设施：自有 event_queue（与 BasicAgent 对等）
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self._event_task: Optional[asyncio.Task] = None

        # 信号输入队列
        self.input_queue: asyncio.Queue = asyncio.Queue()
        self._signal_loop_task: Optional[asyncio.Task] = None

        # Worker 注册表：group name → worker 列表（1 个 = singleton，N 个 = pool）
        self._worker_groups: Dict[str, List[ServiceWorker]] = {}

        self._running = False

        # brain/cerebellum（从 pool 懒加载）
        self._brain = None
        self._cerebellum = None

        # 广播回调（由 runtime 注入）
        self._broadcast_message_callback = None

        # LocalSession（懒加载）—— 给 file_skill 提供 container_session
        self._container_session = None
        self.current_task_id = None

        # TodoManager（懒加载）—— 给 basic_planning.set_todo 用，纯内存模式
        self._todo_manager = None

    def _get_service_skills(self) -> List[str]:
        """子类返回此服务需要的技能列表。"""
        return []

    # ============================================================
    # Service 接口（子类按需 override）
    # ============================================================

    def get_status(self) -> dict:
        """返回 service 状态摘要。"""
        return {"running": self._running, "name": self.name}

    def get_workers(self) -> List[dict]:
        """返回所有 worker 的状态列表。"""
        return [w.get_info() for w in self.get_all_workers()]

    def get_actions(self) -> List[dict]:
        """返回可手动触发的 action 列表。默认空。"""
        return []

    async def execute_action(self, action_id: str, payload: dict = None) -> dict:
        """执行手动 action。子类 override。"""
        raise ValueError(f"Unknown action: {action_id}")

    # ============================================================
    # Worker 注册与管理
    # ============================================================

    def register_worker(self, worker: ServiceWorker, group: str = "default"):
        """注册 worker 到命名组。同 group 多个 worker = pool。"""
        self._worker_groups.setdefault(group, []).append(worker)

    def get_worker_group(self, group: str) -> List[ServiceWorker]:
        """获取命名组下的所有 worker。"""
        return self._worker_groups.get(group, [])

    def get_all_workers(self) -> List[ServiceWorker]:
        """获取所有 worker（跨组）。"""
        return [w for ws in self._worker_groups.values() for w in ws]

    def _select_from_group(self, group: str, signal=None) -> Optional[ServiceWorker]:
        """从命名组中选择一个 worker。默认：首个 idle。Override 可实现不同策略。"""
        workers = self._worker_groups.get(group)
        if not workers:
            return None
        for w in workers:
            if w.status == "idle":
                return w
        return workers[0]

    # ============================================================
    # 信号输入
    # ============================================================

    async def receive_signal(self, signal):
        """外部入口 — 将 signal 放入 input_queue。"""
        await self.input_queue.put(signal)

    def send_signal_nowait(self, signal):
        """同步版本（非阻塞），适用于从同步上下文投递。"""
        self.input_queue.put_nowait(signal)

    async def _signal_loop(self):
        """持续消费 input_queue，委托给 _handle_signal。"""
        while self._running:
            try:
                signal = await self.input_queue.get()
            except asyncio.CancelledError:
                break
            try:
                await self._handle_signal(signal)
            except Exception as e:
                logger.error(f"Error handling signal in {self.name}: {e}")

    async def _handle_signal(self, signal):
        """Override point — 子类定义如何处理每种 signal。

        默认实现：将 signal 翻译为 ServiceTask，投递到 default 组。
        """
        self.dispatch_to_worker(signal)

    # ============================================================
    # Worker 分发
    # ============================================================

    def dispatch_to_worker(self, signal, group: str = "default",
                           priority: int = 1) -> Optional[asyncio.Future]:
        """将 signal 翻译为 ServiceTask，选择 worker 并提交。

        priority 越小越优先（默认 1=普通，0=高优先级）。

        返回值：
        - Future：成功投递，await 此 future 可等待 task 完成
        - None：无可翻译的 task，或组内无可用 worker
        """
        task = self._signal_to_task(signal)
        if task is None:
            return None
        worker = self._select_from_group(group, signal)
        if worker is None:
            logger.warning(f"No worker in group '{group}' for signal: {signal}")
            return None
        return worker.submit(task, priority=priority)

    def _signal_to_task(self, signal) -> Optional[ServiceTask]:
        """将 signal 翻译为 ServiceTask。Override 可自定义翻译逻辑。"""
        return ServiceTask(
            label=f"signal-{signal.signal_type}",
            text=signal.to_text(),
        )

    # ============================================================
    # AgentShell 协议实现
    # ============================================================

    @property
    def root_agent(self):
        return self

    @property
    def container_session(self):
        """懒加载 LocalSession —— 给 file_skill 提供 shell 执行能力。"""
        if self._container_session is None:
            self._init_local_session()
        return self._container_session

    def _init_local_session(self):
        from .container.local_session import LocalSession
        import logging as _logging
        home_dir = str(self._runtime.paths.get_agent_home_dir(self.name))
        env_bin = self._runtime.paths.get_shared_env_bin()
        session = LocalSession(
            home_dir=home_dir,
            logger=_logging.getLogger(f"local_session.{self.name}"),
            env_bin_path=env_bin,
        )
        session.start()
        self._container_session = session

    def resolve_path_to_host(self, file_path: str):
        """file_skill 安全检查需要 —— 委托给 runtime.paths。"""
        return self._runtime.paths.resolve_path_to_host(
            file_path, self.name, self.current_task_id
        )

    @property
    def todo_manager(self):
        """懒加载 EphemeralTodoManager —— per-micro 隔离，basic_planning.set_todo 用。"""
        if self._todo_manager is None:
            from .ephemeral_todo import EphemeralTodoManager
            self._todo_manager = EphemeralTodoManager(self)
        return self._todo_manager

    @property
    def brain(self):
        if self._brain is None:
            self._brain = self._runtime.llm_pool.create_pool_client("default_llm")
        return self._brain

    @property
    def cerebellum(self):
        if self._cerebellum is None:
            from ..core.cerebellum import Cerebellum
            slm_client = self._runtime.llm_pool.create_pool_client("default_slm")
            self._cerebellum = Cerebellum(slm_client, self.name)
        return self._cerebellum

    @property
    def runtime(self):
        return self._runtime

    async def checkpoint(self):
        pass

    async def compress_messages(self, agent):
        if not hasattr(agent, 'messages') or len(agent.messages) <= 4:
            return

        working_notes = await self._generate_working_notes(agent.messages)

        has_system = agent.messages and agent.messages[0].get("role") == "system"
        new_user_content = f"[WORKING NOTES]\n{working_notes}\n\n请继续执行当前任务。"

        if has_system:
            agent.messages = [agent.messages[0], {"role": "user", "content": new_user_content}]
        else:
            agent.messages = [{"role": "user", "content": new_user_content}]

    async def _generate_working_notes(self, messages: list) -> str:
        conversation = ""
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if isinstance(content, str) and content:
                conversation += f"[{role}]: {content[:500]}\n\n"

        prompt = (
            "请从以下对话中提取关键信息，生成简洁的工作笔记。\n"
            "保留：任务目标、已完成的操作、关键发现、待处理事项。\n"
            "去除：客套话、重复信息、格式细节。\n"
            "直接输出笔记内容，不要加标题或解释。\n\n"
            f"{conversation[-8000:]}"
        )

        result = await self.brain.think_with_retry(
            [{"role": "user", "content": prompt}],
            lambda raw, **kw: {"status": "success", "content": raw},
            max_retries=1,
        )
        return result if isinstance(result, str) else str(result)

    async def generate_working_notes(self, messages, focus_hint=""):
        return ""

    def notify_llm_unavailable(self):
        pass

    async def wait_for_llm_recovery(self):
        pass

    def get_prompt_template(self, name: str) -> str:
        if hasattr(self._runtime, 'prompt_registry'):
            try:
                return self._runtime.prompt_registry.get(name)
            except KeyError:
                return ""
        return ""

    def get_md_skill_prompt(self, names) -> str:
        return ""

    def is_llm_available(self) -> bool:
        if hasattr(self._runtime, 'llm_monitor') and self._runtime.llm_monitor:
            return self._runtime.llm_monitor.is_available()
        return True

    # ============================================================
    # 事件消费（与 BasicAgent._consume_events 对等）
    # ============================================================

    def emit_service_event(self, event_name: str, detail: dict = None):
        """发射 service 级事件（非 worker/MicroAgent 事件）。

        事件流入 event_queue，经 _consume_events 持久化到 DB（session_id='__service__'）
        并通过 WebSocket 广播。前端 Activity feed 消费这些事件。

        用法：self.emit_service_event("scan_started", {"kb_count": 3})
        """
        self.event_queue.put_nowait(CoreEvent(
            event_type="service",
            event_name=event_name,
            source="__service__",
            detail=detail or {},
        ))

    def _ensure_event_consumer(self):
        """确保 event_consumer task 在运行。"""
        if self._event_task and not self._event_task.done():
            return
        self._event_task = asyncio.create_task(self._consume_events())

    async def _consume_events(self):
        """持续消费自己的 event_queue，持久化到 DB + 广播。"""
        while self._running:
            try:
                event = await self.event_queue.get()
            except asyncio.CancelledError:
                break

            try:
                await self._handle_core_event(event)
            except Exception as e:
                logger.warning(f"Error handling core event: {e}")

    async def _handle_core_event(self, event: CoreEvent):
        """处理 CoreEvent — 持久化到 DB + WebSocket 广播。"""
        import re

        event_type = event.event_type
        event_name = event.event_name

        # signal / status 是 MicroAgent 内部协调事件，不持久化也不广播。
        # detail 里可能含 Signal 对象（不可 JSON 序列化）。
        if event_type in ("signal", "status"):
            return

        # 1. 持久化到 session_events 表
        event_detail = {}

        if event_type == "think" and event_name == "brain":
            detail = event.detail or {}
            raw_reply = detail.get("raw_reply", "")
            has_actions = bool(re.search(r'<action_script[^>]*>', raw_reply))

            if has_actions:
                display_text = re.sub(
                    r'<action_script[^>]*>.*?</action_script>', '',
                    raw_reply, flags=re.DOTALL
                ).strip()
                if display_text:
                    event_detail = {
                        "step_count": detail.get("step_count"),
                        "thought": display_text,
                    }
            else:
                text = raw_reply.strip()
                if text:
                    event_detail = {
                        "step_count": detail.get("step_count"),
                        "text": text,
                    }
        elif event_type == "action":
            event_detail = event.detail or {}
        else:
            event_detail = event.detail or {}

        if event_detail or event_type == "service":
            await self._log_service_event(event.source, event_type, event_name, event_detail)

        # 2. WebSocket 广播（给前端 Service Monitor）
        if self._broadcast_message_callback:
            try:
                await self._broadcast_message_callback({
                    "type": "SERVICE_EVENT",
                    "service": self.name,
                    "source": event.source,
                    "event_type": event_type,
                    "event_name": event_name,
                    "data": event_detail,
                })
            except Exception as e:
                logger.warning(f"Broadcast failed: {e}")

    async def _log_service_event(
        self, source: str, event_type: str, event_name: str, event_detail: dict
    ):
        """持久化 service 事件到 DB。"""
        try:
            db = self._runtime.post_office.email_db
            # 用 service name 作为 owner，source（micro agent name）作为 session_id
            detail_str = json.dumps(event_detail, ensure_ascii=False) if event_detail else None
            await db.insert_session_event(
                owner=self.name,
                session_id=source or self.name,
                event_type=event_type,
                event_name=event_name,
                event_detail=detail_str,
            )
        except Exception as e:
            logger.warning(f"Failed to log service event: {e}")

    # ============================================================
    # MicroAgent 执行
    # ============================================================

    def _create_micro_agent(
        self,
        name: str,
        system_prompt: str,
        available_skills: Optional[List[str]] = None,
    ) -> MicroAgent:
        """创建一个以本服务为 parent 的 MicroAgent。"""
        skills = available_skills or self._get_service_skills()
        return MicroAgent(
            parent=self,
            name=name,
            available_skills=skills,
            system_prompt=system_prompt,
        )

    async def execute(
        self,
        task: str,
        system_prompt: str = "",
        name: str = "service-task",
        available_skills: Optional[List[str]] = None,
        simple_mode: bool = True,
        **kwargs,
    ) -> Any:
        """创建 MicroAgent 执行一次性任务。

        Args:
            task: 任务描述
            system_prompt: system prompt（为空时使用任务描述）
            name: 任务名称（用于日志）
            available_skills: 技能列表（为空时使用 _get_service_skills()）
            simple_mode: 是否使用简单模式
            **kwargs: 传给 MicroAgent.execute 的额外参数

        Returns:
            MicroAgent 的执行结果
        """
        if not system_prompt:
            system_prompt = task

        micro = self._create_micro_agent(
            name=name,
            system_prompt=system_prompt,
            available_skills=available_skills,
        )

        return await micro.execute(
            run_label=name,
            task=task,
            simple_mode=simple_mode,
            **kwargs,
        )

    # ============================================================
    # 生命周期（子类 override start/stop 以加入自己的逻辑）
    # ============================================================

    def _ensure_signal_loop(self):
        """确保 signal_loop task 在运行。"""
        if self._signal_loop_task and not self._signal_loop_task.done():
            return
        self._signal_loop_task = asyncio.create_task(self._signal_loop())

    async def _stop_signal_loop(self):
        """停止 signal_loop。"""
        if self._signal_loop_task:
            self._signal_loop_task.cancel()
            try:
                await asyncio.wait_for(self._signal_loop_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._signal_loop_task = None
