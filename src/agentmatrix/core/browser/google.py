import traceback

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


async def search_google(adapter, tab, query, max_pages=5, page=None):
    """
    Perform a Google search and extract results from multiple pages.

    Args:
        adapter: DrissionPageAdapter instance
        tab: Current browser tab handle
        query: Search query string
        max_pages: Maximum number of pages to extract (default: 5)
        page: Specific page to extract (default: None). If specified, only returns results from that page.

    Returns:
        List of dictionaries containing title, url, and snippet for each search result
    """
    print(f"\n=== Google Search: {query} (max pages: {max_pages}) ===")

    # Navigate to Google
    print("1. Navigating to Google...")
    interaction_report = await adapter.navigate(tab, "https://www.google.com")
    print(f"✓ Navigation completed. URL changed: {interaction_report.is_url_changed}")

    # Wait a moment for page to load
    import time
    time.sleep(2)

    # Type search query in textarea and submit
    print("2. Typing search query...")
    await adapter.type_text(tab, "@@tag()=textarea", f"{query}", True)
    search_btn = await adapter.find_element(tab, 'xpath:(//input[@type="submit" and @role="button"])[2]')
    await adapter.click_and_observe(tab, search_btn)
    print("✓ Search query submitted")

    # Stabilize the search results page
    print("\n3. Stabilizing search results page...")
    stabilization_success = await adapter.stabilize(tab)
    print(f"✓ Stabilization completed: {stabilization_success}")

    # If page is specified, only extract that specific page
    if page is not None:
        print(f"\n=== Extracting page {page} only ===")

        # Navigate to the specified page
        target_page = page
        while target_page > 1:
            try:
                next_page_selector = f'css:a[aria-label="Page {target_page}"]'
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
            # Look for next page link using aria-label="Page X"
            next_page_num = current_page + 1
            next_page_selector = f'css:a[aria-label="Page {next_page_num}"]'

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
