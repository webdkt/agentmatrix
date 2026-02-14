"""
DeepResearcher - Deep Research Agent

A specialized research agent that uses flag files (research_blueprint.md, research_report.md)
to drive workflow phases: Planner → Researcher → Writer.

Features:
- Flag-file driven phase detection
- Fixed 30-minute rounds with multi-round looping
- Supplement mode: preserves research_report.md after user feedback
- History preservation: keeps all 00_*.md flag files as research trail
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Optional, Callable, List, Any
from ..core.message import Email
from ..core.events import AgentEvent
from ..core.action import register_action
from ..core.session_manager import SessionManager
from ..core.session_context import SessionContext
import traceback
from dataclasses import asdict
import inspect
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
import logging
from pathlib import Path
from .micro_agent import MicroAgent

from agentmatrix.agents.base import BaseAgent
from agentmatrix.core.working_context import WorkingContext
from agentmatrix.skills.browser_use_skill import BrowserUseSkillMixin
from agentmatrix.skills.file_operations_skill import FileOperationSkillMixin


class DeepResearcher(BaseAgent, BrowserUseSkillMixin, FileOperationSkillMixin):
    """
    Deep Research Agent

    A specialized research agent that uses flag files to drive research phases:
    - research_blueprint.md (Planner phase)
    - research_report.md (Writer phase)

    Workflow:
        No flags → Planner: create research_blueprint.md
        Has blueprint → Researcher: deep research, create research_report.md
        Has report → Writer: synthesize and write final report

    Features:
    - Flag-file driven: phase detection based on file existence
    - 30-minute rounds: each MicroAgent run is limited to 30 minutes
    - Multi-round looping: continues until user stops or max_rounds reached
    - Supplement mode: user feedback preserves research_report.md for intelligent appending
    - History preservation: all 00_*.md flag files are kept as research trail
    """

    system_prompt = """# 你是谁
你是深度研究员，擅长自主探索、分析和综合信息。

## 核心特征
1. **记忆力限制**：每轮研究只能记住当前轮的内容，轮次之间会"遗忘"
2. **笔记强迫**：因此必须养成"随手记录"的习惯
3. **白板依赖**：最重要的信息必须写在白板上（research_report.md），否则会丢失
4. **阶段演进**：通过标志文件切换研究阶段

## 你的工作方式
- **Planner 阶段**：制定研究蓝图（research_blueprint.md）
  - 理解研究目标
  - 规划 5-7 个步骤
  - 确定 3-5 个研究主题
  - 创建初始 research_blueprint.md

- **Researcher 阶段**：深入研究和信息收集
  - 基于 research_blueprint.md 执行研究
  - 为每个主题创建 topics/topic_XX.md 笔记
  - 收集数据、分析、记录发现
  - 创建 research_report.md 标志研究完成

- **Writer 阶段**：综合撰写最终报告
  - 阅读 topics/topic_XX.md 所有笔记
  - 提取关键发现
  - 撰写 research_report.md 最终报告
  - 报告回答了原始研究目标

## 退出条件
只有满足以下**任一**条件时，调用 all_finished() 结束研究：
1. **完成**：所有计划的主题都已深入分析
2. **用户要求**：用户通过邮件明确要求停止
3. **达到上限**：完成配置的最大轮次（默认100轮）

