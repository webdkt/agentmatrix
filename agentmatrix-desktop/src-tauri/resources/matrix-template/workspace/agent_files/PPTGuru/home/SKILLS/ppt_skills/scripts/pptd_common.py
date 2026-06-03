#!/usr/bin/env python3
"""
PPTD Common Utilities — shared constants, paths, EMU conversion, resource helpers.
"""

import re
import json
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
RESOURCE_DIR = PROJECT_DIR / 'resource'
FORMAT_DIR = PROJECT_DIR / 'format'
ICONS_DIR = RESOURCE_DIR / 'icons'
FONTS_DIR = RESOURCE_DIR / 'fonts'

# ---------------------------------------------------------------------------
# OOXML XML namespaces
# ---------------------------------------------------------------------------

NSMAP = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}

RELS_NS = '{http://schemas.openxmlformats.org/package/2006/relationships}'

# ---------------------------------------------------------------------------
# EMU <-> Pixel conversion  (914400 EMU = 1 inch = 96 px)
# ---------------------------------------------------------------------------

EMU_PER_PX = 9525  # 914400 / 96


def emu_to_px(emu):
    if emu is None:
        return 0
    return round(int(emu) / EMU_PER_PX)


def px_to_emu(px):
    return int(px * EMU_PER_PX)


# ---------------------------------------------------------------------------
# EMU <-> Point conversion  (12700 EMU = 1 pt)
# ---------------------------------------------------------------------------

EMU_PER_PT = 12700


def pt_to_emu(pt):
    return int(pt * EMU_PER_PT)


def emu_to_pt(emu):
    return round(int(emu) / EMU_PER_PT)


# ---------------------------------------------------------------------------
# OOXML unit constants
# ---------------------------------------------------------------------------

OOXML_DEGREE_UNIT = 60000    # 1 degree = 60000 units
OOXML_PERCENT_UNIT = 100000  # 100% = 100000 units


def ooxml_angle_to_degrees(val):
    return round(int(val) / OOXML_DEGREE_UNIT, 1)


def degrees_to_ooxml_angle(deg):
    return int(deg * OOXML_DEGREE_UNIT)


def ooxml_pct_to_ratio(val):
    return int(val) / OOXML_PERCENT_UNIT


def ratio_to_ooxml_pct(val):
    return int(val * OOXML_PERCENT_UNIT)


# ---------------------------------------------------------------------------
# Dash/border style mapping (OOXML <-> PPTD)
# ---------------------------------------------------------------------------

# OOXML ST_PresetLineDashVal → PPTD style (solid | dash | dot | none)
DASH_MAP = {
    'solid': 'solid', 'dash': 'dash', 'lgDash': 'dash',
    'dot': 'dot', 'lgDashDot': 'dash', 'lgDashDotDot': 'dash',
    'dashDot': 'dash', 'sysDash': 'dash', 'sysDot': 'dot',
    'sysDashDot': 'dash', 'sysDashDotDot': 'dash',
}


def map_dash_style(ooxml_val):
    """Map OOXML prstDash value to PPTD border/line style."""
    return DASH_MAP.get(ooxml_val, 'solid')


# PPTD style → python-pptx XL_DASH_STYLE integer
PPTD_DASH_TO_XL = {'solid': 1, 'dash': 2, 'dot': 3}


# ---------------------------------------------------------------------------
# Font family parsing
# ---------------------------------------------------------------------------

def parse_font_family(font_str):
    """Parse 'Latin, CJK' font string into list of font names."""
    if not font_str:
        return []
    return [f.strip().strip('"').strip("'") for f in font_str.split(',')]


# ---------------------------------------------------------------------------
# Hex8 color injection helper (for lxml XML construction)
# ---------------------------------------------------------------------------

