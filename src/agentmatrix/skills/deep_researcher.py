"!!! 过时待删除或者重做 !!!"
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
from ..agents.micro_agent import MicroAgent
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
            "research_purpose": "研究的目的"
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
            research_overall_summary="",  # 项目整体总结（初始化为空）
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
            persona_parser,
            header="[正式文稿]"
        )

        # 生成研究员人设
        researcher_prompt = format_prompt(
            DeepResearcherPrompts.RESEARCHER_PERSONA_DESIGNER, ctx, director_persona=director_persona
        )
        researcher_persona = await self.brain.think_with_retry(
            researcher_prompt,
            persona_parser,
            header="[正式文稿]"
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
            你正在为 [{research_title}] 项目制定研究蓝图。

            研究目的：{research_purpose}

            研究蓝图包含三个部分：
            1. 研究想法和整体思路
            2. 研究任务列表，列出明确研究的步骤和顺序
            3. 章节大纲，规划报告的结构

            开始制定研究蓝图吧！注意，研究任务不需要包括报告编写工作，研究工作完成后会单独处理报告撰写。目前只需要完成研究蓝图的制定，不需要开始实际研究。
            """,
            ctx
        )

        # 执行 Micro Agent
        try:
            # 直接创建 MicroAgent
            micro_agent = MicroAgent(parent=self)
            result = await micro_agent.execute(
                run_label="planning_stage",
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

    async def _do_research_task(self, task_content: str, max_steps: int = 30, max_time: float = 30.0) -> str:
        """
        执行单个研究任务（可能多轮短会话）

        Args:
            task_content: 任务内容
            max_steps: 每轮最大步数（可选，默认 30）
            max_time: 每轮最大时间（分钟）（可选，默认 30.0）

        Returns:
            执行结果（最后一轮的结果）
        """
        self.logger.info(f"📌 开始执行任务：{task_content}")

        # 保存当前任务到 transient context
        self.set_transient("current_research_task", task_content)

        ctx = self.get_session_context()

        # 任务级别的循环（多轮短会话）
        round_count = 0
        while True:
            round_count += 1
            self.logger.info(f"\n--- 第 {round_count} 轮 ---")

            # 执行一轮
            try:
                # 获取当前任务的总结
                current_task_data = self._find_task_by_content(task_content)
                current_summary = current_task_data.get("summary", "") if current_task_data else ""

                # 获取项目整体总结
                overall_summary = ctx.get("research_overall_summary", "")

                # 获取研究蓝图文本
                blueprint_text = self._get_research_blueprint_text()

                # 构建 Micro Agent 任务描述
                research_task_prompt = f"""

目前进行的研究：
{blueprint_text}

【项目整体纪要】
{overall_summary if overall_summary else "（暂无项目整体总结）"}

**【当前任务】**：{task_content}

【当前任务纪要】
{current_summary if current_summary else "（暂无任务总结）"}

请充分思考后工作。如果发现无法完成该任务，就简短总结说明原因并保存，然后结束任务。
重要：
- 好记性不如烂笔头，请务必勤记笔记，不写下来的东西，都不会被记得。
- 尽管现在只做研究不写报告，但如果有任何局部草稿、腹稿或者打算写进最终版本的内容，务必记笔记，Again, 不写下来的东西，都不会被记得
- 纪要也只是现在记得，如果有任何内容是对将来写报告有用的，不能只更新纪要，必须记笔记。
笔记是一切
"""

                # 创建独立的子上下文用于这个研究任务
                task_name = f"task_{sanitize_filename(task_content[:50])}"
                task_context = self.working_context.create_child(task_name, use_timestamp=True)

                # 执行 Micro Agent
                micro_agent = MicroAgent(parent=self, working_context=task_context)
                result = await micro_agent.execute(
                    persona=ctx['researcher_persona'],
                    task=research_task_prompt,
                    available_actions=[
                        "web_search",
                        "take_note",
                        "update_task_summary",
                        "update_research_overall_summary",
                        "check_task_summary",
                        "update_research_plan",
                        "update_chapter_outline",
                        "all_finished",
                        "visit_url"
                    ],
                    max_steps=max_steps,
                    max_time=max_time,
                    run_label=f"research_round_{round_count}"  # 执行标签
                )

                # 检查任务状态
                task_data = self._find_task_by_content(task_content)

                if not task_data:
                    self.logger.warning(f"❌ 找不到任务数据：{task_content}")
                    break

                # 退出条件1: LLM 主动完成任务
                if task_data["status"] == "completed":
                    self.logger.info(f"✅ 任务「{task_content}」已完成（LLM 主动调用 all_finished）")
                    break

                # 退出条件2: 正常完成（非"未完成"消息）
                if isinstance(result, str) and not result.startswith("未完成"):
                    self.logger.info(f"✅ 任务「{task_content}」正常完成")
                    # 主动设置状态（如果还没设置）
                    if task_data["status"] == "pending":
                        await self._update_task_status(task_content, "completed")
                    break

                # 否则：达到限制，继续下一轮
                self.logger.info(f"⏸ 第 {round_count} 轮结束：{result}")
                self.logger.info(f"⏳ 继续下一轮...")

            except Exception as e:
                self.logger.error(f"❌ 第 {round_count} 轮执行失败: {e}")
                # 失败时标记为失败状态
                await self._update_task_status(task_content, "failed")
                break

        self.logger.info(f"✅ 任务执行完成（共 {round_count} 轮）")
        return result

    async def _research_loop(self):
        """
        新的研究循环 - 任务驱动模式

        工作流程：
        1. 循环获取下一个 pending 任务
        2. 调用 _do_research_task 执行任务（内部支持多轮短会话）
        3. 继续下一个任务，直到所有任务完成
        """
        self.logger.info("🔍 进入研究循环")

        task_count = 0
        while True:
            # 获取下一个 pending 任务（返回完整的任务数据）
            current_task_data = self._get_next_pending_task()

            if not current_task_data:
                self.logger.info("✅ 所有研究任务已完成")
                break

            current_task = current_task_data["content"]  # 提取任务内容
            task_count += 1
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"任务 {task_count}: {current_task}")
            self.logger.info(f"{'='*60}")

            # 执行任务（内部会处理多轮短会话）
            try:
                await self._do_research_task(current_task)
                self.logger.info(f"✅ 任务 {task_count} 执行完成")

            except Exception as e:
                self.logger.error(f"❌ 任务 {task_count} 执行失败: {e}")
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
        新的报告撰写循环 - 双层循环架构

        步骤1: 将章节大纲转换为 Markdown heading 格式
        步骤2: 为每个一级章节生成草稿文件
        步骤3: 双层循环 - 逐个 summary 更新章节草稿
        """
        self.logger.info("✍️ 进入新的报告撰写循环")

        ctx = self.get_session_context()
        notebook = self._get_notebook()
        if not notebook:
            raise ValueError("Notebook 未初始化")

        # 步骤1: 转换章节大纲为 Markdown heading 格式
        chapter_heading_map = await self._convert_outline_to_headings(ctx["chapter_outline"])

        # 步骤2: 为每个一级章节生成草稿文件
        draft_folder = await self._create_chapter_drafts(
            ctx["chapter_outline"],
            chapter_heading_map
        )

        # 步骤3: 双层循环 - 逐个 summary 更新章节草稿
        await self._drafting_loop(
            ctx,
            notebook,
            chapter_heading_map,
            draft_folder
        )

        # 汇总完整报告
        report_path = await self._assemble_final_report(
            ctx,
            chapter_heading_map,
            draft_folder
        )

        return str(report_path)

    async def _convert_outline_to_headings(self, chapter_outline: list) -> dict:
        """
        步骤1: 将章节大纲转换为 Markdown heading 格式

        Args:
            chapter_outline: 原始章节列表 (如 ["第一章 研究背景", "第二章 文献综述"])

        Returns:
            dict: mapping {原章节名: Markdown heading}
                  (如 {"第一章 研究背景": "# 第一章 研究背景"})
        """
        self.logger.info("📝 步骤1: 转换章节大纲为 Markdown heading 格式")

        ctx = self.get_session_context()

        # 构建转换 prompt
        outline_text = "\n".join(chapter_outline)

        prompt = f"""
你是编辑助理，正在为一项研究报告整理章节大纲。

当前章节大纲（非 Markdown 格式）：
{outline_text}

请将上述章节大纲转换为 Markdown heading 格式。

要求：
1. 一级章节使用 "# " (heading 1)
2. 如果有子章节，使用对应的heading等级（"## "、"### " 等）
3. 保持章节的层次结构
4. 章节名称保持不变，只添加 Markdown 标记

可以先简要说明你的理解，然后用 [MARKDOWN_OUTLINE] 作为分隔符，在分隔符后输出 Markdown 格式的章节大纲。

输出示例：
```
（可选的思考过程）

[MARKDOWN_OUTLINE]
# 第一章 研究背景
## 1.1 研究意义
# 第二章 文献综述
## 2.1 国内研究现状
## 2.2 国外研究现状
```
"""

        # 定义 parser
        def parse_markdown_outline(raw_reply: str, section_headers: list = None) -> dict:
            """解析并验证 Markdown 格式的章节大纲"""
            from .parser_utils import multi_section_parser

            if section_headers is None:
                section_headers = ["[MARKDOWN_OUTLINE]"]

            # 提取 Markdown outline
            result = multi_section_parser(
                raw_reply,
                section_headers=section_headers,
                match_mode="ALL"
            )

            if result["status"] == "error":
                return result

            markdown_outline = result["content"]["[MARKDOWN_OUTLINE]"].strip()
            markdown_lines = [line.strip() for line in markdown_outline.split('\n') if line.strip()]

            # 行数检查
            if len(markdown_lines) != len(chapter_outline):
                return {
                    "status": "error",
                    "feedback": f"行数不匹配，不要增加或者删除章节，不要改变章节内容"
                }

            # 逐行验证
            mapping = {}
            def clean_hash(text: str) -> str:
                while text.startswith('#'):
                    text = text[1:].lstrip()
                return text.strip()

            for original, markdown in zip(chapter_outline, markdown_lines):
                cleaned_original = clean_hash(original)
                cleaned_markdown = clean_hash(markdown)

                # 检查是否是合法的 markdown heading
                if not markdown.startswith('#'):
                    return {
                        "status": "error",
                        "feedback": f"章节「{original}」转换后不是合法的 Markdown heading：{markdown}"
                    }

                # 内容是否一致
                if cleaned_original != cleaned_markdown:
                    return {
                        "status": "error",
                        "feedback": f"章节「{original}」转换错误，不要修改内容"
                    }

                mapping[original] = markdown

            return {"status": "success", "content": mapping}

        # 使用 think_with_retry 进行转换
        try:
            chapter_heading_map = await self.brain.think_with_retry(
                prompt,
                parse_markdown_outline,
                section_headers=["[MARKDOWN_OUTLINE]"],
                max_retries=3
            )

            self.logger.info(f"✓ 章节大纲已转换为 Markdown 格式（{len(chapter_heading_map)} 个章节）")

            # 打印章节映射，用于调试
            self.logger.info(f"📋 章节映射关系：")
            for chapter_name, heading in chapter_heading_map.items():
                self.logger.info(f"  {heading:40s} <- {chapter_name}")

            return chapter_heading_map

        except Exception as e:
            self.logger.error(f"章节大纲转换失败: {e}")
            raise

    async def _create_chapter_drafts(
        self,
        chapter_outline: list,
        chapter_heading_map: dict
    ) -> str:
        """
        步骤2: 为每个一级章节生成草稿文件

        Args:
            chapter_outline: 原始章节列表
            chapter_heading_map: {原章节名: Markdown heading} 映射

        Returns:
            str: draft 文件夹路径
        """
        self.logger.info("📁 步骤2: 为每个章节生成草稿文件")

        from pathlib import Path

        # 创建 draft 目录
        session_folder = self.get_session_folder()
        draft_folder = Path(session_folder) / "draft"
        draft_folder.mkdir(parents=True, exist_ok=True)

        # 为每个一级章节生成草稿文件
        top_level_count = 0
        for original_chapter_name, markdown_heading in chapter_heading_map.items():
            # 只处理一级章节（# 开头但不是 ##）
            if not (markdown_heading.startswith('# ') and not markdown_heading.startswith('##')):
                continue

            top_level_count += 1

            # 生成文件名（先清洗章节名，再加扩展名）
            filename = sanitize_filename(original_chapter_name) + ".md"
            draft_file = draft_folder / filename

            # 初始化草稿内容：包含章节 heading
            draft_content = f"{markdown_heading}\n\n"

            # 保存草稿文件
            with open(draft_file, 'w', encoding='utf-8') as f:
                f.write(draft_content)

            self.logger.info(f"✓ 创建草稿文件: {draft_file.name}")

        self.logger.info(f"✓ 所有草稿文件已创建在 {draft_folder}（{top_level_count} 个一级章节）")

        return str(draft_folder)

    def _get_child_chapters(self, top_level_chapter_name: str, chapter_heading_map: dict) -> list:
        """
        获取某个一级章节的所有子章节

        利用 chapter_heading_map 的顺序和 markdown heading 层级：
        - 遇到 # 开头 → 新的一级章节
        - 之后遇到 ## 开头的 → 都是它的子章节
        - 直到遇到下一个 # 开头 → 停止

        Args:
            top_level_chapter_name: 一级章节名称
            chapter_heading_map: {章节名: markdown heading} 映射

        Returns:
            list: 子章节名称列表
        """
        children = []
        found_parent = False

        for chapter_name, heading in chapter_heading_map.items():
            # 找到目标父章节
            if chapter_name == top_level_chapter_name:
                found_parent = True
                continue

            # 如果已经找到父章节
            if found_parent:
                # 遇到下一个一级章节（# 开头但不是 ##），停止
                if heading.startswith('# ') and not heading.startswith('##'):
                    break
                # 否则就是子章节
                children.append(chapter_name)

        return children

    def _get_chapter_materials(
        self,
        notebook: 'Notebook',
        chapter_name: str,
        chapter_heading_map: dict,
        batch_size: int = 3
    ) -> list:
        """
        获取章节相关的所有素材（原始 notes）

        包括：
        1. 该章节本身（一级章节）的 notes
        2. 该章节所有子章节的 notes
        3. 未分类的 notes

        Args:
            notebook: Notebook 对象
            chapter_name: 一级章节名称
            chapter_heading_map: {章节名: markdown heading} 映射
            batch_size: 每批 notes 数量（默认 3）

        Returns:
            list: 素材列表，每个元素是字符串（合并后的 notes）
        """
        materials = []

        # 1. 获取该一级章节的所有子章节
        child_chapters = self._get_child_chapters(chapter_name, chapter_heading_map)

        # 2. 收集所有相关章节的 notes（父章节 + 子章节）
        all_related_chapters = [chapter_name] + child_chapters

        self.logger.info(f"  章节相关子章节: {child_chapters}")

        all_notes = []
        for related_chapter in all_related_chapters:
            chapter_notes = notebook.get_notes_by_chapter(related_chapter)
            all_notes.extend(chapter_notes)

        # 3. 获取未分类的原始 notes
        uncategorized_notes = notebook.get_notes_by_chapter(notebook.UNCATEGORIZED_NAME)
        all_notes.extend(uncategorized_notes)

        # 4. 按 batch_size 分批（每批 3 个 notes）
        for i in range(0, len(all_notes), batch_size):
            batch = all_notes[i:i + batch_size]
            # 将这个批次的 notes 合并为一个文本
            batch_text = "\n\n".join([f"- {note.content}" for note in batch])
            materials.append(batch_text)

        return materials

    async def _drafting_loop(
        self,
        ctx: dict,
        notebook: 'Notebook',
        chapter_heading_map: dict,
        draft_folder: str
    ):
        """
        步骤3: 双层循环 - 逐个 summary 更新章节草稿

        外层循环: 遍历每个 chapter
        内层循环: 遍历该 chapter 相关的素材（summaries + 未分类笔记）

        Args:
            ctx: session context
            notebook: Notebook 对象
            chapter_heading_map: {原章节名: Markdown heading} 映射
            draft_folder: draft 文件夹路径
        """
        self.logger.info("🔄 步骤3: 开始双层循环更新草稿")

        from pathlib import Path

        # 外层循环：遍历每个一级章节
        for original_chapter_name, markdown_heading in chapter_heading_map.items():
            # 只处理一级章节（# 开头但不是 ##）
            if not (markdown_heading.startswith('# ') and not markdown_heading.startswith('##')):
                continue

            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"开始撰写章节: {original_chapter_name}")
            self.logger.info(f"{'='*60}")

            # 获取草稿文件路径（先清洗章节名，再加扩展名）
            filename = sanitize_filename(original_chapter_name) + ".md"
            draft_file = Path(draft_folder) / filename

            # 获取该章节相关的所有素材（包括子章节）
            materials = self._get_chapter_materials(notebook, original_chapter_name, chapter_heading_map)

            if not materials:
                self.logger.warning(f"章节 '{original_chapter_name}' 没有相关笔记素材，跳过")
                continue

            self.logger.info(f"找到 {len(materials)} 个素材（原始笔记）")

            # 内层循环：逐个素材更新草稿
            for idx, material_content in enumerate(materials, 1):
                is_first = (idx == 1)
                is_last = (idx == len(materials))
                is_only = (len(materials) == 1)

                if is_first:
                    self.logger.info(f"  [{idx}/{len(materials)}] 第一笔：建立章节框架...")
                elif is_last:
                    self.logger.info(f"  [{idx}/{len(materials)}] 最后一笔：最终完善...")
                else:
                    self.logger.info(f"  [{idx}/{len(materials)}] 中间迭代：补充细节...")

                # 重试循环：处理 LLM 异常
                retry_count = 0
                while True:
                    try:
                        # 读取当前草稿
                        with open(draft_file, 'r', encoding='utf-8') as f:
                            current_draft = f.read()

                        # 使用 think_with_retry 更新草稿
                        task_prompt = self._build_draft_update_task(
                            ctx,
                            original_chapter_name,
                            markdown_heading,
                            current_draft,
                            material_content,
                            is_first=is_first,
                            is_only=is_only
                        )

                        # 使用 simple_section_parser 提取 [新草稿] 后的内容
                        from .parser_utils import simple_section_parser

                        updated_draft = await self.brain.think_with_retry(
                            task_prompt,
                            simple_section_parser,
                            section_header="[新草稿]",
                            max_retries=3
                        )

                        # 保存更新后的草稿
                        with open(draft_file, 'w', encoding='utf-8') as f:
                            f.write(updated_draft)

                        self.logger.info(f"  ✓ 草稿已更新")
                        break  # 成功，跳出重试循环

                    except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                        retry_count += 1

                        # 判断异常类型
                        if isinstance(e, (asyncio.TimeoutError, asyncio.CancelledError)):
                            error_type = "超时/取消"
                        else:
                            error_type = "未知错误"

                        self.logger.error(f"  ✗ LLM 调用失败 ({error_type}, 第 {retry_count} 次): {str(e)[:200]}")

                        if retry_count >= 10:  # 最多重试10次
                            self.logger.error(f"  ✗ 达到最大重试次数，跳过该素材")
                            break

                        # 等待 5 分钟后重试
                        self.logger.info(f"  ⏳ 等待 5 分钟后重试...")
                        import asyncio
                        await asyncio.sleep(300)  # 300 秒 = 5 分钟
                        self.logger.info(f"  🔄 第 {retry_count + 1} 次重试...")

            self.logger.info(f"✓ 章节 '{original_chapter_name}' 撰写完成")

        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"所有章节撰写完成")
        self.logger.info(f"{'='*60}")

    def _build_draft_update_task(
        self,
        ctx: dict,
        original_chapter_name: str,
        markdown_heading: str,
        current_draft: str,
        material_content: str,
        is_first: bool = False,
        is_only: bool = False
    ) -> str:
        """
        构建草稿更新任务的 prompt

        Args:
            ctx: session context
            original_chapter_name: 原始章节名
            markdown_heading: Markdown heading
            current_draft: 当前草稿内容
            material_content: 当前素材内容
            is_first: 是否是第一次编写（建立框架）
            is_only: 是否是唯一素材（直接写完整）

        Returns:
            str: 任务 prompt
        """
        # 获取完整章节目录
        chapter_outline = ctx.get("chapter_outline", [])
        chapter_list = "\n".join([f"{i+1}. {ch}" for i, ch in enumerate(chapter_outline)])

        # 根据不同情况构建不同的 prompt
        if is_only:
            # 情况1：唯一素材 - 直接写完整
            task_instruction = """
这是本章节的唯一素材，请直接撰写完整的章节内容。

要求：
1. **完整性**：基于这个素材，尽可能完整地撰写章节
2. **结构清晰**：使用合适的子标题组织内容
3. **具体详实**：尽可能详细地展开论述
4. **保持 Markdown 格式**：确保输出是有效的 Markdown 格式
"""

        elif is_first:
            # 情况2：第一次编写（后续还有素材）- 建立框架
            task_instruction = """
这是本章节的第一笔素材。请先建立章节的整体框架，不要追求细节。

要求：
1. **建立框架**：列出章节应该包含的主要内容和结构
2. **使用子标题**：用 ## 标记各个子部分
3. **列出要点**：在每个子标题下，用 - 或 * 列出关键要点
4. **不要展开**：暂时不要详细展开，保持简洁
5. **留有空间**：用 [TODO: 需要补充xxx] 标记后续需要填充的部分
6. **保持 Markdown 格式**：确保输出是有效的 Markdown 格式

类似这样：
## 子主题1
- 要点1
- 要点2
[TODO: 需要补充具体数据]

## 子主题2
- 要点1
- 要点2
"""

        else:
            # 情况3：后续轮次 - 整合新素材
            task_instruction = """
这是新的研究笔记素材，请将其中有用的信息整合到当前草稿中。

要求：
1. **整体把握**：了解整篇文章的结构和当前章节的位置，确保内容深度合适
2. **保持结构**：保持当前的章节结构（heading 格式）
3. **补充内容**：将新素材中有用的信息融入到草稿的合适位置
4. **逻辑连贯**：确保新增内容与现有内容逻辑连贯
5. **填充 TODO**：如果新素材可以补充之前的 [TODO]，请填充并去掉标记
6. **避免重复**：如果素材内容已在草稿中，就跳过或做适当补充
7. **修正错误**：如果新素材中有更正之前草稿的内容，请修正草稿中的错误信息
8. **仔细甄别**：如果素材内容与当前章节关联不大，请不要强行添加，保持章节的聚焦和清晰
8. **保持 Markdown 格式**：确保输出是有效的 Markdown 格式
"""

        prompt = f"""
你是 {ctx['researcher_persona']}，正在为一项关于 {ctx['research_title']} 的研究撰写报告。

研究目的：
{ctx['research_purpose']}

报告章节目录：
{chapter_list}

当前正在撰写章节：{original_chapter_name}

当前草稿内容：
```
{current_draft}
```

新的研究笔记素材：
{material_content}

{task_instruction}

请先简要说明你的思路，然后用 [新草稿] 作为分隔符，在分隔符后输出更新后的完整草稿（包含 {markdown_heading} heading）。

输出格式：
```
（可选的思考过程）

[新草稿]
# 章节标题
更新后的完整草稿内容...
```
"""

        return prompt

    async def _assemble_final_report(
        self,
        ctx: dict,
        chapter_heading_map: dict,
        draft_folder: str
    ) -> str:
        """
        汇总所有章节草稿为完整报告

        Args:
            ctx: session context
            chapter_heading_map: {原章节名: Markdown heading} 映射
            draft_folder: draft 文件夹路径

        Returns:
            str: 最终报告文件路径
        """
        self.logger.info("📄 汇总完整报告")

        from pathlib import Path

        # 读取所有章节草稿
        draft_folder_path = Path(draft_folder)
        chapter_contents = []

        for original_chapter_name, markdown_heading in chapter_heading_map.items():
            filename = sanitize_filename(original_chapter_name) + ".md"
            draft_file = draft_folder_path / filename

            with open(draft_file, 'r', encoding='utf-8') as f:
                content = f.read()
                chapter_contents.append(content)

        # 汇总完整报告
        full_report = f"# {ctx['research_title']}\n\n"
        full_report += f"## 研究目的\n\n{ctx['research_purpose']}\n\n"
        full_report += "---\n\n"
        full_report += "\n\n".join(chapter_contents)

        # 保存最终报告
        from pathlib import Path
        session_folder = self.get_session_folder()
        report_path = Path(session_folder) / f"{sanitize_filename(ctx['research_title'])}_report.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(full_report)

        self.logger.info(f"✓ 最终报告已保存: {report_path}")

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
        description="制定并保存章节大纲，每行一个一级章节（不要包含子章节）,只写出章节标题，不要多余描述",
        param_infos={
            "outline": "章节大纲多行文本，每行一个一级章节。注意：只能是一级章节，不要包含子章节。例如：第一章 研究背景"
        }
    )
    async def create_chapter_outline(self, outline: str) -> str:
        """
        保存章节大纲（仅支持一级章节）

        解析规则：
        - 分行，strip
        - 每行作为一个章节标题
        - 去重：重复的章节只保留第一个
        - 重要：只支持一级章节，不要包含子章节（如 1.1、1.2 等）

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
            - 只能是一级章节，不要包含子章节
            - 示例格式：
            第一章 研究背景
            第二章 文献综述
            第三章 研究方法
            第四章 数据分析"""

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
        description="更新章节大纲（只能是一级章节）。可以提供完整的新章节列表，或者给出具体的修改内容",
        param_infos={
            "new_outline": "（可选）完整的章节列表文本，每行一个一级章节。注意：不要包含子章节",
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
        

        
        generate_prompt = f"""你是一个出版编辑，正在协助一位作者更新章节大纲。

            当前的章节大纲：
            {current_chapters}

            经过讨论大家认为应该对章节组织做如下调整：\n{modification_advice}

            **重要：只能是一级章节，不要包含子章节（如 1.1、1.2 等）**

            请先简要说明你的理解和思考，然后在 `[新章节目录] `下列出新的完整的章节列表，每行一个一级章节。

            输出示范；
            ```
            可选的思考过程...

            [新章节目录]
            第一章 研究背景
            第二章 文献综述
            第三章 研究方法
            完整的新章节列表，每行一个一级章节
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
            generate_prompt = f"""你是 {ctx['researcher_persona']}

            目前正在进行一个研究，研究主题：{ctx['research_title']}。 研究目的：{ctx['research_purpose']}

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
        description="更新全局计划。可以提供完整的新任务列表替代原有任务计划，或者提供修改意见。",
        param_infos={
            "new_plan": "（可选）完整的全局任务列表文本，每行一个任务。",
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

            generate_prompt = f"""
你是 {ctx['researcher_persona']}。
目前正在进行的研究：{ctx['research_title']}

研究目的是：\n{ctx['research_purpose']}

当前的研究计划任务列表：
=== begin of plan ===
{current_plan_text}
=== end of plan ===

现在经过和导师的讨论以及你自己的思考，你决定对计划做这样一些修改：：
== begin of modification advice ===
{modification_advice}
== end of modification advice ===

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
        description="用番茄笔记法记笔记，记录有价值的、可能对报告写作有帮助的信息。记住：任何没记录的信息在写作的时候都不会记得，好记性不如烂笔头。如果笔记属于某个章节，就提供章节名称。如果有来源信息（例如url），最好一并提供。",
        param_infos={
            "note": "笔记内容",
            "url": "来源URL",
            "chapter_name": "（可选）关联的章节名称"
        }
    )
    async def take_note(self, note: str, url: str = "", chapter_name: str = "") -> str:
        """
        记录笔记到笔记本（支持智能章节匹配）

        Args:
            note: 笔记内容
            url: 来源 URL（可选）
            chapter_name: 章节名称（可选），会自动匹配到 chapter_outline

        Returns:
            str: 记录结果
        """
        notebook = self._get_notebook()
        if not notebook:
            return "❌ Notebook 未初始化"

        # 如果没有指定章节，添加到"未分类"
        if not chapter_name or not chapter_name.strip():
            notebook.add_note(note, notebook.UNCATEGORIZED_NAME, url=url if url else None)
            return f"✓ 笔记已记录到「{notebook.UNCATEGORIZED_NAME}」"

        # 智能解析章节名称（返回列表，可能包含多个章节）
        resolved_chapters = await self._resolve_chapter_names(chapter_name)

        # 为每个章节添加笔记
        for chapter in resolved_chapters:
            notebook.add_note(note, chapter, url=url if url else None)

        # 返回结果
        if len(resolved_chapters) == 1:
            return f"✓ 笔记已记录到「{resolved_chapters[0]}」"
        else:
            chapters_str = "、".join(resolved_chapters)
            return f"✓ 笔记已记录到多个章节：{chapters_str}"

    async def _resolve_chapter_names(self, chapter_name: str) -> list:
        """
        智能解析章节名称（支持多章节）

        三级匹配策略：
        1. 完全匹配
        2. 局部匹配（字符串包含关系）
        3. LLM 智能匹配（可返回多个章节）

        Args:
            chapter_name: 原始章节名称

        Returns:
            list: 解析后的章节名称列表（一定在 chapter_outline 中）
        """
        ctx = self.get_session_context()
        chapter_outline = ctx.get("chapter_outline", [])

        if not chapter_outline:
            # 没有章节大纲，返回"未分类"
            return [Notebook.UNCATEGORIZED_NAME]

        # Level 1: 完全匹配
        if chapter_name in chapter_outline:
            return [chapter_name]

        # Level 2: 局部匹配（字符串包含关系）
        for outline_chapter in chapter_outline:
            if chapter_name in outline_chapter or outline_chapter in chapter_name:
                self.logger.debug(f"局部匹配：'{chapter_name}' -> '{outline_chapter}'")
                return [outline_chapter]

        # Level 3: LLM 智能匹配（可返回多个章节）
        return await self._find_matching_chapters_by_llm(chapter_name, chapter_outline)

    async def _find_matching_chapters_by_llm(self, chapter_name: str, chapter_outline: list) -> list:
        """
        使用 LLM 智能匹配章节名称（支持多章节）

        Args:
            chapter_name: 原始章节名称
            chapter_outline: 章节大纲列表

        Returns:
            list: 匹配的章节名称列表，找不到则返回 ["未分类"]
        """
        ctx = self.get_session_context()

        # 构建匹配 prompt
        outline_list = "\n".join([f"{i+1}. {ch}" for i, ch in enumerate(chapter_outline)])

        prompt = f"""
你是秘书在帮导师整理笔记。

笔记被要求按下面的最新的章节大纲来归类：
====beingn of outline====
{outline_list}
====end of outline====

现在有一条旧笔记，写着应该属于：{chapter_name}

请判断这个旧的章节名称应该对应新大纲中的哪个/哪些章节？

**重要**：
1. 如果能找到明确对应的章节，返回章节名称（如果是多个，每行一个）
2. 如果找不到明确对应的章节，返回"{Notebook.UNCATEGORIZED_NAME}"
3. 在[匹配结果]下输出你的选择

输出样例：
```
（可选）你的想法

[匹配结果]
你的选择的章节名称，每行一个
如果没有匹配的章节，写"{Notebook.UNCATEGORIZED_NAME}"
```
"""

        try:
            # 使用 multi_section_parser 提取多行章节名
            from .parser_utils import multi_section_parser

            sections = await self.brain.think_with_retry(
                prompt,
                multi_section_parser,
                section_headers=["[匹配结果]"],
                match_mode="ANY",
                return_list=True,
                
            )

            # sections 是一个 dict: {"[匹配结果]": ["第一章 研究背景", "第二章 文献综述"]}
            matched_chapters = sections.get("[匹配结果]", [])

            # 验证返回的章节是否都在 outline 中
            validated_chapters = []
            for ch in matched_chapters:
                if ch in chapter_outline:
                    validated_chapters.append(ch)
                else:
                    self.logger.warning(f"LLM 返回的章节 '{ch}' 不在章节大纲中，已忽略")

            # 如果验证后没有有效章节，返回"未分类"
            if not validated_chapters:
                self.logger.warning(f"LLM 未找到有效章节，归类为未分类")
                return [Notebook.UNCATEGORIZED_NAME]

            self.logger.debug(f"LLM 章节匹配：'{chapter_name}' -> {validated_chapters}")
            return validated_chapters

        except Exception as e:
            self.logger.warning(f"LLM 章节匹配失败: {e}，归类为未分类")
            return [Notebook.UNCATEGORIZED_NAME]


    

    # ==========================================
    # 研究计划管理 Actions（任务驱动模式）
    # ==========================================

    @register_action(
        description="标记任务为已完成（需要提供任务的具体名字）",
        param_infos={
            "task_content": "要标记为已完成的任务名字"
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
        description="更新研究计划的内容（不是状态）：提供新的任务列表文本（每行一个任务），将替换当前所有未完成的任务（已完成的任务会保留）",
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
        description="随时对当前进行的工作进行一些总结，帮助自己记录当前工作项的进展和状态（不是记录知识点，知识点是记到笔记本的），可以提供全新的总结文本，或者对现有总结的修改意见",
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
            plan_txt = self._format_plan(current_plan, indent="")
            generate_prompt = f"""
你是 {ctx['researcher_persona']},正在进行一项研究工作。

[当前研究主题]：
{ctx['research_title']}
[研究目的]：
{ctx['research_purpose']}

[研究计划任务列表]：

{plan_txt}

[当前进行的任务]：

{current_task}

[当前的任务总结]：
{current_summary if current_summary else "（暂无总结）"}

[总结修改意见]：
{modification_advice}
====END OF SUMMARY====

请根据修改意见，生成更新后的任务总结。

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
        description="更新项目总结，记录对整个研究生命周期都有重要价值的关键信息和状态，用于跨任务的知识传递和全局进度把握，保持一页纸长度",
        param_infos={
            "new_summary": "（可选）全新的项目总结全文",
            "modification_advice": "（可选）对现有项目总结的修改意见"
        }
    )
    async def update_research_overall_summary(
        self,
        new_summary: str = "",
        modification_advice: str = ""
    ) -> str:
        """
        更新项目整体总结

        功能：
        - 记录整个研究的关键发现、方向调整、重要进展
        - 帮助 LLM 在不同任务间保持上下文连贯性
        - 提供项目级别的"工作记忆"

        处理两种情况：
        1. new_summary 有值 → 直接替换
        2. modification_advice 有值 → LLM 基于当前总结生成新版本
        """
        ctx = self.get_session_context()
        current_overall_summary = ctx.get("research_overall_summary", "")

        if not new_summary and not modification_advice:
            return "❌ 请提供全新的项目总结文本或修改意见"

        # 情况1：直接替换
        if new_summary:
            overall_summary = new_summary.strip()
            if not overall_summary:
                return "❌ 项目总结不能为空"

            # 保存到 session context
            await self.update_session_context(research_overall_summary=overall_summary)

            return f"✅ 项目整体总结已更新（{len(overall_summary)} 字符）"

        # 情况2：通过修改意见生成新版本
        if modification_advice:
            if not current_overall_summary:
                return "❌ 当前没有项目总结，请使用 new_summary 参数创建新总结"

            # 获取研究计划（作为参考）
            plan = ctx.get("research_plan", [])
            plan_txt = self._format_plan(plan, indent="") if plan else "（暂无研究计划）"

            generate_prompt = f"""
你是 {ctx['researcher_persona']},正在进行一项研究工作。

[当前研究主题]：
{ctx['research_title']}

[研究目的]：
{ctx['research_purpose']}

[研究计划任务列表]：
{plan_txt}

[当前的项目整体总结]：
{current_overall_summary}

[总结修改意见]：
{modification_advice}
====END OF SUMMARY====

请根据修改意见，生成更新后的项目整体总结。

项目整体总结的作用：
- 记录整个研究的关键发现、方向调整、重要进展
- 帮助后续任务快速了解项目背景和当前状态
- 提供项目级别的"工作记忆"

请先简要说明你的理解和思考，然后用 [新总结] 作为分隔符，
在分隔符后输出新的项目整体总结。

输出格式：
```
你的思考过程...

[新总结]
更新后的项目整体总结内容
```
"""

            try:
                # 使用 think_with_retry + multi_section_parser
                sections = await self.brain.think_with_retry(
                    generate_prompt,
                    multi_section_parser,
                    section_headers=["[新总结]"],
                    match_mode="ALL"
                )

                # 提取新总结
                new_overall_summary = sections["[新总结]"].strip()

                # 更新
                await self.update_session_context(research_overall_summary=new_overall_summary)

                return f"✅ 项目整体总结已更新（{len(new_overall_summary)} 字符）"

            except Exception as e:
                return f"❌ 生成新项目总结失败：{str(e)}"

        return "❌ 请提供全新的总结文本或修改意见"

    @register_action(
        description="查看某个已完成任务的总结，要指明是看哪个任务",
        param_infos={
            "task_name": "要查看的任务内容"
        }
    )
    async def check_task_summary(self, task_name: str) -> str:
        """
        查看指定任务的总结

        Args:
            task_name: 任务内容

        Returns:
            任务的总结内容
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        if not plan:
            return "❌ 研究计划不存在"

        # 使用通用方法查找任务
        task_data = self._find_task_by_content(task_name)

        if not task_data:
            formatted_plan = self._format_plan(plan)
            return f"❌ 未找到你说的任务：{task_name}\n\n当前研究计划：\n{formatted_plan}"

        summary = task_data.get("summary", "")
        status = task_data.get("status", "pending")

        if not summary:
            return f"任务「{task_name}」暂无总结（状态：{status}）"

        return f"""任务「{task_name}」的总结：

                状态：{status}

                {summary}
                """

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

    def _get_next_pending_task(self) -> Optional[dict]:
        """
        获取下一个待进行的任务

        Returns:
            dict: 下一个 pending 任务的完整数据，如果没有则返回 None
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        for task in plan:
            if task.get("status") == "pending":
                return task

        return None

    def _find_task_by_content(self, task_content: str) -> Optional[dict]:
        """
        通过任务内容查找任务（通用方法）

        Args:
            task_content: 任务内容

        Returns:
            dict: 找到的任务数据，找不到返回 None
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        for task in plan:
            if task["content"] == task_content:
                return task

        return None

    async def _update_task_status(self, task_content: str, new_status: str) -> bool:
        """
        更新任务状态（通用方法）

        Args:
            task_content: 任务内容
            new_status: 新状态（"pending", "completed"）

        Returns:
            bool: 是否更新成功
        """
        ctx = self.get_session_context()
        plan = ctx.get("research_plan", [])

        for task in plan:
            if task["content"] == task_content:
                task["status"] = new_status
                await self.update_session_context(research_plan=plan)
                return True

        return False

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
        标记任务为已完成（使用通用方法）

        Args:
            task_content: 任务内容
        """
        success = await self._update_task_status(task_content, "completed")
        if success:
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

        prompt = f"""你是经验老道的编辑。正在整理一份资料的章节变动情况。

原版本的章节列表：
{old_chapters_text}

新版本的章节列表：
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

    # ==========================================
    # 覆盖 BaseAgent 的 all_finished
    # ==========================================

    @register_action(
        description="完成当前研究任务并标记为已完成",
        param_infos={
            "result": "任务结果描述（可选）",
            "task_name": "要标记为完成的任务名称（可选，默认当前任务）"
        }
    )
    async def all_finished(self, result: str = None, task_name: str = None) -> str:
        """
        完成研究任务（覆盖 BaseAgent.all_finished）

        功能：
        - 标记指定任务为 completed
        - 返回任务完成消息

        Args:
            result: 任务结果描述（可选）
            task_name: 要标记为完成的任务名称（可选，默认当前任务）

        Returns:
            str: 任务完成消息
        """
        # 1. 获取当前任务（从 transient context）
        current_task = self.get_transient("current_research_task")

        # 2. 确定要完成的任务
        task_to_complete = task_name or current_task

        if not task_to_complete:
            return "❌ 无法确定要完成的任务"

        # 3. 标记为 completed
        await self._mark_task_completed(task_to_complete)

        # 4. 记录日志
        self.logger.info(f"✅ 任务「{task_to_complete}」已标记为完成")

        # 5. 返回结果
        if result:
            return f"✅ 任务「{task_to_complete}」已完成：{result}"
        else:
            return f"✅ 任务「{task_to_complete}」已完成"

