"""
Debug 收集器：把 capture 各阶段的证据落到 <out_dir>/_debug_pptx_export/。

启用方式：export_pptx(..., debug=True)

每张 slide 产出 5 份证据 + 1 份 summary：

    _debug_pptx_export/
        slide-01.html.png         playwright 截图（capture 后 DOM 状态）
        slide-01.dom.html         slide 元素 outerHTML（capture 时的 DOM 源）
        slide-01.capture.json     capture 脚本吐出的 SlideNode 树
        slide-01.pptx.xml         这张 slide 在最终 pptx 里的 OOXML
        slide-01.warnings.txt     build 阶段的 per-slide warnings
        slide-01.capture-failed.txt   （仅当 capture 抛异常）异常堆栈
        summary.md                整体统计：每 slide 的 shape/text 数 + 字体状态

排查路径（按顺序问）：
    1. html.png 看起来对吗？ —— 不对：HTML/showJs 问题（动画没收尾、字体没加载）
    2. capture.json 的 rect 对吗？ —— 不对：capture 脚本 bug（DOM walk）
    3. pptx.xml 写对了吗？      —— 不对：Python renderer bug
    4. 都对但 pptx 打开视觉错   —— PowerPoint 兼容性 / 用户机器字体缺失
"""

from __future__ import annotations

import base64
import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional


# 文件名前缀格式：slide-01, slide-02, ... (两位数 zero-pad，最多 99 张)
def _prefix(i: int) -> str:
    return f"slide-{i + 1:02d}"


class DebugCollector:
    """每张 slide 的证据收集器。

    用 .enable() 启用，.disabled() 拿一个 no-op 实例。
    所有 record_* 方法都是 async（即使 no-op，便于 caller 不分叉）。
    """

    def __init__(self, enabled: bool, out_dir: Optional[str]):
        self.enabled = enabled
        if enabled:
            self.dir = Path(out_dir) / "_debug_pptx_export"
            self.dir.mkdir(parents=True, exist_ok=True)
        else:
            self.dir = None

    @classmethod
    def enable(cls, out_dir: str) -> "DebugCollector":
        return cls(enabled=True, out_dir=out_dir)

    @classmethod
    def disabled(cls) -> "DebugCollector":
        return cls(enabled=False, out_dir=None)

    # -----------------------------------------------------------------
    # Editable mode
    # -----------------------------------------------------------------

    async def record_capture(self, i: int, spec, cap: dict, driver) -> None:
        """editable capture 成功后调用。cap 是 driver.capture_editable() 的返回。"""
        if not self.enabled:
            return
        prefix = _prefix(i)
        captured = cap.get("captured")
        root = getattr(captured, "root", None) if captured else None

        # (1) html.png —— capture 后立刻截全 viewport（DOM 还在 capture 状态）
        try:
            png = await driver.page.screenshot(type="png")
            (self.dir / f"{prefix}.html.png").write_bytes(png)
        except Exception as e:
            self._write_text(f"{prefix}.screenshot-error.txt", f"截图失败: {e}\n")

        # (2) dom.html —— slide 元素 outerHTML
        try:
            outer_html = await driver.page.evaluate(
                "(sel) => { const el = document.querySelector(sel); "
                "return el ? el.outerHTML : null; }",
                spec.selector,
            )
            if outer_html:
                self._write_text(f"{prefix}.dom.html", outer_html)
            else:
                self._write_text(
                    f"{prefix}.dom-notfound.txt",
                    f"selector 未匹配到元素: {spec.selector}\n",
                )
        except Exception as e:
            self._write_text(f"{prefix}.dom-error.txt", f"取 outerHTML 失败: {e}\n")

        # (3) capture.json —— SlideNode 树
        try:
            payload = {
                "index": i,
                "spec": {
                    "selector": spec.selector,
                    "showJs": spec.showJs,
                    "delay": spec.delay,
                },
                "captured": _captured_slide_to_dict(cap["captured"]) if cap.get("captured") else None,
                "meta": {
                    "hash": cap.get("hash"),
                    "imagesWaited": cap.get("imagesWaited"),
                    "imagesFailed": cap.get("imagesFailed"),
                },
            }
            self._write_text(
                f"{prefix}.capture.json",
                json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            )
        except Exception as e:
            self._write_text(f"{prefix}.capture-error.txt", f"序列化 capture 失败: {e}\n")

    async def record_capture_failure(self, i: int, spec, exc: Exception, driver) -> None:
        """editable capture 抛异常时调用。"""
        if not self.enabled:
            return
        prefix = _prefix(i)
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # 异常时也截一张图看下当时 DOM 状态
        try:
            png = await driver.page.screenshot(type="png")
            (self.dir / f"{prefix}.html.png").write_bytes(png)
        except Exception as e:
            self._write_text(f"{prefix}.screenshot-error.txt", f"截图失败: {e}\n")
        self._write_text(
            f"{prefix}.capture-failed.txt",
            f"slide {i + 1} capture 抛异常\nselector: {spec.selector}\nshowJs: {spec.showJs}\n\n{tb}\n",
        )

    # -----------------------------------------------------------------
    # Screenshots mode（无 capture.json，主要存 png）
    # -----------------------------------------------------------------

    async def record_screenshot(self, i: int, spec, data_url: str, driver) -> None:
        if not self.enabled:
            return
        prefix = _prefix(i)
        # data_url 形如 "data:image/png;base64,...."
        try:
            b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
            png = base64.b64decode(b64)
            (self.dir / f"{prefix}.html.png").write_bytes(png)
        except Exception as e:
            self._write_text(f"{prefix}.screenshot-error.txt", f"解码 PNG 失败: {e}\n")
        # screenshots 模式没有 capture tree，存个 spec 元信息方便对照
        self._write_text(
            f"{prefix}.spec.json",
            json.dumps({
                "index": i,
                "selector": spec.selector,
                "showJs": spec.showJs,
                "delay": spec.delay,
            }, ensure_ascii=False, indent=2),
        )

    # -----------------------------------------------------------------
    # Finalize：抽 per-slide XML + 写 summary
    # -----------------------------------------------------------------

    async def finalize(
        self,
        *,
        pptx_bytes: bytes,
        pptx_path: Optional[str],
        all_warnings: List[str],
        warnings_start: int,
        slides,           # List[CapturedSlide]
        captures,         # List[dict]
        setup_res,        # SetupResult
        input_,           # GenPptxInput
    ) -> None:
        """build 完成后：抽 pptx per-slide XML + 写 summary.md。"""
        if not self.enabled:
            return

        n_slides = len(slides)
        # 平均分 warnings 到每张 slide（build 阶段的 warnings 无法精确归因到单 slide，
        # 因为 renderer 跑在 build_editable_pptx 内部；这里按顺序均分 + 把全部也写一份）
        build_warnings = all_warnings[warnings_start:] if warnings_start < len(all_warnings) else all_warnings
        per_slide_warns = _split_list_round_robin(build_warnings, n_slides)
        for i in range(n_slides):
            prefix = _prefix(i)
            self._write_text(
                f"{prefix}.warnings.txt",
                ("\n".join(per_slide_warns[i]) + "\n") if per_slide_warns[i] else "（该 slide 无 warning）\n",
            )

        # 抽 per-slide XML
        slide_xmls = _extract_slide_xmls(pptx_bytes)
        for i in range(min(n_slides, len(slide_xmls))):
            self._write_text(f"{_prefix(i)}.pptx.xml", slide_xmls[i])

        # 写 summary.md
        summary = _build_summary_md(
            n_slides=n_slides,
            slides=slides,
            captures=captures,
            setup_res=setup_res,
            input_=input_,
            pptx_path=pptx_path,
            all_warnings=all_warnings,
            per_slide_warns=per_slide_warns,
        )
        self._write_text("summary.md", summary)

    # -----------------------------------------------------------------
    # 内部
    # -----------------------------------------------------------------

    def _write_text(self, name: str, text: str) -> None:
        try:
            (self.dir / name).write_text(text, encoding="utf-8")
        except Exception:
            pass  # debug 失败不阻塞主流程