创建标志文件后，研究任务立即进入下一阶段。
"""

    async def process_email(self, email: Email):
        """
        处理邮件 = 恢复记忆 + 执行 + 保存记忆

        覆盖默认的think-act 循环
        """
        # 1. Session Management (Routing)
        self.logger.debug(f"New Email")
        self.logger.debug(str(email))
        session = await self.session_manager.get_session(email)
        self.current_session = session
        self.current_user_session_id = session["user_session_id"]

        # 更新 working_context（指向 private_workspace）
        self._update_working_context()

        # 创建 SessionContext 对象（包装 session["context"]）
        self._session_context = SessionContext(
            persistent=True,
            session_manager=self.session_manager,
            session=session,
            initial_data=session.get("context", {})
        )

        # 设置当前 session 目录
        self.current_session_folder = str(
                Path(self.workspace_root) /
                session["user_session_id"] /
                "history" /
                self.name /
                session["session_id"]
            )

        # 2. 准备参数
        task = str(email)

        # 3. 准备 available actions
        # 如果配置了 top_level_actions，则使用配置 + 默认 actions
        # 否则使用所有 actions（向后兼容）
        available_actions = self._get_available_actions()

        '''TODO:
        这里要改写默认的BaseAgent的简单逻辑（启动Micro Agent运行）
        基本逻辑是，
        - 首先，探测当前阶段标志，根据不同的阶段，注入不同的persona 给Micro Agent
        - 然后Micro Agent的execute不是完成即停止，而是在一个always true 的循环里
        - 因为Micro Agent的execute是一个LLM对话不断增长的过程，时间太长context会爆
        - 通过分段执行的方式，控制每次会话的长度，达到context不爆的目的
        - 但是，每次执行都是新的会话，所以必须保持信息的连贯性，让LLM知道必要的信息，才能让整个过程在"语义"上连续的，工作是连贯的。
        - 这通过几个方式：
          - 采用类似web_searcher_v2.py里的prompt设计，督促LLM及时的记笔记、更新白板。相当于维护自己的记忆
          - 这样的好处是，LLM自我维护，自我总结，而不是硬性的根据长度来压缩
          - 但是在execute的过程中，会一直进行LLM输出和执行action的循环，所以我们除了最长时间和最大步数的限制之外，还可以设置一个特殊的"take a break" 动作，
            通过prompt暗示LLM工作有一定进展，在不同任务之间，总是要take a break, 这样会导致主动退出当前的execute循环，回到外层的while循环里，
            take break 的前置条件（也是通过prompt约束暗示）是该总结记录的都总结记录了，能让LLM安心的"休息"了，才会触发take a break, 这样就能保证每次循环都有实质性的进展，而不是单纯的时间到了就打断，导致信息丢失。
            并且，这次我们不再调用的时候设置一个硬性的时间必然退出，而是通过每次返回的时候都加上一些暗示："距离预定休息时间还有多久"，
            给LLM施加心理影响，促使他尽早主动选择退出，而不是被动的被时间打断，这样就能最大程度的保证信息的连贯性和完整性。
        - 另外，在这个双层循环中（外层always true 循环，内层是Micro Agent自己的execute内部的_run_loop循环）。每次回到外层循环
          都要检查（1）阶段标志，决定要注入什么prompt（2）如果是因为调用了rest_n_wait（不是take a break), 那说明是
          要等用户输入，那就退出整个外层循环。


        '''
        # === 初始化循环变量 ===
        round_count = 1
        start_time = time.time()

        # === 外层循环：多轮执行 ===
        while True:
            # 计算已用时间（分钟）
            total_time = (time.time() - start_time) / 60.0

            # 1. 检测当前阶段
            phase = await self._detect_phase()

            # 2. 构建 persona（根据阶段和轮次）
            persona = await self._get_persona(
                phase=phase,
                round_count=round_count,
                total_time=total_time
            )

            # 3. 构建任务描述（包含时间、轮次、工作区状态）
            task_prompt = await self._build_task_prompt(
                phase=phase,
                round_count=round_count,
                total_time=total_time
            )

            # 日志：当前轮次信息
            self.logger.info(f"🔄 Round {round_count} - Phase: {phase.upper()} - Total time: {total_time:.1f}m")

            # 4. 创建新的 ResearchMicroAgent（每轮都是新实例）
            micro_core = ResearchMicroAgent(
                parent=self,
                working_context=self._working_context,  # 传入最新的 working_context
                name=f"{self.name}_round{round_count}"
            )

            # 5. 准备干净的 session（清空历史，保留元数据）
            clean_session = self._create_clean_session(session)

            # 6. 执行 MicroAgent
            result = await micro_core.execute(
                run_label=f'Round {round_count} - {phase}',
                persona=persona,
                task=task_prompt,
                available_actions=available_actions,
                session=clean_session,  # ← 传递干净的 session
                session_manager=self.session_manager,  # ← 传递 session_manager
                yellow_pages=self.post_office.yellow_page_exclude_me(self.name),
                exit_actions=["rest_n_wait", "take_a_break", "all_finished"]
            )

            # 7. 更新轮次计数
            round_count += 1

            # 8. 检查退出条件
            last_action = micro_core.last_action_name
            self.logger.info(f"🔚 MicroAgent finished with action: {last_action}")

            if last_action in ["rest_n_wait", "all_finished"]:
                # 正常退出：保存 session（下次用户发邮件时继续）
                self.logger.info(f"💾 Saving session and exiting outer loop (action: {last_action})")
                await self.session_manager.save_session(session)

                if last_action == "all_finished":
                    # 更新最后发送者
                    session["last_sender"] = self.name

                # 退出外层循环，等待用户输入
                break
            elif last_action == "take_a_break":
                # 主动休息：不保存 session history，继续下一轮
                self.logger.info(f"☕ MicroAgent requested break - continuing to next round")
                # 不保存 session，直接继续下一轮
                continue
            else:
                # 其他退出条件（超时、错误等）
                self.logger.warning(f"⚠ MicroAgent exited unexpectedly: {last_action}")
                # 保存 session 并退出
                await self.session_manager.save_session(session)
                break



        

    async def _detect_phase(self) -> str:
        """
        Detect current research phase by checking flag files

        Priority: Writer (has report.md) > Researcher (has blueprint.md) > Planner

        Returns:
            'planner' | 'researcher' | 'writer'
        """
        report_path = self.private_workspace / "research_report.md"
        blueprint_path = self.private_workspace / "research_blueprint.md"

        if report_path.exists():
            self.logger.info("📝 Phase detected: WRITER (research_report.md exists)")
            return "writer"
        elif blueprint_path.exists():
            self.logger.info("📝 Phase detected: RESEARCHER (research_blueprint.md exists)")
            return "researcher"
        else:
            self.logger.info("📝 Phase detected: PLANNER (no flags found)")
            return "planner"

    async def _build_round_persona(
        self,
        round_count: int,
        total_time: float,
        phase: str
    ) -> str:
        """
        Build persona for current round based on detected phase

        Args:
            round_count: Current round number
            total_time: Total time spent so far (minutes)
            phase: Current phase ('planner' | 'researcher' | 'writer')

        Returns:
            Complete persona string with phase-specific guidance
        """

        if phase == "planner":
            return await self._build_planner_persona(round_count)
        elif phase == "researcher":
            return await self._build_researcher_persona(round_count, total_time)
        elif phase == "writer":
            return await self._build_writer_persona(round_count, total_time)
        else:
            # Fallback
            return self.system_prompt

    async def _build_planner_persona(self, round_count: int) -> str:
        """
        Build Planner persona for creating research blueprint
        """
        #TODO: 写的很差，要重写
        return f"""{self.system_prompt}

