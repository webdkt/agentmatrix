#!/usr/bin/env python3
"""
PPTX to PPTD Converter — converts .pptx files to .pptd format.
Usage: python3 pptd_convert.py <input.pptx> [-o output_dir/]
"""

import sys
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote

import yaml

from pptd_common import NSMAP, RELS_NS, emu_to_px, px_to_emu
from pptd_color import (
    build_scheme_color_map_from_theme_xml,
    build_clr_map, apply_clr_map_overrides,
    parse_ooxml_color, _parse_color_value, parse_color_with_ref,
)
from pptd_text import parse_ooxml_text_content
from pptd_shape import parse_ooxml_shape_properties


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tag(ns, local):
    return f'{NSMAP[ns]}{local}'


def _rel_id(elem, attr='embed'):
    """Extract r:id from an element."""
    return elem.get(f'{{{NSMAP["r"]}}}{attr}')


def _safe_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _read_zip(z, path):
    """Read a file from zip, return bytes or None."""
    try:
        return z.read(path)
    except KeyError:
        return None


# ---------------------------------------------------------------------------
# Relationship maps
# ---------------------------------------------------------------------------

def _build_rel_map(z, rels_path):
    """Build {rId: target} from a .rels file."""
    rel_map = {}
    data = _read_zip(z, rels_path)
    if data is None:
        return rel_map
    root = ET.fromstring(data)
    for rel in root.findall(f'.//{RELS_NS}Relationship'):
        rid = rel.get('Id')
        target = rel.get('Target')
        rel_type = rel.get('Type', '')
        if rid and target:
            rel_map[rid] = {'target': target, 'type': rel_type}
    return rel_map


def _resolve_media(target, media_map):
    """Resolve a relationship target to an absolute image path."""
    if target.startswith('../'):
        target = target.replace('../', 'ppt/')
    elif target.startswith('./'):
        target = target[2:]
    media_filename = Path(target).name
    return media_map.get(media_filename, f'/placeholder/{media_filename}')


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------

def _extract_media(z, output_dir):
    """Extract all media files from PPTX. Returns {filename: absolute_path}."""
    images_dir = output_dir / 'images'
    images_dir.mkdir(exist_ok=True)
    media_map = {}
    for name in z.namelist():
        if name.startswith('ppt/media/'):
            data = z.read(name)
            filename = Path(name).name
            out_path = images_dir / filename
            with open(out_path, 'wb') as f:
                f.write(data)
            media_map[filename] = str(out_path.resolve())
    return media_map


# ---------------------------------------------------------------------------
# Theme extraction
# ---------------------------------------------------------------------------

def _extract_theme(z, scheme_map):
    """Extract theme colors and font scheme from the PPTX."""
    theme = {'colors': {}, 'textStyles': {}, 'tableStyles': {}}

    # Extract all 12 scheme colors
    color_names = [
        'dk1', 'dk2', 'lt1', 'lt2', 'accent1', 'accent2', 'accent3',
        'accent4', 'accent5', 'accent6', 'hlink', 'folHlink',
    ]
    for name in color_names:
        hex_val = scheme_map.get(name)
        if hex_val:
            theme['colors'][name] = hex_val

    # Extract font scheme
    theme_xml = _read_zip(z, 'ppt/theme/theme1.xml')
    if theme_xml:
        try:
            root = ET.fromstring(theme_xml)
            font_scheme = root.find('.//a:fontScheme', NSMAP)
            if font_scheme is not None:
                major = font_scheme.find('.//a:majorFont/a:latin', NSMAP)
                minor = font_scheme.find('.//a:minorFont/a:latin', NSMAP)
                if major is not None:
                    tf = major.get('typeface')
                    if tf:
                        theme['textStyles']['title'] = {'fontFamily': tf}
                if minor is not None:
                    tf = minor.get('typeface')
                    if tf:
                        theme['textStyles']['body'] = {'fontFamily': tf}
        except Exception:
            pass

    # Build textStyles with defaults
    title_style = theme['textStyles'].get('title', {})
    title_style.setdefault('fontSize', 36)
    title_style.setdefault('color', '$accent1')
    title_style.setdefault('fontFamily', 'Arial')
    theme['textStyles']['title'] = title_style

    body_style = theme['textStyles'].get('body', {})
    body_style.setdefault('fontSize', 18)
    body_style.setdefault('color', '$dk1')
    body_style.setdefault('fontFamily', 'Arial')
    body_style.setdefault('lineHeight', 1.5)
    theme['textStyles']['body'] = body_style

    return theme


# ---------------------------------------------------------------------------
# Slide background parsing
# ---------------------------------------------------------------------------

def _parse_bg_pr(bg_pr, scheme_map):
    """Parse a p:bgPr element into PPTD background dict."""
    if bg_pr is None:
        return None

    # Solid fill
    solid = bg_pr.find('a:solidFill', NSMAP)
    if solid is not None:
        color = _parse_color_value(solid, scheme_map)
        if color:
            return {'type': 'solid', 'color': color}

    # Gradient fill
    grad = bg_pr.find('a:gradFill', NSMAP)
    if grad is not None:
        gs_lst = grad.find('a:gsLst', NSMAP)
        stops = []
        if gs_lst is not None:
            for gs in gs_lst.findall('a:gs', NSMAP):
                pos = gs.get('pos')
                color = _parse_color_value(gs, scheme_map)
                if color:
                    stops.append({
                        'position': int(pos) / 100000 if pos else 0,
                        'color': color,
                    })
        lin = grad.find('a:lin', NSMAP)
        angle = 0
        if lin is not None:
            ang = lin.get('ang')
            if ang:
                angle = round((int(ang) / 60000) % 360, 1)
        return {
            'type': 'gradient',
            'gradientType': 'linear',
            'angle': angle,
            'stops': stops,
        }

    # Image fill
    blip_fill = bg_pr.find('a:blipFill', NSMAP)
    if blip_fill is not None:
        blip = blip_fill.find('a:blip', NSMAP)
        if blip is not None:
            embed = _rel_id(blip)
            if embed:
                return {'type': 'image', 'src': embed}

    return None


def _parse_slide_background(slide_elem, scheme_map, layout_root=None):
    """Parse p:cSld/p:bg into PPTD background dict, with layout fallback."""
    bg = slide_elem.find('p:cSld/p:bg', NSMAP)
    if bg is not None:
        # Try bgPr first
        bg_pr = bg.find('.//p:bgPr', NSMAP)
        if bg_pr is not None:
            result = _parse_bg_pr(bg_pr, scheme_map)
            if result:
                return result
        # Try bgRef (scheme color reference)
        bg_ref = bg.find('p:bgRef', NSMAP)
        if bg_ref is not None:
            color = _parse_color_value(bg_ref, scheme_map)
            if color:
                return {'type': 'solid', 'color': color}

    # Only fall back to layout background if slide has an explicit <p:bg>
    # that couldn't be resolved (e.g., bgRef we couldn't follow).
    # If slide has NO <p:bg> at all, it inherits from master/layout through
    # OOXML's inheritance chain — don't apply layout bg directly.
    if bg is not None and layout_root is not None:
        layout_bg = layout_root.find('.//p:cSld/p:bg', NSMAP)
        if layout_bg is not None:
            bg_pr = layout_bg.find('.//p:bgPr', NSMAP)
            if bg_pr is not None:
                result = _parse_bg_pr(bg_pr, scheme_map)
                if result:
                    return result
            bg_ref = layout_bg.find('p:bgRef', NSMAP)
            if bg_ref is not None:
                color = _parse_color_value(bg_ref, scheme_map)
                if color:
                    return {'type': 'solid', 'color': color}

    return None


# ---------------------------------------------------------------------------
# Speaker notes parsing
# ---------------------------------------------------------------------------

def _parse_notes(z, slide_idx, slide_rels, scheme_map):
    """Extract speaker notes for a slide."""
    # Find notes slide via relationships
    for rid, info in slide_rels.items():
        if 'notesSlide' in info.get('type', ''):
            target = info['target']
            if target.startswith('/'):
                notes_path = target.lstrip('/')
            else:
                notes_path = f'ppt/slides/{target}'
            notes_xml = _read_zip(z, notes_path)
            if notes_xml:
                try:
                    notes_root = ET.fromstring(notes_xml)
                    txBody = notes_root.find('.//p:notes/p:cSld/p:spTree/p:sp/p:txBody', NSMAP)
                    if txBody is None:
                        # Try alternate path
                        txBody = notes_root.find('.//p:cSld/p:spTree/p:sp/p:txBody', NSMAP)
                    if txBody is not None:
                        text = parse_ooxml_text_content(txBody, scheme_map)
                        if text and text.strip():
                            # Strip HTML tags for plain text notes
                            import re
                            plain = re.sub(r'<[^>]+>', '', text).strip()
                            if plain:
                                return plain
                except Exception:
                    pass
    return None


# ---------------------------------------------------------------------------
# Shape / element parsing
# ---------------------------------------------------------------------------

def _parse_transform(xfrm_elem):
    """Extract bounds [x, y, w, h] from a:xfrm."""
    if xfrm_elem is None:
        return None
    off = xfrm_elem.find('a:off', NSMAP)
    ext = xfrm_elem.find('a:ext', NSMAP)
    if off is not None and ext is not None:
        return [
            emu_to_px(off.get('x')),
            emu_to_px(off.get('y')),
            emu_to_px(ext.get('cx')),
            emu_to_px(ext.get('cy')),
        ]
    return None


def _parse_image_crop(blip_fill_elem):
    """Parse a:blipFill/a:stretch/a:fillRect into PPTD crop dict."""
    if blip_fill_elem is None:
        return None
    stretch = blip_fill_elem.find('a:stretch', NSMAP)
    if stretch is None:
        return None
    fill_rect = stretch.find('a:fillRect', NSMAP)
    if fill_rect is None:
        return None
    # Values are in 1/100000 of the image dimension
    side_map = {'l': 'left', 't': 'top', 'r': 'right', 'b': 'bottom'}
    crop = {}
    for ooxml_side, pptd_side in side_map.items():
        val = fill_rect.get(ooxml_side)
        if val and int(val) > 0:
            crop[pptd_side] = int(val) / 100000
    return crop if crop else None


