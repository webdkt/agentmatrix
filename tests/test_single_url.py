#!/usr/bin/env python3
"""
单独测试特定URL的导航页判断
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


async def test_single_url(url: str):
    """单独测试一个URL"""

    print("=" * 80)
    print(f"测试URL: {url}")
    print("=" * 80)

    profile_path = os.path.join(os.path.dirname(__file__), "..", ".matrix", "browser_profile", "test_single")

    adapter = DrissionPageAdapter(profile_path=profile_path, download_path=os.getcwd())

    tester = NavigationTester()

    try:
        print(f"\n1. 启动浏览器...")
        await adapter.start(headless=False)

        print(f"\n2. 导航到URL...")
        tab = await adapter.get_tab()
        await adapter.navigate(tab, url)
        await asyncio.sleep(3)  # 等待页面加载

        # 获取URL信息
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        path = parsed_url.path
        print(f"\n   URL信息:")
        print(f"      完整URL: {url}")
        print(f"      Path: '{path}'")
        print(f"      Path长度: {len(path)}")

        # 检查 Open Graph
        print(f"\n3. 检查 Open Graph 标签:")
        try:
            og_type_tag = tab.ele('css:meta[property="og:type"]', timeout=2)
            if og_type_tag:
                og_content = og_type_tag.attr('content')
                print(f"      找到 og:type = '{og_content}'")
            else:
                print(f"      未找到 og:type 标签")
        except Exception as e:
            print(f"      检查 og:type 时出错: {e}")

        # 检查页面文本和链接
        print(f"\n4. 检查页面文本和链接:")
        try:
            all_text = tab.text.strip()
            total_length = len(all_text)
            print(f"      页面总文本长度: {total_length} 字符")

            if total_length > 0:
                link_elements = tab.eles('tag:a')
                link_text_length = 0
                print(f"      找到 {len(link_elements)} 个链接")

                for i, link in enumerate(link_elements[:5]):
                    try:
                        link_text = link.text.strip()
                        link_text_length += len(link_text)
                        if i < 5:
                            print(f"         链接{i+1}: '{link_text[:50]}...' ({len(link_text)}字符)")
                    except:
                        continue

                link_density = link_text_length / total_length
                print(f"\n      链接文本总长度: {link_text_length} 字符")
                print(f"      链接密度: {link_density:.1%}")
                print(f"      是否 >30%: {'是' if link_density > 0.3 else '否'}")
                print(f"      总字数是否很少(<500): {'是' if total_length < 500 else '否'}")

        except Exception as e:
            print(f"      检查链接密度时出错: {e}")

        # 最终判断
        print(f"\n5. 最终判断:")
        is_nav, reason = await tester.is_navigation_page(tab, url)
        print(f"      判断结果: {'✓ 导航页' if is_nav else '✗ 内容页'}")
        print(f"      判断原因: {reason}")

        print(f"\n6. 按 Ctrl+C 退出...")

        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print(f"\n测试结束")


if __name__ == "__main__":
    # 测试新华网政治频道
    test_url = "https://www.news.cn/politics/index.html"

    try:
        asyncio.run(test_single_url(test_url))
    except KeyboardInterrupt:
        print(f"\n\n✓ 测试结束")
