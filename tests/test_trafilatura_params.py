#!/usr/bin/env python
"""
清晰测试 trafilatura 的所有参数组合
"""

import trafilatura

# 测试 HTML
test_html = """
<html>
<body>
    <h1>Test Page</h1>
    <p>This is a paragraph with a <a href="https://example.com/page1">link to page 1</a> in the middle.</p>
    <p>Another paragraph with <a href="https://example.com/page2">another link</a>.</p>
    <ul>
        <li>Item with <a href="https://example.com/item1">link 1</a></li>
        <li>Item with <a href="https://example.com/item2">link 2</a></li>
    </ul>
</body>
</html>
"""

print("=" * 80)
print("测试所有参数组合")
print("=" * 80)

# 组合 1: include_links=True, include_formatting=True
print("\n【组合 1】include_links=True, include_formatting=True, output_format='markdown'")
print("-" * 80)
result1 = trafilatura.extract(
    test_html,
    include_links=True,
    include_formatting=True,
    output_format='markdown'
)
print("输出内容:")
print(result1)
print("\n输出 repr:")
print(repr(result1))

# 检查是否包含标准 Markdown 链接
import re
links1 = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', result1)
print(f"\n✓ 找到 {len(links1)} 个标准 Markdown 链接 [text](url)")
if links1:
    for text, url in links1:
        print(f"  [{text}]({url})")

# 组合 2: include_links=True, include_formatting=False
print("\n" + "=" * 80)
print("【组合 2】include_links=True, include_formatting=False, output_format='markdown'")
print("-" * 80)
result2 = trafilatura.extract(
    test_html,
    include_links=True,
    include_formatting=False,
    output_format='markdown'
)
print("输出内容:")
print(result2)
print("\n输出 repr:")
print(repr(result2))

links2 = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', result2)
print(f"\n✓ 找到 {len(links2)} 个标准 Markdown 链接 [text](url)")
if links2:
    for text, url in links2:
        print(f"  [{text}]({url})")

# 组合 3: include_links=True, output_format='txt'
print("\n" + "=" * 80)
print("【组合 3】include_links=True, output_format='txt'")
print("-" * 80)
result3 = trafilatura.extract(
    test_html,
    include_links=True,
    output_format='txt'
)
print("输出内容:")
print(result3)
print("\n输出 repr:")
print(repr(result3))

# 组合 4: include_links=False, output_format='markdown'
print("\n" + "=" * 80)
print("【组合 4】include_links=False, output_format='markdown'")
print("-" * 80)
result4 = trafilatura.extract(
    test_html,
    include_links=False,
    output_format='markdown'
)
print("输出内容:")
print(result4)
print("\n输出 repr:")
print(repr(result4))

# 总结
print("\n" + "=" * 80)
print("【总结】")
print("=" * 80)
print(f"组合1 (links=True, formatting=True, markdown): 找到 {len(links1)} 个标准链接")
print(f"组合2 (links=True, formatting=False, markdown): 找到 {len(links2)} 个标准链接")

if len(links1) > 0 or len(links2) > 0:
    print("\n✅ trafilatura 可以生成标准 Markdown 链接格式")
    print("   推荐使用的参数组合：")
    if len(links1) > 0:
        print("   - include_links=True, include_formatting=True, output_format='markdown'")
    if len(links2) > 0:
        print("   - include_links=True, include_formatting=False, output_format='markdown'")
else:
    print("\n❌ trafilatura 无法生成标准 Markdown 链接格式")
    print("   需要考虑其他解决方案")
