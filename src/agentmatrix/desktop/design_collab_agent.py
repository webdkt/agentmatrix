"""
DesignCollabAgent — 设计协作 Agent。

在 BaseAgent 基础上，提供：
- 内置 in-process 静态 HTTP server，serve 自己的 work_files 根目录，
  用于预览设计产出（HTML / 多文件原型 / deck）。
- design 工具组 UI action（export_pptx 等）。

server 是 agent 的一部分（系统内本 agent 为单例），随 agent 首次激活启动，
serve runtime.paths.get_agent_work_base_dir(self.name)。URL 按 task_id 区分：
    http://localhost:<port>/<task_id>/output/index.html

agent 本身不碰 server / URL —— 只往 ~/current_task/output/ 写文件，
调 design_preview skill 的 refresh_preview / screenshot_preview / ask_user_question。
"""

import asyncio
import functools
import logging
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from .base_agent import BaseAgent


logger = logging.getLogger(__name__)


# 预览输出在 task 目录下的约定子路径
PREVIEW_OUTPUT_SUBDIR = "output"
PREVIEW_ENTRY_FILE = "index.html"


class _CorsDirHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler + CORS / iframe 友好响应头。

    前端 iframe 加载预览时需要这些头才能：
    - 跨源截图（fetch / drawImage 不被同源策略阻塞）
    - 被父页面 embed 而不被 X-Frame-Options 拦截
    """

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        # 不发 X-Frame-Options，允许任意 iframe embed
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


class _PreviewHTTPServer:
    """serve 一个根目录的常驻静态 HTTP server（daemon 线程）。

    线程模型：ThreadingHTTPServer 跑在 daemon 线程，不依赖 asyncio loop，
    避免 agent 主 loop 的耦合。端口探测 4311..4350，全部占用则交给 OS。
    """

    def __init__(self, root: Path, port_hint: int = 4311, port_range: int = 40):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.port = self._bind_port(port_hint, port_range)
        handler = functools.partial(_CorsDirHandler, directory=str(self.root))
        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), handler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(
            target=self._httpd.serve_forever, name="DesignPreviewHTTPServer", daemon=True
        )
        self._thread.start()
        logger.info(
            f"[DesignPreview] HTTP server started: http://127.0.0.1:{self.port}/ "
            f"(root={self.root})"
        )

    def _bind_port(self, hint: int, count: int) -> int:
        for offset in range(count):
            port = hint + offset
            try:
                with ThreadingHTTPServer(("127.0.0.1", port), SimpleHTTPRequestHandler) as probe:
                    pass  # 立即释放
                return port
            except OSError:
                continue
        # 全占用 → 让 OS 分配
        with ThreadingHTTPServer(("127.0.0.1", 0), SimpleHTTPRequestHandler) as probe:
            return probe.server_address[1]

    def stop(self):
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
            logger.info("[DesignPreview] HTTP server stopped")
        except Exception as e:
            logger.warning(f"[DesignPreview] stop error: {e}")


class DesignCollabAgent(BaseAgent):
    """设计协作 Agent —— 带内置预览 server。

    系统内单例。server 在首次激活 session 时启动，serve 自己的 work_files 根。
    """

    def __init__(self, profile, profile_path: str = None):
        super().__init__(profile, profile_path)
        self._preview_server: Optional[_PreviewHTTPServer] = None
        self.preview_port: Optional[int] = None

    # ========== runtime setter：runtime 注入即启动 server（单例，与 session 无关）==========

    @BaseAgent.runtime.setter
    def runtime(self, value):
        super(DesignCollabAgent, type(self)).runtime.fset(self, value)
        if value is not None:
            self._ensure_preview_server()

    def _ensure_preview_server(self):
        """启动预览 server（idempotent）。runtime 注入后 paths 即可用。"""
        if self._preview_server is not None:
            return
        if self.runtime is None or getattr(self.runtime, "paths", None) is None:
            logger.warning("[DesignPreview] runtime/paths 尚未就绪，server 延迟启动")
            return
        root = self.runtime.paths.get_agent_work_base_dir(self.name)
        try:
            self._preview_server = _PreviewHTTPServer(root)
            self.preview_port = self._preview_server.port
        except Exception as e:
            logger.error(f"[DesignPreview] 启动预览 server 失败: {e}")

    # ========== session 生命周期 ==========

    async def _on_activate_session(self, session: dict, first_signal=None):
        """激活 session：先跑基类逻辑（工作区切换等），再确保预览就绪。"""
        await super()._on_activate_session(session, first_signal)

        # 启动预览 server（首次）
        self._ensure_preview_server()

        # 确保 task 输出目录存在
        task_id = session.get("task_id") or self.current_task_id
        if task_id and self.runtime and getattr(self.runtime, "paths", None):
            try:
                out_dir = (
                    self.runtime.paths.get_agent_work_files_dir(self.name, task_id)
                    / PREVIEW_OUTPUT_SUBDIR
                )
                out_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.warning(f"[DesignPreview] 创建输出目录失败: {e}")

        # 回放预览入口：若该 session 之前调过 refresh_preview，把 entry_path
        # 再 emit 一次 design/refresh，让刚切回来的前端能恢复 iframe URL。
        # 这是 active session metadata 作为"agent 当前属性"的自然用法 ——
        # 不需要前端查 events，也不需要 user_sessions 表加字段。
        metadata = session.get("metadata") or {}
        entry_path = metadata.get("preview_entry_path")
        if entry_path:
            from ..core.signals import CoreEvent

            self.event_queue.put_nowait(CoreEvent(
                event_type="design",
                event_name="refresh",
                detail={
                    "task_id": task_id,
                    "entry_path": entry_path,
                    "preview_port": self.preview_port,
                },
                source=self.name,
                session_id=session.get("session_id"),
            ))

    # ========== UI schema ==========

    def get_ui_schema(self):
        base = super().get_ui_schema()
        design_group = {
            "name": "design",
            "icon": "palette",
            "children": [
                {
                    "action": "export_pptx",
                    "icon": "file-down",
                    "display_mode": "toast",
                },
            ],
        }
        return [design_group] + base

    async def export_pptx(self, **kwargs):
        """导出 PPTX —— 读 current_task/output/export.json，调本地 Python exporter。

        已从外部的 Node gen-pptx CLI 迁移到内置 Python 实现
        (skills/design_preview/pptx_export/)，复用 Playwright + python-pptx，
        不再需要用户端 npm install。

        Returns:
            dict: {ok, file?, slides?, bytes?, flags?, warnings?, error?}
        """
        import json

        task_id = getattr(self, "current_task_id", None)
        if not task_id:
            return {"ok": False, "error": "当前没有激活的 task / session"}

        out_dir = (
            self.runtime.paths.get_agent_work_files_dir(self.name, task_id)
            / PREVIEW_OUTPUT_SUBDIR
        )
        export_json = out_dir / "export.json"
        if not export_json.exists():
            return {
                "ok": False,
                "error": (
                    f"未找到 export 配置：{export_json}\n"
                    "请让 Designer Agent 先把导出配置写到 output/export.json。"
                ),
            }

        try:
            config = json.loads(export_json.read_text("utf-8"))
        except Exception as e:
            return {"ok": False, "error": f"export.json 解析失败：{e}"}

        preview_url = self.get_preview_url(task_id, f"{PREVIEW_OUTPUT_SUBDIR}/{PREVIEW_ENTRY_FILE}")
        if not preview_url:
            return {"ok": False, "error": "预览 server 未启动"}

        from .skills.design_preview.pptx_export import export_pptx as run_export
        logger.info(f"[DesignPreview] export_pptx (python) url={preview_url} mode={config.get('mode')}")
        result = await run_export(
            url=preview_url,
            config=config,
            out_dir=str(out_dir),
            filename=config.get("filename"),
        )
        return result.to_dict()

    # ========== 预览 URL ==========

    def get_preview_url(self, task_id: str, relative_path: str = None) -> Optional[str]:
        """拼出某个 task 的预览 URL。

        Args:
            task_id: 当前 task / session 的 task_id
            relative_path: 相对 task 目录的文件路径，默认 output/index.html
        """
        self._ensure_preview_server()
        if not self.preview_port:
            return None
        rel = relative_path or f"{PREVIEW_OUTPUT_SUBDIR}/{PREVIEW_ENTRY_FILE}"
        rel = rel.lstrip("/")
        return f"http://127.0.0.1:{self.preview_port}/{task_id}/{rel}"

    # ========== 截图（Playwright headless 渲染） ==========

    async def take_preview_screenshot(self, url: str) -> Optional[str]:
        """用 Playwright 启动 headless Chrome 渲染 url，截图 → 落盘。

        Returns: 容器内路径（如 `~/current_task/output/_screenshots/<ts>.png`），失败返回 None。
        不再投递 ScreenshotSignal —— action 同步返回路径，由 LLM 自己决定是否 look() 查看。
        """
        try:
            png_bytes = await _PlaywrightManager.default().screenshot(url)
        except Exception as e:
            logger.error(f"[DesignPreview] Playwright 截图失败 ({url}): {e}")
            return None
        if not png_bytes:
            return None

        import time

        task_id = getattr(self, "current_task_id", None)
        if not task_id or not self.runtime or getattr(self.runtime, "paths", None) is None:
            logger.warning("[DesignPreview] take_preview_screenshot: no active task / runtime")
            return None

        shots_dir = (
            self.runtime.paths.get_agent_work_files_dir(self.name, task_id)
            / PREVIEW_OUTPUT_SUBDIR
            / "_screenshots"
        )
        shots_dir.mkdir(parents=True, exist_ok=True)
        host_path = shots_dir / f"{int(time.time() * 1000)}.png"
        try:
            host_path.write_bytes(png_bytes)
        except Exception as e:
            logger.warning(f"[DesignPreview] 截图落盘失败: {e}")
            return None

        # 容器内路径 —— 与 agent 全程使用的 `~/current_task/...` 约定一致，
        # vision skill 的 look() 能正确映射回 host。
        return f"~/current_task/{PREVIEW_OUTPUT_SUBDIR}/_screenshots/{host_path.name}"

    # ========== 清理 ==========

    def _on_stop(self):
        super()._on_stop()
        if self._preview_server is not None:
            self._preview_server.stop()
            self._preview_server = None
        # 异步关 Playwright —— fire-and-forget，避免阻塞 stop
        try:
            mgr = _PlaywrightManager.default()
            asyncio.create_task(mgr.aclose())
        except Exception:
            pass


class _PlaywrightManager:
    """单例：lazy 启动 Playwright + 一个常驻 headless browser，所有截图共用。

    优先用系统装的 Chrome（channel='chrome'），失败 fallback 到 Playwright 自带 Chromium。
    每次 screenshot 只 new_page → goto → screenshot → close，~100ms 一张。
    """

    _instance: Optional["_PlaywrightManager"] = None

    @classmethod
    def default(cls) -> "_PlaywrightManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        from playwright.async_api import async_playwright

        self._async_playwright = async_playwright()
        self._pw = None             # Playwright 实例
        self._browser = None        # 常驻 browser
        self._lock = asyncio.Lock()
        self._start_attempted = False
        self._start_error: Optional[str] = None

    async def _ensure_started(self):
        if self._browser is not None:
            return
        async with self._lock:
            if self._browser is not None:
                return
            if self._start_attempted:
                raise RuntimeError(
                    "渲染引擎启动失败：未检测到 Google Chrome。\n"
                    "请安装 Google Chrome（https://www.google.com/chrome/）后重试。"
                )
            self._start_attempted = True
            try:
                self._pw = await self._async_playwright.start()
                # 优先用系统 Chrome（无需下载 Chromium），失败再 fallback
                chrome_err = None
                try:
                    self._browser = await self._pw.chromium.launch(channel="chrome")
                    logger.info("[DesignPreview] Playwright 已启动 (channel=chrome)")
                except Exception as e_chrome:
                    chrome_err = e_chrome
                    logger.warning(
                        f"[DesignPreview] 系统 Chrome 启动失败，尝试 bundled chromium: {e_chrome}"
                    )
                    try:
                        self._browser = await self._pw.chromium.launch()
                        logger.info("[DesignPreview] Playwright 已启动 (bundled chromium)")
                    except Exception:
                        # 两个都失败：抛出对用户友好的错误（包含 Chrome 路径线索）
                        raise RuntimeError(
                            "渲染引擎启动失败：未检测到 Google Chrome。\n"
                            "请安装 Google Chrome（https://www.google.com/chrome/）后重试。"
                        ) from chrome_err
            except RuntimeError:
                raise
            except Exception as e:
                self._start_error = str(e)
                logger.error(f"[DesignPreview] Playwright 启动失败: {e}")
                raise

    async def screenshot(self, url: str, viewport_width: int = 1280,
                         viewport_height: int = 800,
                         wait_ms: int = 300) -> bytes:
        """对 url 截图，返回 PNG bytes。"""
        await self._ensure_started()
        page = await self._browser.new_page(
            viewport={"width": viewport_width, "height": viewport_height}
        )
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
            # networkidle 之后再多给一点时间，覆盖懒加载 / webfont / 异步 hydration
            if wait_ms > 0:
                await page.wait_for_timeout(wait_ms)
            return await page.screenshot(full_page=True, type="png")
        finally:
            try:
                await page.close()
            except Exception:
                pass

    async def new_page(self, viewport: Optional[dict] = None,
                       device_scale_factor: float = 1.0,
                       timeout_ms: int = 30000):
        """在共享 browser 上开新 page，供需要自定义流程的调用方使用（如 pptx 导出）。

        Caller 负责 page.close()。viewport 形如 {"width": 1280, "height": 720}。
        """
        await self._ensure_started()
        ctx_kwargs = {}
        if viewport is not None:
            ctx_kwargs["viewport"] = viewport
        if device_scale_factor != 1.0:
            ctx_kwargs["device_scale_factor"] = device_scale_factor
        # 每次新建独立 context，避免 CSS / font-face / cookie 串台
        ctx = await self._browser.new_context(**ctx_kwargs)
        page = await ctx.new_page()
        page.set_default_timeout(timeout_ms)
        # 把 ctx 也绑到 page 上，方便 close 时一并关
        page._agentmatrix_ctx = ctx
        return page

    @staticmethod
    async def close_page(page):
        """关掉 new_page 出来的 page + 它的 context。"""
        ctx = getattr(page, "_agentmatrix_ctx", None)
        try:
            await page.close()
        except Exception:
            pass
        if ctx is not None:
            try:
                await ctx.close()
            except Exception:
                pass

    async def aclose(self):
        try:
            if self._browser is not None:
                await self._browser.close()
        except Exception:
            pass
        try:
            if self._pw is not None:
                await self._pw.stop()
        except Exception:
            pass
        self._browser = None
        self._pw = None
        _PlaywrightManager._instance = None
