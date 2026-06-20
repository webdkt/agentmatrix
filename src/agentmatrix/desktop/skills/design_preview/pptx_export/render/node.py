"""Recursive node renderer. 对应 render/render-node.ts。

这是 Phase 2 最大块。直接 port TS 版，调 ctx.slide（PptxSlideAdapter）的
addText / addShape / addImage。opts 用 dict（PptxGenJS 风格）。
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Set

from ..parse.color import parse_color, parse_gradient, opacity_to_transparency
from ..parse.css import (
    extract_px,
    parse_border_radius,
    extract_rotation,
    parse_shadow,
    border_style_to_dash_type,
    text_align,
    line_spacing_multiple,
    letter_spacing_points,
    no_wrap,
    normalize_text,
    parse_opacity,
)
from ..parse.units import clamp, js_round, px_to_inches, px_to_points
from ..types import Rect, SlideNode
from .context import RenderContext, rect_to_pptx
from .list_detect import detect_list, list_style_config
from .media_cache import image_key
from .text_runs import (
    extract_text_runs,
    text_format,
    text_transform_fn,
    valign_from_box,
    align_from_flex,
    http_href,
    runs_adjacent,
    runs_on_different_lines,
)


PT_PER_INCH = 72


def render_node_to_pptx(node: SlideNode, ctx: RenderContext):
    """Render a captured node (and its subtree) into the slide."""
    # ---- text leaf ----
    if node.tag == '#text':
        _render_text_leaf(node, ctx)
        return

    style = node.style
    if node.rect.w < 0.5 or node.rect.h < 0.5:
        for child in node.children:
            render_node_to_pptx(child, ctx)
        return
    if style.get('display') == 'none' or style.get('opacity') == '0':
        return
    if style.get('visibility') == 'hidden':
        for child in node.children:
            render_node_to_pptx(child, ctx)
        return

    rotation = extract_rotation(style.get('transform'))
    if rotation is not None and node.untransformedRect is not None:
        box_rect = node.untransformedRect
    else:
        box_rect = node.rect

    coords = rect_to_pptx(box_rect, ctx)
    min_side = min(box_rect.w, box_rect.h)
    radius_px = parse_border_radius(
        style.get('borderTopLeftRadius') or style.get('borderRadius'), min_side,
    )
    radius_ratio = (radius_px / min_side) if min_side > 0 else 0.0
    opacity = parse_opacity(style)

    bg_color = parse_color(style.get('backgroundColor'))
    if bg_color is None and not node.imageUrl:
        bg_color = parse_gradient(style.get('backgroundImage'))
    bg_fill = None
    if bg_color is not None:
        bg_fill = {'hex': bg_color.hex, 'alpha': bg_color.alpha * opacity}

    top_w = extract_px(style.get('borderTopWidth') or style.get('borderWidth'))
    bottom_w = extract_px(style.get('borderBottomWidth'))
    left_w = extract_px(style.get('borderLeftWidth'))
    right_w = extract_px(style.get('borderRightWidth'))
    any_border = top_w or bottom_w or left_w or right_w
    top_color = style.get('borderTopColor') or style.get('borderColor')
    bottom_color = style.get('borderBottomColor') or style.get('borderColor')
    left_color = style.get('borderLeftColor') or style.get('borderColor')
    right_color = style.get('borderRightColor') or style.get('borderColor')
    top_style_v = style.get('borderTopStyle') or style.get('borderStyle')
    bottom_style_v = style.get('borderBottomStyle') or style.get('borderStyle')
    left_style_v = style.get('borderLeftStyle') or style.get('borderStyle')
    right_style_v = style.get('borderRightStyle') or style.get('borderStyle')

    uniform_border = (
        top_w > 0
        and top_w == bottom_w == left_w == right_w
        and top_color == bottom_color == left_color == right_color
        and top_style_v == bottom_style_v == left_style_v == right_style_v
    )
    uniform_border_color = parse_color(top_color) if uniform_border else None
    shadow = parse_shadow(style.get('boxShadow'))
    dash_type = border_style_to_dash_type(style.get('borderTopStyle') or style.get('borderStyle'))

    # ---- background / uniform border / shadow shape ----
    if bg_fill or uniform_border_color or shadow:
        opts: Dict[str, Any] = {
            'x': coords.x,
            'y': coords.y,
            'w': coords.w,
            'h': coords.h,
            'fill': (
                {'color': bg_fill['hex'], 'transparency': opacity_to_transparency(bg_fill['alpha'])}
                if bg_fill else {'type': 'none'}
            ),
            'line': (
                {
                    'color': uniform_border_color.hex,
                    'width': clamp(px_to_points(top_w), 0.25, 20),
                    'transparency': opacity_to_transparency(uniform_border_color.alpha * opacity),
                    'dashType': dash_type,
                }
                if uniform_border_color else {'type': 'none'}
            ),
        }
        if shadow:
            opts['shadow'] = {
                'type': shadow.type,
                'color': shadow.color,
                'opacity': shadow.opacity * opacity,
                'blur': shadow.blur,
                'offset': shadow.offset,
                'angle': shadow.angle,
            }
        if rotation is not None:
            opts['rotate'] = rotation
        shape_name = 'rect'
        if radius_ratio >= 0.49:
            aspect = box_rect.w / box_rect.h if box_rect.h else 0
            if 0.75 < aspect < 1.33:
                shape_name = 'ellipse'
            else:
                shape_name = 'roundRect'
                opts['rectRadius'] = px_to_inches(radius_px)
        elif radius_px > 0.5:
            shape_name = 'roundRect'
            opts['rectRadius'] = px_to_inches(radius_px)
        try:
            ctx.slide.addShape(shape_name, opts)
        except Exception as e:
            ctx.warnings.append(f'addShape failed for <{node.tag}>: {e}')

    # ---- per-side borders (non-uniform) ----
    if not uniform_border and any_border > 0:
        cx = box_rect.x + box_rect.w / 2
        cy = box_rect.y + box_rect.h / 2
        rad = math.radians(rotation) if rotation is not None else 0.0
        cos_v = math.cos(rad)
        sin_v = math.sin(rad)

        def side(width, color_str, px_v, py_v, pw, ph_v):
            if width <= 0:
                return
            color = parse_color(color_str)
            if not color:
                return
            ox = px_v
            oy = py_v
            if rotation is not None:
                dx = px_v + pw / 2 - cx
                dy = py_v + ph_v / 2 - cy
                ox = cx + dx * cos_v - dy * sin_v - pw / 2
                oy = cy + dx * sin_v + dy * cos_v - ph_v / 2
            try:
                side_opts = {
                    'x': px_to_inches(ox - ctx.originX),
                    'y': px_to_inches(oy - ctx.originY),
                    'w': px_to_inches(max(pw, 1)),
                    'h': px_to_inches(max(ph_v, 1)),
                    'fill': {
                        'color': color.hex,
                        'transparency': opacity_to_transparency(color.alpha * opacity),
                    },
                    'line': {'type': 'none'},
                }
                if rotation is not None:
                    side_opts['rotate'] = rotation
                ctx.slide.addShape('rect', side_opts)
            except Exception:
                pass  # per-side border is best-effort

        if bottom_w > 0:
            side(bottom_w, bottom_color, box_rect.x, box_rect.y + box_rect.h - bottom_w, box_rect.w, bottom_w)
        if top_w > 0:
            side(top_w, top_color, box_rect.x, box_rect.y, box_rect.w, top_w)
        if left_w > 0:
            side(left_w, left_color, box_rect.x, box_rect.y, left_w, box_rect.h)
        if right_w > 0:
            side(right_w, right_color, box_rect.x + box_rect.w - right_w, box_rect.y, right_w, box_rect.h)

    # ---- image / canvas / svg / background-image ----
    key = image_key(node)
    if key:
        entry = ctx.mediaCache.get(key)
        if entry and entry.dataUrl:
            img_opts: Dict[str, Any] = {
                'x': coords.x, 'y': coords.y,
                'w': coords.w, 'h': coords.h,
                'data': entry.dataUrl,
            }
            is_media_tag = node.tag in ('img', 'canvas', 'svg', 'object')
            has_bg_image = bool(style.get('backgroundImage') and style.get('backgroundImage') != 'none')
            fit = None
            if style.get('objectFit') and (is_media_tag or (style.get('objectFit') != 'fill' and not has_bg_image)):
                fit = style.get('objectFit')
            if not fit:
                if style.get('backgroundSize') == 'cover':
                    fit = 'cover'
                elif style.get('backgroundSize') == 'contain':
                    fit = 'contain'
            if fit in ('cover', 'contain'):
                img_opts['sizing'] = {'type': fit, 'w': coords.w, 'h': coords.h}

                def centered(pos):
                    # R5-3: TS 用 /^50%\s+50%$/ 接受任意空白（空格/tab/多空格）；
                    # 之前 Python 用字面量 '50% 50%' 只匹配单 ASCII 空格，
                    # CSS objectPosition 写成 '50%\t50%' 或多空格时不匹配，
                    # 不会触发 entry.w/h 的精确尺寸覆盖，图片会被错误拉伸。
                    return (not pos) or bool(re.match(r'^50%\s+50%$', pos.strip()))

                obj_fit_centered = (
                    bool(style.get('objectFit'))
                    and (is_media_tag or style.get('objectFit') != 'fill')
                    and style.get('objectFit') in ('cover', 'contain')
                    and (centered(style.get('objectPosition')) if is_media_tag else (not has_bg_image))
                )
                bg_centered = (
                    (not is_media_tag)
                    and has_bg_image
                    and (style.get('backgroundPosition') or '').strip() == '50% 50%'
                )
                if node.imageUrl and entry.w and entry.h and (obj_fit_centered or bg_centered):
                    img_opts['w'] = px_to_inches(entry.w)
                    img_opts['h'] = px_to_inches(entry.h)
            if radius_ratio >= 0.4:
                img_opts['rounding'] = True
            if opacity < 1:
                img_opts['transparency'] = clamp(js_round((1 - opacity) * 100), 0, 100)
            if rotation is not None:
                img_opts['rotate'] = rotation
            try:
                ctx.slide.addImage(img_opts)
            except Exception as e:
                ctx.warnings.append(f'addImage failed for <{node.tag}>: {e}')
        if node.tag in ('svg', 'img', 'canvas'):
            return

    # ---- uniform-list shortcut ----
    list_items = detect_list(node)
    consumed: Set[int] = set()
    if list_items:
        first_li = node.children[0]
        li_style = first_li.style
        list_type = li_style.get('listStyleType') or ''
        font_size = clamp(px_to_points(extract_px(li_style.get('fontSize')) or 16), 1, 400)
        fmt = text_format(li_style, ctx.fontMap)
        transform = text_transform_fn(li_style.get('textTransform'))
        cfg = list_style_config(list_type)
        indent_pt = max(font_size * 1.5, 14) if cfg.isNum else max(font_size * 0.7, 8)
        last_li = node.children[-1]
        top = first_li.rect.y - ctx.originY
        bottom = last_li.rect.y + last_li.rect.h - ctx.originY
        left = first_li.rect.x - ctx.originX
        opts: Dict[str, Any] = {
            'x': px_to_inches(left) - indent_pt / PT_PER_INCH,
            'y': px_to_inches(top),
            'w': px_to_inches(max(first_li.rect.w, 4)) + indent_pt / PT_PER_INCH + px_to_inches(8),
            'h': px_to_inches(max(bottom - top, 4)) + px_to_inches(4),
            'margin': 2,
            'fontFace': fmt.fontFace,
            'fontSize': font_size,
            'bold': fmt.bold,
            'italic': fmt.italic,
            'underline': fmt.underline,
            'strike': fmt.strike,
            'color': fmt.color,
            'transparency': clamp(js_round(100 - (100 - fmt.transparency) * opacity), 0, 100),
            'align': text_align(li_style.get('textAlign')),
            'valign': 'top',
            'fit': 'shrink',
            'wrap': not no_wrap(li_style),
            'lineSpacingMultiple': line_spacing_multiple(li_style.get('lineHeight'), font_size),
            'charSpacing': letter_spacing_points(li_style.get('letterSpacing')),
        }
        list_shadow = parse_shadow(li_style.get('textShadow'))
        if list_shadow:
            opts['shadow'] = {
                'type': list_shadow.type, 'color': list_shadow.color,
                'opacity': list_shadow.opacity * opacity,
                'blur': list_shadow.blur, 'offset': list_shadow.offset, 'angle': list_shadow.angle,
            }
        tab_pos = indent_pt / PT_PER_INCH

        def bullet_for(i):
            if list_type == 'none':
                return False
            if cfg.isNum:
                return {
                    'type': 'number', 'indent': indent_pt,
                    'numberStartAt': i + 1, 'numberType': cfg.numberType,
                }
            return {'indent': indent_pt, 'characterCode': cfg.characterCode}

        text_objs = []
        for i, item in enumerate(list_items):
            text_objs.append({
                'text': transform(item),
                'options': {
                    'bullet': bullet_for(i),
                    'tabStops': None if list_type == 'none' else [{'position': tab_pos}],
                    'breakLine': i < len(list_items) - 1,
                },
            })
        try:
            ctx.slide.addText(text_objs, opts)
        except Exception as e:
            ctx.warnings.append(f'addText(list) failed for <{node.tag}>: {e}')
        for child in node.children:
            consumed.add(id(child))

    # ---- inline text runs ----
    runs, run_consumed = extract_text_runs(node, ctx.fontMap)
    for c_id in run_consumed:
        consumed.add(c_id)
    if runs:
        font_size = clamp(px_to_points(extract_px(style.get('fontSize')) or 16), 1, 400)
        valign = valign_from_box(style)
        align = align_from_flex(style) or text_align(style.get('textAlign'))
        pad_top = extract_px(style.get('paddingTop'))
        pad_bottom = extract_px(style.get('paddingBottom'))
        pad_left = extract_px(style.get('paddingLeft'))
        pad_right = extract_px(style.get('paddingRight'))
        inset_left = left_w + pad_left
        inset_right = right_w + pad_right
        inset_top = top_w + pad_top
        inset_bottom = bottom_w + pad_bottom
        box_x = coords.x + px_to_inches(inset_left)
        box_y = coords.y + px_to_inches(inset_top)
        box_w = max(coords.w - px_to_inches(inset_left + inset_right), px_to_inches(4))
        box_h = max(coords.h - px_to_inches(inset_top + inset_bottom), px_to_inches(4))
        extra_w = px_to_inches(max(8, box_rect.w * 0.03))
        shift_x = extra_w if align == 'right' else (extra_w / 2 if align == 'center' else 0)
        opts: Dict[str, Any] = {
            'x': box_x - shift_x,
            'y': box_y,
            'w': box_w + extra_w,
            'h': box_h + px_to_inches(4),
            'margin': 2,
            'fontSize': font_size,
            'align': align,
            'valign': valign,
            'fit': 'shrink',
            'wrap': not no_wrap(style),
            'lineSpacingMultiple': line_spacing_multiple(style.get('lineHeight'), font_size),
            'charSpacing': letter_spacing_points(style.get('letterSpacing')),
        }
        if rotation is not None:
            opts['rotate'] = rotation
        text_shadow = parse_shadow(style.get('textShadow'))
        if text_shadow:
            opts['shadow'] = {
                'type': text_shadow.type, 'color': text_shadow.color,
                'opacity': text_shadow.opacity * opacity,
                'blur': text_shadow.blur, 'offset': text_shadow.offset, 'angle': text_shadow.angle,
            }
        if node.tag == 'li':
            list_type = style.get('listStyleType') or ''
            if list_type != 'none':
                cfg = list_style_config(list_type)
                indent_pt = max(font_size * 1.5, 14) if cfg.isNum else max(font_size * 0.7, 8)
                indent_in = indent_pt / PT_PER_INCH
                opts['x'] = opts['x'] - indent_in
                opts['w'] = opts['w'] + indent_in
                opts['tabStops'] = [{'position': indent_in}]
                if cfg.isNum:
                    bullet = {'type': 'number', 'indent': indent_pt, 'numberType': cfg.numberType}
                    if node.liIndex:
                        bullet['numberStartAt'] = node.liIndex
                    opts['bullet'] = bullet
                else:
                    opts['bullet'] = {'indent': indent_pt, 'characterCode': cfg.characterCode}

        node_href = http_href(node.href)
        if node_href:
            opts['hyperlink'] = {'url': node_href}
        transform = text_transform_fn(style.get('textTransform'))
        if len(runs) == 1:
            run = runs[0]
            alpha = (1 - run.fmt.transparency / 100) * opacity
            if not node_href and run.href:
                opts['hyperlink'] = {'url': run.href}
            opts.update({
                'fontFace': run.fmt.fontFace,
                'fontSize': run.fmt.fontSize if run.fmt.fontSize is not None else opts.get('fontSize'),
                'bold': run.fmt.bold,
                'italic': run.fmt.italic,
                'underline': run.fmt.underline,
                'strike': run.fmt.strike,
                'subscript': run.fmt.subscript,
                'superscript': run.fmt.superscript,
                'highlight': run.fmt.highlight,
                'color': run.fmt.color,
                'transparency': opacity_to_transparency(alpha),
            })
            try:
                ctx.slide.addText(transform(run.text), opts)
            except Exception as e:
                ctx.warnings.append(f'addText failed for <{node.tag}>: {e}')
        else:
            text_objs = []
            for i, run in enumerate(runs):
                alpha = (1 - run.fmt.transparency / 100) * opacity
                next_run = runs[i + 1] if i + 1 < len(runs) else None
                # next run 在新一行（HTML <br> 分行）→ 当前 run 末尾换行，不加空格
                # next run 同一行且紧贴 → 不加空格
                # next run 同一行但有间距 → 加空格
                if next_run and runs_on_different_lines(run, next_run):
                    sep = ''
                    break_line = True
                elif next_run and not runs_adjacent(run, next_run):
                    sep = ' '
                    break_line = False
                else:
                    sep = ''
                    break_line = False
                text_objs.append({
                    'text': transform(run.text) + sep,
                    'options': {
                        'fontFace': run.fmt.fontFace,
                        'fontSize': run.fmt.fontSize,
                        'bold': run.fmt.bold,
                        'italic': run.fmt.italic,
                        'underline': run.fmt.underline,
                        'strike': run.fmt.strike,
                        'subscript': run.fmt.subscript,
                        'superscript': run.fmt.superscript,
                        'highlight': run.fmt.highlight,
                        'color': run.fmt.color,
                        'transparency': opacity_to_transparency(alpha),
                        'hyperlink': ({'url': run.href} if (not node_href and run.href) else None),
                        'breakLine': break_line,
                    },
                })
            try:
                ctx.slide.addText(text_objs, opts)
            except Exception as e:
                ctx.warnings.append(f'addText(runs) failed for <{node.tag}>: {e}')

    for child in node.children:
        if id(child) not in consumed:
            render_node_to_pptx(child, ctx)


# ---------------------------------------------------------------------------
# Text leaf (#text node) — split out for readability
# ---------------------------------------------------------------------------

def _render_text_leaf(node: SlideNode, ctx: RenderContext):
    style = node.style
    text = normalize_text(node.text, style.get('whiteSpace')) if node.text else ''
    if not text or node.rect.w < 0.5 or node.rect.h < 0.5 or style.get('visibility') == 'hidden':
        return
    coords = rect_to_pptx(node.rect, ctx)
    fmt = text_format(style, ctx.fontMap)
    font_size = fmt.fontSize or clamp(px_to_points(extract_px(style.get('fontSize')) or 16), 1, 400)
    opacity = parse_opacity(style)
    width_pad = px_to_inches(max(8, node.rect.w * 0.03))
    try:
        opts = {
            'x': coords.x,
            'y': coords.y,
            'w': coords.w + width_pad,
            'h': coords.h + px_to_inches(4),
            'margin': 0,
            'fontFace': fmt.fontFace,
            'fontSize': font_size,
            'bold': fmt.bold,
            'italic': fmt.italic,
            'underline': fmt.underline,
            'strike': fmt.strike,
            'color': fmt.color,
            'transparency': opacity_to_transparency((1 - fmt.transparency / 100) * opacity),
            'align': text_align(style.get('textAlign')),
            'valign': 'top',
            'fit': 'shrink',
            'wrap': not no_wrap(style),
            'lineSpacingMultiple': line_spacing_multiple(style.get('lineHeight'), font_size),
            'charSpacing': letter_spacing_points(style.get('letterSpacing')),
        }
        ctx.slide.addText(text_transform_fn(style.get('textTransform'))(text), opts)
    except Exception as e:
        ctx.warnings.append(f'addText(#text) failed: {e}')
