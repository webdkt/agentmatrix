import trafilatura
import re

# 模拟 Google 搜索结果页的 HTML（较长内容）
test_html = """
<html>
<body>
    <h1>2024年财务报告分析</h1>
    <p>完全没有阿萨德理解；阿身份获取文凭后i我企鹅返回为后期和晚饭后额外前后i和未婚夫会去外婆额返回哦额问候哦好微风ji
saofhadsoifhasflh
asdhfhoiw woehoohwef  weohowehfo
weoihjoiwehfo wehfwehfl
sdohfohwe f太奇怪了胎气挂了是v哦我好我哦好0话费可靠090号是一个非常重要的内联链接：<a href="https://example.com/page1">点击查看详情</a>。正文内容通常需要有一定的长度，才能被提取器识别为核心内容。</p>

    <p>随着经济的发展，我们观察到了很多有趣的现象。这些现象在我们的<a href="https://example.com/page2">年度总结页面</a>中有详细描述。trafilatura 依靠文本块的长度和链接密度来判断什么是正文，什么是导航。</p>

    <p>如果是孤立的链接列表，如下所示，通常会被当作导航栏处理，除非它们嵌在很长的文本中间：</p>
    <ul>
        <li><a href="https://example.com/item1">参考资料 1</a> - 这里的文字稍微多一点可能有助于保留。</li>
        <li><a href="https://example.com/item2">参考资料 2</a></li>
        <li><a href="https://translate.google.com/translate?hl=en&sl=auto&tl=zh-CN&u=https://example.com/item2">翻译此页</a></li>
    </ul>

    <p>更多内容请查看相关文档。这里还有一些干扰链接：<a href="https://translate.google.com/translate?u=https://example.com/page1">Translate this page</a></p>
</body>
</html>
"""

print("=" * 80)
print("【测试 1】不预处理（原始 HTML）")
print("=" * 80)
markdown1 = trafilatura.extract(
    test_html,
    include_links=True,
    output_format='markdown',
    url="https://www.google.com/search"  # 模拟 Google 搜索页面
)
print(markdown1)
print("\n链接统计：")
links1 = re.findall(r'\[([^\]]+)\]\((https?://[^)]+)\)', markdown1)
print(f"找到 {len(links1)} 个链接")
for text, url in links1:
    print(f"  [{text}]({url})")

print("\n" + "=" * 80)
print("【测试 2】预处理后（移除 Google 翻译链接）")
print("=" * 80)

# 预处理：移除 Google 翻译链接
processed_html = test_html
processed_html = re.sub(
    r'<a\s+[^>]*href="https://translate\.google\.com[^"]*"[^>]*>.*?</a>',
    '',
    processed_html,
    flags=re.IGNORECASE | re.DOTALL
)
processed_html = re.sub(
    r"<a\s+[^>]*href='https://translate\.google\.com[^']*'[^>]*>.*?</a>",
    '',
    processed_html,
    flags=re.IGNORECASE | re.DOTALL
)

markdown2 = trafilatura.extract(
    processed_html,
    include_links=True,
    output_format='markdown',
    url="https://www.google.com/search"
)
print(markdown2)
print("\n链接统计：")
links2 = re.findall(r'\[([^\]]+)\]\((https?://[^)]+)\)', markdown2)
print(f"找到 {len(links2)} 个链接")
for text, url in links2:
    print(f"  [{text}]({url})")

print("\n" + "=" * 80)
print("【对比】")
print("=" * 80)
print(f"原始 HTML 中的链接数: {len(links1)}")
print(f"预处理后的链接数: {len(links2)}")

# 检查是否还有翻译链接
has_translate_in_original = any('translate.google.com' in url for _, url in links1)
has_translate_in_processed = any('translate.google.com' in url for _, url in links2)

print(f"\n原始输出中包含翻译链接: {has_translate_in_original}")
print(f"预处理后包含翻译链接: {has_translate_in_processed}")

if has_translate_in_original and not has_translate_in_processed:
    print("\n✅ 成功！预处理有效移除了翻译链接")
elif not has_translate_in_original:
    print("\n✅ 原本就没有翻译链接（可能被 trafilatura 过滤了）")
else:
    print("\n❌ 预处理失败，翻译链接仍然存在")
