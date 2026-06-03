# Academic

> Applicable scenarios: Thesis defense, academic presentations, research reports, academic lectures, conference presentations, etc.
> Style anchor: Top university thesis defense style + IEEE/ACM conference presentation style + Nature/Science publication figure standards

## Design Philosophy
- **Structured and rigorous**: Logical clarity is paramount; every page should demonstrate systematic academic thinking
- **Content-centric**: Research methodology, data, and conclusions are the core; visual elements serve only to enhance readability, never to distract
- **Scholarly restraint**: Avoid commercial or flashy decorative elements; maintain a solemn, professional academic tone
- **Readability priority**: Dense content (formulas, charts, citations) requires careful typographic hierarchy to ensure audience comprehension
- **Information density: High (80-90%)**: Academic presentations must carry substantial content; blank space is a luxury but should be used strategically for emphasis
- **Faithful to the source**: Prioritize reusing original figures, data, and expressions from the paper/report, maintaining consistency with the source material without unsupported secondary processing

## Chapter Page Style
- **Preferred**: Light background chapter pages (`$background` fill) with large semi-transparent chapter number watermark in `$secondary`
- **Rationale**: Academic presentations prioritize clarity and readability. Light chapter pages maintain visual consistency with content pages and avoid the theatrical feel of dark transitions.
- **Avoid**: Dark background chapter pages unless the conference or institution explicitly requires dramatic styling.

## Text-to-Visual Ratio: Text-heavy, Visuals as Evidence
- Text is the absolute carrier of academic arguments; visuals (charts, formulas, diagrams) serve as evidence and illustration
- Recommended ratio: approximately 35% text + 55% charts, original figures, formulas, tables + 10% whitespace
- Results pages are absolutely chart-centric, with text serving only as annotations and key interpretations
- Encourage using flowcharts and diagrams to show research architecture, method workflows, and system design
- Avoid text-only pages (except for research background overview pages); strive for text-visual integration
- Original figures and charts from the source should be prioritized for direct reuse

## Color Guidance
- **University theme color**: Use the target university's emblem/VI standard color as the primary color — this is the top priority for academic presentation color schemes. When the user specifies a university name, look up the university's standard color and use it as the primary color. If the user does not specify a university, follow the color guidance below
- **Highly restrained color palette**: Academic scenarios demand solemnity and rationality; limit the palette to 1-2 core colors plus a grayscale hierarchy
- **Single primary color system**: Choose one stable academic tone (commonly dark blue, dark green, or burgundy) as the primary color for structural elements (title bars, key chart series, emphasis text)
- **Neutral color dominance**: Page backgrounds should be white or near-white; text should be near-black or dark gray; structural elements (dividers, table borders) should use light gray
- **Background and body text**: Backgrounds should maintain sufficient brightness to ensure high readability of charts, formulas, and text; body text color must form clear contrast with the background to avoid visual fatigue
- **Data visualization restraint**: Charts should primarily use the primary color family + neutral grays; avoid high-saturation or high-contrast multi-color schemes that appear unprofessional
- **Chart colors**: Distinguishability is the primary goal for chart colors, while avoiding overly harsh or overly similar colors. Reference the color palettes of major academic journals (such as Nature/Science) to maintain professionalism
- **Emphasis through weight, not color**: Key conclusions and data should be emphasized via bold text, larger font sizes, or positional prominence, not via bright colors
- **Accent color**: Used only to highlight key findings, core conclusions, or significance markers; usage should be restrained and not overextended
- **Strictly prohibit decorative coloring**: No gradient backgrounds, no decorative color blocks, no emotionally expressive colors
- **Overall prohibitions**: Avoid dark backgrounds for large body text areas (impairs chart readability), high-saturation neon colors, and visual clutter caused by multiple high-contrast colors used simultaneously in large areas

