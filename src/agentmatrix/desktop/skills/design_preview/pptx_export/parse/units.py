"""Unit conversions. 对应 core/units.ts。"""

from __future__ import annotations

import math
import re

DPI = 96
PX_TO_PT = 0.75

# JS parseInt/parseFloat parse leading numeric prefix permissively:
#   parseInt('600abc', 10) -> 600
#   parseFloat('1.5xyz')   -> 1.5
# Python's int()/float() reject any trailing garbage. Real CSS values are
# clean, but malformed values (e.g. agent-generated content) reach here.
# See findings P5-2 / P9-3 / P11-4.
_INT_PREFIX_RE = re.compile(r'\s*([+-]?\d+)')
_FLOAT_PREFIX_RE = re.compile(r'\s*([+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)')


def parse_int_lenient(s, default: int = 0) -> int:
    """JS parseInt(s, 10) semantics: parse leading integer prefix."""
    if s is None:
        return default
    if isinstance(s, (int, float)):
        if math.isfinite(s):
            return int(s)
        return default
    m = _INT_PREFIX_RE.match(str(s))
    return int(m.group(1)) if m else default


def parse_float_lenient(s, default: float = 0.0) -> float:
    """JS parseFloat semantics: parse leading float prefix; NaN → default."""
    if s is None:
        return default
    if isinstance(s, (int, float)):
        return float(s) if math.isfinite(s) else default
    m = _FLOAT_PREFIX_RE.match(str(s))
    return float(m.group(1)) if m else default


def px_to_inches(px: float) -> float:
    return px / DPI


def px_to_points(px: float) -> float:
    return px * PX_TO_PT


def clamp(value: float, lo: float, hi: float) -> float:
    """Clamp to [lo, hi]; non-finite falls back to lo."""
    if not math.isfinite(value):
        return lo
    return max(lo, min(hi, value))


def js_round(value: float) -> int:
    """JavaScript Math.round semantics: round half away from zero (toward +inf).

    Python's built-in round() uses banker's rounding (half to even), which
    diverges from JS for .5 cases. gen-pptx relies on JS Math.round in
    css.ts (shadow angle) and color.ts (rgb channel, transparency).

    Note on Infinity (P16-5): JS Math.round(Infinity)=Infinity, then
    clamp(Inf, 0, 255)=255 via Math.min. Py chain: js_round(Inf)→0,
    clamp(0,0,255)→0. Diverges only on +Inf input, but all call sites feed
    regex-bound `(-?[\\d.]+)` matches which can't produce Infinity — so the
    divergence is unreachable in practice. NaN path: both end at lo via clamp.
    """
    if not math.isfinite(value):
        return 0
    return math.floor(value + 0.5)
