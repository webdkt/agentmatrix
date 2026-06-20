"""Text-run extraction. 对应 render/text-runs.ts。

从 SlideNode 树里把可合并的 inline 文本节点拍平成带格式的 TextRun 列表。
同时报告被吸收掉的节点集合（让外层 render-node 跳过它们）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from ..parse.color import parse_color, opacity_to_transparency
from ..parse.css import (
    extract_px,
    is_bold,
    parse_shadow,
    underline_style,
    normalize_text,
)
from ..parse.fonts import resolve_font_family
from ..parse.units import clamp, px_to_points
from ..types import Rect, SlideNode
from .media_cache import image_key


@dataclass
class TextFormat:
    color: str = '000000'
    transparency: int = 0
    bold: bool = False
    italic: bool = False
    underline: Optional[Dict] = None     # {style, color?}
    strike: Optional[bool] = None
    fontFace: str = 'Arial'
    fontSize: Optional[float] = None
    subscript: Optional[bool] = None
    superscript: Optional[bool] = None
    highlight: Optional[str] = None


@dataclass
class TextRun:
    text: str
    fmt: TextFormat
    rect: Optional[Rect] = None
    href: Optional[str] = None


def text_format(style: Dict[str, str], swap_map: Optional[Dict[str, str]] = None) -> TextFormat:
    color = parse_color(style.get('color')) or _BlackOpaqueColor
    deco = f"{style.get('textDecorationLine') or ''} {style.get('textDecoration') or ''}"
    deco_color = parse_color(style.get('textDecorationColor'))
    underline_color = deco_color.hex if deco_color and deco_color.hex != color.hex else None
    font_size_px = extract_px(style.get('fontSize'))
    return TextFormat(
        color=color.hex,
        transparency=opacity_to_transparency(color.alpha),
        bold=is_bold(style.get('fontWeight')),
        italic=(style.get('fontStyle') == 'italic' or (style.get('fontStyle') or '').startswith('oblique')),
        underline=(
            {'style': underline_style(style.get('textDecorationStyle')), 'color': underline_color}
            if 'underline' in deco else None
        ),
        strike=True if 'line-through' in deco else None,
        fontFace=resolve_font_family(style.get('fontFamily'), swap_map),
        fontSize=clamp(px_to_points(font_size_px), 1, 400) if font_size_px > 0 else None,
    )


_BlackOpaqueColor = type('_PC', (), {'hex': '000000', 'alpha': 1.0})()


def _capitalize_unicode(s: str) -> str:
    """CSS `text-transform: capitalize` — uppercase first letter of each word.

    Equivalent to TS regex `(^|[^\\p{L}\\p{N}'\\u2019])(\\p{L})`. Python's `re`
    can't cleanly express `\\p{L}` boundaries, so do it char-by-char using
    Unicode-aware `str.isalpha()` / `str.isalnum()` (matches TS semantics).
    Word-internal letters/digits/apostrophes/U+2019 are non-boundaries.
    """
    out = []
    cap_next = True
    for ch in s:
        if cap_next and ch.isalpha():
            ch = ch.upper()
        out.append(ch)
        cap_next = not (ch.isalnum() or ch in "'\u2019")
    return ''.join(out)


def text_transform_fn(value):
    """text-transform → a function applied to run text."""
    if value == 'uppercase':
        return lambda s: s.upper()
    if value == 'lowercase':
        return lambda s: s.lower()
    if value == 'capitalize':
        return _capitalize_unicode
    return lambda s: s


INLINE_MERGE_KEYS = ('textTransform', 'letterSpacing')


def _is_run_mergeable(node: SlideNode, parent_style: Dict[str, str]) -> bool:
    if node.tag == '#text':
        return True
    s = node.style
    display = s.get('display') or ''
    if (
        (display not in ('inline', 'inline-block', 'inline-flex', 'contents'))
        or s.get('visibility') == 'hidden'
        or (s.get('opacity') and s.get('opacity') != '1')
    ):
        return False
    valign = s.get('verticalAlign') or 'baseline'
    if (
        valign not in ('baseline', 'sub', 'super', '0px', '0')
        or image_key(node)
        or (
            parse_color(s.get('backgroundColor'))
            and (
                extract_px(s.get('paddingTop'))
                + extract_px(s.get('paddingRight'))
                + extract_px(s.get('paddingBottom'))
                + extract_px(s.get('paddingLeft'))
                > 0
            )
        )
        or extract_px(s.get('borderTopWidth') or s.get('borderWidth')) > 0
        or extract_px(s.get('borderBottomWidth')) > 0
        or extract_px(s.get('borderLeftWidth')) > 0
        or extract_px(s.get('borderRightWidth')) > 0
        or parse_shadow(s.get('boxShadow'))
        or parse_shadow(s.get('textShadow'))
    ):
        return False
    for k in INLINE_MERGE_KEYS:
        if (s.get(k) or '') != (parent_style.get(k) or ''):
            return False
    return True


def valign_from_box(style: Dict[str, str]) -> str:
    """Vertical alignment inferred from flex/table-cell."""
    if style.get('display') in ('flex', 'inline-flex'):
        if (style.get('flexDirection') or '').startswith('column'):
            v = style.get('justifyContent')
        else:
            v = style.get('alignItems')
        if v == 'center':
            return 'middle'
        if v in ('flex-end', 'end'):
            return 'bottom'
    if style.get('display') == 'table-cell':
        if style.get('verticalAlign') == 'middle':
            return 'middle'
        if style.get('verticalAlign') == 'bottom':
            return 'bottom'
    return 'top'


def align_from_flex(style: Dict[str, str]):
    if style.get('display') not in ('flex', 'inline-flex'):
        return None
    if (style.get('flexDirection') or '').startswith('column'):
        a = style.get('alignItems')
    else:
        a = style.get('justifyContent')
    if a == 'center':
        return 'center'
    if a in ('flex-end', 'end'):
        return 'right'
    return None


_HTTP_HREF_RE = re.compile(r'^https?://', re.I)


def http_href(href):
    return href if (href and _HTTP_HREF_RE.match(href)) else None


def runs_adjacent(a: TextRun, b: TextRun) -> bool:
    if not a.rect or not b.rect:
        return False
    gap = b.rect.x - (a.rect.x + a.rect.w)
    return -1 <= gap < 2


def runs_on_different_lines(a: TextRun, b: TextRun) -> bool:
    """True if run b 视觉上在 run a 的下一行（不同 Y）。

    用于识别 HTML 里的 <br> / block 分行：capture 会把 <br> 两侧的文本
    拆成不同 #text 节点（不同 rect.y），合并它们会导致 PowerPoint 把
    本该分行的文字塞进一段、按 textbox 宽度 word-wrap，行数和原 HTML 对不上。

    阈值取 max(a.h * 0.3, 4px)：超过这条线就认为是新行，而不是行内 float 噪声。
    """
    if not a.rect or not b.rect:
        return False
    return (b.rect.y - a.rect.y) > max(a.rect.h * 0.3, 4)


def _formats_equal(a: TextFormat, b: TextFormat) -> bool:
    return (
        a.color == b.color
        and a.transparency == b.transparency
        and a.bold == b.bold
        and a.italic == b.italic
        and a.fontFace == b.fontFace
        and a.fontSize == b.fontSize
        and bool(a.underline) == bool(b.underline)
        and (a.underline or {}).get('style') == (b.underline or {}).get('style')
        and (a.underline or {}).get('color') == (b.underline or {}).get('color')
        and bool(a.strike) == bool(b.strike)
        and bool(a.subscript) == bool(b.subscript)
        and bool(a.superscript) == bool(b.superscript)
        and a.highlight == b.highlight
    )


@dataclass
class _InheritedCtx:
    href: Optional[str] = None
    baseline: Optional[str] = None  # "sub" | "super"
    underline: Optional[Dict] = None
    strike: Optional[bool] = None
    highlight: Optional[str] = None


def extract_text_runs(
    node: SlideNode,
    swap_map: Optional[Dict[str, str]] = None,
) -> Tuple[List[TextRun], Set[int]]:
    """Recursive inline walk → formatted runs + ids() of consumed descendants."""
    consumed: Set[int] = set()
    collected: List[TextRun] = []

    own_text = normalize_text(node.text, node.style.get('whiteSpace')) if node.text else ''
    if own_text:
        collected.append(TextRun(text=own_text, fmt=text_format(node.style, swap_map), rect=node.rect))

    def all_mergeable(n: SlideNode) -> bool:
        if not _is_run_mergeable(n, node.style):
            return False
        return all(all_mergeable(c) for c in n.children)

    def absorb(n: SlideNode, inherited: Optional[_InheritedCtx] = None):
        consumed.add(id(n))
        if n.tag != '#text' and (n.style.get('visibility') == 'hidden' or n.style.get('opacity') == '0'):
            return
        href = http_href(n.href) or (inherited.href if inherited else None)
        fmt = text_format(n.style, swap_map)
        valign = n.style.get('verticalAlign')
        if inherited and inherited.baseline:
            baseline = inherited.baseline
        elif valign == 'sub':
            baseline = 'sub'
        elif valign == 'super':
            baseline = 'super'
        else:
            baseline = None
        if baseline == 'sub':
            fmt.subscript = True
        elif baseline == 'super':
            fmt.superscript = True
        if not fmt.underline and inherited and inherited.underline:
            fmt.underline = inherited.underline
        if not fmt.strike and inherited and inherited.strike:
            fmt.strike = True
        bg = parse_color(n.style.get('backgroundColor'))
        highlight = bg.hex if bg else (inherited.highlight if inherited else None)
        if highlight:
            fmt.highlight = highlight
        text = normalize_text(n.text, n.style.get('whiteSpace')) if n.text else ''
        if text:
            collected.append(TextRun(text=text, fmt=fmt, rect=n.rect, href=href))
        for child in n.children:
            absorb(child, _InheritedCtx(
                href=href,
                baseline=baseline,
                underline=fmt.underline,
                strike=fmt.strike,
                highlight=highlight,
            ))

    if node.children:
        has_direct_text = any(c.tag == '#text' for c in node.children)

        def has_media(n: SlideNode) -> bool:
            if image_key(n):
                return True
            return any(has_media(c) for c in n.children)

        def all_inline_no_media(c: SlideNode) -> bool:
            if c.tag == '#text':
                return True
            if has_media(c):
                return False
            display = c.style.get('display') or ''
            return display in ('inline', 'inline-block', 'inline-flex', 'contents')

        if (
            all(all_mergeable(c) for c in node.children)
            or (has_direct_text and all(all_inline_no_media(c) for c in node.children))
        ):
            for child in node.children:
                absorb(child)

    # Coalesce adjacent runs with identical formatting + href.
    # 但不同行（<br> 分行）的 runs 不能合并 —— 否则 PowerPoint 会按 textbox 宽度
    # 自己 word-wrap，行数和 HTML 对不上。让它们保持独立，由 node.py 多 run 路径
    # 设置 breakLine=True 走 pptx 的硬换行。
    merged: List[TextRun] = []
    for run in collected:
        if merged:
            last = merged[-1]
            if (
                last.href == run.href
                and _formats_equal(last.fmt, run.fmt)
                and not runs_on_different_lines(last, run)
            ):
                last.text += ('' if runs_adjacent(last, run) else ' ') + run.text
                last.rect = run.rect
                continue
        merged.append(TextRun(text=run.text, fmt=run.fmt, rect=run.rect, href=run.href))
    return merged, consumed
