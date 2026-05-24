"""
Base Skill - 所有 MicroAgent 必备的基础 Actions

包含基础 actions：
- get_current_datetime: 获取当前时间
- take_a_break: 60秒休息

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

    _skill_description = """基础技能。利用好whiteboard来记录工作要点，whiteboard是你和用户进行项目协作时的实时协作工具，也是你自己备忘、记录、规划的工具。
    whiteboard的内容要分section 组织。同一个section内，每一条内容要有一个key来标识。更新和删除，要指定section和key. key的内容是容易记忆和理解的简短文本"""

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
        short_desc="(section, key, content) 设置/删除whiteboard条目",
        description="操作白板（whiteboard）。按 section 分组，每条有 key 和 content。"
        "section+key+content 写入；section+key+空content 删除该条目；"
        "section+空key+空content 删除整个 section。白板持久化到文件，压缩后不清空。",
        param_infos={
            "section": "分组名称（必填）",
            "key": "条目标识（更新/删除时必填）",
            "content": "要记录的内容，留空则删除",
        },
    )
    async def set_whiteboard(self, section: str, key: str = "", content: str = "") -> str:
        return self._on_whiteboard_changed(section, key, content)

