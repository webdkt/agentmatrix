import traceback
from urllib.parse import quote_plus

async def extract_search_results(adapter, tab):
    """
    Extract search results from Google search results page.

    Args:
        adapter: DrissionPageAdapter instance
        tab: Current browser tab handle

    Returns:
        List of dictionaries containing title, url, and snippet for each search result
    """
    print("\n4. Extracting search results...")
    results = []

    try:
        # Wait for search results to load
        print("   Waiting for search results to load...")
        import time
        time.sleep(3)  # Give time for search results to appear

        # Find all h3 elements (each h3 is a search result title)
        search_result_elements = tab.eles('@tag()=h3')

        print(f"   Found {len(search_result_elements)} h3 elements")

        for idx, h3_element in enumerate(search_result_elements):
            try:
                print(f"   Processing result {idx+1}...")

                # Extract title from h3
                title = h3_element.text.strip()
                if not title:
                    print(f"   No title found in h3 {idx+1}")
                    continue

                print(f"   Found title: {title[:50]}...")

                # Find the parent <a> element (h3's direct parent)
                # Try to get parent - DrissionPage might have different API
                a_element = h3_element.parent()

                # Verify it's an <a> element
                if not a_element or a_element.tag != 'a':
                    # Try alternative: search for <a> in parent chain
                    current = h3_element
                    a_element = None
                    for _ in range(3):  # Check up to 3 levels up
                        current = current.parent() if current else None
                        if current and current.tag == 'a':
                            a_element = current
                            break

                if not a_element:
                    print(f"   No parent <a> found for h3 {idx+1}")
                    continue

                # Extract URL from <a> element
                url = a_element.attr('href')
                if not url:
                    print(f"   No href found in <a> of result {idx+1}")
                    continue

                print(f"   Found URL: {url}")

                # Navigate up from <a> to find 3 levels of <div> elements
                # Structure: a -> [possibly other elements] -> div -> div -> div
                # Then find the sibling of the 3rd div, which contains the snippet

                current = a_element
                div_count = 0
                target_div = None

                # Navigate up to find the 3rd level div
                while current and div_count < 3:
                    current = current.parent()
                    if current and current.tag == 'div':
                        div_count += 1
                        if div_count == 3:
                            target_div = current
                            break

                if not target_div:
                    print(f"   Could not find 3 levels of <div> for result {idx+1}")
                    snippet = "No description available"
                else:
                    # Find the sibling div of the 3rd level div
                    snippet_div = target_div.next()

                    if snippet_div:
                        snippet = snippet_div.text.strip() if snippet_div.text else "No description available"
                        print(f"   Found snippet: {snippet[:50]}...")
                    else:
                        snippet = "No description available"

                # Add result to list
                if title and url:
                    result = {
                        'title': title,
                        'url': url,
                        'snippet': snippet
                    }
                    results.append(result)
                    print(f"   ✓ Successfully extracted result {idx+1}")

            except Exception as e:
                print(f"   Error extracting result {idx+1}: {e}")
                traceback.print_exc()
                continue

        print(f"✓ Successfully extracted {len(results)} search results")

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Error extracting search results: {e}")

    return results


async def search_google(adapter, tab, query, max_pages=1):
    """
    Perform a Google search using human-like behavior.

    This function ONLY executes the search and leaves the browser on the search results page.
    It does NOT extract any search results - that's handled by the caller.

    Args:
        adapter: DrissionPageAdapter instance
        tab: Current browser tab handle
        query: Search query string (will be typed into search box)
        max_pages: Maximum number of pages to navigate (default: 1). Note: This function
                   only stays on the first page; multi-page navigation is handled elsewhere.

    Returns:
        bool: True if search completed successfully, False otherwise

    Raises:
        Exception: If search fails (no search box found, navigation fails, etc.)
    """
    print(f"\n=== Google Search: {query} ===")

    import time
    import random

    # Step 1: Navigate to Google homepage
    print("1. Navigating to Google homepage...")
    interaction_report = await adapter.navigate(tab, "https://www.google.com")
    print(f"   Query: {query}")
    print(f"✓ Navigation to homepage completed. URL changed: {interaction_report.is_url_changed}")

    # Wait for page to load
    time.sleep(2)

    # Step 2: Stabilize the homepage
    print("\n2. Stabilizing Google homepage...")
    stabilization_success = await adapter.stabilize(tab)
    print(f"✓ Stabilization completed: {stabilization_success}")

    # Step 3: Type search query like a human
    print("\n3. Typing search query...")

    # 额外等待，确保搜索框完全加载
    print("   Waiting for search box to be ready...")
    time.sleep(random.uniform(1.5, 2.5))  # 随机等待1.5-2.5秒

    # Google search box selector
    search_box_selector = 'textarea[name="q"]'

    print(f"   Trying selector: {search_box_selector}")
    success = await adapter.type_text(tab, search_box_selector, query, clear_existing=True)

    if success:
        print(f"   ✓ Query typed successfully")
    else:
        error_msg = "Failed to find and type in Google search box"
        print(f"   ✗ {error_msg}")
        raise Exception(error_msg)

    # 模拟人类思考：输入完后短暂停顿，准备点击搜索
    print("   Pausing briefly (simulating human behavior)...")
    time.sleep(random.uniform(0.8, 1.5))  # 随机等待0.8-1.5秒

    # Step 4: Submit search (click search button instead of pressing Enter)
    print("\n4. Submitting search...")

    # 额外等待，让用户看到输入的内容
    time.sleep(random.uniform(0.3, 0.7))  # 额外等待0.3-0.7秒

    # 尝试多种搜索按钮选择器（使用固定属性）
    search_button_selectors = [
        'css:input[type="submit"][aria-label="Google 搜索"]',  # 中文版
        'css:input[type="submit"][aria-label="Google Search"]', # 英文版
        'css:input[name="btnK"][type="submit"]',  # 备选：name + type 组合
    ]

    button_clicked = False
    for selector in search_button_selectors:
        try:
            print(f"   Trying to click search button: {selector}")

            # 使用 click_first_visible_by_selector 来找到可见的按钮
            success = await adapter.click_first_visible_by_selector(tab, selector)

            if not success.error:
                print(f"   ✓ Search button clicked successfully")
                button_clicked = True
                break
            else:
                print(f"   ✗ Failed to click button: {success.error}")
        except Exception as e:
            print(f"   ✗ Button click failed: {e}")
            continue

    if not button_clicked:
        # 如果点击按钮失败，尝试按回车（但在 textarea 里会换行）
        print(f"   ⚠️  Could not find search button, trying Enter key (may not work in textarea)...")
        from ..browser.browser_adapter import KeyAction
        submit_report = await adapter.press_key(tab, KeyAction.ENTER)
        print(f"   Pressed Enter. URL changed: {submit_report.is_url_changed}")

    # Wait for search results page to load
    print("   Waiting for search results page to load...")
    time.sleep(random.uniform(2.5, 3.5))  # 随机等待2.5-3.5秒，更真实

    # Step 5: Stabilize the search results page
    print("\n5. Stabilizing search results page...")
    stabilization_success = await adapter.stabilize(tab)
    print(f"✓ Stabilization completed: {stabilization_success}")

    print(f"\n✓ Search completed successfully. Browser now on search results page.")
    return True
