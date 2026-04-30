"""
Base Skill — 基础操作

提供 get_current_datetime action。
"""

from agentmatrix.core.action import register_action


class BaseSkillMixin:
    """基础技能"""

    _skill_description = "基础技能"

    @register_action(
        short_desc="获取当前时间",
        description="检查当前日期和时间，你不知道日期和时间，如果需要日期时间信息必须调用此action",
        param_infos={},
    )
    async def get_current_datetime(self):
        from datetime import datetime
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")
