"""
公共浏览器数据结构和工具

为 data_crawler 和 web_searcher 等技能提供共享的数据结构。
"""

import time
from abc import ABC
from dataclasses import dataclass, field
from typing import Deque, Set, List
from collections import deque

from ...core.browser.browser_adapter import TabHandle


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


class BaseCrawlerContext(ABC):
    """
    爬虫上下文基类
    提供公共的状态管理和历史记录功能。
    """

    def __init__(self, deadline: float):
        self.deadline = deadline
        self.visited_urls: Set[str] = set()
        self.interaction_history: Set[str] = set()
        self.assessed_links: Set[str] = set()
        self.assessed_buttons: Set[str] = set()
        self.blacklist: Set[str] = {
            "facebook.com", "twitter.com", "instagram.com",
            "taobao.com", "jd.com", "amazon.com",
            "signin", "login", "signup"
        }

    def __repr__(self):
        return f"{self.__class__.__name__}(deadline={self.deadline}, visited={len(self.visited_urls)})"

    def is_time_up(self) -> bool:
        return time.time() > self.deadline

    def mark_visited(self, url: str):
        self.visited_urls.add(url)

    def has_visited(self, url: str) -> bool:
        return url in self.visited_urls

    def mark_interacted(self, url: str, button_text: str):
        key = f"{url}|{button_text}"
        self.interaction_history.add(key)

    def has_interacted(self, url: str, button_text: str) -> bool:
        key = f"{url}|{button_text}"
        return key in self.interaction_history

    def mark_link_assessed(self, url: str):
        """标记链接为已评估（默认：内存版本）"""
        self.assessed_links.add(url)

    def has_link_assessed(self, url: str) -> bool:
        """检查链接是否已评估"""
        return url in self.assessed_links

    def mark_buttons_assessed(self, url: str, button_texts: List[str]):
        """批量标记按钮为已评估（默认：内存版本）"""
        for button_text in button_texts:
            key = f"{url}|{button_text}"
            self.assessed_buttons.add(key)

    def has_button_assessed(self, url: str, button_text: str) -> bool:
        """检查按钮是否已评估"""
        key = f"{url}|{button_text}"
        return key in self.assessed_buttons
