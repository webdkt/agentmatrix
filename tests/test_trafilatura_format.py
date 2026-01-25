#!/usr/bin/env python
"""
测试 trafilatura 实际输出的 Markdown 链接格式
"""

import trafilatura

# 测试 HTML（包含各种链接）
test_html = """
<html>
<body>
    <h1>测试页面</h1>
    <p>这是一个内联链接：<a href="https://example.com/page1">Example Page 1</a></p>
    <p>这是另一个链接：<a href="https://example.com/page2">Example Page 2</a></p>
    <p>带参数的链接：<a href="https://example.com/search?q=test&lang=en">Search</a></p>
    <p>相对路径链接：<a href="/relative/path">Relative</a></p>
    <ul>
        <li><a href="https://example.com/item1">Item 1</a></li>
        <li><a href="https://example.com/item2">Item 2</a></li>
    </ul>
</body>
</html>
"""

# 使用 trafilatura 转换
markdown = trafilatura.extract(
    test_html,
    include_links=True,
    output_format='markdown'
)

print("=== Trafilatura 输出的 Markdown ===")
print(markdown)
