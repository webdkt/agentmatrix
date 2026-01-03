"""
公共浏览器数据结构和工具

为 data_crawler 和 web_searcher 等技能提供共享的数据结构。
"""

from dataclasses import dataclass, field
from typing import Deque
from collections import deque

from core.browser.browser_adapter import TabHandle


@dataclass
class TabSession:
    """
    物理标签页上下文 (Physical Tab Context)

    用于管理浏览器标签页的状态和待处理队列。
    被多个爬虫技能共享使用。
    """
    handle: TabHandle
    current_url: str = ""
    depth: int = 0
    pending_link_queue: Deque[str] = field(default_factory=deque)
