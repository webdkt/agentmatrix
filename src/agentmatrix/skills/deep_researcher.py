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
from .parser_utils import multi_section_parser
from .web_searcher import WebSearcherMixin


class DeepResearcherMixin(WebSearcherMixin):
    """Deep Researcher Skill Mixin

    继承 WebSearcherMixin 以获得 web_search 能力
    """

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
        初始化研究上下文

        在 session context 中设置：
        - research_title: 研究标题
        - research_purpose: 研究目的

        在 transient context 中设置：
        - notebook: Notebook 对象（非持久化）
        """
        # 获取 session 文件夹
        session_folder = self.get_session_folder()

        # 初始化 notebook（使用 session 文件夹）
        from pathlib import Path
        notebook_file = str(Path(session_folder) / "notebook.json")
        notebook = Notebook(file_path=notebook_file, page_size_limit=2000)

        # 保存到 session context（持久化）
        await self.update_session_context(
            research_title=research_title,
            research_purpose=research_purpose,
            notebook_file=notebook_file  # 保存路径，用于数据持久化
        )

        # 保存 notebook 对象到 transient context（非持久化）
        self.set_transient("notebook", notebook)

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
            2. 研究任务列表，列出明确研究的步骤和顺序
            3. 章节大纲，规划报告的结构



            开始制定研究蓝图吧！注意，研究任务不需要包括报告编写工作，研究工作完成后会单独处理报告撰写。
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
                    "create_chapter_outline",
                    "update_blueprint",
                    "update_research_plan",
                    "update_chapter_outline"

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

    async def _do_research_task(self, task_content: str) -> str:
        """
        执行单个研究任务（Micro Agent）

        Args:
            task_content: 任务内容

        Returns:
            执行结果（Micro Agent 的最终输出）
        """
        self.logger.info(f"📌 开始执行任务：{task_content}")

        # 保存当前任务到 transient context
        self.set_transient("current_research_task", task_content)

        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        # 获取当前任务的初始总结（如果有）
        current_task_data = None
        for task in plan:
            if task["content"] == task_content:
                current_task_data = task
                break

        current_summary = current_task_data.get("summary", "") if current_task_data else ""

        # 获取研究蓝图文本（包含三要素）
        blueprint_text = self._get_research_blueprint_text()

        # 构建 Micro Agent 任务描述
        research_task_prompt = f"""{ctx['researcher_persona']}

你正在执行深度研究的任务。

== 研究背景 ==
{blueprint_text}

现在准备进行：{task_content}

请充分思考后开始。如果现有能力无法完成该任务，就写个简短总结说明原因，然后结束任务。
"""

        # 执行 Micro Agent
        try:
            result = await self._run_micro_agent(
                persona=ctx['researcher_persona'],
                task=research_task_prompt,
                available_actions=[
                    "web_search",
                    "take_note",
                    "update_task_summary",
                    "check_task_summary",
                    "update_research_plan",
                    "update_chapter_outline",
                    "finish_task"
                ],
                max_steps=20  # 每个任务最多 20 步
            )

            self.logger.info(f"✅ 任务完成：{task_content}")

            # 标记任务为 completed
            await self._mark_task_completed(task_content)

            return result

        except Exception as e:
            self.logger.error(f"❌ 任务执行失败：{task_content}，错误：{e}")
            raise

    async def _research_loop(self):
        """
        新的研究循环 - 任务驱动模式

        工作流程：
        1. 循环获取下一个 pending 任务
        2. 为每个任务创建 Micro Agent 执行研究
        3. Micro Agent 调用 finish_task 后返回
        4. 标记任务为 completed
        5. 继续下一个任务，直到所有任务完成
        """
        self.logger.info("🔍 进入研究循环（新架构）")

        ctx = self.get_session_context()

        
        task_count = 0
        while True:
            # 1. 获取下一个 pending 任务
            current_task = self._get_next_pending_task()

            if not current_task:
                self.logger.info("✅ 所有研究任务已完成")
                break

            task_count += 1
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"任务 {task_count}: {current_task}")
            self.logger.info(f"{'='*60}")

            # 2. 执行任务（Micro Agent）
            try:
                result = await self._do_research_task(current_task)
                self.logger.info(f"任务 {task_count} 执行完成")

            except Exception as e:
                self.logger.error(f"任务 {task_count} 执行失败: {e}")
                # 继续下一个任务，不中断整个研究流程
                continue

        # 研究循环结束
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"研究循环完成，共执行 {task_count} 个任务")
        self.logger.info(f"{'='*60}")

    

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

        # 获取 notebook
        notebook = self._get_notebook()
        if not notebook:
            raise ValueError("Notebook 未初始化")

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

        # 使用 _get_research_blueprint_text 获取研究蓝图
        blueprint_text = self._get_research_blueprint_text()

        # 如果是错误，直接返回
        if blueprint_text.startswith("Error:"):
            return f"❌ {blueprint_text}\n\n提示：请先完成研究蓝图的三要素（研究思路、研究计划、章节大纲）后再咨询导师。"

        # 构建咨询提示
        consultation_prompt = f"""{ctx['director_persona']}

