================================================================================
PART 1: SKILL.md — PPT技能入口和总体框架
================================================================================

---
name: pptx
description:  The only skill for all PPT/presentation creation and editing tasks. Any requests involving PowerPoint, PPT, PPTX, slides or presentations must be processed using this skill, including but not limited to: creating, generating, editing, modifying, redesigning, formatting, beautifying or converting presentations, as well as modifying .pptx files uploaded by users.\nImportant note: Presentation creation must use the PPTD domain-specific language (.pptd/.page) provided by this skill. Direct creation, editing or generation of .pptx files using python-pptx, OpenXML SDK or any other libraries/methods is prohibited.
---

# Definition
The pptx skill is responsible for generating, creating, or editing PPTX presentations. This skill defines an intermediate layer (with the .pptd extension) that further abstracts OOXML, making presentation generation effortless.

# .pptd Format
- The .pptd format is a simplified abstraction layer over OOXML, based on YAML syntax, designed specifically for AI to read and write presentations. This abstraction retains the core content of OOXML (themes, page layouts, element positions and definitions, etc.) while removing complex nested logic such as Masters, making each page self-contained and WYSIWYG.
- User usage: In the frontend, users can directly open .pptd files for preview, or click the "Export" button to convert .pptd to .pptx. Converting .pptx or .pptd files to images for preview purposes is strictly prohibited.
- Read format/pptd.md for the detailed definition of the .pptd format.

# Reading User-Uploaded PPTs
If you only want to read a PPT and loaded this skill by mistake, you can read user-uploaded .pptx files through the following three methods to obtain different levels of information:
1. read_file tool: Parses the .pptx file into markdown text, suitable for quickly obtaining the text content and basic structure of the PPT.
2. screenshot script: Generates screenshots of .pptx pages, suitable for obtaining the visual design and layout information of the PPT.
```bash
scripts/screenshot.sh path/input.pptx -o screenshot/

# You can also specify page numbers:
scripts/screenshot.sh path/input.pptx -p 1,3,5 -o screenshot/

# Or specify a page range:
scripts/screenshot.sh path/input.pptx -p 2-6 -o screenshot/
```
3. convert script: Converts .pptx to .pptd file format, obtaining complete information about the .pptx file, such as page notes and layouts, element positions, sizes, content, settings, etc. Suitable for editing user-uploaded .pptx files or when you need an in-depth understanding of the .pptx file structure.
```bash
scripts/convert.sh input.pptx -o output_dir/
```
- Methods listed later provide more detailed information, but also consume more context. You need to decide how to read the PPT based on the actual situation.

# PPTX Presentation Generation
When the user requests: creating a PPT / converting a document to PPT / replicating an image or website as a PPT / using an uploaded .pptx as a template / creating a PPT referencing a PPT style, read guideline/generate_slides.md for more guidance.

# Editing User-Uploaded PPTX Presentations
When the user requests modifying an uploaded PPT, read guideline/edit_user_slides.md for more guidance.

# Skill File Tree

```
pptx/
├── SKILL.md                        ← This file (skill entry point)
├── format/                         → PPTD format specification
│   ├── pptd.md                     → PPTD full specification
│   ├── shapes.md                   → Complete shape list
│   └── fonts.md                    → Available font list
├── guideline/                      → Workflow guidelines
│   ├── generate_slides.md          → Presentation generation
│   ├── edit_user_slides.md         → Editing user-uploaded PPTX
│   ├── content/                    → Content design modes
│   │   ├── outline_mode.md         → Outline mode
│   │   ├── summary_mode.md         → Summary mode
│   │   └── search_mode.md          → Search mode
│   ├── design/                     → Visual design modes
│   │   ├── creative_mode.md        → Creative mode
│   │   ├── reference_mode.md       → Reference/replication mode
│   │   ├── template_mode.md        → Template mode
│   │   ├── template/               → Preset template files
│   │   └── profiles/               → Scene style presets
│   └── search/                     → Search guidelines
│       └── text_search.md          → Information search
└── scripts/                        → Scripts and source code
    ├── check.sh                    → PPTD checker (format validation + overflow/occlusion detection)
    └── screenshot.sh               → PPTX screenshot script
```

# ATTENTION

## YAML Quoting Rules (Must Follow)
- The `content.text` field **must use block scalar (`|`)** and must not be wrapped with `"` or `'`, otherwise double quotes in HTML attributes (e.g., `style="..."`) will cause YAML parsing errors.
- For other fields, if the value contains special characters such as `:`, `#`, `{`, `}`, wrap them with quotes or use block scalar.

## Basic Guidelines
1. Scope of operations: Directly operating on .pptx files is strictly prohibited. All your operations should apply to .pptd files, and you are also prohibited from converting .pptd files to .pptx files. Users who need .pptx files should convert .pptd to .pptx themselves by clicking the card below to enter the editor page, then clicking the "Export" button.
2. In-place delivery: .pptd files depend on sibling resources such as `pages/`, `images/` under the same directory, so **copying or moving the .pptd file alone is strictly prohibited**. If relocation is required, the entire directory must be migrated together — otherwise the Artifact Output will not be clickable because its dependencies cannot be found.
3. Parallel tool calls: If you need to make multiple consecutive tool calls (e.g., generating multiple .page files in sequence; making multiple edit tool calls to modify different locations in the same file, etc.), you should make multiple parallel tool calls in a single output, rather than making separate thinking-toolcall, thinking-toolcall rounds. This avoids context redundancy caused by multiple rounds of output.
4. When the user requests creating multiple presentations, **you must adopt a generate-all-first, then check-one-by-one strategy!** That is, serially complete the creation or modification of each PPT (including .page files and .pptd files), and only proceed to unified checking, fixing, and delivery after all presentations are created. **Never complete one PPT and immediately check, fix, and deliver it before creating the next PPT**.

================================================================================
PART 2: generate_slides.md — 生成工作流（8步法）
================================================================================

# Presentation Generation

## File Isolation
Create an independent working directory for the current PPT task (directory name based on the English short name of the title/topic), and write all artifacts into this directory:
```
output/<ppt-dir>/
├── design.md          # Design document
├── outline.md         # Outline document
├── <ppt-name>.pptd   # PPT main entry file
└── pages/             # .page file directory
```

## Workflow

### step1: File Reading
- If the user has uploaded files, **read them in full** first, including images, documents, websites, etc. Do not proceed until all files have been fully read.

### step2: User Requirements and Audience Analysis
- Analyze the user's requirements for the final presentation, including:
  1. Language requirements: Does the user have a specific language preference? If not, match the language of the user's input
  2. Provided content requirements: Did the user provide a research topic, or a complete outline with page-level planning? Are there complete reference materials or reference images?
  3. Page count requirements
  4. Content requirements: Does the user have specific charts, data, conclusions, or topic requirements, or specific requirements for language style?
  5. Visual requirements: Does the user have specific design style or color scheme requirements, or specific requirements for images, charts, and other elements?
  6. Audience analysis: Analyze the target audience the user is likely addressing, including age, profession, expertise level, expected content presentation style, etc.

### step3: Determine Working Mode
Based on the user requirements analyzed in step2, determine which working mode to enter:
- Visual mode:
  1. Replication/Reference mode: e.g., user uploads images or websites and asks you to replicate them as PPT; or asks to create a PPT in the same style as reference screenshots
  2. Creative mode: No visual references provided, only style/color requirements or nothing at all
  3. Template mode: User uploads a PPT and requests it be used as a template for a new PPT, or explicitly specifies using a preset template
- Content mode:
  1. Summary mode: e.g., user uploads a long document (such as a paper, report, etc.) and asks you to generate a PPT based on it
  2. Outline mode: e.g., user provides an outline with per-page content planning; or provides a highly structured outline
  3. Search mode: User provides no outline or long document, only a topic and related requirements, requiring you to search and supplement content

**Note: If entering template mode, perform step5 content design first, then combine with content for step4 visual design!!**

### step4: Visual Design
- Based on the visual mode determined in step3, enter the corresponding visual design workflow, **use the file.write tool** to complete the visual design document `<ppt-dir>/design.md`
  1. Replication/Reference mode: Read guideline/design/reference_mode.md for more information
  2. Creative mode: Read guideline/design/creative_mode.md for more information
  3. Template mode: Read guideline/design/template_mode.md for more information
    * Note: Only enter template mode when the user explicitly requests using the uploaded PPT as a template or specifies using a preset template! Otherwise, reading template_mode.md is strictly forbidden!
- **design.md is the core visual reference for subsequent presentation generation. It must be persisted using the file.write tool for step6 to read and reference. It is strictly forbidden to only output it in the conversation.**

