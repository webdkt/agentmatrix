"""
Data contract for pptx_export（对应 gen-pptx 的 src/types.ts）。

所有结构都是 JSON 可序列化的，方便跨越 page.evaluate() 边界。
用 dataclass + typing，不引入 Pydantic（保持依赖最小）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


Mode = Literal["editable", "screenshots"]
_VALID_MODES = frozenset({"editable", "screenshots"})


# 对应 TS types.ts:78-93 WarningKind 联合类型。validate.py 产出的 flag.kind 必须
# 落在这个集合里，下游消费者（debug / 调用方）可以靠 Literal 类型静态校验。
WarningKind = Literal[
    'duplicate_adjacent',
    'duplicate_majority',
    'slide_size_mismatch',
    'reset_selector_miss',
    'fonts_timeout',
    'font_swap_failed',
    'no_speaker_notes',
    'notes_count_mismatch',
    'notes_uniform_nonempty',
    'images_failed',
]
WARNING_KINDS = frozenset({
    'duplicate_adjacent',
    'duplicate_majority',
    'slide_size_mismatch',
    'reset_selector_miss',
    'fonts_timeout',
    'font_swap_failed',
    'no_speaker_notes',
    'notes_count_mismatch',
    'notes_uniform_nonempty',
    'images_failed',
})


@dataclass
class ValidationFlag:
    """对应 TS types.ts:90-93 ValidationFlag {kind, message}。

    之前用裸 dict 承载，重构为 dataclass 后能在 import 时被静态检查器（mypy /
    Pyright）校验 kind 字面量，避免拼写错误静默 through。
    """
    kind: WarningKind
    message: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message}

    @classmethod
    def from_dict(cls, d: dict) -> "ValidationFlag":
        return cls(kind=str(d.get("kind", "")), message=str(d.get("message", "")))


@dataclass
class FontSwap:
    from_: str = ""
    to: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "FontSwap":
        return cls(from_=str(d.get("from", "")), to=str(d.get("to", "")))

    def to_dict(self) -> dict:
        return {"from": self.from_, "to": self.to}


@dataclass
class SlideSpec:
    selector: str
    showJs: Optional[str] = None
    delay: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SlideSpec":
        return cls(
            selector=str(d.get("selector", "")),
            showJs=d.get("showJs"),
            delay=d.get("delay"),
        )


@dataclass
class GenPptxInput:
    width: int
    height: int
    slides: List[SlideSpec] = field(default_factory=list)
    mode: Mode = "editable"
    hideSelectors: List[str] = field(default_factory=list)
    resetTransformSelector: Optional[str] = None
    googleFontImports: List[str] = field(default_factory=list)
    fontSwaps: List[FontSwap] = field(default_factory=list)
    filename: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "GenPptxInput":
        # T1-4: Mode 之前是裸 str，typo 如 'screenshot' 会静默走 editable 分支。
        # 这里显式校验，非法值抛 ValueError，caller (exporter.py:40-41) 会转成
        # GenPptxResult(ok=False, error=...)。
        mode = str(d.get("mode") or "editable")
        if mode not in _VALID_MODES:
            raise ValueError(
                f"mode 必须是 'editable' 或 'screenshots'，got {mode!r}"
            )
        return cls(
            width=int(d.get("width", 0)),
            height=int(d.get("height", 0)),
            slides=[SlideSpec.from_dict(s) for s in (d.get("slides") or [])],
            mode=mode,
            hideSelectors=[str(s) for s in (d.get("hideSelectors") or [])],
            resetTransformSelector=d.get("resetTransformSelector"),
            googleFontImports=[str(s) for s in (d.get("googleFontImports") or [])],
            fontSwaps=[FontSwap.from_dict(p) for p in (d.get("fontSwaps") or [])],
            filename=d.get("filename"),
        )


@dataclass
class Rect:
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "Rect":
        return cls(
            x=float(d.get("x", 0)),
            y=float(d.get("y", 0)),
            w=float(d.get("w", 0)),
            h=float(d.get("h", 0)),
        )


@dataclass
class SetupResult:
    notes: List[str] = field(default_factory=list)
    fontsReady: bool = False
    resetRect: Optional[Rect] = None
    fontSwapMisses: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "SetupResult":
        rr = d.get("resetRect")
        return cls(
            notes=[str(n) for n in (d.get("notes") or [])],
            fontsReady=bool(d.get("fontsReady", False)),
            resetRect=Rect.from_dict(rr) if rr else None,
            fontSwapMisses=[str(s) for s in (d.get("fontSwapMisses") or [])],
        )


# ---------------------------------------------------------------------------
# Editable-mode capture (Phase 2)
# ---------------------------------------------------------------------------

@dataclass
class SlideNode:
    tag: str = ""
    rect: Rect = field(default_factory=Rect)
    style: Dict[str, str] = field(default_factory=dict)
    children: List["SlideNode"] = field(default_factory=list)
    text: Optional[str] = None
    href: Optional[str] = None
    imageUrl: Optional[str] = None
    svg: Optional[str] = None
    untransformedRect: Optional[Rect] = None
    liIndex: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SlideNode":
        return cls(
            tag=str(d.get("tag", "")),
            rect=Rect.from_dict(d.get("rect") or {}),
            style={str(k): str(v) for k, v in (d.get("style") or {}).items()},
            children=[cls.from_dict(c) for c in (d.get("children") or [])],
            text=d.get("text"),
            href=d.get("href"),
            imageUrl=d.get("imageUrl"),
            svg=d.get("svg"),
            untransformedRect=Rect.from_dict(d["untransformedRect"]) if d.get("untransformedRect") else None,
            liIndex=d.get("liIndex"),
        )


@dataclass
class CapturedSlide:
    rect: Rect = field(default_factory=Rect)
    root: Optional[SlideNode] = None
    notes: Optional[str] = None


@dataclass
class MediaEntry:
    dataUrl: str = ""
    w: Optional[float] = None
    h: Optional[float] = None


@dataclass
class MediaRef:
    kind: str  # "url" | "svg"
    key: str
    url: Optional[str] = None
    svg: Optional[str] = None
    w: Optional[float] = None
    h: Optional[float] = None

    def to_dict(self) -> dict:
        d: Dict[str, Any] = {"kind": self.kind, "key": self.key}
        if self.url is not None:
            d["url"] = self.url
        if self.svg is not None:
            d["svg"] = self.svg
        if self.w is not None:
            d["w"] = self.w
        if self.h is not None:
            d["h"] = self.h
        return d


@dataclass
class ResolvedMedia:
    key: str
    value: Optional[MediaEntry] = None
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ResolvedMedia":
        v = d.get("value")
        return cls(
            key=str(d.get("key", "")),
            value=MediaEntry(
                dataUrl=str(v.get("dataUrl", "")),
                w=v.get("w"),
                h=v.get("h"),
            ) if v else None,
            warnings=[str(s) for s in (d.get("warnings") or [])],
        )


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class GenPptxResult:
    """对应 TS 的 cli.ts 输出 + 错误路径合并（不是 types.ts 的 GenPptxResult）。

    Field 命名说明（intentional deviation from TS types.ts，见 finding T1-1）：
    - `flags`：TS 接口叫 `validation: ValidationFlag[]`；这里沿用 CLI 输出层的
      字段名 `flags`，且类型为 `List[ValidationFlag]`（不是裸 dict）。
    - `file`：TS 接口叫 `savedPath?`；这里沿用 CLI 输出层 `file`。
    - `ok` / `error`：TS 通过 `{result, buffer}` 二元组 + 异常路径表达；Python
      合并到单一返回值（export_pptx 是 async），新增这两个字段表达成功/失败。
    """
    ok: bool
    file: Optional[str] = None
    slides: int = 0
    bytes: int = 0
    flags: List[ValidationFlag] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    speakerNotes: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "file": self.file,
            "slides": self.slides,
            "bytes": self.bytes,
            "flags": [f.to_dict() for f in self.flags],
            "warnings": self.warnings,
            "speakerNotes": self.speakerNotes,
            "error": self.error,
        }
