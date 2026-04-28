"""
AgentShell — Agent 的外层壳接口。

Agent = AgentShell + AgentCore（一对一）
不同应用形态实现这个接口，Core 通过它与外部世界交互。
"""

from __future__ import annotations
from typing import Protocol, runtime_checkable


@runtime_checkable
class AgentShell(Protocol):
    """
    AgentCore 的宿主接口。

    现在是空壳，方法会随重构逐步添加。
    """
    pass
