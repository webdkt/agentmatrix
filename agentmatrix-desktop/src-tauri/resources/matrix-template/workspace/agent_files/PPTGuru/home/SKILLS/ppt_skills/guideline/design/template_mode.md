# Template Mode Workflow

When the user uploads a presentation as a template or specifies a preset template, build the design.md document based on the template's visual style and page structure **using the file.write tool**.

## workflow

### Entry Point Decision

Determine which path to enter based on user input:

- User-uploaded template: The user uploaded a PPT/PPTX file or screenshot, requesting to "use this as a template" to create a new PPT
- Preset template: The user explicitly requests to use a specific .pptd file under template/

---

### User-Uploaded Template

The user provided their own PPT file as a template. You need to extract the complete visual system from it and generate design.md.

**Core principle: Use the user-uploaded PPT as the base, reuse elements from the original PPTD, rather than rebuilding from scratch.**

#### step1. Conversion and Style Analysis

1. **Convert to PPTD**: Use the convert script to convert the user-uploaded PPTX to the original PPTD file (which also produces `images/`, `fonts/`, and other resource directories)
2. **Generate screenshots**: Use the screenshot script to convert the PPTX to screenshots, then review them sequentially (if the user's presentation is lengthy, selectively read 8-12 pages)

**Critical metadata from conversion** — the converted PPTD contains layout metadata that MUST be preserved in the generated output:

- **`sourceTemplate`** (root-level): Points to the original `.pptx` file. The export script uses this to copy the template's slide master, layouts, and theme. Without it, all layout formatting (fonts, bullets, spacing inherited from master) is lost.
- **`layoutIndex`** (per-page): Identifies which slide layout from the template to use for each page. Determines the layout skeleton (title placement, content area, footers).
- **`placeholder`** (per-element): Maps an element to a layout placeholder via `idx` and `type`. When present, the export script preserves the layout's inherited formatting (bullet styles, indentation, default fonts) instead of creating a plain text box.

Based on the screenshots and original PPTD, systematically analyze the template's visual system:

- **Page type classification**: Analyze each page's category: cover, table_of_contents, chapter, content, final
- **Common element identification**: Identify common elements reused across content pages, such as header bars, navigation bars, page numbers, logos, decorative color bands, corner decorations, layout structures, content areas, etc.
- **Style anchor identification**: Determine whether the template belongs to a recognizable style school or brand system (e.g., McKinsey/BCG consulting style, Apple/Muji brand style, Bauhaus/Swiss International Style, etc.); beyond the anchor itself, more importantly, explain what aspect of this style to reference
- **Color and font analysis**: Extract core colors, font combinations, and font size hierarchy
- **Container and decoration analysis**: Card structures, separation methods, decorative elements
- **Image style analysis**: Visual style of icons, charts, tables, and illustrations
- **Layout pattern summarization**: Identify representative layout patterns for content pages

Based on the analysis results, output the complete design document following the "design.md Output Structure" below.

---

### Path B: Preset Template

The user specified a preset template name. You need to read the template file and corresponding style file, then generate design.md.

#### step1. Locate Template and Style Files

1. Based on the user-specified template name, look up the corresponding template file and style file in the preset template index table
2. Read the `template/{name}/{name}.pptd` template file to understand the existing page structure and visual system
3. **Check for `template.pptx`**: If `template/{name}/template.pptx` exists, this template has layout metadata (slide masters, layouts, placeholders). All template metadata requirements (sections 5, 6, 12) apply — the generated `.pptd` MUST declare `sourceTemplate`, pages MUST preserve `layoutIndex`, and elements MUST preserve `placeholder`.
4. **Read all .page files one by one**: Read each .page file under the template's `pages/` directory to understand the layout characteristics of the template
5. Read the `guideline/design/profiles/{profile}.md` style file to understand style requirements and content expression strategy

#### step2. Determine Whether Style Adjustments Are Needed

Compare user requirements with the template's preset style to determine if adjustments are needed:

- **Adjustments needed**: When the user's query contains explicit requirements inconsistent with the style file (e.g., different color scheme, font size preferences, layout preferences, etc.)
- **No adjustments needed**: If the user has no additional style requirements, design.md simply declares "execute entirely according to the preset style file and template file"

Based on the determination, output the complete design document following the "design.md Output Structure" below.

---

## design.md Output Structure

Whether user-uploaded or preset template, design.md must include the following sections, output in order:

### 1. Profile Baseline Declaration

- **Profile selection**: Specify which scenario profile file serves as the baseline for this design (e.g., `profiles/business_insight.md`, `profiles/general.md`, etc.)
- **Selection rationale**: Briefly explain why this profile was chosen (scenario match, audience characteristics, etc.)
- **Referenced dimensions**: Describe which dimensions were referenced from this profile — design philosophy, information density, color guidance, font guidance, layout patterns, content expression techniques, decoration prohibitions, etc.
- **Deviation notes**: If this design needs to deviate from certain profile guidance (e.g., user has explicit requirements, or template style is inconsistent with the profile), list each deviation point and reason here

### 2. Original Source Declaration

- **User-uploaded template**: Specify the original PPTD file path and resource directory paths (`images/`, `fonts/`); during subsequent generation, resources such as images are referenced directly from these paths (absolute path references)
- **Preset template**: Specify the template file used (`template/{name}.pptd`) and style file (`guideline/design/profiles/{profile}.md`)

### 3. Extract Style from Template

From the template's PPTD source files and screenshots, systematically extract **specific style parameters** (not descriptive language) to ensure generated pages are visually consistent with the template:

1. **Color Extraction**
   - Extract actual color values used in the template PPTD and map to theme.colors color roles:
     * **primary** (required): Theme color, record the specific color value (e.g., `#1e40af`)
     * **secondary** (required): Supporting color, record the specific color value
     * **accent** (optional): Emphasis color; do not set if the template has no clear accent color
     * **background** (required): Page background color
     * **text** (required): Body text color
   - User-uploaded template: Extract actual color values from .page files, rather than directly using color values defined in the uploaded template's .pptd file (since it is very likely the user did not define this section)
   - Preset template: Use the template's defined color scheme; note any adjustments here if needed

2. **Font and Font Size Hierarchy Extraction**
   - User-uploaded template: Check font files in the `fonts/` directory and prioritize using the template's original fonts; you may also read `format/fonts.md` for the preset font list
   - Extract **specific font size values** for each level from the template PPTD: actual fontSize for cover titles, page titles, subtitles, body text, annotations, etc.
   - **Font sizes should be consistent with the template**; recommended body font size is 18-22px (use 22px when page text content is minimal, 20px for moderate, 18px for heavy; must not go below 18px) to ensure presentation readability
   - Record specific parameters for font combinations (fontFamily), font weight (bold), line height (lineHeight), etc.

3. **Text Box and Container Style Extraction**
   - Extract **specific parameters** for cards/containers from the template PPTD: cornerRadius values, border styles (style/width/color), fill color values, shadow parameters, etc.
   - Content separation methods: Card separation, line separation, whitespace separation, color block separation? Record specific styles of separating lines (color, width)
   - Specific style parameters for decorative elements (texture color values, color band bounds/fill, angled shapes, etc.)
   - **Be sure to reference specific values from the original PPTD's .page files, rather than describing from memory**

4. **Image Style**: Extract the overall style of illustrations, icons, charts, tables, and other visual elements from the template
   - Icons: Outline icons or solid icons? What is the color strategy?
   - Tables: Extract specific tableStyle parameters from the template (headerFill, bodyFill, border, etc.)
   - Charts: Chart style preference, whether series colors follow the theme
   - Illustrations: Identify the template's illustration color palette (black & white/color, high saturation/low saturation, etc.), style, and processing method (original/mask overlay/cropped to specific shapes/desaturated, etc.)
     - **For preset template paths, template illustrations are only color palette and style references — they must NOT be used when creating the actual PPT!!**

5. **Other Content**: If the uploaded PPT contains style requirements in other forms (such as text content, image content, etc. within the PPT), read and follow them as well

### 4. Adjustments (If Any)

Output only when the user has additional style requirements inconsistent with the template:
- List each adjustment inconsistent with the template/profile, with rationale

### 5. Reusable Pages (When Template Has Layout Metadata)

Identify pages from the original PPTD that can be directly reused as-is (cover pages, table of contents pages, chapter pages, closing pages):
- List .page file names and page types (e.g.: cover page `cover`, chapter page `chapter_01`, closing page `final`)
- During generation, these pages' structures and elements are **directly extracted from the original PPTD**, with text content replaced and text box positions/text styles slightly adjusted based on new content to ensure highly consistent page styling

**Layout metadata preservation (mandatory)**:

When reusing template pages, the following metadata MUST be carried over to the generated .pptd and .page files:

1. **Root-level `sourceTemplate`**: The generated `.pptd` MUST declare `sourceTemplate: <filename>.pptx` pointing to the original template PPTX. This is the single most important field — without it, the export creates a blank PPTX and all layout formatting is lost.
2. **Per-page `layoutIndex`**: Each reused page MUST retain its `layoutIndex` value from the converted template. This selects the correct slide layout (title positioning, footer area, content placeholder structure) from the template's master.
3. **Per-element `placeholder`**: Elements that correspond to layout placeholders MUST retain `placeholder.idx` and `placeholder.type`. This allows the export script to preserve inherited formatting (bullet styles, indentation, default fonts) rather than creating plain text boxes.

### 6. Content Page Common Elements (When Template Has Layout Metadata)

List common elements reused across content pages, **recording each element's complete attributes** to ensure strict replication during generation:

- List each common element's elementId and type (e.g., header bar, navigation bar, page number, logo, decorative color band, etc.)
- **Record key attributes**: bounds (position and size), fill (solid/gradient), border (border style), text content and style (if any), image reference path (if any)
- **Record `placeholder` metadata**: For elements that map to layout placeholders (especially page numbers, footers, headers), record `placeholder.idx` and `placeholder.type`
- During content page generation, these common elements are **copied verbatim** without modifying position, style, or image references; only the content area is filled

### 7. Content Page Structure Specification

Define the **fixed framework** for content pages; all newly generated content pages must fill content within this framework:

- **Title area**: Extract the page title's fixed position (bounds), font size, color, font, and alignment from the template. If the title element has `placeholder` metadata, record its `idx` and `type` for reuse.
- **Content area**: Specify the content area's bounds range (i.e., the usable space after removing common elements and the title area); all content elements must be laid out within this range. If the content area maps to a layout placeholder (e.g., `type: body`), record the `placeholder.idx` so new content elements can inherit the layout's bullet/indent formatting.
- **Footer area** (if any): Fixed position and style for page numbers, footnotes, data sources, etc. Footer elements typically have `placeholder` metadata (e.g., `type: ftr`, `type: sldNum`) — these MUST be preserved.

> The purpose of this specification is to ensure that every newly generated content page has title position, content area, and common decorative elements identical to the template, with only the specific elements within the content area varying due to different content.

### 8. Content Page Layout Strategy

#### Chapter Page Style Selection

The chapter/section transition page can use **either light or dark background** depending on the presentation's tone and audience. The choice must be explicitly documented in design.md:

- **Light chapter page** (default for most scenarios):
  - White or `$background` color background
  - Large semi-transparent chapter number as watermark (e.g., `$secondary` at 20-30% opacity)
  - Chapter title in `$primary` or `$text` color below the watermark
  - Clean, airy feel; suitable for academic, education, business insight, work report profiles
  - Example: `template/strategic-1/pages/chapter.page` (light variant)

- **Dark chapter page** (for high-stakes strategic/gravitas scenarios):
  - `$primary` or `$darkBg` color filling the entire page
  - Accent color strip (8px) on the left edge
  - "CHAPTER 01" label in small uppercase letters
  - Large semi-transparent white watermark number (e.g., `#FFFFFF14`)
  - Chapter title in white, subtitle in `$lightAccent`
  - Progress indicator ("第一章 / 共八章") in bottom-right
  - Formal, authoritative feel; suitable for board presentations, investor pitches, IPO roadshows
  - Example: create by copying `template/chapter_dark.page` pattern

> **Do not force dark chapter pages on all templates.** Match the chapter style to the profile's gravitas: dark for strategic/fundraising, light for academic/education/general. When in doubt, default to light.

- **User-uploaded template**: Extract **complete page file structures** from representative content pages in the template as layout skeletons
  - List .page file names and layout characteristic descriptions (e.g.: `slide_03` — left image right text, `slide_05` — three-column cards)
  - During generation, **directly copy** the corresponding layout skeleton's page file structure (common elements + content area framework), then replace specific elements in the content area (reusing template content area layouts is encouraged)
  - Variants may be moderately expanded based on existing layouts, but expanded variants **must strictly follow**: same common elements, same title area, same content area bounds, same container style parameters
- **Preset template**:
  - Reference preset template content page styles for layout, **must strictly follow the template's design language** (same spacing patterns, container styles, font size hierarchy, decorative elements), **must preserve the original layout structure, common elements, container styles, and spacing parameters**
  - Full reuse of content pages from the template is allowed, but **the same layout must not appear consecutively more than 2 times**; layout selection should be based on content characteristics from outline.md

- Special content pages may be expanded:
  * Full-page image + gradient mask + brief content as transition pages
  * Full-page tables, full-page charts
- **Strictly prohibit numerical overfitting**: Layout descriptions should be flexible patterns, not specifying "has N points" or other specific quantities

### 9. Style Usage Rules

Describe how each Theme style should be used across different scenarios, including:
- Which element types and page scenarios each textStyle applies to
- How each color is allocated across text, backgrounds, decorations, etc.
- Usage scenarios for tableStyle

### 10. Risk Prohibitions

Based on this PPT's scenario, style, and layout characteristics, extract **the prohibitions most likely to be violated this time** from the above design specifications and scenario profiles, listed as a checklist to serve as warnings during subsequent generation. For example:
- Color prohibitions (e.g., which cliche color schemes this scenario tends to fall into)
- Layout prohibitions (e.g., alignment/whitespace issues common in this layout style)
- Decoration prohibitions from the scenario profile (e.g., decorative elements unsuitable for this scenario)
- Content expression prohibitions (e.g., expression styles unsuitable for this audience)

- Font size prohibitions: **Explicitly list font size constraints for each element type**, such as minimum body font size, minimum title font size, minimum auxiliary text/annotation font size, minimum table/chart label font size, etc. to prevent excessively small font sizes during generation that affect readability

- **Template reuse prohibitions** (applicable when template has `template.pptx` / layout metadata):
  - **Do not ignore existing template pages and design from scratch** — must prioritize reusing the template's built-in .page files; custom layouts are only allowed when all template pages have been used or no suitable page exists
  - **Do not completely restructure template pages** — must not change the overall layout direction (e.g., horizontal → vertical), remove common elements, or significantly adjust content area bounds
  - **Do not treat templates merely as "style references"** — template pages are directly reusable layout skeletons, not just style examples for reference
  - **Do not omit `sourceTemplate`** — the generated `.pptd` MUST declare `sourceTemplate` pointing to the original template PPTX; without it the export creates a blank PPTX and all layout formatting is lost
  - **Do not drop `layoutIndex` or `placeholder` metadata** — when reusing template pages, preserve `layoutIndex` on each page and `placeholder.idx`/`placeholder.type` on elements that map to layout placeholders

Only list prohibitions that are **genuinely relevant** to this PPT; do not generically list all universal prohibitions.

### 11. Theme Definition

Based on all the above design decisions (color scheme, fonts, font size hierarchy, table styles, etc.), output the complete pptd theme YAML definition:

- **User-uploaded template**: If the template already uses a theme, preserve the original theme; if not, construct a new theme based on actually used colors, text styles, and table styles
- **Preset template**: Use the theme already defined in the template; note any adjustments here if needed

```yaml
theme:
  colors:
    primary: "#1e40af"
    secondary: "#64748b"
    accent: "#f59e0b"
    background: "#ffffff"
    text: "#1f2937"
  textStyles:
    title:
      fontSize: 48
      color: "$primary"
      fontFamily: "MiSans"
    subtitle:
      fontSize: 24
      color: "#6b7280"
      fontFamily: "MiSans"
    body:
      fontSize: 18
      color: "$text"
      lineHeight: 1.6
  tableStyles:
    default:
      headerFill: "$primary"
      headerColor: "#ffffff"
      headerBold: true
      bodyFill: ["#ffffff", "#f8f9fa"]
      bodyColor: "$text"
      firstColumnBold: true
      border:
        style: solid
        width: 1
        color: "#e0e0e0"
```

### 12. Template Metadata for Generated .pptd (When Template Has Layout Metadata)

When generating the final `.pptd` file, the following metadata fields MUST be included to ensure the exported PPTX retains the template's layout formatting:

```yaml
# Root-level — points to the original template PPTX
sourceTemplate: template.pptx

# Per-page — selects the slide layout from the template
pages:
  - pages/cover.page     # page file with layoutIndex inside
```

Per-page `.page` files MUST include `layoutIndex`:
```yaml
pageType: cover
layoutIndex: 1          # ← selects layout[1] from the template PPTX
layoutName: Title Slide  # ← optional, for documentation
```

Elements that map to layout placeholders MUST include `placeholder`:
```yaml
- elementId: coverTitle
  elementType: text
  bounds: [83, 226, 672, 134]
  placeholder:           # ← preserves layout-inherited formatting
    idx: 0
    type: ctrTitle
  content:
    text: <p>My Title</p>
```

**Why this matters**: The export script uses `sourceTemplate` to copy the template PPTX (preserving slide masters, layouts, and theme). `layoutIndex` selects the correct layout for each page. `placeholder` maps elements to layout placeholders, preserving inherited formatting (bullet styles, indentation, default fonts). Without these, the export creates a blank PPTX and all layout formatting is lost.

---

## Preset Template Index

| Template Name | Template File | Corresponding Style | Applicable Scenarios |
|---|---|---|---|
| Classic Gray Elegance | `template/academic-1/academic-1.pptd` | `profiles/academic.md` | Thesis defense, academic presentations |
| Dark Red Gold Classic | `template/academic-2/academic-2.pptd` | `profiles/academic.md` | Thesis defense, research reports |
| Blue-White Minimalist | `template/academic-3/academic-3.pptd` | `profiles/academic.md` | Graduate thesis defense |
| Purple Serene | `template/academic-4/academic-4.pptd` | `profiles/academic.md` | Academic lectures, thesis defense |
| Lake Blue Diamond | `template/academic-5/academic-5.pptd` | `profiles/academic.md` | Research project presentations, academic reports |
| Emerald Gold Insight | `template/business_insight-1/business_insight-1.pptd` | `profiles/business_insight.md` | Business strategy reports, market analysis |
| Steel Gray Texture | `template/business_insight-2/business_insight-2.pptd` | `profiles/business_insight.md` | In-depth industry research, industrial analysis |
| Red Line Sharp | `template/business_insight-3/business_insight-3.pptd` | `profiles/business_insight.md` | Consulting reports, industry research |
| Navy Copper Gold | `template/business_insight-4/business_insight-4.pptd` | `profiles/business_insight.md` | Investment research reports, financial data analysis |
| Burgundy Consulting | `template/business_insight-5/business_insight-5.pptd` | `profiles/business_insight.md` | Strategic consulting reports, business analysis |
| Inspiration Ark | `template/education-1/education-1.pptd` | `profiles/education.md` | Adult education training, knowledge lectures |
| Light of Enlightenment | `template/education-2/education-2.pptd` | `profiles/education.md` | Middle school math teaching, course lectures |
| Blue-Orange Classroom | `template/education-3/education-3.pptd` | `profiles/education.md` | Middle school teaching, math courses |
| Coral Academic | `template/education-4/education-4.pptd` | `profiles/education.md` | Student course presentations, thesis defense |
| Emerald Gold Forum | `template/education-5/education-5.pptd` | `profiles/education.md` | University academic lectures, education forums |
| Midnight Luxury | `template/promotion-1/promotion-1.pptd` | `profiles/promotion.md` | Brand promotion, luxury marketing |
| Forest Green Marketing | `template/promotion-2/promotion-2.pptd` | `profiles/promotion.md` | Marketing proposals, project pitches |
| Elegant Portfolio | `template/promotion-3/promotion-3.pptd` | `profiles/promotion.md` | Photography portfolios, visual showcase |
| Warm Brown Journal | `template/promotion-4/promotion-4.pptd` | `profiles/promotion.md` | Creative portfolios, personal brand showcase |
| Midnight Blue Copper | `template/strategic-1/strategic-1.pptd` | `profiles/strategic.md` | Corporate strategic planning, board presentations |
| Dawn Pioneer | `template/strategic-2/strategic-2.pptd` | `profiles/strategic.md` | Strategic planning, fundraising roadshows |
| Dark Tech | `template/strategic-3/strategic-3.pptd` | `profiles/strategic.md` | Tech strategic planning, product strategy |
| Wooden Oasis | `template/strategic-4/strategic-4.pptd` | `profiles/strategic.md` | Sustainability strategy, ESG reports |
| Consulting Edge | `template/work_report-1/work_report-1.pptd` | `profiles/work_report.md` | Annual work summaries, quarterly reports |
| Nordic Breeze | `template/work_report-2/work_report-2.pptd` | `profiles/work_report.md` | Annual review reports, corporate retrospectives |
| Dawn Gradient | `template/work_report-3/work_report-3.pptd` | `profiles/work_report.md` | Work summaries, quarterly achievement showcase |
| Rhythm Grayscale | `template/work_report-4/work_report-4.pptd` | `profiles/work_report.md` | Annual work reports, quarterly summaries |
| Efficiency Network | `template/work_report-5/work_report-5.pptd` | `profiles/work_report.md` | Quarterly work reports, team achievement showcase |
| Azure Impact | `template/general-1/general-1.pptd` | `profiles/general.md` | Product launches, marketing events |
| Lead Gray Future | `template/general-2/general-2.pptd` | `profiles/general.md` | Technology introductions, product showcases |
| Fresh Water Blue | `template/general-3/general-3.pptd` | `profiles/general.md` | General showcases, project promotions |
| Ink Jade Edge | `template/general-4/general-4.pptd` | `profiles/general.md` | Brand introductions, general showcases |
| Sandstone Rhythm | `template/general-5/general-5.pptd` | `profiles/general.md` | Knowledge sharing, general presentations |

### NEXT STEP
1. Generate the complete design.md document
2. Based on user requirements, generate the presentation
