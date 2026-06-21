"""输入清洗。对应 gen-pptx 的 src/core/sanitize.ts。

在 config 跨越 page.evaluate 边界（注入浏览器执行）之前，对 hideSelectors /
googleFontImports / fontSwaps 做类型过滤，避免非字符串/畸形对象混入 DOM 选择器
或 fontSwap 查找路径。

设计原则（与 TS 版对齐）：**只过滤，不强制类型转换**。例如 `[42, "foo"]` →
`["foo"]`，而非 `["42", "foo"]`。原因是数值/对象等若被 stringify 后送进
querySelector，会触发意外选择器语法异常或匹配到不期望的元素。
"""

from __future__ import annotations

from typing import Any, List

from ..types import FontSwap


def sanitize_strings(value: Any) -> List[str]:
    """对应 sanitizeStrings：只保留 string 元素。"""
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str)]


def sanitize_font_swaps(value: Any) -> List[FontSwap]:
    """对应 sanitizeFontSwaps：只保留 {from: str, to: str} 形态的项。"""
    if not isinstance(value, list):
        return []
    out: List[FontSwap] = []
    for v in value:
        if not isinstance(v, dict):
            continue
        frm = v.get("from")
        to = v.get("to")
        if isinstance(frm, str) and isinstance(to, str):
            out.append(FontSwap(from_=frm, to=to))
    return out
