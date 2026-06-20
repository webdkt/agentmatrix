"""
Main entry: 对应 cli.ts + orchestrator/run.ts 的入口逻辑。

    result = await export_pptx(url=..., config={...}, out_dir=...)
    # result.to_dict() -> {ok, file, slides, bytes, flags, warnings, speakerNotes}
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from .types import GenPptxInput, GenPptxResult
from .driver import PptxExportDriver
from .errors import stringify_error, timeout_hint
from .parse.sanitize import sanitize_strings, sanitize_font_swaps
from .validate import SlideHashResult, validate as run_validate


async def export_pptx(url: str, config: dict, out_dir: str,
                      filename: Optional[str] = None,
                      debug: bool = False) -> GenPptxResult:
    """导出 PPTX。

    Args:
        url: 已 serve 的 HTML deck URL（必须 http(s)://，不能 file://）
        config: GenPptxInput 的 dict 形式（含 width/height/slides/mode）
        out_dir: 输出目录，.pptx 落到这里
        filename: 输出文件名（不含扩展名）；None 则用 export-<timestamp>.pptx
        debug: True 时在 <out_dir>/_debug_pptx_export/ 下为每张 slide 导出
                截图 + capture.json + pptx.xml + warnings + summary.md，用于排查布局问题

    Returns:
        GenPptxResult（含 to_dict()）
    """
    if not url or not re.match(r"^https?://", url):
        return GenPptxResult(ok=False, error=f"url 必须是 http(s):// URL：{url!r}")

    raw = config or {}
    try:
        input_ = GenPptxInput.from_dict(raw)
    except Exception as e:
        return GenPptxResult(ok=False, error=f"config 解析失败：{e}")
    # 入口清洗（对应 run.ts:30-35）：hideSelectors / googleFontImports / fontSwaps
    # 在注入浏览器执行前过滤掉非字符串/畸形项。这里从 raw 取原始值再过滤，
    # 避免 from_dict 的 str() 强转把 42→"42" 这类畸形值救回来。
    input_.hideSelectors = sanitize_strings(raw.get("hideSelectors"))
    input_.googleFontImports = sanitize_strings(raw.get("googleFontImports"))
    input_.fontSwaps = sanitize_font_swaps(raw.get("fontSwaps"))
    if not input_.slides:
        return GenPptxResult(ok=False, error="config.slides 为空")
    if input_.width <= 0 or input_.height <= 0:
        return GenPptxResult(ok=False, error="config 必须包含数值型 width/height")

    if filename:
        input_.filename = filename

    mode = input_.mode or "editable"
    driver: Optional[PptxExportDriver] = None
    try:
        driver = await PptxExportDriver.launch(url, input_)
        await driver.inject_capture_bundle()

        # screenshots 模式：lock viewport 到 slide size + 双 rAF settle
        if mode == "screenshots":
            await driver.set_viewport_size(input_.width, input_.height)
            await driver.raf_settle()

        setup_res = await driver.setup(input_)

        if mode == "screenshots":
            return await _run_screenshots(driver, input_, setup_res, out_dir, debug=debug)
        else:
            return await _run_editable(driver, input_, setup_res, out_dir, debug=debug)
    except Exception as e:
        msg = stringify_error(e) + timeout_hint(stringify_error(e), "setup")
        return GenPptxResult(ok=False, error=msg)
    finally:
        if driver is not None:
            try:
                await driver.close()
            except Exception:
                pass


async def _run_screenshots(driver: PptxExportDriver, input_: GenPptxInput,
                           setup_res, out_dir: str, *, debug: bool = False) -> GenPptxResult:
    from .render.screenshot import build_screenshot_pptx
    from .debug import DebugCollector

    debug_col = DebugCollector.enable(out_dir) if debug else DebugCollector.disabled()

    data_urls = []
    for i, spec in enumerate(input_.slides):
        try:
            await driver.capture_screenshot(spec)
            data_url = await driver.screenshot_data_url()
        except Exception as e:
            await debug_col.record_capture_failure(i, spec, e, driver)
            msg = stringify_error(e)
            return GenPptxResult(
                ok=False,
                error=(
                    f"slide {i + 1}/{len(input_.slides)} capture failed: {msg}"
                    + timeout_hint(msg, "screenshots", i + 1)
                ),
            )
        data_urls.append(data_url)
        await debug_col.record_screenshot(i, spec, data_url, driver)

    build = build_screenshot_pptx(
        image_data_urls=data_urls,
        notes=setup_res.notes,
        width_px=input_.width,
        height_px=input_.height,
    )

    saved_path = _write_output(build["bytes"], out_dir, input_.filename)

    per_slide = [SlideHashResult(hash_=_djb2_hash_middle(u)) for u in data_urls]
    # screenshots 模式没有 captured tree，用空 list 占位
    flags = run_validate(setup_res, per_slide, [], input_, mode="screenshots")

    return GenPptxResult(
        ok=True,
        file=saved_path,
        slides=build["slides"],
        bytes=build["bytes_len"],
        flags=flags,
        warnings=build["warnings"],
        speakerNotes=setup_res.notes[:len(input_.slides)],
    )


async def _run_editable(driver: PptxExportDriver, input_: GenPptxInput,
                        setup_res, out_dir: str, *, debug: bool = False) -> GenPptxResult:
    """Editable 模式：capture tree → build editable pptx via python-pptx."""
    from .render.editable import build_editable_pptx
    from .debug import DebugCollector

    debug_col = DebugCollector.enable(out_dir) if debug else DebugCollector.disabled()

    captured_slides = []
    captures = []  # {hash, imagesWaited, imagesFailed} 给后续 validate
    warnings_start = 0  # 用于切片每张 slide 的 warnings delta

    for i, spec in enumerate(input_.slides):
        # 在 capture 前后记录 warnings 长度，切片出该 slide 的 warnings
        # （build_editable_pptx 接收的 warnings list 是共享的，先让 capture 阶段 0 warning；
        # build 阶段的 warning 在 build 之后统一算）
        try:
            cap = await driver.capture_editable(spec, input_.fontSwaps)
        except Exception as e:
            await debug_col.record_capture_failure(i, spec, e, driver)
            msg = stringify_error(e)
            return GenPptxResult(
                ok=False,
                error=(
                    f"slide {i + 1}/{len(input_.slides)} editable capture failed: {msg}"
                    + timeout_hint(msg, "editable", i + 1)
                ),
            )
        captured = cap['captured']
        # 把对应的讲稿贴上
        if i < len(setup_res.notes) and (setup_res.notes[i] or '').strip():
            captured.notes = setup_res.notes[i]
        captured_slides.append(captured)
        captures.append({
            'hash': cap['hash'],
            'imagesWaited': cap['imagesWaited'],
            'imagesFailed': cap['imagesFailed'],
        })
        # debug: capture 后立刻存证据（此时 DOM 还在 capture 状态）
        await debug_col.record_capture(i, spec, cap, driver)

    font_map = {p.from_: p.to for p in input_.fontSwaps} if input_.fontSwaps else None

    build = await build_editable_pptx(
        width=input_.width,
        height=input_.height,
        slides=captured_slides,
        resolve_media=driver.resolve_media,
        font_map=font_map,
    )

    saved_path = _write_output(build['bytes'], out_dir, input_.filename)

    # debug: 把 build 阶段的 warnings 切片到每张 slide + 抽 pptx 的 per-slide XML
    await debug_col.finalize(
        pptx_bytes=build['bytes'],
        pptx_path=saved_path,
        all_warnings=build['warnings'],
        warnings_start=warnings_start,
        slides=captured_slides,
        captures=captures,
        setup_res=setup_res,
        input_=input_,
    )

    per_slide = [
        SlideHashResult(
            hash_=c['hash'],
            imagesWaited=c['imagesWaited'],
            imagesFailed=c['imagesFailed'],
        )
        for c in captures
    ]
    flags = run_validate(setup_res, per_slide, captured_slides, input_, mode="editable")

    return GenPptxResult(
        ok=True,
        file=saved_path,
        slides=build['slides'],
        bytes=build['bytes_len'],
        flags=flags,
        warnings=build['warnings'],
        speakerNotes=setup_res.notes[:len(input_.slides)],
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _write_output(buf: bytes, out_dir: str, filename: Optional[str]) -> str:
    import time

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = f"export-{int(time.time())}.pptx"
    if not filename.endswith(".pptx"):
        filename += ".pptx"
    # Intentional deviation from TS output.ts:12（which 用 `/[^\w-]/g` 只保留
    # word chars + dash）。Python 这里额外保留 . 和 -，因为：
    # 1) 允许 . 才能保住 'export-1234567890.pptx' 的扩展名不被替换成 _pptx；
    # 2) 不允许空格 —— 空格在 shell 引用 / 上传到某些 backend 时是常见踩坑源；
    # 3) endswith('.pptx') 检查避免 TS 'foo.pptx' → 'foo.pptx.pptx' 的重复后缀。
    # 见 finding O9-1（推荐策略 B：文档化分歧 + 删空格）。
    safe = re.sub(r"[^\w.\-]", "_", filename)
    p = out / safe
    p.write_bytes(buf)
    return str(p)


# ---------------------------------------------------------------------------
# Screenshots-mode hash (djb2 over middle 4096 chars, used for dedup)
# ---------------------------------------------------------------------------

def _djb2_hash_middle(s: str) -> int:
    """对应 run.ts 的 djb2 over middle 4096 chars。"""
    v = 5381
    mid = len(s) >> 1
    for ch in s[mid:mid + 4096]:
        v = ((v << 5) + v + ord(ch)) & 0xFFFFFFFF
    return v
