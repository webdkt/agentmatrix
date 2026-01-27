"""
Deep Researcher Skill - 深度研究技能

主流程：
1. 目标理解与人设生成
2. 研究计划制定 (Planning Stage)
3. 研究循环 (Research Loop)
4. 报告撰写 (Writing Loop)

使用MicroAgent递归调用来组织各个阶段。
"""

import os
from typing import Dict, List, Optional, Any
from pathlib import Path
from ..core.action import register_action
from .deep_researcher_helper import (
    ResearchContext,
    Notebook,
    format_prompt,
    DeepResearcherPrompts,
    persona_parser,
    research_plan_parser,
    director_approval_parser
)
from .utils import sanitize_filename


class DeepResearcherMixin:
    """Deep Researcher Skill Mixin"""

    # ==========================================
    # 主入口
    # ==========================================

    @register_action(
        description="对指定主题进行深度研究，生成完整的研究报告",
        param_infos={
            "research_title": "研究的标题（简短描述）",
            "research_purpose": "研究的详细目的和需求"
        }
    )
    async def deep_research(self, research_title: str, research_purpose: str) -> str:
        """
        深度研究的主入口

        Args:
            research_title: 研究标题
            research_purpose: 研究目的和需求

        Returns:
            研究报告的文件路径
        """
        self.logger.info(f"🚀 开始深度研究: {research_title}")

        try:
            # 1. 初始化研究上下文
            ctx = await self._init_research_context(research_title, research_purpose)
            self.logger.info("✓ 研究上下文初始化完成")

            # 2. 生成人设（使用think-with-retry）
            await self._generate_personas(ctx)
            self.logger.info("✓ 人设生成完成")

            # 3. 制定研究计划（Planning Stage - MicroAgent）
            await self._planning_stage(ctx)
            self.logger.info("✓ 研究计划制定完成")

            # 4. 执行研究循环（Research Loop - MicroAgent）
            await self._research_loop(ctx)
            self.logger.info("✓ 研究循环完成")

            # 5. 撰写报告（Writing Loop - MicroAgent）
            report_path = await self._writing_loop(ctx)
            self.logger.info(f"✓ 研究报告生成完成: {report_path}")

            return f"研究报告已生成：{report_path}"

        except Exception as e:
            self.logger.error(f"深度研究失败: {e}")
            raise

    # ==========================================
    # Stage 1: 初始化与人设生成
    # ==========================================

    async def _init_research_context(self, research_title: str, research_purpose: str) -> ResearchContext:
        """初始化研究上下文"""
        ctx = ResearchContext(
            research_title=research_title,
            research_purpose=research_purpose
        )

        # 初始化笔记本
        ctx.notebook = Notebook(page_size_limit=2000)

        # 创建研究目录
        ctx.research_dir.mkdir(parents=True, exist_ok=True)

        return ctx

    async def _generate_personas(self, ctx: ResearchContext):
        """
        生成研究导师和研究员人设

        使用think-with-retry模式确保输出格式正确
        """
        # 生成研究导师人设
        director_prompt = format_prompt(
            DeepResearcherPrompts.DIRECTOR_PERSONA_DESIGNER,
            ctx
        )
        director_persona = await self.brain.think_with_retry(
            director_prompt,
            persona_parser  # 使用从helper导入的parser
        )
        ctx.director_persona = director_persona
        self.logger.info(f"✓ 研究导师人设生成完成")

        # 生成研究员人设
        researcher_prompt = format_prompt(
            DeepResearcherPrompts.RESEARCHER_PERSONA_DESIGNER,
            ctx
        )
        researcher_persona = await self.brain.think_with_retry(
            researcher_prompt,
            persona_parser  # 使用从helper导入的parser
        )
        ctx.researcher_persona = researcher_persona
        self.logger.info(f"✓ 研究员人设生成完成")

    # ==========================================
    # Stage 2: 研究计划制定 (Planning Stage)
    # ==========================================

    async def _planning_stage(self, ctx: ResearchContext):
        """
        研究计划制定阶段

        使用dialog_with_retry模式，让researcher生成计划，director评估并批准。
        这是一个智能对话循环，director不仅仅是检查格式，而是深度评估计划质量。
        """
        self.logger.info("📋 进入研究计划制定阶段")

        # Producer (A) - Researcher的任务
        producer_task = format_prompt(
            DeepResearcherPrompts.START_PLAN_PROMPT,
            ctx
        )

        # Verifier (B) - Director的评估任务模板
        verifier_task_template = format_prompt(
            """
            {{director_persona}}

            研究员提交了以下研究计划，请你进行深度评估并决定是否批准。

            [研究计划草稿]
            {{producer_output}}

            请重点评估：
            1. 核心逻辑链闭环（The "Fatal Flaw" Check）
               - 研究目的是否明确？
               - 方法是否能回答研究目的？

            2. 第一步极其具体（The "Tomorrow" Test）
               - 计划的第一个步骤是否具备极高的可操作性？

            3. 区分"必要性修改"与"偏好性修改"
               - 必要性修改：逻辑错误、安全隐患、方法不可行（必须指出）
               - 偏好性修改：你觉得这样更好（可以不提）

            输出格式：
            [决策]
            批准 / 不批准

            [理由]
            你的评估理由

            [反馈]
            如果不批准，请提供具体的改进建议
            """,
            ctx
        )

        # 使用dialog_with_retry进行对话
        result = await self.brain.dialog_with_retry(
            producer_task=producer_task,
            producer_persona=ctx.researcher_persona,
            verifier_task_template=verifier_task_template,
            verifier_persona=ctx.director_persona,
            producer_parser=research_plan_parser,     # ← A的结构验证
            approver_parser=director_approval_parser,  # ← B的语义验证
            max_rounds=3
        )

        # 检查是否超过max_rounds
        if result.get("max_rounds_exceeded"):
            self.logger.warning(f"⚠️ 研究计划未能在{result['rounds_used']}轮内获得批准")
            if "last_feedback" in result:
                self.logger.warning(f"最后反馈: {result['last_feedback'][:200]}...")
        else:
            self.logger.info(f"✅ 研究计划在第 {result['rounds_used']} 轮获得批准")

        # result["content"] 已经是解析后的数据
        final_plan = result["content"]

        # 保存到context
        ctx.research_plan = final_plan["[研究计划]"]
        chapter_outline = final_plan["[章节大纲]"]
        ctx.key_questions = final_plan["[关键问题清单]"]

        # 解析章节大纲
        chapters = []
        for line in chapter_outline.split('\n'):
            line = line.strip()
            if line.startswith('# '):
                chapter_name = line[2:].strip()
                chapters.append(chapter_name)
                # 在笔记本中创建对应章节
                ctx.notebook.create_chapter(chapter_name)

        ctx.chapter_outline = chapters
        self.logger.info(f"✓ 研究计划包含 {len(chapters)} 个章节")

    # ==========================================
    # Stage 3: 研究循环 (Research Loop)
    # ==========================================

    async def _research_loop(self, ctx: ResearchContext):
        """
        研究循环

        使用MicroAgent来执行研究任务，包括搜索、浏览、记笔记
        """
        self.logger.info("🔍 进入研究循环")

        # 临时保存当前研究上下文，供actions访问
        self._current_research_ctx = ctx

        # 构建研究任务指导
        notebook_summary = self._get_notebook_summary(ctx)

        research_task_prompt = format_prompt(
            DeepResearcherPrompts.RESEARCH_TASK_GUIDANCE,
            ctx,
            notebook_summary=notebook_summary
        )

        # 执行研究循环（MicroAgent可以自由选择action）
        research_result = await self._run_micro_agent(
            persona=ctx.researcher_persona,
            task=research_task_prompt + "\n\n请开始研究工作，使用web_search搜索相关信息，使用take_note记录重要发现。",
            available_actions=[
                "web_search",  # 来自web_searcher skill
                "take_note",   # 本skill提供的action
                "summarize_page",
                "check_notebook"
            ],
            max_steps=20  # 限制研究步骤
        )

        self.logger.info(f"研究循环完成: {research_result}")

        # 清理上下文引用
        self._current_research_ctx = None

    def _get_notebook_summary(self, ctx: ResearchContext) -> str:
        """获取笔记本的摘要信息"""
        summary = []
        summary.append(f"总页数: {len(ctx.notebook.pages)}")
        summary.append(f"总章节数: {len(ctx.notebook.list_chapters())}")

        for chapter_name in ctx.notebook.list_chapters():
            info = ctx.notebook.get_chapter_info(chapter_name)
            summary.append(f"\n章节 '{chapter_name}':")
            summary.append(f"  - 笔记数: {len(info['notes'])}")
            summary.append(f"  - 页面数: {len(info['pages'])}")
            summary.append(f"  - 摘要数: {len(info['summaries'])}")

        return '\n'.join(summary)

    # ==========================================
    # Stage 4: 报告撰写 (Writing Loop)
    # ==========================================

    async def _writing_loop(self, ctx: ResearchContext) -> str:
        """
        报告撰写循环

        基于番茄笔记法，为每个章节撰写草稿
        """
        self.logger.info("✍️ 进入报告撰写循环")

        report_path = ctx.research_dir / f"{sanitize_filename(ctx.research_title)}_report.md"
        chapter_drafts = []

        # 为每个章节撰写草稿
        for chapter_name in ctx.chapter_outline:
            self.logger.info(f"撰写章节: {chapter_name}")

            # 获取章节相关的笔记和摘要
            chapter_info = ctx.notebook.get_chapter_info(chapter_name)
            chapter_notes = [note.content for note in chapter_info['notes']]
            chapter_summaries = chapter_info['summaries']

            # 使用MicroAgent撰写章节草稿
            chapter_draft = await self._run_micro_agent(
                persona=ctx.researcher_persona,
                task=format_prompt(
                    DeepResearcherPrompts.WRITE_CHAPTER_DRAFT,
                    ctx,
                    chapter_name=chapter_name,
                    chapter_notes='\n'.join(chapter_notes),
                    chapter_summaries='\n'.join(chapter_summaries)
                ),
                available_actions=["think_only"],
                max_steps=1
            )

            chapter_drafts.append(f"# {chapter_name}\n\n{chapter_draft}\n\n")

        # 汇总完整报告
        full_report = f"# {ctx.research_title}\n\n"
        full_report += f"## 研究目的\n\n{ctx.research_purpose}\n\n"
        full_report += "---\n\n"
        full_report += '\n'.join(chapter_drafts)

        # 保存报告
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(full_report)

        self.logger.info(f"✓ 报告已保存: {report_path}")

        return str(report_path)

    # ==========================================
    # 研究循环Actions
    # ==========================================

    @register_action(
        description="从网页内容中提取关键信息并记录到笔记本",
        param_infos={
            "content": "网页内容",
            "url": "网页URL",
            "title": "网页标题",
            "chapter_name": "关联的章节名称"
        }
    )
    async def take_note(self, content: str, url: str, title: str, chapter_name: str) -> str:
        """
        记录笔记到笔记本

        使用MicroAgent提取关键信息并记录
        """
        # 获取当前研究上下文
        ctx = getattr(self, '_current_research_ctx', None)
        if not ctx:
            return "错误：没有活跃的研究上下文"

        # 使用MicroAgent提取关键信息
        note_prompt = f"""
        从以下网页内容中提取关键信息：

        研究主题：{ctx.research_title}
        关联章节：{chapter_name}
        URL: {url}
        标题: {title}
        内容: {content[:3000]}...

        请提取：
        1. 与章节直接相关的关键信息、数据、观点
        2. 值得引用的具体例子或案例
        3. 需要进一步验证的问题

        以简洁的要点形式输出笔记，每条笔记不超过50字。
        """

        note_content = await self._run_micro_agent(
            persona="你是一个专业的研究助理",
            task=note_prompt,
            available_actions=["think_only"],
            max_steps=1
        )

        # 添加到笔记本
        page = ctx.notebook.add_note(note_content, chapter_name)

        return f"✓ 已记录笔记到章节 '{chapter_name}'，当前页共有 {len(page.notes)} 条笔记"

    @register_action(
        description="总结当前页面的所有笔记",
        param_infos={
            "page_number": "页码（可选，默认为最后一页）"
        }
    )
    async def summarize_page(self, page_number: int = -1) -> str:
        """总结当前页面"""
        # 获取当前研究上下文
        ctx = getattr(self, '_current_research_ctx', None)
        if not ctx:
            return "错误：没有活跃的研究上下文"

        # 获取指定页面
        if page_number == -1:
            # 默认最后一页
            if not ctx.notebook.pages:
                return "错误：笔记本为空"
            page = ctx.notebook.pages[-1]
        else:
            if page_number < 0 or page_number >= len(ctx.notebook.pages):
                return f"错误：页码 {page_number} 超出范围"
            page = ctx.notebook.pages[page_number]

        if not page.notes:
            return f"页面 {page_number} 没有笔记"

        # 构建总结prompt
        notes_text = '\n'.join([f"{i+1}. {note.content}" for i, note in enumerate(page.notes)])

        # 获取页面相关章节
        chapter_names = list(page.chapter_ids)

        summary_prompt = f"""
        请为当前研究页面的所有笔记生成一份总结摘要。

        研究主题：{ctx.research_title}
        页码：{page.page_number}
        关联章节：{', '.join(chapter_names)}
        本页笔记数量：{len(page.notes)}
        本页笔记内容：
        {notes_text}

        请生成一份200字以内的总结，概括本页的核心发现和关键信息。
        """

        summary = await self._run_micro_agent(
            persona="你是一个专业的研究助理",
            task=summary_prompt,
            available_actions=["think_only"],
            max_steps=1
        )

        # 保存摘要
        ctx.notebook.set_page_summary(page.page_number, summary)

        return f"✓ 页面 {page_number} 已生成摘要：{summary[:100]}..."

    @register_action(
        description="查看笔记本当前状态，包括页面数、章节数、笔记数等"
    )
    async def check_notebook(self) -> str:
        """查看笔记本状态"""
        # 获取当前研究上下文
        ctx = getattr(self, '_current_research_ctx', None)
        if not ctx:
            return "错误：没有活跃的研究上下文"

        summary = self._get_notebook_summary(ctx)
        return summary
