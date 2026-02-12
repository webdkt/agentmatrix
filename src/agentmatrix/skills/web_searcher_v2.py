"""
Web Searcher V2 - 基于 Micro Agent 的网络搜索技能

设计理念：
- 单一接口：web_search(query)
- Micro Agent 自主规划：不提供详细指令，让 Micro Agent 自己决定如何使用工具
- 工具集：browser_navigate + file_operation + update_dashboard
- 永久循环：每轮 30 分钟，支持无限轮次，context 不会爆炸
- 状态管理：通过纯文本 dashboard 保持长期记忆

参考模式：deep_researcher._do_research_task
"""

import time
from typing import Optional
from ..core.action import register_action
from .browser_use_skill import BrowserUseSkillMixin
from .file_operations_skill import FileOperationSkillMixin
from ..agents.base import BaseAgent
from ..agents.micro_agent import MicroAgent


class WebSearcherV2Mixin(BrowserUseSkillMixin, FileOperationSkillMixin):
    """
    Web Searcher V2 Skill Mixin

    继承：
    - BrowserUseSkillMixin: 提供 browser_navigate action
    - FileOperationSkillMixin: 提供 file_operation action
    - BaseAgent: 通过继承 BaseAgent 获得 MicroAgent 创建能力

    对外接口：
    - web_search(purpose): 执行网络搜索
    """

    # ==========================================
    # 主入口
    # ==========================================

    @register_action(
        description="使用浏览器来查找需要的信息",
        param_infos={
            "purpose": "使用浏览器的目的，例如需要查找的问题或主题，想要发现什么"
        }
    )
    async def web_search(self, purpose: str) -> str:
        """
        执行网络搜索（主入口）

        工作流程：
        1. 创建搜索专属的子目录（每次搜索都是新的）
        2. 初始化 dashboard
        3. 启动永久搜索循环（每轮 30 分钟，所有轮次共享同一目录）
        4. 返回最终的 dashboard 状态

        Args:
            purpose: 搜索目的或问题

        Returns:
            str: 最终的 dashboard 状态（包含搜索结果摘要）
        """
        self.logger.info(f"🔍 [WebSearcherV2] 开始搜索: {purpose}")

        try:
            # 1. 创建搜索专属的子目录（每次搜索都是新的）
            search_context = self.working_context.create_child(
                "web_search",
                use_timestamp=True  # 每次搜索创建新目录
            )
            self.logger.info(f"✓ 创建搜索目录: {search_context.current_dir}")

            # 2. 初始化 dashboard
            await self._init_dashboard()

            # 3. 执行搜索循环（所有轮次共享 search_context）
            final_dashboard = await self._do_search_task(purpose, search_context)

            self.logger.info(f"✅ [WebSearcherV2] 搜索完成")

            return final_dashboard

        except Exception as e:
            self.logger.error(f"❌ [WebSearcherV2] 搜索失败: {e}")
            raise

    # ==========================================
    # Dashboard 管理
    # ==========================================

    async def _init_dashboard(self):
        """
        初始化 dashboard（纯文本）
        """
        initial_dashboard = "<<无内容>>"

        await self.update_session_context(search_dashboard=initial_dashboard)
        self.logger.debug("✓ Dashboard 初始化完成")

    async def _get_dashboard(self) -> str:
        """
        获取当前 dashboard（纯文本）+ 容量提示

        Returns:
            str: dashboard 内容 + 容量信息（如 "whiteboard is 45% full"）
        """
        # 白板容量上限（字符数）
        DASHBOARD_CAPACITY = 2000

        ctx = self.get_session_context()
        dashboard = ctx.get("search_dashboard", "")

        # 计算容量百分比
        char_count = len(dashboard)
        percentage = min(100, int(char_count / DASHBOARD_CAPACITY * 100))

        # 生成容量提示
        # 超过 85% 时全大写警示
        if percentage >= 85:
            capacity_info = f"WHITEBOARD IS {percentage}% FULL"
        else:
            capacity_info = f"whiteboard is {percentage}% full"

        # 返回 dashboard + 容量信息（中间空一行）
        if dashboard:
            return f"{dashboard}\n\n{capacity_info}"
        else:
            return capacity_info

    @register_action(
        description="更新白板内容。可以提供完整的新的dashboard文本，或者局部修改意见",
        param_infos={
            "new_content": "（可选）完整的白板内容文本",
            "modification_feedback": "（可选）对现有白板内容的修改意见"
        }
    )
    async def update_dashboard(self, new_content: str = "", modification_feedback: str = "") -> str:
        """
        更新 dashboard（Micro Agent 调用）

        支持两种模式：
        1. 全文替换：new_content 有值 → 直接更新
        2. 智能修改：modification_feedback 有值 → LLM 根据当前内容 + 修改意见生成新版本

        Args:
            new_content: 完整的新 dashboard 内容（纯文本）
            modification_feedback: 对当前 dashboard 的修改意见

        Returns:
            确认消息
        """
        if not new_content and not modification_feedback:
            return "❌ 请提供完整的白板内容或修改意见"

        # 模式1：全文替换
        if new_content:
            dashboard = new_content.strip()
            if not dashboard:
                return "❌ 白板内容不能为空"

            await self.update_session_context(search_dashboard=dashboard)
            self.logger.debug(f"✓ Dashboard 已更新（全文替换，{len(dashboard)} 字符）")
            return f"✅ 白板已更新（{len(dashboard)} 字符）"

        # 模式2：智能修改
        if modification_feedback:
            ctx = self.get_session_context()
            current_dashboard = ctx.get("search_dashboard", "")

            # 构建 LLM prompt
            # 注意：这里使用 Micro Agent 的 persona（从 _do_search_task 传入）
            # 我们需要通过 session_context 或其他方式获取 persona
            # 为了简化，我们直接在 prompt 中描述任务
            generate_prompt = f"""你是一个高效的项目助理，正在管理项目白板。

当前白板内容：
{current_dashboard}

项目经理的修改意见：
{modification_feedback}

请根据修改意见，生成更新后的白板内容。

请先简要说明你的理解和思考，然后用 "[正式文稿]" 作为分隔符，输出正式的更新后的白板内容。

输出格式：
你的思考过程...

[正式文稿]
更新后的白板内容
"""

            try:
                from .parser_utils import multi_section_parser

                result = await self.brain.think_with_retry(
                    generate_prompt,
                    multi_section_parser,
                    section_headers=["[正式文稿]"],
                    match_mode="ALL"
                )

                new_dashboard = result["[正式文稿]"].strip()

                # 更新
                await self.update_session_context(search_dashboard=new_dashboard)
                self.logger.debug(f"✓ Dashboard 已更新（智能修改，{len(new_dashboard)} 字符）")
                return f"✅ 白板已更新（{len(new_dashboard)} 字符）"

            except Exception as e:
                self.logger.error(f"智能修改 dashboard 失败: {e}")
                return f"❌ 生成新白板失败：{str(e)}"

    # ==========================================
    # 搜索循环
    # ==========================================

    async def _get_current_browser_url(self) -> Optional[str]:
        """
        获取浏览器当前访问的 URL（实时）

        Returns:
            str or None: 当前 URL，如果浏览器未启动或无法获取则返回 None
        """
        # 尝试从 Browser 实例获取实时 URL
        if hasattr(self, '_browser_use_browser') and self._browser_use_browser is not None:
            try:
                current_url = await self._browser_use_browser.get_current_page_url()
                if current_url and current_url != 'about:blank':
                    return current_url
            except Exception as e:
                self.logger.debug(f"获取实时 URL 失败: {e}")

        return None

    async def _do_search_task(self, purpose: str, working_context) -> str:
        """
        执行搜索任务（永久循环）

        参考：deep_researcher._do_research_task

        工作流程：
        1. 启动永久循环
        2. 每轮调用 Micro Agent（30分钟/轮）
        3. 通过 dashboard 保持连续性
        4. Micro Agent 主动决定何时完成（调用 all_finished）

        Args:
            purpose: 搜索目的
            working_context: 工作上下文（所有轮次共享）

        Returns:
            str: 最终的 dashboard 状态
        """
        self.logger.info(f"🔄 [WebSearcherV2] 启动搜索循环")

        round_count = 0
        total_time = 0.0  # 总时间（分钟）

        while True:
            round_count += 1
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"第 {round_count} 轮搜索开始")
            self.logger.info(f"{'='*60}")

            # 获取当前 dashboard
            dashboard = await self._get_dashboard()

            # 🆕 获取当前浏览器 URL
            current_url = await self._get_current_browser_url()

            # 🆕 根据轮次生成不同的浏览器状态文本
            if round_count == 1:
                browser_status = "浏览器已经打开。"
            else:
                if current_url:
                    browser_status = f"浏览器目前停留在 {current_url}"
                else:
                    browser_status = "浏览器已经打开。"

            persona = """
            The first principle is that you must not fool yourself and you are the easiest person to fool.
            The fundamental cause of the trouble is that in the modern world the stupid are cocksure while the intelligent are full of doubt.
            你像微博用户Tombkeeper一样高度理性。擅长利用互联网来查找资料，逻辑缜密并善于分辨信源可靠度和资料的真假。
            你蔑视各种SEO、垃圾信息、标题党和AI生成的虚假内容
            你总能识别最真实、权威、有效的信息
            你习惯于看穿文字背后的意图，而不是轻易相信表面字义。
            你睿智又果断，绝不做闷头拉磨的驴子，看好路，能行则行，不能行则止。
            但是你饱受记忆衰退之苦，难以记住30分钟以前的事情。
            所以必须**记笔记**，最重要的事情写到白板上，白板总是能看到的。
            **任何没有写入文件的内容都会被遗忘，任何写下来但无法通过白板最终定位到的内容也等于没有**。
            写下**必须记住**的东西，写的时候就要**想清楚写到那里**，以后如何能**追溯**到它。因为一切都会被忘记。
            你会按需创建新的文件。
            但你有如同磐石一般无法改变的习惯：
            - 笔记记录在 notes.md
            - 重要发现记录在 finding.md
            - 任务计划和状态记录在plan.md
            - **时刻不能忘东西的记在白板上**
            - 只有完全结束、或无法继续、没必要再继续的时候，你才会新建并把总结写进 final_result.md
            
            创建final_result.md 代表任务结束，无论成功与否。
            
            """

            # 构建时间信息（第一轮不提昏睡醒来的事）
            if round_count == 1:
                time_info = f"现在是{time.strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                time_info = f"现在是{time.strftime('%Y-%m-%d %H:%M:%S')}，你已从工作又休息了 {round_count - 1} 次，合计用时 {total_time:.1f} 分钟。"

            # 构建 Micro Agent 任务描述（告知 Micro Agent 使用专属目录）
            task_prompt = f"""
【本次上网的目的】
{purpose}
=====END OF TASK=====

[现在时间]
{time_info}

[浏览器状态]
{browser_status}

[目前的白板]
{dashboard}
=======END OF BOARD=====

现在决定下一步动作
"""

            # 执行 Micro Agent（30分钟/轮）
            try:
                # 记录开始时间（计算实际执行时间）
                round_start_time = time.time()

                # 直接创建 Micro Agent
                micro_agent = MicroAgent(
                    parent=self,
                    working_context=working_context  # 所有轮次共享
                )

                result = await micro_agent.execute(
                    run_label=f"search_round_{round_count}",
                    persona=persona,
                    task=task_prompt,
                    available_actions=[
                        "use_browser",
                        "update_dashboard",
                        "read",
                        "write",
                        "list_dir",
                        "search",
                        "shell_cmd"
                    ],
                    max_steps=None,  # 不限制步数
                    max_time=30.0   # 每轮最多 30 分钟
                )

                # 计算实际执行时间（分钟）
                round_actual_time = (time.time() - round_start_time) / 60.0
                total_time += round_actual_time
                self.logger.info(f"⏱ 本轮实际用时: {round_actual_time:.2f} 分钟")

                # 🆕 检查退出条件（简化版：只检查 final_result.md）
                should_stop, final_result_content = await self._should_stop(working_context)

                if should_stop:
                    self.logger.info(f"✅ 搜索循环结束（第 {round_count} 轮）")

                    # 🆕 如果有 final_result.md 内容，返回它而不是 dashboard
                    if final_result_content:
                        return final_result_content
                    else:
                        return result

                    

                # 否则继续下一轮
                self.logger.info(f"⏸ 第 {round_count} 轮结束，继续下一轮...")

            except Exception as e:
                self.logger.error(f"❌ 第 {round_count} 轮执行失败: {e}")
                # 失败时记录到 dashboard，然后继续
                current_dashboard = await self._get_dashboard()
                error_dashboard = f"{current_dashboard}\n\n【错误】\n第 {round_count} 轮执行失败: {e}\n"
                await self.update_session_context(search_dashboard=error_dashboard)
                
                # 如果连续失败太多，可能需要退出（这里简单处理：继续）
                return f"web_search failed {e}"



    async def _should_stop(self, working_context) -> tuple[bool, Optional[str]]:
        """
        检查是否应该退出搜索循环

        简化逻辑：只要存在 final_result.md 文件，就说明任务完成

        防爆机制：限制返回 200 行，超出部分添加说明

        Args:
            working_context: 工作上下文

        Returns:
            tuple[bool, Optional[str]]: (是否应该退出, final_result.md 的内容或截断内容)
                - 如果文件不存在：(False, None)
                - 如果文件存在且 <=200 行：(True, 全部内容)
                - 如果文件存在且 >200 行：(True, 前 200 行 + 说明)
        """
        from pathlib import Path
        import os

        # 在当前工作目录下检查 final_result.md
        final_result_file = Path(working_context.current_dir) / "final_result.md"

        if not final_result_file.exists():
            # 文件不存在，继续
            return False, None

        # 文件存在，读取内容
        try:
            with open(final_result_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 计算行数
            lines = content.split('\n')
            total_lines = len(lines)
            file_size = os.path.getsize(final_result_file)

            # 格式化文件大小
            if file_size < 1024:
                file_size_str = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                file_size_str = f"{file_size / 1024:.1f}KB"
            else:
                file_size_str = f"{file_size / (1024 * 1024):.1f}MB"

            # 🆕 防爆机制：限制返回 200 行
            MAX_LINES = 200

            if total_lines <= MAX_LINES:
                # 文件较小，全部返回
                self.logger.info(f"✓ 发现 final_result.md ({total_lines} 行)，任务完成")
                return True, content
            else:
                # 文件较大，只返回前 200 行并添加说明
                self.logger.info(f"✓ 发现 final_result.md ({total_lines} 行，已截断显示前 {MAX_LINES} 行)，任务完成")

                # 获取相对路径（相对于 base_dir）
                try:
                    rel_path = os.path.relpath(final_result_file, working_context.base_dir)
                except ValueError:
                    rel_path = str(final_result_file)

                # 截取前 200 行
                truncated_lines = lines[:MAX_LINES]
                truncated_content = '\n'.join(truncated_lines)

                # 构建说明
                header = f"# 文件: {rel_path} ({file_size_str}, 共 {total_lines} 行)\n"
                header += f"# 显示前 {MAX_LINES} 行（已截断）\n\n"

                return True, header + truncated_content

        except Exception as e:
            self.logger.error(f"读取 final_result.md 失败: {e}")
            # 即使读取失败，仍然退出（因为文件存在）
            return True, None
