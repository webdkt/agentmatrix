#!/usr/bin/env python3
"""
PPTD Color — OOXML color parsing, scheme colors, clrMap resolution.
"""

from pptd_common import NSMAP

# ---------------------------------------------------------------------------
# OOXML scheme color map
# ---------------------------------------------------------------------------

# Default Office theme scheme colors (accent1-6, dk1-2, lt1-2, hlink, folHlink)
SCHEME_COLOR_MAP = {
    'dk1': '#000000',
    'dk2': '#44546A',
    'lt1': '#FFFFFF',
    'lt2': '#E7E6E6',
    'accent1': '#4472C4',
    'accent2': '#ED7D31',
    'accent3': '#A5A5A5',
    'accent4': '#FFC000',
    'accent5': '#5B9BD5',
    'accent6': '#70AD47',
    'hlink': '#0563C1',
    'folHlink': '#954F72',
}


# ---------------------------------------------------------------------------
# clrMap — semantic color slot resolution
# ---------------------------------------------------------------------------

def build_clr_map(master_clr_map_elem):
    """Parse <p:clrMap> element and return dict of semantic name → base scheme name.

    Returns e.g. {'bg1': 'lt1', 'bg2': 'lt2', 'tx1': 'dk1', 'tx2': 'dk2', ...}
    """
    DEFAULT_CLR_MAP = {
        'bg1': 'lt1', 'tx1': 'dk1', 'bg2': 'lt2', 'tx2': 'dk2',
        'accent1': 'accent1', 'accent2': 'accent2', 'accent3': 'accent3',
        'accent4': 'accent4', 'accent5': 'accent5', 'accent6': 'accent6',
        'hlink': 'hlink', 'folHlink': 'folHlink',
    }
    if master_clr_map_elem is None:
        return dict(DEFAULT_CLR_MAP)
    result = dict(DEFAULT_CLR_MAP)
    for attr, val in master_clr_map_elem.attrib.items():
        attr_name = attr.split('}')[-1] if '}' in attr else attr
        result[attr_name] = val
    return result


def apply_clr_map_overrides(base_clr_map, layout_clr_map_elem, slide_clr_map_elem):
    """Apply layout and slide clrMapOvr on top of the base clrMap.

    Priority order (highest to lowest):
    1. Slide overrideClrMapping
    2. Layout overrideClrMapping (applied even if slide has masterClrMapping)
    3. Master clrMap (base)

    Slide masterClrMapping means "use master as base" but does NOT block
    the layout's overrideClrMapping from applying.
    """
    result = dict(base_clr_map)

    # Apply layout override first (it's between master and slide in the chain)
    if layout_clr_map_elem is not None:
        override = layout_clr_map_elem.find('a:overrideClrMapping', NSMAP)
        if override is not None:
            for attr, val in override.attrib.items():
                attr_name = attr.split('}')[-1] if '}' in attr else attr
                result[attr_name] = val

    # Slide-level override takes highest priority
    if slide_clr_map_elem is not None:
        override = slide_clr_map_elem.find('a:overrideClrMapping', NSMAP)
        if override is not None:
            for attr, val in override.attrib.items():
                attr_name = attr.split('}')[-1] if '}' in attr else attr
                result[attr_name] = val
        # masterClrMapping: keep current result (layout override already applied)
        # No clrMapOvr: keep current result

    return result


def build_scheme_color_map_from_theme_xml(theme_xml_bytes, clr_map=None):
    """Parse theme1.xml and return a dict of scheme color name → hex string.

    If clr_map is provided, use it to resolve semantic color names (bg1, bg2, tx1, tx2)
    to their actual base scheme names. Otherwise use OOXML standard defaults.
    """
    import xml.etree.ElementTree as ET
    result = dict(SCHEME_COLOR_MAP)
    try:
        root = ET.fromstring(theme_xml_bytes)
        clr_scheme = root.find('.//a:clrScheme', NSMAP)
        if clr_scheme is None:
            return result
        for child in clr_scheme:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            srgb = child.find('.//a:srgbClr', NSMAP)
            if srgb is not None:
                val = srgb.get('val')
                if val:
                    result[tag] = f'#{val}'
            else:
                sys_clr = child.find('.//a:sysClr', NSMAP)
                if sys_clr is not None:
                    val = sys_clr.get('lastClr')
                    if val:
                        result[tag] = f'#{val}'

        # Build semantic color aliases using clrMap
        if clr_map is None:
            # Default OOXML mapping (ECMA-376 Part 1, §20.1.6.3)
            clr_map = {'bg1': 'lt1', 'bg2': 'lt2', 'tx1': 'dk1', 'tx2': 'dk2'}

        for semantic_name, base_name in clr_map.items():
            if semantic_name not in result and base_name in result:
                result[semantic_name] = result[base_name]
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Hex color helpers
# ---------------------------------------------------------------------------

