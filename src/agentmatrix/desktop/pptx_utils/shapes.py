"""
Shape name → python-pptx MSO_SHAPE 映射。

Extracted from PPTGuru's pptd_common.py（load_pptd_to_mso_map）+ 加 CSS 别名。

DOM 节点最终映射成 PPT shape 时用：
    - rect / roundRect / ellipse / triangle ... (PPTD 命名)
    - rectangle / circle / pill / square (CSS 别名)
    - 不识别的 fallback 到 RECTANGLE
"""

from __future__ import annotations

from typing import Optional


# 别名映射：CSS / HTML 常见叫法 → PPTD shape 名（再走 PPTD_TO_MSO 映射到 MSO_SHAPE）
CSS_SHAPE_ALIASES = {
    'rectangle': 'rect',
    'square': 'rect',
    'box': 'rect',
    'rounded-rectangle': 'roundRect',
    'rounded': 'roundRect',
    'roundedrect': 'roundRect',
    'pill': 'roundRect',
    'circle': 'ellipse',
    'oval': 'ellipse',
    'round': 'ellipse',
    'triangle': 'triangle',
    'star': 'star5',
    'arrow': 'rightArrow',
    'line': 'line',
    'diamond': 'diamond',
    'parallelogram': 'parallelogram',
    'trapezoid': 'trapezoid',
    'hexagon': 'hexagon',
    'pentagon': 'pentagon',
    'octagon': 'octagon',
}


_PPTD_TO_MSO_CACHE = None
_PPTD_TO_MSO_LOWER_CACHE = None  # lower(key) → MSO_SHAPE，用于宽松匹配


def _load_pptd_to_mso_map():
    """Lazy-loaded map: PPTD shapeName → MSO_SHAPE enum。"""
    global _PPTD_TO_MSO_CACHE, _PPTD_TO_MSO_LOWER_CACHE
    if _PPTD_TO_MSO_CACHE is not None:
        return _PPTD_TO_MSO_CACHE
    try:
        from pptx.enum.shapes import MSO_SHAPE
    except ImportError:
        _PPTD_TO_MSO_CACHE = {}
        _PPTD_TO_MSO_LOWER_CACHE = {}
        return _PPTD_TO_MSO_CACHE

    _PPTD_TO_MSO_CACHE = {
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
    }
    _PPTD_TO_MSO_LOWER_CACHE = {k.lower(): v for k, v in _PPTD_TO_MSO_CACHE.items()}
    return _PPTD_TO_MSO_CACHE


def _lookup_lowercase(pptd_map, key: str):
    """宽松查找：lower(key) 直接命中 / 去除/添加连字符命中。"""
    lower_map = _PPTD_TO_MSO_LOWER_CACHE or {k.lower(): v for k, v in pptd_map.items()}
    if key in lower_map:
        return lower_map[key]
    # 去掉连字符再试：'flowchart-process' → 'flowchartprocess' → 'flowchartprocess' 仍 miss
    # 改：拆段后用每段首字母大写重组（首段不大写），逐段试
    parts = key.replace('_', '-').split('-')
    if len(parts) > 1:
        camel = parts[0] + ''.join(p.capitalize() for p in parts[1:])
        if camel.lower() in lower_map:
            return lower_map[camel.lower()]
        # 全部首字母大写：'FlowChartProcess' 也试一下
        pascal = ''.join(p.capitalize() for p in parts)
        if pascal.lower() in lower_map:
            return lower_map[pascal.lower()]
    return None


def get_mso_shape(shape_name: str, fallback: Optional[str] = 'rect'):
    """CSS / PPTD shape name → MSO_SHAPE 枚举。

    Args:
        shape_name: 任意大小写 / 横线 / 下划线形式
        fallback: 解析不到时的默认 shape（'rect' / None）

    Returns:
        MSO_SHAPE 枚举值；fallback=None 时找不到返回 None。
    """
    pptd_map = _load_pptd_to_mso_map()
    if not pptd_map:
        return None
    if not shape_name:
        return pptd_map.get(fallback) if fallback else None

    raw = shape_name.strip()
    key = raw.lower()
    # 0. 先按原样查 pptd_map（保留 camelCase，如 'roundRect' / 'rightArrow'）
    if raw in pptd_map:
        return pptd_map[raw]
    # 1. 按 CSS 别名转 PPTD 名（key 已小写）
    normalized = CSS_SHAPE_ALIASES.get(key, key)
    if normalized in pptd_map:
        return pptd_map[normalized]
    # 2. lower 宽松匹配（覆盖 'roundRect' / 'flowChartProcess' 这类 camelCase 输入被 lower 后的情况）
    loose = _lookup_lowercase(pptd_map, key)
    if loose is not None:
        return loose
    # 3. css-style 'rounded-rect' / 'rounded_rect' → camelCase 'roundRect'（再走 lower）
    parts = normalized.replace('_', '-').split('-')
    if len(parts) > 1:
        camel = parts[0] + ''.join(p.capitalize() for p in parts[1:])
        loose = _lookup_lowercase(pptd_map, camel.lower())
        if loose is not None:
            return loose
    if fallback:
        return pptd_map.get(fallback)
    return None