def _parse_text_element(sp, shape_id, bounds, scheme_map, media_map, slide_rels, layout_lst=None):
    """Parse a shape with text into a PPTD text element."""
    txBody = sp.find('p:txBody', NSMAP)
    if txBody is None:
        return None

    text_content = parse_ooxml_text_content(txBody, scheme_map)
    if not text_content or not text_content.strip():
        return None

    # Check if it's really just a text box (no special shape geometry)
    spPr = sp.find('p:spPr', NSMAP)
    prst_geom = spPr.find('a:prstGeom', NSMAP) if spPr is not None else None
    shape_name = prst_geom.get('prst', 'rect') if prst_geom is not None else 'rect'

    # Extract default text style from first run
    first_rPr = txBody.find('.//a:r/a:rPr', NSMAP)
    content = {'text': text_content}

    if first_rPr is not None:
        sz = first_rPr.get('sz')
        if sz:
            content['fontSize'] = int(int(sz) / 100)
        else:
            # Inherit font size from lstStyle defRPr (for footer/notes shapes)
            # Try slide's lstStyle first, then layout's lstStyle
            lst_style = txBody.find('a:lstStyle', NSMAP)
            found_sz = False
            if lst_style is not None:
                for lvl_tag in ('a:lvl1pPr', 'a:lvl2pPr', 'a:lvl3pPr'):
                    lvl_elem = lst_style.find(lvl_tag, NSMAP)
                    if lvl_elem is not None:
                        def_rpr = lvl_elem.find('a:defRPr', NSMAP)
                        if def_rpr is not None:
                            inherited_sz = def_rpr.get('sz')
                            if inherited_sz:
                                content['fontSize'] = int(int(inherited_sz) / 100)
                                found_sz = True
                                break
            # Fallback to layout's lstStyle
            if not found_sz and layout_lst is not None:
                for lvl_tag in ('a:lvl1pPr', 'a:lvl2pPr', 'a:lvl3pPr'):
                    lvl_elem = layout_lst.find(lvl_tag, NSMAP)
                    if lvl_elem is not None:
                        def_rpr = lvl_elem.find('a:defRPr', NSMAP)
                        if def_rpr is not None:
                            inherited_sz = def_rpr.get('sz')
                            if inherited_sz:
                                content['fontSize'] = int(int(inherited_sz) / 100)
                                break

        latin = first_rPr.find('a:latin', NSMAP)
        ea = first_rPr.find('a:ea', NSMAP)
        fonts = []
        if latin is not None and latin.get('typeface'):
            tf = latin.get('typeface')
            if not tf.startswith('+'):
                fonts.append(tf)
        if ea is not None and ea.get('typeface'):
            tf = ea.get('typeface')
            if not tf.startswith('+') and tf not in fonts:
                fonts.append(tf)
        if fonts:
            content['fontFamily'] = ', '.join(fonts)

        # Letter spacing (a:rPr/@spc, in 1/100 of a point)
        spc = first_rPr.get('spc')
        if spc:
            try:
                content['letterSpacing'] = round(int(spc) / 100, 1)
            except ValueError:
                pass

        # Text color from first run's solidFill
        solid_fill = first_rPr.find('a:solidFill', NSMAP)
        if solid_fill is not None:
            color = _parse_color_value(solid_fill, scheme_map)
            if color:
                content['color'] = color

    # Text direction and wrap from a:bodyPr
    body_pr = txBody.find('a:bodyPr', NSMAP)
    if body_pr is not None:
        vert = body_pr.get('vert')
        if vert in ('vert', 'eaVert', 'mongolianVert'):
            content['textDirection'] = 'vertical'
        wrap_attr = body_pr.get('wrap')
        if wrap_attr == 'none':
            content['wrap'] = False

    # Paragraph-level default alignment
    pPr = txBody.find('.//a:p/a:pPr', NSMAP)
    h_align = None
    if pPr is not None:
        align = pPr.get('algn')
        align_map = {'ctr': 'center', 'r': 'right', 'l': 'left', 'just': 'justify', 'dist': 'distributed'}
        if align in align_map:
            h_align = align_map[align]

    # Vertical alignment from a:bodyPr anchor attribute
    v_align = None
    if body_pr is not None:
        anchor = body_pr.get('anchor')
        anchor_map = {'t': 'top', 'ctr': 'middle', 'b': 'bottom'}
        if anchor in anchor_map:
            v_align = anchor_map[anchor]

    # Store as [h, v] array per spec (default vertical to 'top')
    if h_align or v_align:
        content['align'] = [h_align or 'left', v_align or 'top']

    element = {
        'elementId': f'text_{shape_id}',
        'elementType': 'text',
        'bounds': bounds,
        'content': content,
    }

    # Always include shapeName to preserve shape type for round-trip
    element['shapeName'] = shape_name

    return element


def _parse_shape_element(sp, shape_id, bounds, spPr, scheme_map):
    """Parse a shape without meaningful text into a PPTD shape element."""
    prst_geom = spPr.find('a:prstGeom', NSMAP) if spPr is not None else None
    cust_geom = spPr.find('a:custGeom', NSMAP) if spPr is not None else None

    custom_path = None
    if cust_geom is not None:
        shape_name = 'custom'
        # Try to extract SVG path from a:custGeom/a:avLst + a:pathLst
        path_elem = cust_geom.find('.//a:path', NSMAP)
        if path_elem is not None:
            w = path_elem.get('w', '0')
            h = path_elem.get('h', '0')
            # Build a simple SVG path from commands
            path_d = _ooxml_path_to_svg(path_elem)
            if path_d:
                custom_path = f'{w},{h};{path_d}'
    elif prst_geom is not None:
        shape_name = prst_geom.get('prst', 'rect')
    else:
        shape_name = 'rect'

    element = {
        'elementId': f'shape_{shape_id}',
        'elementType': 'shape',
        'bounds': bounds,
        'shapeName': shape_name,
    }
    if custom_path:
        element['path'] = custom_path

    # Add style properties from spPr
    if spPr is not None:
        props = parse_ooxml_shape_properties(spPr, scheme_map)
        element.update(props)

    return element


def _ooxml_path_to_svg(path_elem):
    """Convert OOXML a:path to SVG path d attribute string."""
    commands = []
    for child in path_elem:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'moveTo':
            pt = child.find('a:pt', NSMAP)
            if pt is not None:
                commands.append(f'M{pt.get("x", "0")},{pt.get("y", "0")}')
        elif tag == 'lnTo':
            pt = child.find('a:pt', NSMAP)
            if pt is not None:
                commands.append(f'L{pt.get("x", "0")},{pt.get("y", "0")}')
        elif tag == 'cubicBezTo':
            pts = child.findall('a:pt', NSMAP)
            if len(pts) >= 3:
                coords = []
                for pt in pts:
                    coords.append(f'{pt.get("x", "0")},{pt.get("y", "0")}')
                commands.append(f'C{" ".join(coords)}')
        elif tag == 'arcTo':
            wR = child.get('wR', '0')
            hR = child.get('hR', '0')
            stAng = child.get('stAng', '0')
            swAng = child.get('swAng', '0')
            # Approximate arc as line (simplified)
            commands.append(f'L{stAng},{swAng}')
        elif tag == 'close':
            commands.append('Z')
    return ' '.join(commands) if commands else None


def _parse_image_element(pic, shape_id, bounds, media_map, slide_rels):
    """Parse a p:pic into a PPTD image element."""
    blip = pic.find('.//a:blip', NSMAP)
    image_src = f'/placeholder/{shape_id}.png'

    if blip is not None:
        # Check for direct r:embed on a:blip (raster images)
        embed = _rel_id(blip)
        # Also check for SVG blip in extensions (asvg:svgBlip)
        if not embed:
            SVG_NS = 'http://schemas.microsoft.com/office/drawing/2016/SVG/main'
            svg_blip = blip.find(f'.//{{{SVG_NS}}}svgBlip')
            if svg_blip is not None:
                embed = svg_blip.get(f'{{{NSMAP["r"]}}}embed')
        if embed and embed in slide_rels:
            target = slide_rels[embed]['target']
            image_src = _resolve_media(target, media_map)

    element = {
        'elementId': f'img_{shape_id}',
        'elementType': 'image',
        'bounds': bounds,
        'src': image_src,
    }

    # Shape name and adjustments from p:spPr/a:prstGeom
    spPr = pic.find('p:spPr', NSMAP)
    if spPr is not None:
        prst_geom = spPr.find('a:prstGeom', NSMAP)
        if prst_geom is not None:
            prst = prst_geom.get('prst')
            if prst and prst != 'rect':
                element['shapeName'] = prst
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
                    element['adjustments'] = adjustments

    # Image crop and fit
    blip_fill = pic.find('.//a:blipFill', NSMAP)
    if blip_fill is not None:
        crop = _parse_image_crop(blip_fill)
        if crop:
            element['crop'] = crop
        # Image fit mode (PPTD spec: "fill" | "contain" | "cover")
        stretch = blip_fill.find('a:stretch', NSMAP)
        tile = blip_fill.find('a:tile', NSMAP)
        if tile is not None:
            # tile is not in PPTD spec; omit fit (defaults to cover)
            pass
        elif stretch is not None:
            fill_rect = stretch.find('a:fillRect', NSMAP)
            if fill_rect is not None:
                has_crop = any(fill_rect.get(s) and int(fill_rect.get(s, '0')) > 0
                              for s in ('l', 't', 'r', 'b'))
                if has_crop:
                    element['fit'] = {'mode': 'cover'}
                else:
                    element['fit'] = {'mode': 'fill'}
            else:
                element['fit'] = {'mode': 'fill'}

    return element


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------

