"""
Color utilities for gen-pptx Python port.

Extracted from PPTGuru's pptd_color.py（剥掉 scheme_map / theme_ref 相关）+ 新增 CSS color 解析。

提供：
- hex / rgba 解析
- RGB ↔ HSL 转换
- WCAG 对比度（validate 用）
- CSS color 字符串解析（#hex / rgb() / rgba() / hsl() / hsla() / 命名色 / transparent）

不依赖 OOXML / pptd_common / lxml —— 纯 Python 工具。
"""

from __future__ import annotations

from typing import Optional, Tuple


# ---------------------------------------------------------------------------
# Hex color helpers
# ---------------------------------------------------------------------------

def is_valid_hex_color(color) -> bool:
    """3 / 4 / 6 / 8 位 hex（前缀 # 可选）。"""
    if not isinstance(color, str):
        return False
    c = color.lstrip('#')
    if len(c) not in (3, 4, 6, 8):
        return False
    return all(ch in '0123456789ABCDEFabcdef' for ch in c)


def hex_to_rgb(hex_color) -> Optional[Tuple[int, int, int]]:
    """#RRGGBB / #RGB / #RRGGBBAA / #RGBA → (r, g, b). 失败返回 None。"""
    if not hex_color or not isinstance(hex_color, str):
        return None
    h = hex_color.lstrip('#')
    # 展开 #RGB / #RGBA 简写
    if len(h) in (3, 4):
        h = ''.join(ch * 2 for ch in h)
    if len(h) >= 6:
        try:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        except ValueError:
            return None
    return None


def hex_to_rgba(hex_color) -> Optional[Tuple[int, int, int, int]]:
    """#RRGGBB / #RGB / #RRGGBBAA / #RGBA → (r, g, b, a). a 默认 255。失败返回 None。"""
    if not hex_color or not isinstance(hex_color, str):
        return None
    h = hex_color.lstrip('#')
    if len(h) in (3, 4):
        h = ''.join(ch * 2 for ch in h)
    if len(h) >= 6:
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            a = int(h[6:8], 16) if len(h) >= 8 else 255
            return (r, g, b, a)
        except ValueError:
            return None
    return None


def rgb_to_hex(r: int, g: int, b: int, a: Optional[int] = None) -> str:
    """RGB(A) 0-255 → #RRGGBB 或 #RRGGBBAA（a < 255 时附 alpha）。"""
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    base = f'#{r:02X}{g:02X}{b:02X}'
    if a is not None and a < 255:
        a = max(0, min(255, int(a)))
        base += f'{a:02X}'
    return base


def alpha_to_hex(alpha_0_to_1: float) -> str:
    """0.0-1.0 alpha → 'AA'（2 位 hex）。OOXML 注入时用。"""
    a = max(0, min(255, round(float(alpha_0_to_1) * 255)))
    return f'{a:02X}'


# ---------------------------------------------------------------------------
# HSL conversion
# ---------------------------------------------------------------------------