现在有一个新的研究任务：
{ctx['research_title']}

研究目的和需求：
{ctx['research_purpose']}

研究员提交了她的研究蓝图和计划方案：

{blueprint_text}

请评估一下是否可以开始，或者有无其他建议，重点评估：
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

请简洁地给出你的反馈。
"""

        try:
            response = await self.brain.think(consultation_prompt)
            advice = response['reply']


            return f"📝 导师反馈如下：\n{advice}"

        except Exception as e:
            return f"❌ 咨询导师失败：{str(e)}"

    @register_action(
        description="创建并保存研究计划任务列表（每行一个任务）",
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

        # 只检查是否为空
        if not task_list:
            return "❌ 任务列表不能为空"

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
        description="制定并保存章节大纲",
        param_infos={
            "outline": "章节大纲多行文本，每行一个章节。例如：第一章 研究背景"
        }
    )
    async def create_chapter_outline(self, outline: str) -> str:
        """
        保存章节大纲

        解析规则：
        - 分行，strip
        - 每行作为一个章节标题
        - 去重：重复的章节只保留第一个

        验证：
        - 至少有一个章节标题
        """
        # 分行并清理
        chapters = []
        seen = set()  # 用于去重

        for line in outline.strip().split('\n'):
            line = line.strip()
            if line and line not in seen:
                chapters.append(line)
                seen.add(line)

        # 验证：至少有一个章节
        if not chapters:
            return """❌ 章节大纲不能为空

提示：
- 每行一个章节标题
- 示例格式：
  第一章 研究背景
  第二章 文献综述
  研究方法
  数据收集"""

        # 在 notebook 中创建章节
        notebook = self._get_notebook()
        if not notebook:
            return "❌ Notebook 未初始化"

        for chapter_name in chapters:
            try:
                notebook.create_chapter(chapter_name)
            except ValueError:
                pass  # 章节已存在

        # 保存到 session context
        await self.update_session_context(chapter_outline=chapters)

        # 格式化显示
        chapters_preview = "\n".join([f"  {ch}" for ch in chapters])

        return f"""✅ 章节大纲已保存，共 {len(chapters)} 个章节：

