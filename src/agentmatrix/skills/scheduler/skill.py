"""
Scheduler Skill - 定时任务管理技能

提供创建、删除、修改、查询定时任务的功能。
"""

from datetime import datetime, timezone
from ...core.action import register_action
from ...core.message import Email
import uuid


class SchedulerSkillMixin:
    """定时任务管理技能 - 访问全局TaskScheduler服务"""

    _skill_description = "创建、删除、修改和查询定时任务，具体使用参数用help查看"

    @register_action(
        short_desc="创建定时任务",
        description="创建一个定时任务。",
        param_infos={
            "task_name": "任务名称（如'周报提醒'）",
            "trigger_time": "触发时间，格式：YYYY-MM-DD HH:MM:SS（如'2026-03-15 14:30:00'）",
            "description": "自然语言描述的任务，到时间做什么事情",
            "recurrence": "可选：重复规则（'daily', 'weekly', 'monthly'）"
        }
    )
    async def create_task(
        self,
        task_name: str,
        trigger_time: str,
        description: str = "",
        recurrence: str = ""
    ) -> str:
        """创建定时任务（目标为当前Agent自己）"""
        from .time_utils import parse_local_time

        # 目标 Agent 为自己
        target_agent = self.root_agent.name

        # 解析时间（本地时间 → UTC）
        try:
            utc_time = parse_local_time(trigger_time)
        except ValueError as e:
            return f"❌ 时间格式错误: {e}。请使用格式：YYYY-MM-DD HH:MM:SS"

        # 创建任务记录
        task_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        task = {
            'id': task_id,
            'task_name': task_name,
            'target_agent': target_agent,
            'trigger_time': utc_time.isoformat(),
            'recurrence_rule': recurrence or None,
            'task_description': description,
            'status': 'active',
            'created_at': now,
            'updated_at': now
        }

        # 保存到数据库（通过全局scheduler）
        await self.root_agent.runtime.task_scheduler.db.create_task(task)

        return f"✅ 已创建定时任务 '{task_name}'，ID: {task_id}，将在 {trigger_time} 提醒我"

    @register_action(
        short_desc="根据task_id删除定时任务",
        description="删除指定的定时任务",
        param_infos={
            "task_id": "任务ID（使用list_tasks查看）"
        }
    )
    async def delete_task(self, task_id: str) -> str:
        """删除定时任务"""
        await self.root_agent.runtime.task_scheduler.db.delete_task(task_id)
        return f"✅ 已删除任务 {task_id}"

    @register_action(
        short_desc="修改定时任务",
        description="修改已存在的定时任务",
        param_infos={
            "task_id": "任务ID",
            "trigger_time": "新的触发时间（可选）",
            "task_name": "新的任务名称（可选）",
            "description": "新的描述（可选）",
            "recurrence": "新的重复规则（可选）"
        }
    )
    async def modify_task(
        self,
        task_id: str,
        trigger_time: str = None,
        task_name: str = None,
        description: str = None,
        recurrence: str = None
    ) -> str:
        """修改定时任务"""
        from .time_utils import parse_local_time

        updates = {}

        if task_name:
            updates['task_name'] = task_name
        if description:
            updates['task_description'] = description
        if recurrence:
            updates['recurrence_rule'] = recurrence
        if trigger_time:
            try:
                utc_time = parse_local_time(trigger_time)
                updates['trigger_time'] = utc_time.isoformat()
            except ValueError as e:
                return f"❌ 时间格式错误: {e}"

        if not updates:
            return "❌ 没有提供任何更新"

        await self.root_agent.runtime.task_scheduler.db.update_task(task_id, updates)
        return f"✅ 已更新任务 {task_id}"

    @register_action(
        short_desc="列出定时任务",
        description="列出所有定时任务",
        param_infos={
            "status_filter": "可选：按状态过滤（'active', 'paused', 'completed', 'failed'）"
        }
    )
    async def list_tasks(
        self,
        status_filter: str = ""
    ) -> str:
        """列出当前Agent的定时任务"""
        from .time_utils import format_utc_for_display

        # 只查询当前Agent的任务
        tasks = await self.root_agent.runtime.task_scheduler.db.list_tasks(
            status=status_filter or None,
            agent=self.root_agent.name
        )

        if not tasks:
            return "没有找到任务"

        result = f"找到 {len(tasks)} 个任务：\n\n"
        for task in tasks:
            trigger_time = format_utc_for_display(datetime.fromisoformat(task['trigger_time']))
            result += f"** {task['task_name']} (ID: {task['id']}) **\n"
            result += f"   触发时间: {trigger_time}\n"
            result += f"   状态: {task['status']}\n"
            if task.get('recurrence_rule'):
                result += f"   重复: {task['recurrence_rule']}\n"
            if task.get('task_description'):
                result += f"   描述: {task['task_description']}\n"
            result += "\n"

        return result

    @register_action(
        short_desc="启用/暂停任务[task_id, action=enable|pause]",
        description="启用或暂停指定的定时任务",
        param_infos={
            "task_id": "任务ID",
            "action": "'enable' 启用 或 'pause' 暂停"
        }
    )
    async def set_task_status(self, task_id: str, action: str) -> str:
        """启用或暂停任务"""
        if action not in ['enable', 'pause']:
            return "❌ 无效操作，请使用 'enable' 或 'pause'"

        status = 'active' if action == 'enable' else 'paused'
        await self.root_agent.runtime.task_scheduler.db.update_task(task_id, {'status': status})

        return f"✅ 任务 {task_id} 已{status}"