def rgb_to_hsl(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """0-255 RGB → HSL (h=0-1, s=0-1, l=0-1)."""
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


def hsl_to_rgb(h: float, s: float, l: float) -> Tuple[int, int, int]:
    """HSL (h=0-1, s=0-1, l=0-1) → 0-255 RGB."""
    if s == 0:
        v = round(l * 255)
        return v, v, v

    def hue_to_rgb(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = round(hue_to_rgb(p, q, h + 1 / 3) * 255)
    g = round(hue_to_rgb(p, q, h) * 255)
    b = round(hue_to_rgb(p, q, h - 1 / 3) * 255)
    return r, g, b


# ---------------------------------------------------------------------------
# WCAG contrast ratio
# ---------------------------------------------------------------------------

def _relative_luminance(r: int, g: int, b: int) -> float:
    """WCAG 2.0 relative luminance (0.0-1.0)."""
    def linearize(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def contrast_ratio(color1, color2) -> Optional[float]:
    """两个 hex 颜色之间的 WCAG 对比度（1.0-21.0）。"""
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)
    if not rgb1 or not rgb2:
        return None
    l1 = _relative_luminance(*rgb1)
    l2 = _relative_luminance(*rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def get_contrast_threshold(font_size_pt: float, bold: bool = False) -> float:
    """WCAG AA 阈值：大字（>=18pt 或 >=14pt bold）3:1，普通 4.5:1。"""
    if font_size_pt >= 18 or (bold and font_size_pt >= 14):
        return 3.0
    return 4.5


# ---------------------------------------------------------------------------
# CSS color parsing
# ---------------------------------------------------------------------------

# CSS3 基础命名色（17 个）+ extended 的高频色，gen-pptx 处理 HTML 时够用。
# 完整 CSS3 147 色太长，按需扩展。
CSS_NAMED_COLORS = {
    'transparent': (0, 0, 0, 0),
    'black': (0, 0, 0, 255),
    'white': (255, 255, 255, 255),
    'red': (255, 0, 0, 255),
    'lime': (0, 255, 0, 255),
    'blue': (0, 0, 255, 255),
    'yellow': (255, 255, 0, 255),
    'cyan': (0, 255, 255, 255),
    'aqua': (0, 255, 255, 255),
    'magenta': (255, 0, 255, 255),
    'fuchsia': (255, 0, 255, 255),
    'silver': (192, 192, 192, 255),
    'gray': (128, 128, 128, 255),
    'grey': (128, 128, 128, 255),
    'maroon': (128, 0, 0, 255),
    'olive': (128, 128, 0, 255),
    'green': (0, 128, 0, 255),
    'purple': (128, 0, 128, 255),
    'teal': (0, 128, 128, 255),
    'navy': (0, 0, 128, 255),
    'orange': (255, 165, 0, 255),
    'pink': (255, 192, 203, 255),
    'brown': (165, 42, 42, 255),
    'gold': (255, 215, 0, 255),
    'tomato': (255, 99, 71, 255),
    'coral': (255, 127, 80, 255),
    'khaki': (240, 230, 140, 255),
    'lavender': (230, 230, 250, 255),
    'violet': (238, 130, 238, 255),
    'salmon': (250, 128, 114, 255),
}


def _parse_channel(value: str) -> int:
    """解析 rgb() 通道值：0-255 或 0%-100%。"""
    v = value.strip()
    if v.endswith('%'):
        return round(float(v[:-1]) / 100 * 255)
    return int(v)


def _parse_alpha(value: str) -> float:
    """解析 rgba/hsla 的 alpha：0-1 或 0%-100%。"""
    v = value.strip()
    if v.endswith('%'):
        return float(v[:-1]) / 100
    return float(v)


def parse_css_color(text) -> Optional[Tuple[int, int, int, int]]:
    """解析 CSS color 字符串 → (r, g, b, a)。

    支持：
      - #RGB / #RGBA / #RRGGBB / #RRGGBBAA
      - rgb(r,g,b) / rgba(r,g,b,a)
      - hsl(h,s%,l%) / hsla(h,s%,l%,a)
      - 命名色（'red' / 'transparent' 等，见 CSS_NAMED_COLORS）
      - 'transparent'

    不支持：currentColor / 系统色 / calc() / 4-channel rgb() with `/` 语法（CSS Color 4）。
    """
    if not text or not isinstance(text, str):
        return None
    s = text.strip().lower()

    # 命名色
    if s in CSS_NAMED_COLORS:
        return CSS_NAMED_COLORS[s]

    # hex
    if s.startswith('#'):
        return hex_to_rgba(s)

    # rgb() / rgba()
    if s.startswith('rgb(') or s.startswith('rgba('):
        inner = s[s.index('(') + 1: s.rindex(')')]
        # CSS Color 4: rgb(r g b / a) 空格分隔
        if '/' in inner:
            rgb_part, _, alpha_part = inner.partition('/')
            parts = rgb_part.split()
            alpha = _parse_alpha(alpha_part)
        else:
            parts = inner.split(',')
            alpha = _parse_alpha(parts[3]) if len(parts) >= 4 else 1.0
        if len(parts) < 3:
            return None
        try:
            r = _parse_channel(parts[0])
            g = _parse_channel(parts[1])
            b = _parse_channel(parts[2])
            return (r, g, b, round(alpha * 255))
        except (ValueError, IndexError):
            return None

    # hsl() / hsla()
    if s.startswith('hsl(') or s.startswith('hsla('):
        inner = s[s.index('(') + 1: s.rindex(')')]
        if '/' in inner:
            hsl_part, _, alpha_part = inner.partition('/')
            parts = hsl_part.split()
            alpha = _parse_alpha(alpha_part)
        else:
            parts = inner.split(',')
            alpha = _parse_alpha(parts[3]) if len(parts) >= 4 else 1.0
        if len(parts) < 3:
            return None
        try:
            h = float(parts[0].rstrip('deg')) / 360.0
            sat = float(parts[1].rstrip('%')) / 100.0
            lig = float(parts[2].rstrip('%')) / 100.0
            r, g, b = hsl_to_rgb(h % 1.0, sat, lig)
            return (r, g, b, round(alpha * 255))
        except (ValueError, IndexError):
            return None

    return None


def css_color_to_hex(text) -> Optional[str]:
    """CSS color 字符串 → #RRGGBB / #RRGGBBAA。失败返回 None。"""
    rgba = parse_css_color(text)
    if rgba is None:
        return None
    r, g, b, a = rgba
    return rgb_to_hex(r, g, b, a if a < 255 else None)
