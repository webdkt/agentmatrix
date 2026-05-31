"""
Deep Reader Skill — 深度阅读辅助工具

提供 take_note action，供 deep_read 的子 MicroAgent 使用。
子 agent 用 take_note 记录发现，用 return_result 返回结果。

子 agent 的 MicroAgent 实例上需要设置：
  sub_agent.notes = []
"""

from agentmatrix.core.action import register_action


class Deep_readerSkillMixin:
    """深度阅读辅助工具"""

    _skill_description = "深度阅读辅助：记录笔记"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, "notes"):
            self.notes = []

    @register_action(
        short_desc="[note] 记录有价值的发现",
        description="记录有价值的发现到笔记中。找到新的事实、数据、关键信息时使用。可以多次调用。",
        param_infos={"note": "要记录的笔记内容"},
    )
    async def take_note(self, note: str) -> str:
        self.notes.append(note)
        return f"已记录笔记（共{len(self.notes)}条）"
