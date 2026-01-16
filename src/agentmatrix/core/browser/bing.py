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

async def search_bing(adapter, tab, query, max_pages=5, page=None):
    """
    Perform a Bing search and extract results from multiple pages.

    Args:
        adapter: DrissionPageAdapter instance
        tab: Current browser tab handle
        query: Search query string
        max_pages: Maximum number of pages to extract (default: 5)
        page: Specific page to extract (default: None). If specified, only returns results from that page.

    Returns:
        List of dictionaries containing title, url, and snippet for each search result
    """
    print(f"\n=== Bing Search: {query} (max pages: {max_pages}) ===")

    # Navigate directly to Bing search results page
    print("1. Navigating to Bing search results...")
    encoded_query = quote_plus(query)
    print(f"   Query: {query}")
    print(f"   Encoded: {encoded_query}")
    interaction_report = await adapter.navigate(tab, f"https://www.bing.com/search?q={encoded_query}")
    print(f"✓ Navigation completed. URL changed: {interaction_report.is_url_changed}")

    # Wait a moment for page to load
    import time
    time.sleep(2)

    # Check for International button and click if present
    intl_btn = tab.ele("@id=est_en")
    if intl_btn:
        print("   Found International button. Clicking...")
        intl_btn.click()
        time.sleep(1)  # Wait for the page to update after clicking intl button

    # Stabilize the search results page
    print("\n2. Stabilizing search results page...")
    stabilization_success = await adapter.stabilize(tab)
    print(f"✓ Stabilization completed: {stabilization_success}")

    # If page is specified, only extract that specific page
    if page is not None:
        print(f"\n=== Extracting page {page} only ===")

        # Navigate to the specified page
        target_page = page
        while target_page > 1:
            try:
                next_page_selector = f'css:a[aria-label=\'Page {target_page}\']'
                print(f"Looking for Page {target_page}...")
                next_page_link = tab.ele(next_page_selector, timeout=2)

                if next_page_link:
                    print(f"✓ Found Page {target_page}, clicking...")
                    next_page_link.click()
                    time.sleep(2)
                    await adapter.stabilize(tab)
                    target_page -= 1
                else:
                    print(f"✗ Page {page} not found")
                    return []
            except Exception as e:
                print(f"✗ Error navigating to page {page}: {e}")
                return []

        # Extract results from the specified page
        print(f"\n=== Processing page {page} ===")
        page_results = await extract_search_results(adapter, tab)
        print(f"\n=== Total results collected: {len(page_results)} ===")
        return page_results

    # Extract search results from multiple pages (original logic)
    all_results = []
    current_page = 1

    while current_page <= max_pages:
        print(f"\n=== Processing page {current_page} ===")

        # Extract results from current page
        page_results = await extract_search_results(adapter, tab)
        all_results.extend(page_results)

        # Check if we should continue to next page
        if current_page < max_pages:
            # Look for next page link using aria-label='Page X'
            next_page_num = current_page + 1
            next_page_selector = f'css:a[aria-label=\'Page {next_page_num}\']'

            try:
                print(f"\nLooking for next page (Page {next_page_num})...")
                next_page_link = tab.ele(next_page_selector, timeout=2)

                if next_page_link:
                    print(f"✓ Found next page link, clicking...")
                    next_page_link.click()
                    time.sleep(2)  # Wait for page to load

                    # Stabilize after page change
                    await adapter.stabilize(tab)
                    current_page += 1
                else:
                    print(f"✓ No more pages available")
                    break

            except Exception as e:
                print(f"✓ No more pages available or error finding next page: {e}")
                break
        else:
            print(f"\n✓ Reached maximum page limit ({max_pages})")
            break

    print(f"\n=== Total results collected: {len(all_results)} ===")
    return all_results