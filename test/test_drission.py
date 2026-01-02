#!/usr/bin/env python3
"""
Test script for DrissionPageAdapter basic functionality.

This script will:
1. Initialize DrissionPageAdapter using test/profile as Chrome profile directory
2. Start browser (non-headless mode)
3. Wait for 5 seconds
4. Close browser

Running this script can verify whether the start and close methods of DrissionPageAdapter work correctly.
"""

import asyncio
import sys
import os
from pathlib import Path
import traceback

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.browser.drission_page_adapter import DrissionPageAdapter, DrissionPageElement



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
                        'element':  link_element,
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


async def test_basic_functionality():
    """Test basic start, wait, close functionality"""

    print("=== DrissionPageAdapter Basic Functionality Test ===")

    # Get absolute path of profile directory
    profile_path = Path(__file__).parent / "profile"
    profile_path = profile_path.absolute()

    print(f"Using Chrome Profile directory: {profile_path}")

    # Initialize adapter
    adapter = DrissionPageAdapter(profile_path=str(profile_path))

    try:
        print("\n1. Starting browser...")
        # Start in non-headless mode so we can see the browser window
        await adapter.start(headless=False)
        print("✓ Browser started successfully")

        print("\n2. Getting current tab...")
        current_tab = await adapter.get_tab()
        print(f"✓ Current tab obtained: {type(current_tab)}")

        print("\n3. Navigating to https://www.bing.com (International version)...")
        # Navigate to www.bing.com - this will test our adapter's navigation capability
        
        interaction_report = await adapter.navigate(current_tab, "https://www.bing.com")
        print(f"✓ Navigation completed. URL changed: {interaction_report.is_url_changed}")
        #tab = await adapter.get_tab()
        intl_btn = current_tab.ele("@id=est_en")
        if intl_btn:
            print("   Found International button. Clicking...")
            intl_btn.click()
        


        await adapter.type_text(current_tab, "@@tag()=input@@name=q","安利中国公司\n", True)

        # Stabilize the search results page
        print("\n4. Stabilizing search results page...")
        stabilization_success = await adapter.stabilize(current_tab)
        print(f"✓ Stabilization completed: {stabilization_success}")

        # Extract search results
        search_results = await extract_search_results(adapter, current_tab)

        # Display the extracted results
        if search_results:
            print(f"\n5. Displaying extracted search results:")
            print("=" * 60)
            for result in search_results:
                print(f"\n{result['title']}")
                print(f"   URL: {result['url']}")
                print(f"   Description: {result['snippet'][:100]}...")
            print("=" * 60)
            print(f"\nTotal results extracted: {len(search_results)}")
        else:
            print("\n❌ No search results were extracted")

        #打开第一个结果：
        print("\n6. Opening first search result...")
        first_link = search_results[0]['element']
        pe = DrissionPageElement(first_link)
        navi_result = await adapter.click_and_observe(current_tab, pe)
        print(navi_result)
        
        print("Opening page")
        await adapter.navigate(current_tab, 'https://www.sohu.com/a/917113354_122485359')
        print("Wait for stablization")
        await adapter.stabilize(current_tab)
        print("Stable Status")
        content = await adapter.get_page_snapshot(current_tab)
        print(content.main_text)

        # Keep browser open for potential additional steps as requested
        print("\n6. Keeping browser open for 10 seconds for observation...")
        await asyncio.sleep(10)
        print("✓ Observation period completed")

        # print("\n7. Closing browser...")
        # await adapter.close()
        # print("✓ Browser closed successfully")

        print("\n=== Test completed! Everything is normal ===")

    except Exception as e:
        traceback.print_exc()
        print(f"\n❌ Test failed: {e}")
        print(f"Error type: {type(e).__name__}")



        return False

    return True


def check_dependencies():
    """Check if necessary dependencies are installed"""
    try:
        import DrissionPage
        print("✓ DrissionPage is installed")
        return True
    except ImportError:
        print("❌ DrissionPage is not installed")
        print("Please run: pip install DrissionPage")
        return False


if __name__ == "__main__":
    print("Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)

    print("Starting test...")
    success = asyncio.run(test_basic_functionality())

    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Test failed!")
        sys.exit(1)