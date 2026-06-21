"""错误辅助。对应 gen-pptx 的 src/orchestrator/errors.ts。

两个 helper：
- stringify_error：把任意异常安全转为 string（带 'unknown error' fallback）。
- timeout_hint：检测 message 含 timeout 后追加阶段特定提示（setup / editable / screenshots），
  给出可操作的恢复建议（如换 screenshots 模式重试）。
"""

from __future__ import annotations

import re
from typing import Literal

Phase = Literal["setup", "editable", "screenshots"]

_TIMEOUT_RE = re.compile(r"timed?\s*out|timeout", re.IGNORECASE)


def stringify_error(err) -> str:
    """对应 stringifyError：任意 thrown value → string，永不抛。"""
    msg = getattr(err, "message", None)
    if msg:
        return str(msg)
    try:
        return str(err)
    except Exception:
        return "unknown error"


def timeout_hint(message: str, phase: Phase, slide_num: int = None) -> str:
    """对应 timeoutHint：超时类错误追加阶段特定提示，否则返回空串。"""
    if not message or not _TIMEOUT_RE.search(message):
        return ""
    if phase == "setup":
        return (
            ". The page didn't finish loading the deck in time — confirm the URL "
            "serves the deck, then retry."
        )
    where = f"slide {slide_num}"
    if phase == "editable":
        return (
            f". Capture stalled on {where} (slide too heavy for editable capture). "
            "Retrying identically will stall again — tell the user, then retry with "
            "mode:'screenshots' for a pixel-perfect non-editable fallback."
        )
    # screenshots
    return (
        f". Capture stalled on {where}. Retrying identically may stall again — "
        "tell the user and consider a longer delay."
    )
