"""
AgentShell — Agent 的外层壳接口。

Agent = AgentShell + AgentCore（一对一）
不同应用形态实现这个接口，Core 通过它与外部世界交互。
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable

from .interfaces import BrainProtocol, CerebellumProtocol


@runtime_checkable
class AgentShell(Protocol):
    """
    AgentCore 的宿主接口。

    不同应用形态实现这个接口，Core 通过它与外部世界交互。
    """

    brain: BrainProtocol
    cerebellum: CerebellumProtocol

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
