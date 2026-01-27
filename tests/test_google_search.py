#!/usr/bin/env python3
"""
测试 Google 搜索功能的独立脚本

使用方法：
    python test_google_search.py                    # 使用默认搜索词
    python test_google_search.py "your search query"  # 使用自定义搜索词
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.core.browser.drission_page_adapter import DrissionPageAdapter
from agentmatrix.core.browser.google import search_google


async def test_google_search(query: str = "Python programming"):
    """测试 Google 搜索功能

    Args:
        query: 搜索关键词
    """

    print("=" * 60)
    print("测试 Google 搜索功能")
    print("=" * 60)

    # 初始化浏览器适配器
    profile_path = os.path.join(os.path.dirname(__file__), "..", ".matrix", "browser_profile", "test_google")
    download_path = os.path.join(os.path.dirname(__file__), "..", "test_downloads")

    print(f"\n1. 初始化浏览器...")
    print(f"   Profile path: {profile_path}")
    print(f"   Download path: {download_path}")

    adapter = DrissionPageAdapter(
        profile_path=profile_path,
        download_path=download_path
    )

    try:
        # 启动浏览器
        print(f"\n2. 启动浏览器...")
        await adapter.start(headless=False)  # headless=False 可以看到浏览器操作

        # 获取或创建标签页
        print(f"\n3. 创建标签页...")
        tab = await adapter.get_tab()

        # 测试搜索
        test_query = query
        print(f"\n4. 执行搜索测试...")
        print(f"   搜索词: '{test_query}'")
        print(f"   " + "-" * 50)

        success = await search_google(
            adapter=adapter,
            tab=tab,
            query=test_query,
            max_pages=1
        )

        print(f"   " + "-" * 50)
        if success:
            print(f"\n✅ 搜索成功！")

            # 获取当前 URL 验证
            current_url = adapter.get_tab_url(tab)
            print(f"   当前 URL: {current_url}")

            # 检查是否在搜索结果页
            if "google.com/search" in current_url:
                print(f"   ✅ 确认：浏览器已停在搜索结果页")
            else:
                print(f"   ⚠️  警告：URL 可能不是搜索结果页")

        else:
            print(f"\n❌ 搜索失败")

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 等待用户查看结果
        print(f"\n" + "=" * 60)
        print(f"测试完成。浏览器将保持打开供你查看...")
        print(f"按 Ctrl+C 退出脚本（浏览器将继续运行）")
        print("=" * 60)

        # 不自动关闭，让用户手动操作
        print(f"\n✓ 浏览器保持打开状态")


if __name__ == "__main__":
    # 从命令行参数获取搜索词，如果没有则使用默认值
    query = sys.argv[1] if len(sys.argv) > 1 else "Python programming"

    try:
        asyncio.run(test_google_search(query))
    except KeyboardInterrupt:
        print(f"\n\n✓ 脚本已退出")