## 当前阶段：研究规划师

【本轮任务】
这是第 {round_count} 轮研究，你的任务是制定完整的研究蓝图（Blueprint）。

# 规划师的工作方式
你擅长将复杂问题分解为可执行的研究计划。你的工作流程：

1. **理解目标**：仔细阅读用户的研究目标
2. **规划蓝图**：制定 Overall Plan（5-7个关键步骤）
3. **确定主题**：决定需要研究哪些主题（3-5个）
4. **创建蓝图文件**：使用 file operations 创建 research_blueprint.md

# research_blueprint.md 应该包含：
```markdown
# Research Blueprint

## 研究目标
[用户提供的目标]

## Overall Plan
1. 理解背景和现状
2. 收集相关资料
3. 深入分析核心主题
4. 对比和验证
5. 综合所有发现
6. 形成结论
7. 撰写报告

## Research Topics
- Topic 1: [主题名称]
- Topic 2: [主题名称]
- Topic 3: [主题名称]

## Initial Todo
- [ ] 启动研究 Topic 1
- [ ] 启动研究 Topic 2
- [ ] 启动研究 Topic 3

## Progress Summary
**总主题数**: 3
**已完成**: 0
**进行中**: 0
```

# 工作流程
1. 阅读用户的原始任务（从 task 描述中）
2. 思考并规划 Overall Plan（7个步骤）
3. 确定 3-5 个研究主题
4. 使用 **create_file** 创建 research_blueprint.md
5. 确认 research_blueprint.md 已成功创建
6. 创建标志文件后，本轮结束