### step5: Content Design
- Based on the content mode determined in step3, enter the corresponding content design workflow, **use the file.write tool** to complete the content design document `<ppt-dir>/outline.md`
  1. Summary mode: Read guideline/content/summary_mode.md for more information
  2. Outline mode: Read guideline/content/outline_mode.md for more information
  3. Search mode: Read guideline/content/search_mode.md for more information
- **outline.md is the core content reference for subsequent presentation generation. It must be persisted using the file.write tool for step6 to read and reference. It is strictly forbidden to only output it in the conversation.**

### step6: Generate Presentation
- Refer to the image supplementation strategy below to add appropriate illustrations to the presentation
- Generate the presentation based on the visual design and content outline. Ensure full compliance with the format requirements defined in format/pptd.md during generation.
- If outline.md contains annotated source URLs, use `<a href="url">` in the PPTD to link key data, cited viewpoints, etc. to the original source pages, making it easy for the audience to trace and verify.
- Generation order: Files must be generated in the following order. Skipping pages or writing page files first is strictly forbidden:
  1. First generate the .pptd main file under `<ppt-dir>/`
  2. Then generate .page files in page order: Starting from page 1, generate sequentially according to the page order in outline.md, without skipping or reordering
  * The reason: The .pptd main file defines the global theme and page list, serving as the contextual foundation for all page files. Sequential generation ensures content continuity and style consistency between pages, avoiding context breaks caused by page skipping.

#### Image Supplementation Strategy
1. Prioritize extracting suitable images from user-uploaded content (such as Word, PDF, PPTX, etc.) as presentation illustrations
2. If the user has not provided sufficient and suitable images, and has not explicitly requested no additional images, you should by default use image search, image generation tools, etc. to prepare appropriate illustrations for the presentation
3. Image search strategy:
  - Collected images should reference the visual design style in design.md, pursuing movie poster or magazine cover level visual impact and aesthetics. Prioritize high-resolution, watermark-free images
  - Using English keywords for searches typically yields higher quality results. Append style keywords to match the design style. Never include words like PPT, presentation, premium color scheme: these will cause search results to return PPT screenshots
  - Do not search for data charts (line charts, bar charts, pie charts, etc. — use chart elements), table screenshots (use table elements), icons (use icon elements), or diagrams (flowcharts, hierarchy diagrams, architecture diagrams, etc. — use shape+text+line element combinations)
4. Retry strategy: If initial search results are of poor quality, you must try different keywords or use image generation tools (if available). ***Never use low-quality images or substitute with gradients/solid colors/placeholders!**
  - Do not replace image slots that originally need images with solid color backgrounds, gradient fills, shape compositions, etc. just because searching is difficult. If a suitable image truly cannot be found, use the closest search result rather than removing the image.
5. Image usage guidelines
  - Cover/chapter/closing pages: Full-bleed high-quality images with gradient masks are recommended to create visual impact
  - Content pages: Images should be directly relevant to the page content; avoid purely decorative images
  - Image sizing: Set sizes appropriately based on layout needs; cropping is preferred; avoid stretching unless necessary

#### Text Box Size Estimation
- Text box wrapping control: When generating PPTD, you **must** explicitly set `wrap: false` for every text box intended to display on a single line: title text boxes, labels/badges, data numbers, navigation elements, etc.
- Line height calculation: The actual rendered line height of a font is approximately fontSize x 1.3 (ascent + descent in font metrics), not fontSize itself. Therefore:
  * Single-line text height = fontSize x max(lineHeight, 1.3)
  * X-line text height = fontSize x max(lineHeight, 1.3) x X
  * Example: fontSize=14, lineHeight=1.2 -> single-line height = 14 x 1.3 = 18.2px, not 14 x 1.2 = 16.8px.
- Text width calculation:
  * Chinese character width is approximately fontSize; English/digit width is approximately fontSize x 0.5~0.6
  * With letter spacing: total width is approximately fontSize x Y + letterSpacing x (Y - 1)
- Text box size calculation for required content
  * Use the above methods to calculate text width and line height, combined with paragraph spacing settings, to estimate the required text box dimensions (width and height)
  * Ensure text box dimensions match actual text content size: oversized content will cause text overflow; undersized content will cause page whitespace

#### Overall Page Layout Control
- Set body area content appropriately: After removing fixed page elements (title, footnotes, etc.), the body content area layout should also be evenly and reasonably distributed:
  * Avoid excessive content concentration: Avoid content height being far less than the page body area height (e.g., body area height 500px, content only 200px). Use font size, element spacing, number of decorative elements, etc. to ensure actual content height is close to the page body area height
  * Avoid top-heavy bottom-empty: When content is sparse and genuinely far less than the body area height, ensure the actual content area is centered within the body area with equal top and bottom whitespace. Content concentrated at the top with excessive bottom whitespace is strictly forbidden
- Maintain grid alignment: Ensure all elements are properly aligned
  * For left-right layouts, ensure left and right content grids are aligned with consistent heights: avoid one side extending to the bottom while the other only fills halfway
  * For top-bottom layouts, ensure content has equal left and right whitespace: avoid content concentrated on the left with large right-side whitespace

### step7: Check .pptd Files

1. Check
- After generating the .pptd files, you **must** use the built-in checker to verify the files, ensuring no format errors or unexpected overflow issues:
> Tip: Use relative paths. Make sure to cd to the pptx skill directory before running check.sh
```bash
scripts/check.sh filename.pptd
```
- The checker will check for the following issues, divided into Error and Warning categories:
  * Format check: Whether YAML syntax is valid, required fields are present, field values are valid, elementId is unique within pages, etc.
  * Data validation: Color format and reference validity, elements exceeding page boundaries, shapeName validity, chart/table data completeness
  * Layout detection: Text occlusion, text box misalignment with underlying containers
  * Text box content detection: Text width/height overflow, text underfill

2. Fix
- Fix all ERRORs first: These issues will cause conversion failures and must be fixed
- Then handle WARNINGs: **PPTD renders precisely and will not automatically scale text or adjust layout. Every WARNING reported by the checker means a corresponding visual issue (truncation, occlusion, overflow, etc.) will appear in the final PPTX and will not be auto-corrected.** Therefore, WARNINGs must be fixed by default unless you can clearly determine that the WARNING is part of the intended design (e.g., decorative elements intentionally extending beyond the canvas). If skipping a WARNING, you must explain the reason.
- **Fix in parallel**: **You must call the edit_file tool in parallel as much as possible in a single response**, fixing issues across multiple files at once rather than fixing files one by one sequentially.
  1. TextOverflowWarning (text overflow): The space required by text content exceeds the text box space, causing content truncation (must fix)
  2. TextOcclusionWarning (text occlusion): Text is occluded by other elements (images/shapes/text boxes, etc.), making text unreadable
  3. TextDriftWarning (text drift): The text box is pierced through by other elements, or is not fully aligned with underlying shapes, images, etc.
  4. TextUnderfillWarning (text underfill): The text box is too large or the font size is too small, resulting in large blank areas within the text box, often causing unexpected whitespace on the page
  5. BoundsOutsideWarning (out of bounds): The element is partially or fully outside the canvas dimensions, making it partially or fully invisible

3. Re-verification
- After fixing, **re-run the checker** and **review the complete output** (using grep/sed to filter is forbidden). Focus on the Summary at the bottom, checking the count of each issue type to confirm all ERRORs have been eliminated and all unexpected WARNINGs have been addressed. If residual issues remain, continue fixing and repeat verification until the Summary shows `0 errors, 0 warnings`. **Using grep to filter and only viewing/fixing partial issues is strictly forbidden!**

#### Fix Precautions
- Maintain margins: After adjusting element bounds, check whether reasonable spacing is still maintained between the element and page edges, adjacent elements, and bottom elements. Do not forget to leave appropriate margins when adjusting bounds to resolve text overflow or whitespace issues, causing text boxes to be pressed against edges and losing original margins. **Fixed bounds should maintain consistent margins with other elements of the same type on the page.**
- Do not move common element positions: Common elements on pages (such as navigation bars, titles, corner badges, etc.) should maintain consistent positions across pages. When layout issues exist, prioritize adjusting content layout to avoid subtle differences in common elements across pages (such as inconsistent heights, font sizes, etc.; intentionally designed special layouts are exceptions)
- Ensure content alignment: When adjusting element A, ensure related elements are adjusted in sync. Common situations include:
  * Adjusted text box size but did not sync the background color/card size beneath the text box
  * Adjusted element A's position but did not sync attached decorative elements (such as decoration bars, progress bars, etc.) in size and position, causing misalignment

