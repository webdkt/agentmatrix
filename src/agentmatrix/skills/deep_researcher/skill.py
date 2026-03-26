"""
Deep Researcher Skill - 深度研究协调者

三个 phase actions：
- do_planning:  创建 Planning MicroAgent 完成规划
- do_research:  创建 Research MicroAgent 完成研究
- do_writing:   创建 Writing MicroAgent 完成写作

子 MicroAgent 使用 deep_researcher_helper skill（take_note, write_chapter_draft, polish_chapter, assemble_report）。

阶段转换由子 MicroAgent 通过 prompt 指令直接写 phase.md 文件完成。
"""

from pathlib import Path
from ...core.action import register_action
from ...agents.micro_agent import MicroAgent
from .helpers import (
    read_work_file, write_work_file,
    format_prompt, persona_parser,
)
from .prompts import ResearchPrompts

# 读取文件系统规范
_FS_SPEC_PATH = Path(__file__).parent / "filesystem_spec.md"
_FILESYSTEM_SPEC = _FS_SPEC_PATH.read_text(encoding="utf-8")


class Deep_researcherSkillMixin:
    """Deep Researcher 深度研究协调者"""

    _skill_description = "深度研究技能，对指定主题进行深度研究并生成完整报告"
    _skill_dependencies = ["simple_web_search"]

    def _get_work_dir(self) -> str:
        task_id = self.root_agent.current_task_id or "default"
        return str(self.root_agent.runtime.paths.get_agent_work_files_dir(
            self.root_agent.name, task_id
        ))

    def _read_file(self, rel_path: str) -> str:
        return read_work_file(self._get_work_dir(), rel_path)

    def _write_file(self, rel_path: str, content: str) -> None:
        write_work_file(self._get_work_dir(), rel_path, content)

    # ==========================================
    # Phase actions
    # ==========================================

    @register_action(
        short_desc="规划研究（写清楚研究的标题，和研究目的需求描述）",
        description="执行研究规划阶段。制定研究计划、章节大纲。完成后进入 research 阶段。",
        param_infos={
            "research_title": "研究的标题（简短描述）",
            "research_purpose": "研究的目的和需求"
        }
    )
    async def do_planning(self, research_title: str, research_purpose: str) -> str:
        work_dir = Path(self._get_work_dir())
        state_dir = work_dir / "research_state"

        # 初始化或恢复
        if state_dir.exists() and self._read_file("research_state/phase.md").strip():
            phase = self._read_file("research_state/phase.md").strip()
            if phase == "done":
                return "研究已完成，报告在 /work_files/final_report.md"
            self.logger.info(f"恢复研究，当前阶段: {phase}")
        else:
            state_dir.mkdir(parents=True, exist_ok=True)
            (work_dir / "notebook").mkdir(parents=True, exist_ok=True)
            (work_dir / "drafts").mkdir(parents=True, exist_ok=True)
            self._write_file("research_state/phase.md", "planning")
            self._write_file("research_state/research_title.md", research_title)
            self._write_file("research_state/research_purpose.md", research_purpose)

        # 生成人设（如果还没有）
        if not self._read_file("research_state/personas.md"):
            await self._generate_personas(research_title, research_purpose)

        personas = self._read_file("research_state/personas.md")
        researcher_persona = self._extract_persona(personas, "Researcher")

        self._write_file("research_state/phase.md", "planning")
        self.logger.info("进入规划阶段")

        planner = MicroAgent(
            parent=self.root_agent,
            name="ResearchPlanner",
            available_skills=["simple_web_search"]
        )

        planning_task = f"""
{_FILESYSTEM_SPEC}

你正在为 [{research_title}] 项目制定研究蓝图。

研究目的：{research_purpose}

你需要完成以下工作：

1. 探索主题：用 web_search 搜索相关信息，了解研究背景
2. 制定研究蓝图：用 write 写入 research_state/blueprint_overview.md
3. 制定研究任务列表：用 write 写入 research_state/research_plan.md，格式参见上方 File Formats 中 research_plan.md 的约定
4. 制定章节大纲：用 write 写入 research_state/chapter_outline.md，格式参见上方 File Formats 中 chapter_outline.md 的约定

可以用 consult_with_director 咨询导师建议。

当规划完成后：
- 把 research_state/phase.md 的内容改为 research（用 write action）
- 然后调用 all_finished 结束
"""
        await planner.execute(
            run_label="planning",
            persona=researcher_persona,
            task=planning_task,
            max_steps=20
        )

        return "规划阶段执行完毕"

    @register_action(
        short_desc="执行研究",
        description="执行研究阶段。逐个完成研究任务，搜索资料、记笔记。完成后自动进入 writing 阶段。",
        param_infos={}
    )
    async def do_research(self) -> str:
        personas = self._read_file("research_state/personas.md") or ""
        researcher_persona = self._extract_persona(personas, "Researcher")
        plan_text = self._read_file("research_state/research_plan.md") or ""
        overall_summary = self._read_file("research_state/research_overall_summary.md") or "无"
        chapter_outline = self._read_file("research_state/chapter_outline.md") or ""

        # 提取有效章节名
        chapters = []
        for line in chapter_outline.strip().split('\n'):
            line = line.strip()
            if line.startswith('# '):
                chapters.append(line[2:].strip())
        chapters_hint = "、".join(chapters) if chapters else "（未定义）"

        self._write_file("research_state/phase.md", "research")
        self.logger.info("进入研究阶段")

        researcher = MicroAgent(
            parent=self.root_agent,
            name="Researcher",
            available_skills=["simple_web_search", "deep_researcher_helper"]
        )

        research_task = f"""
{_FILESYSTEM_SPEC}

你是一个深度研究员。你的任务是逐个完成研究计划中的所有任务。

研究计划：
{plan_text}

整体总结：{overall_summary}

有效章节名: {chapters_hint}

工作流程：
1. 用 read 读取 research_plan.md 找到第一个 [pending] 的任务
2. 搜索资料（web_search），记笔记（take_note），把重要内容记录到 notebook/ 下对应的章节文件
3. 如果研究充分，编辑 research_plan.md 把当前任务的 [pending] 改为 [completed]
   并把下一个 [pending] 改为 [in_progress]（用 replace_string_in_file 或 write 覆写整个文件）
   状态值域：pending | in_progress | completed
4. 继续下一个 pending 任务
5. 所有任务完成后，用 write 把 research_state/phase.md 改为 writing，然后调用 all_finished 结束

重要：
- 好记性不如烂笔头，务必勤记笔记（take_note）
- take_note 的 chapter_name 参数使用上面的有效章节名
- 每完成一个重要任务，用 write 更新 research_state/research_overall_summary.md
- 可以用 read 读取 research_state/chapter_outline.md 查看当前章节列表
- 可以用 consult_with_director 向导师请教
"""
        await researcher.execute(
            run_label="research",
            persona=researcher_persona,
            task=research_task,
            max_steps=50
        )

        return "研究阶段执行完毕"

    @register_action(
        short_desc="执行写作",
        description="执行写作阶段。根据研究笔记撰写报告各章节，组装最终报告。完成后自动标记 done。",
        param_infos={}
    )
    async def do_writing(self) -> str:
        title = self._read_file("research_state/research_title.md").strip()
        personas = self._read_file("research_state/personas.md") or ""
        researcher_persona = self._extract_persona(personas, "Researcher")
        outline = self._read_file("research_state/chapter_outline.md") or ""

        self._write_file("research_state/phase.md", "writing")
        self.logger.info("进入写作阶段")

        writer = MicroAgent(
            parent=self.root_agent,
            name="ReportWriter",
            available_skills=["deep_researcher_helper"]
        )

        writing_task = f"""
{_FILESYSTEM_SPEC}

请根据收集的研究笔记撰写完整的研究报告。

研究主题：{title}

章节大纲：
{outline}

工作流程：
1. 用 read 读取章节大纲，了解需要撰写的章节（格式：每行一个 # 章节标题）
2. 逐章撰写草稿（write_chapter_draft），草稿保存到 drafts/{chapter_name}.md
3. 逐章润色（polish_chapter）
4. 所有章节完成后，调用 assemble_report 组装最终报告，报告保存为 final_report.md
"""
        await writer.execute(
            run_label="writing",
            persona=researcher_persona,
            task=writing_task,
            max_steps=100
        )

        return "写作阶段执行完毕"

    # ==========================================
    # 工具方法
    # ==========================================

    async def _generate_personas(self, title: str, purpose: str):
        """生成 Director 和 Researcher 人设"""
        director_prompt = format_prompt(
            ResearchPrompts.DIRECTOR_PERSONA_DESIGNER,
            {"research_title": title, "research_purpose": purpose}
        )
        director_persona = await self.root_agent.brain.think_with_retry(
            director_prompt,
            persona_parser,
            header="[正式文稿]"
        )

        researcher_prompt = format_prompt(
            ResearchPrompts.RESEARCHER_PERSONA_DESIGNER,
            {"research_title": title, "research_purpose": purpose},
            director_persona=director_persona
        )
        researcher_persona = await self.root_agent.brain.think_with_retry(
            researcher_prompt,
            persona_parser,
            header="[正式文稿]"
        )

        personas_content = f"## Director Persona\n{director_persona}\n\n## Researcher Persona\n{researcher_persona}\n"
        self._write_file("research_state/personas.md", personas_content)
        self.logger.info("人设生成完成")

    def _extract_persona(self, personas_text: str, role: str) -> str:
        """从 personas.md 中提取指定角色的人设"""
        if not personas_text:
            return ""

        import re
        pattern = rf"## {role} Persona\s*\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, personas_text, re.DOTALL)
        if match:
            return match.group(1).strip()

        return personas_text
