"""
Deep Researcher Skill - 深度研究顶层 actions

扁平化架构：顶层 agent 直接拥有所有工具，通过 set_mindset 动态切换思维模式。

Actions:
- set_mindset:             设置当前思维模式 (planning/research/writing)
- take_note:               记录笔记到 sqlite 数据库（自动去重检查）
- search_note_w_keyword:   关键词搜索笔记
- search_note_w_natural_lang: 自然语言搜索笔记
- verify_notes_format:        整理和验证笔记及草稿
- finalize_report:         组装最终报告
"""

import re
from pathlib import Path
from ...core.action import register_action
from .helpers import (
    duplicate_check_parser,
    nl_search_answer_parser,
    format_prompt,
    init_note_db,
    normalize_tags,
    insert_note,
    fix_all_note_tags,
    search_notes_by_keyword,
    search_notes_by_keywords,
    find_similar_notes,
    get_notes_by_chapter,
    get_all_notes,
)
from .prompts import ResearchPrompts




class Deep_researcherSkillMixin:
    """Deep Researcher 深度研究协调者"""

    _skill_description = "深度研究技能，对指定主题进行深度研究并生成完整报告。先规划，再研究，最后写作。"
    _skill_dependencies = []

    # ==========================================
    # 工具方法
    # ==========================================

    def _get_work_dir(self) -> str:
        task_id = self.root_agent.current_task_id or "default"
        return str(
            self.root_agent.runtime.paths.get_agent_work_files_dir(
                self.root_agent.name, task_id
            )
        )

    def _get_note_db_path(self) -> str:
        return str(Path(self._get_work_dir()) / "note.db")

    # ==========================================
    # Actions
    # ==========================================

    @register_action(
        short_desc="设置当前思维模式(planning/research/writing)",
        description=(
            "切换工作阶段的思维模式。不同模式有不同的工作流程和思考方式。"
            "规划阶段聚焦于建立研究蓝图和计划；"
            "研究阶段聚焦于搜索资料和记笔记；"
            "写作阶段聚焦于撰写和组装报告。"
        ),
        param_infos={"mindset": "思维模式，可选值: planning, research, writing"},
    )
    async def set_mindset(self, mindset: str) -> str:
        valid = {"planning", "research", "writing"}
        mindset_lower = mindset.lower().strip()
        if mindset_lower not in valid:
            return f"无效的 mindset: '{mindset}'。可选值: {', '.join(sorted(valid))}"

        # 获取新 mindset 文本
        mindset_text = getattr(ResearchPrompts, f"{mindset_lower.upper()}_MINDSET")

        # 替换 persona 中的 [Mindset]...[End of Mindset] 块
        pattern = r"\[Mindset\].*?\[End of Mindset\]"
        replacement = f"[Mindset]\n{mindset_text}\n[End of Mindset]"
        self.persona = re.sub(pattern, replacement, self.persona, flags=re.DOTALL)

        # 更新 system prompt（如果 messages 已初始化且第一条是 system）
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = self._build_system_prompt()

        # 更新 phase.md（通过 file.write action 或直接写）
        work_dir = Path(self._get_work_dir())
        state_dir = work_dir / "research_state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "phase.md").write_text(mindset_lower, encoding="utf-8")

        return f"思维模式已切换到: {mindset_lower}"

    @register_action(
        short_desc="记录研究笔记到数据库(自动去重检查)，提供笔记文本，所属chapter_name(可选）， 逗号分隔的tags(可选）",
        description=(
            "记录研究笔记到 sqlite 数据库 note.db。"
            "自动标准化 tags（小写、去特殊字符、排序、最多3个）。"
            "自动检查是否有内容重复的已有笔记。"
        ),
        param_infos={
            "note_text": "笔记内容",
            "chapter_name": "用途章节（可选，留空表示未确定归属）",
            "tags": "逗号分隔的关键词，最多3个（如: ai,transformer,attention）",
        },
    )
    async def take_note(self, note_text: str, chapter_name: str = "", tags: str = "") -> str:
        db_path = self._get_note_db_path()

        # 标准化 tags
        original_tags = tags
        normalized_tags = normalize_tags(tags)
        tag_warning = ""
        if original_tags:
            # 比较时去掉逗号包裹，只看内容差异
            display_norm = normalized_tags.strip(",") if normalized_tags else ""
            original_clean = original_tags.strip().lower().replace(" ", "-")
            if display_norm != original_clean:
                tag_warning = f" (tags 已标准化: '{original_tags}' → '{display_norm}')"

        # 确保数据库存在
        init_note_db(db_path)

        # 重复检查：分 batch 判断
        if normalized_tags:
            similar = find_similar_notes(db_path, normalized_tags)
            if similar:
                batch_size = 20
                duplicate_found = False
                for i in range(0, len(similar), batch_size):
                    batch = similar[i : i + batch_size]
                    candidate_text = "\n".join(
                        f"[ID={r[0]}] tags=[{r[3].strip(',') if r[3] else ''}]\n{r[1]}"
                        for r in batch
                    )
                    prompt = format_prompt(
                        ResearchPrompts.DUPLICATE_CHECK_PROMPT,
                        new_note_text=note_text,
                        candidate_notes=candidate_text,
                    )
                    try:
                        result = await self.root_agent.cerebellum.backend.think_with_retry(
                            prompt, duplicate_check_parser
                        )
                        if isinstance(result, dict) and result.get("duplicate"):
                            dup_id = result.get("duplicate_id", "?")
                            reason = result.get("reason", "语义重复")
                            # 找到原文
                            original_text = ""
                            for r in batch:
                                if r[0] == dup_id:
                                    original_text = r[1]
                                    break
                            return (
                                f"发现 ID={dup_id} 的笔记与要增加的笔记语义重复。\n"
                                f"原因: {reason}\n"
                                f"原文: {original_text}\n"
                                f"如果要更新或继续插入请自行直接操作数据库。"
                            )
                    except Exception as e:
                        self.logger.exception(e)
                        continue  # 该 batch 判断失败，继续下一个 batch

        # 无重复，正常插入
        note_id = insert_note(db_path, note_text, chapter_name, normalized_tags)

        result_msg = f"笔记已记录 (ID={note_id})"
        if chapter_name:
            result_msg += f", chapter={chapter_name}"
        if normalized_tags:
            result_msg += f", tags=[{normalized_tags}]"
        result_msg += tag_warning
        return result_msg

    @register_action(
        short_desc="关键词搜索笔记(全文搜索note_text和tags)",
        description=(
            "对笔记进行关键词全文搜索。搜索 note_text 和 tags 字段，"
            "tags 需完全匹配某一个 tag。"
        ),
        param_infos={"search_query": "搜索关键词"},
    )
    async def search_note_w_keyword(self, search_query: str) -> str:
        db_path = self._get_note_db_path()
        results = search_notes_by_keyword(db_path, search_query)

        if not results:
            return f"未找到匹配 '{search_query}' 的笔记"

        def format_note(r):
            note_id, text, chapter, tags = r
            chapter_str = f" | chapter={chapter}" if chapter else ""
            tags_str = f" | tags=[{tags.strip(',') if tags else ''}]"
            return f"[ID={note_id}]{chapter_str}{tags_str}\n  {text}\n"

        total = len(results)
        if total <= 10:
            lines = [f"搜索 '{search_query}' 找到 {total} 条结果：\n"]
            lines.extend(format_note(r) for r in results)
        else:
            lines = [f"搜索 '{search_query}' 找到 {total} 条结果，列出前10条：\n"]
            lines.extend(format_note(r) for r in results[:10])
            lines.append(f"共找到 {total} 条，如需要进一步列出更多请直接访问数据库。")

        return "\n".join(lines)

    @register_action(
        short_desc="[问题] 通过搜索笔记内容来回答自然语言问题",
        description=(
            "用自然语言问题搜索笔记。自动拆解问题为多个搜索组合，"
            "逐步搜索并用 LLM 判断结果是否能回答问题。"
        ),
        param_infos={"question": "要搜索的自然语言问题"},
    )
    async def search_note_w_natural_lang(self, question: str) -> str:
        db_path = self._get_note_db_path()

        # Step 1: 用 LLM 生成搜索组合
        query_prompt = format_prompt(
            ResearchPrompts.NL_SEARCH_QUERY_PROMPT, question=question
        )
        query_result = await self.root_agent.cerebellum.backend.think_with_retry(
            query_prompt, lambda x: {"status": "success", "content": x}
        )

        if query_result and isinstance(query_result, dict):
            query_content = query_result.get("content", "")
        else:
            query_content = str(query_result)

        # 解析 [QUERIES] 块，支持引号包裹的 keyword
        queries = []
        if "[QUERIES]" in query_content:
            queries_section = query_content[query_content.index("[QUERIES]"):]
            for line in queries_section.split("\n"):
                line = line.strip().lstrip("-").strip()
                if line and "[" not in line and not line.startswith("[QUERIES"):
                    # 提取关键词：按逗号分，支持 "quoted phrase"
                    parts = [p.strip() for p in line.split(",")]
                    parsed = []
                    for p in parts:
                        if p.startswith('"') and p.endswith('"'):
                            parsed.append(p[1:-1])
                        elif p:
                            parsed.append(p)
                    if parsed:
                        queries.append(parsed)

        if not queries:
            queries = [[question]]

        # Step 2: 逐组合搜索，用 LLM JSON 判断，累积有用 notes
        useful_note_ids = set()
        useful_notes_text = {}  # id -> preview text

        for keywords in queries:
            # SQL AND 搜索：所有 keywords 都必须命中
            all_results = search_notes_by_keywords(db_path, keywords)
            if not all_results:
                continue

            # 分 batch 给 LLM 判断
            batch_size = 20
            for i in range(0, len(all_results), batch_size):
                batch = all_results[i : i + batch_size]

                # 格式化当前批次（给 ID + 全文）
                current_notes_text = "\n\n".join(
                    f"[ID={r[0]}] {r[1]}" for r in batch
                )

                # 格式化已有有用 notes（只给文本，不给ID）
                existing_section = ""
                if useful_notes_text:
                    existing_section = "\n".join(
                        f"- {text}" for text in useful_notes_text.values()
                    )

                # 用 LLM JSON 判断
                answer_prompt = format_prompt(
                    ResearchPrompts.NL_SEARCH_ANSWER_PROMPT,
                    question=question,
                    existing_answer_section=existing_section,
                    current_notes=current_notes_text,
                )
                try:
                    answer_result = await self.brain.think_with_retry(
                        answer_prompt, nl_search_answer_parser
                    )
                except Exception:
                    continue

                if not isinstance(answer_result, dict):
                    continue

                if answer_result.get("answered"):
                    return f"找到答案：\n{answer_result['answer']}"

                # 累积有用 notes
                for nid in answer_result.get("useful_ids", []):
                    if nid not in useful_note_ids:
                        useful_note_ids.add(nid)
                        for r in batch:
                            if r[0] == nid:
                                useful_notes_text[nid] = r[1][:150]
                                break

                # 超过 20 条有用 notes 还没回答，放弃
                if len(useful_note_ids) >= 20:
                    break

            if len(useful_note_ids) >= 20:
                break

        # 所有搜索组合都未能回答
        if useful_note_ids:
            useful_summary = "\n".join(
                f"  [ID={nid}] {useful_notes_text.get(nid, '')}..."
                for nid in sorted(useful_note_ids)[:10]
            )
            return f"现有笔记无法完全回答该问题。以下是相关笔记：\n{useful_summary}"
        else:
            return "现有笔记中未找到与该问题相关的内容"

    @register_action(
        short_desc="验证研究工作区结构完整性",
        description=(
            "检查 research_state/ 目录和 drafts/ 目录的结构完整性。"
            "验证 research_state 各文件是否存在，"
            "drafts 一级目录是否与 chapter_outline 匹配，"
            "所有子目录和文件是否以数字编号开头。"
        ),
        param_infos={},
    )
    async def verify_structure(self) -> str:
        work_dir = Path(self._get_work_dir())
        state_dir = work_dir / "research_state"
        drafts_dir = work_dir / "drafts"

        lines = []

        # 1. 检查 research_state 文件
        expected_state_files = [
            "phase.md", "research_title.md", "blueprint.md",
            "plan.md", "chapter_outline.md", "writing_schema.md",
        ]
        lines.append("## research_state/")
        for f in expected_state_files:
            exists = (state_dir / f).exists()
            lines.append(f"  {'✓' if exists else '✗'} {f}")

        # 2. 读取 chapter_outline
        outline_file = state_dir / "chapter_outline.md"
        chapters = []
        if outline_file.exists():
            for line in outline_file.read_text(encoding="utf-8").strip().split("\n"):
                line = line.strip()
                if line.startswith("# "):
                    chapters.append(line[2:].strip())

        # 3. 检查 drafts 目录
        lines.append("\n## drafts/")
        if not drafts_dir.exists():
            lines.append("  drafts/ 目录不存在")
        elif not chapters:
            lines.append("  chapter_outline.md 不存在或无章节定义，无法校验匹配")
        else:
            draft_dirs = sorted(d.name for d in drafts_dir.iterdir() if d.is_dir())
            # 去掉数字前缀（如 "1-引言" → "引言"）再比较
            def strip_number_prefix(name):
                m = re.match(r"^\d+[-_](.+)$", name)
                return m.group(1) if m else name

            draft_chapters = {strip_number_prefix(d): d for d in draft_dirs}
            chapter_set = set(chapters)
            draft_name_set = set(draft_chapters.keys())

            missing = chapter_set - draft_name_set
            extra = draft_name_set - chapter_set

            if missing:
                for m in sorted(missing):
                    lines.append(f"  ✗ 缺少章节目录: {m}")
            if extra:
                for e in sorted(extra):
                    orig = draft_chapters[e]
                    lines.append(f"  ✗ 多余目录（不在大纲中）: {orig}")
            if not missing and not extra:
                lines.append(f"  ✓ 一级目录与 chapter_outline 完全匹配 ({len(chapters)} 章)")

            # 4. 递归检查所有子目录和文件是否以数字编号开头
            naming_issues = []
            for d in sorted(drafts_dir.rglob("*")):
                rel = d.relative_to(drafts_dir)
                name = d.name
                if name and not name[0].isdigit():
                    kind = "目录" if d.is_dir() else "文件"
                    naming_issues.append(f"  ✗ {kind} '{rel}' 未以数字编号开头")

            if naming_issues:
                lines.append("\n## 命名规范问题")
                lines.extend(naming_issues)
            else:
                lines.append("  ✓ 所有子目录和文件均以数字编号开头")

        return "\n".join(lines)

    @register_action(
        short_desc="整理和验证笔记数据库（统计、查错、自动修复tags）",
        description=(
            "对笔记数据库进行统计汇总和格式检查。"
            "输出每章笔记数量统计，发现错误章节名，自动修复 tags 格式。"
        ),
        param_infos={},
    )
    async def verify_notes_format(self) -> str:
        work_dir = Path(self._get_work_dir())
        db_path = self._get_note_db_path()

        # 1. 读取有效章节名
        outline_file = work_dir / "research_state" / "chapter_outline.md"
        valid_chapters = set()
        if outline_file.exists():
            for line in outline_file.read_text(encoding="utf-8").strip().split("\n"):
                line = line.strip()
                if line.startswith("# "):
                    valid_chapters.add(line[2:].strip())

        # 2. 自动修复 tags（静默执行）
        tags_fixed = fix_all_note_tags(db_path)

        # 3. 汇总统计
        all_notes = get_all_notes(db_path)
        total = len(all_notes)

        chapter_counts = {}   # chapter_name -> count
        invalid_chapters = {} # invalid chapter_name -> count
        unassigned = 0

        for note in all_notes:
            _, _, chapter, _ = note
            if not chapter:
                unassigned += 1
            elif chapter in valid_chapters:
                chapter_counts[chapter] = chapter_counts.get(chapter, 0) + 1
            else:
                invalid_chapters[chapter] = invalid_chapters.get(chapter, 0) + 1

        # 4. 组装输出
        parts = []

        # --- 统计汇总 ---
        summary_lines = [f"## 笔记统计 (共 {total} 条)"]
        for ch in sorted(valid_chapters):
            count = chapter_counts.get(ch, 0)
            summary_lines.append(f"  - {ch}: {count} 条")
        summary_lines.append(f"  - 未分配章节: {unassigned} 条")
        no_notes = [ch for ch in sorted(valid_chapters) if chapter_counts.get(ch, 0) == 0]
        if no_notes:
            summary_lines.append(f"  ⚠ 以下 {len(no_notes)} 章没有笔记: {', '.join(no_notes)}")
        parts.append("\n".join(summary_lines))

        # --- 问题发现 ---
        issues = []
        if invalid_chapters:
            lines = [f"## 错误章节名 ({sum(invalid_chapters.values())} 条)"]
            for ch, count in sorted(invalid_chapters.items()):
                lines.append(f"  - '{ch}': {count} 条")
            issues.append("\n".join(lines))
        if not issues:
            parts.append("## 问题检查: 通过")
        else:
            parts.append("\n\n".join(issues))

        return "\n\n".join(parts)

    

    @register_action(
        short_desc="组装最终报告(完成所有章节后调用)",
        description=(
            "将所有章节草稿组装成完整的研究报告。"
        ),
        param_infos={},
    )
    async def finalize_report(self) -> str:
        work_dir = Path(self._get_work_dir())

        # 读取 title
        title_file = work_dir / "research_state" / "research_title.md"
        title = title_file.read_text(encoding="utf-8").strip() if title_file.exists() else "研究报告"

        # 读取 chapter outline（用于排序）
        outline_text = ""
        outline_file = work_dir / "research_state" / "chapter_outline.md"
        if outline_file.exists():
            outline_text = outline_file.read_text(encoding="utf-8")

        # 遍历 drafts 下的一级子目录和 md 文件，作为实际章节
        drafts_dir = work_dir / "drafts"
        if not drafts_dir.exists():
            return "drafts 目录不存在，无法组装报告"

        # 收集所有章节项：(排序行号, 名称, 路径)
        chapters = []
        for item in drafts_dir.iterdir():
            if item.name.startswith("."):
                continue
            if item.is_dir():
                # 跳过递归最深层也没有 .md 文件的空目录
                if not any(item.rglob("*.md")):
                    continue
                # 在 chapter_outline 中搜索该目录名，取行号作为排序依据
                order = self._find_chapter_order(outline_text, item.name)
                chapters.append((order, item.name, "dir", item))
            elif item.is_file() and item.suffix == ".md":
                order = self._find_chapter_order(outline_text, item.stem)
                chapters.append((order, item.stem, "file", item))

        if not chapters:
            return "drafts 目录为空，无法组装报告"

        # 按行号排序（未匹配到的排到最后）
        chapters.sort(key=lambda x: (x[0] == 0, x[0]))

        # 组装报告
        report_parts = [f"# {title}\n"]

        for order, name, kind, path in chapters:
            if kind == "file":
                report_parts.append(path.read_text(encoding="utf-8"))
            elif kind == "dir":
                content = self._merge_directory(path, level=2)
                report_parts.append(content)
            report_parts.append("\n---\n")

        final_report = "\n".join(report_parts)
        (work_dir / f"{title}.md").write_text(final_report, encoding="utf-8")

        # 更新 phase
        (work_dir / "research_state" / "phase.md").write_text("done", encoding="utf-8")

        self.logger.info(f"组装最终报告完成: {title}.md ({len(chapters)} 章)")
        return f"最终报告已生成: {title}.md ({len(chapters)} 章)"

    def _find_chapter_order(self, outline_text: str, chapter_name: str) -> int:
        """在 chapter_outline 中搜索章节名，返回首次出现的行号（1-based），未找到返回0"""
        for i, line in enumerate(outline_text.split("\n"), 1):
            if chapter_name in line:
                return i
        return 0

    def _merge_directory(self, dir_path: Path, level: int = 2) -> str:
        """递归合并目录中的 .md 文件和子目录，按编号顺序排列"""
        parts = []
        prefix = "#" * level

        def _sort_key(p: Path):
            m = re.match(r"(\d+)", p.name)
            return (int(m.group(1)) if m else 0, p.name)

        items = sorted(dir_path.iterdir(), key=_sort_key)
        for item in items:
            if item.is_file() and item.suffix == ".md":
                parts.append(item.read_text(encoding="utf-8"))
            elif item.is_dir():
                parts.append(f"\n{prefix} {item.name}\n")
                parts.append(self._merge_directory(item, level + 1))

        return "\n\n".join(parts)