#### Text Overflow Fix Strategy
When the checker reports TextOverflowWarning, fix in the order suggested by the checker:
- Height overflow:
  1. Condense text: Compress expressions, merge points, remove secondary content
  2. Reduce font size: Decrease content font size, line spacing, paragraph spacing, etc.
  3. Expand text box height: If the above approaches are not feasible and there is space below the text box, increase the bounds height to accommodate the content. But be careful not to introduce overlap or drift issues
- Width overflow:
  1. Condense text: Shorten text content, reducing the content volume to the percentage suggested by the checker
  2. Switch to multi-line: Set `wrap: true` to enable auto-wrapping, and adjust text box height and layout accordingly
> **It is forbidden to excessively reduce font size to eliminate overflow, causing large blank areas within the text box** -- this is more detrimental to aesthetics than slight overflow.

### step8: Deliver .pptd Files
- **In-place delivery — do not copy the .pptd file alone.** .pptd is the entry of a multi-file project and strictly depends on sibling directories such as `pages/`, `images/` (and possibly `svg/`). Running `cp xxx.pptd /some/other/dir/` will cause the Artifact Output to fail because its dependencies cannot be found.
  - Option A (recommended): **Build the ref card directly against the .pptd's original path**, with no file movement needed
  - Option B: If relocation is truly required, **migrate the entire directory together**
- Inform the user that the presentation is complete, and provide a summary of the content highlights, core insights, specific structure, and other key information.
- Inform the user that they can click the card in the conversation to view and download the presentation in PPTX format

## Additional Notes

### Multi-Presentation Generation
When the user requests creating multiple presentations, **you must adopt a generate-all-first, then check-one-by-one strategy!** That is, serially complete the creation or modification of each PPT (including .page files and .pptd files), and only proceed to unified checking, fixing, and delivery after all presentations are created. **Never complete one PPT and immediately check, fix, and deliver it before creating the next PPT**.

### Parallel Writing
**You must call the file.write tool in parallel as much as possible in a single response.** Specifically:
- After generating the .pptd main file, write as many .page files as possible in parallel in the same response
- Each .page file is an independent file.write call with no dependencies, and should all be issued in the same response

================================================================================
PART 3: template_mode.md — 模板模式规范
================================================================================

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
3. **Read all .page files one by one**: Read each .page file under the template's `pages/` directory to understand the layout characteristics of the template
4. Read the `guideline/design/profiles/{profile}.md` style file to understand style requirements and content expression strategy

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

### 5. Reusable Pages (User-Uploaded Template Only)

Identify pages from the original PPTD that can be directly reused as-is (cover pages, table of contents pages, chapter pages, closing pages):
- List .page file names and page types (e.g.: cover page `cover`, chapter page `chapter_01`, closing page `final`)
- During generation, these pages' structures and elements are **directly extracted from the original PPTD**, with text content replaced and text box positions/text styles slightly adjusted based on new content to ensure highly consistent page styling

### 6. Content Page Common Elements (User-Uploaded Template Only)

List common elements reused across content pages, **recording each element's complete attributes** to ensure strict replication during generation:

- List each common element's elementId and type (e.g., header bar, navigation bar, page number, logo, decorative color band, etc.)
- **Record key attributes**: bounds (position and size), fill (solid/gradient), border (border style), text content and style (if any), image reference path (if any)
- During content page generation, these common elements are **copied verbatim** without modifying position, style, or image references; only the content area is filled

### 7. Content Page Structure Specification

Define the **fixed framework** for content pages; all newly generated content pages must fill content within this framework:

- **Title area**: Extract the page title's fixed position (bounds), font size, color, font, and alignment from the template
- **Content area**: Specify the content area's bounds range (i.e., the usable space after removing common elements and the title area); all content elements must be laid out within this range
- **Footer area** (if any): Fixed position and style for page numbers, footnotes, data sources, etc.

> The purpose of this specification is to ensure that every newly generated content page has title position, content area, and common decorative elements identical to the template, with only the specific elements within the content area varying due to different content.

### 8. Content Page Layout Strategy

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

- Font size prohibitions: **Explicitly list font size constraints for each element type**, such as minimum body font size, minimum title font size, minimum auxiliary text/annotation font size, minimum table/chart label font size, etc., to prevent excessively small font sizes during generation that affect readability

- **Template reuse prohibitions** (applicable to user-uploaded templates):
  - **Do not ignore existing template pages and design from scratch** — must prioritize reusing the template's built-in .page files; custom layouts are only allowed when all template pages have been used or no suitable page exists
  - **Do not completely restructure template pages** — must not change the overall layout direction (e.g., horizontal → vertical), remove common elements, or significantly adjust content area bounds
  - **Do not treat templates merely as "style references"** — template pages are directly reusable layout skeletons, not just style examples for reference

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

================================================================================
PART 4: summary_mode.md — 内容摘要模式规范
================================================================================

# Summary Mode Workflow

When the user uploads a long document (such as a paper, report, article, etc.) and requests generating a presentation based on its content, in-depth understanding and distillation of the document is required, ultimately delivering a presentation outline.

## workflow

Based on the user requirements and audience analysis completed in generate_slides.md step2, proceed with content design.

### step1. In-Depth Document Understanding

Perform systematic reading and analysis of the user's uploaded document:

1. **Structure mapping**: Identify the document's overall structure -- chapter divisions, argument hierarchy, reasoning logic
2. **Core extraction**: Mark the document's core arguments, key data, important conclusions, and innovative viewpoints
3. **Audience adaptation**: Based on the target audience's expertise level, determine which content needs to retain its original depth, which needs simplified explanation, and which can be omitted
   - For professional audiences: Retain technical details, data-driven arguments, methodology
   - For non-professional audiences: Highlight conclusions and implications, simplify process descriptions, add background explanations

### step2. Supplementary Search (Optional)
- If the document content requires additional background information, data support, or the latest developments to enhance the presentation, conduct targeted searches
- Supplemented content must be clearly annotated with information sources (with URLs) to distinguish it from the original content

### step3. Content Reorganization and Narrative Design

Reorganize the document content into a narrative structure suitable for presentations:

1. **Narrative logic selection**: Prioritize the original text's narrative logic. If the original narrative logic has shortcomings, select an appropriate narrative approach based on the document type and audience:
   - Papers/research reports: Background -> Methods -> Findings -> Conclusions -> Implications
   - Industry reports: Current state -> Trends -> Opportunities and challenges -> Recommendations
   - Business proposals: Problem -> Analysis -> Solution -> Expected outcomes
   - Or other narrative structures that suit the content characteristics

2. **Content filtering and distillation**
   - Distill core viewpoints, with each page focusing on one clear information point
   - Retain key data, charts, and case studies from the original text as support; trim redundant arguments, repetitive content, and excessive details
   - Prioritize original content; mark search-supplemented content with "[supplemented]" in the outline

### step4. Outline Writing

Based on the content reorganization results, use the `file.write` tool to construct the presentation outline `outline.md`.

#### Outline Design Principles

1. **Faithful to the original**: The outline structure should reflect the core logic of the original text without deviating from the document's main thesis
2. **Information density**: Each page should have substantive, in-depth content, prioritizing analytical conclusions, core insights, and key data over simple excerpts
3. **Page transitions**: Content between pages should be interconnected with natural, smooth transitions
4. **Page types**: Set a type for each page (cover/table_of_contents/chapter/content/final)

#### Page Count Control

1. **User did not specify page count**: Design based on document content volume and information density, recommended 12-18 pages; be sure to include cover, table of contents, chapters, content, and ending pages
2. **User specified a page count**: Design according to the user's requirement; encouraged to include cover, table of contents, chapters, content, and ending pages. If the page count is small (e.g., 5 or fewer), focus on content pages to increase information density

#### Outline Format

```markdown
# Presentation Outline

## Page 1 [cover]
- **Title**: Title of the presentation
- **Content**: Subtitle of the presentation, may be empty

## Page 2 [table_of_contents]
- **Title**: Table of contents heading. e.g., Table of Contents, Executive Overview, etc.
- **Content**: Chapter plan of the presentation. e.g., 1. Chapter One Title; 2. Chapter Two Title, ...

## Page 3 [chapter]
- **Title**: Chapter number and name. e.g., Chapter 1: xxx, 01: xxx
- **Content**: Chapter subtitle or other content to be presented on the page. Ensure the chapter title accurately summarizes all content within that chapter without being overly narrow!

## Page 4 [content]
- **Title**: Title of the page
- **Content**: Reference the original text's "chapter name/paragraph location" (e.g., Chapter 3 "Market Analysis", Section 2.1 "Experimental Methods"), and distill core information points from that section, summarizing in one or two sentences the key message this page should convey. If search supplementation was performed, mark supplemented content with "[supplemented]" in the outline
- **Source**: Search information source for supplemented content on this page (annotated with URL), e.g., https://example.com/report-2025

......

## Page x [final]
- **Title**: Title of the ending page
- **Content**: Core viewpoints/insights/inspirations, or thought-provoking questions, or thank-you messages, etc. Determine based on the user's scenario
```

