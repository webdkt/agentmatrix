"""Media cache builders. 对应 render/media-cache.ts。"""

from __future__ import annotations

import math
from typing import Any, Awaitable, Callable, Dict, List, Set, Tuple

from ..types import CapturedSlide, MediaEntry, MediaRef, ResolvedMedia, SlideNode


def hash_svg(s: str) -> str:
    """FNV-1a → base36. Stable key for an inline <svg>'s serialized markup.

    Mirrors JS `h.toString(36)` (lowercase alphanumeric).
    """
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    if h == 0:
        return '0'
    digits = '0123456789abcdefghijklmnopqrstuvwxyz'
    out = []
    while h > 0:
        out.append(digits[h % 36])
        h //= 36
    return ''.join(reversed(out))


def image_key(node: SlideNode):
    """Cache key for a node's media: raster URL verbatim, or svg:<hash>:<w>x<h>."""
    if node.imageUrl:
        return node.imageUrl
    if node.svg:
        return f'svg:{hash_svg(node.svg)}:{node.rect.w}x{node.rect.h}'
    return None


def collect_image_refs(
    node: SlideNode,
    urls: Set[str],
    svgs: Dict[str, Tuple[str, float, float]],
):
    if node.imageUrl:
        urls.add(node.imageUrl)
    elif node.svg:
        key = image_key(node)
        if key and key not in svgs:
            svgs[key] = (node.svg, node.rect.w, node.rect.h)
    for child in node.children:
        collect_image_refs(child, urls, svgs)


async def build_media_cache(
    slides: List[CapturedSlide],
    warnings: List[str],
    resolve_media: Callable[[List[MediaRef]], Awaitable[List[ResolvedMedia]]],
) -> Dict[str, MediaEntry]:
    urls: Set[str] = set()
    svgs: Dict[str, Tuple[str, float, float]] = {}
    for slide in slides:
        if slide.root is not None:
            collect_image_refs(slide.root, urls, svgs)

    refs: List[MediaRef] = []
    for url in urls:
        refs.append(MediaRef(kind='url', key=url, url=url))
    for key, (svg, w, h) in svgs.items():
        refs.append(MediaRef(kind='svg', key=key, svg=svg, w=w, h=h))

    cache: Dict[str, MediaEntry] = {}
    if not refs:
        return cache

    resolved = await resolve_media(refs)
    for r in resolved:
        for w in r.warnings:
            warnings.append(w)
        if r.value is not None:
            cache[r.key] = r.value
    return cache
