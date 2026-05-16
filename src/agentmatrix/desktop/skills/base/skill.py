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
import time
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
        short_desc="(key,content) 设置/删除whiteboard内容：提供 key+content 写入，content 为空则删除该条目",
        description="操作草稿纸（whiteboard）。提供 key 和 content 时写入或更新条目；content 为空时删除该 key。草稿纸用于随手记录工作要点，压缩时辅助生成 Working Notes，压缩后自动清空。",
        param_infos={"key": "条目标识（必填）", "content": "要记录的内容，留空则删除该条目"},
    )
    async def set_whiteboard(self, key: str, content: str = "") -> str:
        """
        设置或删除草稿纸条目

        Args:
            key: 条目标识
            content: 要记录的内容，为空则删除该 key

        Returns:
            str: 操作结果及当前条数
        """
        if not content:
            if key in self.whiteboard:
                del self.whiteboard[key]
                return f"Deleted '{key}'"
            return f"Key '{key}' not found"
        if len(self.whiteboard) >= 20 and key not in self.whiteboard:
            return "Whiteboard is full. Delete some first."
        self.whiteboard[key] = {"content": content, "ts": time.time()}
        return f"Set '{key}'"