#### Chapter Consistency

If the outline includes chapter transition pages (type=chapter), the transition pages across different chapters must be set uniformly -- either every chapter has one or none do. It is strictly forbidden to have transition pages for only some chapters.

## Writing Guidance for PPTD Generation

1. **Faithful to the original**: Distill rather than rewrite. Do not add viewpoints or data that do not exist in the original text. Page content must have corresponding basis in the source document
2. **Make good use of hyperlinks: When the PPT involves reference materials, further reading, or other external resources, use `<a href="url">` to add hyperlinks to related text, making it convenient for the audience to explore further**
3. **Per-page focus**: Each page should develop around the key points annotated in the outline, supported by key data and case studies from the original text. It is acceptable to condense verbose original text into concise expressions suitable for presentations, but core information must not be lost

## NEXT STEP
1. If visual design has not been completed, complete visual design and generate `design.md` first
2. When both `design.md` and `outline.md` are complete, proceed to generate_slides.md step6 to generate the presentation

================================================================================
PART 5: business_insight.md — 商业洞察场景基线
================================================================================

# Business Insight

> Applicable scenarios: Equity research reports, industry research, market surveys, competitive analysis, strategic consulting, etc.
> Style anchor: Presentation style of top consulting firms such as McKinsey/BCG/Bain + equity research reports (CICC/Huatai/Minsheng, etc.)

## Design Philosophy
- **Conclusion first (Pyramid Principle)**: Titles are complete insight conclusion sentences (Action Titles); reading the title reveals the conclusion
- **Ultimate restraint**: Zero decoration — no rounded corners, shadows, gradients, or colored cards. All visual elements must carry information
- **Typography as hierarchy**: Establish visual hierarchy solely through font size, font weight, and serif/sans-serif contrast, rather than relying on color or decoration
- **High density (top priority)**: Extremely high content density with densely packed page text, maintaining readability through margins and line spacing. **Pages must not be empty — this is the most important principle**
- **Verifiability**: All data and conclusions must cite information sources, ensuring every key argument is traceable and verifiable

## Information Density: Extremely High (90%+)
- Each page carries a large volume of information, with content area fill rate of at least **90%** or above; large blank areas are strictly prohibited
- Each page body should contain at least **3-5 key data points** (bolded numbers/highlighted), giving readers sufficient information
- Combine charts+text, tables+bullet points, and other formats to present multi-layered information on a single page
- Data tables should have at least **4 rows or more** (including headers), fully utilizing the table's information-carrying capacity
- Professional charts densely arranged; a single page can accommodate 2-3 related charts with concise text interpretation
- Avoid: a single large chart filling the entire page, bullet point pages with only 2-3 items, large blank areas

## Text-to-Visual Ratio: Balanced, Leaning Toward Text
- Text is the core information carrier; charts serve as data visualization and evidence support
- Recommended for content pages: approximately 60% text + 30% charts + 10% for data annotations and source notes
- Charts must be accompanied by text interpretation or key data extraction; charts must not stand in isolation
- Data annotations must be complete: axis labels, units, data labels, and legends for charts are all essential
- Source annotations are recommended to use `<a href="url">` hyperlinks pointing to the original report or data page, enhancing credibility and traceability

## Color Guidance
- **Extremely restrained color strategy**: The overall color scheme should maintain a high degree of rationality and restraint, building visual order with a small number of core colors supplemented by neutral color hierarchy, without using high-saturation or visually impactful color combinations.
- **Multiple tones are allowed, but colors must remain convergent within a single page or chart**. Each page should revolve around a clear primary color system, with other colors serving only as auxiliary hierarchy or contrast elements.
- **Single primary color system**: Content pages should establish a visual tone around a stable primary color, mainly used for key chart elements, important data, or a small number of structural elements; the rest of the content builds information hierarchy with neutral colors of varying brightness.
- **Brand consistency first**: If the content involves a specific company or institution, priority should be given to referencing that brand's visual system, extracting core tones as the primary color source to enhance professional consistency.
- Chart color principles:
  - Core data series in charts should use the primary color or variations within the same color family to express hierarchy.
  - Other data series should use neutral or low-presence auxiliary colors to avoid interfering with the understanding of core data.
  - Different data series should maintain clear contrast, but the total number of colors should be kept to the minimum necessary.
- **Key information expression**: Emphasis on key numbers or conclusions should primarily be achieved through font weight, font size, or position, rather than relying on striking color contrast.
- **Background and structural elements**: Page backgrounds should remain clean and unified; structural elements (such as divider lines, table borders, etc.) should use low-presence neutral colors to maintain an information-oriented visual environment.
- **Strictly limit decorative coloring**: Avoid using high-saturation or emotionally expressive colors as information emphasis tools, as they may interfere with rational reading and data interpretation.
- Maintain visual purity: The overall color scheme should serve information expression, not serve a decorative function, ensuring the page's visual center of gravity always falls on the content itself.

## Font Guidance
- **Titles (Action Title, cover, chapter)**: Serif Bold, conveying professional authority
- **Body text, data, footer**: Sans-serif (e.g., Arial)
- **Chinese**: Microsoft YaHei, paired with Arial
- Font size hierarchy contrast should be strong: Cover title 44-56px → Action Title 26-32px → Body text 18-22px (use 22px when page text content is light, 20px for moderate, 18px for heavy; must not go below 18px) → Footnotes/sources 12-16px

## Content Page Structure
- **Content pages typically consist of the following elements**:
  - Action Title (conclusion headline)
  - Main content area (charts/tables/bullet points)
  - Data source
  - Page number
- **Optional structures**:
  - Single-column analysis structure (vertical narrative)
  - Left-chart, right-interpretation structure
  - Top-chart, bottom-insight structure
  - Dual-chart comparison structure
  - Data table + conclusion structure
- The Action Title is the most defining visual feature; divider lines and content areas adapt below the title
- **The content area uses free layout (charts, tables, text, etc.) and should be filled as much as possible**
- Footer area reserved for data source notes, with consistent formatting and reduced font size, ensuring information traceability

## Narrative Style: Insight-Driven
- Each page leads with a core insight/conclusion as the Action Title, supported by data and cases
- Avoid pure fact enumeration; emphasize the "so what" — the meaning behind the data and business implications
- Content layers: Conclusion → Data/Evidence → Interpretation/Implications
- Equity research style: Clear viewpoints, rigorous logic, professional but accessible wording, appropriate use of industry terminology

## Content Expression Techniques
- **Dense professional charts**: Bar charts, line charts, pie charts, area charts, combo charts, and other data visualizations; encourage comparative charts, trend charts, YoY/QoQ analysis charts. Common chart types not defined in pptd.md (such as waterfall charts) can be built using shape + text box combinations
- **Structured expression**: Ordered/unordered lists paired with topic sentences; each bullet group should have at least 2-3 items, each containing specific data; bullets must not be overly brief
- **Big number highlights**: Key metrics displayed as large numbers + units + brief explanations (e.g., revenue, growth rate, market share, and other core metrics)
- **Tables**: Suitable for multi-dimensional comparisons (competitor comparison, financial metric comparison, plan comparison, etc.); headers with dark background + white text, data rows alternating white/light gray
- **Emphasis marking**: Bold key data and core conclusions (no colored text)
- **Data source annotations**: Charts and key data must include source notes, formatted as `Source: Institution Name, Year;` etc., 10-12px gray, ensuring verifiability. Source text should use `<a href="url">` hyperlinks pointing to the original report or data page
- **Footnote citations**: Important assertions should use footnote numbering referencing specific reports or databases; footnote content should also use `<a href="url">` hyperlinks pointing to original sources, enhancing professional credibility
- **Within the same document, different pages should avoid using completely identical layouts; layout structure should vary based on content to maintain reading rhythm**.

## Image Usage Rules
**Allowed (informational images)** — The image itself carries information; the reader gains understanding through the image that cannot be conveyed by text alone:

| Image Type | Examples | Applicable Pages |
|---------|------|---------|
| Product photos | Flagship vehicle exterior, chip wafer, flagship smartphone | Content pages (when discussing the product), cover, chapter pages |
| Technical process images | Lithography equipment, production lines, EUV process diagrams | Content pages (beside technical comparison paragraphs) |
| Brand/person images | Corporate logo wall, CEO photos, launch event scenes | Content pages (beside competitive landscape paragraphs), cover |
| Scene/atmosphere images | NEV driving scenes, consumer usage scenarios | Cover, chapter pages |
| Maps/regional images | Production capacity distribution maps, market region heat maps | Content pages (for geographic distribution analysis) |