def _parse_table_element(graphic_frame, shape_id, bounds, scheme_map):
    """Parse a p:graphicFrame with a:tbl into a PPTD table element."""
    tbl = graphic_frame.find('.//a:tbl', NSMAP)
    if tbl is None:
        return None

    # Table style ID
    tblPr = tbl.find('a:tblPr', NSMAP)
    table_style_id = None
    if tblPr is not None:
        style_id_elem = tblPr.find('a:tableStyleId', NSMAP)
        if style_id_elem is not None and style_id_elem.text:
            table_style_id = style_id_elem.text.strip()

    # Column widths from tblGrid (raw EMU values)
    tbl_grid = tbl.find('a:tblGrid', NSMAP)
    raw_col_widths = []
    if tbl_grid is not None:
        for grid_col in tbl_grid.findall('a:gridCol', NSMAP):
            w = grid_col.get('w')
            if w:
                raw_col_widths.append(int(w))

    # Convert to percentages (0-1, sum to 1)
    total_col_w = sum(raw_col_widths) if raw_col_widths else 0
    column_widths = [round(w / total_col_w, 4) for w in raw_col_widths] if total_col_w > 0 else []

    # Parse rows and cells
    raw_rows = []  # list of (height_emu, [cells])
    for tr in tbl.findall('a:tr', NSMAP):
        row_height = int(tr.get('h', '0'))
        cells = []

        for tc in tr.findall('a:tc', NSMAP):
            grid_span = int(tc.get('gridSpan', '1'))
            v_merge = tc.get('vMerge')

            # Cell text
            txBody = tc.find('a:txBody', NSMAP)
            cell_text = ''
            if txBody is not None:
                cell_text = parse_ooxml_text_content(txBody, scheme_map)

            cell = {}
            if cell_text:
                cell['content'] = {'text': cell_text}

            # Merged cells
            if grid_span > 1:
                cell['colSpan'] = grid_span
            if v_merge == '1' or v_merge == 'continue':
                cell['rowSpan'] = -1  # placeholder, will fix below

            # Cell fill
            tc_pr = tc.find('a:tcPr', NSMAP)
            if tc_pr is not None:
                solid_fill = tc_pr.find('a:solidFill', NSMAP)
                no_fill = tc_pr.find('a:noFill', NSMAP)
                if solid_fill is not None:
                    color = _parse_color_value(solid_fill, scheme_map)
                    if color:
                        cell['fill'] = {'type': 'solid', 'color': color}
                elif no_fill is not None:
                    cell['fill'] = 'none'

                # Vertical alignment → content.align [h, v]
                anchor = tc_pr.get('anchor')
                if anchor:
                    anchor_map = {'t': 'top', 'ctr': 'middle', 'b': 'bottom'}
                    v_align = anchor_map.get(anchor)
                    if v_align:
                        if 'content' not in cell:
                            cell['content'] = {}
                        cell['content']['align'] = ['center', v_align]

                # Per-cell borders — array format [top, right, bottom, left]
                border_map = {}
                for side_name, side_tag in [('top', 'a:lnT'), ('right', 'a:lnR'),
                                             ('bottom', 'a:lnB'), ('left', 'a:lnL')]:
                    ln = tc_pr.find(side_tag, NSMAP)
                    if ln is not None:
                        border = {}
                        w = ln.get('w')
                        if w:
                            border['width'] = round(int(w) / 12700)
                        # Check for noFill inside border
                        if ln.find('a:noFill', NSMAP) is not None:
                            border['style'] = 'none'
                        else:
                            # Check for prstDash
                            prst_dash = ln.find('a:prstDash', NSMAP)
                            if prst_dash is not None:
                                border['style'] = _map_dash_style(prst_dash.get('val', 'solid'))
                            else:
                                border['style'] = 'solid'
                        color = _parse_color_value(ln, scheme_map)
                        if color:
                            border['color'] = color
                        if border:
                            border_map[side_name] = border
                if border_map:
                    # Convert to array format: [top, right, bottom, left]
                    cell['border'] = [
                        border_map.get('top'),
                        border_map.get('right'),
                        border_map.get('bottom'),
                        border_map.get('left'),
                    ]

            cells.append(cell)

        raw_rows.append((row_height, cells))

    # Convert row heights to percentages (0-1, sum to 1)
    total_row_h = sum(h for h, _ in raw_rows) if raw_rows else 0
    row_heights = [round(h / total_row_h, 4) for h, _ in raw_rows] if total_row_h > 0 else []

    # Extract cell arrays from raw_rows
    rows = [cells for _, cells in raw_rows]

    # Fix rowSpan: convert -1 markers to actual span counts
    if rows and column_widths:
        num_cols = len(column_widths)
        for col_idx in range(num_cols):
            span = 1
            for row_idx in range(len(rows)):
                cells = rows[row_idx]
                if col_idx < len(cells):
                    cell = cells[col_idx]
                    if cell.get('rowSpan') == -1:
                        span += 1
                    else:
                        if span > 1:
                            rows[row_idx - span + 1][col_idx]['rowSpan'] = span
                        span = 1
            if span > 1:
                rows[len(rows) - span][col_idx]['rowSpan'] = span

        # Remove continuation cells (rowSpan == -1) from rows per spec:
        # "Each row array lists only actual cells, automatically skipping occupied columns"
        new_rows = []
        for row in rows:
            filtered = [cell for cell in row if cell.get('rowSpan') != -1]
            new_rows.append(filtered)
        rows = new_rows

    element = {
        'elementId': f'table_{shape_id}',
        'elementType': 'table',
        'bounds': bounds,
        'columnWidths': column_widths,
        'rowHeights': row_heights,
        'rows': rows,
    }
    if table_style_id:
        element['tableStyleId'] = table_style_id

    return element


# ---------------------------------------------------------------------------
# Chart parsing
# ---------------------------------------------------------------------------

def _parse_chart_element(graphic_frame, shape_id, bounds, z, slide_rels, scheme_map):
    """Parse a p:graphicFrame with c:chart into a PPTD chart element (spec format)."""
    # Find chart relationship (charts use r:id, not r:embed)
    chart_rid = None
    graphic = graphic_frame.find('.//a:graphic/a:graphicData', NSMAP)
    if graphic is not None:
        chart_elem = graphic.find('.//c:chart', NSMAP)
        if chart_elem is not None:
            chart_rid = _rel_id(chart_elem, 'id')
            if not chart_rid:
                chart_rid = _rel_id(chart_elem, 'embed')

    if not chart_rid or chart_rid not in slide_rels:
        return None

    chart_target = slide_rels[chart_rid]['target']
    if chart_target.startswith('/'):
        chart_path = chart_target.lstrip('/')
    else:
        import posixpath
        chart_path = posixpath.normpath(f'ppt/slides/{chart_target}')

    chart_xml = _read_zip(z, chart_path)
    if chart_xml is None:
        return None

    try:
        chart_root = ET.fromstring(chart_xml)
    except Exception:
        return None

    plot_area = chart_root.find('.//c:plotArea', NSMAP)
    if plot_area is None:
        return None

    # Find the chart type element (c:doughnutChart, c:barChart, etc.)
    # For combo charts, there may be multiple chart type elements
    oxml_tag, chart_elem = None, None
    chart_type_elements = []  # List of (tag, element) for combo charts
    for tag in ['doughnutChart', 'pieChart', 'pie3DChart',
                'barChart', 'bar3DChart', 'lineChart', 'line3DChart',
                'areaChart', 'area3DChart', 'scatterChart', 'radarChart', 'bubbleChart']:
        elem = plot_area.find(f'c:{tag}', NSMAP)
        if elem is not None:
            chart_type_elements.append((tag, elem))
            if oxml_tag is None:
                oxml_tag = tag
                chart_elem = elem

    if chart_elem is None:
        return None

    # Map OOXML tag to PPTD type (doughnut → pie, handled via options.innerRadius)
    oxml_to_pptd = {
        'barChart': 'bar', 'bar3DChart': 'bar',
        'lineChart': 'line', 'line3DChart': 'line',
        'pieChart': 'pie', 'pie3DChart': 'pie',
        'doughnutChart': 'pie',
        'areaChart': 'area', 'area3DChart': 'area',
        'scatterChart': 'scatter',
        'radarChart': 'radar',
        'bubbleChart': 'bubble',
    }

    # Check if this is a combo chart (multiple chart types)
    is_combo = len(chart_type_elements) > 1
    if is_combo:
        chart_type = 'combo'
    else:
        chart_type = oxml_to_pptd.get(oxml_tag, 'bar')

    # Build options
    options = {}

    # Doughnut → innerRadius
    if oxml_tag == 'doughnutChart':
        hole_size = chart_elem.find('c:holeSize', NSMAP)
        if hole_size is not None:
            val = hole_size.get('val', '70')
            options['innerRadius'] = int(val) / 100
        else:
            options['innerRadius'] = 0.7  # OOXML default

    # Pie startAngle
    if oxml_tag in ('pieChart', 'pie3DChart', 'doughnutChart'):
        start_ang = chart_elem.find('c:firstSliceAng', NSMAP)
        if start_ang is not None:
            val = start_ang.get('val', '0')
            if int(val) != 0:
                options['startAngle'] = int(val)

    # Bar direction
    if oxml_tag in ('barChart', 'bar3DChart'):
        bar_dir = chart_elem.find('c:barDir', NSMAP)
        if bar_dir is not None and bar_dir.get('val', '') == 'bar':
            options['direction'] = 'horizontal'

    # Stacking
    grouping = chart_elem.find('c:grouping', NSMAP)
    if grouping is not None:
        val = grouping.get('val', '')
        if val == 'stacked':
            options['stacked'] = True
        elif val == 'percentStacked':
            options['stacked'] = '100%'

    # Null handling (displayBlanksAs)
    display_blanks = chart_root.find('.//c:displayBlanksAs', NSMAP)
    if display_blanks is not None:
        val = display_blanks.get('val', '')
        null_map = {
            'span': 'connect',
            'gap': 'gap',
            'zero': 'zero',
        }
        if val in null_map:
            options['nullHandling'] = null_map[val]

    # Bar width (c:barSz)
    if oxml_tag in ('barChart', 'bar3DChart'):
        bar_sz = chart_elem.find('c:barSz', NSMAP)
        if bar_sz is not None:
            val = bar_sz.get('val')
            if val:
                try:
                    options['barWidth'] = int(val) / 100
                except ValueError:
                    pass

    # Extract data, series styles, and dPt colors
    if is_combo:
        # For combo charts, extract data from all chart type elements
        data, y_field, series_styles, names = _extract_combo_chart_data(chart_type_elements, scheme_map)
    else:
        data, y_field, series_styles, names = _extract_chart_data(chart_elem, scheme_map)
    if not data:
        return None

    # dPt colors (per-data-point, e.g. pie/doughnut slices)
    colors = _extract_dpt_colors(chart_elem, scheme_map)

    # Build element per PPTD spec
    element = {
        'elementId': f'chart_{shape_id}',
        'elementType': 'chart',
        'bounds': bounds,
        'type': chart_type,
        'x': '_category',
        'y': y_field,
        'data': data,
    }
    # For bubble charts, add size field
    if chart_type == 'bubble':
        if isinstance(y_field, list):
            # Multiple series: size fields are {name}_size
            element['size'] = [f'{name}_size' for name in y_field]
        else:
            element['size'] = '_size'
    if options:
        element['options'] = options
    if colors:
        element['colors'] = colors
    if names:
        element['names'] = names
    if series_styles:
        element['seriesStyle'] = series_styles

    # Data labels
    data_labels = _extract_chart_data_labels(chart_root, chart_elem, scheme_map)
    if data_labels:
        element['dataLabels'] = data_labels

    # Legend
    legend = _extract_chart_legend(chart_root, scheme_map)
    if legend is not None:
        element['legend'] = legend

    # Title
    auto_title_deleted = chart_root.find('.//c:autoTitleDeleted', NSMAP)
    if auto_title_deleted is None or auto_title_deleted.get('val', '0') != '1':
        title_elem = chart_root.find('.//c:title', NSMAP)
        if title_elem is not None:
            title_config = _extract_chart_title_config(title_elem, scheme_map)
            if title_config:
                element['title'] = title_config

    # Axes
    cat_ax = plot_area.find('c:catAx', NSMAP)
    val_ax_list = plot_area.findall('c:valAx', NSMAP)
    if cat_ax is not None:
        ax_config = _extract_axis_config(cat_ax, scheme_map)
        if ax_config:
            element['xAxis'] = ax_config
    if val_ax_list:
        # Primary value axis (first one)
        ax_config = _extract_axis_config(val_ax_list[0], scheme_map)
        if ax_config:
            element['yAxis'] = ax_config
        # Secondary value axis (second one, if exists)
        if len(val_ax_list) > 1:
            ax_config = _extract_axis_config(val_ax_list[1], scheme_map)
            if ax_config:
                element['secondaryAxis'] = ax_config

    # Try to extract chart-wide fontFamily from title or axis tick labels
    # This is a heuristic for the options.fontFamily convenience property
    font_family = None
    # Try title first
    title_elem = chart_root.find('.//c:title', NSMAP)
    if title_elem is not None:
        latin = title_elem.find('.//a:latin', NSMAP)
        if latin is not None:
            tf = latin.get('typeface')
            if tf:
                font_family = tf
    # Try axis tick labels
    if not font_family:
        for ax in (cat_ax, val_ax_list[0] if val_ax_list else None):
            if ax is not None:
                latin = ax.find('.//a:latin', NSMAP)
                if latin is not None:
                    tf = latin.get('typeface')
                    if tf:
                        font_family = tf
                        break
    if font_family:
        options['fontFamily'] = font_family

    return element


