"""
Playwright driver: 在共享 browser 上开 page，注入 capture bundle，drive setup/capture/resolveMedia。

对应 gen-pptx 的 src/orchestrator/{driver,inject}.ts。Browser 来自
design_collab_agent._PlaywrightManager（截图 & pptx 导出共享一个 Chrome 实例）。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional

from .types import (
    CapturedSlide, FontSwap, GenPptxInput, MediaRef, ResolvedMedia,
    SetupResult, SlideNode, SlideSpec,
)

# capture.iife.js 在包内 assets/，预构建（原项目 npm run build:page 产出）
_CAPTURE_BUNDLE_PATH = Path(__file__).parent / "assets" / "capture.iife.js"
_CAPTURE_SOURCE_CACHE: Optional[str] = None


def _load_capture_bundle() -> str:
    global _CAPTURE_SOURCE_CACHE
    if _CAPTURE_SOURCE_CACHE is None:
        _CAPTURE_SOURCE_CACHE = _CAPTURE_BUNDLE_PATH.read_text("utf-8")
    return _CAPTURE_SOURCE_CACHE


def _capture_budget(spec: SlideSpec) -> int:
    """mirrors inject.ts::captureBudget：15000 + (delay ?? 600)。"""
    d = spec.delay if isinstance(spec.delay, (int, float)) else 600
    return 15000 + int(d)


async def _evaluate_with_timeout(coro, ms: int, label: str):
    """page.evaluate() 包一层超时，防 runaway showJs / animation。"""
    try:
        return await asyncio.wait_for(coro, timeout=ms / 1000.0)
    except asyncio.TimeoutError as e:
        raise RuntimeError(f"{label} timed out after {ms}ms") from e


class PptxExportDriver:
    """共享 browser + 一个新 context（独立 viewport / device scale）。"""

    def __init__(self, page, browser_manager):
        self.page = page
        self._browser_manager = browser_manager  # 用于 close

    @classmethod
    async def launch(cls, url: str, input_: GenPptxInput) -> "PptxExportDriver":
        # 延迟 import 避免循环
        from agentmatrix.desktop.design_collab_agent import _PlaywrightManager
        mgr = _PlaywrightManager.default()
        mode = input_.mode or "editable"
        # screenshots 模式 2x DPI 锐化；editable 只需要坐标，1x 即可
        dsf = 2.0 if mode == "screenshots" else 1.0
        page = await mgr.new_page(
            viewport={"width": input_.width, "height": input_.height},
            device_scale_factor=dsf,
            timeout_ms=30000,
        )
        driver = cls(page, mgr)
        try:
            await page.goto(url, wait_until="load", timeout=30000)
        except Exception:
            await driver.close()
            raise
        return driver

    async def close(self):
        from agentmatrix.desktop.design_collab_agent import _PlaywrightManager
        await _PlaywrightManager.close_page(self.page)
        self.page = None

    # ----- capture bundle injection -----

    async def inject_capture_bundle(self):
        await self.page.add_script_tag(content=_load_capture_bundle())
        ok = await self.page.evaluate(
            "() => typeof window.__genpptx === 'object'"
        )
        if not ok:
            raise RuntimeError("capture bundle failed to initialise window.__genpptx")

    # ----- typed wrappers around window.__genpptx -----

    async def setup(self, input_: GenPptxInput) -> SetupResult:
        mode = input_.mode or "editable"
        arg = {
            "mode": mode,
            "width": input_.width,
            "height": input_.height,
            "hideSelectors": input_.hideSelectors,
            "googleFontImports": input_.googleFontImports,
            "fontSwaps": [p.to_dict() for p in input_.fontSwaps],
            # screenshots 模式忽略 resetTransformSelector（与原项目一致）
            "resetTransformSelector": (
                None if mode == "screenshots" else input_.resetTransformSelector
            ),
        }
        raw = await _evaluate_with_timeout(
            self.page.evaluate(
                "(arg) => window.__genpptx.setup(arg)", arg
            ),
            15000,
            "setup",
        )
        return SetupResult.from_dict(raw or {})

    async def capture_screenshot(self, spec: SlideSpec):
        """对应 __genpptx.captureScreenshot —— 只在页面里跑 showJs + settle，
        真正的 screenshot 通过 driver.screenshot() 拿。"""
        await _evaluate_with_timeout(
            self.page.evaluate(
                "(s) => window.__genpptx.captureScreenshot(s)",
                {"showJs": spec.showJs, "selector": spec.selector, "delay": spec.delay},
            ),
            _capture_budget(spec),
            "screenshot capture",
        )

    async def screenshot_data_url(self) -> str:
        """全 viewport PNG，返回 data:image/png;base64,... URL。"""
        buf = await self.page.screenshot(type="png")
        import base64
        return "data:image/png;base64," + base64.b64encode(buf).decode("ascii")

    async def capture_editable(self, spec: SlideSpec, font_swaps):
        """对应 __genpptx.captureEditable —— returns dict
        {captured: CapturedSlide, hash, imagesWaited, imagesFailed}."""
        from .types import Rect
        raw = await _evaluate_with_timeout(
            self.page.evaluate(
                "([s, f]) => window.__genpptx.captureEditable(s, f)",
                [
                    {"showJs": spec.showJs, "selector": spec.selector, "delay": spec.delay},
                    [p.to_dict() for p in font_swaps],
                ],
            ),
            _capture_budget(spec),
            "editable capture",
        )
        raw = raw or {}
        slide_raw = raw.get('slide') or {}
        root_raw = slide_raw.get('root') or {}
        captured = CapturedSlide(
            rect=Rect.from_dict(slide_raw.get('rect') or {}),
            root=SlideNode.from_dict(root_raw) if root_raw else None,
            notes=None,
        )
        return {
            'captured': captured,
            'hash': int(raw.get('hash', 0) or 0),
            'imagesWaited': int(raw.get('imagesWaited', 0) or 0),
            'imagesFailed': int(raw.get('imagesFailed', 0) or 0),
        }

    async def resolve_media(self, refs):
        if not refs:
            return []
        raw = await self.page.evaluate(
            "(r) => window.__genpptx.resolveMedia(r)",
            [r.to_dict() for r in refs],
        )
        return [ResolvedMedia.from_dict(d) for d in (raw or [])]

    async def set_viewport_size(self, width: int, height: int):
        await self.page.set_viewport_size({"width": width, "height": height})

    async def raf_settle(self):
        """双 rAF，等一帧布局稳定（screenshots 模式 setup 前）。"""
        await self.page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r())))"
        )
