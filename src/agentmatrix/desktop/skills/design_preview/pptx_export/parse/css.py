"""CSS style → PptxGenJS-option helpers. 对应 core/css.ts。"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from .units import clamp, js_round, px_to_points, parse_int_lenient, parse_float_lenient
from .color import parse_color, ParsedColor


def extract_px(value) -> float:
    """First px length in value, else 0."""
    if not value:
        return 0.0
    m = re.search(r'(-?[\d.]+)px', value)
    return float(m.group(1)) if m else 0.0


def is_bold(weight) -> bool:
    # P5-2: JS parseInt('600abc',10)=600; Python int() rejects. Use lenient parser
    # to match TS semantics on malformed CSS.
    if not weight:
        return False
    if weight in ('bold', 'bolder'):
        return True
    return parse_int_lenient(weight, default=-1) >= 600


def text_align(value) -> str:
    """text-align → PptxGenJS align ('left'|'center'|'right'|'justify')."""
    if value == 'center':
        return 'center'
    if value in ('right', 'end'):
        return 'right'
    if value == 'justify':
        return 'justify'
    return 'left'


def border_style_to_dash_type(value) -> Optional[str]:
    """CSS border-style → PptxGenJS line dashType. double collapses to solid."""
    if value == 'dashed':
        return 'dash'
    if value == 'dotted':
        return 'dot'
    if value == 'double':
        return 'solid'
    return None


def parse_border_radius(value, min_side: float) -> float:
    if not value or min_side <= 0:
        return 0.0
    pct = re.match(r'^([\d.]+)%', value)
    px = (float(pct.group(1)) / 100) * min_side if pct else extract_px(value)
    if px <= 0:
        return 0.0
    return clamp(px, 0, min_side / 2)


def extract_rotation(transform) -> Optional[float]:
    """transform → rotation degrees (rotate() or matrix()), None when ~0."""
    if not transform or transform == 'none':
        return None
    rot = re.search(r'rotate\((-?[\d.]+)deg\)', transform)
    if rot:
        deg = float(rot.group(1))
        return None if deg == 0 else deg
    mat = re.search(r'matrix\(\s*([^,\s]+),\s*([^,\s]+),', transform)
    if mat:
        # P9-3: 用 parse_float_lenient 兼容 JS parseFloat 的前缀解析语义。
        a = parse_float_lenient(mat.group(1))
        b = parse_float_lenient(mat.group(2))
        deg = math.atan2(b, a) * (180 / math.pi)
        return None if abs(deg) < 0.01 else deg
    return None


@dataclass
class ShadowSpec:
    type: str        # "outer"
    color: str       # hex
    opacity: float   # 0..1
    blur: float      # points
    offset: float    # points
    angle: int       # degrees


def parse_shadow(value) -> Optional[ShadowSpec]:
    """First non-inset box/text shadow → ShadowSpec。"""
    if not value or value == 'none':
        return None
    # split on top-level commas (color funcs contain their own commas)
    parts = []
    depth = 0
    buf = ''
    for ch in value:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(buf)
            buf = ''
        else:
            buf += ch
    if buf:
        parts.append(buf)

    for part in parts:
        s = part.strip()
        if re.search(r'\binset\b', s):
            continue
        cm = re.search(r'(rgba?\([^)]+\)|#[0-9a-fA-F]{3,8})', s)
        # TS: regex matched but parseColor returned null (e.g. transparent /
        # rgba(0,0,0,0)) → skip this shadow entirely. Only fall back to
        # default black when NO color token was present at all.
        if cm:
            color = parse_color(cm.group(1))
            if color is None:
                continue
        else:
            color = ParsedColor(hex='000000', alpha=0.3)
        lengths = re.findall(r'(-?[\d.]+)px', s.replace(cm.group(0) if cm else '', ''))
        if len(lengths) < 2:
            continue
        offset_x = float(lengths[0])
        offset_y = float(lengths[1])
        blur = float(lengths[2]) if len(lengths) >= 3 else 0.0
        dist = math.sqrt(offset_x * offset_x + offset_y * offset_y)
        angle = math.atan2(offset_y, offset_x) * (180 / math.pi)
        if angle < 0:
            angle += 360
        return ShadowSpec(
            type='outer',
            color=color.hex,
            opacity=clamp(color.alpha, 0, 1),
            blur=clamp(px_to_points(blur), 0, 100),
            offset=clamp(px_to_points(dist), 0, 200),
            angle=js_round(angle),
        )
    return None


def line_spacing_multiple(line_height, font_size_px: float) -> Optional[float]:
    """line-height → PptxGenJS lineSpacingMultiple.

    px values normalize against the 1.3333 default leading; unitless multipliers
    pass through.
    """
    if not line_height or line_height == 'normal':
        return None
    px = extract_px(line_height)
    if px > 0:
        baseline = font_size_px * 1.3333333333333333
        return None if baseline <= 0 else clamp(px / baseline, 0.5, 5)
    # P11-4: 用 parse_float_lenient 兼容 JS parseFloat 的前缀解析语义。
    # line_height 已在上面完成 truthy + != 'normal' 检查。
    mult = parse_float_lenient(line_height, default=None)
    if mult is None:
        return None
    if 0 < mult < 10:
        return clamp(mult, 0.5, 5)
    return None


def letter_spacing_points(value) -> Optional[float]:
    if not value or value == 'normal':
        return None
    px = extract_px(value)
    if px != 0:
        return clamp(px_to_points(px), -20, 100)
    return None


def underline_style(value) -> str:
    if value == 'double':
        return 'dbl'
    if value == 'dotted':
        return 'dotted'
    if value == 'dashed':
        return 'dash'
    if value == 'wavy':
        return 'wavy'
    return 'sng'


def parse_opacity(style: dict) -> float:
    """统一 opacity 解析（对应 TS css.ts 的 `parseFloat(opacity ?? '1') || 1`）。

    TS 端的 `|| 1` 是个 latent bug：`opacity='0.0'` 时 parseFloat=0，`0 || 1 = 1`，
    author 明明想要完全透明，TS 却当不透明处理。Python 这里**有意偏离** TS：
    - 缺失 / 非法值 → 1.0（与 TS 一致）
    - '0' / '0.0' / '-0' → 0.0（语义正确，与 TS 偏离）

    见 findings R1-4 / R3-3。caller 用本 helper 替代 `_float_or + clamp` 链。
    """
    if not style:
        return 1.0
    raw = style.get('opacity')
    if raw is None or raw == '':
        return 1.0
    val = parse_float_lenient(raw, default=None)
    if val is None:
        return 1.0
    return clamp(val, 0.0, 1.0)


def normalize_text(text: str, white_space) -> str:
    if not text:
        return ''
    if white_space in ('pre', 'pre-wrap'):
        return re.sub(r'^\n+|\n+$', '', text)
    if white_space == 'pre-line':
        return re.sub(
            r'^\n+|\n+$', '',
            '\n'.join(
                re.sub(r'[ \t]+', ' ', line).strip()
                for line in text.split('\n')
            ),
        )
    return re.sub(r'\s+', ' ', text).strip()


def no_wrap(style: dict) -> bool:
    """Should this box suppress wrapping?"""
    if style.get('whiteSpace') == 'pre':
        return True
    if style.get('whiteSpace') != 'nowrap':
        return False
    raw_overflow = style.get('overflow') or ''
    # TS: `(style.overflow ?? '').trim().split(/\s+/)[0] ?? ''`
    # split() on a whitespace-only string returns [] → guard with [:1]
    parts = raw_overflow.strip().split()
    overflow = parts[0] if parts else ''
    scrollable = overflow in ('auto', 'scroll', 'overlay')
    ellipsis = (
        overflow in ('hidden', 'clip')
        and 'ellipsis' in (style.get('textOverflow') or '')
    )
    return not scrollable and not ellipsis
