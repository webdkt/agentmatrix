# AgentMatrix Desktop UI Design Guide

**Version:** 1.0.0
**Last Updated:** 2025-03-17
**Status:** Phase 0 - Foundation

---

## Design Philosophy

### Core Principles

1. **Clarity Over Complexity**
   - Every element serves a purpose
   - Remove rather than add
   - Let content breathe

2. **Refined Business Aesthetic**
   - Professional without being sterile
   - Warmth through subtle details
   - Confidence through restraint

3. **Visual Hierarchy**
   - Clear information architecture
   - Purposeful contrast
   - Guided eye movement

4. **Responsive & Adaptive**
   - Fluid layouts
   - Graceful degradation
   - Performance-first animations

### Design Influences

**Structural Inspiration:**
- Microsoft Outlook for Mac (layout efficiency)
- Apple Mail (refinement and polish)
- Notion (clarity and purpose)

**Visual Language:**
- Apple's Human Interface Guidelines
- Swiss/International Typographic Style
- Modern minimalist Japanese design

### What We Avoid

❌ **Cliché Design Patterns:**
- Generic Material Design shadows (elevation 1-8)
- Standard 8px/12px/16px border radius
- Heavy gradient overlays
- Over-used rounded cards
- Generic blue primary colors

✅ **Our Approach:**
- Subtle, purposeful shadows
- Intentional radius scale (6px, 10px, 14px)
- Color as accent, not decoration
- Sharp edges with purposeful rounding
- Sophisticated color palette

---

## Color System

### Primary Colors

Our primary palette is sophisticated and gender-neutral.

```
--primary-50:  #EEF2FF
--primary-100: #E0E7FF
--primary-200: #C7D2FE
--primary-300: #A5B4FC
--primary-400: #818CF8
--primary-500: #6366F1  ← Primary Brand Color
--primary-600: #4F46E5
--primary-700: #4338CA
--primary-800: #3730A3
--primary-900: #312E81
```

**Usage:**
- Primary actions, CTAs
- Active states
- Important indicators
- Links (when needed)

### Neutral Colors

A warm neutral palette that's easier on the eyes than pure grayscale.

```
--neutral-50:  #FAFAF9
--neutral-100: #F5F5F4
--neutral-200: #E7E5E4
--neutral-300: #D6D3D1
--neutral-400: #A8A29E
--neutral-500: #78716C
--neutral-600: #57534E
--neutral-700: #44403C
--neutral-800: #292524
--neutral-900: #1C1917
```

**Semantic Mappings:**
- Backgrounds: 50, 100, 200
- Borders: 200, 300
- Text: 500, 600, 700, 800
- UI elements: 300, 400

### Semantic Colors

Purposeful colors for specific UI states.

```
--success-50:  #ECFDF5
--success-500: #10B981
--success-700: #047857

--warning-50:  #FFFBEB
--warning-500: #F59E0B
--warning-700: #B45309

--error-50:   #FEF2F2
--error-500:  #EF4444
--error-700:  #B91C1C

--info-50:    #EFF6FF
--info-500:   #3B82F6
--info-700:   #1D4ED8
```

### Dark Mode

Dark mode uses slightly desaturated colors for reduced eye strain.

```
--bg-primary:   #0A0A0A
--bg-secondary: #141414
--bg-tertiary:  #1C1C1E
--bg-elevated:  #2C2C2E

--text-primary:   #FFFFFF
--text-secondary: #EBEBF5
--text-tertiary:  #EBEBF599
--text-quaternary: #EBEBF54D
```

---

## Typography

### Type Scale

```
--font-xs:    0.75rem   (12px)   line-height: 1.5
--font-sm:    0.875rem  (14px)   line-height: 1.5
--font-base:  1rem      (16px)   line-height: 1.5
--font-lg:    1.125rem  (18px)   line-height: 1.4
--font-xl:    1.25rem   (20px)   line-height: 1.4
--font-2xl:   1.5rem    (24px)   line-height: 1.3
--font-3xl:   1.875rem  (30px)   line-height: 1.2
```

### Font Families

```css
--font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text",
             "Segoe UI", "Helvetica Neue", Arial, sans-serif;

--font-display: -apple-system, BlinkMacSystemFont, "SF Pro Display",
                 "Segoe UI", "Helvetica Neue", Arial, sans-serif;

--font-mono: "SF Mono", "Menlo", "Monaco", "Cascadia Code",
             "Courier New", monospace;
```

### Font Weights

```
--font-normal:  400
--font-medium:  500
--font-semibold: 600
--font-bold:    700
```

### Typography Hierarchy

**Display:**
- Hero titles, large headers
- Size: 30px, Semibold
- Letter-spacing: -0.5px

**Heading 1:**
- Page titles
- Size: 24px, Semibold
- Letter-spacing: -0.3px

