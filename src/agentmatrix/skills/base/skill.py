"""
Base Skill - 所有 MicroAgent 必备的基础 Actions

包含基础 actions：
- get_current_datetime: 获取当前时间
- take_a_break: 60秒休息
- ask_user: 向用户提问并等待回答

注意：
- all_finished 不在此 skill 中，它硬编码在 MicroAgent 中
- send_email 已移到 email skill 中
"""

import asyncio
from typing import Any
from ...core.action import register_action


class BaseSkillMixin:
    """
    所有 MicroAgent 必备的基础 Actions

    提供通用的基础功能，如获取时间、用户交互等。
    """

    _skill_description = "基础技能"

    @register_action(
        "检查当前日期和时间，你不知道日期和时间，如果需要日期时间信息必须调用此action",
        param_infos={}
    )
    async def get_current_datetime(self):
        """获取当前日期和时间"""
        from datetime import datetime
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    @register_action(
        "Take a break，让身体恢复一下",
        param_infos={}
    )
    async def take_a_break(self):
        """扩展休息（60秒 sleep）"""
        await asyncio.sleep(60)
        return "Return from Break"

    @register_action(
        "向用户提问并等待回答。当你需要用户提供信息（如预算、偏好、确认等）时调用此 action。",
        param_infos={
            "question": "要向用户提出的问题（清晰、具体）"
        }
    )
    async def ask_user(self, question: str) -> str:
        """
        💬 向用户提问并等待回答（特殊 action）

        这是一个特殊的 action，会挂起当前 MicroAgent 的执行，等待用户通过 Server API 提供答案。

        注意：此方法会被 MicroAgent._execute_action 特殊处理，实际调用 root_agent.ask_user()。

        Args:
            question: 向用户提出的问题

        Returns:
            str: 用户的回答

        Raises:
            RuntimeError: 如果没有 root_agent（不应该发生）
        """
        # 这个方法不应该被直接调用
        # _execute_action 会检测到 action_name="ask_user" 并调用 root_agent.ask_user()
        # 这里只是为了注册 action，提供一个占位实现
        raise RuntimeError("ask_user should be handled by MicroAgent._execute_action, check root_agent")

