"""
Deep Researcher Helper Skill - 研究/写作工具 actions

给子 MicroAgent 使用的 actions：
- take_note:          记录笔记（模糊匹配章节名 + 时间戳）
- consult_with_director: 咨询导师（调 LLM）
- write_chapter_draft: 撰写章节草稿（调 LLM）
- polish_chapter:     润色章节（调 LLM）
- assemble_report:    组装最终报告

纯文件读写（读 md、写 md、检查状态）不需要注册 action，
LLM 通过 file skill 直接操作。
"""

from pathlib import Path
from datetime import datetime
from ...core.action import register_action


class Deep_researcher_helperSkillMixin:
    """深度研究辅助工具"""

    _skill_description = "深度研究辅助：记录笔记、撰写和润色报告章节、咨询导师"

    def _get_work_dir(self) -> str:
        task_id = self.root_agent.current_task_id or "default"
        return str(self.root_agent.runtime.paths.get_agent_work_files_dir(
            self.root_agent.name, task_id
        ))

    def _read_file(self, rel_path: str) -> str:
        file_path = Path(self._get_work_dir()) / rel_path
        if not file_path.exists():
            return ""
        return file_path.read_text(encoding="utf-8")

    def _write_file(self, rel_path: str, content: str) -> None:
        file_path = Path(self._get_work_dir()) / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    # ==========================================
    # 研究工具
    # ==========================================

    @register_action(
        short_desc="记录笔记",
        description="记录研究笔记到指定章节的笔记文件。chapter_name 使用章节大纲中的有效章节名。",
        param_infos={
            "content": "笔记内容",
            "chapter_name": "章节名称（使用章节大纲中定义的名称）"
        }
    )
    async def take_note(self, content: str, chapter_name: str) -> str:
        work_dir = Path(self._get_work_dir())
        notebook_dir = work_dir / "notebook"
        notebook_dir.mkdir(parents=True, exist_ok=True)

        # 模糊匹配章节名
        chapter_outline = self._read_file("research_state/chapter_outline.md") or ""
        valid_chapters = []
        for line in chapter_outline.strip().split('\n'):
            line = line.strip()
            if line.startswith('# '):
                valid_chapters.append(line[2:].strip())

        matched_chapter = self._fuzzy_match_chapter(chapter_name, valid_chapters)

        # 追加到笔记文件
        note_file = notebook_dir / f"{matched_chapter}.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        note_entry = f"\n## 笔记 - {timestamp}\n{content}\n"

        existing = note_file.read_text(encoding="utf-8") if note_file.exists() else ""
        note_file.write_text(existing + note_entry, encoding="utf-8")

        self.logger.info(f"记录笔记到 {matched_chapter}")
        return f"笔记已记录到 notebook/{matched_chapter}.md"

    def _fuzzy_match_chapter(self, name: str, valid_chapters: list) -> str:
        """模糊匹配章节名"""
        if not valid_chapters:
            return name

        name_lower = name.lower().strip()

        # 精确匹配
        for ch in valid_chapters:
            if ch.lower() == name_lower:
                return ch

        # 包含匹配
        for ch in valid_chapters:
            if name_lower in ch.lower() or ch.lower() in name_lower:
                return ch

        return name

    @register_action(
        short_desc="咨询导师",
        description="向 Director 导师请教问题。导师会根据研究目的和当前进展给出建议。",
        param_infos={"question": "要向导师请教的问题"}
    )
    async def consult_with_director(self, question: str) -> str:
        from ..deep_researcher.helpers import format_prompt
        from ..deep_researcher.prompts import ResearchPrompts

        persona_text = self._read_file("research_state/personas.md") or ""
        title = self._read_file("research_state/research_title.md") or ""
        purpose = self._read_file("research_state/research_purpose.md") or ""

        import re
        pattern = r"## Director Persona\s*\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, persona_text, re.DOTALL)
        director_persona = match.group(1).strip() if match else "一位资深研究总监"

        prompt = format_prompt(
            ResearchPrompts.DIRECTOR_REVIEW_PROMPT,
            {
                "director_persona": director_persona,
                "research_title": title,
                "research_purpose": purpose,
                "question": question
            }
        )

        result = await self.root_agent.cerebellum.think_with_retry(
            prompt,
            lambda x: {"status": "success", "content": x}
        )

        if result and isinstance(result, dict):
            return result.get("content", str(result))
        return str(result)

    # ==========================================
    # 写作工具
    # ==========================================

    @register_action(
        short_desc="撰写章节草稿",
        description="根据研究笔记撰写指定章节的草稿。会读取 notebook/ 下对应章节的笔记作为素材。",
        param_infos={"chapter_name": "章节名称（使用章节大纲中定义的名称）"}
    )
    async def write_chapter_draft(self, chapter_name: str) -> str:
        notes = self._read_file(f"notebook/{chapter_name}.md") or ""
        title = self._read_file("research_state/research_title.md") or ""
        purpose = self._read_file("research_state/research_purpose.md") or ""
        persona = self._read_file("research_state/personas.md") or ""

        prompt = f"""
{persona}

请根据收集的研究笔记撰写 [{chapter_name}] 章节的草稿。

研究主题：{title}
研究目的：{purpose}

本章相关笔记：
{notes if notes else "暂无笔记，请根据你的知识撰写"}

请撰写一份详细的章节草稿，要求：
1. 基于笔记进行扩写
2. 保持逻辑清晰、层次分明
3. 如果发现数据缺失或需要补充，用 [待查] 标记
4. 输出格式为 Markdown
"""
        result = await self.root_agent.cerebellum.think_with_retry(
            prompt,
            lambda x: {"status": "success", "content": x}
        )

        if result and isinstance(result, dict):
            draft_content = result.get("content", str(result))
        else:
            draft_content = str(result)

        self._write_file(f"drafts/{chapter_name}.md", draft_content)
        self.logger.info(f"撰写章节草稿: {chapter_name}")
        return f"章节 [{chapter_name}] 草稿已保存到 drafts/{chapter_name}.md"

    @register_action(
        short_desc="润色章节",
        description="润色指定章节的草稿。修正语法、统一格式、优化逻辑。",
        param_infos={"chapter_name": "章节名称"}
    )
    async def polish_chapter(self, chapter_name: str) -> str:
        draft = self._read_file(f"drafts/{chapter_name}.md") or ""
        if not draft:
            return f"章节 [{chapter_name}] 的草稿不存在，请先 write_chapter_draft"

        title = self._read_file("research_state/research_title.md") or ""

        prompt = f"""
请对以下研究报告草稿进行润色和优化。

研究主题：{title}
章节名称：{chapter_name}

草稿内容：
{draft}

润色要求：
1. 修正语法和表达错误
2. 统一格式和风格
3. 优化段落逻辑和过渡
4. 确保专业术语使用准确
5. 保持原有观点和数据不变

输出润色后的完整章节内容（Markdown 格式）。
"""
        result = await self.root_agent.cerebellum.think_with_retry(
            prompt,
            lambda x: {"status": "success", "content": x}
        )

        if result and isinstance(result, dict):
            polished = result.get("content", str(result))
        else:
            polished = str(result)

        self._write_file(f"drafts/{chapter_name}.md", polished)
        self.logger.info(f"润色章节: {chapter_name}")
        return f"章节 [{chapter_name}] 已润色完成"

    @register_action(
        short_desc="组装报告",
        description="将所有章节草稿组装成最终报告。所有章节完成后调用。",
        param_infos={}
    )
    async def assemble_report(self) -> str:
        title = self._read_file("research_state/research_title.md") or "研究报告"
        chapter_outline = self._read_file("research_state/chapter_outline.md") or ""

        chapters = []
        for line in chapter_outline.strip().split('\n'):
            line = line.strip()
            if line.startswith('# '):
                chapters.append(line[2:].strip())

        if not chapters:
            return "章节大纲为空，无法组装报告"

        report_parts = [f"# {title}\n"]

        for chapter_name in chapters:
            draft = self._read_file(f"drafts/{chapter_name}.md")
            if draft:
                report_parts.append(draft)
                report_parts.append("\n---\n")
            else:
                report_parts.append(f"\n## {chapter_name}\n\n[待撰写]\n\n---\n")

        final_report = '\n'.join(report_parts)

        self._write_file("final_report.md", final_report)
        self._write_file("research_state/phase.md", "done")

        self.logger.info(f"组装最终报告完成: final_report.md ({len(chapters)} 章)")
        return f"最终报告已生成: /work_files/final_report.md"
