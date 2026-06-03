#!/usr/bin/env python3
"""
PPTD Shape — OOXML shape property parsing (fill, border, shadow, rotation).
"""

import math

from pptd_common import NSMAP, emu_to_px
from pptd_color import SCHEME_COLOR_MAP, _parse_color_value, parse_color_with_ref


def parse_ooxml_shape_properties(spPr, scheme_map=None, preserve_scheme=False):
    """Parse OOXML a:spPr element into PPTD fill/border/shadow/rotation/flip dict."""
    result = {}
    if spPr is None:
        return result
    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP

    # Fill
    solid_fill = spPr.find('a:solidFill', NSMAP)
    no_fill = spPr.find('a:noFill', NSMAP)
    grad_fill = spPr.find('a:gradFill', NSMAP)
    blip_fill = spPr.find('a:blipFill', NSMAP)

    color_fn = parse_color_with_ref if preserve_scheme else _parse_color_value

    if no_fill is not None:
        result['fill'] = None
    elif solid_fill is not None:
        color = color_fn(solid_fill, scheme_map)
        if color:
            result['fill'] = {'type': 'solid', 'color': color}
    elif grad_fill is not None:
        gs_lst = grad_fill.find('a:gsLst', NSMAP)
        stops = []
        if gs_lst is not None:
            for gs in gs_lst.findall('a:gs', NSMAP):
                pos = gs.get('pos')
                color = color_fn(gs, scheme_map)
                if color:
                    stops.append({
                        'position': int(pos) / 100000 if pos else 0,
                        'color': color,
                    })
        lin = grad_fill.find('a:lin', NSMAP)
        angle = 0
        if lin is not None:
            ang = lin.get('ang')
            if ang:
                angle = round((int(ang) / 60000) % 360, 1)
        path = grad_fill.find('a:path', NSMAP)
        gradient_type = 'radial' if path is not None else 'linear'
        result['fill'] = {
            'type': 'gradient',
            'gradientType': gradient_type,
            'angle': angle,
            'stops': stops,
        }
    elif blip_fill is not None:
        # Image fill — extract src from relationship
        blip = blip_fill.find('a:blip', NSMAP)
        if blip is not None:
            embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            if embed:
                result['fill'] = {'type': 'image', 'src': embed}  # rId, resolved later

    # Border
    ln = spPr.find('a:ln', NSMAP)
    if ln is not None:
        width = ln.get('w')
        border = {}
        if width:
            border['width'] = round(int(width) / 12700)  # EMU to pt/px
        border_color = color_fn(ln, scheme_map)
        if border_color:
            border['color'] = border_color
        dash = ln.find('a:prstDash', NSMAP)
        if dash is not None:
            val = dash.get('val', '')
            # OOXML ST_PresetLineDashVal → PPTD border style
            # PPTD spec: solid | dash | dot | none
            DASH_MAP = {
                'solid': 'solid', 'dash': 'dash', 'lgDash': 'dash',
                'dot': 'dot', 'lgDashDot': 'dash', 'lgDashDotDot': 'dash',
                'dashDot': 'dash', 'sysDash': 'dash', 'sysDot': 'dot',
                'sysDashDot': 'dash', 'sysDashDotDot': 'dash',
            }
            border['style'] = DASH_MAP.get(val, 'solid')
        else:
            no_line = ln.find('a:noFill', NSMAP)
            if no_line is not None:
                border['style'] = 'none'
            elif border_color:
                border['style'] = 'solid'
        if border:
            result['border'] = border

        # Arrows (a:ln/a:headEnd, a:ln/a:tailEnd)
        head_end = ln.find('a:headEnd', NSMAP)
        tail_end = ln.find('a:tailEnd', NSMAP)
        if head_end is not None or tail_end is not None:
            head_type = head_end.get('type', 'none') if head_end is not None else 'none'
            tail_type = tail_end.get('type', 'none') if tail_end is not None else 'none'
            # Only add arrow if at least one end has an arrow
            if head_type != 'none' or tail_type != 'none':
                result['arrow'] = [
                    head_type if head_type != 'none' else None,
                    tail_type if tail_type != 'none' else None,
                ]

    # Opacity (a:effectLst/a:alpha)
    effect_lst = spPr.find('a:effectLst', NSMAP)
    if effect_lst is not None:
        alpha_elem = effect_lst.find('a:alpha', NSMAP)
        if alpha_elem is not None:
            val = alpha_elem.get('val')
            if val:
                result['opacity'] = round(int(val) / 100000, 3)

        outer_shdw = effect_lst.find('a:outerShdw', NSMAP)
        if outer_shdw is not None:
            blur_rad = outer_shdw.get('blurRad')
            dist = outer_shdw.get('dist')
            direction = outer_shdw.get('dir')
            shadow = {}
            if blur_rad:
                shadow['blur'] = emu_to_px(blur_rad)
            if dist and direction:
                dist_px = emu_to_px(dist)
                angle_rad = int(direction) / 60000 * math.pi / 180
                shadow['offset'] = [
                    round(dist_px * math.cos(angle_rad)),
                    round(dist_px * math.sin(angle_rad)),
                ]
            shdw_color = _parse_color_value(outer_shdw, scheme_map)
            if shdw_color:
                shadow['color'] = shdw_color
            if shadow:
                result['shadow'] = shadow

    # Rotation (in 60000ths of a degree)
    xfrm = spPr.find('a:xfrm', NSMAP)
    if xfrm is not None:
        rot = xfrm.get('rot')
        if rot:
            result['rotation'] = round(int(rot) / 60000, 1)
        flip_h = xfrm.get('flipH') == '1'
        flip_v = xfrm.get('flipV') == '1'
        if flip_h or flip_v:
            result['flip'] = [flip_h, flip_v]

    # Shape adjustments
    prst_geom = spPr.find('a:prstGeom', NSMAP)
    if prst_geom is not None:
        av_lst = prst_geom.find('a:avLst', NSMAP)
        if av_lst is not None:
            adjustments = []
            for gd in av_lst.findall('a:gd', NSMAP):
                fmla = gd.get('fmla', '')
                if fmla.startswith('val '):
                    try:
                        adjustments.append(int(fmla[4:]))
                    except ValueError:
                        pass
            if adjustments:
                result['adjustments'] = adjustments

    return result
