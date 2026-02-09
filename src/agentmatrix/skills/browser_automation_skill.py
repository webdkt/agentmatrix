"""
浏览器自动化Skill

提供智能的浏览器自动化能力，通过视觉理解完成任意网页操作任务。
核心特性：
- ReAct循环模式（规划+执行混合）
- 智能自适应视觉定位
- 多层MicroAgent隔离
- 自然恢复机制
"""

import asyncio
from typing import Optional, Dict, Any

from ..agents.base import BaseAgent
from ..core.log_util import AutoLoggerMixin
from .browser_vision_locator import IntelligentVisionLocator


class BrowserAutomationSkillMixin(AutoLoggerMixin):
    """
    浏览器自动化专家Skill

    依赖注入：
    - browser_adapter: 浏览器适配器实例
    - brain_with_vision: 支持视觉的LLM客户端
    """

    # 配置参数
    _custom_log_level = 30  # WARNING级别，减少日志噪音

    # 默认配置
    DEFAULT_MAX_STEPS = 50
    DEFAULT_SCREENSHOT_AFTER_ACTION = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 懒加载：在第一次使用时创建
        self._vision_locator = None

    # ================================================================
    # 主入口 Actions
    # ================================================================

    async def browser_research(self, task: str, max_steps: int = None) -> str:
        """
        执行浏览器自动化任务（主入口）

        这个action启动一个ReAct循环，通过视觉理解逐步完成任务。

        Args:
            task: 任务描述，如"登录Gmail并发送邮件"
            max_steps: 最大执行步数

        Returns:
            str: 执行结果描述
        """
        self.logger.info(f"开始浏览器任务: {task}")

        # 检查依赖
        browser = self._get_browser_adapter()
        vision = getattr(self, 'vision_brain', None)

        if not browser:
            return "错误：缺少 browser_adapter 配置"

        if not vision:
            return "错误：缺少 vision_brain 配置。请在 agent 配置文件中添加 vision_brain.backend_model"

        # 获取或创建tab
        tab = await browser.get_tab()
        current_url = await asyncio.to_thread(lambda: tab.url)
        self.logger.info(f"当前页面: {current_url}")

        # 初始化定位器
        if self._vision_locator is None:
            from .browser_vision_locator import IntelligentVisionLocator
            self._vision_locator = IntelligentVisionLocator(browser, vision)

        # 启动ReAct循环（MicroAgent Level 1）
        result = await self._run_micro_agent(
            persona=self._build_browser_task_persona(),
            task=f"""你要完成以下浏览器任务：{task}

当前页面URL: {current_url}

请分析当前页面状态，规划执行步骤，然后逐步执行。每执行一步操作后，观察页面变化，判断下一步该做什么。

操作类型包括：
- 点击某个元素（使用 _locate_and_click）
- 在输入框输入文本（使用 _locate_and_input）
- 滚动页面（使用 _locate_and_scroll）

任务完成后，使用 finish_task 报告结果。""",
            available_actions=["_analyze_and_decide_action", "_finish_task"],
            max_steps=max_steps or self.DEFAULT_MAX_STEPS,
            exclude_actions=["rest_n_wait", "take_a_break"]
        )

        return result

    def _build_browser_task_persona(self) -> str:
        """构建浏览器任务的persona"""
        return """你是一个经验丰富的浏览器自动化专家。

你的能力：
1. 能够通过观察页面截图理解当前状态
2. 能够分析页面元素并规划操作步骤
3. 能够使用视觉定位系统精确找到目标元素
4. 能够智能判断操作结果并决定下一步

工作流程：
1. 先观察当前页面（截图）
2. 分析页面，思考下一步应该做什么操作
3. 执行操作（点击/输入/滚动）
4. 观察操作后的页面变化
5. 判断任务是否完成，或决定继续哪一步
6. 重复直到任务完成

注意事项：
- 如果操作失败，分析原因并尝试替代方案
- 如果遇到新的页面，重新分析再规划
- 保持耐心，一步一步完成任务
"""

    # ================================================================
    # 分析和决策 Actions
    # ================================================================

    async def _analyze_and_decide_action(self) -> str:
        """
        分析当前页面并决策下一步操作

        这个action会：
        1. 截取当前页面
        2. 让vision_brain分析页面状态
        3. 决定下一步操作类型和目标

        Returns:
            str: 分析结果和操作决策
        """
        browser = self._get_browser_adapter()
        vision = getattr(self, 'vision_brain', None)

        if not browser:
            return "错误：缺少 browser_adapter"
        if not vision:
            return "错误：缺少 vision_brain"

        tab = await browser.get_tab()

        # 截图
        screenshot = await browser.capture_screenshot(tab)
        current_url = await asyncio.to_thread(lambda: tab.url)

        # 使用vision_brain分析
        analysis_prompt = f"""请分析当前页面的截图，告诉我：

1. 这是什么页面？（页面标题和主要功能）
2. 页面上有哪些主要的可交互元素？
3. 如果要完成我们的任务，下一步应该做什么操作？

当前URL: {current_url}

请简洁回答，重点说明下一步操作和操作目标。"""

        try:
            analysis = await vision.think_with_image(
                messages=[{"role": "user", "content": analysis_prompt}],
                image=screenshot
            )

            self.logger.info(f"页面分析: {analysis}")
            return f"页面分析结果：{analysis}\n\n请根据分析结果选择具体的操作action。"

        except Exception as e:
            self.logger.error(f"页面分析失败: {e}")
            return f"页面分析失败: {str(e)}。请根据你的判断选择操作。"

    # ================================================================
    # 定位和操作 Actions
    # ================================================================

    async def _locate_and_click(self, element_description: str) -> str:
        """
        定位并点击元素

        Args:
            element_description: 目标元素的描述，如"登录按钮"

        Returns:
            str: 操作结果
        """
        browser = self._get_browser_adapter()
        tab = await browser.get_tab()

        # 使用智能视觉定位器
        locator_result = await self._vision_locator.locate_element_interactively(
            tab=tab,
            element_description=element_description,
            operation_type="click",
            max_steps=8
        )

        if not locator_result.success:
            return f"定位失败: {locator_result.reason}\n步骤: {'; '.join(locator_result.steps_taken)}"

        # 执行点击
        try:
            report = await browser.click_and_observe(tab, locator_result.element)

            result_msg = f"✓ 成功点击: {element_description}\n"
            result_msg += f"URL变化: {report.is_url_changed}\n"
            result_msg += f"DOM变化: {report.is_dom_changed}\n"

            if report.new_tabs:
                result_msg += f"新标签页: {len(report.new_tabs)}个\n"

            if report.error:
                result_msg += f"错误: {report.error}\n"

            return result_msg

        except Exception as e:
            return f"点击操作失败: {str(e)}"

    async def _locate_and_input(self, element_description: str, text: str) -> str:
        """
        定位输入框并输入文本

        Args:
            element_description: 输入框的描述，如"用户名输入框"
            text: 要输入的文本

        Returns:
            str: 操作结果
        """
        browser = self._get_browser_adapter()
        tab = await browser.get_tab()

        # 先定位元素
        locator_result = await self._vision_locator.locate_element_interactively(
            tab=tab,
            element_description=element_description,
            operation_type="input",
            max_steps=8
        )

        if not locator_result.success:
            return f"定位失败: {locator_result.reason}\n步骤: {'; '.join(locator_result.steps_taken)}"

        try:
            # 获取底层 ChromiumElement
            chromium_element = locator_result.element.get_element()

            # 先点击输入框获得焦点
            await asyncio.to_thread(chromium_element.click)
            await asyncio.sleep(0.2)

            # 输入文本（使用 DrissionPage 的 input 方法）
            await asyncio.to_thread(chromium_element.input, vals=text, clear=True)

            # 等待输入完成
            await asyncio.sleep(0.2)

            return f"✓ 成功在 {element_description} 中输入了: {text}"

        except Exception as e:
            return f"输入操作失败: {str(e)}"

    async def _locate_and_scroll(self, direction: str = "down", distance: int = 500) -> str:
        """
        滚动页面

        Args:
            direction: 方向 ("up", "down", "top", "bottom")
            distance: 滚动距离（像素），仅当direction为up/down时有效

        Returns:
            str: 操作结果
        """
        browser = self._get_browser_adapter()
        tab = await browser.get_tab()

        try:
            success = await browser.scroll(tab, direction, distance)

            if success:
                return f"✓ 页面向{direction}滚动{distance if direction in ['up', 'down'] else ''}"
            else:
                return f"滚动失败"

        except Exception as e:
            return f"滚动操作失败: {str(e)}"

    async def _finish_task(self, result: str, summary: str = "") -> str:
        """
        完成任务并返回结果

        Args:
            result: 任务结果描述
            summary: 可选的任务总结

        Returns:
            str: 最终结果
        """
        final_msg = f"任务完成：{result}"
        if summary:
            final_msg += f"\n\n总结：{summary}"
        return final_msg

    # ================================================================
    # 辅助方法
    # ================================================================

    def _get_browser_adapter(self):
        """获取browser_adapter"""
        return getattr(self, 'browser_adapter', None)
