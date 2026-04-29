"""
AgentShell — Agent 的外层壳接口。

Agent = AgentShell + AgentCore（一对一）
不同应用形态实现这个接口，Core 通过它与外部世界交互。
"""

from __future__ import annotations
import logging
from typing import List, Dict, Protocol, runtime_checkable

from .interfaces import BrainProtocol, CerebellumProtocol


@runtime_checkable
class AgentShell(Protocol):
    """
    AgentCore 的宿主接口。

    不同应用形态实现这个接口，Core 通过它与外部世界交互。
    """

    brain: BrainProtocol
    cerebellum: CerebellumProtocol
    logger: logging.Logger

    def get_prompt_template(self, name: str) -> str:
        """获取 prompt 模板。

        Core 通过此方法访问模板，不直接接触文件系统或配置。
        不同 Shell 实现可以用不同方式加载模板（文件系统、数据库、内存等）。

        Args:
            name: 模板名称（如 "SYSTEM_PROMPT", "CORE_PROMPT"）

        Returns:
            模板文本
        """
        ...

    async def generate_working_notes(
        self, messages: List[Dict[str, str]], focus_hint: str = ""
    ) -> str:
        """从对话历史生成 Working Notes（工作笔记）。

        不同 Shell 实现可根据通信模式定制 prompt（邮件、聊天、纯任务等）。

        Args:
            messages: 当前对话历史
            focus_hint: 可选，指导 LLM 重点关注某方面

        Returns:
            Markdown 格式的 Working Notes
        """
        ...