**Heading 2:**
- Section headers
- Size: 18px, Medium
- Letter-spacing: -0.2px

**Body:**
- Content, descriptions
- Size: 14px, Normal
- Line-height: 1.5

**Caption:**
- Metadata, timestamps
- Size: 12px, Normal
- Color: neutral-500

---

## Spacing System

### Spacing Scale

Consistent spacing based on a 4px base unit.

```
--spacing-0:   0
--spacing-1:   0.25rem  (4px)
--spacing-2:   0.5rem   (8px)
--spacing-3:   0.75rem  (12px)
--spacing-4:   1rem     (16px)
--spacing-5:   1.25rem  (20px)
--spacing-6:   1.5rem   (24px)
--spacing-8:   2rem     (32px)
--spacing-10:  2.5rem   (40px)
--spacing-12:  3rem     (48px)
--spacing-16:  4rem     (64px)
--spacing-20:  5rem     (80px)
```

### Common Patterns

```
--spacing-xs:   var(--spacing-1)   (4px)   - Tight spacing
--spacing-sm:   var(--spacing-2)   (8px)   - Compact spacing
--spacing-md:   var(--spacing-4)   (16px)  - Default spacing
--spacing-lg:   var(--spacing-6)   (24px)  - Comfortable spacing
--spacing-xl:   var(--spacing-8)   (32px)  - Loose spacing
--spacing-2xl:  var(--spacing-12)  (48px)  - Extra loose spacing
```

---

## Border Radius

Intentional radius scale - not the usual suspects.

```
--radius-sm:   6px    - Small elements, tags
--radius-md:   10px   - Buttons, inputs, cards
--radius-lg:   14px   - Large cards, modals
--radius-xl:   18px   - Hero cards, panels
--radius-full: 9999px - Pills, badges, avatar
```

---

## Shadows

Subtle, purposeful shadows. Elevation is implied, not stated.

```
--shadow-xs:  0 1px 2px rgba(0, 0, 0, 0.05)
--shadow-sm:  0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)
--shadow-md:  0 4px 6px rgba(0, 0, 0, 0.07), 0 2px 4px rgba(0, 0, 0, 0.06)
--shadow-lg:  0 10px 15px rgba(0, 0, 0, 0.08), 0 4px 6px rgba(0, 0, 0, 0.05)
--shadow-xl:  0 20px 25px rgba(0, 0, 0, 0.08), 0 10px 10px rgba(0, 0, 0, 0.04)
```

**Usage:**
- `shadow-xs`: Hover states, subtle depth
- `shadow-sm`: Cards, panels
- `shadow-md`: Dropdowns, popovers
- `shadow-lg`: Modals, large panels
- `shadow-xl`: Hero elements, calls-to-action

---

## Layout

### View Selector (Left Sidebar)

```
--view-selector-width: 72px
--view-selector-collapsed: 72px
```

- Vertical orientation
- Icon-only navigation
- 72px fixed width
- Active state: subtle highlight
- Hover state: subtle background change

### Session List

```
--session-list-width: 280px
--session-list-collapsed: 280px
```

- Compact items
- Left-aligned content
- 8px vertical spacing between items
- Active state: subtle background change
- New email button: full-width, prominent

### Email List

```
--email-list-min-width: 400px
--email-list-flex: 1
```

- Takes remaining space
- Compact cards, 12px spacing
- Left-aligned content
- Agent status in toolbar
- Reply: floating at bottom

### Global Layout

```
--app-padding: 0
--app-max-width: 100%
```

- No padding on app container
- Full-width content
- No centering constraints

---

## Components

### Buttons

**Primary Button:**
```
height: 40px
padding: 0 20px
background: primary-500
color: white
radius: 10px
font: 14px Medium
```

**Secondary Button:**
```
height: 40px
padding: 0 20px
background: neutral-100
color: neutral-700
radius: 10px
font: 14px Medium
border: 1px solid neutral-200
```

**Ghost Button:**
```
height: 40px
padding: 0 20px
background: transparent
color: neutral-600
radius: 10px
font: 14px Medium
```

### Inputs

**Text Input:**
```
height: 40px
padding: 0 16px
background: neutral-50
border: 1px solid neutral-200
radius: 10px
font: 14px Normal
placeholder: neutral-400

focus: border-primary-300
```

**Search Input:**
```
height: 36px
padding: 0 16px 0 40px
background: neutral-50
border: 1px solid neutral-200
radius: 10px
font: 14px Normal
icon-position: left, 12px
```

### Cards

**Default Card:**
```
padding: 16px
background: white
border: 1px solid neutral-200
radius: 10px
shadow: shadow-sm
```

**Email Card:**
```
padding: 12px 16px
background: white
border: 1px solid neutral-200
radius: 10px
hover: shadow-md
```

### Session Item

```
height: 56px
padding: 12px 16px
border-radius: 10px
gap: 12px

avatar: 32px
title: 14px Semibold
subtitle: 12px Normal
```