## Font Guidance
- **Titles and headings**: Serif fonts (e.g., Times New Roman, Noto Serif SC) to convey academic rigor and tradition; Sans-serif Bold (e.g., QuattrocentoSans Bold, MiSans Bold) for clean projection legibility
- **Body text, data, formulas**: Sans-serif fonts (e.g., Arial, Calibri, MiSans) for clarity and screen readability
- **Chinese**: Songti/SimSun or Microsoft YaHei; for formal thesis defense, Songti (serif) is preferred for titles
- **English references/terminology**: Keep the same font family as body text; do not switch fonts
- Font size hierarchy should be clear but not overly dramatic:
  - Cover title: 36-44px
  - Chapter titles: 32-36px
  - Page titles / Action titles: 24-28px
  - Subtitle (Table N / Fig. N / analysis section title): 22-26px
  - Body text: 18-22px (use 22px when page text content is light, 20px for moderate, 18px for heavy; must not go below 18px)
  - Formulas, captions, footnotes, citations: 14-16px
  - Minimum annotation font size: 12px

## Content Page Structure
- **Standard academic structure**:
  - Page title (conclusion or topic statement)
  - Main argument / methodology / data presentation area
  - Source annotations / footnotes (essential for academic integrity)
  - Page numbers
- **Navigation bar**: Recommend setting up a horizontal or vertical navigation bar with width/height matching the page width/height, chapter titles evenly distributed, current chapter highlighted with a white rectangle with themed border and readable text color, helping the audience track presentation progress and overall structure; navigation bar format is flexible
- **Page title**: Use descriptive short phrases (e.g., "Experimental Results: Multi-Metric Performance Comparison"), no more than one line; the title should directly convey the page's research point
- **University logo**: When the user specifies a university name, it is recommended to search online for the university's logo (or extract from user-uploaded attachments) and place it at a consistent fixed position on every page to clearly indicate the presenting institution
- **Content area**:
  - Single-column analysis structure (vertical narrative)
  - Left-figure, right-interpretation structure
  - Top-figure, bottom-insight structure
  - Dual-figure comparison structure
  - Data table + conclusion structure
- **Numbering and references**: All figures and tables should have standard numbering (e.g., Table 1, Figure 2, etc.); charts must have complete titles, legends, axis labels, and unit annotations
- **Reference citations**: References cited in the body must use standardized citation formats (see citation format requirements in "Narrative Style"). If a reference has an online link (such as DOI or paper homepage), `<a href="url">` hyperlinks can be used to link to the original text
- **Footer area**: Footnotes, reference superscripts, or supplementary notes at the bottom-left of the page; page numbers fixed at the bottom-right
- **Citation and source format**: All non-original data, cited theories, and comparative literature must include source annotations (author, year, publication); format: `Source: Author, Year;` or footnote numbering with a references page

## Narrative Style: Logic-Driven / Argumentation-Driven
- Follow the standard academic narrative: Background/Research Question -> Literature Review -> Methodology -> Experiments/Data -> Results/Analysis -> Conclusions/Future Work
- **Overall structure**: Organize slides following the classic academic paper structure
- Each page should represent a single logical step; transitions between pages should be natural and explicit
- Arguments must be evidence-based; avoid unsupported assertions
- Balance depth and accessibility: explain methodology clearly for non-specialist committee members while maintaining technical accuracy
- **Language style**: Objective and rigorous, using academic language, avoiding subjective exaggeration and vague expressions. **Hallucinations are strictly prohibited — ensure all content has authentic, complete citations!**
- **Citation format requirements**: When citing related work in the body, reference numbers must be annotated (e.g., [1], [2-4]), with numbers corresponding one-to-one to the reference list at the end. Citation format should follow the user-specified standard (e.g., GB/T 7714, APA, IEEE, etc.); if the user does not specify, Chinese defenses default to GB/T 7714 format, English scenarios default to APA format
- **Faithful citation**: Faithfully cite the core viewpoints and conclusions of related work based on the original text; do not fabricate or speculate. Every citation must be traceable to the original literature
- **Reference page (required)**: A dedicated reference page must be included at the end of the slides, listing all references cited in the body with consistent formatting and sequential numbering. Each entry should include author, title, journal/conference name, year, and other key information. If references are numerous, they can span two pages, using small font size (12-16px) with compact arrangement