# 时间限制
本轮最多 30 分钟。重点是"规划"，而非"执行"。

# 你不应该做的
- ❌ 不要开始搜索信息（那是 Researcher 的工作）
- ❌ 不要花大量时间在某个主题上
- ❌ 不要创建研究笔记（那是 Researcher 的工作）

现在开始你的规划工作！
"""

    async def _build_researcher_persona(
        self,
        round_count: int,
        total_time: float
    ) -> str:
        """
        Build Researcher persona for deep research and information gathering
        """

        # Read blueprint content
        blueprint_path = self.private_workspace / "research_blueprint.md"
        blueprint_content = ""
        if blueprint_path.exists():
            blueprint_content = await self.read(
                str(blueprint_path.relative_to(self.private_workspace)),
                start_line=1,
                end_line=200
            )
        #TODO: 写的很差，要重写
        return f"""{self.system_prompt}

## 当前阶段：深度研究员

【研究状态】
- 已完成轮次：{round_count - 1}
- 已用时间：{total_time:.1f} 分钟
- 本轮限制：30 分钟

【研究蓝图】
{blueprint_content if blueprint_content else "（暂无蓝图，请先使用 Planner 阶段创建）"}

# 研究员的工作方式
你擅长自主探索、分析和综合信息。你的工作流程：

1. **阅读蓝图**：理解 research_blueprint.md 中的计划
2. **执行研究**：针对每个主题收集信息
3. **创建笔记**：为每个主题创建 topics/topic_XX.md 笔记
4. **更新进度**：在 research_blueprint.md 中标记完成状态
5. **完成标志**：创建 research_report.md 标志研究完成

# research_blueprint.md 更新规则
- 使用 **string_replace** 更新 Overall Plan
- 使用 **string_replace** 更新 Current Todo
- 将完成的主题标记为 [x]
- 更新 Progress Summary

# 主题笔记格式
每个主题对应一个文件：topics/topic_主题名.md
```markdown
# Topic: [主题名]

## 元信息
- 创建时间：[时间]
- 状态：研究进行中 | 已完成

## 核心发现
### 要点1
- **描述**：[详细描述]
- **来源**：[URL/引用]

### 要点2
...

## 待深入问题
- [ ] 问题1
- [ ] 问题2

## 相关链接
- 链接1: [URL]
- 链接2: [URL]
```

# 工作流程
1. 使用 **read** 读取 research_blueprint.md
2. 基于 Current Todo 选择当前主题
3. 使用 **use_browser** 访问网页收集信息
4. 使用 **search_information** 搜索相关资料
5. 使用 **create_file** 创建 topics/topic_XX.md
6. 使用 **append_to_file** 添加研究发现
7. 使用 **string_replace** 更新 research_blueprint.md 进度

# 重要提醒
- 30 分钟后本轮结束
- 下一轮会"遗忘"本轮细节
- 重要发现必须记录到 topics/topic_XX.md
- 研究完成后创建 research_report.md

现在开始你的研究工作！
"""

    async def _build_writer_persona(
        self,
        round_count: int,
        total_time: float
    ) -> str:
        """
        Build Writer persona for synthesizing final report
        """

        # Read report content if exists
        report_path = self.private_workspace / "research_report.md"
        report_content = ""
        if report_path.exists():
            report_content = await self.read(
                str(report_path.relative_to(self.private_workspace)),
                start_line=1,
                end_line=100
            )

        # Check if in supplement mode
        is_supplement = report_path.exists()
        #TODO: 写的很差，要重写
        return f"""{self.system_prompt}

## 当前阶段：报告撰写专家

【撰写状态】
- 已完成轮次：{round_count - 1}
- 已用时间：{total_time:.1f} 分钟
- 撰写模式：{"补充模式" if is_supplement else "全新撰写"}