**Prohibited (decorative images)** — Images used only for aesthetics; removing them does not affect information completeness:
- Abstract background textures, geometric patterns
- People/scene stock photos unrelated to content
- Vague "tech feel" light effects/particle backgrounds
- Data charts (use chart elements instead)
- Process diagrams (use shape+text combinations instead)

## Decoration Prohibitions
| Prohibited | Alternative |
|--------|---------|
| Shadows | No shadows whatsoever |
| Gradient fills | Solid color fills |
| Decorative icons | Avoid unless necessary; let text and data speak |
| Data citations without sources | Source information must be annotated |

================================================================================
PART 6: pptd.md — PPTD格式技术规范
================================================================================

# Global Conventions
## Coordinate System and Units
* All geometry and dimension units are in px (pixels), 1px=1pt, page origin is at the top-left corner (0, 0)
* `bounds`: [x, y, w, h] array (px)
* `rotation`: Clockwise rotation angle (degrees) around the center of the element's bounds
* Z-Order: Determined by the order of the Page.elements array

## Font Family (fontFamily)
* Supports specifying a single font (e.g., `"MiSans"`) or using "Latin, CJK" format for dual fonts (e.g., `"Arial, Microsoft YaHei"`)
* Applies to all `fontFamily` / `font-family` fields

# Multi-File Structure
PPTD uses a multi-file structure. A presentation project consists of a main entry file and independent page files:
```
project/
  slides_name.pptd     # Main entry file (size/theme/title + page reference list)
  pages/                 # Page file directory
    cover.page           # One .page file per page
    intro.page
    chart_slide.page
```
## Path Rules
- Paths in the `pages` list of the main entry `.pptd` file are relative to the directory containing the main entry file
- Image `src` (including Image element `src`, `background.src`, shape `fill.src`, `mask.src`) only supports absolute paths or URLs:
  - **Absolute path**: e.g. `/abs/path/to/img.png` (relative paths are not supported)
  - **http(s) URL**: e.g. `https://example.com/img.jpg`
## Cannot Directly Operate .page Files
- `.page` files cannot be passed individually to the convert or check commands; they must go through the main entry `.pptd` file

# Top-Level Structure
## Main Entry File (.pptd)
```typescript
interface Presentation {
  title?: string;  // Presentation title
  theme: Theme;
  size: [number, number];  // [width, height], recommended [1280, 720] for 16:9, [960, 720] for 4:3
  pages: string[];  // Page file path list (e.g., pages/cover.page, pages/intro.page)
}
```
**Example:**
```yaml
title: My Presentation
size: [1280, 720]
theme:
  colors:
    primary: "#1A73E8"
  textStyles:
    title: { fontSize: 32 }
pages:
  - pages/cover.page
  - pages/intro.page
  - pages/chart_slide.page
```
## Page File (.page)
```typescript
type PageType = "cover" | "table_of_contents" | "chapter" | "content" | "final";

interface PageFile {
  pageType: PageType;

  background?: Fill;
  notes?: string;  // Speaker notes, recommended to leave empty unless explicitly requested by the user

  elements: Element[]; // Element list; elements later in the array appear on higher layers
}
```
**Example (cover.page):**
```yaml
pageType: cover
background:
  type: solid
  color: "#FFFFFF"
notes: Speaker notes
elements:
  - elementId: title1
    elementType: text
    bounds: [100, 200, 760, 80]
    content:
      text: Hello World
```

## ElementBase (Element Base Class)

```typescript
type ElementType = "text" | "shape" | "image" | "icon" | "table" | "chart";

interface ElementBase {
  elementId: string;
  elementType: ElementType;

  bounds: [number, number, number, number];  // [x, y, w, h] (px)

  rotation?: number;  // degrees, default 0
  opacity?: number;   // 0-1, default 1
  flip?: [boolean, boolean];  // [horizontal flip, vertical flip], default no flip
}

type Element = Text | Shape | Image | Icon | Table | Chart;
```

# Theme System

The theme is used to centrally manage the colors and text styles of a PPT, supporting references in any color or rich text field.

## Type Definitions

```typescript
interface Theme {
  colors: Record<string, string>;
  textStyles: Record<string, TextStyleConfig>;
  tableStyles?: Record<string, TableStyleConfig>;
}

interface TextStyleConfig {
  color?: string;           // Text color
  fontSize?: number;        // Font size (px)
  fontFamily?: string;      // Font family
  fontStyle?: 'normal' | 'italic';
  backgroundColor?: string; // Background color
  lineHeight?: number;      // Line height (multiplier)
  lineHeightPx?: number;    // Fixed line height (px), mutually exclusive with lineHeight
  letterSpacing?: number;   // Letter spacing (px)
  marginTop?: number;        // Paragraph top margin (px)
}

interface TableStyleConfig {
  fontSize?: number;         // Uniform font size (px), can be overridden by cell rich text
  fontFamily?: string;       // Uniform font family
  fill?: Fill;               // Default cell background (applies when not overridden by headerFill/bodyFill)
  headerFill?: string;       // Header row background color (first row), supports theme references
  headerColor?: string;      // Header row text color
  headerBold?: boolean;      // Header row bold, default true
  headerBorder?: Border | [Border | null, Border | null] | [Border | null, Border | null, Border | null, Border | null];  // Header row border (overrides global border)
  bodyFill?: string[];       // Data row alternating background colors, applied cyclically
  bodyColor?: string;        // Data row text color
  bodyBorder?: Border | [Border | null, Border | null] | [Border | null, Border | null, Border | null, Border | null];  // Data row border (overrides global border, excludes first and last rows)
  lastRowBorder?: Border | [Border | null, Border | null] | [Border | null, Border | null, Border | null, Border | null];  // Last row border (overrides bodyBorder and global border)
  firstColumnFill?: string;  // First column background color
  firstColumnColor?: string; // First column text color
  firstColumnBold?: boolean; // First column bold
  border?: Border | [Border | null, Border | null] | [Border | null, Border | null, Border | null, Border | null];  // Default cell border
}
```

## Example (YAML)

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
```

## Reference Specification

In any field that accepts a color or text style, theme references (`$` prefix + key name) can be used:

```yaml
fill:
  type: solid
  color: "$primary"      # Color reference
border:
  color: "$accent"
content:
  style: "$title"        # Text style reference
  text: "<p>...</p>"
```

- The `color` and `backgroundColor` fields within TextStyle also support color references in `$primary` format.

- The theme style set by TextContent.style serves as the default style and can be overridden by rich text inline styles or other TextContent fields.



# Element Types

## Text (Text Box)

```typescript
interface Text extends ElementBase {
  elementType: "text";
  content: TextContent;
}

interface TextContent {
  text: string;  // Rich text string, see "Rich Text Rules" below

  style?: string;           // Reference to a theme.textStyles key, e.g., "$title"
  color?: string;           // Base text color, can be overridden via <span style="color:...">
  fontSize?: number;        // Base font size (px), can be overridden via <span style="font-size:...">
  fontFamily?: string;      // Base font family; can be overridden via <span style="font-family:...">

  lineHeight?: number;      // Line height multiplier, default 1
  lineHeightPx?: number;    // Fixed line height (px), mutually exclusive with lineHeight, takes higher priority
  letterSpacing?: number;   // Letter spacing (px), default 0
  marginTop?: number;        // Paragraph top margin (px)

  textDirection?: "horizontal" | "vertical";  // Default horizontal
  wrap?: boolean;  // Text auto-wrap, default true, recommended to explicitly set to false for single-line text

  align?: Alignment; // Alignment

  gradient?: GradientFill;  // Text gradient color (applied to the text itself, not the text box)
  shadow?: Shadow;          // Text shadow (applied to the text itself, not the text box)
}

type HorizontalAlign = "left" | "center" | "right" | "justify" | "distributed";
// justify: Justified alignment (last line not stretched)
// distributed: Distributed alignment (last line stretched)
type VerticalAlign = "top" | "middle" | "bottom";
type Alignment = [HorizontalAlign, VerticalAlign];  // e.g., ["center", "middle"]
```

Examples:

```yaml
# Basic usage: theme style + plain text
- elementId: title-1
  elementType: text
  bounds: [100, 50, 760, 80]
  content:
    style: "$title"
    align: [center, middle]
    text: Annual Work Summary

