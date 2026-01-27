import traceback
from urllib.parse import quote_plus

async def extract_search_results(adapter, tab):
    """
    Extract search results from Bing search results page.

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

        # Use DrissionPage's ele method to find search result elements
        # Bing search results are typically in li.b_algo elements
        search_result_elements = tab.eles('@@tag()=li@@class=b_algo')

        print(f"   Found {len(search_result_elements)} search result elements")

        for idx, element in enumerate(search_result_elements):
            #print(element)
            
            try:
                #print(f"   Processing element {idx+1}...")

                # Extract title and URL from h2 element containing a link
                title_element = element.ele('@tag()=h2')
                if not title_element:
                    print(f"   No h2 found in element {idx+1}")
                    continue

                # Find the link within h2
                link_element = title_element.ele('@tag()=a')
                if not link_element:
                    print(f"   No link found in h2 of element {idx+1}")
                    continue

                title = link_element.text
                url = link_element.attr('href')

                print(f"   Found title: {title[:50]}...")
                print(f"   Found URL: {url}")

                # Extract snippet/description - try multiple possible selectors
                snippet_element = None
                snippet = "No description available"

                # Try different possible selectors for the description
                possible_selectors = [
                    'css:.b_caption p',
                    'tag:p',
                    'css:.b_caption',
                    'tag:div'
                ]

                for selector in possible_selectors:
                    try:
                        snippet_element = element.ele(selector)
                        if snippet_element and snippet_element.text.strip():
                            snippet = snippet_element.text.strip()
                            break
                    except:
                        continue

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
                continue

        print(f"✓ Successfully extracted {len(results)} search results")

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Error extracting search results: {e}")

    return results

async def search_bing(adapter, tab, query, max_pages=1):
    """
    Perform a Bing search using human-like behavior.

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
    print(f"\n=== Bing Search: {query} ===")

    import time
    import random

    # Step 1: Navigate to Bing homepage
    print("1. Navigating to Bing homepage...")
    interaction_report = await adapter.navigate(tab, "https://www.bing.com")
    print(f"   Query: {query}")
    print(f"✓ Navigation to homepage completed. URL changed: {interaction_report.is_url_changed}")

    # Wait for page to load
    time.sleep(2)

    # Step 2: Stabilize the homepage
    print("\n2. Stabilizing Bing homepage...")
    stabilization_success = await adapter.stabilize(tab)
    print(f"✓ Stabilization completed: {stabilization_success}")

    # Step 3: Type search query like a human
    print("\n3. Typing search query...")

    # 额外等待，确保搜索框完全加载
    print("   Waiting for search box to be ready...")
    time.sleep(random.uniform(1.5, 2.5))  # 随机等待1.5-2.5秒

    # Bing search box selector (try multiple possible selectors)
    search_box_selectors = [
        'input[name="q"]',      # Standard Bing search box
        'textarea[name="q"]',   # Alternative design
    ]

    search_typed = False
    for selector in search_box_selectors:
        try:
            print(f"   Trying selector: {selector}")

            # Type the query with human-like behavior
            success = await adapter.type_text(tab, selector, query, clear_existing=True)

            if success:
                print(f"   ✓ Query typed successfully with: {selector}")
                search_typed = True
                break
            else:
                print(f"   ✗ Failed to type with: {selector}")
        except Exception as e:
            print(f"   ✗ Selector failed: {selector} - {e}")
            continue

    if not search_typed:
        error_msg = "Failed to find and type in Bing search box"
        print(f"   ✗ {error_msg}")
        raise Exception(error_msg)

    # 模拟人类思考：输入完后短暂停顿，准备点击搜索
    print("   Pausing briefly (simulating human behavior)...")
    time.sleep(random.uniform(0.8, 1.5))  # 随机等待0.8-1.5秒

    # Step 4: Submit search (click search button instead of pressing Enter)
    print("\n4. Submitting search...")

    # 额外等待，让用户看到输入的内容
    time.sleep(random.uniform(0.3, 0.7))  # 额外等待0.3-0.7秒

    # 尝试多种搜索按钮选择器
    search_button_selectors = [
        'css:button[type="submit"]',      # 标准提交按钮
        'css:input[name="go"]',           # Bing 的搜索按钮
        'css:#search_icon',               # 搜索图标按钮
        'css:.search_icon',               # 搜索图标（class）
        'css:#sb_form_go',                # Bing 搜索按钮 ID
    ]

    button_clicked = False
    for selector in search_button_selectors:
        try:
            print(f"   Trying to click search button: {selector}")
            success = await adapter.click_by_selector(tab, selector)

            if success and not success.error:
                print(f"   ✓ Search button clicked successfully")
                button_clicked = True
                break
            else:
                print(f"   ✗ Failed to click button (or button not found)")
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

    # Step 5: Check for International button and click if present
    print("\n5. Checking for International button...")
    intl_btn = tab.ele("@id=est_en")
    if intl_btn:
        print("   Found International button. Clicking...")
        intl_btn.click()
        time.sleep(1)  # Wait for the page to update after clicking intl button
    else:
        print("   No International button found (or already on international version)")

    # Step 6: Stabilize the search results page
    print("\n6. Stabilizing search results page...")
    stabilization_success = await adapter.stabilize(tab)
    print(f"✓ Stabilization completed: {stabilization_success}")

    print(f"\n✓ Search completed successfully. Browser now on search results page.")
    return True