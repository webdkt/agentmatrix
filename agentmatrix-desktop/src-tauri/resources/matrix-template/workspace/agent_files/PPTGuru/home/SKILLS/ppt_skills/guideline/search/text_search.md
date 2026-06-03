# Text Search Guidelines

This guideline provides instructions for conducting effective information searches to support presentation content creation.

## Search Strategy

### When to Search

1. **Search mode**: When the user provides only a topic without detailed content
2. **Summary mode supplementary**: When the uploaded document needs additional context, data, or current developments
3. **Creative mode**: When searching for images, examples, or best practices for design inspiration

### Search Best Practices

1. **Use English keywords** for higher quality results, especially for:
   - Technical topics
   - Industry reports
   - Market data
   - Academic research

2. **Be specific**:
   - Include year/timeframe when looking for current data
   - Include specific metrics or parameters
   - Use industry terminology

3. **Multi-source verification**:
   - Cross-check facts across multiple sources
   - Prioritize authoritative sources (government, research institutions, established media)
   - Note publication dates for currency

## Information Evaluation

### Source Quality Hierarchy

1. **Primary sources** (highest quality):
   - Government statistics and reports
   - Official company filings and reports
   - Peer-reviewed academic papers
   - International organization reports (UN, World Bank, IMF, etc.)

2. **Secondary sources** (good quality):
   - Reputable research firms (McKinsey, BCG, Bain, Deloitte, etc.)
   - Industry associations and trade groups
   - Established business media (Financial Times, Wall Street Journal, Economist, etc.)
   - Specialized industry publications

3. **Tertiary sources** (use with caution):
   - News aggregators
   - Blogs and opinion pieces
   - Social media
   - Wikipedia (good for overview, verify facts elsewhere)

### Data Quality Checklist

- [ ] Is the data recent and relevant?
- [ ] Is the source credible and authoritative?
- [ ] Is the methodology transparent?
- [ ] Is the data consistent with other sources?
- [ ] Are units and definitions clear?

## Image Search Guidelines

### Search and Download Workflow

Use the **browser** to search and download images. Use **vision.look** to visually inspect results before committing.

1. **Search**: Open the browser and navigate to an image search engine (e.g., Google Images, Bing Images). Use the search query strategy below.
2. **Browse results**: Scroll through the search results page. Use `vision.look` on the browser screenshot to quickly scan which results look promising based on thumbnails.
3. **Preview candidates**: Click into promising results to view the full-size image or the source page. Use `vision.look` again to inspect the actual image quality, composition, and relevance.
4. **Download**: Once satisfied, download the image to the project's `images/` directory. Use `vision.look` on the downloaded file to do a final quality check — verify resolution, clarity, and that there are no watermarks or artifacts.
5. **Reject and retry**: If the downloaded image does not meet quality criteria, discard it and go back to step 2 with different keywords.

> **Never skip the visual inspection step.** Text-based metadata (file size, claimed resolution) is not sufficient — always use `vision.look` to confirm the image actually looks good and matches the intended use.

### Search Query Strategy

1. **Use English keywords** for better results
2. **Append style keywords** to match the design direction:
   - For business: "professional", "corporate", "clean"
   - For technology: "futuristic", "high-tech", "innovation"
   - For nature: "landscape", "aerial", "panoramic"
   - For products: "product photography", "studio shot", "isolated"

3. **Avoid search terms that return poor results**:
   - "PPT", "presentation", "template", "premium color scheme" — these return screenshot clutter
   - Instead search for the actual subject matter

4. **Quality criteria**:
   - High resolution (preferably 1920x1080 or higher)
   - Clean, uncluttered compositions
   - Watermark-free
   - Relevant to the specific content

### Image Types to Search For

- **Cover/chapter images**: High-impact, visually striking, relevant to topic
- **Content illustrations**: Directly supporting the information on the page
- **Product/brand images**: Official or high-quality photography
- **Technical images**: Diagrams, equipment, processes
- **Scene images**: Real-world applications, usage scenarios

### Image Types to Avoid Searching For

- Data charts (use chart elements instead)
- Table screenshots (use table elements instead)
- Icons (use icon elements instead)
- Flowcharts/diagrams (use shape+text combinations instead)
- Decorative abstract backgrounds

## Source Citation

All searched information must be properly cited:

1. **In outline.md**: Mark supplemented content with "[supplemented]" and include source URLs
2. **In PPTD**: Use `<a href="url">` hyperlinks for key data and cited viewpoints
3. **Source format**: `Source: Institution Name, Year;` with hyperlink to original page

## Search Limitations

- Do not rely solely on search results; cross-verify critical facts
- Be aware of potential bias in sources
- Note that search results may not always be current; verify dates
- If search results are insufficient, try alternative keywords or reframe the query