# ---------------------------------------------------------------------------
# 序列化 helpers
# ---------------------------------------------------------------------------

def _captured_slide_to_dict(captured) -> dict:
    """CapturedSlide → JSON 友好的 dict（递归转 SlideNode）。"""
    return {
        "rect": _rect_to_dict(getattr(captured, "rect", None)),
        "notes": getattr(captured, "notes", None),
        "root": _slide_node_to_dict(getattr(captured, "root", None)),
    }


def _slide_node_to_dict(node) -> Optional[dict]:
    if node is None:
        return None
    return {
        "tag": node.tag,
        "rect": _rect_to_dict(node.rect),
        "style": dict(node.style) if node.style else {},
        "text": node.text,
        "href": node.href,
        "imageUrl": node.imageUrl,
        "svg": node.svg,
        "untransformedRect": _rect_to_dict(node.untransformedRect) if node.untransformedRect else None,
        "liIndex": node.liIndex,
        "children": [_slide_node_to_dict(c) for c in (node.children or [])],
    }


def _rect_to_dict(rect) -> Optional[dict]:
    if rect is None:
        return None
    return {"x": rect.x, "y": rect.y, "w": rect.w, "h": rect.h}


# ---------------------------------------------------------------------------
# pptx ZIP → per-slide XML
# ---------------------------------------------------------------------------