# Rich text + content-level property overrides
- elementId: body-1
  elementType: text
  bounds: [100, 200, 600, 200]
  content:
    fontSize: 20
    color: "$text"
    lineHeight: 1.6
    align: [left, top]
    text: |
      <p><strong>Key Achievements</strong>: Completed <span style="color:$primary;">3</span> major projects</p>
      <p style="text-align:right; line-height:1.2"><span style="font-size:14px; color:#6b7280;">-- FY2024</span></p>

# Text gradient + shadow (effects applied to the text itself)
- elementId: hero-text
  elementType: text
  bounds: [100, 100, 760, 120]
  content:
    align: [center, middle]
    text: |
      <p><span style="font-size:64px;">FUTURE</span></p>
    gradient:
      type: gradient
      gradientType: linear
      angle: 90
      stops:
        - {position: 0, color: "$primary"}
        - {position: 1, color: "$accent"}
    shadow:
      blur: 6
      color: "#00000040"
      offset: [0, 3]
```

### Rich Text Rules

> **YAML Writing Rules (Must Follow)**: The `content.text` field **must use block scalar (`|`)** and must not be wrapped with quotes. Reason: Rich text contains `style="..."` double-quote attributes; wrapping with `"..."` or `'...'` will cause YAML parsing errors.
>
> ```yaml
> # Correct
> text: |
>   <p><span style="color:$primary;">Text</span></p>
>
> # Wrong (double quotes inside style="" break YAML syntax)
> text: "<p><span style="color:$primary;">Text</span></p>"
> ```

#### Supported Tags

| Tag         | Description                | Example                                        |
| ---------- | ----------------- | ----------------------------------------- |
| `<p>`      | Paragraph, supports style attribute to override paragraph-level styles | `<p>This is a paragraph</p>`                           |
| `<span>`   | Inline style            | `<span style="color:#ff0000">Red text</span>` |
| `<strong>` | Bold                | `<strong>Important</strong>`                     |
| `<em>`     | Italic                | `<em>Emphasis</em>`                             |
| `<u>`      | Underline               | `<u>Underlined text</u>`                            |
| `<s>`      | Strikethrough               | `<s>Deleted</s>`                              |
| `<sup>`    | Superscript                | `100<sup>&copy;</sup>`                         |
| `<sub>`    | Subscript                | `H<sub>2</sub>O`                          |
| `<a>`      | Hyperlink, supports `https://`, `http://`, `mailto:` protocols. Hyperlinks automatically add blue underline style, overriding other format tags               | `<a href="https://example.com">Link</a>`    |
| `<ul>`     | Unordered list              | `<ul><li>Item 1</li></ul>`                   |
| `<ol>`     | Ordered list              | `<ol><li>First item</li></ol>`                   |
| `<li>`     | List item               | Used with `<ul>` or `<ol>`                     |

#### Style Properties

Both `<p>` and `<span>` tags support `style` attribute for inline styles. Paragraph-level styles on `<p>` override TextContent defaults; paragraphs without explicit settings inherit the corresponding TextContent properties.

| Property               | Applicable Tags          | Example Values                       | Description                                         |
| ---------------- | ------------- | -------------------------- | ------------------------------------------ |
| color            | `<span>`      | #ff0000, $primary          | Text color (supports theme references)                               |
| font-size        | `<span>`      | 24px                       | Font size (px)                                   |
| font-family      | `<span>`      | "Arial", "Arial, Microsoft YaHei" | Font family             |
| font-style       | `<span>`      | normal, italic             | Font style                                       |
| background-color | `<span>`      | #ffff00, $accent           | Text background color (supports theme references)                              |
| text-align       | `<p>`         | center, right              | Overrides the horizontal alignment of TextContent.align                  |
| line-height      | `<p>`         | 1.5, 24px                  | Overrides TextContent.lineHeight / lineHeightPx    |
| letter-spacing   | `<p>`         | 2px                        | Overrides TextContent.letterSpacing                |
| margin-top        | `<p>`        | 8px                        | Overrides TextContent.marginTop                    |

```yaml
content:
  align: [left, top]
  lineHeight: 1.2
  text: |
    <p><span style="font-size:32px; color:$primary;">Main Title</span><span style="font-size:18px; color:$secondary;">Subtitle</span></p>
    <p style="text-align:center; line-height:1.8">This paragraph is center-aligned with 1.8x line height</p>
    <p style="text-align:right">This paragraph is right-aligned, inheriting the default 1.2 line height</p>
```

#### Plain Text Shorthand

When `content.text` contains plain text directly, it is equivalent to wrapping it in a single `<p>`: `text: "Hello"` is equivalent to `text: "<p>Hello</p>"`

#### LaTeX Formulas

Rich text content supports embedding LaTeX formulas using `\(...\)` delimiters, either as standalone paragraphs or mixed with other text within `<p>` tags. Rich text tags are not allowed inside formulas; they inherit the `color`, `font-size`, and `font-family` of the surrounding context. Block-level formulas (standalone paragraphs) follow paragraph alignment.

```yaml
content:
  text: |
    <p>Pythagorean theorem: \(a^2 + b^2 = c^2\)</p>
    <p>\(\int_0^1 x^2 \mathrm{d}x = \frac{1}{3}\)</p>
```

#### Default Styles

| Property | Default Value |
|---|---|
| Font | "MiSans", Arial, sans-serif |
| Font size | 18px |
| Color | #000000 |
| Font weight | normal (400) |
| Line height | 1 |


## Shape

```typescript
interface Shape extends ElementBase {
  elementType: "shape";

  shapeName: string;      // See supported shape list below
  adjustments?: number[]; // Shape geometry parameters, see supported shape list below

  path?: string; // Custom geometry path, used only when shapeName="custom". Format: "viewBoxW,viewBoxH;SVG path data"

  arrow?: [ArrowType | null, ArrowType | null]; // Connector arrows [start, end], only valid when shapeName is a line-type shape

  fill?: Fill;
  border?: Border;
  shadow?: Shadow;
}

type ArrowType = "none" | "arrow" | "stealth" | "diamond" | "oval";
```

Examples:

```yaml
- elementId: shape-1
  elementType: shape
  bounds: [200, 200, 300, 150]
  shapeName: roundRect
  adjustments: [20000]
  fill:
    type: solid
    color: "$primary"
  border:
    style: solid
    width: 2
    color: "$accent"
- elementId: shape-2
  elementType: shape
  bounds: [100, 200, 500, 5]
  shapeName: custom
  path: "1000,100;M0 0 L1000 0 L1000 100 L0 100 Z"
  fill:
    type: solid
    color: "$accent1"
```

### Supported Shape List

adjustments parameter conventions:
* Described following the parameter order and count defined by OOXML
* Value range is generally [0, 100000] (100000 = 100%), conversion: `value / 1000 = percentage`
* The parameter array must be complete (intermediate values cannot be omitted), or entirely absent to use default values

#### Shape List

> The complete list of 177 shapes and their adjustments parameters can be found in ./shapes.md. The table below lists only the most commonly used shapes.

| shapeName | Description | adjustments Parameters | Default Values |
| --------- | --- | -------------- | ---- |
| rect | Rectangle | - | - |
| roundRect | Rounded rectangle | [corner radius] | [16667] |
| ellipse | Ellipse | - | - |
| triangle | Triangle | [apex horizontal position] | [50000] |
| diamond | Diamond | - | - |
| plus | Plus sign | [arm width ratio] | [25000] |
| homePlate | Pentagon arrow | [arrow tip offset] | [50000] |
| chevron | Chevron | [V tip offset] | [50000] |
| donut | Donut | [ring width ratio] | [25000] |
| star5 | 5-point star | [inner radius ratio, horizontal factor, vertical factor] | [19098, 105146, 110557] |
| rightArrow | Right arrow | [shaft width, head length] | [50000, 50000] |
| wedgeRectCallout | Rectangular callout | [tip X offset, tip Y offset] | [-20833, 62500] |
| bracePair | Brace pair | [curvature] | [8333] |
| custom | Custom geometry | - (uses `path` property to define geometry path) | - |

> **Angle parameter note**: Shapes such as `pie`, `arc`, `blockArc` use angle units of OOXML 1/60000 of a degree, conversion: `OOXML value = angle x 60000`.
> Flowchart shapes (`flowChartProcess`, `flowChartDecision`, `flowChartTerminator`, etc.) are detailed in ./shapes.md.

#### Line Shape List
The following `shapeName` values are line-type shapes that support endpoint arrows via the `arrow` field. Line coordinate rules:
1. bounds = [x, y, width, height] represents the bounding box of the line, **the line connects the diagonal corners of the bounding box**
2. **Horizontal line: height must be 0**; **Vertical line: width must be 0**
3. Default direction: from the top-left to the bottom-right of the bounds
4. `flip` changes the line direction, e.g., `[true, false]` makes the line go from top-right to bottom-left

