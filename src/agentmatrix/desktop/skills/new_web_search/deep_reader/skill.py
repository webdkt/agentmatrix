"""
Deep Reader Skill — 深度阅读辅助工具

提供 4 个 action，供 deep_read 的子 MicroAgent 使用：
- take_note: 记录有价值的发现（普通 action）
- provide_final_summary: 提供最终总结，退出阅读（exit action）
- goto_next_section: 跳到下一个章节（exit action）
- no_need_to_read_further: 没有继续阅读的必要（exit action）

子 agent 的 MicroAgent 实例上需要设置：
  sub_agent.notes = []
  sub_agent.answer = None
"""

from agentmatrix.core.action import register_action


class Deep_readerSkillMixin:
    """深度阅读辅助工具"""

    _skill_description = "深度阅读辅助：记录笔记、提供总结、跳转章节、终止阅读"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 这些属性由父 deep_read 方法在 sub_agent 上初始化
        # 如果不存在就初始化为空
        if not hasattr(self, "notes"):
            self.notes = []
        if not hasattr(self, "answer"):
            self.answer = None

    @register_action(
        short_desc="[note] 记录有价值的发现",
        description="记录有价值的发现到笔记中。找到新的事实、数据、关键信息时使用。可以多次调用。",
        param_infos={"note": "要记录的笔记内容"},
    )
    async def take_note(self, note: str) -> str:
        self.notes.append(note)
        return f"已记录笔记（共{len(self.notes)}条）"

    @register_action(
        short_desc="[content] 提供最终总结，完成阅读",
        description="""提供最终总结。当你已收集到足够的信息来回答目标问题时调用。
这是最终答案，调用后阅读会结束。
请确保总结包含了所有重要发现。""",
        param_infos={"content": "最终总结内容"},
    )
    async def provide_final_summary(self, content: str) -> str:
        self.answer = content
        return content

    @register_action(
        short_desc="跳到下一个章节继续阅读",
        description="当前章节没有有价值的内容，跳到下一个章节继续。",
        param_infos={},
    )
    async def goto_next_section(self) -> str:
        return "Moving to next section"

    @register_action(
        short_desc="文章剩余内容和要求的目的没有太大关系，没有继续阅读的必要",
        description="整篇文章没有继续阅读的价值。调用前请至少用 take_note 记录你发现了什么（即使很少）。",
        param_infos={},
    )
    async def no_need_to_read_further(self) -> str:
        return "Stopping"
