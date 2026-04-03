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

import os
import time
from datetime import datetime
from typing import Dict, Optional, Callable, List, Any
from ..core.message import Email
from ..core.events import AgentEvent
from ..core.action import register_action
from ..core.session_manager import SessionManager
import asyncio
from pathlib import Path
from .micro_agent import MicroAgent

from agentmatrix.agents.base import BaseAgent

from agentmatrix.skills.browser_use_skill import BrowserUseSkillMixin
from agentmatrix.skills.file_operations_skill import FileOperationSkillMixin
from ..skills.parser_utils import multi_section_parser


class DeepResearcher(BaseAgent, BrowserUseSkillMixin, FileOperationSkillMixin):
    
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
        self.current_task_id = session["task_id"]



        # 设置当前 session 目录
        self.current_session_folder = str(
                Path(self.workspace_root) /
                session["task_id"] /
                "history" /
                self.name /
                session["session_id"]
            )

        

        # === 初始化循环变量 ===
        round_count = 1
        start_time = time.time()
        history_before_loop = session.get("history", []).copy()

        # === 外层循环：多轮执行 ===
        while True:
            # 计算已用时间（分钟）
            total_time = (time.time() - start_time) / 60.0

            # 1. 检测当前阶段
            phase = await self._detect_phase()
            persona =  self.get_persona(phase)
            #self.logger.debug(f"Current phase: {phase}, using persona: {persona}")
            

        
            history = history_before_loop.copy()
            if history:
                for item in history:
                    if item["role"] == "user":
                        content = item["content"]
                        # 检查是否包含白板内容
                        if "[白板]" in content and "==== END OF WHITEBOARD ====" in content:
                            # 移除白板内容
                            start = content.find("[白板]")
                            end = content.find("==== END OF WHITEBOARD ====") + len("==== END OF WHITEBOARD ====")
                            item["content"] = content[:start] + content[end:]
                session["history"] = history
                asyncio.create_task(self.session_manager.save_session(self.session)) #This effectively restore history to begin of while True loop.  
                # 也就是说，每次ResearchMicroAgent的execute，都是同样的session history 起点，不同的是whiteboard，和所有其他文件


            current_whiteboard = await self.read_whiteboard()

            # 3. 构建任务描述（包含时间、轮次、工作区状态）
            task_prompt = await self._build_task_prompt(
                phase=phase,
                round_count=round_count,
                email = str(email),
                whiteboard = current_whiteboard
            )

            # 日志：当前轮次信息
            self.logger.info(f"🔄 Round {round_count} - Phase: {phase.upper()} - Total time: {total_time:.1f}m")

            # 4. 创建新的 ResearchMicroAgent（每轮都是新实例）
            micro_core = ResearchMicroAgent(
                parent=self,
                name=f"{self.name}_round{round_count}"
            )

            

            # 6. 执行 MicroAgent,  execute 内部也是一个永久循环，直到运行 rest_n_wait, take_a_break, 或声明式退出
            result = await micro_core.execute(
                run_label=f'Round {round_count} - {phase}',
                persona=persona,
                task=task_prompt,
                session=session,  # ← 传递干净的 session
                session_manager=self.session_manager,  # ← 传递 session_manager
                #yellow_pages=self.post_office.yellow_page_exclude_me(self.name),
                exit_actions=["rest_n_wait", "take_a_break"]
            )

            # 7. 更新轮次计数
            round_count += 1

            # 8. 检查退出条件
            last_action = micro_core.last_action_name
            self.logger.info(f"🔚 MicroAgent finished with action: {last_action}")

            if last_action in ["rest_n_wait"] or not last_action:
                # 正常退出：保存 session（下次用户发邮件时继续）
                # rest_n_wait 显式退出，或声明式退出（无 last_action）
                self.logger.info(f"💾 Saving session and exiting outer loop (action: {last_action or 'declarative'})")
                #这个时候篡改一下session hisotry
                old_history_length = len(history_before_loop)
                new_history = session["history"].copy()
                #取new_history 的0到old_history_length，以及最后一条，拼接在一起， 相当于new_history比old_history多了两条
                session["history"] = new_history[:old_history_length] + new_history[-1:]


                await self.session_manager.save_session(session)

                # 退出外层循环，等待用户输入
                break
            elif last_action == "take_a_break":
                # 主动休息：不保存 session history，继续下一轮
                self.logger.info(f"☕ MicroAgent requested break - continuing to next round")
                # 不保存 session，直接继续下一轮
                session = self._create_clean_session(session)
                continue
            else:
                # 其他退出条件（超时、错误等）
                self.logger.warning(f"⚠ MicroAgent exited unexpectedly: {last_action}")
                # 应该是超过1024步了
                session = self._create_clean_session(session)
                



    @register_action(
        description="向 AI 提问(这个AI毫无记忆，每次问答都是独立的)",
        param_infos={
            "question": "要向 AI 提出的问题"
        }
    )
    async def ask_ai(self, question: str) -> str:
        """向 AI 助手提问"""
        try:
            response = await self.brain.think(question)
            return response['reply']
        except Exception as e:
            return f"ask_ai 失败: {str(e)}"

    @register_action(
        description="必须执行这个动作才是真的休息一会",
        param_infos={}
    )
    async def take_a_break(self):
        # 什么都不做，直接返回
        return ""


        

    async def _detect_phase(self) -> str:
        """
        Detect current research phase by checking flag files

        Priority: Writer (has report.md) > Researcher (has blueprint.md) > Planner

        Returns:
            'planner' | 'researcher' | 'writer'
        """
        
        blueprint_path = self.private_workspace / "research_blueprint.md"
        draft_path = self.private_workspace / "draft"
        report_path = self.private_workspace / "final_report.md"

        if draft_path.exists():
            self.logger.info("📝 Phase detected: WRITER (final_writing_plan.md exists)")
            return "writer"
        elif blueprint_path.exists():
            self.logger.info("📝 Phase detected: RESEARCHER (research_blueprint.md exists)")
            return "researcher"
        elif report_path.exists():
            self.logger.info("📝 Phase detected: OTHER (final_report.md exists)")
            return "after-write"
        else:
            self.logger.info("📝 Phase detected: PLANNER (no flags found)")
            return "planner"

    

   

    async def _build_task_prompt(self, phase: str, round_count: int, email: str, whiteboard) -> str:
        """Build task prompt for current round"""
        #先检查session.history是不是空的
        if round_count == 1:
            
            return f'''
            [💡NEW EMAIL] 
            {email}
            
            
            {whiteboard}

            现在决定你的下一步

            '''
        else:
            return f'''
            [💡 NEW EMAIL] 
            {email}
            

            

            {whiteboard}

            现在继续你的工作
            '''

        
        
        

    
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

        This is used for continuing rounds where we want a fresh session
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
        # - task_id
        # - session_id
        # - context
        # - last_sender
        # - metadata

        self.logger.debug(f"Created clean session for {session['session_id']} with empty history")
        return clean_session
    @register_action(
        description="读取白板内容",
        param_infos={
            
        }
    )
    async def read_whiteboard(self) -> str:
        """
        读取 whiteboard 内容（Micro Agent 调用）

        Returns:
            白板内容（纯文本）
        """
        # 白板路径：workspace_root/agent_files/{agent_name}/work_files/{task_id}/whiteboard.md
        task_id = self.current_task_id or "default"
        whiteboard_path = os.path.join(
            self.workspace_root,
            "agent_files",
            self.name,
            "work_files",
            task_id,
            "whiteboard.md"
        )
        if not os.path.exists(whiteboard_path):
            #create file
            with open(whiteboard_path, "w", encoding="utf-8") as f:
                f.write("")
            return "[白板]\n<<暂时空白>>\n=====END OF WHITEBOARD====="

        try:
            with open(whiteboard_path, "r", encoding="utf-8") as f:
                content = f.read()
                content = content.strip()
                if content:
                    # 计算内容字数，占2000的比例，超过2000算100%
                    word_count = len(content)
                    word_percent = min(word_count / 2000, 1)
                    content = "[白板]\n"+ content + "\n=====END OF WHITEBOARD====="
                    if word_percent >= 0.8:
                        content += f"\n<<⚠️ WHITEBOARD {word_percent*100:.1f}% FULL>>"
                    elif word_percent >= 0.5:
                        content += f"\n<<ℹ️ whiteboard {word_percent*100:.1f}% full>>"
                else:
                    content = "[白板]\n<<暂时空白>>\n=====END OF WHITEBOARD====="
                return content
        except Exception as e:
            self.logger.error(f"读取白板内容失败: {e}")
            return f"❌ 读取白板失败：{str(e)}"
        

    
    @register_action(
        description="更新白板内容，默认全部擦掉重写，如果只是更新局部或者添加内容，要明确指出",
        param_infos={
            "full_new_content": "（可选）完整的新白板内容",    
            "partial_edit": "（可选）对当前白板的局部修改或添加，需要明确指出改哪里改什么"
        }
    )
    
    async def update_whiteboard(self, full_new_content: str = "", partial_edit: str = "") -> str:
        """
        更新 whiteboard（Micro Agent 调用）

        支持两种模式：
        1. 全文替换：new_content 有值 → 直接更新
        2. 智能修改：modification_feedback 有值 → LLM 根据当前内容 + 修改意见生成新版本

        Args:
            new_content: 完整的新 dashboard 内容（纯文本）
            modification_feedback: 对当前 dashboard 的修改意见

        Returns:
            确认消息
        """
        full_new_content = full_new_content.strip()
        partial_edit = partial_edit.strip()
        if not full_new_content and not partial_edit:
            return "❌ 请提供完整的白板内容或修改意见"

        # 白板路径：workspace_root/agent_files/{agent_name}/work_files/{task_id}/whiteboard.md
        task_id = self.current_task_id or "default"
        whiteboard_path = os.path.join(
            self.workspace_root,
            "agent_files",
            self.name,
            "work_files",
            task_id,
            "whiteboard.md"
        )
        existing_content = ""
        #check if file exists, if not create it
        if not os.path.exists(whiteboard_path):
            with open(whiteboard_path, "w", encoding="utf-8") as f:
                f.write("")
        
        # 模式1：全文替换
        #直接overwrite 方式写入
        if full_new_content:
            with open(whiteboard_path, "w", encoding="utf-8") as f:
                f.write(full_new_content)

            

        # 模式2：智能修改
        elif partial_edit:
            # 读取当前 whiteboard 内容
            
            
            
            #使用python 方法读取whiteboard_path 
            existing_content = ""
            with open(whiteboard_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
            

            # 构建 LLM prompt
            # 注意：这里使用 Micro Agent 的 persona（从 _do_search_task 传入）
            # 我们需要通过 session_context 或其他方式获取 persona
            # 为了简化，我们直接在 prompt 中描述任务
            generate_prompt = f"""你是一个高效的项目助理，正在管理项目白板。

当前白板内容：
{existing_content}

项目经理的修改意见：
{partial_edit}

请根据修改意见，生成更新后的白板内容。

请先简要说明你的理解和思考，然后用 "[正式文稿]" 作为分隔符，输出正式的更新后的白板内容。

输出格式：
你的思考过程...

[正式文稿]
更新后的白板内容
"""

            try:
                

                result = await self.brain.think_with_retry(
                    generate_prompt,
                    multi_section_parser,
                    section_headers=["[正式文稿]"],
                    match_mode="ALL"
                )

                full_new_content = result["[正式文稿]"].strip()    

            # 更新
                with open(whiteboard_path, "w", encoding="utf-8") as f:
                    f.write(full_new_content)

            except Exception as e:
                self.logger.error(f"智能修改 dashboard 失败: {e}")
                return f"❌ 生成新白板失败：{str(e)}"

        word_count = len(full_new_content)
        word_percent = min(word_count / 2000, 1)
        if word_percent ==1:
            return(f"✅ 白板已更新 ⚠️ WHITEBOARD FULL,REDUCE BEFORE ADDING MORE")
        if word_percent >= 0.8:
            return f"✅ 白板已更新，⚠️ WHITEBOARD {word_percent*100:.1f}% FULL, ORGANIZE RECOMMENDED"
        elif word_percent >= 0.5:
            return f"✅ 白板已更新，ℹ️ whiteboard {word_percent*100:.1f}% full"
        else:
            return "✅ 白板已更新"

    


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

        if remaining_minutes > 15:
            # 还有充足时间
            hint = "" #NO need to hint
        elif remaining_minutes > 0:
            # 接近建议休息时间
            hint = f"⏰ [时间提示] 已工作{elapsed_minutes:.1f} 分钟，距离计划的休息时间还有 {remaining_minutes:.1f} 分钟。记得多存盘"
        else:
            # 已超过建议时间
            over_time = elapsed_minutes - suggested_round_time
            hint = f"⏰ [时间提示] 已超时工作 {over_time:.1f} 分钟）。为了健康建议尽早存盘休息一会！"

        return hint

    async def _prepare_feedback_message(
        self,
        combined_result: str,
        step_count: int,
        start_time: float
    ) -> str:
        """
        重写：添加时间提示到反馈消息

        Args:
            combined_result: 所有 action 的执行结果
            step_count: 当前步数
            start_time: 循环开始时间

        Returns:
            增强后的反馈消息
        """
        # 计算当前已用时间（分钟）
        elapsed_minutes = (time.time() - start_time) / 60.0

        # 生成时间提示
        time_hint = self._generate_time_hint(
            elapsed_minutes=elapsed_minutes,
            suggested_round_time=45.0,
            step_count=step_count
        )

        # 追加时间提示到反馈信息
        return f"[💡Body Feedback]:\n {combined_result}\n\n{time_hint}"

    
        


    
                

            