Examples:
```yaml
# Horizontal line (height must be 0)
- elementId: hline
  elementType: shape
  bounds: [100, 250, 700, 0]
  shapeName: straightConnector1
  border: {style: solid, width: 2, color: "$primary"}

# Diagonal line with arrow (width and height are both non-zero)
- elementId: diagonal
  elementType: shape
  bounds: [100, 100, 300, 200]
  shapeName: straightConnector1
  arrow: [null, "arrow"]
  border: {style: solid, width: 2, color: "$accent"}
```

| shapeName          | Description           | adjustments           | Default Values             | Value Range         |
| ------------------ | ------------ | --------------------- | --------------- | ------------ |
| straightConnector1 | Straight line           | -                     | -               | -            |
| bentConnector2     | L-shaped connector (1 bend point)  | -                     | -               | -            |
| bentConnector3     | Z-shaped connector (2 bend points)  | X coordinate offset (midpoint position)        | [50000]        | [0, 100000] |
| bentConnector4     | Z-shaped connector (3 bend points)  | [X offset, Y offset] (midpoint position) | [50000, 50000] | [0, 100000] |
| curvedConnector2   | Simple arc         | -                     | -               | -            |
| curvedConnector3   | S-shaped curve (1 inflection point) | X coordinate offset (control point position)        | [50000]        | [0, 100000] |
| curvedConnector4   | Spiral curve (2 inflection points)  | [X offset, Y offset] (control point position) | [50000, 50000] | [0, 100000] |

## Image

```typescript
interface Image extends ElementBase {
  elementType: "image";

  src: string;  // Image URL or local path

  // Shape clipping (optional, default "rect")
  shapeName?: string;
  adjustments?: number[];

  // Fit and crop
  fit?: ImageFit;    // Default { mode: "cover" }
  crop?: ImageCrop;

  border?: Border;
  shadow?: Shadow;
}

interface ImageFit {
  mode: "fill" | "contain" | "cover";
  // fill: Stretch to fill the container, may distort
  // contain: Display the complete image, maintain aspect ratio, may leave whitespace
  // cover: Fill the container, maintain aspect ratio, may crop (default)
}

interface ImageCrop {
  left?: number;    // 0-1, crop ratio
  top?: number;     // 0-1
  right?: number;   // 0-1
  bottom?: number;  // 0-1
}
```

Example:

```yaml
- elementId: img-1
  elementType: image
  bounds: [50, 50, 400, 300]
  src: "https://example.com/image.jpg"
  shapeName: roundRect
  adjustments: [15000]
  fit:
    mode: cover
  shadow:
    blur: 10
    color: "#00000033"
    offset: [0, 4]
```

## Icon

```typescript
interface Icon extends ElementBase {
  elementType: "icon";

  iconName: string;  // Font Awesome icon name, see Icon Library section below

  fill?: Fill;  // Icon fill, supports complex fills
  border?: Border;
  shadow?: Shadow;
}
```

Example:

```yaml
- elementId: icon-1
  elementType: icon
  bounds: [100, 100, 48, 48]
  iconName: "fas:lightbulb"
  fill:
    type: solid
    color: "$primary"
```

### Icon Library

This specification uses Font Awesome 7.x. Documentation: https://fontawesome.com/search?ic=free-collection

iconName format: `style:name`

* `fas`: Solid (filled, default)
* `far`: Regular
* `fab`: Brands

Examples: `fas:house` (solid house), `far:heart` (outlined heart), `fab:github` (brand icon)

## Table

```typescript
interface Table extends ElementBase {
  elementType: "table";

  columnWidths: number[];  // Width percentage per column (0-1, sum to 1)
  rowHeights: number[];    // Height percentage per row (0-1, sum to 1)

  rows: Cell[][];

  style?: string | TableStyleConfig;  // "$default" references theme, or inline TableStyleConfig

  // Priority: Cell-level properties > style config > defaults

  shadow?: Shadow;
}

interface Cell {
  content?: TextContent;  // Cell text content; if content.align is not set, defaults to [center, middle]
  fill?: Fill;            // Cell background
  border?: Border | [Border | null, Border | null] | [Border | null, Border | null, Border | null, Border | null];  // Cell border, supports per-edge setting
  rowSpan?: number;       // Number of rows to merge downward, default 1
  colSpan?: number;       // Number of columns to merge rightward, default 1
}
```

border array format: single value = same for all sides; two values = [top-bottom, left-right]; four values = [top, right, bottom, left] (clockwise); `null` means no border on that side.

Default when border is not set: `{style: solid, width: 1, color: "#000000"}`

### Basic Example (Using Theme Table Style)

```yaml
- elementId: table-basic
  elementType: table
  bounds: [80, 120, 800, 280]
  columnWidths: [0.3, 0.35, 0.35]
  rowHeights: [0.33, 0.33, 0.34]
  style: "$default"
  rows:
    - - content: {text: "Metric"}
      - content: {text: "2023"}
      - content: {text: "2024"}
    - - content: {text: "Revenue (100M)"}
      - content: {text: "82.5"}
      - content: {text: "96.3"}
    - - content: {text: "Net Profit (100M)"}
      - content: {text: "12.1"}
      - content: {text: "15.8"}
```

### Merged Cells

Use `rowSpan`/`colSpan` to declare merge regions. Each row array lists only actual cells, automatically skipping occupied columns from left to right.

Example (3x3 table, top-left 2x2 merge):

```yaml
- elementId: table-1
  elementType: table
  bounds: [100, 100, 600, 400]
  columnWidths: [0.33, 0.33, 0.34]
  rowHeights: [0.33, 0.33, 0.34]
  rows:
    - - content:
          text: "Merged Cell"
        fill:
          type: solid
          color: "$accent"
        rowSpan: 2
        colSpan: 2
      - content:
          text: "C1"
    - - content:
          text: "C2"
    - - content:
          text: "A3"
      - content:
          text: "B3"
      - content:
          text: "C3"
```

## Chart