def is_valid_hex_color(color):
    """Check if a string is a valid hex color (3, 4, 6, or 8 digits after #)."""
    if not isinstance(color, str):
        return False
    c = color.lstrip('#')
    if len(c) not in (3, 4, 6, 8):
        return False
    return all(ch in '0123456789ABCDEFabcdef' for ch in c)


def hex_to_rgb(hex_color):
    """Convert #RRGGBB or #RRGGBBAA to (r, g, b) tuple. Returns None on failure."""
    if not hex_color or not isinstance(hex_color, str):
        return None
    h = hex_color.lstrip('#')
    if len(h) >= 6:
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except ValueError:
            pass
    return None


def hex_to_rgba(hex_color):
    """Convert #RRGGBB or #RRGGBBAA to (r, g, b, a) tuple. a defaults to 255."""
    if not hex_color or not isinstance(hex_color, str):
        return None
    h = hex_color.lstrip('#')
    if len(h) >= 6:
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            a = int(h[6:8], 16) if len(h) >= 8 else 255
            return (r, g, b, a)
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# HSL conversion (for lumMod/lumOff/hueOff/hueMod/satMod/satOff)
# ---------------------------------------------------------------------------

def _rgb_to_hsl(r, g, b):
    """Convert 0-255 RGB to HSL (h=0-1, s=0-1, l=0-1)."""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    cmax, cmin = max(r, g, b), min(r, g, b)
    l = (cmax + cmin) / 2.0
    if cmax == cmin:
        return 0.0, 0.0, l
    d = cmax - cmin
    s = d / (2.0 - cmax - cmin) if l > 0.5 else d / (cmax + cmin)
    if cmax == r:
        h = ((g - b) / d + (6 if g < b else 0)) / 6.0
    elif cmax == g:
        h = ((b - r) / d + 2) / 6.0
    else:
        h = ((r - g) / d + 4) / 6.0
    return h, s, l


def _hsl_to_rgb(h, s, l):
    """Convert HSL (h=0-1, s=0-1, l=0-1) to 0-255 RGB."""
    if s == 0:
        v = round(l * 255)
        return v, v, v
    def hue_to_rgb(p, q, t):
        if t < 0: t += 1
        if t > 1: t -= 1
        if t < 1/6: return p + (q - p) * 6 * t
        if t < 1/2: return q
        if t < 2/3: return p + (q - p) * (2/3 - t) * 6
        return p
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = round(hue_to_rgb(p, q, h + 1/3) * 255)
    g = round(hue_to_rgb(p, q, h) * 255)
    b = round(hue_to_rgb(p, q, h - 1/3) * 255)
    return r, g, b


# ---------------------------------------------------------------------------
# OOXML color value parsing
# ---------------------------------------------------------------------------

def parse_ooxml_color(color_elem, scheme_map=None):
    """Extract a hex color string from an OOXML color element.

    Handles a:srgbClr, a:schemeClr, a:sysClr, and a:alpha transparency.
    Returns a hex string like '#RRGGBB' or '#RRGGBBAA', or None.
    """
    if color_elem is None:
        return None

    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP

    # Solid fill wrapper
    solid = color_elem.find('.//a:solidFill', NSMAP)
    if solid is not None:
        return _parse_color_value(solid, scheme_map)

    # Direct color child elements
    result = _parse_color_value(color_elem, scheme_map)
    if result:
        return result

    return None