def _extract_chart_data(chart_elem, scheme_map):
    """Extract series data as row-oriented format + series styles.

    Returns (data_rows, y_field_name, series_styles_dict).
    """
    series_raw = []  # [(name, categories, values, style_dict_or_None)]

    for ser in chart_elem.findall('c:ser', NSMAP):
        # Series name
        name = None
        tx = ser.find('c:tx', NSMAP)
        if tx is not None:
            str_ref = tx.find('c:strRef', NSMAP)
            if str_ref is not None:
                str_cache = str_ref.find('c:strCache', NSMAP)
                if str_cache is not None:
                    pt = str_cache.find('c:pt', NSMAP)
                    if pt is not None:
                        v = pt.find('c:v', NSMAP)
                        if v is not None and v.text:
                            name = v.text

        # Categories
        categories = None
        cat = ser.find('c:cat', NSMAP)
        if cat is not None:
            categories = _extract_chart_values(cat)

        # Values
        values = None
        val = ser.find('c:val', NSMAP)
        if val is None:
            val = ser.find('c:yVal', NSMAP)
        if val is not None:
            values = _extract_chart_values(val)

        # Bubble size (c:bubbleSize or c:zVal)
        bubble_size = None
        bubble_elem = ser.find('c:bubbleSize', NSMAP)
        if bubble_elem is None:
            bubble_elem = ser.find('c:zVal', NSMAP)
        if bubble_elem is not None:
            bubble_size = _extract_chart_values(bubble_elem)

        # Series style (fill + border + line/width + smooth)
        style = None
        sp_pr = ser.find('c:spPr', NSMAP)
        if sp_pr is not None:
            props = parse_ooxml_shape_properties(sp_pr, scheme_map, preserve_scheme=True)
            style = {}
            if 'fill' in props:
                style['fill'] = props['fill']
            if 'border' in props:
                style['border'] = props['border']
                # Extract line style and width from border
                border = props['border']
                if isinstance(border, dict):
                    if 'style' in border:
                        style['line'] = border['style']
                    if 'width' in border:
                        style['width'] = border['width']
        # Smooth (c:smooth element)
        smooth_elem = ser.find('c:smooth', NSMAP)
        if smooth_elem is not None:
            if style is None:
                style = {}
            val = smooth_elem.get('val', '1')
            style['smooth'] = val == '1'

        # Marker (c:marker element)
        marker_elem = ser.find('c:marker', NSMAP)
        if marker_elem is not None:
            if style is None:
                style = {}
            marker_config = {}
            # Symbol (shape)
            symbol = marker_elem.find('c:symbol', NSMAP)
            if symbol is not None:
                val = symbol.get('val', '')
                if val == 'none':
                    style['marker'] = False
                else:
                    shape_map = {
                        'circle': 'circle',
                        'square': 'square',
                        'diamond': 'diamond',
                        'triangle': 'triangle',
                    }
                    if val in shape_map:
                        marker_config['shape'] = shape_map[val]
            # Size
            size = marker_elem.find('c:size', NSMAP)
            if size is not None:
                val = size.get('val')
                if val:
                    try:
                        marker_config['size'] = int(val)
                    except ValueError:
                        pass
            # Fill/border from spPr
            sp_pr = marker_elem.find('c:spPr', NSMAP)
            if sp_pr is not None:
                props = parse_ooxml_shape_properties(sp_pr, scheme_map)
                if 'fill' in props:
                    marker_config['fill'] = props['fill']
                if 'border' in props:
                    marker_config['border'] = props['border']
            if marker_config:
                style['marker'] = marker_config

        # Series-level dataLabels (c:dLbls inside c:ser)
        dLbls = ser.find('c:dLbls', NSMAP)
        if dLbls is not None:
            if style is None:
                style = {}
            series_dl = _extract_chart_data_labels(None, ser, scheme_map)
            if series_dl:
                style['dataLabels'] = series_dl

        if values:
            series_raw.append((name, categories, values, bubble_size, style))

    if not series_raw:
        return [], None, {}

    # Use categories from first series
    categories = series_raw[0][1] or []

    # Build row-oriented data and seriesStyle
    y_field = series_raw[0][0] or '_value'
    data_rows = []
    series_styles = {}

    if len(series_raw) == 1:
        # Single series: one y field
        _, _, values, bubble_size, style = series_raw[0]
        for i, cat_val in enumerate(categories):
            row = {'_category': str(cat_val)}
            row[y_field] = values[i] if i < len(values) else 0
            if bubble_size:
                row['_size'] = bubble_size[i] if i < len(bubble_size) else 0
            data_rows.append(row)
        if style:
            series_styles[y_field] = style
    else:
        # Multiple series: each series becomes a y field
        # Use series name as field name, fallback to _value_N
        field_names = []
        for idx, (name, _, values, bubble_size, style) in enumerate(series_raw):
            fname = name or f'_value_{idx}'
            # Ensure unique field names
            if fname in field_names:
                fname = f'{fname}_{idx}'
            field_names.append(fname)
            if style:
                series_styles[fname] = style

        y_field = field_names
        for i, cat_val in enumerate(categories):
            row = {'_category': str(cat_val)}
            for j, (_, _, values, bubble_size, _) in enumerate(series_raw):
                row[field_names[j]] = values[i] if i < len(values) else 0
                if bubble_size:
                    row[f'{field_names[j]}_size'] = bubble_size[i] if i < len(bubble_size) else 0
            data_rows.append(row)

    # Collect series names for the names array
    names = [name for name, _, _, _, _ in series_raw if name]

    return data_rows, y_field, series_styles, names


def _extract_combo_chart_data(chart_type_elements, scheme_map):
    """Extract data from multiple chart type elements (combo chart).

    Returns (data_rows, y_field_names, series_styles_dict).
    """
    all_series = []  # List of (name, categories, values, bubble_size, style, chart_type)

    # OOXML tag to PPTD type mapping
    oxml_to_pptd = {
        'barChart': 'bar', 'bar3DChart': 'bar',
        'lineChart': 'line', 'line3DChart': 'line',
        'areaChart': 'area', 'area3DChart': 'area',
        'scatterChart': 'scatter',
    }

    for oxml_tag, chart_elem in chart_type_elements:
        pptd_type = oxml_to_pptd.get(oxml_tag, 'bar')

        for ser in chart_elem.findall('c:ser', NSMAP):
            # Series name
            name = None
            tx = ser.find('c:tx', NSMAP)
            if tx is not None:
                str_ref = tx.find('c:strRef', NSMAP)
                if str_ref is not None:
                    str_cache = str_ref.find('c:strCache', NSMAP)
                    if str_cache is not None:
                        pt = str_cache.find('c:pt', NSMAP)
                        if pt is not None:
                            v = pt.find('c:v', NSMAP)
                            if v is not None and v.text:
                                name = v.text

            # Categories
            categories = None
            cat = ser.find('c:cat', NSMAP)
            if cat is not None:
                categories = _extract_chart_values(cat)

            # Values
            values = None
            val = ser.find('c:val', NSMAP)
            if val is None:
                val = ser.find('c:yVal', NSMAP)
            if val is not None:
                values = _extract_chart_values(val)

            # Bubble size
            bubble_size = None
            bubble_elem = ser.find('c:bubbleSize', NSMAP)
            if bubble_elem is None:
                bubble_elem = ser.find('c:zVal', NSMAP)
            if bubble_elem is not None:
                bubble_size = _extract_chart_values(bubble_elem)

            # Series style
            style = None
            sp_pr = ser.find('c:spPr', NSMAP)
            if sp_pr is not None:
                props = parse_ooxml_shape_properties(sp_pr, scheme_map)
                style = {}
                if 'fill' in props:
                    style['fill'] = props['fill']
                if 'border' in props:
                    style['border'] = props['border']
                    border = props['border']
                    if isinstance(border, dict):
                        if 'style' in border:
                            style['line'] = border['style']
                        if 'width' in border:
                            style['width'] = border['width']
                # Add chart type to style for combo charts
                style['type'] = pptd_type

            # Check for secondary axis binding
            # In OOXML, series reference axes via c:axId elements
            # The chart type element (e.g., c:barChart) contains c:axId references
            # We need to check if the series' parent chart type references a secondary axis
            if style is None:
                style = {}
            # Get the axis IDs from the parent chart type element
            ax_id_elems = chart_elem.findall('c:axId', NSMAP)
            if len(ax_id_elems) > 1:
                # Multiple axes - check if this series is on the secondary axis
                # For now, we'll mark all series in the second chart type as secondary
                # A more precise implementation would track axis IDs
                if pptd_type != oxml_to_pptd.get(chart_type_elements[0][0], 'bar'):
                    style['axis'] = 'secondary'
                else:
                    style['axis'] = 'primary'

            # Smooth
            smooth_elem = ser.find('c:smooth', NSMAP)
            if smooth_elem is not None:
                if style is None:
                    style = {}
                val = smooth_elem.get('val', '1')
                style['smooth'] = val == '1'

            # Marker
            marker_elem = ser.find('c:marker', NSMAP)
            if marker_elem is not None:
                if style is None:
                    style = {}
                marker_config = {}
                symbol = marker_elem.find('c:symbol', NSMAP)
                if symbol is not None:
                    val = symbol.get('val', '')
                    if val == 'none':
                        style['marker'] = False
                    else:
                        shape_map = {
                            'circle': 'circle',
                            'square': 'square',
                            'diamond': 'diamond',
                            'triangle': 'triangle',
                        }
                        if val in shape_map:
                            marker_config['shape'] = shape_map[val]
                size = marker_elem.find('c:size', NSMAP)
                if size is not None:
                    val = size.get('val')
                    if val:
                        try:
                            marker_config['size'] = int(val)
                        except ValueError:
                            pass
                sp_pr = marker_elem.find('c:spPr', NSMAP)
                if sp_pr is not None:
                    props = parse_ooxml_shape_properties(sp_pr, scheme_map)
                    if 'fill' in props:
                        marker_config['fill'] = props['fill']
                    if 'border' in props:
                        marker_config['border'] = props['border']
                if marker_config:
                    style['marker'] = marker_config

            # Series-level dataLabels (c:dLbls inside c:ser)
            dLbls = ser.find('c:dLbls', NSMAP)
            if dLbls is not None:
                if style is None:
                    style = {}
                series_dl = _extract_chart_data_labels(None, ser, scheme_map)
                if series_dl:
                    style['dataLabels'] = series_dl

            if values:
                all_series.append((name, categories, values, bubble_size, style))

    if not all_series:
        return [], None, {}, []

    # Use categories from first series
    categories = all_series[0][1] or []

    # Build row-oriented data and seriesStyle
    field_names = []
    series_styles = {}
    names = []

    for idx, (name, _, values, bubble_size, style) in enumerate(all_series):
        fname = name or f'_value_{idx}'
        if fname in field_names:
            fname = f'{fname}_{idx}'
        field_names.append(fname)
        if name:
            names.append(name)
        if style:
            series_styles[fname] = style

    data_rows = []
    for i, cat_val in enumerate(categories):
        row = {'_category': str(cat_val)}
        for j, (_, _, values, bubble_size, _) in enumerate(all_series):
            row[field_names[j]] = values[i] if i < len(values) else 0
            if bubble_size:
                row[f'{field_names[j]}_size'] = bubble_size[i] if i < len(bubble_size) else 0
        data_rows.append(row)

    return data_rows, field_names, series_styles, names


