#!/usr/bin/env python3
"""
测试导航页判断和 jina.ai API
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.core.browser.drission_page_adapter import DrissionPageAdapter
from agentmatrix.skills.crawler_helpers import CrawlerHelperMixin


class NavigationTester(CrawlerHelperMixin):
    """测试类，继承 CrawlerHelperMixin 来使用辅助方法"""

    def __init__(self):
        # 需要 cerebellum 和 logger 属性，这里简单初始化
        class MockCerebellum:
            class MockBackend:
                async def think(self, messages):
                    return {"reply": "mock response"}
            backend = MockBackend()

        self.cerebellum = MockCerebellum()

        import logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)


async def test_navigation_detection_and_jina():
    """测试导航页判断和 jina.ai API"""

    print("=" * 80)
    print("测试导航页判断和 jina.ai API")
    print("=" * 80)

    # 测试URL列表
    test_urls = [
        ("https://www.xinhuanet.com/", "新华网首页（预期：导航页）"),
        ("https://www.news.cn/politics/index.html", "新华网政治频道（预期：导航页）"),
        ("http://www.people.com.cn/", "人民网首页（预期：导航页）"),
        ("http://finance.people.com.cn/", "人民网财经频道（预期：导航页）"),
    ]

    profile_path = os.path.join(os.path.dirname(__file__), "..", ".matrix", "browser_profile", "test_navigation")

    adapter = DrissionPageAdapter(profile_path=profile_path, download_path=os.getcwd())

    tester = NavigationTester()

    try:
        print(f"\n1. 启动浏览器...")
        await adapter.start(headless=False)

        for url, description in test_urls:
            print(f"\n{'=' * 80}")
            print(f"测试: {description}")
            print(f"URL: {url}")
            print(f"{'-' * 80}")

            # 导航到URL
            tab = await adapter.get_tab()
            await adapter.navigate(tab, url)
            await asyncio.sleep(3)  # 等待页面加载

            # 测试1: 判断是否为导航页
            print(f"\n【测试1】判断是否为导航页")
            is_nav, reason = await tester.is_navigation_page(tab, url)
            print(f"   结果: {'✓ 导航页' if is_nav else '✗ 内容页'}")
            print(f"   原因: {reason}")

            # 测试2: 使用 jina.ai 获取 markdown
            print(f"\n【测试2】使用 jina.ai 获取 Markdown")
            try:
                print(f"   正在请求 jina.ai API...")
                markdown = await tester.get_markdown_via_jina(url, timeout=30)

                print(f"   ✓ 成功获取 Markdown")
                print(f"   Markdown 长度: {len(markdown)} 字符")
                print(f"   Markdown 预览（前200字符）:")
                print(f"   {markdown[:200]}...")

                # 测试3: 提取导航链接
                print(f"\n【测试3】从 Markdown 中提取导航链接")
                links = tester.extract_navigation_links(markdown)
                print(f"   提取到 {len(links)} 个链接")

                if links:
                    print(f"   前5个链接:")
                    for i, (link_url, link_text) in enumerate(links[:5]):
                        print(f"      {i+1}. [{link_text}]({link_url})")
                else:
                    print(f"   ⚠️  未找到链接")

            except Exception as e:
                print(f"   ✗ jina.ai 获取失败: {e}")

            print(f"\n等待3秒后测试下一个...")
            await asyncio.sleep(3)

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print(f"\n" + "=" * 80)
        print(f"测试完成。浏览器将保持打开供你查看...")
        print(f"按 Ctrl+C 退出脚本")
        print("=" * 80)

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print(f"\n\n✓ 测试结束")


if __name__ == "__main__":
    asyncio.run(test_navigation_detection_and_jina())
