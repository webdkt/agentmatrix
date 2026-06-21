"""Font-family resolution. 对应 core/fonts.ts。"""

from __future__ import annotations

GENERIC_FONT_MAP = {
    'serif': 'Georgia',
    'sans-serif': 'Arial',
    'monospace': 'Courier New',
    'system-ui': 'Arial',
    '-apple-system': 'Arial',
    'blinkmacsystemfont': 'Arial',
    'ui-serif': 'Georgia',
    'ui-sans-serif': 'Arial',
    'ui-monospace': 'Courier New',
    'ui-rounded': 'Arial',
    'cursive': 'Comic Sans MS',
    'fantasy': 'Impact',
    'math': 'Cambria Math',
    'emoji': 'Segoe UI Emoji',
}


def resolve_font_family(family, swap_map: dict = None) -> str:
    """Resolve a font-family value to a single face name.

    The capture step has usually already collapsed the stack to the rendered
    face; this maps any remaining swap/generic and strips quotes.
    """
    if not family:
        return 'Arial'
    first = family.split(',')[0].strip()
    first = first.strip('"').strip("'")
    if not first:
        return 'Arial'
    lc = first.lower()
    if swap_map:
        for k, v in swap_map.items():
            if k.lower() == lc:
                return v
    return GENERIC_FONT_MAP.get(lc, first)
