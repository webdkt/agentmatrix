#!/usr/bin/env python3
"""
探索 Google 首页结构的脚本
"""
import asyncio
import sys
import os
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from agentmatrix.core.browser.drission_page_adapter import DrissionPageAdapter


async def explore_google():
    """探索 Google 首页结构"""

    print("=" * 60)
    print("探索 Google 首页结构")
    print("=" * 60)

    # 初始化浏览器适配器
    profile_path = os.path.join(os.path.dirname(__file__), "..", ".matrix", "browser_profile", "explore_google")

    adapter = DrissionPageAdapter(
        profile_path=profile_path,
        download_path=os.getcwd()
    )

    try:
        # 启动浏览器
        print(f"\n1. 启动浏览器...")
        await adapter.start(headless=False)

        # 获取标签页
        tab = await adapter.get_tab()

        # 导航到 Google 首页
        print(f"\n2. 导航到 Google 首页...")
        await adapter.navigate(tab, "https://www.google.com")
        time.sleep(3)

        # 稳定化
        print(f"\n3. 稳定化页面...")
        await adapter.stabilize(tab)
        time.sleep(2)

        # 探索输入元素
        print(f"\n4. 探索输入和文本域元素...")

        try:
            all_inputs = tab.eles('tag:input')
            print(f"   Found {len(all_inputs)} input elements")
            for i, inp in enumerate(all_inputs[:10]):  # 只显示前10个
                try:
                    name = inp.attr('name') or 'None'
                    inp_type = inp.attr('type') or 'None'
                    inp_id = inp.attr('id') or 'None'
                    inp_class = inp.attr('class') or 'None'
                    print(f"      Input {i+1}: name={name}, type={inp_type}, id={inp_id}, class={inp_class}")
                except Exception as e:
                    print(f"      Input {i+1}: Error getting attributes: {e}")
        except Exception as e:
            print(f"   Error finding inputs: {e}")

        try:
            all_textareas = tab.eles('tag:textarea')
            print(f"\n   Found {len(all_textareas)} textarea elements")
            for i, txt in enumerate(all_textareas):
                try:
                    name = txt.attr('name') or 'None'
                    txt_id = txt.attr('id') or 'None'
                    txt_class = txt.attr('class') or 'None'
                    placeholder = txt.attr('placeholder') or 'None'
                    print(f"      Textarea {i+1}: name={name}, id={txt_id}, class={txt_class}, placeholder={placeholder}")
                except Exception as e:
                    print(f"      Textarea {i+1}: Error getting attributes: {e}")
        except Exception as e:
            print(f"   Error finding textareas: {e}")

        # 探索搜索按钮
        print(f"\n5. 探索搜索按钮...")

        try:
            all_buttons = tab.eles('tag:button')
            print(f"   Found {len(all_buttons)} button elements")
            for i, btn in enumerate(all_buttons[:10]):  # 只显示前10个
                try:
                    btn_type = btn.attr('type') or 'None'
                    btn_name = btn.attr('name') or 'None'
                    btn_id = btn.attr('id') or 'None'
                    btn_class = btn.attr('class') or 'None'
                    btn_text = btn.text.strip()[:30] if btn.text else 'None'
                    print(f"      Button {i+1}: type={btn_type}, name={btn_name}, id={btn_id}, class={btn_class}, text='{btn_text}'")
                except Exception as e:
                    print(f"      Button {i+1}: Error getting attributes: {e}")
        except Exception as e:
            print(f"   Error finding buttons: {e}")

        # 尝试特定的搜索按钮选择器
        print(f"\n6. 测试特定搜索按钮选择器...")
        search_button_selectors = [
            'css:button[type="submit"]',
            'css:input[name="btnK"]',
            'css:input[name="btnI"]',
            'css:#gbqfbb',
            'css:.gNO89b',
            'css:button[aria-label="Google Search"]',
            'css:button[aria-label="搜索"]',
        ]

        for selector in search_button_selectors:
            try:
                print(f"   Trying: {selector}")
                btn = tab.ele(selector, timeout=1)
                if btn:
                    print(f"      ✓ Found button!")
                    print(f"         Tag: {btn.tag}, Type: {btn.attr('type')}, Text: {btn.text[:30] if btn.text else 'None'}")
                else:
                    print(f"      ✗ Not found")
            except Exception as e:
                print(f"      ✗ Error: {e}")

        # 当前URL
        print(f"\n7. 当前页面信息...")
        print(f"   URL: {tab.url}")
        print(f"   Title: {tab.title}")

        print(f"\n" + "=" * 60)
        print(f"探索完成。浏览器保持打开供你查看...")
        print(f"按 Ctrl+C 退出脚本")
        print("=" * 60)

        # 保持浏览器打开
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        print(f"\n❌ 发生错误:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    finally:
        print(f"\n✓ 浏览器保持打开状态")


if __name__ == "__main__":
    try:
        asyncio.run(explore_google())
    except KeyboardInterrupt:
        print(f"\n\n✓ 脚本已退出")
