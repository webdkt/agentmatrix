#!/usr/bin/env python3
"""
PPTD Text — rich text parsing, OOXML text content extraction, text measurement.
"""

import re
import math
import html
import unicodedata
from html.parser import HTMLParser

from pptd_common import NSMAP, find_font
from pptd_color import SCHEME_COLOR_MAP, _parse_color_value

# PIL font measurement (optional, for accurate text width)
_PIL_AVAILABLE = False
try:
    from PIL import ImageFont
    _PIL_AVAILABLE = True
except ImportError:
    pass

_font_cache = {}  # (font_path, size) → PIL Font object


_DEFAULT_FONT_PATHS = [
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/Library/Fonts/Arial Unicode.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
]


def _load_font(font_family, size_px, bold=False):
    """Load a PIL font for measurement. Returns Font or None."""
    if not _PIL_AVAILABLE:
        return None

    path = None
    if font_family:
        # Try bold variant first if bold
        if bold:
            result = find_font(f'{font_family} Bold')
            if not result:
                result = find_font(font_family)
        else:
            result = find_font(font_family)
        if result:
            path = result['path']

    # Fallback to default system font
    if not path:
        for dp in _DEFAULT_FONT_PATHS:
            import os
            if os.path.exists(dp):
                path = dp
                break
    if not path:
        return None

    key = (path, round(size_px, 1), bold)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(path, round(size_px))
        except Exception:
            return None
    return _font_cache[key]


# ---------------------------------------------------------------------------
# Rich text HTML parsing (PPTD → segments, for export)
# ---------------------------------------------------------------------------