{chapters_preview}"""

    @register_action(
        description="更新章节大纲。可以提供完整的新章节列表，或者给出具体的修改内容",
        param_infos={
            "new_outline": "（可选）完整的章节列表文本，每行一个章节",
            "modification_advice": "（可选）对现有章节大纲的修改内容"
        }
    )
    async def update_chapter_outline(self,
                                     new_outline: str = "",
                                     modification_advice: str = "") -> str:
        """
        更新章节大纲（智能处理改名和删除）

        处理两种情况：
        1. new_outline 有值 → 直接替换，智能识别改名
        2. modification_advice 有值 → LLM 生成新章节，智能识别改名

        安全保证：
        - 删除章节时，该章节的笔记自动变为"未分类"
        - 改名时，自动更新笔记关联
        - 使用 LLM 判断是改名还是删除
        """
        ctx = self.get_session_context()
        current_chapters = ctx.get("chapter_outline", [])
        new_outline = new_outline.strip()
        modification_advice = modification_advice.strip()
        if not new_outline and not modification_advice:
            return "❌ 请提供完整的章节列表或修改意见"

        # 根据参数获取新章节列表
        if new_outline:
            # 情况1：直接解析新章节列表
            new_chapters = [line.strip() for line in new_outline.strip().split('\n') if line.strip()]
        elif modification_advice:
            # 情况2：LLM 生成新章节列表
            new_chapters = await self._generate_chapters_by_llm(current_chapters, modification_advice)
        else:
            return "❌ 请提供完整的章节列表或修改意见"

        # 识别章节变化
        current_chapters_set = set(current_chapters)
        new_chapters_set = set(new_chapters)

        deleted_chapters = current_chapters_set - new_chapters_set  # 被删除的
        added_chapters = new_chapters_set - current_chapters_set    # 新增的

        # 处理被删除的章节（可能是改名）
        rename_count = 0
        delete_count = 0

        if deleted_chapters:
            # 获取 notebook
            notebook = self._get_notebook()
            if not notebook:
                return "❌ Notebook 未初始化"

            for deleted_chapter in deleted_chapters:
                # 让 LLM 判断是改名还是删除
                judgment = await self._judge_chapter_change(
                    deleted_chapter=deleted_chapter,
                    old_chapters=list(current_chapters_set),
                    new_chapters=list(new_chapters_set)
                )

                if judgment["is_renamed"]:
                    # 判断为改名
                    new_name = judgment["new_name"]

                    # 容错校验：新名称必须在新章节列表里
                    if new_name in new_chapters_set:
                        # ✅ 真的是改名 → 更新笔记关联
                        success = notebook.rename_chapter(deleted_chapter, new_name)
                        if success:
                            rename_count += 1
                        # 如果 rename 失败（章节不存在），也没关系，继续处理
                    else:
                        # ❌ LLM 判断错（新名字不在列表里）→ 当作删除
                        notebook.delete_chapter(deleted_chapter, cascade=False)
                        delete_count += 1
                else:
                    # 判断为删除 → 笔记移到"未分类"
                    notebook.delete_chapter(deleted_chapter, cascade=False)
                    delete_count += 1

        # 保存新章节列表
        await self.update_session_context(chapter_outline=new_chapters)

        # 返回变更摘要
        return "✅ 章节大纲已更新"



    async def _generate_chapters_by_llm(
        self, current_chapters: list, modification_advice: str
    ) -> list:
        """让 LLM 生成新的章节列表"""
        

        
        generate_prompt = f"""你是一个出版编辑，正在为一位作者协助更新章节大纲。

当前的章节大纲：
{current_chapters}

经过讨论大家认为应该对章节组织做如下调整：\n{modification_advice}

请先简要说明你的理解和思考，然后在 `[新章节目录] `下列出新的完整的章节列表，每行一个章节。

输出示范；
```
可选的思考过程...

[新章节目录]
完整的新章节列表，每行一个章节
```

"""

        # 使用 think_with_retry + parser
        new_chapters = await self.brain.think_with_retry(
            generate_prompt,
            self._parse_chapter_list,
            section_headers=["[新章节目录]"]
        )

        return new_chapters

    # ==========================================
    # 更新 Actions（支持研究中动态调整）
    # ==========================================

    @register_action(
        description="更新研究思路和方法。可以提供完整的新的blueprint文本，或者局部修改意见",
        param_infos={
            "new_blueprint": "（可选）完整的研究思路和方法文本",
            "modification_feedback": "（可选）对现有研究思路的修改意见"
        }
    )
    async def update_blueprint(self,
                             new_blueprint: str = "",
                             modification_feedback: str = "") -> str:
        """
        更新研究蓝图概览

        处理两种情况：
        1. new_blueprint 有值 → 直接更新
        2. modification_feedback 有值 → 调用 LLM 生成新版本
        """
        ctx = self.get_session_context()

        if not new_blueprint and not modification_feedback:
            return "❌ 请提供全新的blueprint或修改意见"

        # 情况1：直接更新
        if new_blueprint:
            blueprint = new_blueprint.strip()
            if not blueprint:
                return "❌ Blueprint不能为空"

            await self.update_session_context(blueprint_overview=blueprint)
            return f"✅ 研究思路和方法已更新（{len(blueprint)} 字符）"

        # 情况2：通过修改意见生成新版本
        if modification_feedback:
            current_blueprint = ctx.get("blueprint_overview", "")

            # 构建生成 prompt
            generate_prompt = f"""{ctx['researcher_persona']}

