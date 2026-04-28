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
from agentmatrix.core.action import register_action


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
        short_desc="随手记录工作过程中的关键要点（完成的步骤、遇到的约束、重要发现等），没有记下的信息稍后会被遗忘",
        description="随手记录工作过程中的关键要点（完成的步骤、遇到的约束、重要发现等）。这些笔记会在上下文压缩时辅助生成更精准的 Working Notes，压缩后自动清空。自由追加，无需清空。",
        param_infos={"content": "要记录的要点内容"},
    )
    async def add_scratchpad(self, content: str) -> str:
        """
        在草稿纸上记一条要点

        将重要信息追加到 scratchpad，压缩时作为辅助材料喂给 Working Notes 生成器。
        压缩后自动清空，无需手动管理。

        适用场景：完成关键步骤、遇到约束、发现重要信息时随手记一条。

        Args:
            content: 要记录的要点内容

        Returns:
            str: 操作结果及当前条数
        """
        self.scratchpad.append(content)
        return f"Done (scratchpad: {len(self.scratchpad)} 条)"

