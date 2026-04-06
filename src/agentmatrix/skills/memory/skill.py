"""
Memory Skill - 核心实现

提供基于邮件历史的记忆搜索：
- recall: 通过关键词搜索邮件历史，由子 agent 阅读邮件找答案
"""

import asyncio
from ...core.action import register_action


class MemorySkillMixin:
    """
    Memory Skill Mixin

    提供基于邮件历史的回忆搜索功能。
    """

    _skill_description = "用自然语言搜索邮件历史，找回Layer 3记忆信息"

    @register_action(
        short_desc="(question)，搜索历史对话，描述要找什么",
        description="搜索历史对话回忆信息。当你需要回忆之前讨论过的事情、决策、项目细节等时调用此 action。",
        param_infos={
            "question": "要回忆的问题（如'上次讨论的预算是多少？'）",
        },
    )
    async def search_conversations(self, question: str) -> str:
        return await self.search_emails(question)

    @register_action(
        short_desc="(question)，搜索邮件，描述要找什么",
        description="搜索邮件历史回忆信息。当你需要回忆之前讨论过的事情、决策、项目细节等时调用此 action。",
        param_infos={
            "question": "要回忆的问题（如'上次讨论的预算是多少？'）",
        },
    )
    async def search_emails(self, question: str) -> str:
        """
        搜索邮件历史回忆信息

        流程：
        1. LLM 提取搜索关键词分组（OR-of-AND）
        2. 并行搜索每组关键词
        3. 第一个找到答案的返回，取消其他
        """
        from .parser_utils import keyword_groups_parser

        # 1. LLM 提取关键词分组
        keyword_prompt = f"""分析以下问题，提取用于搜索邮件的关键词分组。

问题：{question}

你最多可以提供 3 组关键词（按优先级排序），每组最多 3 个关键词。
- 组内关键词是 AND 关系（所有词必须同时匹配）
- 组与组之间是 OR 关系（按顺序尝试，找到就停）

例如问题"A项目的预算讨论"：
- 第1组（最精确）: ["A项目", "预算"]
- 第2组（宽泛）: ["A项目"]
- 第3组（同义词）: ["A", "预算方案"]

例如问题"张三的联系方式"：
- 第1组: ["张三", "联系方式"]
- 第2组: ["张三", "电话"]

关键词应该是具体的名词、术语、项目名等，避免"什么"、"如何"等泛化词。

输出 JSON 格式：
```json
{{"groups": [["关键词1a", "关键词1b"], ["关键词2"], ...]}}
```
"""

        try:
            kw_result = await self.root_agent.cerebellum.backend.think_with_retry(
                initial_messages=keyword_prompt,
                parser=keyword_groups_parser,
                max_retries=2,
            )
            keyword_groups = kw_result
        except Exception as e:
            self.logger.warning(f"关键词提取失败: {e}")
            return "无法提取搜索关键词"

        if not keyword_groups:
            return "无法提取搜索关键词"

        groups_desc = " | ".join(
            " AND ".join(g) for g in keyword_groups
        )
        self.logger.info(f"Recall keyword groups: {groups_desc}")

        # 2. 并行搜索每组
        tasks = [
            asyncio.create_task(
                self._search_one_group(question, gi, keywords)
            )
            for gi, keywords in enumerate(keyword_groups)
        ]

        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                try:
                    result = await task
                except asyncio.CancelledError:
                    continue
                except Exception as e:
                    self.logger.error(f"Recall group task failed: {e}")
                    continue
                if result:
                    for p in pending:
                        p.cancel()
                    return result

        return "记忆里没有找到相关信息"

    async def _search_one_group(
        self, question: str, group_index: int, keywords: list
    ) -> str | None:
        """
        搜索一组关键词，找到答案返回 str，否则返回 None
        """
        from ...agents.micro_agent import MicroAgent

        self.logger.info(
            f"Group {group_index}: searching AND({', '.join(keywords)})"
        )

        post_office = self.root_agent.post_office
        search_results = post_office.email_db.search_emails_by_keyword_groups(
            self.root_agent.name, keywords
        )

        if not search_results:
            self.logger.info(f"Group {group_index}: no results")
            return None

        top_sessions = search_results[:5]

        self.logger.info(
            f"Group {group_index}: found {len(search_results)} sessions, "
            f"reading top {len(top_sessions)}"
        )

        for session_info in top_sessions:
            session_id = session_info["session_id"]
            self.logger.info(
                f"Group {group_index}: reading session {session_id} "
                f"(hits={session_info['hit_count']}, "
                f"subject={session_info['first_subject'][:50]})"
            )

            emails = post_office.get_emails_by_session(
                session_id, self.root_agent.name
            )

            if not emails:
                continue

            batch_size = 20
            total_batches = (len(emails) + batch_size - 1) // batch_size
            session_notes = []

            for i in range(total_batches):
                start = i * batch_size
                end = min(start + batch_size, len(emails))
                batch_emails = emails[start:end]
                batch_text = self._format_emails_for_reading(batch_emails)

                task = f"""你的任务是阅读以下邮件，找到要回答问题的答案。

[待回答问题]
{question}

[搜索关键词]
{', '.join(keywords)}

[已记录的笔记]
{chr(10).join(session_notes) if session_notes else '无'}

[邮件内容（第 {i+1}/{total_batches} 批）]
{batch_text}

重要：
- 对于值得记录的信息，用 take_note 积累发现
- provide_final_answer 是最终答案，调用后阅读结束
- 读完本批如果不能提供最终答案，思考决定选择：
    - 如果后面还值得探索，用 read_next_batch 继续
    - 如果当前 session 与问题完全无关，用 session_irrelevant 跳过
"""

                sub_agent = MicroAgent(
                    parent=self,
                    name=f"{self.name}_recall_g{group_index}_{session_id[:8]}_{i}",
                    available_skills=["memory.memory_reader", "file"],
                )
                sub_agent.notes = []
                sub_agent.answer = None

                try:
                    await sub_agent.execute(
                        run_label=f"recall_g{group_index}_{i}",
                        task=task,
                        persona=getattr(self, "persona", None),
                        simple_mode=True,
                        exit_actions=[
                            "provide_final_answer",
                            "read_next_batch",
                            "session_irrelevant",
                        ],
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.error(f"Recall sub-agent failed: {e}")
                    continue

                sub_notes = getattr(sub_agent, "notes", [])
                session_notes.extend(sub_notes)

                action = getattr(sub_agent, "return_action_name", None)
                answer = getattr(sub_agent, "answer", None)

                self.logger.info(
                    f"Group {group_index}: session batch {i} exit action: {action}"
                )

                if action == "provide_final_answer":
                    return answer or "\n".join(session_notes)

                elif action == "session_irrelevant":
                    break

                # read_next_batch: continue

        self.logger.info(f"Group {group_index}: no answer found")
        return None

    def _format_emails_for_reading(self, emails) -> str:
        """格式化邮件列表为可读文本"""
        lines = []
        agent_name = self.root_agent.name

        for email in emails:
            ts = email.timestamp.strftime("%Y-%m-%d %H:%M") if hasattr(email.timestamp, "strftime") else str(email.timestamp)

            if email.sender == agent_name:
                lines.append(f"[{ts}] → {email.recipient}: {email.body}")
            else:
                lines.append(f"[{ts}] {email.sender}: {email.body}")

        return "\n\n".join(lines)