def _extract_dpt_colors(chart_elem, scheme_map):
    """Extract per-data-point colors (c:dPt) as a list of hex strings.

    dPt elements live inside c:ser, not directly under the chart element.
    """
    colors = []
    dpt_list = []
    for ser in chart_elem.findall('c:ser', NSMAP):
        for dpt in ser.findall('c:dPt', NSMAP):
            idx_elem = dpt.find('c:idx', NSMAP)
            if idx_elem is None:
                continue
            idx = int(idx_elem.get('val', '0'))
            sp_pr = dpt.find('c:spPr', NSMAP)
            if sp_pr is None:
                continue
            color = parse_color_with_ref(sp_pr, scheme_map)
            if color:
                dpt_list.append((idx, color))

    # Sort by index and build ordered color list
    dpt_list.sort(key=lambda x: x[0])
    for _, color in dpt_list:
        colors.append(color)

    return colors


def _extract_chart_data_labels(chart_root, chart_elem, scheme_map=None):
    """Extract data label config from c:dLbls (chart-level and chart-element-level)."""
    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP
    # Check chart-element-level first (e.g. c:doughnutChart/c:dLbls),
    # then chart-level (c:chart/c:dLbls)
    dLbls = chart_elem.find('c:dLbls', NSMAP)
    if dLbls is None:
        dLbls = chart_root.find('.//c:chart/c:dLbls', NSMAP)
    if dLbls is None:
        return None

    # Check for delete (labels disabled)
    delete = dLbls.find('c:delete', NSMAP)
    if delete is not None and delete.get('val', '0') == '1':
        return {'show': False}

    result = {}
    show_pct = dLbls.find('c:showPercent', NSMAP)
    show_val = dLbls.find('c:showVal', NSMAP)
    show_cat = dLbls.find('c:showCatName', NSMAP)
    show_ser = dLbls.find('c:showSerName', NSMAP)

    # Determine content type from show flags
    if show_pct is not None and show_pct.get('val', '0') == '1':
        result['content'] = 'percentage'
    elif show_cat is not None and show_cat.get('val', '0') == '1':
        result['content'] = 'category'
    elif show_ser is not None and show_ser.get('val', '0') == '1':
        result['content'] = 'name'
    elif show_val is not None and show_val.get('val', '0') == '1':
        result['content'] = 'value'

    # Number format
    num_fmt = dLbls.find('c:numFmt', NSMAP)
    if num_fmt is not None:
        fmt_code = num_fmt.get('formatCode', '')
        if fmt_code and fmt_code != 'General':
            result['numberFormat'] = fmt_code

    # Font properties (color, fontSize)
    tx_pr = dLbls.find('c:txPr', NSMAP)
    if tx_pr is not None:
        for p in tx_pr.findall('a:p', NSMAP):
            p_pr = p.find('a:pPr', NSMAP)
            if p_pr is not None:
                def_rpr = p_pr.find('a:defRPr', NSMAP)
                if def_rpr is not None:
                    sz = def_rpr.get('sz')
                    if sz:
                        result['fontSize'] = int(sz) / 100  # hundredths of a point to px
                    color = parse_color_with_ref(def_rpr, scheme_map)
                    if color:
                        result['color'] = color
                    break

    if result:
        result.setdefault('show', True)
        return result

    return None


def _extract_chart_legend(chart_root, scheme_map=None):
    """Extract legend config from c:legend."""
    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP
    legend = chart_root.find('.//c:legend', NSMAP)
    if legend is None:
        return None

    # Check for explicit delete
    delete = legend.find('c:delete', NSMAP)
    if delete is not None and delete.get('val', '0') == '1':
        return {'show': False}

    result = {}
    pos = legend.find('c:legendPos', NSMAP)
    if pos is not None:
        pos_map = {'t': 'top', 'b': 'bottom', 'l': 'left', 'r': 'right'}
        val = pos.get('val', '')
        if val in pos_map:
            result['position'] = pos_map[val]

    # Font properties (color, fontSize)
    tx_pr = legend.find('c:txPr', NSMAP)
    if tx_pr is not None:
        for p in tx_pr.findall('a:p', NSMAP):
            p_pr = p.find('a:pPr', NSMAP)
            if p_pr is not None:
                def_rpr = p_pr.find('a:defRPr', NSMAP)
                if def_rpr is not None:
                    sz = def_rpr.get('sz')
                    if sz:
                        result['fontSize'] = int(sz) / 100  # hundredths of a point to px
                    color = parse_color_with_ref(def_rpr, scheme_map)
                    if color:
                        result['color'] = color
                    break

    if result:
        result.setdefault('show', True)
        return result

    return {'show': True}


def _extract_chart_title_text(title_elem):
    """Extract plain text from c:title/c:tx/c:rich or c:tx/c:strRef."""
    tx = title_elem.find('c:tx', NSMAP)
    if tx is None:
        return None
    rich = tx.find('.//c:rich', NSMAP)
    if rich is not None:
        # Extract text from paragraphs
        texts = []
        for r in rich.findall('.//a:r/a:t', NSMAP):
            if r.text:
                texts.append(r.text)
        if texts:
            return ''.join(texts)
    str_ref = tx.find('.//c:strRef/c:strCache/c:pt/c:v', NSMAP)
    if str_ref is not None and str_ref.text:
        return str_ref.text
    return None


def _extract_chart_title_config(title_elem, scheme_map=None):
    """Extract chart title config (text + font properties) from c:title."""
    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP
    title_text = _extract_chart_title_text(title_elem)
    if not title_text:
        return None

    # Check for font properties
    tx = title_elem.find('c:tx', NSMAP)
    if tx is not None:
        rich = tx.find('.//c:rich', NSMAP)
        if rich is not None:
            # Look for font properties in paragraph properties
            for p in rich.findall('a:p', NSMAP):
                p_pr = p.find('a:pPr', NSMAP)
                if p_pr is not None:
                    def_rpr = p_pr.find('a:defRPr', NSMAP)
                    if def_rpr is not None:
                        sz = def_rpr.get('sz')
                        color = parse_color_with_ref(def_rpr, scheme_map)
                        if sz or color:
                            result = {'text': title_text}
                            if sz:
                                result['fontSize'] = int(sz) / 100  # hundredths of a point to px
                            if color:
                                result['color'] = color
                            return result
                    break

    return title_text


# OOXML ST_PresetLineDashVal → PPTD style mapping
# PPTD spec: solid | dash | dot | none
_DASH_MAP = {
    'solid': 'solid', 'dash': 'dash', 'lgDash': 'dash',
    'dot': 'dot', 'lgDashDot': 'dash', 'lgDashDotDot': 'dash',
    'dashDot': 'dash', 'sysDash': 'dash', 'sysDot': 'dot',
    'sysDashDot': 'dash', 'sysDashDotDot': 'dash',
}


def _map_dash_style(ooxml_val):
    """Map OOXML prstDash value to PPTD border/line style."""
    return _DASH_MAP.get(ooxml_val, 'solid')


