"""
OOXML / lxml injection utilities for gen-pptx Python port.

Extracted from PPTGuru's pptd_common.py（剥掉 YAML / 文件系统 / shape.md 相关）。

提供：
- NSMAP / qn（namespace → Clark notation）
- EMU ↔ px / pt 转换
- OOXML 单位（角度 / 百分比）
- lxml 直接构造工具：inject_srgb_color / make_gradient_fill / make_shadow / etc.
  用于 python-pptx 不直接支持的渐变 / 透明度 / 阴影等
- dash 样式映射

所有 lxml 操作都是「构造」（数据 → XML），不解析。
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple


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


def qn(tag: str) -> str:
    """'a:srgbClr' → '{ns}srgbClr' Clark notation。"""
    prefix, local = tag.split(':')
    return f'{{{NSMAP[prefix]}}}{local}'


# ---------------------------------------------------------------------------
# EMU <-> Pixel / Point  (914400 EMU = 1 inch = 96 px; 12700 EMU = 1 pt)
# ---------------------------------------------------------------------------

EMU_PER_PX = 9525     # 914400 / 96
EMU_PER_PT = 12700
EMU_PER_INCH = 914400


def emu_to_px(emu) -> int:
    if emu is None:
        return 0
    return round(int(emu) / EMU_PER_PX)


def px_to_emu(px) -> int:
    return int(px * EMU_PER_PX)


def emu_to_pt(emu) -> int:
    return round(int(emu) / EMU_PER_PT)


def pt_to_emu(pt) -> int:
    return int(pt * EMU_PER_PT)


def px_to_inches(px) -> float:
    return float(px) / 96.0


def inches_to_emu(inches) -> int:
    return int(inches * EMU_PER_INCH)


# ---------------------------------------------------------------------------
# OOXML angle / percentage units
# ---------------------------------------------------------------------------

OOXML_DEGREE_UNIT = 60000     # 1 degree = 60000 units
OOXML_PERCENT_UNIT = 100000   # 100% = 100000 units


def ooxml_angle_to_degrees(val) -> float:
    return round(int(val) / OOXML_DEGREE_UNIT, 1)


def degrees_to_ooxml_angle(deg) -> int:
    return int(deg * OOXML_DEGREE_UNIT)


def ooxml_pct_to_ratio(val) -> float:
    return int(val) / OOXML_PERCENT_UNIT


def ratio_to_ooxml_pct(val) -> int:
    return int(val * OOXML_PERCENT_UNIT)


# ---------------------------------------------------------------------------
# Dash / border style mapping
# ---------------------------------------------------------------------------

# CSS line-style → OOXML prstDash
CSS_DASH_TO_OOXML = {
    'solid': 'solid',
    'dashed': 'dash',
    'dotted': 'dot',
    'double': 'solid',  # OOXML 无 double，做不出真正的双线，用 solid 近似
    'groove': 'dash',
    'ridge': 'dash',
    'inset': 'sysDash',
    'outset': 'sysDash',
    'hidden': 'solid',  # width=0 时表示隐藏，style 这里给个默认值
}


# ---------------------------------------------------------------------------
# Font family parsing
# ---------------------------------------------------------------------------

def parse_font_family(font_str: str) -> Sequence[str]:
    """'Latin, CJK' → ['Latin', 'CJK']。"""
    if not font_str:
        return []
    return [f.strip().strip('"').strip("'") for f in font_str.split(',')]


# ---------------------------------------------------------------------------
# lxml color injection
# ---------------------------------------------------------------------------

def inject_srgb_color(parent_elem, hex_color: str):
    """在 parent_elem 下创建 a:srgbClr 子元素（带可选 a:alpha）。

    Args:
        parent_elem: lxml element（如 a:solidFill / a:gradFill gsLst gs）
        hex_color: '#RRGGBB' 或 '#RRGGBBAA'

    Returns:
        The created a:srgbClr element.
    """
    from lxml import etree

    srgb = etree.SubElement(parent_elem, qn('a:srgbClr'))
    hex_clean = (hex_color or '').lstrip('#')
    if len(hex_clean) >= 8:
        srgb.set('val', hex_clean[:6])
        alpha_8bit = int(hex_clean[6:8], 16)
        if alpha_8bit < 255:
            alpha_pct = round(alpha_8bit / 255 * OOXML_PERCENT_UNIT)
            alpha_elem = etree.SubElement(srgb, qn('a:alpha'))
            alpha_elem.set('val', str(alpha_pct))
    elif len(hex_clean) >= 6:
        srgb.set('val', hex_clean)
    else:
        srgb.set('val', '000000')  # 兜底
    return srgb


# ---------------------------------------------------------------------------
# lxml gradient / shadow / effects builders
# ---------------------------------------------------------------------------

def make_gradient_fill_xml(stops: Sequence[Tuple[float, str]],
                           angle_deg: float = 90.0,
                           gradient_type: str = 'linear'):
    """构造 a:gradFill XML 元素。

    Args:
        stops: [(position_0_to_1, hex_color), ...]
        angle_deg: 线性渐变角度（linear 时生效）
        gradient_type: 'linear' 或 'radial'

    Returns:
        lxml a:gradFill element（caller 自行 insert / append 到 spPr）。
    """
    from lxml import etree

    grad_fill = etree.Element(qn('a:gradFill'))
    gs_lst = etree.SubElement(grad_fill, qn('a:gsLst'))
    for pos, color in stops:
        gs = etree.SubElement(gs_lst, qn('a:gs'))
        gs.set('pos', str(ratio_to_ooxml_pct(max(0.0, min(1.0, pos)))))
        inject_srgb_color(gs, color)

    if gradient_type == 'radial':
        path = etree.SubElement(grad_fill, qn('a:path'))
        path.set('path', 'circle')
        fill_rect = etree.SubElement(path, qn('a:fillToRect'))
        fill_rect.set('l', '50000')
        fill_rect.set('t', '50000')
        fill_rect.set('r', '50000')
        fill_rect.set('b', '50000')
    else:  # linear
        lin = etree.SubElement(grad_fill, qn('a:lin'))
        lin.set('ang', str(degrees_to_ooxml_angle(angle_deg % 360)))
        lin.set('scaled', '1')
    return grad_fill


def make_outer_shadow_xml(blur_px: float, offset_x_px: float, offset_y_px: float,
                          color_hex: str, alpha: float = 1.0):
    """构造 a:outerShdw XML 元素（caller 把它放进 a:effectLst）。

    Args:
        blur_px: 模糊半径（px）
        offset_x_px / offset_y_px: x / y 偏移（px）
        color_hex: '#RRGGBB' 或 '#RRGGBBAA'
        alpha: 0-1
    """
    from lxml import etree
    import math

    shdw = etree.Element(qn('a:outerShdw'))
    shdw.set('blurRad', str(px_to_emu(blur_px)))
    dist = math.sqrt(offset_x_px ** 2 + offset_y_px ** 2)
    shdw.set('dist', str(px_to_emu(dist)))
    if dist > 0:
        # OOXML dir 是 1/60000 度，0 度向右，90 度向下（与 CSS 相反）
        ang_deg = math.degrees(math.atan2(offset_y_px, offset_x_px)) % 360
        shdw.set('dir', str(degrees_to_ooxml_angle(ang_deg)))
    shdw.set('rotWithShape', '0')

    srgb = etree.SubElement(shdw, qn('a:srgbClr'))
    srgb.set('val', (color_hex or '#000000').lstrip('#')[:6])
    if alpha < 1.0:
        alpha_elem = etree.SubElement(srgb, qn('a:alpha'))
        alpha_elem.set('val', str(ratio_to_ooxml_pct(alpha)))
    return shdw


def make_inner_shadow_xml(blur_px: float, offset_x_px: float, offset_y_px: float,
                          color_hex: str, alpha: float = 1.0):
    """构造 a:innerShdw XML 元素。参数同 make_outer_shadow_xml。"""
    from lxml import etree
    import math

    shdw = etree.Element(qn('a:innerShdw'))
    shdw.set('blurRad', str(px_to_emu(blur_px)))
    dist = math.sqrt(offset_x_px ** 2 + offset_y_px ** 2)
    shdw.set('dist', str(px_to_emu(dist)))
    if dist > 0:
        ang_deg = math.degrees(math.atan2(offset_y_px, offset_x_px)) % 360
        shdw.set('dir', str(degrees_to_ooxml_angle(ang_deg)))
    srgb = etree.SubElement(shdw, qn('a:srgbClr'))
    srgb.set('val', (color_hex or '#000000').lstrip('#')[:6])
    if alpha < 1.0:
        alpha_elem = etree.SubElement(srgb, qn('a:alpha'))
        alpha_elem.set('val', str(ratio_to_ooxml_pct(alpha)))
    return shdw


def make_effect_lst(*effects):
    """把若干 shadow / glow 元素包进 a:effectLst。"""
    from lxml import etree

    effect_lst = etree.Element(qn('a:effectLst'))
    for eff in effects:
        if eff is not None:
            effect_lst.append(eff)
    return effect_lst


def set_shape_alpha(shape, alpha_0_to_1: float, target: str = 'fill'):
    """给 python-pptx shape 的 fill / line 颜色打 alpha。

    python-pptx 不直接支持透明度，需要 lxml 写 a:alpha。
    shape.fill.fore_color 或 shape.line.color 必须已经设了 srgbClr。
    """
    from copy import deepcopy
    from lxml import etree

    if target == 'fill':
        color_elem = shape.fill.fore_color._xFill.find(qn('a:srgbClr'))
    elif target == 'line':
        color_elem = shape.line.color._xFill.find(qn('a:srgbClr'))
    else:
        return

    if color_elem is None:
        return

    existing_alpha = color_elem.find(qn('a:alpha'))
    if existing_alpha is not None:
        color_elem.remove(existing_alpha)
    alpha_elem = etree.SubElement(color_elem, qn('a:alpha'))
    alpha_elem.set('val', str(ratio_to_ooxml_pct(max(0.0, min(1.0, alpha_0_to_1)))))


def set_picture_crop(picture, left_ratio: float = 0.0, top_ratio: float = 0.0,
                     right_ratio: float = 0.0, bottom_ratio: float = 0.0):
    """给 python-pptx picture 写 a:blipFill/a:stretch/a:fillRect 实现 cover 裁剪。

    ratio 都是 0-1，表示该边裁掉的比例（OOXML fillRect 用负值表示裁掉）。
    """
    _set_picture_fill_rect(picture,
                           left=-ratio_to_ooxml_pct(left_ratio),
                           top=-ratio_to_ooxml_pct(top_ratio),
                           right=-ratio_to_ooxml_pct(right_ratio),
                           bottom=-ratio_to_ooxml_pct(bottom_ratio))


def set_picture_letterbox(picture, left_ratio: float = 0.0, top_ratio: float = 0.0,
                          right_ratio: float = 0.0, bottom_ratio: float = 0.0):
    """contain 模式：在 frame 内留 letterbox 边距。

    ratio 是该边缩进占 frame 边的比例（0-1，正值表示向内留白）。
    OOXML fillRect 正值就是 inset。
    """
    _set_picture_fill_rect(picture,
                           left=ratio_to_ooxml_pct(left_ratio),
                           top=ratio_to_ooxml_pct(top_ratio),
                           right=ratio_to_ooxml_pct(right_ratio),
                           bottom=ratio_to_ooxml_pct(bottom_ratio))


def _set_picture_fill_rect(picture, left: int, top: int, right: int, bottom: int):
    """统一写 a:blipFill/a:stretch/a:fillRect，正/负值由 caller 决定。"""
    from lxml import etree

    sp = picture._element
    # 找到现有的 blipFill（python-pptx 已经创建了）
    blip_fill = sp.find(qn('p:blipFill'))
    if blip_fill is None:
        blip_fill = sp.find(qn('a:blipFill'))
    if blip_fill is None:
        return

    # 移除已有 stretch
    existing_stretch = blip_fill.find(qn('a:stretch'))
    if existing_stretch is not None:
        blip_fill.remove(existing_stretch)

    stretch = etree.SubElement(blip_fill, qn('a:stretch'))
    fill_rect = etree.SubElement(stretch, qn('a:fillRect'))
    fill_rect.set('l', str(left))
    fill_rect.set('t', str(top))
    fill_rect.set('r', str(right))
    fill_rect.set('b', str(bottom))
