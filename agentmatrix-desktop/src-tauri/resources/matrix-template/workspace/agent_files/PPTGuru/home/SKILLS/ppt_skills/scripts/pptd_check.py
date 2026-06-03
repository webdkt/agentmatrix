#!/usr/bin/env python3
"""
PPTD Checker — validates .pptd files for format errors and layout issues.
Usage: python3 pptd_check.py <pptd_file>
"""

import sys
import re
import math
import unicodedata
from pathlib import Path

from pptd_common import (
    load_yaml, get_valid_shapes, find_icon_svg, find_font, RESOURCE_DIR,
)
from pptd_color import is_valid_hex_color, resolve_theme_ref, resolve_color, contrast_ratio, get_contrast_threshold
from pptd_text import rich_text_to_plain_text, estimate_text_width_px, estimate_text_height_px, estimate_text_overflow


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


class PPTDChecker:
    def __init__(self, pptd_path):
        self.pptd_path = Path(pptd_path).resolve()
        self.base_dir = self.pptd_path.parent
        self.data, self.error = load_yaml(pptd_path)
        self.errors = []
        self.warnings = []
        self.theme = {}
        self.page_size = [1280, 720]
        self.element_ids_per_page = {}
        self.shapes = get_valid_shapes()

    def add_error(self, location, message):
        self.errors.append(f'[ERROR] {location}: {message}')

    def add_warning(self, location, message):
        self.warnings.append(f'[WARNING] {location}: {message}')

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def check_format(self):
        if self.error:
            self.add_error('main file', self.error)
            return False
        if not isinstance(self.data, dict):
            self.add_error('main file', 'Root must be a YAML mapping')
            return False

        # Required fields
        if 'theme' not in self.data:
            self.add_error('main file', 'Missing required field: theme')
        else:
            self.theme = self.data.get('theme', {})
            self._validate_theme()

        if 'size' not in self.data:
            self.add_error('main file', 'Missing required field: size')
        else:
            size = self.data['size']
            if not (isinstance(size, list) and len(size) == 2 and
                    isinstance(size[0], (int, float)) and isinstance(size[1], (int, float))):
                self.add_error('main file', 'size must be [width, height] array of numbers')
            else:
                self.page_size = [float(size[0]), float(size[1])]

        # Optional EMU sizes
        for field in ('slideWidth', 'slideHeight'):
            val = self.data.get(field)
            if val is not None and not isinstance(val, (int, float)):
                self.add_error('main file', f'{field} must be a number (EMU)')

        # Optional source template
        source_template = self.data.get('sourceTemplate')
        if source_template is not None:
            if not isinstance(source_template, str):
                self.add_error('main file', 'sourceTemplate must be a string path')
            else:
                template_path = self.base_dir / source_template
                if not template_path.exists():
                    self.add_warning('main file', f'sourceTemplate not found: {template_path}')

        if 'pages' not in self.data:
            self.add_error('main file', 'Missing required field: pages')
        else:
            pages = self.data['pages']
            if not isinstance(pages, list):
                self.add_error('main file', 'pages must be an array')
            else:
                for i, p in enumerate(pages):
                    if not isinstance(p, str):
                        self.add_error('main file', f'pages[{i}] must be a string path')

        return len(self.errors) == 0

    def _validate_theme(self):
        theme = self.theme
        if not isinstance(theme, dict):
            self.add_error('theme', 'theme must be a mapping')
            return

        colors = theme.get('colors', {})
        if isinstance(colors, dict):
            for key, val in colors.items():
                if isinstance(val, str) and val.startswith('$'):
                    self.add_error(f'theme.colors.{key}', f'Circular theme reference not allowed: {val}')
                elif not is_valid_hex_color(val):
                    self.add_error(f'theme.colors.{key}', f'Invalid color value: {val}')

        text_styles = theme.get('textStyles', {})
        if isinstance(text_styles, dict):
            for key, val in text_styles.items():
                if isinstance(val, dict):
                    color = val.get('color')
                    if color and isinstance(color, str):
                        if color.startswith('$'):
                            _, ok = resolve_theme_ref(color, theme, 'colors')
                            if not ok:
                                self.add_error(f'theme.textStyles.{key}.color', f'Undefined color reference: {color}')
                        elif not is_valid_hex_color(color):
                            self.add_error(f'theme.textStyles.{key}.color', f'Invalid color: {color}')

        table_styles = theme.get('tableStyles', {})
        if isinstance(table_styles, dict):
            for key, val in table_styles.items():
                if isinstance(val, dict):
                    for field in ['headerFill', 'headerColor', 'bodyColor', 'firstColumnFill', 'firstColumnColor']:
                        v = val.get(field)
                        if v and isinstance(v, str):
                            if v.startswith('$'):
                                _, ok = resolve_theme_ref(v, theme, 'colors')
                                if not ok:
                                    self.add_error(f'theme.tableStyles.{key}.{field}', f'Undefined color reference: {v}')
                            elif not is_valid_hex_color(v):
                                self.add_error(f'theme.tableStyles.{key}.{field}', f'Invalid color: {v}')

    def check_pages(self):
        pages = self.data.get('pages', [])
        if not isinstance(pages, list):
            return

        for page_path in pages:
            if not isinstance(page_path, str):
                continue

            full_path = self.base_dir / page_path
            if not full_path.exists():
                self.add_error(f'page: {page_path}', 'File not found')
                continue

            page_data, err = load_yaml(full_path)
            if err:
                self.add_error(f'page: {page_path}', err)
                continue

            if not isinstance(page_data, dict):
                self.add_error(f'page: {page_path}', 'Root must be a YAML mapping')
                continue

            # Validate page type
            page_type = page_data.get('pageType')
            valid_types = {'cover', 'table_of_contents', 'chapter', 'content', 'final'}
            if page_type not in valid_types:
                self.add_error(f'page: {page_path}', f'Invalid pageType: {page_type}. Must be one of {valid_types}')

            # Validate layoutIndex
            layout_idx = page_data.get('layoutIndex')
            if layout_idx is not None and not isinstance(layout_idx, int):
                self.add_error(f'page: {page_path}', 'layoutIndex must be an integer')

            # Validate background
            background = page_data.get('background')
            if background is not None:
                self._validate_fill(background, f'page: {page_path}.background')

            # Validate notes
            notes = page_data.get('notes')
            if notes is not None and not isinstance(notes, str):
                self.add_error(f'page: {page_path}', 'notes must be a string')

            # Check elements
            elements = page_data.get('elements', [])
            if not isinstance(elements, list):
                self.add_error(f'page: {page_path}', 'elements must be an array')
                continue

            self.element_ids_per_page[page_path] = set()

            for i, elem in enumerate(elements):
                if not isinstance(elem, dict):
                    self.add_error(f'page: {page_path}[{i}]', 'Element must be a mapping')
                    continue
                self._validate_element(elem, page_path, i)

            # Check for text occlusions, bounds overflow, and contrast
            self._check_occlusions(page_path, elements)
            self._check_bounds_overflow(page_path, elements)

            # Check text-background contrast
            page_bg = None
            if background and isinstance(background, dict):
                page_bg = resolve_color(background.get('color'), self.theme)
            if not page_bg:
                page_bg = '#FFFFFF'  # Default white background
            self._check_text_contrast(page_path, elements, page_bg)

    # ------------------------------------------------------------------
    # Element validation
    # ------------------------------------------------------------------

    def _validate_element(self, elem, page_path, idx):
        element_id = elem.get('elementId')
        loc = f'page: {page_path} element: {element_id or f"[{idx}]"}'

        if not element_id:
            self.add_error(loc, 'Missing required field: elementId')
        else:
            if element_id in self.element_ids_per_page.get(page_path, set()):
                self.add_error(loc, f'Duplicate elementId: {element_id}')
            else:
                self.element_ids_per_page[page_path].add(element_id)

        element_type = elem.get('elementType')
        valid_types = {'text', 'shape', 'image', 'icon', 'table', 'chart'}
        if element_type not in valid_types:
            self.add_error(loc, f'Invalid elementType: {element_type}')

        bounds = elem.get('bounds')
        if not bounds:
            self.add_error(loc, 'Missing required field: bounds')
        elif not (isinstance(bounds, list) and len(bounds) == 4 and
                  all(isinstance(b, (int, float)) for b in bounds)):
            self.add_error(loc, 'bounds must be [x, y, w, h] array of numbers')
        else:
            x, y, w, h = bounds
            pw, ph = self.page_size
            if x < 0 or y < 0 or x + w > pw + 1 or y + h > ph + 1:
                if x < -5 or y < -5 or x + w > pw + 5 or y + h > ph + 5:
                    self.add_warning(loc, f'Bounds Outside: 元素 [{x}, {y}, {w}, {h}] 明显超出页面范围 [{pw}, {ph}]')
                else:
                    self.add_warning(loc, f'Bounds Outside: 元素 [{x}, {y}, {w}, {h}] 超出页面范围 [{pw}, {ph}]')

        # Validate placeholder metadata
        placeholder = elem.get('placeholder')
        if placeholder is not None:
            if not isinstance(placeholder, dict):
                self.add_error(loc, 'placeholder must be a mapping')
            else:
                ph_idx = placeholder.get('idx')
                if ph_idx is not None and not isinstance(ph_idx, int):
                    self.add_error(loc, 'placeholder.idx must be an integer')
                ph_type = placeholder.get('type')
                valid_ph_types = {
                    'title', 'ctrTitle', 'subTitle', 'obj', 'dt', 'ftr', 'sldNum',
                    'chart', 'tbl', 'clipArt', 'dgm', 'media', 'pic', 'body',
                    'centerTitle', 'subTitle', 'halfObj', 'quarterObj',
                }
                if ph_type is not None and ph_type not in valid_ph_types:
                    self.add_warning(loc, f'Unknown placeholder type: {ph_type}')

        # Element-type specific
        if element_type == 'shape':
            shape_name = elem.get('shapeName')
            if shape_name and shape_name not in self.shapes:
                # Allow custom:... shape names (custom path shapes)
                if not shape_name.startswith('custom:'):
                    self.add_error(loc, f'Invalid shapeName: {shape_name}')
            fill = elem.get('fill')
            if fill:
                self._validate_fill(fill, loc)
        elif element_type == 'text':
            content = elem.get('content')
            if not content:
                self.add_error(loc, 'Missing required field: content')
            elif isinstance(content, dict):
                self._validate_text_content(content, bounds, loc)
        elif element_type == 'image':
            src = elem.get('src')
            if not src:
                self.add_error(loc, 'Missing required field: src')
            elif isinstance(src, str):
                if not (src.startswith('http://') or src.startswith('https://') or
                        src.startswith('/') or src.startswith('data:')):
                    self.add_warning(loc, f'Image src should be absolute path or URL: {src}')
                # Check file existence for local paths
                if src.startswith('/'):
                    if not Path(src).exists():
                        self.add_warning(loc, f'Image file not found: {src}')
            # Validate fit
            fit = elem.get('fit')
            if fit and isinstance(fit, dict):
                mode = fit.get('mode')
                if mode and mode not in ('fill', 'contain', 'cover'):
                    self.add_error(loc, f'Invalid fit.mode: {mode}')
            # Validate crop
            crop = elem.get('crop')
            if crop and isinstance(crop, dict):
                for ck, cv in crop.items():
                    if isinstance(cv, (int, float)) and (cv < 0 or cv > 1):
                        self.add_error(loc, f'crop.{ck} must be 0-1, got {cv}')
        elif element_type == 'icon':
            icon_name = elem.get('iconName')
            if not icon_name:
                self.add_error(loc, 'Missing required field: iconName')
            elif not find_icon_svg(icon_name):
                self.add_warning(loc, f'Icon SVG not found in resource/icons/: {icon_name}')
        elif element_type == 'table':
            self._validate_table(elem, loc)
        elif element_type == 'chart':
            self._validate_chart(elem, loc)

        # Common fields
        opacity = elem.get('opacity')
        if opacity is not None:
            if not isinstance(opacity, (int, float)) or opacity < 0 or opacity > 1:
                self.add_error(loc, f'opacity must be between 0 and 1, got {opacity}')

        rotation = elem.get('rotation')
        if rotation is not None and not isinstance(rotation, (int, float)):
            self.add_error(loc, f'rotation must be a number, got {rotation}')

        flip = elem.get('flip')
        if flip is not None:
            if not (isinstance(flip, list) and len(flip) == 2 and
                    all(isinstance(b, bool) for b in flip)):
                self.add_error(loc, 'flip must be [boolean, boolean]')

        border = elem.get('border')
        if border:
            self._validate_border(border, loc)

        shadow = elem.get('shadow')
        if shadow:
            self._validate_shadow(shadow, loc)

    # ------------------------------------------------------------------
    # Fill / Border / Shadow
    # ------------------------------------------------------------------

    def _validate_fill(self, fill, loc):
        if not isinstance(fill, dict):
            self.add_error(loc, 'fill must be a mapping')
            return
        fill_type = fill.get('type')
        if fill_type not in ('solid', 'gradient', 'image'):
            self.add_error(loc, f'Invalid fill type: {fill_type}')
            return
        if fill_type == 'solid':
            color = fill.get('color')
            if color:
                if isinstance(color, str) and color.startswith('$'):
                    _, ok = resolve_theme_ref(color, self.theme, 'colors')
                    if not ok:
                        self.add_error(loc, f'Undefined color reference: {color}')
                elif not is_valid_hex_color(color):
                    self.add_error(loc, f'Invalid color: {color}')
        elif fill_type == 'gradient':
            stops = fill.get('stops')
            if not isinstance(stops, list):
                self.add_error(loc, 'gradient stops must be an array')
            else:
                for i, stop in enumerate(stops):
                    if not isinstance(stop, dict):
                        continue
                    pos = stop.get('position')
                    if pos is not None and (not isinstance(pos, (int, float)) or pos < 0 or pos > 1):
                        self.add_error(loc, f'Invalid gradient stop position at index {i}: {pos}')
                    color = stop.get('color')
                    if color:
                        if isinstance(color, str) and color.startswith('$'):
                            _, ok = resolve_theme_ref(color, self.theme, 'colors')
                            if not ok:
                                self.add_error(loc, f'Undefined color reference in gradient: {color}')
                        elif not is_valid_hex_color(color):
                            self.add_error(loc, f'Invalid gradient color: {color}')
            gt = fill.get('gradientType')
            if gt and gt not in ('linear', 'radial'):
                self.add_error(loc, f'Invalid gradientType: {gt}')
        elif fill_type == 'image':
            src = fill.get('src')
            if not src:
                self.add_error(loc, 'image fill requires src')

    def _validate_border(self, border, loc):
        if not isinstance(border, dict):
            return
        style = border.get('style')
        if style and style not in ('solid', 'dash', 'dot', 'none'):
            self.add_error(loc, f'Invalid border style: {style}')
        color = border.get('color')
        if color:
            if isinstance(color, str) and color.startswith('$'):
                _, ok = resolve_theme_ref(color, self.theme, 'colors')
                if not ok:
                    self.add_error(loc, f'Undefined border color reference: {color}')
            elif not is_valid_hex_color(color):
                self.add_error(loc, f'Invalid border color: {color}')

    def _validate_shadow(self, shadow, loc):
        if not isinstance(shadow, dict):
            return
        if 'blur' not in shadow:
            self.add_error(loc, 'shadow requires blur')
        color = shadow.get('color')
        if color and not is_valid_hex_color(color):
            self.add_error(loc, f'Invalid shadow color: {color}')
        offset = shadow.get('offset')
        if offset is not None:
            if not (isinstance(offset, list) and len(offset) == 2 and
                    all(isinstance(n, (int, float)) for n in offset)):
                self.add_error(loc, 'shadow.offset must be [number, number]')

    # ------------------------------------------------------------------
    # Text content validation + overflow estimation
    # ------------------------------------------------------------------

    def _validate_text_content(self, content, bounds, loc):
        text = content.get('text', '')
        if not text:
            return

        # Style reference
        style_ref = content.get('style')
        if style_ref and isinstance(style_ref, str) and style_ref.startswith('$'):
            _, ok = resolve_theme_ref(style_ref, self.theme, 'textStyles')
            if not ok:
                self.add_error(loc, f'Undefined text style reference: {style_ref}')

        # Resolve font size
        font_size = content.get('fontSize')
        if font_size is None and style_ref:
            resolved, ok = resolve_theme_ref(style_ref, self.theme, 'textStyles')
            if ok and isinstance(resolved, dict):
                font_size = resolved.get('fontSize')
        if font_size is None:
            font_size = 18

        # Validate textDirection
        td = content.get('textDirection')
        if td and td not in ('horizontal', 'vertical'):
            self.add_error(loc, f'Invalid textDirection: {td}')

        # Validate font availability
        font_family = content.get('fontFamily')
        if font_family:
            result = find_font(font_family)
            if result is None:
                self.add_warning(loc, f'Font not found in resource/fonts/ or system fonts: {font_family}')

        # Validate align
        align = content.get('align')
        if align:
            if isinstance(align, list):
                h_valid = {'left', 'center', 'right', 'justify', 'distributed'}
                v_valid = {'top', 'middle', 'bottom'}
                if len(align) >= 1 and align[0] not in h_valid:
                    self.add_error(loc, f'Invalid horizontal align: {align[0]}')
                if len(align) >= 2 and align[1] not in v_valid:
                    self.add_error(loc, f'Invalid vertical align: {align[1]}')

        # Validate text gradient/shadow
        if content.get('gradient'):
            self._validate_fill(content['gradient'], f'{loc}.gradient')
        if content.get('shadow'):
            self._validate_shadow(content['shadow'], f'{loc}.shadow')

        # Text overflow estimation (segment-aware)
        if bounds and len(bounds) == 4:
            box_w, box_h = bounds[2], bounds[3]
            if not text or not text.strip():
                return

            wrap = content.get('wrap', True)
            line_height = content.get('lineHeight', 1.3)

            # Get vertical alignment
            align = content.get('align', [])
            v_align = align[1] if isinstance(align, list) and len(align) >= 2 else 'top'

            # Use new overflow estimation with proper pt→px and padding
            result = estimate_text_overflow(
                text, box_w, box_h,
                font_size_pt=font_size,
                line_height=line_height,
                v_align=v_align
            )

            n_lines = result['num_lines']
            overflow_px = result['overflow_px']
            overflow_dir = result['overflow_direction']
            content_h = result['content_height_px']
            lines_that_fit = result['lines_that_fit']

            if wrap:
                if overflow_px > 0:
                    overflow_lines = n_lines - lines_that_fit
                    dir_cn = '下' if overflow_dir == 'down' else '上'
                    self.add_warning(
                        loc,
                        f'Text Overflow: 内容过多过大，只能容纳{lines_that_fit}行，已向{dir_cn}超出{overflow_lines}行（约{overflow_px:.0f}px）'
                    )
                elif n_lines > 0 and content_h < box_h * 0.3 and n_lines > 1:
                    self.add_warning(loc, f'Text Underfill: 内容过少，仅占容器{(content_h/box_h)*100:.0f}%')

    # ------------------------------------------------------------------
    # Table validation
    # ------------------------------------------------------------------

    def _validate_table(self, elem, loc):
        col_widths = elem.get('columnWidths')
        if not col_widths:
            self.add_error(loc, 'Missing required field: columnWidths')
        elif isinstance(col_widths, list):
            total = sum(col_widths)
            if abs(total - 1.0) > 0.01:
                self.add_error(loc, f'columnWidths must sum to 1.0, got {total}')
            for i, w in enumerate(col_widths):
                if w < 0 or w > 1:
                    self.add_error(loc, f'columnWidths[{i}] out of range [0,1]: {w}')

        row_heights = elem.get('rowHeights')
        if not row_heights:
            self.add_error(loc, 'Missing required field: rowHeights')
        elif isinstance(row_heights, list):
            total = sum(row_heights)
            if abs(total - 1.0) > 0.01:
                self.add_error(loc, f'rowHeights must sum to 1.0, got {total}')
            for i, h in enumerate(row_heights):
                if h < 0 or h > 1:
                    self.add_error(loc, f'rowHeights[{i}] out of range [0,1]: {h}')

        rows = elem.get('rows')
        if not rows:
            self.add_error(loc, 'Missing required field: rows')
        elif isinstance(rows, list):
            expected_cols = len(col_widths) if isinstance(col_widths, list) else 0
            for i, row in enumerate(rows):
                if not isinstance(row, list):
                    self.add_error(loc, f'rows[{i}] must be an array')
                else:
                    actual_cols = sum(
                        (cell.get('colSpan', 1) if isinstance(cell, dict) else 1)
                        for cell in row
                    )
                    if expected_cols > 0 and actual_cols != expected_cols:
                        self.add_error(loc, f'rows[{i}] has {actual_cols} columns, expected {expected_cols}')

                    # Validate merged cells don't exceed bounds
                    if isinstance(row, list):
                        for j, cell in enumerate(row):
                            if isinstance(cell, dict):
                                rs = cell.get('rowSpan', 1)
                                cs = cell.get('colSpan', 1)
                                if rs < 1 or cs < 1:
                                    self.add_error(loc, f'rows[{i}][{j}]: rowSpan/colSpan must be >= 1')
                                if isinstance(row_heights, list) and i + rs > len(row_heights):
                                    self.add_error(loc, f'rows[{i}][{j}]: rowSpan {rs} exceeds table rows')

        style = elem.get('style')
        if style and isinstance(style, str) and style.startswith('$'):
            _, ok = resolve_theme_ref(style, self.theme, 'tableStyles')
            if not ok:
                self.add_error(loc, f'Undefined table style reference: {style}')

    # ------------------------------------------------------------------
    # Chart validation
    # ------------------------------------------------------------------

    def _validate_chart(self, elem, loc):
        chart_type = elem.get('type')
        valid_types = {'bar', 'line', 'area', 'scatter', 'pie', 'radar', 'combo', 'bubble'}
        if chart_type not in valid_types:
            self.add_error(loc, f'Invalid chart type: {chart_type}')

        data = elem.get('data')
        if not data:
            self.add_error(loc, 'Missing required field: data')
        elif not isinstance(data, list):
            self.add_error(loc, 'data must be an array')
        elif len(data) == 0:
            self.add_error(loc, 'data array must not be empty')
        else:
            for i, record in enumerate(data):
                if not isinstance(record, dict):
                    self.add_error(loc, f'data[{i}] must be a mapping')

        x_field = elem.get('x')
        if not x_field:
            self.add_error(loc, 'Missing required field: x')
        elif data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            if x_field not in data[0]:
                self.add_warning(loc, f"x field '{x_field}' not found in first data record")

        y_fields = elem.get('y')
        if not y_fields:
            self.add_error(loc, 'Missing required field: y')
        else:
            if isinstance(y_fields, str):
                y_fields = [y_fields]
            if isinstance(y_fields, list):
                for yf in y_fields:
                    if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                        if yf not in data[0]:
                            self.add_warning(loc, f"y field '{yf}' not found in first data record")

        colors = elem.get('colors')
        if colors and isinstance(colors, list):
            for i, c in enumerate(colors):
                if isinstance(c, str) and c.startswith('$'):
                    _, ok = resolve_theme_ref(c, self.theme, 'colors')
                    if not ok:
                        self.add_error(loc, f'Undefined color reference in colors[{i}]: {c}')
                elif not is_valid_hex_color(c):
                    self.add_error(loc, f'Invalid color in colors[{i}]: {c}')

        options = elem.get('options')
        if options and isinstance(options, dict):
            inner_radius = options.get('innerRadius')
            if inner_radius is not None and (not isinstance(inner_radius, (int, float)) or inner_radius < 0 or inner_radius > 1):
                self.add_error(loc, f'options.innerRadius must be in [0,1]: {inner_radius}')

        # Validate seriesStyle keys
        series_style = elem.get('seriesStyle')
        if series_style and isinstance(series_style, dict):
            y_list = y_fields if isinstance(y_fields, list) else ([y_fields] if isinstance(y_fields, str) else [])
            for key in series_style:
                if key != '*' and key not in y_list:
                    self.add_warning(loc, f"seriesStyle key '{key}' does not match any y field")

    # ------------------------------------------------------------------
    # Occlusion detection
    # ------------------------------------------------------------------

    def _get_text_font_size(self, elem):
        """Resolve effective font size for a text element."""
        content = elem.get('content', {})
        fs = content.get('fontSize')
        if fs is not None:
            return fs
        style_ref = content.get('style')
        if style_ref and isinstance(style_ref, str) and style_ref.startswith('$'):
            resolved, ok = resolve_theme_ref(style_ref, self.theme, 'textStyles')
            if ok and isinstance(resolved, dict):
                fs = resolved.get('fontSize')
                if fs is not None:
                    return fs
        return 18

    def _get_text_overflow_info(self, elem):
        """Get overflow info for a text element using proper pt→px conversion."""
        bounds = elem.get('bounds')
        if not bounds or len(bounds) != 4:
            return None
        x, y, w, h = bounds
        content = elem.get('content', {})
        text = content.get('text', '')
        if not text or not text.strip():
            return {'bounds': bounds, 'overflow_px': 0, 'overflow_direction': None}

        font_size = self._get_text_font_size(elem)
        line_height = content.get('lineHeight', 1.3)

        # Get vertical alignment
        align = content.get('align', [])
        v_align = align[1] if isinstance(align, list) and len(align) >= 2 else 'top'

        result = estimate_text_overflow(
            text, w, h,
            font_size_pt=font_size,
            line_height=line_height,
            v_align=v_align
        )

        # Calculate actual content bounds including overflow
        overflow_px = result['overflow_px']
        overflow_dir = result['overflow_direction']

        if overflow_dir == 'down':
            # Content extends below the box
            content_bounds = [x, y, w, h + overflow_px]
        elif overflow_dir == 'up':
            # Content extends above the box
            content_bounds = [x, y - overflow_px, w, h + overflow_px]
        else:
            content_bounds = bounds

        return {
            'bounds': content_bounds,
            'overflow_px': overflow_px,
            'overflow_direction': overflow_dir,
            'num_lines': result['num_lines'],
            'lines_that_fit': result['lines_that_fit'],
        }

    def _check_occlusions(self, page_path, elements):
        # Collect text elements and shape elements with valid bounds
        text_elems = []
        shape_elems = []
        for idx, elem in enumerate(elements):
            if not isinstance(elem, dict):
                continue
            bounds = elem.get('bounds')
            if not bounds or len(bounds) != 4:
                continue
            if elem.get('elementType') == 'text':
                text_elems.append((idx, bounds, elem))
            elif elem.get('elementType') == 'shape':
                shape_elems.append((idx, bounds, elem))

        # Check text-vs-text overlap
        for i, (idx_a, bounds_a, elem_a) in enumerate(text_elems):
            info_a = self._get_text_overflow_info(elem_a)
            if not info_a:
                continue
            ax, ay, aw, ah = info_a['bounds']

            for j in range(i + 1, len(text_elems)):
                idx_b, bounds_b, elem_b = text_elems[j]
                info_b = self._get_text_overflow_info(elem_b)
                if not info_b:
                    continue
                bx, by, bw, bh = info_b['bounds']

                # AABB intersection
                if ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by:
                    occluded_id = elem_a.get('elementId', 'unknown')
                    occluder_id = elem_b.get('elementId', 'unknown')

                    # Add overflow context
                    overflow_info = ''
                    if info_a['overflow_px'] > 0:
                        overflow_info += f" (overflows {info_a['overflow_px']:.0f}px {info_a['overflow_direction']})"
                    if info_b['overflow_px'] > 0:
                        overflow_info += f" ('{occluder_id}' overflows {info_b['overflow_px']:.0f}px {info_b['overflow_direction']})"

                    self.add_warning(
                        f'page: {page_path} element: {occluded_id}',
                        f"Text Overlap: '{occluded_id}' 与 '{occluder_id}' 文字重叠{overflow_info}"
                    )

        # Check shape-vs-text occlusion (shape on top of text)
        for shape_idx, shape_bounds, shape_elem in shape_elems:
            sx, sy, sw, sh = shape_bounds

            # Check if shape has visible fill
            fill = shape_elem.get('fill', {})
            if not isinstance(fill, dict):
                continue
            fill_type = fill.get('type', 'solid')
            if fill_type not in ('solid', 'gradient'):
                continue

            # Check opacity
            opacity = shape_elem.get('opacity', 1.0)
            if opacity < 0.3:
                continue

            for text_idx, text_bounds, text_elem in text_elems:
                # Only report if shape is on top of text (higher z-order)
                if shape_idx <= text_idx:
                    continue

                tx, ty, tw, th = text_bounds

                # AABB intersection
                if sx < tx + tw and sx + sw > tx and sy < ty + th and sy + sh > ty:
                    shape_id = shape_elem.get('elementId', 'unknown')
                    text_id = text_elem.get('elementId', 'unknown')
                    fill_color = resolve_color(fill.get('color'), self.theme) if fill.get('color') else 'unknown'
                    self.add_warning(
                        f'page: {page_path} element: {text_id}',
                        f"Shape Occlusion: '{text_id}' 被形状 '{shape_id}' 遮挡（填充={fill_color}）"
                    )

    def _get_text_color(self, elem):
        """Resolve the text color for a text element."""
        content = elem.get('content', {})
        # Check inline color
        color = content.get('color')
        if color:
            return resolve_color(color, self.theme)
        # Check style reference
        style_ref = content.get('style')
        if style_ref and isinstance(style_ref, str) and style_ref.startswith('$'):
            resolved, ok = resolve_theme_ref(style_ref, self.theme, 'textStyles')
            if ok and isinstance(resolved, dict):
                color = resolved.get('color')
                if color:
                    return resolve_color(color, self.theme)
        return None

    def _get_element_fill_color(self, elem):
        """Get the fill color of an element."""
        fill = elem.get('fill')
        if not fill or not isinstance(fill, dict):
            return None
        fill_type = fill.get('type', 'solid')
        if fill_type != 'solid':
            return None  # Skip gradients/images for now
        color = fill.get('color')
        return resolve_color(color, self.theme)

    def _get_actual_background_color(self, text_elem, elements, page_background):
        """Determine the actual visual background color of a text element.

        Looks at elements behind the text (lower z-order) and finds
        the first one with a solid fill. Falls back to page background.
        """
        text_idx = elements.index(text_elem) if text_elem in elements else -1
        if text_idx < 0:
            return page_background

        text_bounds = text_elem.get('bounds', [0, 0, 0, 0])
        tx, ty, tw, th = text_bounds

        # Look at elements behind this one (lower z-index)
        for i in range(text_idx - 1, -1, -1):
            elem = elements[i]
            if not isinstance(elem, dict):
                continue
            bounds = elem.get('bounds')
            if not bounds or len(bounds) != 4:
                continue
            ex, ey, ew, eh = bounds

            # Check if this element overlaps with the text element
            if tx < ex + ew and tx + tw > ex and ty < ey + eh and ty + th > ey:
                # Check if this element has a fill
                fill_color = self._get_element_fill_color(elem)
                if fill_color:
                    return fill_color

        return page_background

    def _check_text_contrast(self, page_path, elements, page_background):
        """Check text-background contrast ratio for all text elements."""
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            if elem.get('elementType') != 'text':
                continue

            text_color = self._get_text_color(elem)
            if not text_color:
                continue

            bg_color = self._get_actual_background_color(elem, elements, page_background)
            if not bg_color:
                continue

            ratio = contrast_ratio(text_color, bg_color)
            if ratio is None:
                continue

            font_size = self._get_text_font_size(elem)
            content = elem.get('content', {})
            # Check if bold from style
            style_ref = content.get('style')
            bold = False
            if style_ref and isinstance(style_ref, str) and style_ref.startswith('$'):
                resolved, ok = resolve_theme_ref(style_ref, self.theme, 'textStyles')
                if ok and isinstance(resolved, dict):
                    bold = resolved.get('bold', False)

            threshold = get_contrast_threshold(font_size, bold)

            if ratio < threshold:
                elem_id = elem.get('elementId', 'unknown')
                self.add_warning(
                    f'page: {page_path} element: {elem_id}',
                    f"Low Contrast: 文字颜色 {text_color} 背景 {bg_color}，对比度 {ratio:.1f}:1（{font_size}pt文字最低要求 {threshold}:1）"
                )

    def _check_bounds_overflow(self, page_path, elements):
        """Check if element bounds extend beyond page size."""
        pw, ph = self.page_size
        for elem in elements:
            if not isinstance(elem, dict):
                continue
            bounds = elem.get('bounds')
            if not bounds or len(bounds) != 4:
                continue
            x, y, w, h = bounds
            elem_id = elem.get('elementId', 'unknown')

            # Check right edge
            if x + w > pw + 1:
                self.add_warning(
                    f'page: {page_path} element: {elem_id}',
                    f"BoundsOverflowWarning: Element extends beyond page right edge (x+w={x+w:.0f} > page width {pw})"
                )
            # Check bottom edge
            if y + h > ph + 1:
                self.add_warning(
                    f'page: {page_path} element: {elem_id}',
                    f"BoundsOverflowWarning: Element extends beyond page bottom edge (y+h={y+h:.0f} > page height {ph})"
                )
            # Check left edge
            if x < -1:
                self.add_warning(
                    f'page: {page_path} element: {elem_id}',
                    f"BoundsOverflowWarning: Element extends beyond page left edge (x={x:.0f} < 0)"
                )
            # Check top edge
            if y < -1:
                self.add_warning(
                    f'page: {page_path} element: {elem_id}',
                    f"BoundsOverflowWarning: Element extends beyond page top edge (y={y:.0f} < 0)"
                )

    # ------------------------------------------------------------------
    # Run all checks
    # ------------------------------------------------------------------

    def run(self):
        print(f'{Colors.HEADER}{Colors.BOLD}Checking: {self.pptd_path}{Colors.ENDC}')
        print(f'{Colors.OKBLUE}Base directory: {self.base_dir}{Colors.ENDC}\n')

        if not self.pptd_path.exists():
            print(f'{Colors.FAIL}File not found: {self.pptd_path}{Colors.ENDC}')
            sys.exit(1)

        ok = self.check_format()
        if ok:
            self.check_pages()

        # Results
        print(f'{Colors.BOLD}=== Results ==={Colors.ENDC}\n')

        if self.errors:
            print(f'{Colors.FAIL}{Colors.BOLD}Errors ({len(self.errors)}):{Colors.ENDC}')
            for err in self.errors:
                print(f'  {Colors.FAIL}{err}{Colors.ENDC}')
            print()

        if self.warnings:
            print(f'{Colors.WARNING}{Colors.BOLD}Warnings ({len(self.warnings)}):{Colors.ENDC}')
            for warn in self.warnings:
                print(f'  {Colors.WARNING}{warn}{Colors.ENDC}')
            print()

        if self.errors:
            print(f'{Colors.FAIL}{Colors.BOLD}Summary: {len(self.errors)} errors, {len(self.warnings)} warnings{Colors.ENDC}')
            print(f'{Colors.FAIL}Please fix all errors before proceeding.{Colors.ENDC}')
            sys.exit(1)
        elif self.warnings:
            print(f'{Colors.WARNING}{Colors.BOLD}Summary: 0 errors, {len(self.warnings)} warnings{Colors.ENDC}')
            print(f'{Colors.WARNING}Please review and fix warnings unless they are intentional design choices.{Colors.ENDC}')
            sys.exit(0)
        else:
            print(f'{Colors.OKGREEN}{Colors.BOLD}Summary: 0 errors, 0 warnings{Colors.ENDC}')
            print(f'{Colors.OKGREEN}All checks passed!{Colors.ENDC}')
            sys.exit(0)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} <pptd_file>')
        sys.exit(1)
    checker = PPTDChecker(sys.argv[1])
    checker.run()