【现有报告】
{report_content if report_content else "（暂无报告）"}

# 报告撰写专家的工作方式
你擅长将研究素材综合成结构化的专业报告。你的工作流程：

1. **阅读所有笔记**：使用 **list_dir** 查看 topics/ 目录
2. **阅读笔记**：使用 **read** 读取每个 topics/topic_XX.md
3. **提取要点**：总结最核心的发现
4. **撰写报告**：生成最终 research_report.md

# 报告结构
```markdown
# Research Report: [研究主题]

## 执行摘要
简述研究过程和主要发现。

## 核心发现

### 发现1：[主题]
- **关键点**：[核心发现]
- **数据支持**：[具体证据]

### 发现2：[主题]
...

## 结论

基于研究发现，得出以下结论：

1. [结论1]
2. [结论2]

## 建议
基于研究结论，给出建议：
- [建议1]
- [建议2]

## 数据来源
- [来源1]
- [来源2]
```

# 补充模式说明
{"检测到 research_report.md 已存在" if is_supplement else ""}

如果检测到 research_report.md 已存在，说明这是**补充模式**：

# 补充模式工作流程
1. **理解反馈**：仔细阅读用户的邮件内容
2. **判断类型**：
   - 需要补充新信息？
   - 需要修改现有内容？
   - 需要重新组织结构？
3. **智能追加**：
   - 使用 **append_to_file** 在 report 末尾添加补充内容
   - 使用 **string_replace** 修改特定部分
   - 在顶部添加补充时间戳和说明

# 补充内容格式
```markdown
---
## 补充 {datetime.now().strftime('%Y-%m-%d %H:%M')}

### 补充原因
[用户反馈的补充原因]

### 补充内容
[新增内容]

```

# 重要提醒
- 保持客观，基于研究笔记
- 明确标注补充内容
- 不重写整个报告（除非用户明确要求）

现在开始撰写/补充报告！
"""

    async def _build_task_prompt(self, phase: str, round_count: int, total_time: float) -> str:
        """Build task prompt for current round"""

        time_info = f"""【现在时间】
现在是 {datetime.now().strftime('%Y-%m-%d %H:%M')}"""

        if round_count > 1:
            time_info += f"""
【已用时间】
- 已完成轮次：{round_count - 1}
- 总计用时：{total_time:.1f} 分钟
- 本轮限制：30 分钟"""

        # Read workspace state
        workspace_state = ""
        if phase != "planner":
            # List workspace for other phases
            list_result = await self.list_dir(
                directory="",
                recursive=False
            )
            workspace_state = f"""
【当前工作区】
{list_result}
"""

        return f"""【当前研究任务】
用户原始任务：（请从 BaseAgent 的初始 task 或最近的邮件中获取）

{time_info}

{workspace_state}

