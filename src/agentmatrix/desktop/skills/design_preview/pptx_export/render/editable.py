"""Editable-mode pptx assembler. 对应 render/build-editable.ts."""

from __future__ import annotations

import io
from typing import Any, Awaitable, Callable, Dict, List, Optional

from pptx import Presentation
from pptx.util import Inches

from ..parse.color import parse_color
from ..parse.units import px_to_inches
from ..types import CapturedSlide, MediaEntry, MediaRef, ResolvedMedia
from .context import RenderContext
from .media_cache import build_media_cache
from .node import render_node_to_pptx
from .pptx_slide_adapter import PptxSlideAdapter


async def build_editable_pptx(
    width: float,
    height: float,
    slides: List[CapturedSlide],
    resolve_media: Callable[[List[MediaRef]], Awaitable[List[ResolvedMedia]]],
    font_map: Optional[Dict[str, str]] = None,
) -> dict:
    """Assemble editable .pptx from captured slide trees.

    Returns: dict(bytes, bytes_len, slides, warnings)
    """
    if not slides:
        raise ValueError('build_editable_pptx: deck has no slides')

    warnings: List[str] = []
    prs = Presentation()
    # 自定义 layout（python-pptx 直接覆盖 slide_width / slide_height 即可，
    # 不需要 defineLayout）
    prs.slide_width = Inches(px_to_inches(width))
    prs.slide_height = Inches(px_to_inches(height))
    blank_layout = prs.slide_layouts[6]

    media_cache: Dict[str, MediaEntry] = await build_media_cache(
        slides, warnings, resolve_media,
    )

    for captured in slides:
        adapter = PptxSlideAdapter(prs, blank_layout)
        root = captured.root
        if root is not None:
            # Promote root bg to slide.background if it's fully opaque.
            root_bg = parse_color(root.style.get('backgroundColor'))
            if root_bg and root_bg.alpha == 1:
                adapter.background = {'color': root_bg.hex}
                root.style['backgroundColor'] = 'transparent'
            ctx = RenderContext(
                slide=adapter,
                slideW=width,
                slideH=height,
                originX=captured.rect.x,
                originY=captured.rect.y,
                mediaCache=media_cache,
                warnings=warnings,
                fontMap=font_map,
            )
            try:
                render_node_to_pptx(root, ctx)
            except Exception as e:
                warnings.append(f'Slide render aborted: {e}')
        # R16-7: 之前 (captured.notes or '').strip() 会把首尾空白吃掉，
        # TS build-editable.ts 是 slide.addNotes(captured.notes) 原文写入。
        # 这里只在判断非空时 strip（避免写纯空白页），写入用原文。
        raw_notes = captured.notes or ''
        if raw_notes.strip():
            try:
                adapter.addNotes(raw_notes)
            except Exception as e:
                warnings.append(f'addNotes failed: {e}')

    buf = io.BytesIO()
    prs.save(buf)
    raw = buf.getvalue()
    return {
        'bytes': raw,
        'bytes_len': len(raw),
        'slides': len(slides),
        'warnings': warnings,
    }