def _extract_axis_config(axis_elem, scheme_map=None):
    """Extract axis configuration from c:catAx or c:valAx."""
    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP
    result = {}

    # Visibility
    delete = axis_elem.find('c:delete', NSMAP)
    if delete is not None and delete.get('val', '0') == '1':
        result['show'] = False

    # Gridlines
    major_gl = axis_elem.find('c:majorGridlines', NSMAP)
    if major_gl is not None:
        gl_config = True
        # Check for gridline style
        sp_pr = major_gl.find('c:spPr', NSMAP)
        if sp_pr is not None:
            ln = sp_pr.find('a:ln', NSMAP)
            if ln is not None:
                gl_config = {}
                width = ln.get('w')
                if width:
                    gl_config['width'] = int(width) / 12700  # EMU to pt
                prst_dash = ln.find('a:prstDash', NSMAP)
                if prst_dash is not None:
                    gl_config['style'] = _map_dash_style(prst_dash.get('val', 'solid'))
                color = _parse_color_value(ln, scheme_map)
                if color:
                    gl_config['color'] = color
        result['gridLine'] = gl_config

    # Axis line
    sp_pr = axis_elem.find('c:spPr', NSMAP)
    if sp_pr is not None:
        ln = sp_pr.find('a:ln', NSMAP)
        if ln is not None:
            ax_line = {}
            width = ln.get('w')
            if width:
                ax_line['width'] = int(width) / 12700  # EMU to pt
            prst_dash = ln.find('a:prstDash', NSMAP)
            if prst_dash is not None:
                ax_line['style'] = _map_dash_style(prst_dash.get('val', 'solid'))
            color = _parse_color_value(ln, scheme_map)
            if color:
                ax_line['color'] = color
            # Arrows
            head_end = ln.find('a:headEnd', NSMAP)
            tail_end = ln.find('a:tailEnd', NSMAP)
            if head_end is not None or tail_end is not None:
                arrow = [
                    head_end.get('type', 'arrow') if head_end is not None else None,
                    tail_end.get('type', 'arrow') if tail_end is not None else None,
                ]
                ax_line['arrow'] = arrow
            if ax_line:
                result['axisLine'] = ax_line

    # Tick labels
    tx_pr = axis_elem.find('c:txPr', NSMAP)
    if tx_pr is not None:
        label_config = {}
        # Font size
        body_pr = tx_pr.find('a:bodyPr', NSMAP)
        if body_pr is not None:
            pass  # bodyPr doesn't have font size
        # Look for paragraph properties
        for p in tx_pr.findall('a:p', NSMAP):
            p_pr = p.find('a:pPr', NSMAP)
            if p_pr is not None:
                def_rpr = p_pr.find('a:defRPr', NSMAP)
                if def_rpr is not None:
                    sz = def_rpr.get('sz')
                    if sz:
                        label_config['fontSize'] = int(sz) / 100  # hundredths of a point to px
                    color = parse_color_with_ref(def_rpr, scheme_map)
                    if color:
                        label_config['color'] = color
                    break
        if label_config:
            result['label'] = label_config

    # Number format
    num_fmt = axis_elem.find('c:numFmt', NSMAP)
    if num_fmt is not None:
        fmt_code = num_fmt.get('formatCode', '')
        if fmt_code and fmt_code != 'General':
            result['numberFormat'] = fmt_code

    # Min/Max scale
    min_scale = axis_elem.find('c:scaling/c:min', NSMAP)
    max_scale = axis_elem.find('c:scaling/c:max', NSMAP)
    if min_scale is not None:
        val = min_scale.get('val')
        if val is not None:
            try:
                result['min'] = float(val)
            except ValueError:
                pass
    if max_scale is not None:
        val = max_scale.get('val')
        if val is not None:
            try:
                result['max'] = float(val)
            except ValueError:
                pass

    # Title
    title = axis_elem.find('c:title', NSMAP)
    if title is not None:
        title_config = {}
        title_text = _extract_chart_title_text(title)
        if title_text:
            title_config['text'] = title_text
        # Title font properties
        tx_pr = title.find('c:txPr', NSMAP)
        if tx_pr is not None:
            for p in tx_pr.findall('a:p', NSMAP):
                p_pr = p.find('a:pPr', NSMAP)
                if p_pr is not None:
                    def_rpr = p_pr.find('a:defRPr', NSMAP)
                    if def_rpr is not None:
                        sz = def_rpr.get('sz')
                        if sz:
                            title_config['fontSize'] = int(sz) / 100
                        color = parse_color_with_ref(def_rpr, scheme_map)
                        if color:
                            title_config['color'] = color
                        break
        if title_config:
            result['title'] = title_config

    return result


def _extract_chart_values(parent):
    """Extract numeric or string values from c:numRef or c:strRef.

    Handles missing data points (nulls) by respecting the idx attribute.
    Returns a list where position corresponds to the data point index.
    """
    def _parse_pt_list(pt_list, count_elem, parse_numeric=True):
        """Parse c:pt elements respecting idx for null handling."""
        if not pt_list:
            return None
        # Get expected count from ptCount
        count = 0
        if count_elem is not None:
            try:
                count = int(count_elem.get('val', '0'))
            except ValueError:
                count = 0
        if count == 0:
            count = len(pt_list)
        # Initialize with None for all positions
        values = [None] * count
        for pt in pt_list:
            idx = int(pt.get('idx', '0'))
            v = pt.find('c:v', NSMAP)
            if v is not None and v.text:
                if parse_numeric:
                    try:
                        values[idx] = float(v.text)
                    except ValueError:
                        values[idx] = v.text
                else:
                    values[idx] = v.text
        return values if any(v is not None for v in values) else None

    # Numeric reference
    num_ref = parent.find('c:numRef', NSMAP)
    if num_ref is not None:
        num_cache = num_ref.find('c:numCache', NSMAP)
        if num_cache is not None:
            pt_count = num_cache.find('c:ptCount', NSMAP)
            pt_list = num_cache.findall('c:pt', NSMAP)
            result = _parse_pt_list(pt_list, pt_count, parse_numeric=True)
            if result:
                return result

    # String reference
    str_ref = parent.find('c:strRef', NSMAP)
    if str_ref is not None:
        str_cache = str_ref.find('c:strCache', NSMAP)
        if str_cache is not None:
            pt_count = str_cache.find('c:ptCount', NSMAP)
            pt_list = str_cache.findall('c:pt', NSMAP)
            result = _parse_pt_list(pt_list, pt_count, parse_numeric=False)
            if result:
                return result

    # Inline values (numLit / strLit)
    num_lit = parent.find('c:numLit', NSMAP)
    if num_lit is not None:
        pt_count = num_lit.find('c:ptCount', NSMAP)
        pt_list = num_lit.findall('c:pt', NSMAP)
        result = _parse_pt_list(pt_list, pt_count, parse_numeric=True)
        if result:
            return result

    str_lit = parent.find('c:strLit', NSMAP)
    if str_lit is not None:
        pt_count = str_lit.find('c:ptCount', NSMAP)
        pt_list = str_lit.findall('c:pt', NSMAP)
        result = _parse_pt_list(pt_list, pt_count, parse_numeric=False)
        if result:
            return result

    return None


# ---------------------------------------------------------------------------
# Group shape parsing
# ---------------------------------------------------------------------------

def _parse_group_shapes(grp_sp, elements, counter, scheme_map, media_map, slide_rels, z,
                        layout_ph_bounds=None, layout_ph_styles=None, parent_offset=None):
    """Recursively parse p:grpSp and its children."""
    # Extract group fill for grpFill resolution
    grp_sp_pr = grp_sp.find('p:grpSpPr', NSMAP)
    group_fill_elem = None
    if grp_sp_pr is not None:
        for fill_tag in ('a:solidFill', 'a:gradFill', 'a:blipFill', 'a:noFill'):
            f = grp_sp_pr.find(fill_tag, NSMAP)
            if f is not None:
                group_fill_elem = f
                break

    # Group transform: offset + child offset (chOff)
    grp_xfrm = grp_sp.find('p:grpSpPr/a:xfrm', NSMAP)
    grp_off_x = 0
    grp_off_y = 0
    ch_off_x = 0
    ch_off_y = 0
    if grp_xfrm is not None:
        off = grp_xfrm.find('a:off', NSMAP)
        if off is not None:
            grp_off_x = _safe_int(off.get('x'))
            grp_off_y = _safe_int(off.get('y'))
        ch_off = grp_xfrm.find('a:chOff', NSMAP)
        if ch_off is not None:
            ch_off_x = _safe_int(ch_off.get('x'))
            ch_off_y = _safe_int(ch_off.get('y'))

    # Accumulate: parent offset + group position - child offset
    # Children's coords are in child-space; to get slide-space:
    #   slide_pos = parent_offset + grp_off + (child_pos - ch_off)
    # Which simplifies to: (parent_offset + grp_off - ch_off) + child_pos
    base_x = (parent_offset[0] if parent_offset else 0) + grp_off_x - ch_off_x
    base_y = (parent_offset[1] if parent_offset else 0) + grp_off_y - ch_off_y
    offset = (base_x, base_y)

    for child in grp_sp:
        tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
        if tag == 'sp':
            _parse_sp(child, elements, counter, scheme_map, media_map, slide_rels, z,
                      parent_offset=offset,
                      layout_ph_bounds=layout_ph_bounds,
                      layout_ph_styles=layout_ph_styles,
                      group_fill_elem=group_fill_elem)
        elif tag == 'pic':
            _parse_pic(child, elements, counter, media_map, slide_rels,
                       parent_offset=offset, scheme_map=scheme_map)
        elif tag == 'graphicFrame':
            _parse_graphic_frame(child, elements, counter, scheme_map, media_map,
                                 slide_rels, z, parent_offset=offset)
        elif tag == 'grpSp':
            _parse_group_shapes(child, elements, counter, scheme_map, media_map, slide_rels, z,
                                layout_ph_bounds=layout_ph_bounds,
                                layout_ph_styles=layout_ph_styles, parent_offset=offset)
        elif tag == 'cxnSp':
            shape_id = child.get('id', f'cx{counter["next"]()}')
            xfrm = child.find('p:spPr/a:xfrm', NSMAP)
            bounds = _parse_transform(xfrm)
            if bounds:
                bounds[0] += emu_to_px(offset[0])
                bounds[1] += emu_to_px(offset[1])
                elem = _parse_connector(child, shape_id, bounds, scheme_map)
                elements.append(elem)


# ---------------------------------------------------------------------------
# Connector shape parsing
# ---------------------------------------------------------------------------

def _parse_connector(cxns_sp, shape_id, bounds, scheme_map):
    """Parse a p:cxnSp (connector shape) into a PPTD shape element."""
    spPr = cxns_sp.find('p:spPr', NSMAP)
    prst_geom = spPr.find('a:prstGeom', NSMAP) if spPr is not None else None
    shape_name = prst_geom.get('prst', 'straightConnector1') if prst_geom is not None else 'straightConnector1'

    element = {
        'elementId': f'connector_{shape_id}',
        'elementType': 'shape',
        'bounds': bounds,
        'shapeName': shape_name,
    }

    if spPr is not None:
        props = parse_ooxml_shape_properties(spPr, scheme_map)
        element.update(props)

    return element


# ---------------------------------------------------------------------------
# Individual element parsers (with group offset support)
# ---------------------------------------------------------------------------