class RichTextParser(HTMLParser):
    """Parse PPTD rich text HTML into a list of text segments with formatting."""

    def __init__(self, base_style=None):
        super().__init__()
        self.segments = []
        self.current_text = ''
        self.style_stack = [base_style or {}]
        self.in_p = False
        self.p_style = {}
        self.list_stack = []
        self._next_is_new_para = False

    def get_current_style(self):
        merged = {}
        for s in self.style_stack:
            merged.update(s)
        return merged

    def flush_segment(self):
        if self.current_text:
            # Skip whitespace-only segments outside list context
            # This prevents whitespace between </p> and <ul> from creating
            # a paragraph that steals bullet formatting from the first list item
            if not self.current_text.strip() and not self.list_stack and self._next_is_new_para:
                self.current_text = ''
                return

            style = self.get_current_style()
            p_copy = dict(self.p_style)
            p_copy.update(style)
            list_info = None
            if self.list_stack:
                # Extract tags and level from stack (each entry is (tag, level_str))
                list_info = {
                    'tags': [entry[0] for entry in self.list_stack],
                    'level': self.list_stack[-1][1],  # level from innermost list
                }
            self.segments.append({
                'text': self.current_text,
                'style': p_copy,
                'is_new_para': self._next_is_new_para,
                'list_type': list_info['tags'] if list_info else None,
                'list_level': list_info['level'] if list_info else None,
            })
            self.current_text = ''
            self._next_is_new_para = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'p':
            self.flush_segment()
            self.in_p = True
            self.p_style = {}
            style_str = attrs_dict.get('style', '')
            if style_str:
                for prop in style_str.split(';'):
                    prop = prop.strip()
                    if ':' in prop:
                        k, v = prop.split(':', 1)
                        k, v = k.strip(), v.strip()
                        if k == 'text-align':
                            self.p_style['align'] = v
                        elif k == 'line-height':
                            try:
                                self.p_style['line_height'] = float(v.replace('px', ''))
                            except ValueError:
                                pass
                        elif k == 'margin-top':
                            try:
                                val = v.replace('px', '').replace('pt', '')
                                self.p_style['margin_top'] = int(val)
                            except ValueError:
                                pass
                        elif k == 'margin-bottom':
                            try:
                                val = v.replace('px', '').replace('pt', '')
                                self.p_style['margin_bottom'] = int(val)
                            except ValueError:
                                pass
                        elif k == 'padding-left':
                            try:
                                val = v.replace('px', '').replace('pt', '')
                                self.p_style['padding_left'] = int(val)
                            except ValueError:
                                pass
                        elif k == 'text-indent':
                            try:
                                val = v.replace('px', '').replace('pt', '')
                                self.p_style['text_indent'] = int(val)
                            except ValueError:
                                pass
                        elif k == 'letter-spacing':
                            try:
                                self.p_style['letter_spacing'] = int(v.replace('px', ''))
                            except ValueError:
                                pass

        elif tag == 'span':
            self.flush_segment()
            span_style = {}
            style_str = attrs_dict.get('style', '')
            if style_str:
                for prop in style_str.split(';'):
                    prop = prop.strip()
                    if ':' in prop:
                        k, v = prop.split(':', 1)
                        k, v = k.strip(), v.strip()
                        if k == 'color':
                            span_style['color'] = v
                        elif k == 'font-size':
                            try:
                                span_style['font_size'] = int(v.replace('px', ''))
                            except ValueError:
                                pass
                        elif k == 'font-family':
                            span_style['font_family'] = v.strip('"').strip("'")
                        elif k == 'background-color':
                            span_style['bg_color'] = v
                        elif k == 'font-style':
                            span_style['italic'] = (v == 'italic')
            self.style_stack.append(span_style)

        elif tag == 'strong':
            self.flush_segment()
            self.style_stack.append({'bold': True})
        elif tag == 'em':
            self.flush_segment()
            self.style_stack.append({'italic': True})
        elif tag == 'u':
            self.flush_segment()
            self.style_stack.append({'underline': True})
        elif tag == 's':
            self.flush_segment()
            self.style_stack.append({'strikethrough': True})
        elif tag == 'sup':
            self.flush_segment()
            self.style_stack.append({'superscript': True})
        elif tag == 'sub':
            self.flush_segment()
            self.style_stack.append({'subscript': True})
        elif tag == 'a':
            self.flush_segment()
            self.style_stack.append({'hyperlink': attrs_dict.get('href', '')})
        elif tag in ('ul', 'ol'):
            self.flush_segment()
            level = attrs_dict.get('data-level', '')
            self.list_stack.append((tag, level))
        elif tag == 'li':
            self.flush_segment()
        elif tag == 'br':
            self.current_text += '\n'

    def handle_endtag(self, tag):
        if tag in ('span', 'strong', 'em', 'u', 's', 'sup', 'sub', 'a'):
            self.flush_segment()
            if len(self.style_stack) > 1:
                self.style_stack.pop()
        elif tag == 'p':
            self.flush_segment()
            self.in_p = False
            self.p_style = {}
            self._next_is_new_para = True
        elif tag in ('ul', 'ol'):
            self.flush_segment()
            if self.list_stack:
                self.list_stack.pop()
        elif tag == 'li':
            self.flush_segment()
            self._next_is_new_para = True

    def handle_data(self, data):
        self.current_text += data

    def close(self):
        super().close()
        self.flush_segment()


def unescape_html(text):
    if not isinstance(text, str):
        return str(text) if text is not None else ''
    return html.unescape(text)


def parse_rich_text(html_text, base_style=None):
    """Parse rich text HTML into segments list."""
    if not isinstance(html_text, str):
        return [{'text': str(html_text), 'style': dict(base_style) if base_style else {}}] if html_text else []
    if not html_text:
        return []
    html_text = html_text.rstrip()
    if not html_text:
        return []
    html_text = unescape_html(html_text)
    # Strip newlines between HTML tags (YAML formatting noise, not content)
    html_text = re.sub(r'>\s*\n\s*<', '> <', html_text)
    if not html_text.strip().startswith('<'):
        html_text = f'<p>{html_text}</p>'
    parser = RichTextParser(base_style)
    try:
        parser.feed(html_text)
        parser.close()
    except Exception:
        return [{'text': html_text, 'style': base_style or {}, 'is_new_para': True, 'list_type': None}]
    return parser.segments


def rich_text_to_plain_text(html_text):
    """Strip all HTML tags and return plain text."""
    if not html_text:
        return ''
    return re.sub(r'<[^>]+>', '', unescape_html(html_text)).strip()