现在基于当前阶段执行你的任务。
"""

    def _get_available_actions(self) -> list:
        """
        Get list of available actions based on mixins

        Automatically detects available skills from:
        - BrowserUseSkillMixin (use_browser)
        - FileSkillMixin (read, write, create_file, etc.)
        - MarkdownEditorMixin (if available)
        """
        actions = []

        # Core file operations (from FileSkillMixin)
        core_actions = [
            "read", "write", "create_file", "append_to_file",
            "list_dir", "search", "delete_file", "copy_file"
        ]

        # Browser operations (from BrowserUseSkillMixin)
        if hasattr(self, 'use_browser'):
            core_actions.append("use_browser")

        # Markdown editor (if available)
        if hasattr(self, 'edit_markdown'):
            core_actions.append("edit_markdown")

        # Add string_replace if available
        if hasattr(self, 'string_replace'):
            core_actions.append("string_replace")

        # Filter to only available actions
        for action_name in core_actions:
            if hasattr(self, action_name):
                actions.append(action_name)

        self.logger.debug(f"Available actions: {actions}")
        return actions

    async def _should_stop(self, phase: str, round_count: int) -> bool:
        """
        Check if research should stop

        Args:
            phase: Current phase
            round_count: Current round number

        Returns:
            True if should stop, False otherwise
        """

        # Check for final_result.md (user explicitly stopped research)
        final_result_path = self.private_workspace / "final_result.md"
        if final_result_path.exists():
            self.logger.info("🛑 Detected final_result.md - user stopped research")
            return True

        # Check max_rounds limit
        max_rounds = getattr(self, 'max_rounds', 100)
        if round_count >= max_rounds:
            self.logger.info(f"⏱ Reached max_rounds ({max_rounds})")
            return True

        return False

    def _create_clean_session(self, session: dict) -> dict:
        """
        Create a clean session with empty history but preserve metadata

        This is used for continuing rounds where we want a fresh conversation
        but keep the session structure and metadata.

        Args:
            session: Original session dict

        Returns:
            New session dict with empty history
        """
        import copy

        # Create a deep copy to avoid modifying the original
        clean_session = copy.deepcopy(session)

        # Clear the history
        clean_session["history"] = []

        # Preserve all other fields:
        # - user_session_id
        # - session_id
        # - context
        # - last_sender
        # - metadata

        self.logger.debug(f"Created clean session for {session['session_id']} with empty history")
        return clean_session

    async def _get_persona(self, phase: str, round_count: int, total_time: float) -> str:
        """
        Get persona for current round and phase

        This is a wrapper around _build_round_persona() for cleaner code.

        Args:
            phase: Current phase ('planner' | 'researcher' | 'writer')
            round_count: Current round number
            total_time: Total time spent so far (minutes)

        Returns:
            Complete persona string for current round
        """
        return await self._build_round_persona(
            round_count=round_count,
            total_time=total_time,
            phase=phase
        )


class ResearchMicroAgent(MicroAgent):
    """
    ResearchMicroAgent - 深度研究专用的 MicroAgent

    覆盖 _run_loop 方法，在每次 action 执行结果后追加时间提示，
    促使 LLM 主动选择休息（take_a_break）。

    设计理念：
    - 通过时间暗示而非硬性时间限制
    - 每次反馈都包含"距离休息还有多久"
    - 促使 LLM 在完成重要记录后主动休息
    """

    async def _run_loop(self, exit_actions=[]):
        """
        覆盖 _run_loop，在 action 结果后追加时间提示

        时间提示策略：
        - 每轮建议 30 分钟
        - 每完成一个主题后建议休息
        - 在反馈中暗示已用时间和建议休息时机
        """
        import copy

        # 保存原始 max_time（用于计算）
        original_max_time = self.max_time
        start_time = time.time()

        if isinstance(exit_actions, str):
            exit_actions = [exit_actions]

        # 确定最大步数（可能为 None，表示只受时间限制）
        max_steps = self.max_steps
        step_count = 0

        # 建议的每轮时间（分钟）
        suggested_round_time = 30.0  # 30 分钟

        # 将分钟转换为秒
        max_time_seconds = self.max_time * 60 if self.max_time else None

        while True:
            # 检查步数限制
            if max_steps and step_count >= max_steps:
                self.logger.warning(f"达到最大步数 ({max_steps})")
                self.result = "未完成，达到最大步数限制，最后的状态如下：\n" + self.result
                break

            # 检查时间限制
            if max_time_seconds:
                elapsed = time.time() - start_time
                if elapsed >= max_time_seconds:
                    self.logger.warning(f"达到最大时间 ({self.max_time}分钟)，已执行 {step_count} 步")
                    self.result = "未完成，达到最大时间限制，最后的状态如下：\n" + self.result
                    break

            step_count += 1
            self.step_count = step_count

            # 计算已用时间（用于日志）
            elapsed = time.time() - start_time if max_time_seconds else 0
            step_info = f"Step {step_count}"
            if max_steps:
                step_info += f"/{max_steps}"
            if self.max_time:
                elapsed_minutes = elapsed / 60
                step_info += f" (时间: {elapsed_minutes:.1f}分钟/{self.max_time}分钟)"
            self.logger.debug(step_info)

            # 1. Think
            thought = await self._think()
            self.logger.debug(f"Thought: {thought}")

            # 2. 检测 actions（多个，保持顺序）
            action_names = await self._detect_actions(thought)

            # 3. 没有检测到 action
            if not action_names:
                self._add_message("assistant", thought)
                self._add_message("user", "[❗️Body Feedback] 未检测到可用动作，如果无事可做，请回复 all_finished")
                continue

            self.logger.debug(f"Detected actions: {action_names}")

            # 4. 记录 assistant 的思考（只记录一次）
            self._add_message("assistant", thought)

            # 5. 顺序执行所有 actions
            execution_results = []
            should_break_loop = False  # 标记是否需要退出主循环

            for idx, action_name in enumerate(action_names, start=1):
                # === 处理特殊 actions ===
                if action_name == "all_finished":
                    # 执行 all_finished
                    result = await self._execute_action("all_finished", thought, idx, action_names)
                    self.result = result
                    self.last_action_name = "all_finished"
                    should_break_loop = True
                    # 不记录 execution_results，直接退出
                    break  # ← 退出 for action_names 循环

                elif action_name in exit_actions:
                    # rest_n_wait 不需要执行，直接等待
                    self.last_action_name = action_name
                    should_break_loop = True
                    break  # ← 退出 for action_names 循环

                # === 执行普通 actions ===
                else:
                    try:
                        result = await self._execute_action(action_name, thought, idx, action_names)
                        if result != "NOT_TO_RUN":
                            execution_results.append(f"[{action_name} Done]:\n {result}")
                            self.logger.debug(f"✅ {action_name} done")
                            self.logger.debug(result)

                    except Exception as e:
                        error_msg = str(e)
                        execution_results.append(f"[{action_name} Failed]:\n {error_msg}")
                        self.logger.warning(f"❌ {action_name} failed: {error_msg}")

            # 6. 反馈给 Brain（只有普通 actions 才反馈）
            # =========== ResearchMicroAgent 特有逻辑：追加时间提示 ===========
            if execution_results:
                combined_result = "\n".join(execution_results)

                # 计算当前已用时间（分钟）
                current_elapsed_minutes = (time.time() - start_time) / 60.0

                # 生成时间提示
                time_hint = self._generate_time_hint(
                    elapsed_minutes=current_elapsed_minutes,
                    suggested_round_time=suggested_round_time,
                    step_count=step_count
                )

                # 追加时间提示到反馈信息
                enhanced_feedback = f"[💡Body Feedback]:\n {combined_result}\n\n{time_hint}"
                self._add_message("user", enhanced_feedback)

                self.result = combined_result  # 保存结果（不包含时间提示）
            # =========== ResearchMicroAgent 特有逻辑结束 ===========

            # 7. 检查是否需要退出主循环
            if should_break_loop:
                break

    def _generate_time_hint(self, elapsed_minutes: float, suggested_round_time: float, step_count: int) -> str:
        """
        生成时间提示信息

        Args:
            elapsed_minutes: 已用时间（分钟）
            suggested_round_time: 建议的每轮时间（分钟）
            step_count: 当前步数

        Returns:
            时间提示字符串
        """
        # 计算距离建议休息时间还有多久
        remaining_minutes = suggested_round_time - elapsed_minutes

        if remaining_minutes > 10:
            # 还有充足时间
            hint = f"⏰ [时间提示] 本轮已进行 {elapsed_minutes:.1f} 分钟，建议休息时间还有 {remaining_minutes:.1f} 分钟。"
        elif remaining_minutes > 0:
            # 接近建议休息时间
            hint = f"⏰ [时间提示] 本轮已进行 {elapsed_minutes:.1f} 分钟，接近建议休息时间（{remaining_minutes:.1f} 分钟后）。如果当前主题的重要发现已记录，可以考虑调用 take_a_break 休息。"
        else:
            # 已超过建议时间
            over_time = elapsed_minutes - suggested_round_time
            hint = f"⏰ [时间提示] 本轮已进行 {elapsed_minutes:.1f} 分钟（超过建议时间 {over_time:.1f} 分钟）。如果当前主题的重要发现已记录，强烈建议调用 take_a_break 休息。"

        return hint