```typescript
// Bar chart, line chart, area chart, scatter chart, pie chart (including donut), radar chart, combo chart, bubble chart
type ChartType = 'bar' | 'line' | 'area' | 'scatter' | 'pie' | 'radar'
               | 'combo' | 'bubble';

// -- Chart-level options (cannot be overridden per series) --
interface ChartOptions {
  direction?: 'vertical' | 'horizontal';  // bar only, default 'vertical'
  barWidth?: number;      // Bar width ratio 0~1 (larger = wider bars), default auto
  innerRadius?: number;   // Pie chart inner radius ratio 0~1, creates donut chart when set
  startAngle?: number;    // Pie chart start angle (degrees), default 0
  stacked?: true | '100%'; // Stacking mode (applicable to bar/line/area)
  nullHandling?: 'zero' | 'gap' | 'connect';  // Null value handling, default 'gap'
  fontFamily?: string;    // Chart global font, all text components inherit this setting
}

// -- Chart title --
// Supports string shorthand: title: "text"
interface ChartTitleConfig {
  text: string;
  color?: string;
  fontSize?: number;
}

// -- Data labels --

interface DataLabelConfig {
  show?: boolean;           // Default false, i.e., when dataLabels is not configured, all chart types default to not showing data labels
  content?: 'value' | 'percentage' | 'category' | 'name';  // Default 'value'
  color?: string;
  numberFormat?: string;    // e.g., '0.0%', '#,##0'
  fontSize?: number;
}
// The fontSize of each component can override the auto-calculated value; when not set, it is auto-calculated based on chart size. fontFamily is uniformly inherited from ChartOptions.fontFamily.

// -- Legend --
// Supports bool shorthand: legend: false / legend: true
interface LegendConfig {
  show?: boolean;
  position?: 'top' | 'bottom' | 'left' | 'right';  // Default 'bottom'
  color?: string;
  fontSize?: number;
}

// -- Series style --
type MarkerShape = 'circle' | 'square' | 'diamond' | 'triangle';

interface MarkerConfig {
  shape?: MarkerShape;    // Default 'circle'
  fill?: SolidFill | GradientFill;   // Inherits SeriesStyleConfig.fill when not set
  border?: Border;                    // Inherits SeriesStyleConfig.border when not set
  size?: number;          // Marker size (px); auto-calculated based on chart size when not set (scatter charts default to larger)
}

interface SeriesStyleConfig {
  name?: string;          // Series display name (overrides the corresponding value in names)
  fill?: SolidFill | GradientFill;   // Series fill
  border?: Border;        // Series border
  smooth?: boolean;       // Smooth curve (line/area)
  line?: 'solid' | 'dash' | 'dot';   // Line style
  width?: number;         // Line width (px)
  marker?: false | MarkerConfig;      // false=hide marker, object=custom marker
  type?: 'bar' | 'line' | 'area';    // combo only, specifies series subtype
  axis?: 'primary' | 'secondary';    // Default 'primary', used for combo to bind to secondary axis
  dataLabels?: DataLabelConfig;       // Series-level data label override
}

// -- Axes --
interface AxisLabelConfig {
  color?: string;         // Tick label text color
  fontSize?: number;      // Tick label font size (px)
}

interface AxisLineConfig {
  style?: 'solid' | 'dash' | 'dot';  // Line style
  color?: string;         // Color
  width?: number;         // Line width (px)
  arrow?: boolean;        // Arrow (ignored in gridLine)
}

// -- Axis title --
interface AxisTitleConfig {
  text: string;
  color?: string;
  fontSize?: number;
}

interface AxisConfig {
  show?: boolean;                     // false=hide entire axis
  label?: boolean | AxisLabelConfig;  // false=hide tick labels
  axisLine?: boolean | AxisLineConfig; // false=hide axis line, object=custom style
  gridLine?: boolean | AxisLineConfig; // false=hide grid lines, object=custom style
  min?: number;           // Minimum value (numeric axis)
  max?: number;           // Maximum value (numeric axis)
  numberFormat?: string;  // Tick number format, e.g., '#,##0', '0.0%'
  title?: string | AxisTitleConfig;   // Axis title, string shorthand or object config
}

interface Chart extends ElementBase {
  elementType: 'chart';

  // -- Data --
  type: ChartType;
  data: Record<string, any>[];    // Array of objects, each record is a data point
  x: string;                      // Category field name (field values used as category labels)
  y: string | string[];           // Value field name(s) (multiple = one series each)
  names?: string[];               // Series display names (overrides y field names), corresponds 1:1 with y

  // -- Series colors (shorthand) --
  colors?: string[];              // Color for each series, applied cyclically in order

  // -- Chart-level options --
  options?: ChartOptions;

  // -- Series styles --
  // key: '*' for global default, y field name for per-series override
  seriesStyle?: Record<'*' | string, SeriesStyleConfig>;

  // -- Axis styles --
  // bar(vertical)/line/area: xAxis=category axis, yAxis=value axis
  // bar(horizontal):         xAxis=value axis, yAxis=category axis
  // scatter/bubble:          both axes are value axes
  // pie/radar:               no axes, this config is ignored
  xAxis?: AxisConfig;
  yAxis?: AxisConfig;

  title?: string | ChartTitleConfig;  // Chart title
  legend?: boolean | LegendConfig;    // false=hide, true=show, object=config
  dataLabels?: DataLabelConfig;       // Chart-level data labels
  size?: string;                      // bubble only, bubble size field name
  secondaryAxis?: AxisConfig;         // Secondary axis (used for right-side value axis in combo charts)

  // -- Container styles --
  fill?: Fill;
  border?: Border;
}
```

### Examples

Basic bar chart (vertical, default):

```yaml
- elementId: c1
  elementType: chart
  bounds: [50, 100, 600, 400]
  type: bar
  data:
    - {quarter: "Q1", revenue: 120, cost: 220}
    - {quarter: "Q2", revenue: 132, cost: 182}
    - {quarter: "Q3", revenue: 101, cost: 191}
    - {quarter: "Q4", revenue: 134, cost: 234}
  x: quarter
  y: [revenue, cost]
  names: ["Revenue", "Cost"]
  colors: ["#5470c6", "#91cc75"]
```

Line chart (per-series differentiation):

```yaml
- elementId: c2
  elementType: chart
  bounds: [50, 100, 600, 400]
  type: line
  data:
    - {month: "Jan", actual: 72, target: 65, baseline: 50}
    - {month: "Feb", actual: 85, target: 70, baseline: 50}
    - {month: "Mar", actual: null, target: 78, baseline: 50}
    - {month: "Apr", actual: 90, target: 82, baseline: 50}
  x: month
  y: [actual, target, baseline]
  names: ["Actual", "Target", "Baseline"]
  colors: ["#5470c6", "#ee6666", "#999999"]
  seriesStyle:
    "*":
      smooth: true
      width: 2
    actual: {line: solid, width: 3}
    target: {line: dash}
    baseline: {line: dot, width: 1, smooth: false, marker: false}
  yAxis:
    min: 0
    max: 100
    gridLine:
      color: "#f0f0f0"
  xAxis:
    label:
      color: "#666"
      fontSize: 10
```

Combo chart (bar + line + secondary axis):

```yaml
- elementId: c4
  elementType: chart
  bounds: [50, 100, 600, 400]
  type: combo
  title: "Revenue and Growth Rate"
  legend: {position: top}
  data:
    - {month: "Jan", revenue: 120, growthRate: 0.15}
    - {month: "Feb", revenue: 150, growthRate: 0.25}
  x: month
  y: [revenue, growthRate]
  names: ["Revenue", "Growth Rate"]
  colors: ["#5470c6", "#ee6666"]
  seriesStyle:
    revenue: {type: bar}
    growthRate: {type: line, axis: secondary, smooth: true, width: 2}
  yAxis: {title: "Amount (10K)", numberFormat: "#,##0"}
  secondaryAxis: {title: "Growth Rate", numberFormat: "0%", min: 0, max: 0.5}
```

Pie chart (donut):

```yaml
- elementId: c6
  elementType: chart
  bounds: [50, 100, 400, 400]
  type: pie
  title: "Revenue Composition"
  legend: {position: right}
  data:
    - {category: "Product", value: 55}
    - {category: "Service", value: 30}
    - {category: "Licensing", value: 15}
  x: category
  y: [value]
  colors: ["#5470c6", "#91cc75", "#fac858"]
  options:
    innerRadius: 0.5
    startAngle: 90
  dataLabels:
    show: true
    content: percentage
    numberFormat: "0%"
```
**Note: If you want to customize colors, please set the color values for all elements added to the chart, including series/markers/lines, etc. Avoid inconsistent chart color schemes!**

# Style Structures (Fill / Border / Shadow)

## Fill

```typescript
// Solid fill
interface SolidFill {
  type: "solid";
  color: string;  // hex8 color e.g., #ffffff99, or theme reference e.g., "$primary"
}

// Gradient fill
interface GradientFill {
  type: "gradient";
  gradientType: "linear" | "radial";
  stops: ColorStop[];
  angle?: number;  // degrees, linear only, default 0 (left→right). 90=top→bottom, 180=right→left, 270=bottom→top
}

// Image fill
interface ImageFill {
  type: "image";
  src: string;  // Image URL

  fit?: ImageFit;
  crop?: ImageCrop;  // Only effective when fit.mode is not "fill"

  mask?: SolidFill | GradientFill;  // Mask color overlay
  opacity?: number; // Opacity, 0-1
}

type Fill = SolidFill | GradientFill | ImageFill;
```

## Border

```typescript
interface Border {
  style: "solid" | "dash" | "dot" | "none";
  width?: number;   // px, default 1
  color: string;    // Supports theme references, supports hex8 for transparency (e.g., "#0a0a0d80")
}
```

## Shadow

```typescript
interface Shadow {
  blur: number;              // Blur radius (px)
  color: string;             // Shadow color, recommended to use colors with alpha
  offset?: [number, number]; // [x, y] offset (px), default [0, 0]
}
```

## ColorStop (Gradient Color Stop)

```typescript
interface ColorStop {
  position: number;  // 0-1
  color: string;     // Supports theme references, e.g., "$primary"
}
```

Example:

```yaml
# Image fill (for Shape/Page background)
fill:
  type: image
  src: "https://example.com/bg.jpg"
  fit: {mode: cover}
  mask:
    type: solid
    color: "#00000080"
  opacity: 0.9
```

# Validation Constraints

## Value Ranges

| Field                 | Constraint            |
| ------------------ | ------------- |
| opacity            | 0 <= value <= 1 |
| ColorStop.position | 0 <= value <= 1 |
| ImageCrop.\*       | 0 <= value <= 1 |
| columnWidths       | Array elements sum = 1     |
| rowHeights         | Array elements sum = 1     |

## Theme Reference Constraints

All theme reference formats are `$<key>`. Circular references are prohibited, and the key must exist in the corresponding table:

| Reference Type | Key Location |
|---|---|
| Color reference | theme.colors |
| Text style reference | theme.textStyles |
| Table style reference | theme.tableStyles |

================================================================================
END OF COMBINED DOCUMENT
================================================================================