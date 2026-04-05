"""
Memory Reader Skill — 邮件阅读辅助工具

提供 4 个 action，供 recall 的子 MicroAgent 使用：
- take_note: 记录有价值的发现（普通 action）
- provide_final_answer: 提供最终答案，退出阅读（exit action）
- read_next_batch: 跳到下一批邮件继续阅读（exit action）
- session_irrelevant: 当前 session 与问题无关（exit action）

子 agent 的 MicroAgent 实例上需要设置：
  sub_agent.notes = []
  sub_agent.answer = None
"""

from ....core.action import register_action


class Memory_readerSkillMixin:
    """邮件阅读辅助工具"""

    _skill_description = "邮件阅读辅助：记录笔记、提供答案、读下一批、跳过会话"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self, "notes"):
            self.notes = []
        if not hasattr(self, "answer"):
            self.answer = None

    @register_action(
        short_desc="[note] 记录有价值的发现",
        description="记录有价值的发现到笔记中。找到与问题相关的信息时使用。可以多次调用。",
        param_infos={"note": "要记录的笔记内容"},
    )
    async def take_note(self, note: str) -> str:
        self.notes.append(note)
        return f"已记录笔记（共{len(self.notes)}条）"

    @register_action(
        short_desc="[answer] 提供最终答案，完成阅读",
        description="""提供最终答案。当你已从邮件中找到足够的信息来回答问题时调用。
这是最终答案，调用后阅读会结束。
请确保答案包含了所有重要发现。""",
        param_infos={"content": "最终答案内容"},
    )
    async def provide_final_answer(self, content: str) -> str:
        self.answer = content
        return content

    @register_action(
        short_desc="读下一批邮件继续搜索",
        description="当前批次的邮件中没有找到完整答案，需要继续阅读下一批。",
        param_infos={},
    )
    async def read_next_batch(self) -> str:
        return "Moving to next batch"

    @register_action(
        short_desc="当前会话的邮件和问题无关，跳过",
        description="当前会话的邮件与问题没有关联，没有继续阅读的必要。调用前请至少用 take_note 记录你发现了什么。",
        param_infos={},
    )
    async def session_irrelevant(self) -> str:
        return "Skipping session"