def _parse_color_value(parent, scheme_map):
    """Parse srgbClr / schemeClr / sysClr under *parent* and return hex string.

    First checks for a:solidFill wrapper to avoid matching nested color elements
    (e.g., arrow end colors inside a:ln).
    """
    # Prefer a:solidFill child to scope the search
    solid = parent.find('a:solidFill', NSMAP)
    search_root = solid if solid is not None else parent

    srgb = search_root.find('a:srgbClr', NSMAP)
    if srgb is not None:
        val = srgb.get('val', '')
        if val:
            hex_str = val
            alpha_elem = srgb.find('a:alpha', NSMAP)
            if alpha_elem is not None:
                alpha_val = alpha_elem.get('val')
                if alpha_val:
                    # OOXML alpha: 0-100000 (percentage * 1000)
                    alpha_8bit = round(int(alpha_val) / 100000 * 255)
                    if alpha_8bit < 255:
                        hex_str += f'{alpha_8bit:02X}'
            return f'#{hex_str}'

    scheme = search_root.find('a:schemeClr', NSMAP)
    if scheme is not None:
        val = scheme.get('val', '')
        base = scheme_map.get(val, SCHEME_COLOR_MAP.get(val))
        if base:
            hex_str = base.lstrip('#')
            # Handle tint/shade modifications
            tint_elem = scheme.find('a:tint', NSMAP)
            shade_elem = scheme.find('a:shade', NSMAP)
            if tint_elem is not None:
                tint_val = int(tint_elem.get('val', 0)) / 100000
                r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                r = round(r + (255 - r) * tint_val)
                g = round(g + (255 - g) * tint_val)
                b = round(b + (255 - b) * tint_val)
                hex_str = f'{r:02X}{g:02X}{b:02X}'
            elif shade_elem is not None:
                shade_val = int(shade_elem.get('val', 0)) / 100000
                r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                r = round(r * shade_val)
                g = round(g * shade_val)
                b = round(b * shade_val)
                hex_str = f'{r:02X}{g:02X}{b:02X}'

            # Handle lumMod/lumOff (lightness adjustment in HSL space)
            lum_mod = scheme.find('a:lumMod', NSMAP)
            lum_off = scheme.find('a:lumOff', NSMAP)
            if lum_mod is not None or lum_off is not None:
                r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                h, s, l = _rgb_to_hsl(r, g, b)
                mod_val = int(lum_mod.get('val', 100000)) / 100000.0 if lum_mod is not None else 1.0
                off_val = int(lum_off.get('val', 0)) / 100000.0 if lum_off is not None else 0.0
                l = max(0.0, min(1.0, l * mod_val + off_val))
                r, g, b = _hsl_to_rgb(h, s, l)
                hex_str = f'{r:02X}{g:02X}{b:02X}'

            # Handle hueOff/hueMod (hue rotation)
            hue_off = scheme.find('a:hueOff', NSMAP)
            hue_mod = scheme.find('a:hueMod', NSMAP)
            if hue_off is not None or hue_mod is not None:
                r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                h, s, l = _rgb_to_hsl(r, g, b)
                if hue_off is not None:
                    # hueOff is in 60000ths of a degree, normalized to 0-1
                    h = (h + int(hue_off.get('val', 0)) / 216000000.0) % 1.0
                if hue_mod is not None:
                    h = (h * int(hue_mod.get('val', 100000)) / 100000.0) % 1.0
                r, g, b = _hsl_to_rgb(h, s, l)
                hex_str = f'{r:02X}{g:02X}{b:02X}'

            # Handle satMod/satOff (saturation adjustment)
            sat_mod = scheme.find('a:satMod', NSMAP)
            sat_off = scheme.find('a:satOff', NSMAP)
            if sat_mod is not None or sat_off is not None:
                r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
                h, s, l = _rgb_to_hsl(r, g, b)
                if sat_mod is not None:
                    s = s * int(sat_mod.get('val', 100000)) / 100000.0
                if sat_off is not None:
                    s = s + int(sat_off.get('val', 0)) / 100000.0
                s = max(0.0, min(1.0, s))
                r, g, b = _hsl_to_rgb(h, s, l)
                hex_str = f'{r:02X}{g:02X}{b:02X}'

            alpha_elem = scheme.find('a:alpha', NSMAP)
            if alpha_elem is not None:
                alpha_val = alpha_elem.get('val')
                if alpha_val:
                    alpha_8bit = round(int(alpha_val) / 100000 * 255)
                    if alpha_8bit < 255:
                        hex_str += f'{alpha_8bit:02X}'
            return f'#{hex_str}'

    sys_clr = search_root.find('a:sysClr', NSMAP)
    if sys_clr is not None:
        val = sys_clr.get('lastClr', '')
        if val:
            hex_str = val
            alpha_elem = sys_clr.find('a:alpha', NSMAP)
            if alpha_elem is not None:
                alpha_val = alpha_elem.get('val')
                if alpha_val:
                    alpha_8bit = round(int(alpha_val) / 100000 * 255)
                    if alpha_8bit < 255:
                        hex_str += f'{alpha_8bit:02X}'
            return f'#{hex_str}'

    return None


