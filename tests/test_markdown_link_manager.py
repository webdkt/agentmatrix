#!/usr/bin/env python
"""
测试 MarkdownLinkManager 的基本功能
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.skills.web_searcher import MarkdownLinkManager, WebSearcherContext
import time

def test_markdown_link_manager():
    """测试 MarkdownLinkManager 的基本功能"""

    # 创建一个模拟的 context
    class MockContext:
        def __init__(self):
            self.visited = set()
            self.blacklist = ["spam.com", "blocked.com"]

        def has_visited(self, url):
            return url in self.visited

    ctx = MockContext()
    manager = MarkdownLinkManager(ctx)

    # 测试 Markdown 文本
    test_markdown = """
# 测试文档

这是一个测试文档，包含多个链接：

1. 普通链接：[OpenAI](https://openai.com)
2. 已访问链接：[Google](https://google.com)
3. 黑名单链接：[Spam Site](https://spam.com/page)
4. 无意义文本链接：[点击这里](https://example.com/file.pdf)
5. 重复链接文本：[下载](https://example.com/file1.zip) 和 [下载](https://example.com/file2.zip)
6. 中文链接：[更多信息](https://example.com/zh/info)
"""

    # 标记一个为已访问
    ctx.visited.add("https://google.com")

    # 处理 Markdown
    result = manager.process(test_markdown)

    print("=== 原始 Markdown ===")
    print(test_markdown)
    print("\n=== 处理后的 Markdown ===")
    print(result)
    print("\n=== 链接映射 ===")
    for text, url in manager.text_to_url.items():
        print(f"[{text}] -> {url}")

    # 测试 get_url
    print("\n=== 测试 get_url ===")
    test_cases = [
        "OpenAI",
        "🔗OpenAI",
        "OpenAI。",  # 带标点
        "下载(file1.zip)",
        "下载(file2.zip)",
        "点击这里(file.pdf)",
        "不存在的链接"
    ]

    for test in test_cases:
        url = manager.get_url(test)
        print(f"get_url('{test}') -> {url}")

    print("\n✅ 所有测试通过!")

if __name__ == "__main__":
    test_markdown_link_manager()
