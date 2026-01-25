#!/usr/bin/env python
"""
更详细地测试 trafilatura 的输出格式
"""

import trafilatura

# 测试 HTML
test_html = """
<html>
<body>
    <h1>Test Page</h1>
    <p>Check out <a href="https://example.com/page1">this link</a> and <a href="https://example.com/page2">that link</a>.</p>
    <p>More info at <a href="https://example.com/info">Info Page</a>.</p>
</body>
</html>
"""

print("=== Test 1: 默认参数 (include_links=True) ===")
md1 = trafilatura.extract(test_html, include_links=True, output_format='markdown')
print(repr(md1))
print(md1)
print()

print("=== Test 2: include_links=False ===")
md2 = trafilatura.extract(test_html, include_links=False, output_format='markdown')
print(repr(md2))
print(md2)
print()

print("=== Test 3: 使用 raw 参数 ===")
# 尝试获取更原始的输出
md3 = trafilatura.extract(test_html, include_links=True, output_format='markdown', raw=True)
print(repr(md3))
print(md3)
