"""
Task Scheduler - 定时任务调度器服务

负责定期检查并触发到期的定时任务。
"""

import asyncio
from datetime import datetime
from ..db.agent_matrix_db import AgentMatrixDB
from ..core.log_util import AutoLoggerMixin
from ..core.message import Email
from ..skills.scheduler.time_utils import format_utc_for_display


class TaskScheduler(AutoLoggerMixin):
    """全局定时任务调度器服务"""

    def __init__(self, db_path, post_office, logger):
        self.db = AgentMatrixDB(db_path)
        self.post_office = post_office
        self._running = False
        self._check_interval = 60  # 每60秒检查一次
        self._scheduler_task = None

    async def start(self):
        """启动调度器"""
        if self._running:
            return

        self._running = True
        self.echo(">>> TaskScheduler starting...")

        # 检查并处理错过的任务
        await self._check_missed_tasks()

        # 启动主循环
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        self.echo(">>> TaskScheduler started.")

    async def _scheduler_loop(self):
        """主调度循环"""
        while self._running:
            try:
                await self._check_and_trigger_tasks()
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"TaskScheduler error: {e}")
                await asyncio.sleep(self._check_interval)

    async def _check_and_trigger_tasks(self):
        """检查并触发到期的任务"""
        pending_tasks = self.db.get_pending_tasks()

        for task in pending_tasks:
            try:
                await self._send_task_reminder(task)
                self.db.mark_triggered(task['id'])
                self.logger.info(f"Triggered task: {task['task_name']} ({task['id']})")
            except Exception as e:
                self.logger.error(f"Failed to trigger task {task['id']}: {e}")
                self.db.mark_failed(task['id'], str(e))

    async def _send_task_reminder(self, task):
        """发送任务提醒邮件"""
        # 检查目标Agent是否存在
        if task['target_agent'] not in self.post_office.yellow_page():
            raise Exception(f"Target agent '{task['target_agent']}' not found")

        # 将 UTC 时间转换为本地时间显示
        trigger_time_local = format_utc_for_display(datetime.fromisoformat(task['trigger_time']))

        email = Email(
            sender="SystemDaemon",
            recipient=task['target_agent'],
            subject=f"[定时任务] {task['task_name']}",
            body=f"""这是一条定时任务提醒。

任务：{task['task_name']}
描述：{task.get('task_description', '无描述')}
计划时间：{trigger_time_local}

请开始处理此任务。""",
            metadata={
                "task_type": "scheduled_reminder",
                "scheduled_task_id": task['id'],
                "original_schedule_time": task['trigger_time']
            },
            task_id=task['id'],
            sender_session_id=task['id']
        )

        await self.post_office.dispatch(email)

    async def _check_missed_tasks(self):
        """检查系统离线期间错过的任务"""
        missed_tasks = self.db.get_pending_tasks()
        if missed_tasks:
            self.logger.warning(f"Found {len(missed_tasks)} missed tasks during downtime")

            # 通知User
            if "User" in self.post_office.yellow_page():
                for task in missed_tasks:
                    await self._send_missed_task_notification(task)

    async def _send_missed_task_notification(self, task):
        """发送错过任务的通知"""
        # 将 UTC 时间转换为本地时间显示
        trigger_time_local = format_utc_for_display(datetime.fromisoformat(task['trigger_time']))

        email = Email(
            sender="SystemDaemon",
            recipient="User",
            subject=f"[错过任务] {task['task_name']}",
            body=f"""系统在离线期间错过了一个定时任务。

任务：{task['task_name']}
目标：{task['target_agent']}
计划时间：{trigger_time_local}

该任务已被标记为完成。如需重新执行，请手动创建新任务。""",
            metadata={
                "task_type": "missed_task_notification",
                "original_task_id": task['id']
            },
            sender_session_id=task['id']
        )

        await self.post_office.dispatch(email)

    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        self.echo(">>> TaskScheduler stopped.")
