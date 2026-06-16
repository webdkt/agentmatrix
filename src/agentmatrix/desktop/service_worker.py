"""
ServiceWorker — 持久化 Worker：长期存活的 MicroAgent，从队列逐个处理任务。

每个 worker = 一个 MicroAgent 实例，持续运行。
任务间：session 不变（事件连续），但 messages 和 whiteboard 清空。

每个 task 自带 system_prompt（不同 KB 有不同 schema）。
worker_loop 中设置 micro.system_prompt，execute() 自动清空 messages 并重建。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

from ..core.micro_agent import MicroAgent

logger = logging.getLogger(__name__)


@dataclass
class ServiceTask:
    """Worker 接受的工作单元 — service↔worker 之间的正式契约。

    回调签名（均支持 async）：
    - on_success: async fn() -> None
    - on_error:   async fn(exception) -> None   # CancelledError 也会经此通道
    - before_think_hook: async fn(micro) -> None
    """
    label: str
    text: str                                    # 传给 MicroAgent 的任务内容
    system_prompt: str = ""
    on_success: Optional[Callable] = None        # 成功时触发
    on_error: Optional[Callable] = None          # 失败时触发（异常或被取消）
    before_think_hook: Optional[Callable] = None # 每轮 think 前的回调
    metadata: dict = field(default_factory=dict) # 可扩展；base 会用 '_fut' key 注入 future


class ServiceWorker:
    """持久 Worker — 长期存活的 MicroAgent，从队列逐个处理 ServiceTask。"""

    def __init__(self, service, name, skills):
        self.micro = MicroAgent(
            parent=service, name=name,
            available_skills=skills, system_prompt=""
        )
        self.status = "idle"          # idle | working
        self.current_task = None      # 当前任务描述
        # PriorityQueue 存 (priority, seq, task) 三元组：
        # - priority 越小越优先（service 在 submit 时指定）
        # - seq 是单调递增计数器，保证同 priority 内 FIFO，且避免 ServiceTask 被比较
        self._task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._seq: int = 0
        self._loop_task: asyncio.Task | None = None

    @property
    def name(self) -> str:
        """Worker 名 = micro 名（单一来源，避免 drift）。"""
        return self.micro.name

    async def start(self):
        """启动 worker 循环。"""
        self._loop_task = asyncio.create_task(self._worker_loop())

    async def stop(self):
        """停止 worker。"""
        if self._loop_task:
            self._loop_task.cancel()

    async def _worker_loop(self):
        """持续从队列取 ServiceTask 执行。

        契约：
        - 无论 task 成功/失败/取消，对应 future 都会被 resolve（result 或 exception）。
        - on_success 仅在成功时触发；on_error 在失败/取消时触发。
        - CancelledError 表示 worker 自身被停（stop），中断整个 loop；当前 task 的 on_error
          会先触发，future 被置为 CancelledError 异常。
        """
        while True:
            _priority, _seq, task = await self._task_queue.get()
            fut = task.metadata.get('_fut')
            self.status = "working"
            self.current_task = task.label
            await self._push_status()
            try:
                # 每个任务带自己的 system_prompt（不同 KB schema 不同）
                # execute() → messages=[] → _initialize_session() → 读 self.system_prompt
                self.micro.system_prompt = task.system_prompt

                # 接入 before_think_hook（由 Service 提供具体逻辑）
                if task.before_think_hook:
                    _hook = task.before_think_hook
                    async def _adapted(micro=self.micro, fn=_hook):
                        await fn(micro)
                    self.micro._before_think_hook = _adapted
                else:
                    self.micro._before_think_hook = None

                # 清空 ephemeral 状态（消息由 execute() 自动清空）
                service = self.micro.parent
                if hasattr(service, '_wb') and service._wb is not None:
                    service._wb.cleanup(self.micro)
                if hasattr(service, '_todo_manager') and service._todo_manager is not None:
                    if hasattr(service._todo_manager, 'cleanup'):
                        service._todo_manager.cleanup(self.micro)

                await self.micro.execute(
                    run_label=task.label,
                    task=task.text,
                    simple_mode=True,
                )

                # 成功回调（如 mark_ingested）
                if task.on_success:
                    await task.on_success()
                if fut is not None and not fut.done():
                    fut.set_result(None)

            except asyncio.CancelledError:
                # worker 被 stop —— 触发当前 task 的 on_error 和 future，然后退出 loop
                if task.on_error:
                    try:
                        await task.on_error(asyncio.CancelledError())
                    except Exception as cb_err:
                        logger.warning(f"Worker {self.name} on_error raised: {cb_err}")
                if fut is not None and not fut.done():
                    fut.set_exception(asyncio.CancelledError())
                # 仍走 finally 清理状态；re-raise 让 CancelledError 传播出 loop
                raise
            except Exception as e:
                logger.error(f"Worker {self.name} error on {task.label}: {e}")
                if task.on_error:
                    try:
                        await task.on_error(e)
                    except Exception as cb_err:
                        logger.warning(f"Worker {self.name} on_error raised: {cb_err}")
                if fut is not None and not fut.done():
                    fut.set_exception(e)
            finally:
                self.micro._before_think_hook = None
                self.status = "idle"
                self.current_task = None
                await self._push_status()

    async def _push_status(self):
        """向 WebSocket 推送 worker 状态变化。"""
        service = self.micro.parent
        cb = getattr(service, '_broadcast_message_callback', None)
        if not cb:
            return
        try:
            await cb({
                "type": "SERVICE_EVENT",
                "service": service.name,
                "event_type": "worker_status",
                "event_name": "update",
                "source": self.name,
                "data": self.get_info(),
            })
        except Exception as e:
            logger.warning(f"Worker status push failed: {e}")

    def submit(self, task: ServiceTask, priority: int = 1) -> asyncio.Future:
        """提交 ServiceTask 到优先级队列，返回一个 Future。

        priority 越小越优先（默认 1=普通；高优先级用 0 或负数）。
        同 priority 内部按 submit 顺序（FIFO）处理。

        Future 在 worker 处理完 task 后被 resolve：
        - 成功 → set_result(None)
        - 失败 → set_exception(原始异常)
        - worker 被 stop（CancelledError）→ set_exception(CancelledError())

        调用方可以 await 此 future，或用 asyncio.gather 等待一批 task。
        """
        fut = asyncio.get_event_loop().create_future()
        task.metadata['_fut'] = fut
        self._task_queue.put_nowait((priority, self._seq, task))
        self._seq += 1
        return fut

    @property
    def queue_size(self) -> int:
        return self._task_queue.qsize()

    def get_info(self) -> dict:
        return {
            "id": self.name,
            "name": self.name,
            "status": self.status,
            "current_task": self.current_task,
            "queue_size": self.queue_size,
        }
