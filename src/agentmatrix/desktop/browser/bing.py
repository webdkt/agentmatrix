import traceback
import asyncio
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
        await asyncio.sleep(3)  # Give time for search results to appear

        # Use DrissionPage's ele method to find search result elements
        # Bing search results are typically in li.b_algo elements
        search_result_elements = await asyncio.to_thread(
            tab.eles, "@@tag()=li@@class=b_algo"
        )

        for idx, element in enumerate(search_result_elements):
            try:
                # Extract title and URL from h2 element containing a link
                title_element = await asyncio.to_thread(element.ele, "@tag()=h2")
                if not title_element:
                    continue

                # Find the link within h2
                link_element = await asyncio.to_thread(title_element.ele, "@tag()=a")
                if not link_element:
                    continue

                title = link_element.text
                url = link_element.attr("href")

                # Extract snippet/description - try multiple possible selectors
                snippet_element = None
                snippet = "No description available"

                for selector in [
                    "css:.b_caption p",
                    "tag:p",
                    "css:.b_caption",
                    "tag:div",
                ]:
                    try:
                        snippet_element = await asyncio.to_thread(element.ele, selector)
                        if snippet_element and snippet_element.text.strip():
                            snippet = snippet_element.text.strip()
                            break
                    except:
                        continue

                # Extract visible domain
                domain_element = await asyncio.to_thread(
                    element.ele, "css:.b_attribution"
                )
                visible_domain = domain_element.text.strip() if domain_element else ""

                if title and url:
                    results.append(
                        {
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "domain": visible_domain,
                        }
                    )

            except Exception:
                continue

        print(f"✓ Successfully extracted {len(results)} search results")

    except Exception as e:
        traceback.print_exc()
        print(f"❌ Error extracting search results: {e}")

    return results


async def extract_knowledge_card(tab):
    """
    Extract Bing AI knowledge card content if present.

    Steps:
    1. Find div.qna_tlgacont (may not exist)
    2. Find <a> with <span>Read more</span> inside and click it
    3. Wait for expansion
    4. Extract text from div.qna_tlgacont div.gs_p

    Returns the card text, or None if no card is found.
    """
    try:
        card_container = await asyncio.to_thread(
            tab.ele, "css:div.qna_tlgacont", timeout=3
        )
        if not card_container:
            return None

        # Find and click the "Read more" button
        read_more = await asyncio.to_thread(
            card_container.ele, "@tag()=a@@text():Read more", timeout=2
        )
        if not read_more:
            read_more = await asyncio.to_thread(
                card_container.ele, "@tag()=a@@text():阅读更多", timeout=2
            )
        if read_more:
            await asyncio.to_thread(read_more.click, by_js=True)
            await asyncio.sleep(2)

        # Extract the expanded content
        gs_p = await asyncio.to_thread(
            card_container.ele, "css:div.gs_p", timeout=3
        )
        if gs_p and gs_p.text.strip():
            return gs_p.text.strip()

        return None

    except Exception:
        return None


async def search_bing(adapter, tab, query, max_pages=1):
    """
    Perform a Bing search using human-like behavior.

    This function ONLY executes the search and leaves the browser on the search results page.
    It does NOT extract any search results - that's handled by the caller.
    """
    print(f"\n=== Bing Search: {query} ===")

    import random

    # Step 1: Navigate to Bing homepage
    print("1. Navigating to Bing homepage...")
    interaction_report = await adapter.navigate(tab, "https://www.bing.com")
    print(f"   Query: {query}")
    print(
        f"✓ Navigation to homepage completed. URL changed: {interaction_report.is_url_changed}"
    )

    # Wait for page to load
    await asyncio.sleep(2)

    # Step 2: Stabilize the homepage
    print("\n2. Stabilizing Bing homepage...")
    await adapter.stabilize(tab)

    # Step 3: Type search query like a human
    print("\n3. Typing search query...")
    print("   Waiting for search box to be ready...")
    await asyncio.sleep(random.uniform(1.5, 2.5))

    search_box_selectors = [
        'input[name="q"]',
        'textarea[name="q"]',
    ]

    search_typed = False
    for selector in search_box_selectors:
        try:
            success = await adapter.type_text(tab, selector, query, clear_existing=True)
            if success:
                print(f"   ✓ Query typed successfully with: {selector}")
                search_typed = True
                break
        except Exception:
            continue

    if not search_typed:
        error_msg = "Failed to find and type in Bing search box"
        print(f"   ✗ {error_msg}")
        raise Exception(error_msg)

    # 模拟人类思考：输入完后短暂停顿
    await asyncio.sleep(random.uniform(0.8, 1.5))

    # Step 4: Submit search
    await asyncio.sleep(random.uniform(0.3, 0.7))

    search_button_selectors = [
        'css:button[type="submit"]',
        'css:input[name="go"]',
        "css:#search_icon",
        "css:.search_icon",
        "css:#sb_form_go",
    ]

    button_clicked = False
    for selector in search_button_selectors:
        try:
            success = await adapter.click_by_selector(tab, selector)
            if success and not success.error:
                print(f"   ✓ Search button clicked successfully")
                button_clicked = True
                break
        except Exception as e:
            print(f"   ✗ Button click failed: {e}")
            continue

    if not button_clicked:
        print(f"   ⚠️  Could not find search button, trying Enter key...")
        from ..browser.browser_adapter import KeyAction

        submit_report = await adapter.press_key(tab, KeyAction.ENTER)
        print(f"   Pressed Enter. URL changed: {submit_report.is_url_changed}")

    # Wait for search results page to load
    print("   Waiting for search results page to load...")
    await asyncio.sleep(random.uniform(2.5, 3.5))

    # Step 5: Check for International button and click if present
    print("\n5. Checking for International button...")
    intl_btn = await asyncio.to_thread(tab.ele, "@id=est_en")
    if intl_btn:
        print("   Found International button. Clicking...")
        await asyncio.to_thread(intl_btn.click)
        await asyncio.sleep(1)

    # Step 6: Stabilize the search results page
    print("\n6. Stabilizing search results page...")
    await adapter.stabilize(tab)

    print(f"\n✓ Search completed successfully. Browser now on search results page.")
    return True