def _parse_sp(sp, elements, counter, scheme_map, media_map, slide_rels, z, parent_offset=None, layout_ph_bounds=None, layout_ph_styles=None, group_fill_elem=None):
    """Parse a p:sp into elements list."""
    shape_id = sp.get('id', f's{counter["next"]()}')
    nv_sp = sp.find('p:nvSpPr', NSMAP)
    spPr = sp.find('p:spPr', NSMAP)

    # Resolve grpFill: if spPr has a:grpFill, replace with group's fill
    if spPr is not None and group_fill_elem is not None:
        grp_fill = spPr.find('a:grpFill', NSMAP)
        if grp_fill is not None:
            from copy import deepcopy
            idx = list(spPr).index(grp_fill)
            spPr.remove(grp_fill)
            spPr.insert(idx, deepcopy(group_fill_elem))

    xfrm = spPr.find('a:xfrm', NSMAP) if spPr is not None else None
    bounds = _parse_transform(xfrm)
    if bounds is None:
        # For placeholder shapes with no explicit xfrm, inherit bounds from layout
        nv_pr = sp.find('p:nvSpPr/p:nvPr', NSMAP)
        if nv_pr is not None and layout_ph_bounds:
            ph_elem = nv_pr.find('p:ph', NSMAP)
            if ph_elem is not None:
                # idx defaults to 0 per OOXML spec when absent
                ph_idx = ph_elem.get('idx')
                ph_idx_int = int(ph_idx) if ph_idx is not None else 0
                bounds = layout_ph_bounds.get(ph_idx_int)
        if bounds is None:
            return

    # Apply parent offset for group shapes
    if parent_offset:
        bounds[0] += emu_to_px(parent_offset[0])
        bounds[1] += emu_to_px(parent_offset[1])

    # Determine if text element or shape element
    txBody = sp.find('p:txBody', NSMAP)
    has_text = False
    if txBody is not None:
        # Check for non-empty text
        for t_elem in txBody.findall('.//a:t', NSMAP):
            if t_elem.text and t_elem.text.strip():
                has_text = True
                break

    if has_text:
        # Find layout lstStyle for this placeholder (if any)
        layout_lst = None
        if layout_ph_styles:
            nv_pr = sp.find('p:nvSpPr/p:nvPr', NSMAP)
            if nv_pr is not None:
                ph_elem = nv_pr.find('p:ph', NSMAP)
                if ph_elem is not None:
                    ph_idx = ph_elem.get('idx')
                    ph_idx_int = int(ph_idx) if ph_idx is not None else 0
                    layout_lst = layout_ph_styles.get(ph_idx_int)
        elem = _parse_text_element(sp, shape_id, bounds, scheme_map, media_map, slide_rels, layout_lst=layout_lst)
        if elem:
            # Add fill/border/shadow from spPr
            if spPr is not None:
                props = parse_ooxml_shape_properties(spPr, scheme_map)
                for prop_key in ('fill', 'border', 'shadow', 'rotation', 'flip', 'opacity'):
                    if prop_key in props:
                        elem[prop_key] = props[prop_key]
            # Extract placeholder metadata
            nv_pr = sp.find('p:nvSpPr/p:nvPr', NSMAP)
            if nv_pr is not None:
                ph_elem = nv_pr.find('p:ph', NSMAP)
                if ph_elem is not None:
                    ph = {}
                    # idx defaults to 0 per OOXML spec when absent
                    idx = ph_elem.get('idx')
                    ph['idx'] = int(idx) if idx is not None else 0
                    ph_type = ph_elem.get('type')
                    if ph_type:
                        ph['type'] = ph_type
                    elem['placeholder'] = ph
            elements.append(elem)
    else:
        elem = _parse_shape_element(sp, shape_id, bounds, spPr, scheme_map)
        # Extract placeholder metadata for non-text shapes too
        nv_pr = sp.find('p:nvSpPr/p:nvPr', NSMAP)
        if nv_pr is not None:
            ph_elem = nv_pr.find('p:ph', NSMAP)
            if ph_elem is not None:
                ph = {}
                idx = ph_elem.get('idx')
                ph['idx'] = int(idx) if idx is not None else 0
                ph_type = ph_elem.get('type')
                if ph_type:
                    ph['type'] = ph_type
                elem['placeholder'] = ph
        elements.append(elem)


def _parse_pic(pic, elements, counter, media_map, slide_rels, parent_offset=None, scheme_map=None):
    """Parse a p:pic into elements list."""
    shape_id = pic.get('id', f'p{counter["next"]()}')
    spPr = pic.find('p:spPr', NSMAP)
    xfrm = spPr.find('a:xfrm', NSMAP) if spPr is not None else None
    bounds = _parse_transform(xfrm)
    if bounds is None:
        return

    if parent_offset:
        bounds[0] += emu_to_px(parent_offset[0])
        bounds[1] += emu_to_px(parent_offset[1])

    elem = _parse_image_element(pic, shape_id, bounds, media_map, slide_rels)
    # Extract fill/border/shadow/rotation/flip/opacity from spPr
    if spPr is not None and scheme_map is not None:
        props = parse_ooxml_shape_properties(spPr, scheme_map)
        for prop_key in ('fill', 'border', 'shadow', 'rotation', 'flip', 'opacity'):
            if prop_key in props:
                elem[prop_key] = props[prop_key]
    elements.append(elem)


def _parse_graphic_frame(gf, elements, counter, scheme_map, media_map, slide_rels, z,
                         parent_offset=None):
    """Parse a p:graphicFrame (table or chart) into elements list."""
    shape_id = gf.get('id', f'gf{counter["next"]()}')
    xfrm = gf.find('p:xfrm', NSMAP)
    bounds = _parse_transform(xfrm)
    if bounds is None:
        return

    if parent_offset:
        bounds[0] += emu_to_px(parent_offset[0])
        bounds[1] += emu_to_px(parent_offset[1])

    # Determine if table or chart
    graphic_data = gf.find('.//a:graphicData', NSMAP)
    if graphic_data is None:
        return

    uri = graphic_data.get('uri', '')

    if 'table' in uri:
        elem = _parse_table_element(gf, shape_id, bounds, scheme_map)
        if elem:
            # Extract ElementBase properties (rotation, opacity, flip) from graphicFrame
            spPr = gf.find('p:spPr', NSMAP)
            if spPr is not None:
                props = parse_ooxml_shape_properties(spPr, scheme_map)
                for prop_key in ('rotation', 'flip', 'opacity'):
                    if prop_key in props:
                        elem[prop_key] = props[prop_key]
            elements.append(elem)
    elif 'chart' in uri:
        elem = _parse_chart_element(gf, shape_id, bounds, z, slide_rels, scheme_map)
        if elem:
            # Extract ElementBase properties (rotation, opacity, flip) from graphicFrame
            spPr = gf.find('p:spPr', NSMAP)
            if spPr is not None:
                props = parse_ooxml_shape_properties(spPr, scheme_map)
                for prop_key in ('rotation', 'flip', 'opacity'):
                    if prop_key in props:
                        elem[prop_key] = props[prop_key]
            elements.append(elem)


# ---------------------------------------------------------------------------
# Slide parsing
# ---------------------------------------------------------------------------