def inject_srgb_color(parent_elem, hex_color):
    """Create a:srgbClr element with optional alpha, appending to parent_elem.

    Args:
        parent_elem: lxml element to append to
        hex_color: hex color string like '#RRGGBB' or '#RRGGBBAA'

    Returns:
        The created a:srgbClr element
    """
    from lxml import etree
    srgb = etree.SubElement(parent_elem, qn('a:srgbClr'))
    hex_clean = hex_color.lstrip('#')
    if len(hex_clean) >= 8:
        srgb.set('val', hex_clean[:6])
        alpha_8bit = int(hex_clean[6:8], 16)
        if alpha_8bit < 255:
            alpha_pct = round(alpha_8bit / 255 * OOXML_PERCENT_UNIT)
            alpha_elem = etree.SubElement(srgb, qn('a:alpha'))
            alpha_elem.set('val', str(alpha_pct))
    else:
        srgb.set('val', hex_clean)
    return srgb


def qn(tag):
    """Convert a prefixed tag like 'a:srgbClr' to Clark notation '{ns}tag'."""
    prefix, local = tag.split(':')
    ns = NSMAP[prefix]
    return f'{{{ns}}}{local}'


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_yaml(path):
    """Load a YAML file. Returns (data, error_message)."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, f'YAML parse error: {e}'
    except Exception as e:
        return None, f'File read error: {e}'


# ---------------------------------------------------------------------------
# Shape name mappings
# ---------------------------------------------------------------------------

def load_valid_shapes():
    """Load the set of valid PPTD shape names from shapes.md + common aliases."""
    shapes_file = FORMAT_DIR / 'shapes.md'
    shapes = set()
    if shapes_file.exists():
        with open(shapes_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'^\|\s*([a-zA-Z0-9_]+)\s*\|', line)
                if match:
                    shapes.add(match.group(1))
    # Aliases
    shapes.update({'line', 'arrow2', 'arrow10', 'ovalCallout', 'rectCallout', 'roundRectCallout'})
    return shapes


VALID_SHAPES = None  # Lazy-loaded


def get_valid_shapes():
    global VALID_SHAPES
    if VALID_SHAPES is None:
        VALID_SHAPES = load_valid_shapes()
    return VALID_SHAPES


def load_pptd_to_mso_map():
    """Map PPTD shapeName -> python-pptx MSO_SHAPE enum. Returns dict.

    Lazy-imports python-pptx so the module can be loaded without it for check/convert.
    """
    try:
        from pptx.enum.shapes import MSO_SHAPE
    except ImportError:
        return {}

    return {
        'rect': MSO_SHAPE.RECTANGLE,
        'roundRect': MSO_SHAPE.ROUNDED_RECTANGLE,
        'ellipse': MSO_SHAPE.OVAL,
        'triangle': MSO_SHAPE.ISOSCELES_TRIANGLE,
        'rtTriangle': MSO_SHAPE.RIGHT_TRIANGLE,
        'diamond': MSO_SHAPE.DIAMOND,
        'pentagon': MSO_SHAPE.REGULAR_PENTAGON,
        'hexagon': MSO_SHAPE.HEXAGON,
        'heptagon': MSO_SHAPE.HEPTAGON,
        'octagon': MSO_SHAPE.OCTAGON,
        'decagon': MSO_SHAPE.DECAGON,
        'dodecagon': MSO_SHAPE.DODECAGON,
        'star4': MSO_SHAPE.STAR_4_POINT,
        'star5': MSO_SHAPE.STAR_5_POINT,
        'star6': MSO_SHAPE.STAR_6_POINT,
        'star7': MSO_SHAPE.STAR_7_POINT,
        'star8': MSO_SHAPE.STAR_8_POINT,
        'star10': MSO_SHAPE.STAR_10_POINT,
        'star12': MSO_SHAPE.STAR_12_POINT,
        'star16': MSO_SHAPE.STAR_16_POINT,
        'star24': MSO_SHAPE.STAR_24_POINT,
        'star32': MSO_SHAPE.STAR_32_POINT,
        'rightArrow': MSO_SHAPE.RIGHT_ARROW,
        'leftArrow': MSO_SHAPE.LEFT_ARROW,
        'upArrow': MSO_SHAPE.UP_ARROW,
        'downArrow': MSO_SHAPE.DOWN_ARROW,
        'leftRightArrow': MSO_SHAPE.LEFT_RIGHT_ARROW,
        'upDownArrow': MSO_SHAPE.UP_DOWN_ARROW,
        'quadArrow': MSO_SHAPE.QUAD_ARROW,
        'chevron': MSO_SHAPE.CHEVRON,
        'homePlate': MSO_SHAPE.PENTAGON,
        'parallelogram': MSO_SHAPE.PARALLELOGRAM,
        'trapezoid': MSO_SHAPE.TRAPEZOID,
        'plus': MSO_SHAPE.CROSS,
        'donut': MSO_SHAPE.DONUT,
        'cube': MSO_SHAPE.CUBE,
        'can': MSO_SHAPE.CAN,
        'bevel': MSO_SHAPE.BEVEL,
        'foldedCorner': MSO_SHAPE.FOLDED_CORNER,
        'smileyFace': MSO_SHAPE.SMILEY_FACE,
        'sun': MSO_SHAPE.SUN,
        'moon': MSO_SHAPE.MOON,
        'cloud': MSO_SHAPE.CLOUD,
        'heart': MSO_SHAPE.HEART,
        'lightningBolt': MSO_SHAPE.LIGHTNING_BOLT,
        'pie': MSO_SHAPE.PIE,
        'arc': MSO_SHAPE.ARC,
        'blockArc': MSO_SHAPE.BLOCK_ARC,
        'noSmoking': MSO_SHAPE.NO_SYMBOL,
        'wedgeRectCallout': MSO_SHAPE.RECTANGULAR_CALLOUT,
        'wedgeRoundRectCallout': MSO_SHAPE.ROUNDED_RECTANGULAR_CALLOUT,
        'wedgeEllipseCallout': MSO_SHAPE.OVAL_CALLOUT,
        'cloudCallout': MSO_SHAPE.CLOUD_CALLOUT,
        'bracePair': MSO_SHAPE.DOUBLE_BRACE,
        'bracketPair': MSO_SHAPE.DOUBLE_BRACKET,
        'leftBrace': MSO_SHAPE.LEFT_BRACE,
        'rightBrace': MSO_SHAPE.RIGHT_BRACE,
        'leftBracket': MSO_SHAPE.LEFT_BRACKET,
        'rightBracket': MSO_SHAPE.RIGHT_BRACKET,
        'ribbon': MSO_SHAPE.UP_RIBBON,
        'ribbon2': MSO_SHAPE.DOWN_RIBBON,
        'wave': MSO_SHAPE.WAVE,
        'doubleWave': MSO_SHAPE.DOUBLE_WAVE,
        'plaque': MSO_SHAPE.TRAPEZOID,
        'frame': MSO_SHAPE.FRAME,
        'halfFrame': MSO_SHAPE.HALF_FRAME,
        'teardrop': MSO_SHAPE.OVAL,
        'chord': MSO_SHAPE.CHORD,
        'corner': MSO_SHAPE.CORNER,
        'diagStripe': MSO_SHAPE.DIAGONAL_STRIPE,
        'mathPlus': MSO_SHAPE.MATH_PLUS,
        'mathMinus': MSO_SHAPE.MATH_MINUS,
        'mathMultiply': MSO_SHAPE.MATH_MULTIPLY,
        'mathDivide': MSO_SHAPE.MATH_DIVIDE,
        'mathEqual': MSO_SHAPE.MATH_EQUAL,
        'flowChartProcess': MSO_SHAPE.FLOWCHART_PROCESS,
        'flowChartAlternateProcess': MSO_SHAPE.FLOWCHART_ALTERNATE_PROCESS,
        'flowChartDecision': MSO_SHAPE.FLOWCHART_DECISION,
        'flowChartInputOutput': MSO_SHAPE.FLOWCHART_DATA,
        'flowChartPredefinedProcess': MSO_SHAPE.FLOWCHART_PREDEFINED_PROCESS,
        'flowChartInternalStorage': MSO_SHAPE.FLOWCHART_INTERNAL_STORAGE,
        'flowChartDocument': MSO_SHAPE.FLOWCHART_DOCUMENT,
        'flowChartMultidocument': MSO_SHAPE.FLOWCHART_MULTIDOCUMENT,
        'flowChartTerminator': MSO_SHAPE.FLOWCHART_TERMINATOR,
        'flowChartPreparation': MSO_SHAPE.FLOWCHART_PREPARATION,
        'flowChartManualInput': MSO_SHAPE.FLOWCHART_MANUAL_INPUT,
        'flowChartManualOperation': MSO_SHAPE.FLOWCHART_MANUAL_OPERATION,
        'flowChartConnector': MSO_SHAPE.FLOWCHART_CONNECTOR,
        'flowChartOffpageConnector': MSO_SHAPE.FLOWCHART_OFFPAGE_CONNECTOR,
        'flowChartPunchedCard': MSO_SHAPE.FLOWCHART_PUNCHED_TAPE,
        'flowChartPunchedTape': MSO_SHAPE.FLOWCHART_PUNCHED_TAPE,
        'flowChartCollate': MSO_SHAPE.FLOWCHART_COLLATE,
        'flowChartSort': MSO_SHAPE.FLOWCHART_SORT,
        'flowChartExtract': MSO_SHAPE.FLOWCHART_EXTRACT,
        'flowChartMerge': MSO_SHAPE.FLOWCHART_MERGE,
        'flowChartOr': MSO_SHAPE.FLOWCHART_OR,
        'flowChartSummingJunction': MSO_SHAPE.FLOWCHART_SUMMING_JUNCTION,
        'flowChartOnlineStorage': MSO_SHAPE.FLOWCHART_DIRECT_ACCESS_STORAGE,
        'flowChartDelay': MSO_SHAPE.FLOWCHART_DELAY,
        'flowChartMagneticDisk': MSO_SHAPE.FLOWCHART_MAGNETIC_DISK,
        'flowChartMagneticDrum': MSO_SHAPE.FLOWCHART_MAGNETIC_DISK,
        'flowChartMagneticTape': MSO_SHAPE.FLOWCHART_SEQUENTIAL_ACCESS_STORAGE,
        'flowChartDisplay': MSO_SHAPE.FLOWCHART_DISPLAY,
        # Action buttons
        'actionButtonBlank': MSO_SHAPE.ACTION_BUTTON_CUSTOM,
        'actionButtonHome': MSO_SHAPE.ACTION_BUTTON_HOME,
        'actionButtonHelp': MSO_SHAPE.ACTION_BUTTON_HELP,
        'actionButtonInformation': MSO_SHAPE.ACTION_BUTTON_INFORMATION,
        'actionButtonForwardNext': MSO_SHAPE.ACTION_BUTTON_FORWARD_OR_NEXT,
        'actionButtonBackPrevious': MSO_SHAPE.ACTION_BUTTON_BACK_OR_PREVIOUS,
        'actionButtonEnd': MSO_SHAPE.ACTION_BUTTON_END,
        'actionButtonBeginning': MSO_SHAPE.ACTION_BUTTON_BEGINNING,
        'actionButtonReturn': MSO_SHAPE.ACTION_BUTTON_RETURN,
        'actionButtonDocument': MSO_SHAPE.ACTION_BUTTON_DOCUMENT,
        'actionButtonSound': MSO_SHAPE.ACTION_BUTTON_SOUND,
        'actionButtonMovie': MSO_SHAPE.ACTION_BUTTON_MOVIE,
    }


def get_mso_shape(shape_name):
    """Map PPTD shapeName to MSO_SHAPE enum. Falls back to RECTANGLE."""
    mso_map = load_pptd_to_mso_map()
    return mso_map.get(shape_name)


# ---------------------------------------------------------------------------
# Resource helpers — icons
# ---------------------------------------------------------------------------

# Style prefix -> directory name mapping
_STYLE_TO_DIR = {
    'fas': 'solid',
    'far': 'regular',
    'fab': 'brands',
    'solid': 'solid',
    'regular': 'regular',
    'brands': 'brands',
}

_DIR_TO_STYLE = {v: k for k, v in _STYLE_TO_DIR.items()}

_icons_json_cache = None
_shims_json_cache = None


def _load_icons_json():
    global _icons_json_cache
    if _icons_json_cache is None:
        icons_file = ICONS_DIR / 'icons.json'
        if icons_file.exists():
            with open(icons_file, 'r', encoding='utf-8') as f:
                _icons_json_cache = json.load(f)
        else:
            _icons_json_cache = {}
    return _icons_json_cache


def _load_shims_json():
    global _shims_json_cache
    if _shims_json_cache is None:
        shims_file = ICONS_DIR / 'shims.json'
        if shims_file.exists():
            with open(shims_file, 'r', encoding='utf=8') as f:
                _shims_json_cache = json.load(f)
        else:
            _shims_json_cache = []
    return _shims_json_cache


def _resolve_shim(name):
    """Resolve an old icon name to its current name via shims.json."""
    shims = _load_shims_json()
    for entry in shims:
        if len(entry) >= 3 and entry[0] == name:
            return entry[2]  # new name
    return name


def find_icon_svg(icon_name):
    """Find the SVG file for an icon name like 'fas:house' or 'far:heart'.

    Search order:
    1. Direct match: resource/icons/{style}/{name}.svg
    2. Shim resolution (old name -> new name)
    3. Search icons.json for name in other styles
    4. Search icons.json aliases.names

    Returns Path to SVG file, or None if not found.
    """
    if not icon_name or ':' not in icon_name:
        # Try bare name across all styles
        for style_dir in ('solid', 'regular', 'brands'):
            candidate = ICONS_DIR / style_dir / f'{icon_name}.svg'
            if candidate.exists():
                return candidate
        return None

    style_prefix, name = icon_name.split(':', 1)
    style_dir = _STYLE_TO_DIR.get(style_prefix, style_prefix)

    # 1. Direct match
    candidate = ICONS_DIR / style_dir / f'{name}.svg'
    if candidate.exists():
        return candidate

    # 2. Shim resolution
    resolved = _resolve_shim(name)
    if resolved != name:
        candidate = ICONS_DIR / style_dir / f'{resolved}.svg'
        if candidate.exists():
            return candidate

    # 3. Search icons.json for name in other styles
    icons = _load_icons_json()
    entry = icons.get(name) or icons.get(resolved)
    if entry:
        available_styles = entry.get('styles', [])
        for s in available_styles:
            dir_name = _STYLE_TO_DIR.get(s, s)
            candidate = ICONS_DIR / dir_name / f'{name}.svg'
            if candidate.exists():
                return candidate
            if resolved != name:
                candidate = ICONS_DIR / dir_name / f'{resolved}.svg'
                if candidate.exists():
                    return candidate

    # 4. Search aliases
    if entry:
        aliases = entry.get('aliases', {}).get('names', [])
        for alias in aliases:
            for dir_name in ('solid', 'regular', 'brands'):
                candidate = ICONS_DIR / dir_name / f'{alias}.svg'
                if candidate.exists():
                    return candidate

    return None


# ---------------------------------------------------------------------------
# Resource helpers — fonts
# ---------------------------------------------------------------------------

def find_font(font_name):
    """Check if a font is available in resource/fonts/ or system fonts.

    Returns a dict with status info, or None if not found.
    - If found in resource/fonts/: {'source': 'resource', 'path': '/path/to/font.ttf', 'family': 'FontName'}
    - If found as system font: {'source': 'system', 'path': '/path/to/font.ttf', 'family': 'FontName'}
    - If not found: None
    """
    if not font_name:
        return None

    # Handle "Latin, CJK" dual-font format — check each font
    fonts = [f.strip().strip('"').strip("'") for f in font_name.split(',')]

    for font in fonts:
        # 1. Check resource/fonts/<FontName>/ (subdirectory with weight variants)
        font_dir = FONTS_DIR / font
        if font_dir.is_dir():
            for ext in ('.ttf', '.otf'):
                matches = list(font_dir.glob(f'*{ext}'))
                if matches:
                    return {'source': 'resource', 'path': str(matches[0]), 'family': font}

        # 2. Check resource/fonts/<FontName>.ttf (single file)
        for ext in ('.ttf', '.otf', '.woff', '.woff2'):
            fpath = FONTS_DIR / f'{font}{ext}'
            if fpath.exists():
                return {'source': 'resource', 'path': str(fpath), 'family': font}

        # 3. Check system fonts
        sys_path = _find_system_font(font)
        if sys_path:
            return {'source': 'system', 'path': sys_path, 'family': font}

    return None


def _find_system_font(font_name):
    """Search system font directories for a font by family name.

    Returns the path to the font file if found, or None.
    Supports macOS, Windows, and Linux.
    """
    import sys as _sys
    platform = _sys.platform

    search_dirs = []
    if platform == 'darwin':
        search_dirs = [
            Path.home() / 'Library' / 'Fonts',
            Path('/Library/Fonts'),
            Path('/System/Library/Fonts'),
            Path('/Network/Library/Fonts'),
        ]
    elif platform == 'win32':
        import os
        win_fonts = Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'Fonts'
        search_dirs = [win_fonts]
        # Also check user fonts
        local_app = os.environ.get('LOCALAPPDATA')
        if local_app:
            search_dirs.append(Path(local_app) / 'Microsoft' / 'Windows' / 'Fonts')
    else:
        # Linux
        search_dirs = [
            Path.home() / '.local' / 'share' / 'fonts',
            Path('/usr/share/fonts'),
            Path('/usr/local/share/fonts'),
        ]

    font_lower = font_name.lower().replace(' ', '')

    for d in search_dirs:
        if not d.exists():
            continue
        # Search recursively for matching font files
        for ext in ('.ttf', '.otf', '.ttc', '.woff', '.woff2'):
            for f in d.rglob(f'*{ext}'):
                # Match by filename (case-insensitive, ignore spaces/dashes)
                fname_lower = f.stem.lower().replace(' ', '').replace('-', '')
                if font_lower in fname_lower or fname_lower.startswith(font_lower):
                    return str(f)

    return None


def list_system_fonts():
    """List available system font families. Returns set of font family names."""
    import sys as _sys
    platform = _sys.platform

    search_dirs = []
    if platform == 'darwin':
        search_dirs = [
            Path.home() / 'Library' / 'Fonts',
            Path('/Library/Fonts'),
            Path('/System/Library/Fonts'),
        ]
    elif platform == 'win32':
        import os
        win_fonts = Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'Fonts'
        search_dirs = [win_fonts]
        local_app = os.environ.get('LOCALAPPDATA')
        if local_app:
            search_dirs.append(Path(local_app) / 'Microsoft' / 'Windows' / 'Fonts')
    else:
        search_dirs = [
            Path.home() / '.local' / 'share' / 'fonts',
            Path('/usr/share/fonts'),
        ]

    families = set()
    for d in search_dirs:
        if not d.exists():
            continue
        for ext in ('.ttf', '.otf', '.ttc'):
            for f in d.rglob(f'*{ext}'):
                families.add(f.stem)
    return families