# ---------------------------------------------------------------------------
# Text dimension estimation (for check.py overflow/underfill)
# ---------------------------------------------------------------------------

def estimate_text_width_px(plain_text, font_size):
    """Estimate text width with CJK awareness. Returns px."""
    width = 0.0
    for ch in plain_text:
        ea = unicodedata.east_asian_width(ch)
        if ea in ('F', 'W'):
            width += font_size  # Full-width (CJK, fullwidth symbols)
        else:
            width += font_size * 0.55  # Half-width (Latin, digits)
    return width


def estimate_text_height_px(plain_text, font_size, line_height=1.3, box_width=None, wrap=True):
    """Estimate wrapped text height. Returns (height_px, num_lines)."""
    effective_lh = font_size * max(line_height, 1.3)

    if not wrap or box_width is None:
        # Single line
        num_lines = max(1, plain_text.count('\n') + 1)
        return num_lines * effective_lh, num_lines

    # Wrapped text
    paragraphs = plain_text.split('\n')
    total_lines = 0
    for para in paragraphs:
        if not para.strip():
            total_lines += 1
            continue
        para_width = estimate_text_width_px(para, font_size)
        lines = max(1, math.ceil(para_width / box_width))
        total_lines += lines

    return total_lines * effective_lh, total_lines


# ---------------------------------------------------------------------------
# Text size estimation for checker overflow detection
# Uses proper pt→px conversion and PowerPoint default padding
# ---------------------------------------------------------------------------

# pt → px conversion (standard screen DPI 96)
_PT_TO_PX = 96.0 / 72.0  # ≈ 1.333

# PowerPoint default text box padding (in px at 96 DPI)
# Left/Right: 0.1 inch = 96px × 0.1 = 9.6px ≈ 10px
# Top/Bottom: 0.05 inch = 96px × 0.05 = 4.8px ≈ 5px
_PADDING_LR = 10  # left and right padding
_PADDING_TB = 5   # top and bottom padding

# Character width ratios (relative to font_size_px)
_CJK_RATIO = 1.0      # CJK characters are typically square
_LATIN_RATIO = 0.55   # Average Latin character width
_BOLD_MULTIPLIER = 1.07
_LIST_INDENT_PX = 20  # per nesting level


def _char_width_px(ch, font_size_px, bold=False):
    """Estimate single character width in px (after pt→px conversion)."""
    ea = unicodedata.east_asian_width(ch)
    if ea in ('F', 'W'):
        # Fullwidth/Wide (CJK characters and punctuation)
        w = font_size_px * _CJK_RATIO
    elif ch == ' ':
        w = font_size_px * 0.28
    else:
        # Latin, digits, punctuation - use average
        w = font_size_px * _LATIN_RATIO
    if bold:
        w *= _BOLD_MULTIPLIER
    return w


def _text_width_px(text, font_size_px, bold=False, letter_spacing=0):
    """Estimate total width of text in px."""
    if not text:
        return 0.0
    w = sum(_char_width_px(ch, font_size_px, bold) for ch in text)
    if letter_spacing and len(text) > 1:
        w += letter_spacing * (len(text) - 1)
    return w


