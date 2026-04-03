"""
Base Skill - 所有 MicroAgent 必备的基础 Actions

包含基础 actions：
- get_current_datetime: 获取当前时间
- take_a_break: 60秒休息
- ask_user: 向用户提问并等待回答

注意：
- send_email 已移到 email skill 中
"""

import asyncio
from pathlib import Path
from typing import Any
from ...core.action import register_action


class BaseSkillMixin:
    """
    所有 MicroAgent 必备的基础 Actions

    提供通用的基础功能，如获取时间、用户交互等。
    """

    _skill_description = "基础技能"

    @register_action(
        short_desc="",
        description="检查当前日期和时间，你不知道日期和时间，如果需要日期时间信息必须调用此action",
        param_infos={},
    )
    async def get_current_datetime(self):
        """获取当前日期和时间"""
        from datetime import datetime

        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    # @register_action(
    ##    "Take a break，让身体恢复一下",
    #    param_infos={}
    # )
    # async def take_a_break(self):
    #    """扩展休息（60秒 sleep）"""
    #    await asyncio.sleep(60)
    #    return "Return from Break"

    @register_action(
        short_desc="暂停工作向用户提问并等待回答，当必须用户输入或确认时才使用",
        description="向用户提问并等待回答。当你需要用户提供信息时调用此 action。",
        param_infos={"question": "要向用户提出的问题（清晰、具体）"},
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
        raise RuntimeError(
            "ask_user should be handled by MicroAgent._execute_action, check root_agent"
        )

    

    @register_action(
        short_desc="将重要信息临时pin到本次会话记忆中，必须先unpin清空才能pin新的。如果需要合并就自己整理好新的全量内容。",
        description="将重要信息临时pin到本次会话记忆中，以便在后续步骤中持续访问。注意：必须先使用 unpin_memory 清空之前的固定记忆才能使用此功能。",
        param_infos={"content": "要固定的信息内容"},
    )
    async def pin_memory(self, content: str) -> str:
        """
        固定信息到记忆中

        将重要信息保存到 pinned_memory，以便在后续步骤中持续访问。
        如果已经有固定记忆，需要先使用 unpin_memory 清空。

        Args:
            content: 要固定的信息内容

        Returns:
            str: 操作结果

        Raises:
            RuntimeError: 如果已有固定记忆且未清空
        """
        if self.pinned_memory is not None:
            raise RuntimeError(
                "已有固定记忆存在，请先使用 unpin_memory 清空后再使用 pin_memory"
            )

        self.pinned_memory = content
        return f"Done"

    @register_action(
        short_desc="清空固定的记忆",
        description="清空 pinned_memory 中的固定记忆，释放内存空间。",
        param_infos={},
    )
    async def unpin_memory(self) -> str:
        """
        清空固定的记忆

        将 pinned_memory 设置为 None，释放内存空间。

        Returns:
            str: 操作结果
        """
    
        self.pinned_memory = None
        return f"已unpin记忆"