你正在更新研究蓝图。

研究主题：{ctx['research_title']}
研究目的：{ctx['research_purpose']}

当前的研究思路和方法：
{current_blueprint}

导师/你自己的修改意见：
{modification_feedback}

请根据修改意见，生成更新后的研究思路和方法。

请先简要说明你的理解和思考，然后用 "[正式文稿]" 作为分隔符，输出正式的更新后的研究思路和方法。

输出格式：
你的思考过程...

[正式文稿]
更新后的研究思路和方法内容
"""

            try:
                # 使用 think_with_retry + multi_section_parser
                

                result = await self.brain.think_with_retry(
                    generate_prompt,
                    multi_section_parser,
                    section_headers=["[正式文稿]"],
                    match_mode="ALL"
                )

                new_blueprint = result["[正式文稿]"].strip()

                # 更新
                await self.update_session_context(blueprint_overview=new_blueprint)

                return f"✅ 研究思路和方法已更新（{len(new_blueprint)} 字符）"

            except Exception as e:
                return f"❌ 生成新blueprint失败：{str(e)}"

    @register_action(
        description="更新研究计划。可以提供完整的新任务列表替代原有任务计划，或者提供修改意见",
        param_infos={
            "new_plan": "（可选）完整的全新的任务列表文本，每行一个任务",
            "modification_advice": "（可选）对现有计划的修改意见"
        }
    )
    async def update_research_plan(self,
                                  new_plan: str = "",
                                  modification_advice: str = "") -> str:
        """
        更新研究计划（智能合并已完成任务）

        处理两种情况：
        1. new_plan 有值 → 解析并与现有 plan 合并（保留已完成状态）
        2. modification_advice 有值 → 调用 LLM 生成新 plan，然后合并

        合并逻辑：
        - 比较任务内容（字符串匹配）
        - 如果新 plan 中有与现有 plan 相同的任务，保留原状态
        - 新任务默认为 pending
        - 已完成的任务保留
        """
        ctx = self.get_session_context()
        current_plan = ctx.get("research_plan", [])

        if not new_plan and not modification_advice:
            return "❌ 请提供全新的任务列表（每行一个任务）或修改意见"

        # 情况1：直接解析新 plan
        if new_plan:
            # 解析新任务列表
            new_tasks = [
                line.strip()
                for line in new_plan.strip().split('\n')
                if line.strip()
            ]

            if not new_tasks:
                return "❌ 新任务列表不能为空"

            # 合并逻辑
            merged_plan = self._merge_research_plan(current_plan, new_tasks)

            # 保存
            await self.update_session_context(research_plan=merged_plan)

            return "✅ 研究计划已更新"

        # 情况2：通过修改意见生成新 plan
        if modification_advice:
            # 构建当前 plan 的文本描述
            current_plan_text = self._format_plan(current_plan)

            generate_prompt = f"""{ctx['researcher_persona']}

目前正在进行的研究：{ctx['research_title']}

研究目的是：\n{ctx['research_purpose']}

当前的研究计划任务列表：
{current_plan_text}

现在经过和导师的讨论以及你自己的思考，你决定对计划做这样一些修改：：
{modification_advice}

根据这个修改方案，写下新的完整任务列表。

要求：每行一个任务


可以先简要说明你的想法，然后在 `[新计划] `下写下完整的新任务列表，每行一个任务。