def estimate_text_overflow(html_text, box_width, box_height,
                           font_size_pt=18, line_height=1.3, v_align='top'):
    """Estimate text overflow for a text box.

    Args:
        html_text: HTML text content
        box_width: Text box width in px
        box_height: Text box height in px
        font_size_pt: Font size in points (not px)
        line_height: Line height multiplier (e.g., 1.6)
        v_align: Vertical alignment ('top', 'middle', 'bottom')

    Returns:
        dict with:
            num_lines: total number of text lines
            content_height_px: total content height in px
            overflow_px: overflow amount in px (0 if no overflow)
            overflow_direction: 'down', 'up', or None
            lines_that_fit: how many lines fit in the box
    """
    if not html_text or not html_text.strip():
        return {
            'num_lines': 0,
            'content_height_px': 0,
            'overflow_px': 0,
            'overflow_direction': None,
            'lines_that_fit': 0,
        }

    segments = parse_rich_text(html_text)
    if not segments:
        return {
            'num_lines': 0,
            'content_height_px': 0,
            'overflow_px': 0,
            'overflow_direction': None,
            'lines_that_fit': 0,
        }

    # Convert font size from pt to px
    font_size_px = font_size_pt * _PT_TO_PX

    # Calculate effective area (accounting for padding)
    eff_w = max(10, box_width - _PADDING_LR * 2)
    eff_h = max(10, box_height - _PADDING_TB * 2)

    # Calculate line height in px
    line_height_px = font_size_px * line_height

    # Group segments into paragraphs
    paragraphs = []
    current_para = []
    for seg in segments:
        if seg.get('is_new_para') and current_para:
            paragraphs.append(current_para)
            current_para = []
        current_para.append(seg)
    if current_para:
        paragraphs.append(current_para)

    # Count total characters and calculate lines
    total_lines = 0
    max_chars_per_line = max(1, int(eff_w / (font_size_px * _CJK_RATIO)))

    for para_segments in paragraphs:
        # Get paragraph-level indent
        first = para_segments[0]
        list_level = first.get('list_level')
        indent_px = 0
        if list_level:
            try:
                indent_px = int(list_level) * _LIST_INDENT_PX
            except (ValueError, TypeError):
                indent_px = _LIST_INDENT_PX

        # Available width for this paragraph
        para_eff_w = max(10, eff_w - indent_px)

        # Collect all characters in this paragraph with their widths
        para_chars = []
        for seg in para_segments:
            text = seg.get('text', '')
            style = seg.get('style', {})
            fs_pt = style.get('font_size', font_size_pt)
            fs_px = fs_pt * _PT_TO_PX
            bold = style.get('bold', False)
            ls = style.get('letter_spacing', 0)
            ff = style.get('font_family')

            # Try PIL for accurate per-character widths
            pil_font = _load_font(ff, fs_px, bold)

            # Split on \n within segment
            parts = text.split('\n')
            for pi, part in enumerate(parts):
                if pi > 0:
                    # Forced line break - count current line and start new
                    if para_chars:
                        total_lines += 1
                        para_chars = []

                if not part:
                    continue

                if pil_font:
                    # PIL: accurate per-character width
                    for ch in part:
                        w = pil_font.getlength(ch)
                        if ls:
                            w += ls
                        para_chars.append(w)
                else:
                    # Fallback: ratio-based estimation
                    for ch in part:
                        w = _char_width_px(ch, fs_px, bold)
                        if ls:
                            w += ls
                        para_chars.append(w)

        # Wrap remaining characters
        if para_chars:
            current_w = 0.0
            line_count = 0
            for w in para_chars:
                if current_w > 0 and current_w + w > para_eff_w:
                    line_count += 1
                    current_w = w
                else:
                    current_w += w
            if current_w > 0:
                line_count += 1
            total_lines += line_count

    # Minimum 1 line if there's any text
    if total_lines == 0 and html_text.strip():
        total_lines = 1

    # Calculate content height
    content_height_px = total_lines * line_height_px

    # Calculate how many lines fit in the box
    lines_that_fit = max(1, int(eff_h / line_height_px))

    # Calculate overflow
    overflow_lines = total_lines - lines_that_fit
    overflow_px = max(0, overflow_lines * line_height_px)

    # Determine overflow direction
    overflow_direction = None
    if overflow_px > 0:
        if v_align == 'bottom':
            overflow_direction = 'up'
        else:
            overflow_direction = 'down'

    return {
        'num_lines': total_lines,
        'content_height_px': content_height_px,
        'overflow_px': overflow_px,
        'overflow_direction': overflow_direction,
        'lines_that_fit': lines_that_fit,
    }


# ---------------------------------------------------------------------------
# OOXML text content parsing (PPTX XML → PPTD rich text, for convert)
# ---------------------------------------------------------------------------

