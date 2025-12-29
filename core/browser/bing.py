import traceback
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

async def search_bing(adapter, tab, query):
    interaction_report = await adapter.navigate(tab, "https://www.bing.com")
    print(f"✓ Navigation completed. URL changed: {interaction_report.is_url_changed}")
    #tab = await adapter.get_tab()
    intl_btn = tab.ele("@id=est_en")
    if intl_btn:
        print("   Found International button. Clicking...")
        intl_btn.click()
    


    await adapter.type_text(tab, "@@tag()=input@@name=q",f"{query}\n", True)

    # Stabilize the search results page
    print("\n4. Stabilizing search results page...")
    stabilization_success = await adapter.stabilize(tab)
    print(f"✓ Stabilization completed: {stabilization_success}")

    # Extract search results
    search_results = await extract_search_results(adapter, tab)

    return search_results