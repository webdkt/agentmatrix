"""
CLI Session — 内存 SessionStore 实现。

对话历史只存在内存中，退出即丢失。
"""

from typing import Dict, List


class InMemorySessionStore:
    """内存 SessionStore — 不持久化，退出即丢失。"""

    def __init__(self):
        self._messages: List[Dict] = []

    def load_messages(self) -> List[Dict]:
        return self._messages.copy()

    async def save_messages(self, messages: List[Dict]) -> None:
        self._messages = messages.copy()

    def clear(self):
        self._messages.clear()