def _escape_xml_text(text):
    """Escape special chars for embedding in PPTD rich text."""
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _escape_xml_attr(text):
    """Escape for use inside an HTML attribute value."""
    if not text:
        return ''
    return text.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def parse_ooxml_text_content(text_body, scheme_map=None):
    """Parse an OOXML a:txBody element into PPTD rich text format.

    This is the inverse of parse_rich_text — it reads OOXML XML and produces
    PPTD HTML-like rich text.
    """
    import xml.etree.ElementTree as ET

    if text_body is None:
        return ''

    if scheme_map is None:
        scheme_map = SCHEME_COLOR_MAP

    # Extract lstStyle from txBody for level-based inheritance (bullets, fonts)
    lst_style = text_body.find('a:lstStyle', NSMAP)

    # Build level→style map from lstStyle (for inherited font sizes & bullets)
    # Keys are int level (0-8), values are dicts with 'sz', 'bu_char', etc.
    lst_level_styles = {}
    if lst_style is not None:
        for lvl_tag in ('a:lvl1pPr', 'a:lvl2pPr', 'a:lvl3pPr', 'a:lvl4pPr',
                        'a:lvl5pPr', 'a:lvl6pPr', 'a:lvl7pPr', 'a:lvl8pPr', 'a:lvl9pPr'):
            lvl_elem = lst_style.find(lvl_tag, NSMAP)
            if lvl_elem is not None:
                lvl_num = int(lvl_tag.split('lvl')[1][0]) - 1  # 0-based
                lvl_info = {}

                def_rpr = lvl_elem.find('a:defRPr', NSMAP)
                if def_rpr is not None:
                    sz = def_rpr.get('sz')
                    if sz:
                        lvl_info['sz'] = int(sz)

                    # Bullet definitions at this level
                    bu_none = def_rpr.find('a:buNone', NSMAP)
                    bu_char = def_rpr.find('a:buChar', NSMAP)
                    bu_auto = def_rpr.find('a:buAutoNum', NSMAP)
                    if bu_none is not None:
                        lvl_info['bu_none'] = True
                    elif bu_char is not None:
                        char = bu_char.get('char', '')
                        bu_font = def_rpr.find('a:buFont', NSMAP)
                        lvl_info['bu_char'] = char
                        if bu_font is not None:
                            lvl_info['bu_font'] = bu_font.get('typeface', '')
                    elif bu_auto is not None:
                        lvl_info['bu_auto'] = bu_auto.get('type', 'arabicPeriod')

                lst_level_styles[lvl_num] = lvl_info

    paragraphs = text_body.findall('.//a:p', NSMAP)
    if not paragraphs:
        return ''

    result_lines = []
    for para in paragraphs:
        # Paragraph properties
        pPr = para.find('a:pPr', NSMAP)
        p_style_parts = []

        # Read level from pPr (0-based, default 0)
        para_level = 0
        if pPr is not None:
            lvl_attr = pPr.get('lvl')
            if lvl_attr is not None:
                try:
                    para_level = int(lvl_attr)
                except ValueError:
                    pass

        if pPr is not None:
            align = pPr.get('algn')
            align_map = {'ctr': 'center', 'r': 'right', 'l': 'left', 'just': 'justify', 'dist': 'distributed'}
            if align in align_map:
                p_style_parts.append(f'text-align:{align_map[align]}')

            # Line height
            lnSpc = pPr.find('a:lnSpc', NSMAP)
            if lnSpc is not None:
                spcPct = lnSpc.find('a:spcPct', NSMAP)
                spcPts = lnSpc.find('a:spcPts', NSMAP)
                if spcPct is not None:
                    pct = int(spcPct.get('val', 100000)) / 100000
                    p_style_parts.append(f'line-height:{pct}')
                elif spcPts is not None:
                    pts = int(spcPts.get('val', 0)) / 100
                    p_style_parts.append(f'line-height:{pts}px')

            # Paragraph spacing (margin-top from spcBef)
            spcBef = pPr.find('a:spcBef', NSMAP)
            if spcBef is not None:
                spcPts = spcBef.find('a:spcPts', NSMAP)
                if spcPts is not None:
                    pts = int(spcPts.get('val', 0)) / 100
                    if pts > 0:
                        p_style_parts.append(f'margin-top:{int(pts)}px')

            # Paragraph spacing after (margin-bottom from spcAft)
            spcAft = pPr.find('a:spcAft', NSMAP)
            if spcAft is not None:
                spcPts = spcAft.find('a:spcPts', NSMAP)
                if spcPts is not None:
                    pts = int(spcPts.get('val', 0)) / 100
                    if pts > 0:
                        p_style_parts.append(f'margin-bottom:{int(pts)}px')

            # Indentation (marL → padding-left, indent → text-indent)
            indent = pPr.find('a:indent', NSMAP)
            if indent is not None:
                mar_l = indent.get('marL')
                if mar_l and int(mar_l) > 0:
                    pts = round(int(mar_l) / 12700)
                    p_style_parts.append(f'padding-left:{pts}pt')
                first_line = indent.get('firstLine')
                if first_line and int(first_line) > 0:
                    pts = round(int(first_line) / 12700)
                    p_style_parts.append(f'text-indent:{pts}pt')

        # Resolve bullet: inline pPr → lstStyle level definition → default for lvl > 0
        is_list = False
        list_tag = None
        if pPr is not None:
            buNone = pPr.find('a:buNone', NSMAP)
            buChar = pPr.find('a:buChar', NSMAP)
            buAutoNum = pPr.find('a:buAutoNum', NSMAP)
            if buNone is not None:
                is_list = False
                list_tag = None
            elif buChar is not None:
                is_list = True
                list_tag = 'ul'
            elif buAutoNum is not None:
                is_list = True
                list_tag = 'ol'

        # If no inline bullet definition, check lstStyle level definition
        if not is_list and para_level > 0 and pPr is not None:
            bu_none_inline = pPr.find('a:buNone', NSMAP)
            if bu_none_inline is None:
                lvl_info = lst_level_styles.get(para_level, {})
                if lvl_info.get('bu_none'):
                    pass  # Explicitly no bullet at this level
                elif 'bu_char' in lvl_info:
                    is_list = True
                    list_tag = 'ul'
                elif 'bu_auto' in lvl_info:
                    is_list = True
                    list_tag = 'ol'
                else:
                    # No explicit definition — apply OOXML default bullet
                    is_list = True
                    list_tag = 'ul'

        # Parse runs and line breaks in document order
        para_text = ''
        for child in para:
            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if child_tag == 'br':
                para_text += '<br>'
                continue
            if child_tag != 'r':
                continue
            run = child
            t = run.find('a:t', NSMAP)
            if t is None or not t.text:
                continue
            text = _escape_xml_text(t.text)

            rPr = run.find('a:rPr', NSMAP)
            if rPr is not None:
                span_style_parts = []

                # Font size — inherit from lstStyle defRPr if no explicit sz
                sz = rPr.get('sz')
                if sz:
                    span_style_parts.append(f'font-size:{int(int(sz) / 100)}px')
                elif para_level in lst_level_styles:
                    inherited_sz = lst_level_styles[para_level].get('sz')
                    if inherited_sz:
                        span_style_parts.append(f'font-size:{int(inherited_sz / 100)}px')

                # Color
                solid_fill = rPr.find('a:solidFill', NSMAP)
                if solid_fill is not None:
                    color = _parse_color_value(solid_fill, scheme_map)
                    if color:
                        span_style_parts.append(f'color:{color}')

                # Background color (highlight) — support srgbClr, schemeClr, sysClr
                highlight = rPr.find('a:highlight', NSMAP)
                if highlight is not None:
                    color = _parse_color_value(highlight, scheme_map)
                    if color:
                        span_style_parts.append(f'background-color:{color}')

                # Font family — filter out OOXML theme tokens (start with '+')
                latin = rPr.find('a:latin', NSMAP)
                ea = rPr.find('a:ea', NSMAP)
                fonts = []
                if latin is not None:
                    tf = latin.get('typeface', '')
                    if tf and not tf.startswith('+'):
                        fonts.append(tf)
                if ea is not None:
                    tf = ea.get('typeface', '')
                    if tf and not tf.startswith('+') and tf not in fonts:
                        fonts.append(tf)
                if fonts:
                    span_style_parts.append(f'font-family:{", ".join(fonts)}')

                # Letter spacing (a:rPr/@spc, in 1/100 of a point)
                spc = rPr.get('spc')
                if spc:
                    try:
                        pts = round(int(spc) / 100, 1)
                        if pts != 0:
                            span_style_parts.append(f'letter-spacing:{pts}px')
                    except ValueError:
                        pass

                # Apply inline styles
                if span_style_parts:
                    text = f'<span style="{"; ".join(span_style_parts)}">{text}</span>'

                # Bold
                if rPr.get('b') == '1':
                    text = f'<strong>{text}</strong>'
                # Italic
                if rPr.get('i') == '1':
                    text = f'<em>{text}</em>'
                # Underline
                if rPr.get('u') and rPr.get('u') != 'none':
                    text = f'<u>{text}</u>'
                # Strikethrough
                if rPr.get('strike') and rPr.get('strike') != 'noStrike':
                    text = f'<s>{text}</s>'
                # Superscript / Subscript
                baseline = rPr.get('baseline')
                if baseline:
                    try:
                        baseline_val = int(baseline)
                        if baseline_val > 0:
                            text = f'<sup>{text}</sup>'
                        elif baseline_val < 0:
                            text = f'<sub>{text}</sub>'
                    except ValueError:
                        pass

            # Hyperlink
            hlink = run.find('.//a:hlinkClick', NSMAP)
            if hlink is not None:
                href = hlink.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link', '')
                if href:
                    text = f'<a href="{_escape_xml_attr(href)}">{text}</a>'

            para_text += text

        # Check endParaRPr for default paragraph-end formatting
        endParaRPr = para.find('a:endParaRPr', NSMAP)
        if endParaRPr is not None and not para_text:
            pass

        # Wrap in <p> tag
        style_attr = ''
        if p_style_parts:
            style_attr = f' style="{"; ".join(p_style_parts)}"'

        if is_list and list_tag:
            level_attr = f' data-level="{para_level}"' if para_level > 0 else ''
            result_lines.append(f'<{list_tag}{level_attr}><li{style_attr}>{para_text}</li></{list_tag}>')
        else:
            result_lines.append(f'<p{style_attr}>{para_text}</p>')

    return _merge_list_blocks(result_lines)