def _extract_slide_xmls(pptx_bytes: bytes) -> List[str]:
    """从 pptx bytes 抽出 ppt/slides/slide1.xml, slide2.xml, ...（按序号排序）。"""
    import io
    import zipfile

    out: List[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(pptx_bytes)) as z:
            names = [n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")]
            # 按数字序排：slide1.xml < slide2.xml < ... < slide10.xml
            def key(name: str) -> int:
                stem = name.rsplit("/", 1)[-1].removesuffix(".xml").removeprefix("slide")
                try:
                    return int(stem)
                except ValueError:
                    return 1_000_000
            for name in sorted(names, key=key):
                out.append(z.read(name).decode("utf-8", errors="replace"))
    except Exception as e:
        out.append(f"<!-- 抽 pptx XML 失败: {e} -->")
    return out


# ---------------------------------------------------------------------------
# summary.md
# ---------------------------------------------------------------------------

def _build_summary_md(
    *,
    n_slides: int,
    slides,
    captures,
    setup_res,
    input_,
    pptx_path: Optional[str],
    all_warnings: List[str],
    per_slide_warns: List[List[str]],
) -> str:
    lines: List[str] = []
    lines.append("# PPTX Export Debug Report\n")
    lines.append(f"- **pptx**: `{pptx_path}`\n")
    lines.append(f"- **mode**: {input_.mode}\n")
    lines.append(f"- **canvas**: {input_.width}×{input_.height}\n")
    lines.append(f"- **slides**: {n_slides}\n")
    lines.append(f"- **hideSelectors**: {input_.hideSelectors}\n")
    lines.append(f"- **resetTransformSelector**: {input_.resetTransformSelector}\n")
    lines.append(f"- **googleFontImports**: {len(input_.googleFontImports)} 项\n")
    lines.append(f"- **fontSwaps**: {[p.to_dict() for p in input_.fontSwaps]}\n")
    lines.append(f"- **setup.fontsReady**: {getattr(setup_res, 'fontsReady', None)}\n")
    lines.append(f"- **setup.fontSwapMisses**: {getattr(setup_res, 'fontSwapMisses', None)}\n")
    lines.append(f"- **setup.resetRect**: {_rect_to_dict(getattr(setup_res, 'resetRect', None))}\n")
    lines.append(f"- **total warnings**: {len(all_warnings)}\n")
    lines.append("")

    lines.append("## Per-slide stats\n")
    lines.append("| # | selector | shapes | text nodes | images | hash | warnings |")
    lines.append("|---|----------|--------|------------|--------|------|----------|")
    for i in range(n_slides):
        spec = input_.slides[i]
        captured = slides[i]
        root = getattr(captured, "root", None)
        shape_count, text_count, img_count = _count_tree(root)
        cap_meta = captures[i] if i < len(captures) else {}
        warn_n = len(per_slide_warns[i]) if i < len(per_slide_warns) else 0
        lines.append(
            f"| {i + 1} | `{spec.selector}` | {shape_count} | {text_count} | {img_count} | "
            f"{cap_meta.get('hash', '?')} | {warn_n} |"
        )
    lines.append("")

    lines.append("## How to read this\n")
    lines.append(
        "对每张出问题的 slide，按顺序问：\n"
        "1. `slide-NN.html.png` 视觉对吗？\n"
        "   - 不对 → HTML / showJs 问题（动画未播完、字体未加载、selector 指错元素）。\n"
        "2. `slide-NN.capture.json` 里 root.children 的 rect 对吗（在 canvas 坐标系内）？\n"
        "   - 不对 → capture 脚本 bug（DOM walk 错位、transform 未解开）。\n"
        "3. `slide-NN.pptx.xml` 里的 `<p:sp>/x/y/cx/cy` 和 capture.json 的 rect 对得上吗？\n"
        "   - 对得上但 pptx 视觉错 → PowerPoint 渲染差异（字体、效果降级）。\n"
        "   - 对不上 → Python renderer bug，看 `slide-NN.warnings.txt` 找异常。\n"
    )
    return "\n".join(lines) + "\n"


def _count_tree(root) -> tuple[int, int, int]:
    """统计 SlideNode 树里的 shape / text / image 节点数（粗略，用于 summary）。"""
    if root is None:
        return (0, 0, 0)
    shapes = 0
    texts = 0
    imgs = 0

    def walk(node):
        nonlocal shapes, texts, imgs
        if not node:
            return
        if node.tag == "#text":
            texts += 1
            return
        if node.imageUrl or node.svg:
            imgs += 1
        if node.tag in ("img", "canvas", "svg"):
            imgs += 1
        # 每个非文本节点算一个 shape（粗略）
        if node.tag != "#text":
            shapes += 1
        for c in (node.children or []):
            walk(c)

    walk(root)
    return (shapes, texts, imgs)


def _split_list_round_robin(items: List[str], n: int) -> List[List[str]]:
    """简单均分（不严格，build 阶段 warnings 本来就无法精确归因到 slide）。"""
    if n <= 0:
        return []
    buckets: List[List[str]] = [[] for _ in range(n)]
    for i, item in enumerate(items):
        buckets[i % n].append(item)
    return buckets
