# UI Design System - Quick Reference

**Version:** 1.0.0
**For:** AgentMatrix Desktop Developers

---

## 🚀 Quick Start

### Import Styles

In any Vue component, the design tokens are automatically available:

```vue
<style scoped>
.my-component {
  color: var(--primary-500);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
}
</style>
```

### Common Patterns

**Button (Primary):**
```css
height: var(--button-height-md);
padding: var(--button-padding-md);
background: var(--primary-500);
color: white;
border-radius: var(--radius-md);
font-weight: var(--font-medium);
```

**Card:**
```css
padding: var(--card-padding-md);
background: white;
border: 1px solid var(--neutral-200);
border-radius: var(--radius-md);
box-shadow: var(--shadow-sm);
```

**Input:**
```css
height: var(--input-height-md);
padding: var(--input-padding-md);
background: var(--neutral-50);
border: 1px solid var(--neutral-200);
border-radius: var(--radius-md);
```

---

## 🎨 Colors

### Primary (Brand)
- `--primary-500` - Main brand color (#6366F1)
- `--primary-600` - Hover state
- `--primary-50` - Light background

### Neutrals
- `--neutral-50` - Light backgrounds
- `--neutral-100` - Subtle backgrounds
- `--neutral-200` - Borders
- `--neutral-500` - Secondary text
- `--neutral-700` - Primary text
- `--neutral-900` - Headings

### Semantic
- `--success-500` - Success states
- `--warning-500` - Warning states
- `--error-500` - Error states
- `--info-500` - Info states

---

## 📏 Spacing

```css
--spacing-xs: 4px   /* Tight */
--spacing-sm: 8px   /* Compact */
--spacing-md: 16px  /* Default */
--spacing-lg: 24px  /* Comfortable */
--spacing-xl: 32px  /* Loose */
```

---

## 🔤 Typography

```css
--font-xs: 12px     /* Captions */
--font-sm: 14px     /* Body */
--font-base: 16px   /* Base */
--font-lg: 18px     /* Large */
--font-xl: 20px     /* H3 */
--font-2xl: 24px    /* H2 */
--font-3xl: 30px    /* H1 */
```

**Weights:**
- `--font-normal: 400`
- `--font-medium: 500`
- `--font-semibold: 600`

---

## 📐 Border Radius

```css
--radius-sm: 6px    /* Small elements */
--radius-md: 10px   /* Buttons, cards */
--radius-lg: 14px   /* Large cards */
--radius-xl: 18px   /* Hero elements */
```

---

## 🌗 Dark Mode

### Auto (System Preference)
The app automatically respects system dark mode preference.

### Manual Toggle
Add `.dark` class to any parent element (usually `<html>` or `<body>`):

```javascript
// Enable dark mode
document.documentElement.classList.add('dark')

// Disable dark mode
document.documentElement.classList.remove('dark')
```

---

## 🎬 Animations

### Duration
```css
--duration-fast: 150ms
--duration-base: 200ms
--duration-slow: 300ms
```

### Easing
```css
--ease-out: cubic-bezier(0, 0, 0.2, 1)
--ease-in-out: cubic-bezier(0.4, 0, 0.2, 1)
```

### Pre-built Animations
```css
.animate-fade-in   /* Fade in */
.animate-slide-in  /* Slide in from top */
.animate-spin      /* Rotate 360° */
```

---

## 📱 Layout

### Fixed Widths
```css
--view-selector-width: 72px
--session-list-width: 280px
--email-list-min-width: 400px
```

### App Container
```css
#app {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}
```

---

## 🎯 Component Sizes

### Buttons
```css
--button-height-sm: 36px
--button-height-md: 40px
--button-height-lg: 48px
```

### Inputs
```css
--input-height-sm: 36px
--input-height-md: 40px
--input-height-lg: 48px
```

---

## ♿ Accessibility

### Focus Styles
```css
:focus-visible {
  outline: 2px solid var(--primary-500);
  outline-offset: 2px;
}
```

### Color Contrast
All colors meet WCAG AA standards (4.5:1 for normal text).

---

## 🔧 Utility Classes

### Commonly Used

**Layout:**
- `.flex` - Display flex
- `.flex-col` - Column direction
- `.items-center` - Center items
- `.justify-between` - Space between
- `.gap-2` - 8px gap
- `.gap-4` - 16px gap

**Spacing:**
- `.p-4` - 16px padding
- `.px-4` - Horizontal padding
- `.py-2` - Vertical padding

**Typography:**
- `.text-sm` - 14px
- `.text-base` - 16px
- `.font-medium` - 500 weight

**Colors:**
- `.text-primary-500` - Primary color text
- `.bg-primary-50` - Light background
- `.border-neutral-200` - Neutral border

**Borders:**
- `.rounded` - 10px radius
- `.border` - 1px border

---

## 📁 File Structure

```
agentmatrix-desktop/src/
├── styles/
│   ├── tokens.css      # Design tokens (DO NOT EDIT directly)
│   └── global.css      # Global styles & utilities
├── components/
│   ├── view-selector/  # View selector (new)
│   ├── session/        # Session components
│   ├── email/          # Email components
│   └── settings/       # Settings components
└── App.vue             # Root component
```

---

## 🎨 Design Guidelines

### Do's ✅
- Use design tokens for all values
- Maintain consistent spacing
- Keep components compact
- Left-align content
- Use subtle shadows
- Animate with purpose

### Don'ts ❌
- Hard-code colors or sizes
- Use arbitrary spacing values
- Over-use gradients
- Add unnecessary decoration
- Center-align lists
- Use heavy shadows

---

## 🔄 Migration Guide

### Old → New

**Old:**
```css
padding: 8px;
background: #6366F1;
border-radius: 8px;
```

**New:**
```css
padding: var(--spacing-sm);
background: var(--primary-500);
border-radius: var(--radius-md);
```

---

## 📚 Resources

- **Full Design Guide:** `docs/desktop/ui-design-guide.md`
- **Design Tokens:** `src/styles/tokens.css`
- **Global Styles:** `src/styles/global.css`
- **Component Examples:** (coming soon)

---

## 💡 Tips

1. **Use browser dev tools** to inspect tokens
2. **Check contrast** with accessibility tools
3. **Test in both light and dark modes**
4. **Keep components simple and focused**
5. **Animate transitions sparingly**

---

## 🐛 Troubleshooting

**Styles not applying?**
- Check that `global.css` is imported in `main.js`
- Verify token names are spelled correctly
- Clear browser cache

**Dark mode not working?**
- Check for `.dark` class on `<html>`
- Verify dark mode token overrides
- Test with system preference

**Spacing looks off?**
- Use spacing tokens, not arbitrary values
- Check for conflicting margins/padding
- Verify box-sizing is border-box

---

**Last Updated:** 2025-03-17
**Maintained by:** Design System Team