### Badge/Tag

```
height: 20px
padding: 0 8px
radius: 6px
font: 11px Medium
```

---

## Icons

### Icon Library

- **Primary:** Tabler Icons (ti-*)
- **Fallback:** Heroicons, Lucide

### Icon Sizes

```
--icon-xs:  16px
--icon-sm:  18px
--icon-md:  20px
--icon-lg:  24px
--icon-xl:  28px
```

### Icon Usage

- Use icons purposefully, not decoratively
- Maintain 2px stroke width
- Use circle/rounded variants for warmth
- Left-align icon + text combinations

---

## Animation

### Timing Functions

```
--ease-out: cubic-bezier(0, 0, 0.2, 1)
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)
--ease-spring: cubic-bezier(0.175, 0.885, 0.32, 1.275)
```

### Durations

```
--duration-fast:   150ms
--duration-base:   200ms
--duration-slow:   300ms
--duration-slower: 500ms
```

### Common Animations

**Fade In:**
```css
opacity: 0 → 1
duration: 200ms
easing: ease-out
```

**Slide In:**
```css
transform: translateY(-8px) → translateY(0)
opacity: 0 → 1
duration: 250ms
easing: ease-out
```

**Scale Press:**
```css
transform: scale(1) → scale(0.96)
duration: 100ms
easing: ease-out
```

---

## Interactive States

### Hover

- Subtle background change: neutral-50
- Subtle shadow: shadow-md
- Transform: none (unless button press)

### Active/Pressed

- Scale: 0.96
- Duration: 100ms
- Easing: ease-out

### Focus

- Outline: 2px solid primary-500
- Outline-offset: 2px
- No double borders

### Disabled

- Opacity: 0.5
- Cursor: not-allowed
- No interaction

---

## View-Specific Guidelines

### Email View

**Session List:**
- 280px width, fixed
- New email: 40px height, full-width, prominent
- Search: 36px height, full-width
- Items: 56px height, 8px gap
- Left-aligned content

**Email List:**
- Flexible width
- Toolbar: 48px height
  - Agent status (left)
  - Actions (right, three-dot menu)
- Email cards: 12px gap
- Reply: floating, 40px from bottom

**Reply Controls:**
- Bottom reply: floating, 56px from bottom
- Inline reply: appears below email
- Agent question: replaces bottom reply, prominent

### Settings View

**Structure:**
- Sidebar: 240px width (navigation)
- Content: flexible width
- Section spacing: 32px
- Group spacing: 24px

**Form Elements:**
- Label: 12px Medium, neutral-700
- Input: 40px height
- Helper text: 12px Normal, neutral-500
- Error text: 12px Normal, error-500

---

## Accessibility

### Color Contrast

- WCAG AA: 4.5:1 for normal text
- WCAG AA: 3:1 for large text
- WCAG AAA: 7:1 for normal text (recommended)

### Focus Indicators

- Always visible
- 2px minimum
- High contrast
- Never removed

### Keyboard Navigation

- Tab order: logical
- Skip links: available
- Focus traps: modals
- Escape key: close/dismiss

### Screen Readers

- Semantic HTML
- ARIA labels: when needed
- Role: button/link on interactive elements
- Alt text: meaningful images

---

## Responsive Breakpoints

```
--breakpoint-sm:  640px
--breakpoint-md:  768px
--breakpoint-lg:  1024px
--breakpoint-xl:  1280px
--breakpoint-2xl: 1536px
```

**Note:** Desktop app primarily targets 1024px+

---

## Internationalization

### Text Direction

- LTR: English, Chinese (Simplified)
- Padding/mirroring: handled by CSS logical properties

### Font Support

- Chinese: "PingFang SC", "Microsoft YaHei"
- English: System fonts
- Fallback: Sans-serif

### Character Limits

- Buttons: ≤20 characters
- Headers: ≤40 characters
- Truncation: ellipsis (…)

---

## Dark Mode

### Toggle

- Settings panel: Language & Appearance
- System preference: respected
- Manual override: available

### Adaptations

- Slightly desaturated colors
- Increased contrast for text
- Reduced white backgrounds
- Softer shadows

---

## Design Tokens Reference

All design values are available as CSS custom properties. See:
- `agentmatrix-desktop/src/styles/tokens.css`

---

## Version History

**v1.0.0** (2025-03-17)
- Initial design system
- Color palette
- Typography scale
- Spacing system
- Component foundations
- Layout guidelines

---

## Next Steps

1. ✅ Design system definition
2. ⏳ CSS tokens implementation
3. ⏳ Component library creation
4. ⏳ Pattern documentation
5. ⏳ Accessibility audit
6. ⏳ Dark mode refinement

---

**Designer Notes:**
- This is a living document
- Update when design decisions change
- Maintain version history
- Keep examples up-to-date
- Share with team regularly