def _parse_slide(z, slide_file, slide_idx, total_slides, scheme_map, media_map):
    """Parse a single slide into a PPTD page dict."""
    slide_path = f'ppt/{slide_file}'
    slide_xml = _read_zip(z, slide_path)
    if slide_xml is None:
        return None

    try:
        slide_root = ET.fromstring(slide_xml)
    except Exception as e:
        print(f'  Warning: Could not parse slide {slide_idx + 1}: {e}')
        return None

    # Slide relationships for image/chart resolution
    rels_path = f'ppt/slides/_rels/{Path(slide_file).name}.rels'
    slide_rels = _build_rel_map(z, rels_path)

    # Extract slide layout reference
    layout_index = None
    layout_name = None
    layout_root = None
    layout_ph_bounds = {}  # {idx: [x, y, w, h]} from layout placeholders
    layout_ph_styles = {}  # {idx: lstStyle XML element} from layout placeholders
    layout_type = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout'
    for rid, rel in slide_rels.items():
        if rel.get('type', '').endswith('/slideLayout'):
            target = rel.get('target', '')
            # target is like ../slideLayouts/slideLayout2.xml
            import re
            m = re.search(r'slideLayout(\d+)\.xml', target)
            if m:
                layout_index = int(m.group(1)) - 1  # 0-based
            # Try to read layout name and extract placeholder transforms
            try:
                layout_path = f'ppt/slideLayouts/slideLayout{m.group(1)}.xml' if m else None
                if layout_path:
                    layout_xml = _read_zip(z, layout_path)
                    if layout_xml:
                        layout_root = ET.fromstring(layout_xml)
                        # cSld/@name is the layout name
                        csld = layout_root.find('.//p:cSld', NSMAP)
                        if csld is not None:
                            layout_name = csld.get('name')
                        # Extract placeholder bounds and styles from layout spTree
                        layout_sp_tree = layout_root.find('.//p:cSld/p:spTree', NSMAP)
                        if layout_sp_tree is not None:
                            for l_sp in layout_sp_tree.findall('p:sp', NSMAP):
                                l_nv_pr = l_sp.find('p:nvSpPr/p:nvPr', NSMAP)
                                if l_nv_pr is not None:
                                    l_ph = l_nv_pr.find('p:ph', NSMAP)
                                    if l_ph is not None:
                                        # idx defaults to 0 per OOXML spec when absent
                                        l_idx = l_ph.get('idx')
                                        l_idx_int = int(l_idx) if l_idx is not None else 0
                                        l_spPr = l_sp.find('p:spPr', NSMAP)
                                        if l_spPr is not None:
                                            l_xfrm = l_spPr.find('a:xfrm', NSMAP)
                                            l_bounds = _parse_transform(l_xfrm)
                                            if l_bounds is not None:
                                                layout_ph_bounds[l_idx_int] = l_bounds
                                        # Extract lstStyle for font size inheritance
                                        l_tx_body = l_sp.find('p:txBody', NSMAP)
                                        if l_tx_body is not None:
                                            l_lst = l_tx_body.find('a:lstStyle', NSMAP)
                                            if l_lst is not None:
                                                layout_ph_styles[l_idx_int] = l_lst
            except Exception:
                pass
            break

    # Page type heuristic
    page_type = 'content'
    if slide_idx == 0:
        page_type = 'cover'
    elif slide_idx == total_slides - 1:
        page_type = 'final'

    # Build effective clrMap for this slide
    # The clrMap determines how semantic color names (bg1, bg2, tx1, tx2)
    # map to actual scheme colors (dk1, lt1, dk2, lt2).
    # Dark layouts use overrideClrMapping to swap bg↔tx.
    effective_scheme_map = scheme_map  # default: use global scheme_map
    try:
        # Read master's clrMap
        master_clr_map = None
        if layout_root is not None:
            layout_rels_path = f'ppt/slideLayouts/_rels/slideLayout{layout_index + 1}.xml.rels' if layout_index is not None else None
            if layout_rels_path:
                layout_rels = _build_rel_map(z, layout_rels_path)
                for rid, rel in layout_rels.items():
                    if rel.get('type', '').endswith('/slideMaster'):
                        master_target = rel.get('target', '')
                        import re as _re
                        m = _re.search(r'slideMaster(\d+)\.xml', master_target)
                        if m:
                            master_path = f'ppt/slideMasters/slideMaster{m.group(1)}.xml'
                            master_xml = _read_zip(z, master_path)
                            if master_xml:
                                master_root = ET.fromstring(master_xml)
                                master_clr_map_elem = master_root.find('p:clrMap', NSMAP)
                                master_clr_map = build_clr_map(master_clr_map_elem)
                        break

        if master_clr_map is not None:
            # Read layout's clrMapOvr
            layout_clr_map_elem = None
            if layout_root is not None:
                layout_clr_map_elem = layout_root.find('p:clrMapOvr', NSMAP)

            # Read slide's clrMapOvr
            slide_clr_map_elem = slide_root.find('p:clrMapOvr', NSMAP)

            # Build effective clrMap
            clr_map = apply_clr_map_overrides(master_clr_map, layout_clr_map_elem, slide_clr_map_elem)

            # Rebuild scheme_map with the effective clrMap
            # Theme is on the master's rels (layout → master → theme)
            import re as _re
            for rid, rel in layout_rels.items():
                if rel.get('type', '').endswith('/slideMaster'):
                    master_target = rel.get('target', '')
                    mm = _re.search(r'slideMaster(\d+)\.xml', master_target)
                    if mm:
                        master_rels_path = f'ppt/slideMasters/_rels/slideMaster{mm.group(1)}.xml.rels'
                        master_rels = _build_rel_map(z, master_rels_path)
                        for mrid, mrel in master_rels.items():
                            if mrel.get('type', '').endswith('/theme'):
                                theme_target = mrel.get('target', '')
                                tm = _re.search(r'theme(\d+)\.xml', theme_target)
                                if tm:
                                    theme_xml = _read_zip(z, f'ppt/theme/theme{tm.group(1)}.xml')
                                    if theme_xml:
                                        effective_scheme_map = build_scheme_color_map_from_theme_xml(theme_xml, clr_map)
                                break
                    break
    except Exception:
        pass

    # Background (with layout fallback)
    background = _parse_slide_background(slide_root, effective_scheme_map, layout_root=layout_root)

    # Speaker notes
    notes = _parse_notes(z, slide_idx, slide_rels, effective_scheme_map)

    # Parse all elements
    elements = []
    counter = {'_n': 0, 'next': lambda: (counter.update(_n=counter['_n'] + 1), counter['_n'])[1]}

    sp_tree = slide_root.find('.//p:cSld/p:spTree', NSMAP)
    if sp_tree is None:
        sp_tree = slide_root.find('.//p:spTree', NSMAP)

    if sp_tree is not None:
        for child in sp_tree:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag == 'sp':
                _parse_sp(child, elements, counter, effective_scheme_map, media_map, slide_rels, z,
                          layout_ph_bounds=layout_ph_bounds, layout_ph_styles=layout_ph_styles)
            elif tag == 'pic':
                _parse_pic(child, elements, counter, media_map, slide_rels,
                           scheme_map=effective_scheme_map)
            elif tag == 'graphicFrame':
                _parse_graphic_frame(child, elements, counter, effective_scheme_map, media_map,
                                     slide_rels, z)
            elif tag == 'grpSp':
                _parse_group_shapes(child, elements, counter, effective_scheme_map, media_map,
                                    slide_rels, z, layout_ph_bounds=layout_ph_bounds,
                                    layout_ph_styles=layout_ph_styles)
            elif tag == 'cxnSp':
                # Connector shape
                shape_id = child.get('id', f'cx{counter["next"]()}')
                xfrm = child.find('p:spPr/a:xfrm', NSMAP)
                bounds = _parse_transform(xfrm)
                if bounds:
                    elem = _parse_connector(child, shape_id, bounds, effective_scheme_map)
                    elements.append(elem)

    # Resolve image fill rIds using slide relationships
    for elem in elements:
        fill = elem.get('fill', {})
        if isinstance(fill, dict) and fill.get('type') == 'image':
            src = fill.get('src', '')
            if src.startswith('rId'):
                # Resolve rId to actual media path via relationship
                rel = slide_rels.get(src, {})
                target = rel.get('target', '')
                if target:
                    fill['src'] = _resolve_media(target, media_map)

    page_data = {
        'pageType': page_type,
        'elements': elements,
    }
    if layout_index is not None:
        page_data['layoutIndex'] = layout_index
    if layout_name:
        page_data['layoutName'] = layout_name
    if background:
        page_data['background'] = background
    if notes:
        page_data['notes'] = notes

    return page_data


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def convert_pptx_to_pptd(pptx_path, output_dir):
    """Convert a .pptx file to .pptd format."""
    pptx_path = Path(pptx_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    pages_dir = output_dir / 'pages'
    pages_dir.mkdir(exist_ok=True)

    print(f'Converting: {pptx_path}')
    print(f'Output: {output_dir}')

    with zipfile.ZipFile(pptx_path, 'r') as z:
        # Extract media
        print('Extracting media...')
        media_map = _extract_media(z, output_dir)

        # Read presentation.xml
        pres_xml = _read_zip(z, 'ppt/presentation.xml')
        if pres_xml is None:
            raise FileNotFoundError('ppt/presentation.xml not found in PPTX')
        pres_root = ET.fromstring(pres_xml)

        # Slide size
        sld_sz = pres_root.find('.//p:sldSz', NSMAP)
        width_px = emu_to_px(sld_sz.get('cx', '9144000')) if sld_sz is not None else 1280
        height_px = emu_to_px(sld_sz.get('cy', '5143500')) if sld_sz is not None else 720

        # Build slide list from presentation.xml sldId elements
        pres_rels = _build_rel_map(z, 'ppt/_rels/presentation.xml.rels')
        slide_entries = []  # (idx, slide_file)

        sld_idLst = pres_root.find('.//p:sldIdLst', NSMAP)
        if sld_idLst is not None:
            for idx, sldId in enumerate(sld_idLst.findall('p:sldId', NSMAP)):
                rid = _rel_id(sldId, 'id')
                if rid and rid in pres_rels:
                    target = pres_rels[rid]['target']
                    if target.startswith('/'):
                        slide_file = target.lstrip('/')
                    else:
                        slide_file = target  # e.g. 'slides/slide1.xml'
                    slide_entries.append((idx, slide_file))

        if not slide_entries:
            # Fallback: discover slides from zip
            slide_files = sorted([
                n for n in z.namelist()
                if n.startswith('ppt/slides/slide') and n.endswith('.xml')
            ])
            for idx, sf in enumerate(slide_files):
                slide_entries.append((idx, sf.replace('ppt/', '')))

        total_slides = len(slide_entries)

        # Build scheme color map from theme
        theme_xml = _read_zip(z, 'ppt/theme/theme1.xml')
        scheme_map = {}
        if theme_xml:
            scheme_map = build_scheme_color_map_from_theme_xml(theme_xml)

        # Extract theme metadata
        theme = _extract_theme(z, scheme_map)

        # Parse each slide
        page_files = []
        title = None  # Will extract from first slide or metadata

        for slide_idx, slide_file in slide_entries:
            print(f'  Slide {slide_idx + 1}/{total_slides}: {slide_file}')
            page_data = _parse_slide(z, slide_file, slide_idx, total_slides, scheme_map, media_map)
            if page_data is None:
                continue

            # Extract title from first slide's first text element
            if title is None and slide_idx == 0:
                for elem in page_data.get('elements', []):
                    if elem.get('elementType') == 'text':
                        text = elem.get('content', {}).get('text', '')
                        # Strip HTML tags
                        import re
                        plain = re.sub(r'<[^>]+>', '', text).strip()
                        if plain and len(plain) < 200:
                            title = plain
                            break

            page_file = f'slide_{slide_idx + 1:03d}.page'
            page_path = pages_dir / page_file

            with open(page_path, 'w', encoding='utf-8') as f:
                yaml.dump(page_data, f, allow_unicode=True, sort_keys=False, width=float('inf'))

            elem_count = len(page_data.get('elements', []))
            page_files.append(f'pages/{page_file}')
            print(f'    -> {elem_count} elements')

        # Resolve image fill rIds in elements
        _resolve_image_fills(z, pages_dir, media_map)

        # Try to get title from core properties
        if title is None:
            core_xml = _read_zip(z, 'docProps/core.xml')
            if core_xml:
                try:
                    core_root = ET.fromstring(core_xml)
                    dc_title = core_root.find('.//{http://purl.org/dc/elements/1.1/}title')
                    if dc_title is not None and dc_title.text:
                        title = dc_title.text.strip()
                except Exception:
                    pass

        if title is None:
            title = pptx_path.stem

    # Copy original PPTX as template for round-trip fidelity
    import shutil
    template_path = output_dir / 'template.pptx'
    shutil.copy2(str(pptx_path), str(template_path))
    print(f'  Template: {template_path}')

    # Build main .pptd file
    # Read slide size in EMU for exact round-trip
    sld_sz_emu_cx = int(sld_sz.get('cx', '9144000')) if sld_sz is not None else 9144000
    sld_sz_emu_cy = int(sld_sz.get('cy', '5143500')) if sld_sz is not None else 5143500

    pptd_data = {
        'title': title,
        'size': [width_px, height_px],
        'slideWidth': sld_sz_emu_cx,
        'slideHeight': sld_sz_emu_cy,
        'sourceTemplate': 'template.pptx',
        'theme': theme,
        'pages': page_files,
    }

    pptd_file = output_dir / f'{pptx_path.stem}.pptd'
    with open(pptd_file, 'w', encoding='utf-8') as f:
        yaml.dump(pptd_data, f, allow_unicode=True, sort_keys=False, width=float('inf'))

    print(f'\nConversion complete!')
    print(f'  Main file: {pptd_file}')
    print(f'  Slides: {total_slides}')
    print(f'  Size: {width_px}x{height_px}px')

    return pptd_file


def _resolve_image_fills(z, pages_dir, media_map):
    """Second pass: resolve any remaining image fill rIds in exported page files."""
    # Image fills are now resolved during slide parsing using slide_rels.
    # This function handles any edge cases that might have been missed.
    for page_file in sorted(pages_dir.glob('*.page')):
        with open(page_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for unresolved rId references in fill.src
        if "'src': 'rId" not in content:
            continue

        # Re-read as YAML and fix
        page_data = yaml.safe_load(content)
        if not page_data or 'elements' not in page_data:
            continue

        modified = False
        for elem in page_data['elements']:
            fill = elem.get('fill', {})
            if isinstance(fill, dict) and fill.get('type') == 'image':
                src = fill.get('src', '')
                if src.startswith('rId'):
                    # Still unresolved — try to find in media_map
                    # This shouldn't happen if slide parsing resolved correctly
                    fill['src'] = f'/unresolved/{src}'
                    modified = True

        if modified:
            with open(page_file, 'w', encoding='utf-8') as f:
                yaml.dump(page_data, f, allow_unicode=True, sort_keys=False, width=float('inf'))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Convert PPTX to PPTD format')
    parser.add_argument('input', help='Input .pptx file')
    parser.add_argument('-o', '--output', default='.', help='Output directory (default: .)')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f'Error: Input file not found: {args.input}', file=sys.stderr)
        sys.exit(1)

    try:
        convert_pptx_to_pptd(args.input, args.output)
    except Exception as e:
        print(f'Error during conversion: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
