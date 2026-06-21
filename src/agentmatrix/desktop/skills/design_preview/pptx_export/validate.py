"""
Validation flags. 对应 gen-pptx 的 src/validate/validate.ts。

Cross-check capture/setup facts against the request and emit advisory flags.
All flags are informational (不阻塞导出)；前端按 kind 决定显示。
"""

from __future__ import annotations

import math
from typing import List, Optional

from .types import CapturedSlide, GenPptxInput, SetupResult, ValidationFlag, WarningKind
from .parse.units import js_round


# Each slide's capture facts the validator inspects.
class SlideHashResult:
    __slots__ = ('hash', 'imagesWaited', 'imagesFailed')

    def __init__(self, hash_: int = 0, imagesWaited: int = 0, imagesFailed: int = 0):
        self.hash = hash_
        self.imagesWaited = imagesWaited
        self.imagesFailed = imagesFailed


def _flag(kind: WarningKind, message: str) -> ValidationFlag:
    """Build a ValidationFlag. Centralizes the kind literal so typos are caught."""
    return ValidationFlag(kind=kind, message=message)


def validate(
    setup: SetupResult,
    perSlide: List[SlideHashResult],
    slideTrees: List[CapturedSlide],
    input_: GenPptxInput,
    mode: str,
) -> List[ValidationFlag]:
    """对应 validate.ts::validate. 返回 ValidationFlag 列表。"""
    flags: List[ValidationFlag] = []

    if not setup.fontsReady:
        flags.append(_flag(
            'fonts_timeout',
            'document.fonts.ready did not resolve within 8s — text metrics '
            'may use fallback fonts. Check that font URLs are reachable.',
        ))

    misses = setup.fontSwapMisses or []
    if misses:
        list_str = ', '.join(misses)
        if mode == 'screenshots':
            msg = (
                f'Font swap target(s) {list_str} never loaded — the Google Fonts '
                'CSS fetch failed or returned nothing for the family, or the face '
                "isn't installed locally. The screenshots were rendered with a "
                'fallback font. Retry with a corrected family name or a '
                'Google-served family (check fonts.google.com) — web-safe faces '
                'may not exist in this rendering environment either, so they '
                'are not a fix here. Tell the user plainly which fonts '
                "couldn't be applied."
            )
        else:
            msg = (
                f'Font swap target(s) {list_str} never loaded — the Google Fonts '
                'CSS fetch failed or returned nothing for the family, or the face '
                "isn't installed locally. The exported file names these fonts, "
                'but layout used a fallback, so text sizing and wrapping may '
                'drift. Retry with a corrected family name (check fonts.google.com) '
                'or web-safe fonts, and tell the user plainly which fonts '
                "couldn't be applied."
            )
        flags.append(_flag('font_swap_failed', msg))

    if mode == 'editable' and input_.resetTransformSelector and not setup.resetRect:
        flags.append(_flag(
            'reset_selector_miss',
            f'resetTransformSelector {input_.resetTransformSelector!r} matched '
            'nothing — capture may be scaled.',
        ))
    elif setup.resetRect:
        dw = abs(setup.resetRect.w - input_.width)
        dh = abs(setup.resetRect.h - input_.height)
        if dw > 2 or dh > 2:
            flags.append(_flag(
                'slide_size_mismatch',
                f'resetTransformSelector measures '
                f'{js_round(setup.resetRect.w)}×{js_round(setup.resetRect.h)} '
                f'after reset, expected {input_.width}×{input_.height}. '
                "Check the element isn't constrained by a parent's "
                'max-width/overflow.',
            ))

    for i, tree in enumerate(slideTrees):
        rect = tree.rect
        if rect is None:
            continue
        if abs(rect.w - input_.width) > 2 or abs(rect.h - input_.height) > 2:
            flags.append(_flag(
                'slide_size_mismatch',
                f'Slide {i + 1} root measures '
                f'{js_round(rect.w)}×{js_round(rect.h)}, expected '
                f'{input_.width}×{input_.height}. The selector may be '
                'matching a wrapper rather than the slide content, or the '
                "deck doesn't fix slide dimensions.",
            ))
            break

    dup_adjacent: List[int] = []
    for i in range(1, len(perSlide)):
        if perSlide[i].hash == perSlide[i - 1].hash:
            dup_adjacent.append(i)
    if dup_adjacent:
        pairs = ', '.join(f'{i}/{i + 1}' for i in dup_adjacent)
        flags.append(_flag(
            'duplicate_adjacent',
            f'Slides {pairs} captured identically — showJs likely failed to '
            'navigate. Check the JS actually changes the visible slide; some '
            'decks need a longer delay for transitions.',
        ))

    counts: dict = {}
    for r in perSlide:
        counts[r.hash] = counts.get(r.hash, 0) + 1
    max_count = max(counts.values()) if counts else 0
    if len(perSlide) >= 3 and max_count > len(perSlide) / 2:
        flags.append(_flag(
            'duplicate_majority',
            f'{max_count}/{len(perSlide)} slides captured identically. The '
            "deck likely doesn't expose a JS navigation hook, or the showJs "
            'is wrong.',
        ))

    notes = setup.notes or []
    if len(notes) == 0:
        flags.append(_flag(
            'no_speaker_notes',
            'No speaker notes found in the deck (neither data-speaker-notes '
            'attributes nor a #speaker-notes JSON block). Expected if the '
            'deck has no notes.',
        ))
    else:
        if len(notes) != len(input_.slides):
            flags.append(_flag(
                'notes_count_mismatch',
                f'Speaker notes have {len(notes)} entries but '
                f'{len(input_.slides)} slides were requested — notes attach '
                'by index, so the tail will be missing or misalign.',
            ))
        non_empty = [n for n in notes if n and n.strip()]
        if len(non_empty) >= 2 and len(set(non_empty)) == 1:
            flags.append(_flag(
                'notes_uniform_nonempty',
                f'All {len(non_empty)} non-empty speaker notes are identical '
                '— likely a placeholder, not real notes.',
            ))

    failed = sum(r.imagesFailed for r in perSlide)
    if failed > 0:
        waited = sum(r.imagesWaited for r in perSlide)
        flags.append(_flag(
            'images_failed',
            f'{failed}/{waited} images failed to decode before capture — '
            "they'll be missing from the export. Usually a 404 src or a "
            'CORS-blocked external URL.',
        ))

    return flags
