"""
测试搜索结果解析器

用法：
1. 将搜索引擎结果页的 HTML 保存到文件（如 google_search.html）
2. 运行测试：python tests/test_search_results_parser.py <html_file_path>
"""

import sys
import os
from pathlib import Path

# 添加 src 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.skills.search_results_parser import SearchResultsParser


def test_parse_html_file(html_file_path: str, search_url: str):
    """
    测试解析本地 HTML 文件

    Args:
        html_file_path: HTML 文件路径
        search_url: 模拟的搜索结果页 URL（用于判断搜索引擎）
    """
    print(f"\n{'='*80}")
    print(f"测试文件: {html_file_path}")
    print(f"模拟 URL: {search_url}")
    print(f"{'='*80}\n")

    # 读取 HTML 文件
    print("📂 读取 HTML 文件...")
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        print(f"✓ 文件读取成功，共 {len(html_content)} 字符")
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return

    # 创建解析器
    print("\n🔍 创建解析器...")

    # 创建简单的 logger
    import logging
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    logger = logging.getLogger(__name__)

    parser = SearchResultsParser(logger=logger)

    # 解析搜索结果
    print("\n⚙️  开始解析...")
    try:
        parsed_data = parser.parse(html_content, search_url)
        print(f"✓ 解析完成！")
    except Exception as e:
        print(f"❌ 解析失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 显示解析结果
    print(f"\n📊 解析结果统计:")
    print(f"  搜索引擎: {parsed_data['search_engine']}")
    print(f"  搜索结果数量: {len(parsed_data['results'])}")
    print(f"  有智能回答: {'是' if parsed_data['featured_snippet'] else '否'}")

    if parsed_data['featured_snippet']:
        print(f"\n📝 智能回答 (前200字符):")
        print(f"  {parsed_data['featured_snippet'][:200]}...")

    # 显示前3个搜索结果
    print(f"\n🔗 搜索结果 (前3条):")
    for idx, result in enumerate(parsed_data['results'][:3], start=1):
        print(f"\n  [{idx}] {result.link_id}")
        print(f"      标题: {result.title}")
        print(f"      URL: {result.url}")
        if result.site_info:
            print(f"      站点: {result.site_info}")
        if result.snippet:
            snippet_preview = result.snippet[:150] + "..." if len(result.snippet) > 150 else result.snippet
            print(f"      摘要: {snippet_preview}")

    # 生成格式化的 Markdown
    print(f"\n📝 格式化的 Markdown:")
    print(f"{'='*80}")
    formatted_markdown = parser.format_as_markdown(parsed_data)
    print(formatted_markdown)
    print(f"{'='*80}")

    # 显示链接映射
    print(f"\n🔗 链接映射 (前3条):")
    link_mapping = parser.build_link_mapping(parsed_data)
    for idx, (link_id, url) in enumerate(list(link_mapping.items())[:3], start=1):
        print(f"  [{idx}] {link_id}")
        print(f"      -> {url}")

    # 保存结果到文件
    output_file = html_file_path.replace('.html', '_parsed.txt')
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"=== 解析结果 ===\n\n")
            f.write(f"搜索引擎: {parsed_data['search_engine']}\n")
            f.write(f"搜索结果数量: {len(parsed_data['results'])}\n\n")
            f.write(f"=== 格式化的 Markdown ===\n\n")
            f.write(formatted_markdown)
            f.write(f"\n\n=== 链接映射 ===\n\n")
            for link_id, url in link_mapping.items():
                f.write(f"{link_id} -> {url}\n")
        print(f"\n💾 结果已保存到: {output_file}")
    except Exception as e:
        print(f"\n⚠️  保存结果失败: {e}")

    print(f"\n{'='*80}")
    print("✓ 测试完成！")
    print(f"{'='*80}\n")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python test_search_results_parser.py <html_file_path>")
        print("\n示例:")
        print("  python test_search_results_parser.py google_search.html")
        print("  python test_search_results_parser.py bing_search.html")
        print("\n提示:")
        print("  1. 在浏览器中打开搜索引擎（Google 或 Bing）")
        print("  2. 搜索任意内容")
        print("  3. 右键 -> 保存网页 -> 选择'网页，全部' -> 保存为 .html 文件")
        print("  4. 运行此测试脚本")
        sys.exit(1)

    html_file_path = sys.argv[1]

    # 检查文件是否存在
    if not os.path.exists(html_file_path):
        print(f"❌ 文件不存在: {html_file_path}")
        sys.exit(1)

    # 根据文件名判断搜索引擎
    filename = Path(html_file_path).name.lower()
    if 'google' in filename:
        search_url = "https://www.google.com/search?q=test"
    elif 'bing' in filename:
        search_url = "https://www.bing.com/search?q=test"
    else:
        # 默认使用 Google
        search_url = "https://www.google.com/search?q=test"
        print(f"⚠️  无法从文件名判断搜索引擎，默认使用 Google")

    # 运行测试
    test_parse_html_file(html_file_path, search_url)


if __name__ == "__main__":
    main()
