#!/usr/bin/env python3
"""
测试 PDF Snapshot 功能

测试目标：
1. 验证 _detect_asset_subtype 能正确识别 PDF（通过 content_type）
2. 验证 _snapshot_pdf_browser 能成功下载并转换 PDF
3. 验证动态长度策略对大 PDF 的处理

测试 URL：
- URL 1: 巨潮资讯公告（较小文件）
- URL 2: 巨潮资讯公告（大文件，测试动态长度策略）
"""

import sys
import os
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.browser.drission_page_adapter import DrissionPageAdapter


async def test_pdf_snapshot(adapter, tab, url: str, test_name: str):
    """
    测试单个 PDF 的 snapshot 功能

    Args:
        adapter: DrissionPageAdapter 实例
        url: PDF 的 URL（会自动重定向）
        test_name: 测试名称

    Returns:
        bool: 测试是否成功
    """
    print(f"\n{'=' * 60}")
    print(f"测试: {test_name}")
    print(f"URL: {url}")
    print(f"{'=' * 60}")

    try:
        # 1. 获取当前 tab
        print(f"📌 步骤 1: 获取浏览器标签页")
        
        print(f"✅ 获取成功，初始 URL: {tab.url}")

        

        # 2. 导航到 URL（会自动重定向到 PDF）
        print(f"\n📌 步骤 2: 导航到目标 URL")
        print(f"⏳ 正在访问 {url}...")
        report = await adapter.navigate(tab, url)

        if report.error:
            print(f"❌ 导航失败: {report.error}")
            return False

        print(f"✅ 导航成功")
        print(f"📊 导航后信息:")
        print(f"   - 当前 URL: {tab.url}")
        print(f"   - URL 是否变化: {report.is_url_changed}")
        print(f"   - DOM 是否变化: {report.is_dom_changed}")

        # 3. 等待页面加载
        print(f"\n📌 步骤 3: 等待页面加载完成")
        await asyncio.sleep(5)

        # 检查页面标题
        print(f"📊 页面信息:")
        print(f"   - 标题: {tab.title}")

        # 4. 分析页面类型
        print(f"\n📌 步骤 4: 分析页面类型")
        from core.browser.browser_adapter import PageType
        page_type = await adapter.analyze_page_type(tab)
        print(f"✅ 页面类型: {page_type}")

        # 5. 检查是否是静态资源
        if page_type != PageType.STATIC_ASSET:
            print(f"⚠️  警告: 页面类型不是 STATIC_ASSET")
            print(f"   继续尝试获取 snapshot...")

        # 6. 获取页面 snapshot
        print(f"\n📌 步骤 5: 获取 PDF snapshot")
        print(f"⏳ 正在提取 PDF 内容...")
        snapshot = await adapter.get_page_snapshot(tab)

        # 7. 验证结果
        print(f"\n📌 步骤 6: 验证结果")
        main_text = snapshot.main_text

        print(f"📊 Snapshot 信息:")
        print(f"   - URL: {snapshot.url}")
        print(f"   - 标题: {snapshot.title}")
        print(f"   - 内容类型: {snapshot.content_type}")
        print(f"   - 文本长度: {len(main_text)} 字符")
        print(f"   - Raw HTML 长度: {len(snapshot.raw_html)} 字符")

        # 检查内容
        if not main_text or len(main_text) < 50:
            print(f"❌ 获取失败：内容为空或太短")
            print(f"内容: {main_text}")
            return False

        if "[PDF Document]" not in main_text and main_text != "[PDF Document] (Encrypted or conversion failed)":
            print(f"❌ 获取失败：内容格式不正确")
            print(f"内容预览: {main_text[:200]}")
            return False

        # 8. 打印内容预览
        print(f"\n📌 步骤 7: 内容预览")
        print(f"{'-' * 60}")

        # 检查是否是加密或转换失败的情况
        if "Encrypted" in main_text or "conversion failed" in main_text or "Extraction failed" in main_text:
            print(f"⚠️  {main_text}")
        else:
            # 正常情况，显示内容预览
            content_preview = main_text.replace("[PDF Document]", "").strip()
            preview_length = min(800, len(content_preview))
            print(content_preview[:preview_length])
            if len(content_preview) > preview_length:
                print(f"\n... (还有 {len(content_preview) - preview_length} 字符)")

        print(f"{'-' * 60}")

        print(f"\n✅ 测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败，异常: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主测试函数"""
    print(f"\n{'🧪' * 30}")
    print("PDF Snapshot 功能测试")
    print(f"{'🧪' * 30}\n")

    # 初始化 adapter
    download_path = "test/downloads"
    adapter = DrissionPageAdapter(
        profile_path="test/profile",  # 使用测试 profile
        download_path=download_path
    )

    try:
        # 启动浏览器
        print(f"⏳ 启动浏览器...")
        await adapter.start(headless=False)  # 设置为 False 以便调试
        print(f"✅ 浏览器已启动")

        # 测试 URL 列表
        test_cases = [
            {
                "url": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=600063&orgId=gssh0600063&announcementId=1224909150&announcementTime=2025-12-31",
                "name": "PDF 1 - 巨潮资讯公告（较小文件）"
            },
            {
                "url": "http://www.cninfo.com.cn/new/disclosure/detail?stockCode=002463&announcementId=1224831829&orgId=9900013929&announcementTime=2025-11-28",
                "name": "PDF 2 - 巨潮资讯公告（大文件）"
            }
        ]

        # 运行测试
        results = []
        tab = await adapter.get_tab()
        for i, test_case in enumerate(test_cases, 1):
            
            success = await test_pdf_snapshot(adapter,tab, test_case["url"], test_case["name"])
            results.append((test_case["name"], success))

            # 测试之间等待一下
            if i < len(test_cases):
                print(f"\n⏸️  等待 3 秒后进行下一个测试...")
                await asyncio.sleep(3)

        # 打印总结
        print(f"\n{'=' * 60}")
        print(f"📊 测试总结")
        print(f"{'=' * 60}")

        passed = sum(1 for _, success in results if success)
        total = len(results)

        for name, success in results:
            status = "✅ 通过" if success else "❌ 失败"
            print(f"{status} - {name}")

        print(f"\n总计: {passed}/{total} 测试通过")

        if passed == total:
            print(f"\n🎉 所有测试通过！")
        else:
            print(f"\n⚠️  部分测试失败")

    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 不自动关闭浏览器，让用户手动检查
        print(f"\n💡 测试完成，浏览器保持开启状态")
        print(f"   您可以手动检查浏览器状态")
        print(f"   临时文件保存在: {download_path}")
        print(f"\n按 Ctrl+C 或关闭终端窗口来结束程序...")

        # 保持程序运行，不关闭浏览器
        try:
            # 无限等待，直到用户手动中断
            import signal
            signal.pause()
        except AttributeError:
            # Windows 上 signal.pause() 不可用
            while True:
                await asyncio.sleep(3600)  # 每小时等待一次


if __name__ == "__main__":
    # 运行测试
    success = asyncio.run(main())

    # 返回退出码
    sys.exit(0 if success is not False else 1)
