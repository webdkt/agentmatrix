"""CSS color → {hex, alpha}. 对应 core/color.ts。

返回结构是 ParsedColor dataclass：hex 是 6 位大写（无 #），alpha 是 0..1。
transparent / none / 解析失败 / 完全透明 都返回 None。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from .units import clamp, js_round


@dataclass
class ParsedColor:
    hex: str       # 6-digit uppercase, no leading #
    alpha: float   # 0..1


_HEX_BODY_RE = re.compile(r'^[0-9a-f]+$')
_RGB_RE = re.compile(
    r'rgba?\(\s*(-?[\d.]+)[\s,]+(-?[\d.]+)[\s,]+(-?[\d.]+)(?:[\s,/]+([\d.]+%?))?\s*\)'
)


def parse_color(input_) -> Optional[ParsedColor]:
    if not input_:
        return None
    r = input_.strip().lower()
    if r in ('transparent', 'none'):
        return None

    if r.startswith('#'):
        body = r[1:]
        if len(body) in (3, 4):
            body = ''.join(c + c for c in body)
        alpha = 1.0
        if len(body) == 8:
            alpha = int(body[6:8], 16) / 255
            body = body[:6]
        if alpha == 0 or len(body) != 6 or not _HEX_BODY_RE.match(body):
            return None
        return ParsedColor(hex=body.upper(), alpha=alpha)

    m = _RGB_RE.match(r)
    if m:
        red = clamp(js_round(float(m.group(1))), 0, 255)
        green = clamp(js_round(float(m.group(2))), 0, 255)
        blue = clamp(js_round(float(m.group(3))), 0, 255)
        alpha = 1.0
        if m.group(4) is not None:
            a = m.group(4)
            alpha = float(a[:-1]) / 100 if a.endswith('%') else float(a)
            alpha = clamp(alpha, 0, 1)
        if alpha == 0:
            return None
        return ParsedColor(
            hex=f'{(red << 16) | (green << 8) | blue:06X}',
            alpha=alpha,
        )
    return None


def parse_gradient(input_) -> Optional[ParsedColor]:
    """First color stop of a CSS gradient (best-effort flat fill)."""
    if not input_ or 'gradient(' not in input_:
        return None
    m = re.search(r'(rgba?\([^)]+\)|#[0-9a-fA-F]{3,8})', input_)
    return parse_color(m.group(1)) if m else None


def opacity_to_transparency(alpha: float) -> int:
    """CSS opacity (0..1) → PptxGenJS-style transparency percent (0..100)."""
    return int(clamp(js_round((1 - alpha) * 100), 0, 100))
