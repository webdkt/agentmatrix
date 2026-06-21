"""
SessionStore — Core 的消息持久化接口。

Core 不关心消息存在哪里、怎么存，只关心 load/save。
Shell 实现此接口（如包装 session dict + SessionManager）。
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class SessionStore(Protocol):
    """
    消息持久化接口 — Core 通过它读写对话历史。

    Shell 实现此接口，决定存储介质（磁盘、数据库、内存等）。

    session_id 属性：当前 session 的标识。MicroAgent 在 emit CoreEvent 时
    从这里读取并固化到事件上，避免消费者读到已被切换的 active_session_id。
    无 session 概念的实现（如 CLI 内存模式）返回 None。
    """

    @property
    def session_id(self) -> Optional[str]:
        """当前 session 的 id；无 session 概念时为 None。"""
        ...

    def load_messages(self) -> List[Dict]:
        """加载对话历史。返回 message dict 列表。"""
        ...

    async def save_messages(self, messages: List[Dict]) -> None:
        """保存对话历史。异步、不阻塞主流程。"""
        ...
