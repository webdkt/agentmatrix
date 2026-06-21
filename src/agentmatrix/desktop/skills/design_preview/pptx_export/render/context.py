"""RenderContext + rectToPptx. 对应 render/context.ts。

PptxSlide 这里是 duck-typed —— Phase 2c 会有 PptxSlideAdapter 提供同名方法
（addText / addShape / addImage / addNotes / background）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..parse.units import px_to_inches, clamp
from ..types import Rect


@dataclass
class RenderContext:
    slide: Any                       # PptxSlideAdapter（duck-typed）
    slideW: float
    slideH: float
    originX: float
    originY: float
    mediaCache: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    fontMap: Optional[Dict[str, str]] = None


def rect_to_pptx(rect: Rect, ctx: RenderContext) -> Rect:
    """Page rect → slide-relative inches, clamped to a sane band around the slide."""
    x = rect.x - ctx.originX
    y = rect.y - ctx.originY
    return Rect(
        x=px_to_inches(clamp(x, -ctx.slideW, ctx.slideW * 2)),
        y=px_to_inches(clamp(y, -ctx.slideH, ctx.slideH * 2)),
        w=px_to_inches(max(clamp(rect.w, 0, ctx.slideW * 2), 1)),
        h=px_to_inches(max(clamp(rect.h, 0, ctx.slideH * 2), 1)),
    )
