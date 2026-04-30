"""
Core Interfaces for AgentMatrix Framework

Protocol classes for brain (LLM) and cerebellum (parameter parsing).
Third-party applications can implement these interfaces to customize behavior.
"""

from __future__ import annotations
from typing import Dict, List, Any, Protocol, runtime_checkable


@runtime_checkable
class BrainProtocol(Protocol):
    """LLM 客户端接口。负责思考和生成回复。"""

    async def think(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, str]:
        """单次 LLM 调用。"""
        ...

    async def think_with_retry(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, str]:
        """带重试的 LLM 调用。"""
        ...


@runtime_checkable
class CerebellumProtocol(Protocol):
    """参数解析器接口。负责从 LLM 意图中提取 action 参数。"""

    @property
    def backend(self) -> BrainProtocol:
        """底层 LLM 客户端（用于参数解析时的思考）。"""
        ...

    async def think(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, str]:
        """委托给 backend 的 think。"""
        ...

    async def convert_params(
        self,
        action_name: str,
        user_params: dict,
        param_schema: dict,
        brain_callback: Any = None,
    ) -> dict:
        """参数名对齐 + 补齐缺失的必要参数。"""
        ...