def parse_color_with_ref(parent, scheme_map=None):
    """Parse color element and return $schemeName for simple scheme colors,
    or #RRGGBB for complex/direct colors.

    This preserves theme references for round-trip fidelity.
    Returns None if no color found.
    """
    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP

    solid = parent.find('a:solidFill', NSMAP)
    search_root = solid if solid is not None else parent

    srgb = search_root.find('a:srgbClr', NSMAP)
    if srgb is not None:
        val = srgb.get('val', '')
        if val:
            hex_str = val
            alpha_elem = srgb.find('a:alpha', NSMAP)
            if alpha_elem is not None:
                alpha_val = alpha_elem.get('val')
                if alpha_val:
                    alpha_8bit = round(int(alpha_val) / 100000 * 255)
                    if alpha_8bit < 255:
                        hex_str += f'{alpha_8bit:02X}'
            return f'#{hex_str}'

    scheme = search_root.find('a:schemeClr', NSMAP)
    if scheme is not None:
        val = scheme.get('val', '')
        # Only preserve scheme ref if there are no modifications
        has_mods = (scheme.find('a:tint', NSMAP) is not None or
                    scheme.find('a:shade', NSMAP) is not None or
                    scheme.find('a:lumMod', NSMAP) is not None or
                    scheme.find('a:lumOff', NSMAP) is not None or
                    scheme.find('a:alpha', NSMAP) is not None or
                    scheme.find('a:hueOff', NSMAP) is not None or
                    scheme.find('a:hueMod', NSMAP) is not None or
                    scheme.find('a:satMod', NSMAP) is not None or
                    scheme.find('a:satOff', NSMAP) is not None)
        if not has_mods and val:
            return f'${val}'
        # Has modifications — resolve to hex
        return _parse_color_value(parent, scheme_map)

    sys_clr = search_root.find('a:sysClr', NSMAP)
    if sys_clr is not None:
        val = sys_clr.get('lastClr', '')
        if val:
            return f'#{val}'

    return None


# ---------------------------------------------------------------------------
# Theme reference resolution (for PPTD → PPTX export)
# ---------------------------------------------------------------------------

def resolve_theme_ref(value, theme, ref_type=None):
    """Resolve a $key theme reference.

    Returns (resolved_value, is_valid).
    If ref_type is None, auto-detect by checking colors → textStyles → tableStyles.
    """
    if not isinstance(value, str) or not value.startswith('$'):
        return value, True  # Not a reference

    key = value[1:]

    if ref_type:
        section = theme.get(ref_type, {})
        if key in section:
            return section[key], True
        return None, False

    # Auto-detect
    for section_name in ('colors', 'textStyles', 'tableStyles'):
        section = theme.get(section_name, {})
        if key in section:
            return section[key], True

    return None, False


def resolve_color(value, theme):
    """Resolve a color value (theme ref or hex) to a final hex string. Returns None on failure."""
    if not value:
        return None
    # Direct hex color — return as-is
    if isinstance(value, str) and value.startswith('#'):
        return value
    # Theme reference ($key)
    resolved, ok = resolve_theme_ref(value, theme, 'colors')
    if not ok:
        return None
    if isinstance(resolved, str) and resolved.startswith('#'):
        return resolved
    return None


# ---------------------------------------------------------------------------
# WCAG contrast ratio calculation
# ---------------------------------------------------------------------------

def _relative_luminance(r, g, b):
    """Calculate relative luminance per WCAG 2.0.

    Input: r, g, b in 0-255 range.
    Returns: luminance value 0.0-1.0.
    """
    def linearize(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(color1, color2):
    """Calculate WCAG contrast ratio between two hex colors.

    Args:
        color1, color2: hex strings like '#RRGGBB' or '#RRGGBBAA'

    Returns:
        Contrast ratio (1.0-21.0), or None if colors are invalid.
    """
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    if not rgb1 or not rgb2:
        return None

    l1 = _relative_luminance(*rgb1)
    l2 = _relative_luminance(*rgb2)

    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def get_contrast_threshold(font_size_pt, bold=False):
    """Get WCAG contrast ratio threshold for given font size.

    WCAG 2.0 Level AA:
    - Large text (>=18pt or >=14pt bold): 3:1
    - Normal text: 4.5:1
    """
    if font_size_pt >= 18 or (bold and font_size_pt >= 14):
        return 3.0
    return 4.5