输出格式：
```
（可选的）你的想法...

[新计划]
计划任务列表内容，每项一行
已完成任务无需再写
```
"""

            try:
                # 导入 multi_section_parser
                from .parser_utils import multi_section_parser

                # 使用 think_with_retry + multi_section_parser
                sections = await self.brain.think_with_retry(
                    generate_prompt,
                    multi_section_parser,
                    section_headers=["[新计划]"],
                    match_mode="ALL"
                )

                # 提取任务列表
                new_tasks_text = sections["[新计划]"]
                new_tasks = [
                    line.strip()
                    for line in new_tasks_text.split('\n')
                    if line.strip()
                ]

                # 合并逻辑
                merged_plan = self._merge_research_plan(current_plan, new_tasks)

                # 保存
                await self.update_session_context(research_plan=merged_plan)

                return "✅ 研究计划已更新"

            except Exception as e:
                return f"❌ 生成新plan失败：{str(e)}"

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
        notebook = self._get_notebook()
        if not notebook:
            return "❌ Notebook 未初始化"

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
        # 获取 notebook
        notebook = self._get_notebook()
        if not notebook:
            return "错误：Notebook 未初始化"

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
        description="更新当前研究任务的总结。可以提供全新的总结文本，或者提供修改意见",
        param_infos={
            "new_summary": "（可选）全新的任务总结全文",
            "modification_advice": "（可选）对当前总结的修改意见"
        }
    )
    async def update_task_summary(self,
                                  new_summary: str = "",
                                  modification_advice: str = "") -> str:
        """
        更新当前研究任务的总结

        处理两种情况：
        1. new_summary 有值 → 直接替换当前任务的 summary
        2. modification_advice 有值 → LLM 基于当前 summary 生成新版本

        用途：
        - 记录研究发现
        - 追踪关键信息
        - 为后续任务提供参考
        """
        ctx = self.get_session_context()
        current_plan = ctx.get("research_plan", [])

        if not current_plan:
            return "❌ 研究计划不存在"

        # 获取当前任务（从 transient context）
        current_task = self.get_transient("current_research_task")
        if not current_task:
            return "❌ 没有正在执行的任务"

        # 找到当前任务在 plan 中的索引
        task_index = None
        for i, task in enumerate(current_plan):
            if task["content"] == current_task and task["status"] == "pending":
                task_index = i
                break

        if task_index is None:
            return f"❌ 未找到当前任务：{current_task}"

        # 情况1：直接替换
        if new_summary:
            current_plan[task_index]["summary"] = new_summary.strip()
            # 保存
            await self.update_session_context(research_plan=current_plan)

            return f"✅ 任务总结已更新（{len(new_summary.strip())} 字符）"

        # 情况2：通过修改意见生成新版本
        if modification_advice:
            current_summary = current_plan[task_index].get("summary", "")

            generate_prompt = f"""你是研究员，正在更新任务总结。

当前任务：{current_task}

当前的任务总结：
{current_summary if current_summary else "（暂无总结）"}

修改意见：{modification_advice}

请根据修改意见，生成更新后的任务总结。

要求：
1. 保持客观、准确
2. 包含关键发现和结论
3. 提及重要的信息来源

请先简要说明你的理解和思考，然后用 [新总结] 作为分隔符，
在分隔符后输出新的任务总结。

