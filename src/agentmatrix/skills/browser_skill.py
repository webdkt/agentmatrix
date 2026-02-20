"""
Browser Skill - 浏览器自动化技能（新架构）

特点：
- 基于 browser-use 库
- self 始终指向 MicroAgent
- 简化版本，包含核心功能
"""

import asyncio
from typing import Optional
from pathlib import Path
from ..core.action import register_action
from .registry import register_skill


@register_skill("browser")
class BrowserSkillMixin:
    """
    Browser Automation Skill Mixin（新架构）

    提供：
    - browser_use: 使用 LLM 驱动浏览器执行任务
    """

    @register_action(
        description="使用浏览器自动化完成任务。适用于需要浏览器的复杂任务，如导航、搜索、点击、填表等。",
        param_infos={
            "task": "要执行的任务描述（自然语言）",
            "max_steps": "最大执行步数（默认15）"
        }
    )
    async def browser_use(
        self,
        task: str,
        max_steps: int = 15
    ) -> str:
        """
        使用浏览器自动化完成任务

        Args:
            task: 任务描述（如"打开 Google 搜索 Python"）
            max_steps: 最大执行步数

        Returns:
            str: 执行结果
        """
        from browser_use import Agent
        from browser_use.browser import Browser

        # ✅ 直接访问 self 的属性
        # 需要访问 root_agent 的配置（因为需要 LLM 配置）
        if not hasattr(self, 'root_agent'):
            return "错误：缺少 root_agent"

        root_agent = self.root_agent

        # 获取 LLM 配置路径
        try:
            config_path = self._get_llm_config_path(root_agent)
        except Exception as e:
            return f"错误：{e}"

        # 创建 browser-use Agent
        try:
            browser = Browser()
            agent = Agent(
                task=task,
                llm=self._get_browser_use_llm(config_path, root_agent),
                browser=browser,
                use_vision=True,
                max_steps=max_steps
            )

            # 执行
            result = await agent.run()

            # 清理
            await browser.close()

            return f"浏览器任务完成:\n{result}"

        except Exception as e:
            return f"浏览器任务失败: {e}"

    def _get_llm_config_path(self, root_agent) -> Path:
        """获取 llm_config.json 路径"""
        if not hasattr(root_agent, 'workspace_root') or not root_agent.workspace_root:
            raise ValueError("workspace_root 未设置")

        workspace_root_path = Path(root_agent.workspace_root)
        config_path = workspace_root_path.parent / "agents" / "llm_config.json"

        if not config_path.exists():
            raise FileNotFoundError(f"llm_config.json 不存在: {config_path}")

        return config_path

    def _get_browser_use_llm(self, config_path: Path, root_agent):
        """
        获取适合 browser-use 的 LLM 实例

        简化版：直接使用 runtime 的 LLM 服务
        """
        # TODO: 完整版本需要处理国产模型兼容性
        # 这里先简化，使用 runtime 的 LLM

        if not hasattr(root_agent, 'runtime') or not root_agent.runtime:
            raise ValueError("runtime 未设置")

        # 使用 runtime 的 LLM 服务
        # 注意：browser-use 需要特定的 LLM 接口
        # 这里简化处理，实际需要创建一个适配器

        return root_agent.runtime.llm_service.llm
