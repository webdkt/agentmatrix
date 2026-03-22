# AgentMatrix Desktop App Icon — Design Brief

## What is AgentMatrix?

AgentMatrix is a **dispatch office for distributed cognition**. Autonomous AI agents live inside it — they receive emails (tasks), think in self-correcting loops, assemble skills at runtime, execute work in isolated containers, then hibernate until the next dispatch. It's not a chat app. It's an **operating theater for artificial thought**.

## What is MERIDIAN?

MERIDIAN is the design language. Its soul: **warm, restrained, precise**. Think intelligence archive, not tech startup. Think copperplate engraving, not flat illustration.

## The Design Language at a Glance

- **Parchment backgrounds** (#FDFCF9 — warm ivory, not cold white)
- **India ink text** (#1A1A1A — deep, authoritative)
- **Vermillion accent** (#C23B22 — the color of editorial red marks, Chinese seals, wax stamps on dispatches)
- **Thin 1.5px strokes**, square caps, no fills — engraving aesthetic
- **Serif typography** (Source Serif 4 / Noto Serif SC) for content, sans-serif for operations
- **No gradients, no glassmorphism, no soft shadows** — everything is sharp, ruled, deliberate

## The Icon Should Feel Like...

A **seal** or **stamp mark** — something that could be pressed into wax. Not a 3D rendered logo. Not a gradient blob. Not a friendly mascot.

Think:
- A mark on an official document
- A maker's mark on a book spine
- A Chinese seal (印章) — geometric, authoritative, compact
- A typesetter's ornament
- A copper plate engraving reduced to its simplest form

## Concept Direction

### The Core Metaphor: Matrix × Dispatch

The "A" of AgentMatrix, crossed with the idea of a **dispatch** (a letter, a sealed message, a communication between autonomous entities).

### Suggested Concept: The Stamped A

**Form**: A geometric, monospaced capital "A" — but not a typeface A. A **constructed** A, built from precise strokes. Think of it as a technical drawing of the letter A, like the precision marks on a drafting template.

**Frame**: The "A" sits inside a **square with slightly rounded corners** (radius ~2px, matching the app's border-radius). Not a circle — the square echoes the app's card/panel structure.

**Key detail**: The crossbar of the "A" is replaced by a **thin horizontal line** that extends slightly beyond the letter's legs, touching the frame edges. This line represents:
- The dispatch — a line of communication
- The ruled lines that define MERIDIAN's visual hierarchy
- The crossbar that connects two autonomous systems

**Color**: The background is **vermillion** (#C23B22), the "A" and line are **parchment** (#FDFCF9). Like a red wax seal with the mark pressed in.

**Or alternatively**: Inverted — parchment background, vermillion A. More subtle, more archival.

### Why This Works

1. **Distinctive**: No other app uses a geometric "A" in a vermillion square. It's immediately recognizable.
2. **Scalable**: At 16px (taskbar), it reads as a colored square with a mark. At 512px (installer), the full construction is visible. At every size, it's clear.
3. **On-brand**: It feels like a stamp, a seal, an official mark — exactly MERIDIAN's character.
4. **No trends**: No gradients, no glass effects, no 3D. This will look the same in 10 years. Timeless, like a bookplate.

### Technical Specifications

- **Format**: SVG (primary), PNG @1x, @2x, @3x
- **Sizes**: 16, 32, 64, 128, 256, 512, 1024px
- **macOS**: Needs .icns with all sizes
- **Windows**: Needs .ico with 16, 32, 48, 256px
- **Linux**: SVG + PNG fallbacks
- **Background**: Must work on both light and dark desktop backgrounds

### Color Variants

| Variant | Background | Foreground | Use Case |
|---------|-----------|------------|----------|
| Primary | #C23B22 (Vermillion) | #FDFCF9 (Parchment) | App icon, primary branding |
| Inverted | #FDFCF9 (Parchment) | #C23B22 (Vermillion) | Light backgrounds, watermarks |
| Monochrome | #1A1A1A (India Ink) | #FDFCF9 (Parchment) | Dark mode taskbar, favicons |

### What NOT to Do

- No gradients (not even subtle ones)
- No drop shadows or inner shadows
- No 3D perspective or isometric rendering
- No friendly/rounded/soft shapes (this isn't a consumer chat app)
- No literal brain/robot/AI imagery (it's a cliché)
- No lettermark in a circle (too generic)
- No complex multi-element compositions (it must work at 16px)

### Reference Mood

- Bookplates and ex libris marks
- Chinese seal stamps (朱文印)
- Copperplate engraving vignettes
- The Aldine Press anchor mark
- Japanese hanko stamps
- Technical drafting symbols
- The Bauhaus geometric tradition

## Summary

A **geometric "A" in a rounded square, vermillion and parchment, like a seal pressed into a dispatch**. Sharp, authoritative, timeless. The kind of mark you'd find on an important document.
