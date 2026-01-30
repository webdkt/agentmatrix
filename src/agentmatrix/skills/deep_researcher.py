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
            await self._init_research_context(research_title, research_purpose)

            # 2. 生成人设（使用think-with-retry）
            await self._generate_personas()

            # 3. 制定研究计划（Planning Stage - MicroAgent）
            await self._planning_stage()

            # 4. 执行研究循环（Research Loop - MicroAgent）
            await self._research_loop()

            # 5. 撰写报告（Writing Loop - MicroAgent）
            report_path = await self._writing_loop()

            return f"研究报告已生成：{report_path}"

        except Exception as e:
            self.logger.error(f"深度研究失败: {e}")
            raise

    # ==========================================
    # Stage 1: 初始化与人设生成
    # ==========================================

    async def _init_research_context(self, research_title: str, research_purpose: str):
        """
        初始化研究上下文（直接使用 session context）

        在 session context 中设置：
        - research_title: 研究标题
        - research_purpose: 研究目的
        - notebook_file: notebook 文件路径
        """
        # 检查是否已初始化
        ctx = self.get_session_context()
        if "research_title" in ctx:
            self.logger.info("✓ 研究上下文已存在，跳过初始化")
            return

        # 获取 session 文件夹
        session_folder = self.get_session_folder()
        if not session_folder:
            raise ValueError("No active session folder")

        # 初始化 notebook（使用 session 文件夹）
        from pathlib import Path
        notebook_file = str(Path(session_folder) / "notebook.json")
        notebook = Notebook(file_path=notebook_file, page_size_limit=2000)

        # 保存到 session context
        await self.update_session_context(
            research_title=research_title,
            research_purpose=research_purpose,
            notebook_file=notebook_file
        )

        self.logger.info("✓ 研究上下文初始化完成")

    async def _generate_personas(self):
        """
        生成研究导师和研究员人设

        使用think-with-retry模式确保输出格式正确
        """
        ctx = self.get_session_context()

        # 生成研究导师人设
        director_prompt = format_prompt(
            DeepResearcherPrompts.DIRECTOR_PERSONA_DESIGNER,
            ctx
        )
        director_persona = await self.brain.think_with_retry(
            director_prompt,
            persona_parser
        )

        # 生成研究员人设
        researcher_prompt = format_prompt(
            DeepResearcherPrompts.RESEARCHER_PERSONA_DESIGNER,ctx, direct_persona=director_persona
        )
        researcher_persona = await self.brain.think_with_retry(
            researcher_prompt,
            persona_parser
        )

        # 保存到 session context
        await self.update_session_context(
            director_persona=director_persona,
            researcher_persona=researcher_persona
        )

        self.logger.info("✓ 人设生成完成")

    # ==========================================
    # Stage 2: 研究计划制定 (Planning Stage)
    # ==========================================

    async def _planning_stage(self):
        """
        研究计划制定阶段 - 使用 Micro Agent 模式

        研究蓝图包含三个部分：
        1. blueprint_overview - 自由文本，研究想法和思路
        2. research_plan - 任务列表（todo list）
        3. chapter_outline - 章节大纲（heading one 列表）
        """
        self.logger.info("📋 进入研究计划制定阶段（Micro Agent 模式）")

        ctx = self.get_session_context()

        planning_task = format_prompt(
            """
            {researcher_persona}

            你正在为 [{research_title}] 项目制定研究蓝图。

            研究目的：{research_purpose}

            研究蓝图包含三个部分：
            1. 研究想法和整体思路
            2. 任务列表，列出明确研究的步骤和顺序
            3. 章节大纲，规划报告的结构

            开始制定研究蓝图吧！
            """,
            ctx
        )

        # 执行 Micro Agent
        try:
            result = await self._run_micro_agent(
                persona=ctx["researcher_persona"],
                task=planning_task,
                available_actions=[
                    "web_search",
                    "consult_with_director",
                    "save_blueprint_overview",
                    "create_research_plan",  # 改用 create_research_plan
                    "save_chapter_outline",

                ],
                max_steps=15
            )

            self.logger.info(f"✅ 研究蓝图制定完成: {result}")

            # 重新加载 context，获取最新的更新
            ctx = self.get_session_context()

            # 验证三个必要字段是否已保存
            if not ctx.get("blueprint_overview"):
                raise ValueError("研究蓝图概览未保存，无法继续")

            if not ctx.get("research_plan"):
                raise ValueError("研究计划未保存，无法继续")

            if not ctx.get("chapter_outline"):
                raise ValueError("章节大纲未保存，无法继续")

            # 记录成功信息
            # research_plan 现在是字典列表
            plan_count = len(ctx["research_plan"]) if isinstance(ctx["research_plan"], list) else 0
            chapter_count = len(ctx["chapter_outline"]) if isinstance(ctx["chapter_outline"], list) else 1

            self.logger.info(f"✓ 研究蓝图概览已保存（{len(ctx['blueprint_overview'])} 字符）")
            self.logger.info(f"✓ 研究计划已创建（{plan_count} 个任务）")
            self.logger.info(f"✓ 章节大纲已保存（{chapter_count} 章）")

        except Exception as e:
            self.logger.error(f"研究蓝图制定失败: {e}")
            raise

    # ==========================================
    # Stage 3: 研究循环 (Research Loop)
    # ==========================================

    async def _research_loop(self):
        """
        改进的研究循环 - 任务驱动模式

        工作流程：
        1. MicroAgent 查看任务列表（get_research_progress）
        2. 选择一个待进行任务
        3. 执行任务（web_search, take_note等）
        4. 标记任务完成（complete_task）
        5. 根据研究发现，决定是否需要更新计划（update_research_plan）
        6. 重复直到所有任务完成
        """
        self.logger.info("🔍 进入研究循环（任务驱动模式）")

        ctx = self.get_session_context()

        # 检查研究计划是否存在
        if not ctx.get("research_plan"):
            raise ValueError("研究计划不存在，请先在 Planning Stage 创建计划")

        plan = ctx["research_plan"]

        # 加载 notebook
        from .deep_researcher_helper import Notebook
        notebook = Notebook(file_path=ctx["notebook_file"])

        # 构建任务指导
        notebook_summary = self._get_notebook_summary(notebook)
        task_list = self._format_plan(plan)
        progress_summary = self._get_progress_summary(plan)

        research_task_prompt = f"""{ctx['researcher_persona']}

你正在进行 [{ctx['research_title']}] 的研究工作。

当前研究任务列表：
{task_list}

{progress_summary}

当前笔记本摘要：
{notebook_summary}

请按以下流程工作：
1. 使用 get_research_progress 查看当前任务列表
2. 选择一个 ⏳ 待进行的任务
3. 执行任务（使用 web_search, take_note, summarize_page 等 action）
4. 任务完成后，使用 complete_task 标记为 ✅ 已完成（需要提供任务的确切描述内容）
5. 根据研究发现，决定是否需要用 update_research_plan 更新后续计划
6. 重复步骤 1-5，直到所有任务完成

重要提示：
- complete_task 需要提供任务的确切描述内容（必须完全匹配）
- update_research_plan 会替换所有未完成的任务
- 当所有任务都 ✅ 已完成时，研究工作结束
"""

        # 执行研究循环
        research_result = await self._run_micro_agent(
            persona=ctx["researcher_persona"],
            task=research_task_prompt,
            available_actions=[
                "web_search",
                "take_note",
                "summarize_page",
                "complete_task",           # 新增
                "update_research_plan",    # 新增
                "get_research_progress",   # 新增
                "check_notebook"
            ],
            max_steps=50  # 更大的步数，因为要完成多个任务
        )

        # 检查是否全部完成
        final_plan = ctx.get("research_plan", [])
        all_completed = all(t["status"] == "completed" for t in final_plan)

        if all_completed:
            self.logger.info("✅ 所有研究任务已完成")
        else:
            pending_count = sum(1 for t in final_plan if t["status"] == "pending")
            self.logger.warning(f"⚠️ 仍有 {pending_count} 个任务未完成")

        return research_result

    def _get_notebook_summary(self, notebook) -> str:
        """获取笔记本的摘要信息"""
        summary = []
        summary.append(f"总页数: {len(notebook.pages)}")
        summary.append(f"总章节数: {len(notebook.list_chapters())}")

        for chapter_name in notebook.list_chapters():
            info = notebook.get_chapter_info(chapter_name)
            summary.append(f"\n章节 '{chapter_name}':")
            summary.append(f"  - 笔记数: {len(info['notes'])}")
            summary.append(f"  - 页面数: {len(info['pages'])}")
            summary.append(f"  - 摘要数: {len(info['summaries'])}")

        return '\n'.join(summary)

    # ==========================================
    # Stage 4: 报告撰写 (Writing Loop)
    # ==========================================

    async def _writing_loop(self) -> str:
        """
        报告撰写循环

        基于番茄笔记法，为每个章节撰写草稿
        """
        self.logger.info("✍️ 进入报告撰写循环")

        ctx = self.get_session_context()

        # 加载 notebook
        from .deep_researcher_helper import Notebook
        notebook = Notebook(file_path=ctx["notebook_file"])

        # 报告保存到 session 文件夹
        from pathlib import Path
        session_folder = self.get_session_folder()
        report_path = Path(session_folder) / f"{sanitize_filename(ctx['research_title'])}_report.md"
        chapter_drafts = []

        # 为每个章节撰写草稿
        for chapter_name in ctx["chapter_outline"]:
            self.logger.info(f"撰写章节: {chapter_name}")

            # 获取章节相关的笔记和摘要
            chapter_info = notebook.get_chapter_info(chapter_name)
            chapter_notes = [note.content for note in chapter_info['notes']]
            chapter_summaries = chapter_info['summaries']

            # 使用MicroAgent撰写章节草稿
            chapter_draft = await self._run_micro_agent(
                persona=ctx["researcher_persona"],
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
        full_report = f"# {ctx['research_title']}\n\n"
        full_report += f"## 研究目的\n\n{ctx['research_purpose']}\n\n"
        full_report += "---\n\n"
        full_report += '\n'.join(chapter_drafts)

        # 保存报告
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(full_report)

        self.logger.info(f"✓ 报告已保存: {report_path}")

        return str(report_path)

    # ==========================================
    # Planning Stage Actions
    # ==========================================

    @register_action(
        description="阐述并保存研究蓝图概览（概要简练的研究想法和思路）",
        param_infos={
            "overview": "研究蓝图的概览描述，自由文本格式"
        }
    )
    async def save_blueprint_overview(self, overview: str) -> str:
        """保存研究蓝图概览"""
        # 基本校验：非空
        overview_stripped = overview.strip()
        if not overview_stripped:
            return "❌ 研究蓝图概览不能为空。请描述你的研究想法和思路。"

        # 保存到 session context
        await self.update_session_context(blueprint_overview=overview_stripped)

        return f"✅ 研究蓝图概览已保存（{len(overview_stripped)} 字符）"

    @register_action(
        description="咨询导师确认研究方案是否可行，有无建议"
    )
    async def consult_with_director(self) -> str:
        """咨询导师获取建议"""
        ctx = self.get_session_context()

        # 构建当前状态描述
        status_parts = []
        if ctx.get("blueprint_overview"):
            status_parts.append(f"✓ 已有研究蓝图概览")
        else:
            status_parts.append("✗ 尚未有研究蓝图概览")

        if ctx.get("research_plan"):
            plan_count = len(ctx["research_plan"]) if isinstance(ctx["research_plan"], list) else 1
            status_parts.append(f"✓ 已有研究计划（{plan_count} 个任务）")
        else:
            status_parts.append("✗ 尚未有研究计划")

        if ctx.get("chapter_outline"):
            chapters_str = "\n".join([f"  # {ch}" for ch in ctx["chapter_outline"]])
            status_parts.append(f"✓ 已有章节大纲（{len(ctx['chapter_outline'])} 章）：\n{chapters_str}")
        else:
            status_parts.append("✗ 尚未有章节大纲")

        status_text = "\n".join(status_parts)

        # 构建给导师的内容
        overview_content = ""
        if ctx.get("blueprint_overview"):
            overview_content = f"\n\n[研究蓝图概览]\n{ctx['blueprint_overview']}\n"

        plan_content = ""
        if ctx.get("research_plan"):
            if isinstance(ctx["research_plan"], list):
                plan_items = "\n".join([f"  {i+1}. {task}" for i, task in enumerate(ctx["research_plan"])])
                plan_content = f"\n\n[研究计划 - 任务列表]\n{plan_items}\n"
            else:
                plan_content = f"\n\n[研究计划]\n{ctx['research_plan']}\n"

        outline_content = ""
        if ctx.get("chapter_outline"):
            outline_content = f"\n[章节大纲]\n" + "\n".join([f"# {ch}" for ch in ctx["chapter_outline"]]) + "\n"

        consultation_prompt = f"""{ctx['director_persona']}

现在有一个新的研究任务：
{ctx['research_title']}

研究目的和需求：
{ctx['research_purpose']}

[当前进度]
{status_text}
{overview_content}
{plan_content}
{outline_content}

请根据当前进度提供建议和反馈，重点评估：
1. 核心逻辑链闭环
   - 研究目的是否明确？
   - 方法是否能回答研究目的？

2. 第一步极其具体
   - 计划的第一个步骤是否具备极高的可操作性？

3. 计划和研究目标的适配度
   - 如果目标很简单，计划也应该简单
   - 如果目标复杂，计划也应该相应的复杂

4. 鼓励为主
   - 计划永远不可能完美，基本可行的基础上，鼓励尽快开始实际研究工作

请简洁地给出你的建议（控制在200字以内）。
"""

        try:
            response = await self.brain.think(consultation_prompt)
            advice = response['reply']

            # 保存导师建议到 session context
            await self.update_session_context(director_advice=advice)

            return f"📝 导师建议：\n{advice}"

        except Exception as e:
            return f"❌ 咨询导师失败：{str(e)}"

    @register_action(
        description="创建研究计划任务列表（每行一个任务，所有任务初始状态为待进行）",
        param_infos={
            "tasks": "任务列表文本，每行一个任务"
        }
    )
    async def create_research_plan(self, tasks: str) -> str:
        """
        创建初始研究计划（Planning Stage 使用）

        - 解析任务列表（每行一个）
        - 所有任务状态为 "pending"
        - 直接覆盖 session context 中的 research_plan
        """
        # 解析任务列表
        task_list = [
            line.strip()
            for line in tasks.strip().split('\n')
            if line.strip()
        ]

        if len(task_list) < 2:
            return "❌ 任务数量太少（至少需要2个任务）"

        # 创建任务列表（每个任务是一个字典）
        plan = [
            {"content": content, "status": "pending"}
            for content in task_list
        ]

        # 保存到 session context
        await self.update_session_context(research_plan=plan)

        # 格式化显示
        task_preview = "\n".join([f"  ⏳ {t['content']}" for t in plan])

        return f"""✅ 研究计划已创建，共 {len(plan)} 个任务：

{task_preview}"""

    @register_action(
        description="制定并保存章节大纲（章节标题每行以 # 开头,只需要一级章节）",
        param_infos={
            "outline": "章节大纲多行文本，每行一个章节，用 # 开头。例如：# 第一章 研究背景"
        }
    )
    async def save_chapter_outline(self, outline: str) -> str:
        """校验并保存章节大纲"""
        # 校验格式
        lines = [line.strip() for line in outline.strip().split('\n') if line.strip()]
        errors = []

        for i, line in enumerate(lines, 1):
            if not line.startswith('#'):
                errors.append(f"第 {i} 行: '{line}' 不以 # 开头")

        if errors:
            error_msg = "❌ 章节大纲格式错误：\n" + "\n".join(errors)
            error_msg += "\n\n正确格式示例：\n# 第一章标题\n# 第二章标题\n# 第三章标题"
            return error_msg

        if len(lines) < 2:
            return f"❌ 章节数量太少（当前 {len(lines)} 个），至少需要 2 个章节。"

        # 校验通过，保存章节列表
        chapters = [line[1:].strip() for line in lines]  # 去掉 # 号

        # 在 notebook 中创建章节
        ctx = self.get_session_context()
        from .deep_researcher_helper import Notebook
        notebook = Notebook(file_path=ctx["notebook_file"])

        for chapter_name in chapters:
            try:
                notebook.create_chapter(chapter_name)
            except ValueError:
                pass  # 章节已存在

        # 保存到 session context
        await self.update_session_context(chapter_outline=chapters)

        return f"✅ 章节大纲已保存，共 {len(chapters)} 个章节：\n" + "\n".join([f"  - {ch}" for ch in chapters])

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
        """记录笔记到笔记本"""
        ctx = self.get_session_context()

        # 使用MicroAgent提取关键信息
        note_prompt = f"""
        从以下网页内容中提取关键信息：

        研究主题：{ctx['research_title']}
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

        # 添加到笔记本（自动保存）
        from .deep_researcher_helper import Notebook
        notebook = Notebook(file_path=ctx["notebook_file"])
        page = notebook.add_note(note_content, chapter_name)

        return f"✓ 已记录笔记到章节 '{chapter_name}'，当前页共有 {len(page.notes)} 条笔记"

    @register_action(
        description="总结当前页面的所有笔记",
        param_infos={
            "page_number": "页码（可选，默认为最后一页）"
        }
    )
    async def summarize_page(self, page_number: int = -1) -> str:
        """总结当前页面"""
        ctx = self.get_session_context()

        # 加载 notebook
        from .deep_researcher_helper import Notebook
        notebook = Notebook(file_path=ctx["notebook_file"])

        # 获取指定页面
        if page_number == -1:
            if not notebook.pages:
                return "错误：笔记本为空"
            page = notebook.pages[-1]
        else:
            if page_number < 0 or page_number >= len(notebook.pages):
                return f"错误：页码 {page_number} 超出范围"
            page = notebook.pages[page_number]

        if not page.notes:
            return f"页面 {page_number} 没有笔记"

        # 构建总结prompt
        notes_text = '\n'.join([f"{i+1}. {note.content}" for i, note in enumerate(page.notes)])
        chapter_names = list(page.chapter_ids)

        summary_prompt = f"""
        请为当前研究页面的所有笔记生成一份总结摘要。

        研究主题：{ctx['research_title']}
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

        # 保存摘要（自动保存）
        notebook.set_page_summary(page.page_number, summary)

        return f"✓ 页面 {page_number} 已生成摘要：{summary[:100]}..."

    @register_action(
        description="查看笔记本当前状态，包括页面数、章节数、笔记数等"
    )
    async def check_notebook(self) -> str:
        """查看笔记本状态"""
        ctx = self.get_session_context()

        # 加载 notebook
        from .deep_researcher_helper import Notebook
        notebook = Notebook(file_path=ctx["notebook_file"])

        summary = self._get_notebook_summary(notebook)
        return summary

    # ==========================================
    # 研究计划管理 Actions（任务驱动模式）
    # ==========================================

    @register_action(
        description="标记任务为已完成（需要提供任务的具体描述内容）",
        param_infos={
            "task_content": "要标记为已完成的任务描述（必须与当前任务列表中的任务完全匹配）"
        }
    )
    async def complete_task(self, task_content: str) -> str:
        """
        标记任务为已完成

        工作流程：
        1. 在 research_plan 中查找匹配的任务
        2. 将其 status 改为 "completed"
        3. 保存到 session context
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        if not plan:
            return "❌ 研究计划不存在，请先使用 create_research_plan 创建计划"

        # 查找任务
        task_found = False
        for task in plan:
            if task["status"] == "pending" and task["content"] == task_content:
                task["status"] = "completed"
                task_found = True
                break

        if not task_found:
            # 提供更友好的错误提示
            pending_tasks = [t["content"] for t in plan if t["status"] == "pending"]
            if pending_tasks:
                tasks_preview = "\n".join([f"  - {t}" for t in pending_tasks[:5]])
                return f"""❌ 未找到任务：{task_content}

当前待进行的任务：
{tasks_preview}
{f"... 等共 {len(pending_tasks)} 个任务" if len(pending_tasks) > 5 else ""}

提示：请使用 get_research_progress 查看完整任务列表，确保任务描述完全匹配"""
            else:
                return "❌ 没有待进行的任务了"

        # 保存
        await self.update_session_context(research_plan=plan)

        # 返回进度
        return f"""✅ 任务已完成：{task_content}

{self._get_progress_summary(plan)}"""

    @register_action(
        description="更新研究计划：提供新的任务列表文本（每行一个任务），将替换当前所有未完成的任务（已完成的任务会保留）",
        param_infos={
            "new_tasks": "新的任务列表文本，每行一个任务"
        }
    )
    async def update_research_plan(self, new_tasks: str) -> str:
        """
        更新研究计划（Research Loop 使用）

        功能：
        - 保留所有 status="completed" 的任务
        - 删除所有 status="pending" 的任务
        - 添加新的 pending 任务
        """
        ctx = self.get_session_context()
        current_plan = ctx.get("research_plan", [])

        if not current_plan:
            return "❌ 研究计划不存在，请先使用 create_research_plan 创建计划"

        # 保留已完成的任务
        completed_tasks = [t for t in current_plan if t["status"] == "completed"]

        # 解析新任务列表
        new_task_list = [
            line.strip()
            for line in new_tasks.strip().split('\n')
            if line.strip()
        ]

        if len(new_task_list) < 1:
            return "❌ 任务列表不能为空"

        # 构建新的研究计划
        new_plan = []

        # 1. 保留已完成的任务
        for task in completed_tasks:
            new_plan.append(task)

        # 2. 添加新的待进行任务
        for content in new_task_list:
            new_plan.append({"content": content, "status": "pending"})

        # 保存
        await self.update_session_context(research_plan=new_plan)

        # 返回结果
        pending_count = len(new_task_list)
        completed_count = len(completed_tasks)

        return f"""✅ 研究计划已更新

保留已完成：{completed_count} 个
新增待进行：{pending_count} 个

当前任务列表：
{self._format_plan(new_plan)}"""

    @register_action(
        description="查看当前研究计划和任务完成进度"
    )
    async def get_research_progress(self) -> str:
        """查看研究进度"""
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        if not plan:
            return "❌ 研究计划不存在，请先使用 create_research_plan 创建计划"

        lines = ["📋 研究计划\n"]

        for task in plan:
            emoji = "✅" if task["status"] == "completed" else "⏳"
            lines.append(f"  {emoji} {task['content']}")

        lines.append("\n" + self._get_progress_summary(plan))

        return "\n".join(lines)

    # ==========================================
    # 辅助方法
    # ==========================================

    def _format_plan(self, plan: list) -> str:
        """格式化任务列表用于显示"""
        lines = []
        for task in plan:
            emoji = "✅" if task["status"] == "completed" else "⏳"
            lines.append(f"  {emoji} {task['content']}")
        return "\n".join(lines)

    def _get_progress_summary(self, plan: list) -> str:
        """获取进度摘要"""
        total = len(plan)
        completed = sum(1 for t in plan if t["status"] == "completed")
        pending = total - completed

        pct = (completed / total * 100) if total > 0 else 0

        return f"📊 进度：{completed}/{total} ({pct:.1f}%) | ✅ 已完成 {completed} | ⏳ 待进行 {pending}"