## Content Expression Techniques
- **Original figure reuse (priority)**: Academic presentations should prioritize using original figures and images from the paper or report rather than redrawing them. Original figures preserve complete data precision, annotation standards, and academic formatting; redrawing can introduce errors or omissions. When reusing, maintain the original image's resolution and clarity; add text interpretations or arrows to highlight key findings beside the figure when necessary
- **Structured formulas**: Use LaTeX for all mathematical expressions; ensure formulas are large enough to be read from a distance
- **Data tables**: Clear headers, aligned decimals, units clearly marked; alternating row colors (very light gray) to aid reading across wide tables
- **Charts**: Prefer line charts (trends), bar charts (comparisons), and scatter plots (correlations); label all axes with units; legends must be clear
- **Diagrams and frameworks**: Use simple geometric shapes + text (flowcharts, system architecture); avoid 3D effects and shadows
- **Emphasis techniques**: Bold for key terms and conclusions; larger font size for core findings; boxes or light backgrounds for important formulas
- **Page density management**: Use multiple columns for comparing parallel content; use indentation and bullet levels to show hierarchy
- **Experimental charts**: Line charts (trend comparison), bar charts (method comparison), scatter plots (correlation analysis), radar charts (multi-dimensional comparison), etc.; all charts must have complete annotations. Common chart types not defined in pptd.md (such as waterfall charts) can be built using shape + text box combinations
- **Flowcharts/architecture diagrams**: Use shapes, arrows, and text to illustrate research method workflows or system architecture, suitable for presenting methodology and experimental design
- **Bullet lists**: Research contributions, experimental settings, ablation study conclusions, etc. presented as numbered lists, concise and clear
- **References**: Complete reference list on a dedicated page at the end; footnotes on content pages can include abbreviated key references cited on that page

## Image Usage Rules
**Allowed (informational images)** — Images that carry academic information:

| Image Type | Examples | Applicable Pages |
|---------|------|---------|
| Experimental apparatus/equipment | Lab setups, instruments, hardware prototypes | Methodology, experimental design pages |
| Data visualization screenshots | Software interfaces, simulation outputs, dataset samples | Results, methodology pages |
| System architecture diagrams | Network topology, algorithm flowcharts, system designs | Methodology, system design pages |
| Comparison images | Before/after results, qualitative evaluation samples | Results, evaluation pages |

**Prohibited (decorative images)** — Images that serve only aesthetic purposes:
- Stock photos of people, laboratories, or "science" concepts
- Abstract backgrounds, gradient textures, particle effects
- Decorative icons unrelated to the research content
- 3D rendered decorative elements

## Decoration Prohibitions
| Prohibited | Alternative |
|--------|---------|
| Gradient fills | Solid fills, or no fill (white background) |
| Shadows on any element | Flat design, or 1px solid borders for emphasis |
| Decorative icons and illustrations | Let text, formulas, and data speak |
| Rounded corners on containers | Sharp corners or 2-4px minimal rounding |
| 3D effects, bevels, reflections | Strictly 2D, flat design |
| Animated or transition effects | Static, professional layout |
| Decorative page borders or frames | Clean edges, whitespace as frame |
| Flashy backgrounds/textures | Pure white, very light gray, or other plain backgrounds |
| WordArt/text effects | Standard academic fonts, differentiated by weight and size |
| Charts without annotations | Complete annotations: title, axis labels, legend, units, data source |
| Gradient colors and shadow effects | Flat solid colors, maintaining clean academic chart standards |
| Excessive visual effects | Clean and restrained; the content itself is the focus |

## Additional Academic-Specific Guidelines
- **Formula pages**: Dedicate full pages to important derivations or proofs when necessary; ensure formula size is at least 18px equivalent
- **References page**: Include a dedicated final page or section listing all references in standard academic format (APA, IEEE, GB/T 7714, etc.)
- **Acknowledgments**: If applicable, maintain the same restrained style; avoid emotional or decorative imagery
- **Q&A preparation**: Consider adding a "Thank You / Q&A" final page with clean typography