输出格式：
```
你的思考过程...

[新总结]
更新后的任务总结内容
```
"""

            try:
                # 导入 multi_section_parser
                from .parser_utils import multi_section_parser

                # 使用 think_with_retry + multi_section_parser
                sections = await self.brain.think_with_retry(
                    generate_prompt,
                    multi_section_parser,
                    section_headers=["[新总结]"],
                    match_mode="ALL"
                )

                # 提取新总结
                new_summary_text = sections["[新总结]"].strip()

                # 更新
                current_plan[task_index]["summary"] = new_summary_text

                # 保存
                await self.update_session_context(research_plan=current_plan)

                return f"✅ 任务总结已更新（{len(new_summary_text)} 字符）"

            except Exception as e:
                return f"❌ 生成新总结失败：{str(e)}"

        return "❌ 请提供全新的总结文本或修改意见"

    @register_action(
        description="查看指定任务的总结内容",
        param_infos={
            "task_content": "要查看的任务内容"
        }
    )
    async def check_task_summary(self, task_content: str) -> str:
        """
        查看指定任务的总结

        Args:
            task_content: 任务内容

        Returns:
            任务的总结内容
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        if not plan:
            return "❌ 研究计划不存在"

        # 查找任务
        for task in plan:
            if task["content"] == task_content:
                summary = task.get("summary", "")
                status = task.get("status", "pending")

                if not summary:
                    return f"任务「{task_content}」暂无总结（状态：{status}）"

                return f"""任务「{task_content}」的总结：

状态：{status}

{summary}
"""

        return f"❌ 未找到任务：{task_content}"

    # ==========================================
    # 辅助方法
    # ==========================================

    def _format_plan(self, plan: list, indent: str = "  ") -> str:
        """
        格式化任务列表（不带 emoji）

        - pending 任务：只显示内容
        - 其他状态：显示 "内容 (状态)"

        参数:
            plan: 任务列表
            indent: 缩进字符串（默认 "  "，传入 "" 无缩进）

        返回:
            格式化的任务列表文本
        """
        lines = []
        for task in plan:
            content = task["content"]
            status = task.get("status", "pending")

            if status == "pending":
                lines.append(f"{indent}{content}")
            else:
                lines.append(f"{indent}{content} ({status})")

        return "\n".join(lines)

    def _get_progress_summary(self, plan: list) -> str:
        """获取进度摘要"""
        total = len(plan)
        completed = sum(1 for t in plan if t["status"] == "completed")
        pending = total - completed

        pct = (completed / total * 100) if total > 0 else 0

        return f"📊 进度：{completed}/{total} ({pct:.1f}%) | ✅ 已完成 {completed} | ⏳ 待进行 {pending}"

    def _get_notebook(self) -> Optional[Notebook]:
        """
        获取当前 session 的 notebook 对象

        Returns:
            Notebook: notebook 对象，如果不存在返回 None
        """
        notebook = self.get_transient("notebook")
        if not notebook:
            self.logger.warning("Notebook not found in transient context")
        return notebook

    def _get_research_blueprint_text(self) -> str:
        """
        提取当前研究计划和状态的文本

        整合研究蓝图的三个要素：
        1. blueprint_overview - 研究思路和方法
        2. research_plan - 研究计划（带状态）
        3. chapter_outline - 章节大纲

        返回：
        - 如果缺少要素：返回 "Error: 具体缺了什么内容"
        - 如果齐全：返回格式化的研究蓝图文本
        """
        ctx = self.get_session_context()

        # 检查三个要素是否存在
        missing_elements = []

        if not ctx.get("blueprint_overview"):
            missing_elements.append("研究思路和方法 (blueprint_overview)")

        if not ctx.get("research_plan"):
            missing_elements.append("研究计划 (research_plan)")

        if not ctx.get("chapter_outline"):
            missing_elements.append("章节大纲 (chapter_outline)")

        # 如果有缺失，返回错误
        if missing_elements:
            return f"Error: 缺少 {', '.join(missing_elements)}"

        # 三个要素都齐全，构建文本
        parts = []

        # 1. 研究思路和方法
        parts.append("[研究思路和方法]")
        parts.append(ctx["blueprint_overview"])
        parts.append("")

        # 2. 研究计划（带状态）
        parts.append("[研究计划]")
        plan = ctx["research_plan"]
        plan_text = self._format_plan(plan, indent="")
        parts.append(plan_text)
        parts.append("")

        # 3. 章节大纲
        parts.append("[章节大纲]")
        for chapter in ctx["chapter_outline"]:
            parts.append(chapter)

        return "\n".join(parts)

    def _get_next_pending_task(self) -> Optional[str]:
        """
        获取下一个待进行的任务

        Returns:
            str: 下一个 pending 任务的内容，如果没有则返回 None
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        for task in plan:
            if task.get("status") == "pending":
                return task["content"]

        return None

    def _format_research_plan_with_summary(self, plan: list) -> str:
        """
        格式化研究计划（包含任务总结）

        参数:
            plan: 任务列表

        返回:
            格式化的任务列表文本（包含总结）
        """
        lines = []
        for i, task in enumerate(plan, 1):
            content = task["content"]
            status = task.get("status", "pending")
            summary = task.get("summary", "")

            if status == "pending":
                lines.append(f"{i}. ⏳ {content}")
            else:
                lines.append(f"{i}. ✅ {content}")

            # 如果有总结，添加总结内容
            if summary:
                # 缩进显示总结
                summary_lines = summary.split('\n')
                lines.append(f"   📝 总结：")
                for line in summary_lines[:3]:  # 只显示前3行
                    lines.append(f"      {line}")
                if len(summary_lines) > 3:
                    lines.append(f"      ...（共 {len(summary_lines)} 行）")
            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def _get_completed_task_summaries(self) -> str:
        """
        获取所有已完成任务的总结

        Returns:
            str: 格式化的已完成任务总结
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        completed_tasks = [
            task for task in plan
            if task.get("status") == "completed" and task.get("summary")
        ]

        if not completed_tasks:
            return "（暂无已完成的任务总结）"

        lines = []
        for i, task in enumerate(completed_tasks, 1):
            lines.append(f"任务{i}: {task['content']}")
            lines.append(f"总结：{task['summary']}")
            lines.append("")

        return "\n".join(lines)

    async def _mark_task_completed(self, task_content: str):
        """
        标记任务为已完成

        Args:
            task_content: 任务内容
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        # 找到任务并标记为 completed
        for task in plan:
            if task["content"] == task_content and task["status"] == "pending":
                task["status"] = "completed"
                break

        # 保存
        await self.update_session_context(research_plan=plan)
        self.logger.debug(f"✅ 标记任务完成：{task_content}")

    def _normalize_task_text(self, task_text: str) -> str:
        """
        清理任务文本，去除末尾的状态标记

        支持的模式：
        - 任务A（已完成）
        - 任务B (completed)
        - 任务C（finished）
        - 任务D (失败)

        参数:
            task_text: 原始任务文本

        返回:
            清理后的任务文本（去除状态标记）
        """
        import re

        # 匹配末尾的括号内容（支持半角和全角括号）
        # 模式：最末尾的 (任意内容) 或 （任意内容）
        pattern = r'[\(（].*?[\)）]$'

        # 去除末尾的状态标记
        cleaned = re.sub(pattern, '', task_text.strip())

        return cleaned.strip()

    def _merge_research_plan(self, current_plan: list, new_tasks: list) -> list:
        """
        合并新旧研究计划，保留已完成任务的状态

        合并逻辑：
        1. 保留所有已完成的任务
        2. 对于新任务列表：
           - 如果与当前 plan 中的任务内容相同（使用清理后的文本比较），保留原状态
           - 如果是新任务，状态为 pending

        智能匹配：
        - 清理任务文本末尾的状态标记（如"（已完成）"、"(completed)"等）
        - 使用清理后的文本进行任务匹配
        - 避免因状态信息导致的匹配失败
        """
        # 构建当前 plan 的映射：清理后的文本 -> (原始内容, 状态)
        current_task_map = {}
        for task in current_plan:
            original_content = task["content"]
            normalized_content = self._normalize_task_text(original_content)
            current_task_map[normalized_content] = {
                "original": original_content,
                "status": task["status"]
            }

        # 构建新 plan
        new_plan = []

        # 1. 先保留所有已完成的任务（使用原始内容）
        for task in current_plan:
            if task["status"] == "completed":
                new_plan.append(task)

        # 2. 处理新任务列表
        seen = set()  # 避免重复（使用清理后的文本）
        for task_content in new_tasks:
            # 清理新任务文本
            normalized_content = self._normalize_task_text(task_content)

            if normalized_content in seen:
                continue
            seen.add(normalized_content)

            # 检查是否在当前 plan 中（使用清理后的文本匹配）
            if normalized_content in current_task_map:
                old_task_info = current_task_map[normalized_content]
                old_status = old_task_info["status"]

                # 如果已完成，前面已经添加过了，跳过
                if old_status == "completed":
                    continue

                # 其他状态，保留原状态（使用清理后的文本，避免状态信息累积）
                new_plan.append({
                    "content": normalized_content,
                    "status": old_status
                })
            else:
                # 新任务，状态为 pending（使用清理后的文本）
                new_plan.append({
                    "content": normalized_content,
                    "status": "pending"
                })

        return new_plan

    def _parse_chapter_list(self, raw_reply: str, section_headers: list) -> dict:
        """
        解析章节大纲（用于 think_with_retry）

        使用 multi_section_parser 提取指定 section，然后解析章节

        Args:
            raw_reply: LLM 的原始回复
            section_headers: 要提取的 section header 列表（如 ["[新章节目录]"]）

        Returns:
            {
                "status": "success" | "error",
                "content": List[str]  # 章节列表
                "feedback": str  # 错误信息
            }
        """

        # 1. 先用 multi_section_parser 提取
        result = multi_section_parser(
            raw_reply,
            section_headers=section_headers,
            match_mode="ALL"
        )

        if result["status"] == "error":
            return result

        # 2. 从第一个 section 中提取章节文本
        # section_headers 是一个列表，取第一个作为目标 section
        target_section = section_headers[0]
        chapters_text = result["content"][target_section]

        chapters = [
            line.strip()
            for line in chapters_text.split('\n')
            if line.strip()
        ]

        # 3. 验证：至少有一个章节
        if len(chapters) < 1:
            return {
                "status": "error",
                "feedback": "章节大纲不能为空，请至少提供一个章节"
            }

        return {
            "status": "success",
            "content": chapters
        }

    def _parse_rename_judgment(self, raw_reply: str) -> dict:
        """
        解析 LLM 对章节变更的判断（改名 vs 删除）

        期望格式：
        - 改名：[RENAMED]\n新名称：xxx
        - 删除：[DELETED]

        Returns:
            {
                "status": "success" | "error",
                "content": {
                    "is_renamed": bool,
                    "new_name": str or None
                },
                "feedback": str  # 错误信息
            }
        """
        lines = raw_reply.strip().split('\n')

        # 检查是否有 [RENAMED] 或 [DELETED]
        if "[RENAMED]" in raw_reply:
            # 提取新名称
            for line in lines:
                line = line.strip()
                if line.startswith("新名称：") or line.startswith("新名称:"):
                    new_name = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                    return {
                        "status": "success",
                        "content": {
                            "is_renamed": True,
                            "new_name": new_name
                        }
                    }

            # 如果格式不对，返回错误
            return {
                "status": "error",
                "feedback": "检测到 [RENAMED] 标记，但未找到新名称。请使用格式：[RENAMED]\\n新名称：xxx"
            }

        elif "[DELETED]" in raw_reply:
            return {
                "status": "success",
                "content": {
                    "is_renamed": False,
                    "new_name": None
                }
            }

        else:
            return {
                "status": "error",
                "feedback": "请明确判断是 [RENAMED]（改名）还是 [DELETED]（删除）。使用相应的标记。"
            }

    async def _judge_chapter_change(
        self,
        deleted_chapter: str,
        old_chapters: list,
        new_chapters: list
    ) -> dict:
        """
        判断被删除的章节是改名还是删除

        Args:
            deleted_chapter: 被删除的章节名（如 "第2章 实验方法"）
            old_chapters: 原来的完整章节列表
            new_chapters: 新的完整章节列表

        Returns:
            {
                "is_renamed": bool,      # True=改名, False=删除
                "new_name": str or None   # 如果是改名，新名称是什么
            }
        """
        # 格式化章节列表用于显示
        old_chapters_text = "\n".join(old_chapters)
        new_chapters_text = "\n".join(new_chapters)

        prompt = f"""你是章节变更判断专家。

原来的章节列表：
{old_chapters_text}

新的章节列表：
{new_chapters_text}

请判断：被删除的章节 "{deleted_chapter}"

是以下哪种情况？
1. **改名**：只是改了名称，但实质内容没变（比如 "第2章 实验方法" → "第2章 实验设计"）
2. **删除**：真的删除了这个章节

请按以下格式回答：

如果改名了：
[RENAMED]
新名称：xxx

如果删除了：
[DELETED]
"""

        result = await self.brain.think_with_retry(
            prompt,
            self._parse_rename_judgment,
            max_retries=3
        )

        return result