def _merge_list_blocks(lines):
    """Merge consecutive <ul>...</ul> or <ol>...</ol> blocks into single blocks.

    Only merges blocks with the same tag type (ul/ol) AND same data-level.
    """
    import re
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match list blocks with optional attributes like data-level
        m = re.match(r'^(<ul(?:\s[^>]*)?>|<ol(?:\s[^>]*)?>)(<li(?:\s[^>]*)?>.*</li>)(</ul>|</ol>)$', line)
        if m:
            open_tag = m.group(1)  # <ul> or <ol> (possibly with attributes)
            li_content = m.group(2)
            close_tag = m.group(3)  # </ul> or </ol>
            # Extract base tag name and data-level for matching
            base_tag = 'ul' if open_tag.startswith('<ul') else 'ol'
            level_m = re.search(r'data-level="(\d+)"', open_tag)
            data_level = level_m.group(1) if level_m else None
            items = [li_content]
            # Collect consecutive blocks with the same list type AND same level
            j = i + 1
            while j < len(lines):
                m2 = re.match(r'^(<ul(?:\s[^>]*)?>|<ol(?:\s[^>]*)?>)(<li(?:\s[^>]*)?>.*</li>)(</ul>|</ol>)$', lines[j])
                if m2:
                    base2 = 'ul' if m2.group(1).startswith('<ul') else 'ol'
                    level2_m = re.search(r'data-level="(\d+)"', m2.group(1))
                    data_level2 = level2_m.group(1) if level2_m else None
                    if base2 == base_tag and data_level2 == data_level:
                        items.append(m2.group(2))
                        j += 1
                        continue
                break
            if len(items) > 1:
                merged.append(open_tag + ''.join(items) + close_tag)
            else:
                merged.append(line)
            i = j
        else:
            merged.append(line)
            i += 1
    return '\n'.join(merged)
