"""
基于 DrissionPage 库的 BrowserAdapter 实现类。

该实现使用 DrissionPage 的 ChromiumPage 来提供浏览器自动化功能。
支持使用指定的 Chrome profile 路径启动浏览器。
"""

from typing import List, Optional, Any, Union, Tuple
import time
import os
import hashlib

import uuid
from pathlib import Path
from urllib.parse import urlparse, unquote
from .browser_adapter import (
    BrowserAdapter,
    TabHandle,
    PageElement,
    ElementType,
    PageType,
    InteractionReport,
    PageSnapshot,
    KeyAction,
)
from ...core.log_util import AutoLoggerMixin
from DrissionPage import ChromiumPage, ChromiumOptions
import asyncio, random
import trafilatura
import logging


class DrissionPageElement(PageElement):
    """
    基于 DrissionPage 的 ChromiumElement 的 PageElement 实现类。
    """

    def __init__(self, chromium_element):
        """
        初始化 DrissionPageElement。

        Args:
            chromium_element: DrissionPage 的 ChromiumElement 对象
        """
        self._element = chromium_element

    def get_text(self) -> str:
        """获取元素的可见文本 (用于小脑判断)"""
        return self._element.text

    def get_tag_name(self) -> str:
        """获取元素的标签名 (a, button, div)"""
        return self._element.tag.lower()

    def get_element(self) -> Any:
        """获取元素对象 (ChromiumElement)"""
        return self._element

    def is_visible(self) -> bool:
        """元素是否可见"""
        return self._element.states.is_displayed


class DrissionPageAdapter(BrowserAdapter, AutoLoggerMixin):
    """
    基于 DrissionPage 库的浏览器适配器实现。

    使用 DrissionPage 的 ChromiumPage 来驱动 Chrome 浏览器。
    支持指定 Chrome profile 路径来实现会话持久化。
    """

    _custom_log_level = logging.DEBUG

    def __init__(
        self, profile_path: Optional[str] = None, download_path: Optional[str] = None
    ):
        """
        初始化 DrissionPage 适配器。

        Args:
            profile_path: Chrome profile 的路径。如果提供，将以该路径为 profile 启动 Chrome。
            download_path: 下载文件的保存路径。如果提供，浏览器下载的文件将保存到此目录。
        """
        self.profile_path = profile_path
        self.download_path = download_path

        # 确保下载目录存在
        if self.download_path and not os.path.exists(self.download_path):
            os.makedirs(self.download_path, exist_ok=True)

        self.browser: Optional[Any] = None

    def _hash_path_to_port(self, profile_path: str) -> int:
        """
        根据 profile_path 生成唯一端口号（9200-9500 范围）

        这样可以确保：
        - 相同的 profile_path 总是生成相同的端口 → 浏览器复用
        - 不同的 profile_path 生成不同的端口 → 真正隔离

        Args:
            profile_path: Chrome 用户数据目录路径

        Returns:
            int: 端口号（9200-9500 范围内）
        """
        hash_val = int(hashlib.md5(profile_path.encode()).hexdigest(), 16)
        return 9200 + (hash_val % 300)

    async def start(self, headless: bool = False):
        """
        启动浏览器进程。

        Args:
            headless: 是否以无头模式启动浏览器
        """
        os.environ["no_proxy"] = "localhost,127.0.0.1"

        # 根据 profile_path 生成唯一端口，实现不同 agent 的隔离
        port = self._hash_path_to_port(self.profile_path)

        co = ChromiumOptions()
        co.set_user_data_path(self.profile_path)
        co.set_local_port(port)  # 关键：为每个 agent 分配独立端口

        # 配置下载路径
        if self.download_path:
            co.set_download_path(self.download_path)

        if headless:
            co.headless()

        # 在线程池中创建浏览器实例
        self.browser = await asyncio.to_thread(ChromiumPage, addr_or_opts=co)

    async def start_with_system_profile(
        self, headless: bool = False, use_auto_port: bool = False
    ):
        """
        使用系统默认 Chrome profile 启动浏览器。

        与 start() 方法的区别：
        - start(): 使用自定义 profile_path，生成唯一端口，适合隔离环境
        - start_with_system_profile(): 使用系统默认 profile，使用 DrissionPage 默认配置，
          可以连接到已打开的浏览器，适合需要复用用户数据的场景

        Args:
            headless: 是否以无头模式启动浏览器
            use_auto_port: 是否使用自动分配端口（True）或默认端口 9222（False）
                - True: 自动分配端口，创建新的浏览器实例，不会冲突
                - False: 使用默认端口 9222，可以连接已打开的浏览器（前提是该浏览器用 --remote-debugging-port=9222 启动）

        使用说明：
        - 如果要连接已打开的浏览器：
          1. 确保浏览器用 --remote-debugging-port=9222 启动
          2. 设置 use_auto_port=False
        - 如果要创建新的浏览器实例：
          1. 设置 use_auto_port=True
          2. 会自动分配空闲端口并使用系统用户数据
        """
        os.environ["no_proxy"] = "localhost,127.0.0.1"

        # 使用系统默认用户文件夹
        # 这样可以连接到已经打开的浏览器，或者启动新的使用系统 profile 的浏览器
        co = ChromiumOptions().use_system_user_path()

        # 如果使用自动端口
        if use_auto_port:
            co.auto_port()

        # 配置下载路径（如果指定了）
        if self.download_path:
            co.set_download_path(self.download_path)

        if headless:
            co.headless()

        # 在线程池中创建浏览器实例
        # DrissionPage 会使用默认端口 9222，可以连接到已打开的浏览器
        self.browser = await asyncio.to_thread(ChromiumPage, addr_or_opts=co)

    async def close(self):
        """关闭浏览器进程并清理资源"""
        if self.browser:
            try:
                # 在线程池中关闭浏览器
                await asyncio.to_thread(self.browser.quit)
            except Exception:
                # 忽略关闭时的异常
                self.logger.exception("Error closing browser")
                pass
            finally:
                self.browser = None

    # --- Tab Management (标签页管理) ---
    async def create_tab(self, url: Optional[str] = None) -> TabHandle:
        """打开一个新的标签页，返回句柄"""
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first.")

        # 在线程池中创建新标签页
        new_tab = await asyncio.to_thread(self.browser.new_tab)

        # 如果提供了 URL，导航到该 URL
        if url:
            await asyncio.to_thread(new_tab.get, url)
            await asyncio.sleep(0.5)  # 等待页面初始化

        self.logger.info(f"Created new tab{' with URL: ' + url if url else ''}")
        return new_tab

    async def close_tab(self, tab: TabHandle):
        """关闭指定的标签页"""
        if not tab:
            return
        try:
            await asyncio.to_thread(tab.close)
        except Exception:
            self.logger.warning(f"Failed to close tab")

    async def get_tab(self) -> TabHandle:
        """获取当前焦点标签页的句柄"""
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first.")

        # 在线程池中获取所有标签页
        all_tabs = await asyncio.to_thread(self.browser.get_tabs)

        # 过滤掉 chrome extension 的 tab（如 PDF viewer）
        normal_tabs = []
        for tab in all_tabs:
            try:
                url = tab.url if hasattr(tab, "url") else ""
                # 保留 URL 不是 chrome-extension:// 的 tab
                if url and not url.startswith("chrome-extension://"):
                    normal_tabs.append(tab)
            except Exception:
                # 如果获取 URL 失败，保留这个 tab（可能是新创建的空白 tab）
                normal_tabs.append(tab)

        # 如果找到正常的 tab，返回最新的
        if normal_tabs:
            self.logger.debug(
                f"Found {len(normal_tabs)} normal tab(s) out of {len(all_tabs)} total tabs"
            )
            return normal_tabs[-1]  # 最新的 tab

        # 如果找不到正常的 tab，创建一个新的
        self.logger.warning(
            f"No normal tab found (all {len(all_tabs)} tabs are chrome-extension), creating a new tab"
        )
        return await self.create_tab()

    def get_tab_url(self, tab):
        return tab.url

    async def switch_to_tab(self, tab: TabHandle):
        """将浏览器焦点切换到指定标签页 (模拟人类视线)"""
        # TODO: 实现切换标签页的逻辑
        pass

    # --- Navigation & Content (导航与内容获取) ---
    async def navigate(self, tab: TabHandle, url: str) -> InteractionReport:
        """
        在指定 Tab 访问 URL。
        注意：Navigate 也可能触发下载 (如直接访问 pdf 链接)，因此返回 InteractionReport。
        """
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first.")

        try:
            # 记录导航前的URL
            old_url = tab.url if hasattr(tab, "url") else ""

            # 在线程池中执行导航
            await asyncio.to_thread(tab.get, url)

            # 使用异步睡眠
            await asyncio.sleep(2)  # 等待页面加载

            # 检查URL是否改变
            new_url = tab.url if hasattr(tab, "url") else ""
            is_url_changed = old_url != new_url

            # 创建交互报告
            report = InteractionReport(
                is_url_changed=is_url_changed,
                is_dom_changed=is_url_changed,  # URL改变通常意味着DOM也改变了
            )

            return report

        except Exception as e:
            self.logger.exception(f"Navigation failed for URL: {url}")
            return InteractionReport(error=f"Navigation failed: {str(e)}")

    async def _wait_for_dom_ready(self, tab: TabHandle, timeout: int = 10):
        """
        等待 DOM 完全加载。
        """
        if not tab:
            tab = await self.get_tab()

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 检查页面加载状态
                if hasattr(tab.states, "ready_state"):
                    if tab.states.ready_state == "complete":
                        self.logger.info("DOM is ready (complete)")
                        return True

                # 备用检查：尝试访问 body 元素
                body = tab.ele("body", timeout=0.5)
                if body:
                    self.logger.info("DOM is ready (body found)")
                    return True

            except Exception as e:
                self.logger.debug(f"DOM not ready yet: {e}")

            await asyncio.sleep(0.5)

        self.logger.warning(f"DOM ready timeout after {timeout} seconds")
        return False

    async def stabilize(self, tab: TabHandle):
        """
        优化后的页面稳定化：快速、无等待查找、JS 注入处理。
        """
        if not tab:
            return False

        url = tab.url
        self.logger.info(f"⚓ Fast Stabilizing: {url}")

        # 1. 放入线程池执行整体逻辑，而不是每一步都切线程
        # DrissionPage 的操作是同步阻塞的，所以我们将整个 stabilize 包裹起来
        return await asyncio.to_thread(self._sync_stabilize_logic, tab)

    def _sync_stabilize_logic(self, tab: TabHandle):
        """
        同步逻辑核心，由外部 async 包装，内部不再到处 await。
        """
        try:
            # === 步骤 1: 快速加载 ===
            # 等待 DOM 加载，最多 10 秒，超时就不等了直接干
            tab.wait.doc_loaded(timeout=10)

            # === 步骤 2: 第一次弹窗清理 (针对 Cookie 遮挡) ===
            self._fast_kill_popups(tab)

            # === 步骤 3: 快速滚动触发 Lazy Load ===
            # 不要慢慢滑，快速到底再回滚
            self.logger.info("⚡ Scrolling...")

            # 获取页面高度
            total_height = tab.run_js("return document.body.scrollHeight")
            viewport_height = tab.run_js("return window.innerHeight")

            # 优化滚动：每 800px 滚一次，每次只停 0.1-0.2 秒，足够触发网络请求了
            # 如果页面太长（超过 20000px），限制滚动次数，防止死循环
            max_scrolls = 30
            current_pos = 0

            for _ in range(max_scrolls):
                current_pos += 800
                tab.scroll.to_location(0, current_pos)
                time.sleep(0.15)  # 极短等待，仅为了触发 JS 事件

                # 每滚几下检查一次是否有新弹窗挡路
                if _ % 5 == 0:
                    self._fast_kill_popups(tab)

                # 检查是否到底
                if current_pos >= total_height:
                    # 更新高度（应对无限滚动）
                    new_height = tab.run_js("return document.body.scrollHeight")
                    if new_height <= total_height:
                        break  # 真的到底了
                    total_height = new_height

            # === 步骤 4: 最终清理与复位 ===
            self._fast_kill_popups(tab)
            tab.scroll.to_top()
            time.sleep(0.5)  # 给页面喘息时间重绘

            self.logger.info("✅ Page stabilized (Optimized).")
            return True

        except Exception as e:
            self.logger.error(f"Stabilize logic error: {e}")
            return False

    def _fast_kill_popups(self, tab: TabHandle):
        """
        使用混合策略秒杀弹窗
        """
        # 关键词库（用于策略 B）
        accept_keywords = [
            "accept",
            "agree",
            "allow",
            "consent",
            "got it",
            "i understand",
            "接受",
            "同意",
            "知道了",
            "确认",
        ]

        # 策略 A: JS 注入点击 (最快，最准)
        # 优先点击 "接受" 类按钮
        # 注意：DrissionPage 的 run_js 不支持传递 Python list，所以将关键词直接硬编码到 JS 中
        accept_keywords_js = '["accept", "agree", "allow", "consent", "got it", "i understand", "接受", "同意", "知道了", "确认"]'

        js_click_accept = f"""
        () => {{
            const keywords = {accept_keywords_js};
            const buttons = Array.from(document.querySelectorAll('button, a, div[role="button"], input[type="button"], input[type="submit"]'));
            for (const btn of buttons) {{
                // 必须是可见的
                const style = window.getComputedStyle(btn);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0' || btn.offsetParent === null) continue;

                const text = (btn.innerText || btn.textContent || '').toLowerCase().trim();
                // 检查文本是否包含关键词
                if (keywords.some(k => text.includes(k))) {{
                    console.log('Auto-clicking:', text);
                    btn.click();
                    return true; // 点了一个就跑，避免多点
                }}
            }}
            return false;
        }}
        """

        clicked = tab.run_js(js_click_accept)
        if clicked:
            self.logger.info("🔫 JS Clicked an 'Accept' button.")
            time.sleep(0.5)  # 点完等一下动画
            return

        # 策略 B: 处理常见的 Shadow DOM 或 iframe 中的 Cookie 栏
        # DrissionPage 可以在整个 DOM (包括 shadow-root) 中查找
        # 使用 @@text() 语法非常快
        try:
            # 查找没有 ID/Class 但含有特定文本的按钮
            for kw in accept_keywords:
                # 查找包含文本的 visible 按钮，timeout 为 0.1 表示不等待，找不到立刻过
                btn = tab.ele(
                    f"tag:button@@text():{kw}@@css:visibility!=hidden", timeout=0.1
                )
                if btn and btn.states.is_displayed:
                    btn.click(by_js=True)  # JS 点击穿透力更强
                    self.logger.info(f"🔫 DP Clicked 'Accept': {kw}")
                    time.sleep(0.5)
                    return
        except:
            pass

        # 策略 C: 暴力关闭 (针对 X 号)
        # 只有在找不到 "同意" 的时候才找 "关闭"，因为有些网点关闭等于拒绝，导致一直弹窗
        close_selectors = [
            '[aria-label="Close"]',
            ".close-icon",
            "button.close",
            'div[class*="close"]',  # 风险较大，但在循环末尾可以尝试
        ]

        try:
            for selector in close_selectors:
                # timeout=0 是关键，瞬间检查，不存在就下一个
                btn = tab.ele(selector, timeout=0)
                if btn and btn.states.is_displayed:
                    btn.click(by_js=True)
                    self.logger.info(f"🔫 Clicked Close Button: {selector}")
                    time.sleep(0.2)
                    break
        except:
            pass

        # 策略 D: 移除常见的遮挡层 (如果无法点击，直接删 DOM)
        # 慎用，可能会把页面弄坏，但对于纯采集任务通常可以接受
        # tab.run_js("""
        #     document.querySelectorAll('.modal-backdrop, .overlay').forEach(e => e.remove());
        #     document.body.style.overflow = 'auto'; // 恢复滚动
        # """)

    async def _handle_popups(self, tab: TabHandle):
        """
        智能弹窗处理：基于文本语义和元素属性，而非死板的 CSS 选择器。
        DrissionPage 的优势在于它可以极快地获取元素文本。
        """
        # 1. 定义我们想点击的“关键词”
        # 这些词通常出现在 Consent 弹窗的按钮上
        allow_keywords = [
            "accept",
            "agree",
            "allow",
            "consent",
            "i understand",
            "got it",
            "cookie",
            "接受",
            "同意",
            "知道",
        ]
        # 这些词出现在关闭按钮上
        close_keywords = ["close", "later", "no thanks", "not now", "关闭", "取消"]

        # 2. 查找页面上所有可能是“遮挡层”中的按钮
        # 策略：查找所有 z-index 很高 或者 position fixed 的容器里的按钮
        # 但这太慢。

        # 简易策略：直接找页面上可见的、包含上述关键词的 BUTTON 或 A 标签
        # 并且只处理那些看起来像是在“浮层”里的 (通过简单的 JS 判断，或者不做判断直接盲点风险较大)

        # 安全策略：只针对常见的 ID/Class 模式进行精确打击
        # 结合你原来的逻辑，但做简化

        common_popup_close_selectors = [
            'button[aria-label="Close"]',
            'button[class*="close"]',
            ".close-icon",
            '[id*="cookie"] button',  # Cookie 栏里的按钮通常都是要点的
            '[class*="consent"] button',
        ]

        try:
            for selector in common_popup_close_selectors:
                # 在线程池中查找可见的元素
                eles = await asyncio.to_thread(tab.eles, selector, timeout=2)
                for ele in eles:
                    # 在线程池中检查是否可见
                    is_displayed = await asyncio.to_thread(
                        lambda: ele.states.is_displayed
                    )
                    if is_displayed:
                        # 在线程池中检查文本是否匹配"拒绝"或"关闭"或"同意"
                        txt = await asyncio.to_thread(lambda: ele.text.lower())
                        # 如果是 Cookie 区域的按钮，通常点第一个可见的就行（大概率是 Accept）
                        if "cookie" in selector or "consent" in selector:
                            await asyncio.to_thread(
                                ele.click, by_js=True
                            )  # 用 JS 点更稳，不会被遮挡
                            self.logger.info(f"Clicked cookie consent: {txt}")
                            await asyncio.sleep(0.5)
                            return True

                        # 如果是关闭按钮
                        if (
                            any(k in txt for k in close_keywords) or not txt
                        ):  # 有些关闭按钮没字，只有X
                            await asyncio.to_thread(ele.click, by_js=True)
                            self.logger.info(f"Clicked popup close: {selector}")
                            await asyncio.sleep(0.5)
                            return True

        except Exception:
            pass

        return False

    async def get_page_snapshot(self, tab: TabHandle) -> PageSnapshot:
        """
        [Phase 3] 获取页面内容供小脑阅读。
        智能提取正文，过滤噪音。
        """
        if not tab:
            raise ValueError("Tab handle is None")

        url = tab.url
        title = tab.title

        # 1. 判断内容类型 (HTML? Static Asset?)
        content_type = await self.analyze_page_type(tab)

        # 2. 如果是静态资源，使用专门的静态资源处理
        if content_type == PageType.STATIC_ASSET:
            return await self._get_static_asset_snapshot(tab, url, title, content_type)

        # 3. HTML 正文提取 (核心逻辑)
        # 在线程池中获取当前渲染后的 HTML (包含 JS 执行后的结果)
        raw_html = await asyncio.to_thread(lambda: tab.html)

        # A. 尝试使用 Trafilatura 提取高质量 Markdown
        # include_links=True: 保留正文里的链接，这对小脑判断"是否有价值的引用"很有用
        # include_formatting=True: 保留加粗、标题等
        extracted_text = trafilatura.extract(
            raw_html,
            include_links=True,
            include_formatting=True,
            output_format="markdown",
            url=url,  # 传入 URL 有助于 trafilatura 处理相对路径
        )

        # B. 备选方案 (Fallback)
        if not extracted_text or len(extracted_text) < 50:
            self.logger.info(
                f"Trafilatura extraction failed or too short for {url}, falling back to simple cleaning."
            )
            extracted_text = await self._fallback_text_extraction(tab)

        # 4. 最终组装
        # 可以在这里加一个 Token 截断，比如保留前 15000 字符，
        # 因为用来做“价值判断”不需要读完几万字的长文。
        final_text = extracted_text[:20000]

        return PageSnapshot(
            url=url,
            title=title,
            content_type=content_type,
            main_text=final_text,
            raw_html=raw_html[:2000],  # 只保留一点点头部 HTML 用于 debug，不需要全存
        )

    async def analyze_page_type(self, tab: TabHandle) -> PageType:
        """
        判断页面类型。
        Chrome 浏览器打开 PDF 时，DOM 结构非常特殊。
        """
        try:
            # 1. 检查 URL 特征
            url = tab.url.lower()
            if (
                url == "about:blank"
                or url.startswith("chrome://")
                or url.startswith("data:")
            ):
                self.logger.warning(f"⚠️ Empty/System URL detected: {url}")
                return PageType.ERRO_PAGE

            # 2. 检查 Title 特征 (HTTP 错误通常会反映在标题)
            title = tab.title.lower()
            error_keywords = [
                "404 not found",
                "page not found",
                "500 internal server error",
                "502 bad gateway",
                "site can't be reached",
                "privacy error",
                "无法访问",
                "找不到页面",
                "服务器错误",
                "网站无法连接",
            ]
            if any(k in title for k in error_keywords):
                self.logger.warning(f"⚠️ Error Page Title detected: {title}")
                return PageType.ERRO_PAGE

            # 1. 在线程池中获取 MIME Type
            # 这里的 timeout 要极短，因为如果页面还在加载，我们不希望卡住，
            # 但通常 contentType 是 header 返回后就有的
            content_type = await asyncio.to_thread(
                lambda: tab.run_js("return document.contentType;", timeout=1)
            )
            content_type = content_type.lower() if content_type else ""

            # 2. 判定逻辑
            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                # 特殊情况：有时服务器配置错误，把 JSON 当 HTML 发，
                # 或者这是个纯展示代码的 HTML 页。
                # 但一般按 HTML 处理没错，大不了 Scout 不出东西。
                return PageType.NAVIGABLE

            # 常见的非 HTML 类型
            if any(
                t in content_type
                for t in [
                    "application/pdf",
                    "image/",
                    "text/plain",
                    "application/json",
                    "text/xml",
                ]
            ):
                return PageType.STATIC_ASSET

            # 3. 兜底：如果 JS 失败（比如 XML 有时不能运行 JS），回退到 URL 后缀
            url = tab.url.lower()
            if any(
                url.endswith(ext)
                for ext in [".pdf", ".jpg", ".png", ".json", ".xml", ".txt"]
            ):
                return PageType.STATIC_ASSET

            # 默认视为网页
            return PageType.NAVIGABLE

        except Exception:
            # 如果出错了（比如页面卡死），保守起见当作网页处理，或者根据 URL 判
            return PageType.NAVIGABLE

    async def _fallback_text_extraction(self, tab: TabHandle) -> str:
        """
        当智能提取失败时，使用 DrissionPage 暴力提取可见文本。
        并做简单的清洗。
        """
        # 移除 script, style 等无关标签
        # DrissionPage 的 .text 属性其实已经处理了大部分，但我们可以更彻底一点
        try:
            # 在线程池中获取 body 元素
            body = await asyncio.to_thread(tab.ele, "tag:body")

            # 在线程池中获取文本，这里的 text 获取的是 "innerText"，即用户可见的文本
            raw_text = await asyncio.to_thread(lambda: body.text)

            # 简单的后处理：去除连续空行
            lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
            return "\n".join(lines)
        except Exception as e:
            return f"[Error extracting text: {e}]"

    async def _detect_asset_subtype(self, tab: TabHandle, url: str) -> str:
        """
        判断静态资源的子类型。
        优先使用 content_type 判断（参考 analyze_page_type），回退到 URL 后缀。
        """
        url_lower = url.lower()

        # 0. 特殊情况：Chrome PDF viewer 扩展
        # URL 格式：chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html?...
        if "chrome-extension://" in url_lower and "pdf" in url_lower:
            return "pdf"

        # 1. 优先从 content_type 判断（更可靠）
        try:
            content_type = await asyncio.to_thread(
                tab.run_js, "return document.contentType;", timeout=1
            )
            content_type = content_type.lower() if content_type else ""

            if "application/pdf" in content_type:
                return "pdf"
            elif "application/json" in content_type or "text/json" in content_type:
                return "json"
            elif "text/xml" in content_type or "application/xml" in content_type:
                return "xml"
            elif "image/" in content_type:
                return "image"
        except Exception:
            # JS 执行失败，回退到 URL 判断
            pass

        # 2. 回退到 URL 后缀判断
        if url_lower.endswith(".pdf"):
            return "pdf"
        elif url_lower.endswith(".json"):
            return "json"
        elif url_lower.endswith(".xml"):
            return "xml"
        elif any(url_lower.endswith(ext) for ext in [".txt", ".log", ".md"]):
            return "text"
        else:
            # 默认为 text
            return "text"

    async def _get_static_asset_snapshot(
        self, tab: TabHandle, url: str, title: str, content_type: PageType
    ) -> PageSnapshot:
        """
        处理静态资源的 snapshot。
        """
        subtype = await self._detect_asset_subtype(tab, url)

        self.logger.info(f"Creating snapshot for static asset: {subtype} - {url}")

        if subtype == "pdf":
            return await self._snapshot_pdf_browser(tab, url, title, content_type)
        elif subtype == "json":
            return await self._snapshot_json(tab, url, title, content_type)
        elif subtype == "xml":
            return await self._snapshot_xml(tab, url, title, content_type)
        else:
            return await self._snapshot_text(tab, url, title, content_type)

    async def _snapshot_pdf_browser(
        self, tab: TabHandle, url: str, title: str, content_type: PageType
    ) -> PageSnapshot:
        """
        使用专业的 PDF 解析工具提取 PDF 内容。

        流程：
        1. 下载 PDF 文件到本地
        2. 使用 marker 库转换为 Markdown（动态长度策略）
        3. 清理临时文件

        动态长度策略：
        - 先转换前 5 页
        - 如果长度 ≤ 100,000 字符，继续转换剩余页面
        - 当总长度超过 10,000 字符时停止
        """
        pdf_path = None
        try:
            self.logger.info(f"Extracting PDF content from: {url}")

            # 1. 下载 PDF 文件到本地
            pdf_path = await self.save_static_asset(tab)

            if not pdf_path:
                self.logger.error("Failed to save PDF file")
                return PageSnapshot(
                    url=url,
                    title=title,
                    content_type=content_type,
                    main_text="[PDF Document] (Failed to download)",
                    raw_html="",
                )

            # 2. 导入 pdf_to_markdown
            from skills.report_writer_utils import pdf_to_markdown
            import pymupdf  # PyMuPDF，用于获取 PDF 页数

            # 3. 获取 PDF 总页数
            try:
                self.logger.debug(f"Opening {pdf_path}")
                doc = pymupdf.open(pdf_path)
                total_pages = len(doc)
                doc.close()
                self.logger.info(f"PDF total pages: {total_pages}")
            except Exception as e:
                self.logger.exception(f"Failed to get PDF page count: {e}")
                # 可能是加密或损坏的 PDF，返回空
                return PageSnapshot(
                    url=url,
                    title=title,
                    content_type=content_type,
                    main_text="[PDF Document] (Encrypted or corrupted)",
                    raw_html="",
                )

            # 4. 动态长度转换策略
            try:
                # 先转换前 5 页
                initial_end = min(5, total_pages)
                markdown_text = pdf_to_markdown(
                    pdf_path, start_page=1, end_page=initial_end
                )
                self.logger.info(
                    f"Initial conversion (pages 1-{initial_end}): {len(markdown_text)} chars"
                )

                # 如果长度 ≤ 100,000 字符，继续转换剩余页面
                if len(markdown_text) <= 100000:
                    current_page = initial_end + 1

                    while current_page <= total_pages and len(markdown_text) <= 10000:
                        # 逐页转换
                        page_text = pdf_to_markdown(
                            pdf_path, start_page=current_page, end_page=current_page
                        )
                        markdown_text += "\n\n" + page_text
                        self.logger.debug(
                            f"Added page {current_page}: total {len(markdown_text)} chars"
                        )
                        current_page += 1

                    # 如果在 10,000 字符限制内仍有未转换页面，一次性转换剩余所有
                    if current_page <= total_pages and len(markdown_text) <= 10000:
                        remaining_text = pdf_to_markdown(
                            pdf_path, start_page=current_page, end_page=total_pages
                        )
                        markdown_text += "\n\n" + remaining_text
                        self.logger.info(
                            f"Converted remaining pages: final total {len(markdown_text)} chars"
                        )

                self.logger.info(
                    f"PDF converted to Markdown: {len(markdown_text)} chars"
                )

                return PageSnapshot(
                    url=url,
                    title=title,
                    content_type=content_type,
                    main_text=f"[PDF Document]\n\n{markdown_text}",
                    raw_html="",
                )

            except Exception as e:
                self.logger.exception(f"Failed to convert PDF to Markdown: {e}")
                # 转换失败（可能是加密 PDF），返回空内容不报错
                return PageSnapshot(
                    url=url,
                    title=title,
                    content_type=content_type,
                    main_text="[PDF Document] (Encrypted or conversion failed)",
                    raw_html="",
                )

        except Exception as e:
            self.logger.exception(f"Failed to extract PDF content: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[PDF Document] (Extraction failed)",
                raw_html="",
            )

        finally:
            # 4. 清理临时 PDF 文件
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.unlink(pdf_path)
                    self.logger.info(f"Cleaned up temporary PDF: {pdf_path}")
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup PDF file: {e}")

    async def _snapshot_json(
        self, tab: TabHandle, url: str, title: str, content_type: PageType
    ) -> PageSnapshot:
        """
        提取并格式化 JSON。
        """
        try:
            # 在线程池中获取原始文本
            body = await asyncio.to_thread(tab.ele, "tag:body")
            text = await asyncio.to_thread(lambda: body.text.strip())

            # 尝试解析并格式化
            try:
                import json

                data = json.loads(text)
                formatted = json.dumps(data, indent=2, ensure_ascii=False)

                # 限制在 5K
                max_length = 5000
                if len(formatted) > max_length:
                    formatted = formatted[:max_length] + "\n\n... (truncated)"

                return PageSnapshot(
                    url=url,
                    title=title,
                    content_type=content_type,
                    main_text=f"[JSON Data]\n\n```json\n{formatted}\n```",
                    raw_html="",
                )
            except json.JSONDecodeError:
                # 不是有效的 JSON，当作普通文本处理
                max_length = 5000
                if len(text) > max_length:
                    text = text[:max_length] + "\n\n... (truncated)"

                return PageSnapshot(
                    url=url,
                    title=title,
                    content_type=content_type,
                    main_text=f"[JSON or Text Data]\n\n```\n{text}\n```",
                    raw_html="",
                )

        except Exception as e:
            self.logger.exception(f"Failed to extract JSON: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[JSON/Text Data] (Extraction failed)",
                raw_html="",
            )

    async def _snapshot_xml(
        self, tab: TabHandle, url: str, title: str, content_type: PageType
    ) -> PageSnapshot:
        """
        提取并格式化 XML。
        """
        try:
            # 在线程池中获取原始文本
            body = await asyncio.to_thread(tab.ele, "tag:body")
            text = await asyncio.to_thread(lambda: body.text.strip())

            # 限制在 5K
            max_length = 5000
            if len(text) > max_length:
                text = text[:max_length] + "\n\n... (truncated)"

            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text=f"[XML Data]\n\n```xml\n{text}\n```",
                raw_html="",
            )

        except Exception as e:
            self.logger.exception(f"Failed to extract XML: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[XML Data] (Extraction failed)",
                raw_html="",
            )

    async def _snapshot_text(
        self, tab: TabHandle, url: str, title: str, content_type: PageType
    ) -> PageSnapshot:
        """
        处理纯文本文件。
        """
        try:
            # 在线程池中获取文本
            body = await asyncio.to_thread(tab.ele, "tag:body")
            text = await asyncio.to_thread(lambda: body.text.strip())

            # 限制在 5K
            max_length = 5000
            if len(text) > max_length:
                text = text[:max_length] + "\n\n... (truncated)"

            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text=f"[Text File]\n\n```\n{text}\n```",
                raw_html="",
            )

        except Exception as e:
            self.logger.exception(f"Failed to extract text: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[Text File] (Extraction failed)",
                raw_html="",
            )

    async def save_view_as_file(self, tab: TabHandle, save_dir: str) -> Optional[str]:
        """
        如果当前页面是 PDF 预览或纯文本，将其保存为本地文件。
        """
        # TODO: 实现保存视图为文件的逻辑
        pass

    async def save_static_asset(
        self, tab: TabHandle, original_url: str = None, save_dir: str = None
    ) -> Optional[str]:
        """
        [针对 STATIC_ASSET]
        保存当前 Tab 显示的内容为文件。

        支持的文件类型：
        - PDF 文件
        - 图片文件 (jpg, png, gif, webp, etc.)
        - 文本文件 (json, txt, xml, etc.)

        Args:
            tab: 浏览器标签页
            original_url: 原始URL（可选，用于处理Chrome PDF viewer等转换后的URL）
            save_dir: 保存目录（可选，优先级最高）。如果未提供，回退到 self.download_path，再回退到 "downloads"

        Returns:
            保存的文件路径，失败返回 None
        """
        if not tab:
            self.logger.error("Tab handle is None")
            return None

        try:
            # 1. 获取当前页面信息
            url = tab.url
            page_type = await self.analyze_page_type(tab)

            if page_type != PageType.STATIC_ASSET:
                self.logger.warning(f"Page is not a static asset: {url}")
                return None

            # 2. 确定用于下载的URL（处理Chrome PDF viewer等情况）
            # 如果当前URL不是http开头，尝试使用原始URL
            if not url.startswith("http://") and not url.startswith("https://"):
                if original_url and (
                    original_url.startswith("http://")
                    or original_url.startswith("https://")
                ):
                    self.logger.info(
                        f"当前URL '{url}' 无效，使用原始URL: {original_url}"
                    )
                    url = original_url
                else:
                    raise RuntimeError(
                        f"无法下载静态资源：当前URL '{url}' 不是有效的HTTP URL. "
                        f"这可能是Chrome PDF viewer或其他浏览器内部URL转换导致。"
                    )

            # 3. 确定保存目录
            effective_save_dir = save_dir or self.download_path or "downloads"
            Path(effective_save_dir).mkdir(parents=True, exist_ok=True)

            # 4. 解析 URL 获取文件名
            parsed_url = urlparse(url)
            filename = unquote(os.path.basename(parsed_url.path))

            # 如果 URL 没有清晰的文件名，生成一个
            if not filename or "." not in filename:
                # 根据 URL 路径或生成 UUID
                ext = self._get_extension_from_url(url)
                filename = f"{uuid.uuid4().hex[:8]}{ext}"

            # 5. 判断资源类型并保存
            file_path = os.path.join(effective_save_dir, filename)

            # 判断是否是文本类型
            if self._is_text_content_type(url):
                # 文本类型：直接提取 body 文本
                await self._save_text_asset(tab, file_path)
            else:
                # 在线程池中使用 tab.download 下载二进制类型
                res = await asyncio.to_thread(tab.download, url)
                success, downloaded_path = res

                # 检查下载是否成功
                if not success:
                    self.logger.error(f"Download failed: {downloaded_path}")
                    return None

                file_path = downloaded_path

            # 转换为绝对路径，确保后续调用能正确找到文件
            file_path = os.path.abspath(file_path)
            # 检查file_path 是否存在
            if not os.path.exists(file_path):
                self.logger.error(f"Download failed")
                return None
            self.logger.info(f"Static asset saved to: {file_path}")

            # 检查tab是否卡在PDF viewer页面（chrome-extension://）
            # 这对于PDF文件特别重要，因为Chrome PDF viewer可能导致tab状态异常
            current_url = tab.url if hasattr(tab, "url") else ""
            if current_url.startswith("chrome-extension://"):
                self.logger.warning(
                    f"⚠️ Tab stuck in PDF viewer ({current_url}), navigating to about:blank to restore..."
                )
                try:
                    # Navigate到about:blank让tab脱离PDF viewer状态
                    await asyncio.to_thread(tab.get, "about:blank")
                    await asyncio.sleep(0.5)
                    self.logger.info("✓ Tab restored from PDF viewer")
                except Exception as e:
                    self.logger.error(f"Failed to restore tab from PDF viewer: {e}")

            return file_path

        except Exception as e:
            self.logger.exception(f"Failed to save static asset: {e}")
            return None

    def _get_extension_from_url(self, url: str) -> str:
        """
        从 URL 推断文件扩展名。
        """
        url_lower = url.lower()

        # 常见文件扩展名映射
        extensions = {
            ".pdf": ".pdf",
            ".jpg": ".jpg",
            ".jpeg": ".jpg",
            ".png": ".png",
            ".gif": ".gif",
            ".webp": ".webp",
            ".svg": ".svg",
            ".json": ".json",
            ".txt": ".txt",
            ".xml": ".xml",
            ".html": ".html",
            ".htm": ".html",
        }

        for ext, file_ext in extensions.items():
            if ext in url_lower:
                return file_ext

        # 默认扩展名
        return ".bin"

    def _is_text_content_type(self, url: str) -> bool:
        """
        判断 URL 是否指向文本内容。
        """
        url_lower = url.lower()
        text_extensions = [".json", ".txt", ".xml", ".html", ".htm", ".svg"]
        return any(url_lower.endswith(ext) for ext in text_extensions)

    async def _save_text_asset(self, tab: TabHandle, file_path: str):
        """
        保存文本类型的资源。
        """
        try:
            # 在线程池中提取 body 文本
            body = await asyncio.to_thread(tab.ele, "tag:body")
            if not body:
                raise ValueError("No body element found")

            text_content = await asyncio.to_thread(lambda: body.text)

            # 写入文件（保持同步，按照用户要求）
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text_content)

            self.logger.info(
                f"Text asset saved: {file_path} ({len(text_content)} chars)"
            )

        except Exception as e:
            self.logger.exception(f"Failed to save text asset: {e}")
            raise

    # --- Scouting & Interaction (侦察与交互) ---
    async def scan_elements(self, tab: TabHandle):
        """
        [Phase 4] 扫描页面。
        返回两个列表：
        1. 第一个列表：所有可点的、指向某个明确 URL 的元素（例如 <a> 标签）
        2. 第二个列表：所有可点的、没有明确新 URL 的其他元素（按钮等）
        实现了去重和垃圾过滤。
        """
        # 无价值元素的黑名单（中英文）
        IGNORED_PATTERNS = [
            # 登录/注册
            "登录",
            "login",
            "signin",
            "sign in",
            "register",
            "注册",
            "sign up",
            "signup",
            # 退出/关闭
            "exit",
            "退出",
            "logout",
            "log out",
            "cancel",
            "取消",
            "close",
            "关闭",
            # 通用导航
            "home",
            "首页",
            "back",
            "返回",
            "skip",
            "跳过",
            # 同意/拒绝
            "accept",
            "接受",
            "agree",
            "同意",
            "decline",
            "拒绝",
        ]

        if not tab:
            return {}, {}

        # 1. 定义统一选择器 (Method B)
        # 覆盖：链接, 按钮, 图片输入, 提交按钮, 以及伪装成按钮/链接的 div/span
        # 注意：排除 href 为 javascript: mailto: tel: 的链接，这些通常 Agent 处理不了
        selector = (
            "@|tag()=a"  # 所有带 href 属性的 a 标签
            "@|tag()=button"  # 所有 button 标签
            "input@type=button||"  # type=button 的 input
            "input@type=submit||"  # type=submit 的 input
            "input@type=image||"  # type=image 的 input
            "@role=button||"  # role=button 的元素
            "@role=link||"  # role=link 的元素
            "@role=menuitem"  # role=menuitem 的元素
        )
        selector1 = "@|tag()=a@|tag()=button"
        selector2 = 'css:input[type="button"],input[type="submit"], input[type="image"]'
        selector3 = 'css:[role="button"],[role="link"],[role="menuitem"]'

        raw_elements = []
        try:
            # 2. 在线程池中批量获取元素 (DrissionPage 的 eles 方法)
            # timeout 设短点，找不到就算了
            for css_selector in [selector1, selector2, selector3]:
                self.logger.debug(f"Checking: {css_selector}")
                elements = await asyncio.to_thread(tab.eles, css_selector, timeout=2)
                self.logger.debug(f"Found {len(elements)} elements")
                raw_elements.extend(elements)
            # raw_elements = list(set(raw_elements))  # 去重
        except Exception as e:
            self.logger.exception(f"Scan elements failed: {e}")
            return {}, {}

        # 结果容器

        button_elements = {}  # 没有明确新 URL 的元素

        # 链接去重字典: {normalized_url: (element, text_length)}
        # 我们只保留指向同一个 URL 的链接中，文本最长的那个
        seen_links = {}

        # 3. 遍历与过滤
        # 为了性能，限制最大处理数量 (比如前 500 个 DOM 里的元素)
        max_scan_count = 500

        count = 0
        for ele in raw_elements:
            if count > max_scan_count:
                break

            try:
                # --- 在线程池中快速过滤 (无网络交互) ---
                tag = await asyncio.to_thread(lambda: ele.tag)
                # 获取文本，如果没有可见文本，尝试获取 title 或 aria-label
                # DrissionPage 的 .text 获取的是可见文本，这步其实隐含了可见性检查的一部分，但有些隐藏元素也有 text
                text = await asyncio.to_thread(lambda: ele.text.strip())

                # 补充文本源 (针对图标按钮)
                if not text:
                    aria_label = await asyncio.to_thread(lambda: ele.attr("aria-label"))
                    title_attr = await asyncio.to_thread(lambda: ele.attr("title"))
                    alt_attr = await asyncio.to_thread(lambda: ele.attr("alt"))
                    text = aria_label or title_attr or alt_attr or ""
                    text = text.strip()

                # 如果还是没字，跳过 (除非是 input image)
                if not text and tag != "input":
                    continue

                # --- 黑名单过滤 ---
                # 检查文本是否匹配无价值模式
                text_lower = text.lower()
                should_skip = False
                for pattern in IGNORED_PATTERNS:
                    # 检查是否包含模式（部分匹配）
                    if pattern in text_lower:
                        self.logger.debug(
                            f"⛔ Filtering ignored element: '{text}' (matched '{pattern}')"
                        )
                        should_skip = True
                        break
                    # 检查完全匹配
                    if text_lower.strip() == pattern:
                        self.logger.debug(
                            f"⛔ Filtering ignored element: '{text}' (exact match '{pattern}')"
                        )
                        should_skip = True
                        break

                if should_skip:
                    continue

                # --- 在线程池中进行慢速过滤 (网络交互) ---
                # 检查可见性 (is_displayed 内部会 check visibility, display, opacity)
                # 还要检查尺寸，防止 1x1 的跟踪点
                is_displayed = await asyncio.to_thread(lambda: ele.states.is_displayed)
                if not is_displayed:
                    continue

                rect = await asyncio.to_thread(lambda: ele.rect)
                if rect.size[0] < 5 or rect.size[1] < 5:  # 忽略极小元素
                    continue

                # --- 分类处理 ---

                # A. 链接 (Links) -> 需去重
                role = await asyncio.to_thread(lambda: ele.attr("role"))
                if tag == "a" or role == "link":
                    href = await asyncio.to_thread(lambda: ele.attr("href"))

                    if not href or len(href) < 2 or href.startswith("#"):
                        continue

                    # 绝对路径化 (DrissionPage 拿到的 href 通常已经是绝对路径，或者是 property)
                    # 如果不是，可以在这里做 urljoin，但 DrissionPage 的 .link 属性通常是好的
                    full_url = await asyncio.to_thread(lambda: ele.link)
                    if not full_url:
                        continue

                    # 去重逻辑：保留描述最长的
                    if full_url in seen_links:
                        existing_link_text = seen_links[full_url]
                        if len(text) > existing_link_text:
                            seen_links[full_url] = text  # 更新为更长文本的
                    else:
                        seen_links[full_url] = text

                # B. 按钮 (Buttons) -> 直接添加到 button_elements
                else:
                    # 按钮不需要 URL 去重，因为不同的按钮可能有不同的副作用
                    # 构造返回对象
                    button_elements[text] = DrissionPageElement(ele)

                    count += 1

            except Exception:
                # 遍历过程中元素可能会失效 (StaleElement)，直接忽略
                continue

        self.logger.info(
            f"🔍 Scanned {len(seen_links) + len(button_elements)} elements ({len(seen_links)} links, {len(button_elements)} buttons)"
        )
        return seen_links, button_elements

    async def get_target_element(self, tab, element: Union[str, PageElement]):
        # 根据 element 类型获取 ChromiumElement
        if isinstance(element, str):
            # 如果是字符串选择器，使用 find_element 查找
            target_element = (await self.find_element(tab, element)).get_element()
        else:
            # 如果是 PageElement 对象，直接获取底层元素
            target_element = element.get_element()

        return target_element

    async def click_and_observe(
        self, tab: TabHandle, element: Union[str, PageElement]
    ) -> InteractionReport:
        """
        [Phase 5] 核心交互函数。
        点击元素，并智能等待，捕捉所有可能的后果 (新Tab、下载、页面变动)。
        必须能够处理 SPA (单页应用) 的 DOM 变动检测。

        Args:
            tab: 标签页句柄
            element: 要点击的元素，可以是选择器字符串或 PageElement 对象

        Returns:
            InteractionReport: 点击后的后果报告单
        """
        # 记录点击前的状态
        old_url = tab.url
        old_tab_count = self.browser.tabs_count
        # 快速计算指纹 (IO开销微乎其微)
        # 加上 title，防止 body 为空的情况
        try:
            body_text = await asyncio.to_thread(
                lambda: tab.ele("body", timeout=0.1).text
            )
            raw_text = f"{tab.title}|{body_text}"
            old_fingerprint = hashlib.md5(raw_text.encode("utf-8")).hexdigest()
        except:
            old_fingerprint = ""

        target_element = await self.get_target_element(tab, element)

        # 点击元素
        try:
            await asyncio.to_thread(target_element.click)
        except Exception as e:
            self.logger.exception(f"Click failed for element: {element}")
            # 但不管有啥错，我们继续
        # 点击后有多种可能，一种是有新tab出现，一种是没有，当前tab重新打开别的地方，也可能是当前tab内部dom 变化
        # 有新tab一般几乎立刻就出现了，我们等1秒看看有没有就知道了
        await asyncio.sleep(1)
        new_tabs = []
        is_url_changed = False
        is_dom_changed = False
        try:
            new_tab_count = self.browser.tabs_count
            has_new_tab = new_tab_count > old_tab_count

            # 检查是否有新标签页出现
            if has_new_tab:
                # 获取新出现的标签页
                all_tabs = await asyncio.to_thread(self.browser.get_tabs)
                new_tabs = all_tabs[old_tab_count:]

            # B. 检查当前页面变化

            # 等待页面加载完成，最多60秒
            start_time = time.time()
            timeout = 60  # 60秒超时

            new_url = tab.url
            if old_url != new_url:
                is_url_changed = True
                is_dom_changed = True
                # url变化了，直接范围，肯定都变了
                return InteractionReport(
                    new_tabs=new_tabs,
                    is_url_changed=is_url_changed,
                    is_dom_changed=is_dom_changed,
                )
            # url 没变化，那等到DOM Ready
            waited_time = time.time() - start_time
            while tab.states.ready_state != "complete" and waited_time < timeout:
                await asyncio.sleep(0.2)

            # 这时候，可能是dom ready，也可能是超时了，不要紧，直接比较text指纹

            try:
                new_body_text = await asyncio.to_thread(
                    lambda: tab.ele("body", timeout=0.1).text
                )
                new_text = f"{tab.title}|{new_body_text}"
                new_fingerprint = hashlib.md5(new_text.encode("utf-8")).hexdigest()
                if old_fingerprint != new_fingerprint:
                    is_dom_changed = True
            except:
                pass  # 获取失败视作没变

            # 创建交互报告
            report = InteractionReport(
                new_tabs=new_tabs,
                is_url_changed=is_url_changed,
                is_dom_changed=is_dom_changed,
            )

            return report
        except Exception as e:
            self.logger.exception(f"Click and observe failed for element: {element}")
            return InteractionReport(
                new_tabs=new_tabs,
                is_url_changed=is_url_changed,
                is_dom_changed=is_dom_changed,
            )

    # ==========================================
    # Input & Control (精确输入与控制)
    #    用于 Phase 0 (搜索) 或特定表单交互
    # ==========================================

    async def type_text(
        self, tab: TabHandle, selector: str, text: str, clear_existing: bool = True
    ) -> bool:
        """
        在指定元素中输入文本。

        Args:
            selector: 定位符 (CSS/XPath/DrissionPage语法)。例如: 'input[name="q"]'
            text: 要输入的文本。
            clear_existing: 输入前是否清空原有内容。

        Returns:
            bool: 操作是否成功 (元素找到且输入完成)。
        """
        if not tab:
            tab = await self.get_tab()

        try:
            # print(f"      [DEBUG] type_text: Looking for element with selector '{selector}'")

            # 首先尝试直接查找
            ele = await asyncio.to_thread(tab.ele, selector, timeout=2)

            if not ele:
                # 如果直接查找失败，尝试解析选择器并手动查找
                # print(f"      [DEBUG] Direct lookup failed, trying alternative method...")
                ele = await self._find_element_fallback(tab, selector)

            if ele:
                # print(f"      [DEBUG] type_text: Found element, clicking...")
                await asyncio.to_thread(ele.click)

                # print(f"      [DEBUG] type_text: Clicked, waiting briefly...")
                await asyncio.sleep(random.uniform(0.1, 0.3))

                # print(f"      [DEBUG] type_text: Inputting text: '{text[:50]}...'")
                await asyncio.to_thread(ele.input, vals=text, clear=clear_existing)

                # print(f"      [DEBUG] type_text: ✓ Successfully typed text")
                return True
            else:
                # print(f"      [DEBUG] type_text: Element not found with selector '{selector}'")
                return False
        except Exception as e:
            # 元素未找到或其他错误
            # print(f"      [DEBUG] type_text FAILED: {e}")
            import traceback

            # print(f"      [DEBUG] Traceback: {traceback.format_exc()}")
            return False

    async def _find_element_fallback(self, tab, selector: str):
        """
        Fallback method for finding elements when direct lookup fails.
        Parses common selector patterns and finds elements manually.
        """
        import re

        # 解析选择器，例如: "textarea[name="q"]" 或 "input[name=q]"
        pattern = r'^(\w+)\[name=["\']([^"\']+)["\']\]$'
        match = re.match(pattern, selector)

        if match:
            tag_name = match.group(1)  # e.g., "textarea" or "input"
            name_value = match.group(2)  # e.g., "q"

            # print(f"      [DEBUG] Fallback: Searching for <{tag_name}> with name='{name_value}'")

            # 查找所有该标签的元素
            elements = await asyncio.to_thread(tab.eles, f"tag:{tag_name}")

            # print(f"      [DEBUG] Fallback: Found {len(elements)} <{tag_name}> elements")

            # 遍历找到 name 属性匹配的
            for ele in elements:
                try:
                    name_attr = ele.attr("name")
                    # print(f"      [DEBUG] Fallback: Checking element with name='{name_attr}'")
                    if name_attr == name_value:
                        # print(f"      [DEBUG] Fallback: ✓ Found matching element!")
                        return ele
                except:
                    continue

            # print(f"      [DEBUG] Fallback: No matching element found")
            return None

        # print(f"      [DEBUG] Fallback: Selector pattern not recognized: {selector}")
        return None

    async def press_key(
        self, tab: TabHandle, key: Union[KeyAction, str]
    ) -> InteractionReport:
        """
        在当前页面模拟按键。
        通常用于输入搜索词后按回车。

        Returns:
            InteractionReport: 按键可能会导致页面刷新或跳转 (如按回车提交表单)，
            所以必须返回后果报告，供逻辑层判断是否需要 Soft Restart。
        """
        if not tab:
            tab = await self.get_tab()

        old_url = tab.url if hasattr(tab, "url") else ""

        try:
            # 转换 KeyAction 枚举为实际按键
            if isinstance(key, KeyAction):
                key_map = {
                    KeyAction.ENTER: "enter",
                    KeyAction.ESC: "esc",
                    KeyAction.TAB: "tab",
                    KeyAction.PAGE_DOWN: "page_down",
                    KeyAction.SPACE: "space",
                }
                key_value = key_map.get(key, "enter")
            else:
                key_value = str(key).lower()

            # 使用 DrissionPage 的按键模拟
            await asyncio.to_thread(tab.actions.key_down, key_value)
            await asyncio.sleep(0.1)  # 短暂延迟
            await asyncio.to_thread(tab.actions.key_up, key_value)

            # 等待可能的页面变化
            await asyncio.sleep(1)

            # 检查后果
            new_url = tab.url if hasattr(tab, "url") else ""
            is_url_changed = old_url != new_url

            return InteractionReport(
                is_url_changed=is_url_changed, is_dom_changed=is_url_changed
            )

        except Exception as e:
            self.logger.exception(f"Failed to press key: {key}")
            return InteractionReport(error=f"Key press failed: {str(e)}")

    async def click_by_selector(
        self, tab: TabHandle, selector: str
    ) -> InteractionReport:
        """
        [精确点击] 通过选择器点击特定元素。
        区别于 click_and_observe (那个是基于侦察出的 PageElement 对象)，
        这个方法用于已知页面结构的场景 (如点击搜索按钮)。
        """
        if not tab:
            tab = await self.get_tab()

        old_url = tab.url if hasattr(tab, "url") else ""

        try:
            # 使用 DrissionPage 的 ele 方法查找元素
            element = await asyncio.to_thread(tab.ele, selector, timeout=5)

            if not element:
                self.logger.warning(f"Element not found with selector: {selector}")
                return InteractionReport(error=f"Element not found: {selector}")

            # 点击前记录状态
            old_tabs_count = len(tab.browser.tab_ids) if hasattr(tab, "browser") else 1

            # 模拟人类点击
            await asyncio.to_thread(element.click)
            await asyncio.sleep(random.uniform(0.5, 1.5))  # 随机延迟

            # 检查后果
            new_url = tab.url if hasattr(tab, "url") else ""
            is_url_changed = old_url != new_url

            # 检查是否有新标签页弹出
            new_tabs = []
            if hasattr(tab, "browser"):
                current_tabs_count = len(tab.browser.tab_ids)
                if current_tabs_count > old_tabs_count:
                    # 有新标签页，获取句柄
                    new_tabs = [tab.browser.latest_tab]

            return InteractionReport(
                is_url_changed=is_url_changed,
                is_dom_changed=is_url_changed,
                new_tabs=new_tabs,
            )

        except Exception as e:
            self.logger.exception(f"Failed to click element: {selector}")
            return InteractionReport(error=f"Click failed: {str(e)}")

    async def click_first_visible_by_selector(
        self, tab: TabHandle, selector: str
    ) -> InteractionReport:
        """
        [精确点击] 通过选择器查找所有匹配元素，依次尝试点击直到成功。
        用于处理有多个匹配元素（包括隐藏元素）的情况。

        Args:
            tab: 标签页句柄
            selector: CSS选择器

        Returns:
            InteractionReport: 点击结果报告
        """
        if not tab:
            tab = await self.get_tab()

        old_url = tab.url if hasattr(tab, "url") else ""

        try:
            # 使用 DrissionPage 的 eles 方法查找所有匹配元素
            elements = await asyncio.to_thread(tab.eles, selector, timeout=5)

            if not elements or len(elements) == 0:
                self.logger.warning(f"No elements found with selector: {selector}")
                return InteractionReport(error=f"No elements found: {selector}")

            # print(f"      [DEBUG] Found {len(elements)} elements with selector '{selector}'")

            # 点击前记录状态
            old_tabs_count = len(tab.browser.tab_ids) if hasattr(tab, "browser") else 1

            # 依次尝试每个元素（优先尝试可见的，但不可见的也会尝试）
            for i, ele in enumerate(elements):
                try:
                    # 检查元素是否可见
                    is_visible = ele.states.is_displayed
                    # print(f"      [DEBUG] Element {i+1}: is_displayed={is_visible}, attempting to click...")

                    # 模拟人类点击
                    await asyncio.to_thread(ele.click)
                    await asyncio.sleep(random.uniform(0.5, 1.5))  # 随机延迟

                    # 检查后果
                    new_url = tab.url if hasattr(tab, "url") else ""
                    is_url_changed = old_url != new_url

                    # 检查是否有新标签页弹出
                    new_tabs = []
                    if hasattr(tab, "browser"):
                        current_tabs_count = len(tab.browser.tab_ids)
                        if current_tabs_count > old_tabs_count:
                            # 有新标签页，获取句柄
                            new_tabs = [tab.browser.latest_tab]

                    print(f"      [DEBUG] ✓ Successfully clicked element {i + 1}")

                    return InteractionReport(
                        is_url_changed=is_url_changed,
                        is_dom_changed=is_url_changed,
                        new_tabs=new_tabs,
                    )

                except Exception as e:
                    # print(f"      [DEBUG] Element {i+1}: Click failed with error: {e}")
                    # 继续尝试下一个元素
                    continue

            # 所有元素都尝试失败
            # self.logger.warning(f"Failed to click any of the {len(elements)} elements with selector: {selector}")
            return InteractionReport(
                error=f"Failed to click all {len(elements)} elements"
            )

        except Exception as e:
            # self.logger.exception(f"Failed to click visible element: {selector}")
            return InteractionReport(error=f"Click failed: {str(e)}")

    async def scroll(
        self, tab: TabHandle, direction: str = "bottom", distance: int = 0
    ):
        """
        手动控制滚动。
        Args:
            direction: 'bottom', 'top', 'down', 'up'
            distance: 像素值 (如果 direction 是 down/up)
        """
        if not tab:
            tab = await self.get_tab()

        try:
            if direction == "bottom":
                # 在线程池中滚动到页面底部
                await asyncio.to_thread(tab.scroll.to_bottom)
            elif direction == "top":
                # 在线程池中滚动到页面顶部
                await asyncio.to_thread(tab.scroll.to_top)
            elif direction == "down":
                # 向下滚动指定像素
                if distance <= 0:
                    distance = 500  # 默认向下滚动500像素
                await asyncio.to_thread(tab.scroll.down, distance)
            elif direction == "up":
                # 向上滚动指定像素
                if distance <= 0:
                    distance = 500  # 默认向上滚动500像素
                await asyncio.to_thread(tab.scroll.up, distance)
            else:
                self.logger.warning(f"Unsupported scroll direction: {direction}")
                return False

            # 短暂等待滚动完成
            await asyncio.sleep(0.5)
            return True

        except Exception as e:
            self.logger.warning(f"Scroll failed: {e}")
            return False

    async def find_element(
        self, tab: TabHandle, selector: str, timeout: float = 2.0
    ) -> Optional[PageElement]:
        """
        检查某个特定元素是否存在。
        用于验证页面是否加载正确 (例如：检查是否存在 'input[name="q"]' 来确认是否在 Google 首页)。
        如果存在就返回这个element, 不存在返回None

        Args:
            tab: 标签页句柄
            selector: CSS选择器或XPath等定位符
            timeout: 超时时间（秒），默认2秒

        Returns:
            PageElement if found, None if not found
        """
        if not tab:
            tab = await self.get_tab()

        try:
            # 在线程池中使用 DrissionPage 的 ele 方法查找元素，带超时
            chromium_element = await asyncio.to_thread(
                tab.ele, selector, timeout=timeout
            )
            return DrissionPageElement(chromium_element)
        except Exception as e:
            # DrissionPage 找不到元素时会抛出异常
            self.logger.debug(f"Element not found with selector '{selector}': {e}")
            return None

    # ==========================================
    # Vision & Visual Highlighting (视觉辅助)
    #    用于智能视觉定位的底层支持
    # ==========================================

    async def capture_screenshot(self, tab: TabHandle, full_page: bool = False) -> str:
        """
        捕获页面截图，返回 base64 编码的图片。

        Args:
            tab: 标签页句柄
            full_page: 是否截取整个页面（包括滚动部分）

        Returns:
            str: base64 编码的图片数据 (PNG格式)
        """
        if not tab:
            tab = await self.get_tab()

        try:
            # 使用 DrissionPage 的 as_base64 参数直接获取 base64 字符串
            # 优先级：as_bytes > as_base64 > path
            if full_page:
                screenshot_base64 = await asyncio.to_thread(
                    tab.get_screenshot, as_base64="png", full_page=True
                )
            else:
                # 视口截图，返回 base64 字符串
                screenshot_base64 = await asyncio.to_thread(
                    tab.get_screenshot, as_base64="png"
                )

            # 验证返回的是字符串类型
            if not isinstance(screenshot_base64, str):
                raise TypeError(
                    f"Expected base64 string from get_screenshot(as_base64=True), got {type(screenshot_base64)}"
                )

            self.logger.debug(
                f"Screenshot captured, base64 size: {len(screenshot_base64)} chars"
            )
            return screenshot_base64

        except Exception as e:
            self.logger.exception(f"Failed to capture screenshot: {e}")
            raise

    async def draw_crosshair(
        self, tab: TabHandle, region: "RegionBounds" = None
    ) -> str:
        """
        在页面上画出十字坐标线，将页面（或指定区域）分成四个区域。
        使用绝对定位的 div 覆盖在页面上。

        Args:
            tab: 标签页句柄
            region: 可选的区域边界 (x, y, width, height)。如果为None，则使用全屏

        Returns:
            str: 注入的 crosshair 元素的 ID
        """
        if not tab:
            tab = await self.get_tab()

        # 如果没有指定区域，获取视口大小
        if region is None:
            viewport_size = await asyncio.to_thread(lambda: tab.rect.size)
            region = RegionBounds(0, 0, viewport_size[0], viewport_size[1])

        # 注入 CSS 和 HTML
        crosshair_js = f"""
        (function() {{
            // 创建容器
            const container = document.createElement('div');
            container.id = 'agentmatrix-crosshair-container';
            container.style.position = 'absolute';
            container.style.left = '{region.x}px';
            container.style.top = '{region.y}px';
            container.style.width = '{region.width}px';
            container.style.height = '{region.height}px';
            container.style.pointerEvents = 'none';
            container.style.zIndex = '999999';

            // 创建竖线
            const vLine = document.createElement('div');
            vLine.style.position = 'absolute';
            vLine.style.left = '50%';
            vLine.style.top = '0';
            vLine.style.width = '3px';
            vLine.style.height = '100%';
            vLine.style.backgroundColor = '#FFD700';  // 金黄色
            vLine.style.boxShadow = '0 0 5px rgba(255, 215, 0, 0.8)';

            // 创建横线
            const hLine = document.createElement('div');
            hLine.style.position = 'absolute';
            hLine.style.left = '0';
            hLine.style.top = '50%';
            hLine.style.width = '100%';
            hLine.style.height = '3px';
            hLine.style.backgroundColor = '#FFD700';
            hLine.style.boxShadow = '0 0 5px rgba(255, 215, 0, 0.8)';

            container.appendChild(vLine);
            container.appendChild(hLine);
            document.body.appendChild(container);

            return 'agentmatrix-crosshair-container';
        }})();
        """

        try:
            element_id = await asyncio.to_thread(tab.run_js, crosshair_js)
            self.logger.debug(f"Crosshair drawn with ID: {element_id}")
            return element_id
        except Exception as e:
            self.logger.exception(f"Failed to draw crosshair: {e}")
            raise

    async def get_viewport_size(self, tab: TabHandle) -> Tuple[int, int]:
        """
        获取视口大小

        Args:
            tab: 标签页句柄

        Returns:
            tuple: (width, height) 视口宽度和高度
        """
        if not tab:
            tab = await self.get_tab()

        js = """
        return {
            width: window.innerWidth,
            height: window.innerHeight
        };
        """

        try:
            size = await asyncio.to_thread(tab.run_js, js)
            return size["width"], size["height"]
        except Exception as e:
            self.logger.error(f"Failed to get viewport size: {e}")
            raise

    async def remove_crosshair(self, tab: TabHandle):
        """
        移除十字坐标线。

        Args:
            tab: 标签页句柄
        """
        if not tab:
            tab = await self.get_tab()

        remove_js = """
        (function() {
            const container = document.getElementById('agentmatrix-crosshair-container');
            if (container) {
                container.remove();
                return true;
            }
            return false;
        })();
        """

        try:
            removed = await asyncio.to_thread(tab.run_js, remove_js)
            self.logger.debug(f"Crosshair removed: {removed}")
        except Exception as e:
            self.logger.warning(f"Failed to remove crosshair: {e}")

    async def draw_boundary_box(self, tab: TabHandle, boundary: "BoundaryProbe") -> str:
        """
        在页面上画出边界探测的范围框

        Args:
            tab: 标签页句柄
            boundary: BoundaryProbe 对象，包含边界范围

        Returns:
            str: 执行结果
        """
        if not tab:
            tab = await self.get_tab()

        # 计算边界矩形的左上角和右下角
        box_left = boundary.x_left_min
        box_top = boundary.y_top_min
        box_right = boundary.x_right_max
        box_bottom = boundary.y_bottom_max
        box_width = box_right - box_left
        box_height = box_bottom - box_top

        self.logger.debug(
            f"Drawing boundary box: left={box_left:.0f}, top={box_top:.0f}, width={box_width:.0f}, height={box_height:.0f}"
        )

        draw_box_js = f"""
        (function() {{
            // 移除旧的框
            const oldBox = document.getElementById('agentmatrix-boundary-box');
            if (oldBox) {{
                oldBox.remove();
            }}

            // 创建边界框（直接添加到body）
            const box = document.createElement('div');
            box.id = 'agentmatrix-boundary-box';
            box.style.position = 'fixed';
            box.style.left = '{box_left}px';
            box.style.top = '{box_top}px';
            box.style.width = '{box_width}px';
            box.style.height = '{box_height}px';
            box.style.border = '6px solid #00FF00';
            box.style.backgroundColor = 'transparent';
            box.style.pointerEvents = 'none';
            box.style.zIndex = '999999999';
            box.style.boxShadow = '0 0 15px rgba(0, 255, 0, 0.8)';
            box.style.display = 'block';
            box.style.visibility = 'visible';

            document.body.appendChild(box);

            console.log('Boundary box added to DOM:', box.id, 'size:', box.offsetWidth, 'x', box.offsetHeight);

            return 'boundary-box-drawn';
        }})();
        """

        try:
            result = await asyncio.to_thread(tab.run_js, draw_box_js)
            self.logger.debug(f"Boundary box drawn: {result}")
            return result
        except Exception as e:
            self.logger.warning(f"Failed to draw boundary box: {e}")
            return f"failed: {e}"

    async def draw_vertical_line(self, tab: TabHandle, region: "RegionBounds") -> str:
        """
        在指定区域画出竖线（左右2分）

        Args:
            tab: 标签页句柄
            region: 区域边界 (x, y, width, height)

        Returns:
            str: 注入的元素的 ID
        """
        if not tab:
            tab = await self.get_tab()

        # 计算竖线位置（区域中心）
        line_x = region.x + region.width / 2

        line_js = f"""
        (function() {{
            const container = document.createElement('div');
            container.id = 'agentmatrix-vertical-line-container';
            container.style.position = 'absolute';
            container.style.left = '{region.x}px';
            container.style.top = '{region.y}px';
            container.style.width = '{region.width}px';
            container.style.height = '{region.height}px';
            container.style.pointerEvents = 'none';
            container.style.zIndex = '999999';

            const line = document.createElement('div');
            line.style.position = 'absolute';
            line.style.left = '50%';
            line.style.top = '0';
            line.style.width = '3px';
            line.style.height = '100%';
            line.style.backgroundColor = '#FFD700';
            line.style.boxShadow = '0 0 5px rgba(255, 215, 0, 0.8)';

            container.appendChild(line);
            document.body.appendChild(container);

            return 'agentmatrix-vertical-line-container';
        }})();
        """

        try:
            element_id = await asyncio.to_thread(tab.run_js, line_js)
            self.logger.debug(f"Vertical line drawn at x={line_x:.0f}")
            return element_id
        except Exception as e:
            self.logger.exception(f"Failed to draw vertical line: {e}")
            raise

    async def draw_horizontal_line(self, tab: TabHandle, region: "RegionBounds") -> str:
        """
        在指定区域画出横线（上下2分）

        Args:
            tab: 标签页句柄
            region: 区域边界 (x, y, width, height)

        Returns:
            str: 注入的元素的 ID
        """
        if not tab:
            tab = await self.get_tab()

        # 计算横线位置（区域中心）
        line_y = region.y + region.height / 2

        line_js = f"""
        (function() {{
            const container = document.createElement('div');
            container.id = 'agentmatrix-horizontal-line-container';
            container.style.position = 'absolute';
            container.style.left = '{region.x}px';
            container.style.top = '{region.y}px';
            container.style.width = '{region.width}px';
            container.style.height = '{region.height}px';
            container.style.pointerEvents = 'none';
            container.style.zIndex = '999999';

            const line = document.createElement('div');
            line.style.position = 'absolute';
            line.style.left = '0';
            line.style.top = '50%';
            line.style.width = '100%';
            line.style.height = '3px';
            line.style.backgroundColor = '#FFD700';
            line.style.boxShadow = '0 0 5px rgba(255, 215, 0, 0.8)';

            container.appendChild(line);
            document.body.appendChild(container);

            return 'agentmatrix-horizontal-line-container';
        }})();
        """

        try:
            element_id = await asyncio.to_thread(tab.run_js, line_js)
            self.logger.debug(f"Horizontal line drawn at y={line_y:.0f}")
            return element_id
        except Exception as e:
            self.logger.exception(f"Failed to draw horizontal line: {e}")
            raise

    async def remove_vertical_line(self, tab: TabHandle):
        """移除竖线"""
        if not tab:
            tab = await self.get_tab()

        remove_js = """
        (function() {
            const container = document.getElementById('agentmatrix-vertical-line-container');
            if (container) {
                container.remove();
                return true;
            }
            return false;
        })();
        """

        try:
            await asyncio.to_thread(tab.run_js, remove_js)
            self.logger.debug("Vertical line removed")
        except Exception as e:
            self.logger.warning(f"Failed to remove vertical line: {e}")

    async def remove_horizontal_line(self, tab: TabHandle):
        """移除横线"""
        if not tab:
            tab = await self.get_tab()

        remove_js = """
        (function() {
            const container = document.getElementById('agentmatrix-horizontal-line-container');
            if (container) {
                container.remove();
                return true;
            }
            return false;
        })();
        """

        try:
            await asyncio.to_thread(tab.run_js, remove_js)
            self.logger.debug("Horizontal line removed")
        except Exception as e:
            self.logger.warning(f"Failed to remove horizontal line: {e}")

    async def highlight_region(
        self, tab: TabHandle, bounds: dict, color: str = "#FF0000", label: str = ""
    ):
        """
        加亮指定的矩形区域。

        Args:
            tab: 标签页句柄
            bounds: 区域边界 {"x": int, "y": int, "width": int, "height": int}
            color: 边框颜色（十六进制）
            label: 区域标签（可选）
        """
        if not tab:
            tab = await self.get_tab()

        highlight_js = f"""
        (function() {{
            const div = document.createElement('div');
            div.style.position = 'fixed';
            div.style.left = '{bounds["x"]}px';
            div.style.top = '{bounds["y"]}px';
            div.style.width = '{bounds["width"]}px';
            div.style.height = '{bounds["height"]}px';
            div.style.border = '3px solid {color}';
            div.style.backgroundColor = '{color}33';  // 20% 透明度
            div.style.pointerEvents = 'none';
            div.style.zIndex = '999998';
            div.style.boxShadow = '0 0 10px {color}';

            // 添加标签
            if ('{label}') {{
                const labelDiv = document.createElement('div');
                labelDiv.style.position = 'absolute';
                labelDiv.style.top = '-25px';
                labelDiv.style.left = '0';
                labelDiv.style.backgroundColor = '{color}';
                labelDiv.style.color = 'white';
                labelDiv.style.padding = '2px 6px';
                labelDiv.style.fontSize = '14px';
                labelDiv.style.fontWeight = 'bold';
                labelDiv.style.borderRadius = '3px';
                labelDiv.textContent = '{label}';
                div.appendChild(labelDiv);
            }}

            div.id = 'agentmatrix-highlight-' + Date.now() + '-' + Math.random();
            document.body.appendChild(div);
            return div.id;
        }})();
        """

        try:
            element_id = await asyncio.to_thread(tab.run_js, highlight_js)
            self.logger.debug(f"Region highlighted: {element_id} at {bounds}")
            return element_id
        except Exception as e:
            self.logger.exception(f"Failed to highlight region: {e}")
            raise

    async def highlight_elements(
        self,
        tab: TabHandle,
        elements: list,
        color: str = "#00FF00",
        labels: list = None,
    ):
        """
        加亮多个 DOM 元素。

        Args:
            tab: 标签页句柄
            elements: PageElement 对象列表
            color: 边框颜色（十六进制）
            labels: 每个元素的标签列表（可选）

        Returns:
            list: 注入的 highlight 元素的 ID 列表
        """
        if not tab:
            tab = await self.get_tab()

        if labels is None:
            labels = [str(i + 1) for i in range(len(elements))]

        highlight_ids = []

        for i, element_wrapper in enumerate(elements):
            try:
                # 获取底层 ChromiumElement
                chromium_element = element_wrapper.get_element()

                # 获取元素位置和大小
                rect = await asyncio.to_thread(lambda: chromium_element.rect)
                bounds = {
                    "x": rect.location[0],
                    "y": rect.location[1],
                    "width": rect.size[0],
                    "height": rect.size[1],
                }

                # 滚动到元素可见（如果需要）
                await asyncio.to_thread(chromium_element.scroll.to_view)

                label = labels[i] if i < len(labels) else str(i + 1)
                highlight_id = await self.highlight_region(tab, bounds, color, label)
                highlight_ids.append(highlight_id)

            except Exception as e:
                self.logger.warning(f"Failed to highlight element {i}: {e}")

        self.logger.debug(f"Highlighted {len(highlight_ids)} elements")
        return highlight_ids

    async def remove_highlights(self, tab: TabHandle):
        """
        移除所有加亮元素。

        Args:
            tab: 标签页句柄
        """
        if not tab:
            tab = await self.get_tab()

        remove_js = """
        (function() {
            const highlights = document.querySelectorAll('[id^="agentmatrix-highlight-"]');
            highlights.forEach(el => el.remove());
            return highlights.length;
        })();
        """

        try:
            count = await asyncio.to_thread(tab.run_js, remove_js)
            self.logger.debug(f"Removed {count} highlights")
        except Exception as e:
            self.logger.warning(f"Failed to remove highlights: {e}")

    async def get_elements_in_bounds(self, tab: TabHandle, bounds: dict) -> list:
        """
        获取指定边界内的所有可交互元素。

        Args:
            tab: 标签页句柄
            bounds: {"x": int, "y": int, "width": int, "height": int}

        Returns:
            list: PageElement 对象列表
        """
        if not tab:
            tab = await self.get_tab()

        # 先获取所有可交互元素
        _, button_elements = await self.scan_elements(tab)

        # 过滤在边界内的元素
        elements_in_bounds = []
        x_min, x_max = bounds["x"], bounds["x"] + bounds["width"]
        y_min, y_max = bounds["y"], bounds["y"] + bounds["height"]

        for text, element_wrapper in button_elements.items():
            try:
                chromium_element = element_wrapper.get_element()
                rect = await asyncio.to_thread(lambda: chromium_element.rect)

                elem_x, elem_y = rect.location
                elem_w, elem_h = rect.size

                # 检查元素是否与边界相交（至少有部分在边界内）
                if (
                    elem_x < x_max
                    and elem_x + elem_w > x_min
                    and elem_y < y_max
                    and elem_y + elem_h > y_min
                ):
                    elements_in_bounds.append(element_wrapper)

            except Exception as e:
                self.logger.debug(f"Error checking element bounds: {e}")
                continue

        self.logger.debug(
            f"Found {len(elements_in_bounds)} elements in bounds {bounds}"
        )
        return elements_in_bounds

    async def get_elements_crossed_by_line(
        self, tab: TabHandle, line_type: str, position: float = None
    ) -> list:
        """
        获取被坐标线穿过的可交互元素。

        Args:
            tab: 标签页句柄
            line_type: "vertical" (竖线) 或 "horizontal" (横线)
            position: 坐标线的位置（像素）。如果为 None，使用屏幕中心

        Returns:
            list: PageElement 对象列表，按坐标排序
        """
        if not tab:
            tab = await self.get_tab()

        if position is None:
            # 默认使用屏幕中心
            viewport_size = await asyncio.to_thread(lambda: tab.rect.size)
            if line_type == "vertical":
                position = viewport_size[0] / 2
            else:  # horizontal
                position = viewport_size[1] / 2

        # 获取所有可交互元素
        _, button_elements = await self.scan_elements(tab)

        crossed_elements = []
        tolerance = 10  # 容差（像素）

        for text, element_wrapper in button_elements.items():
            try:
                chromium_element = element_wrapper.get_element()
                rect = await asyncio.to_thread(lambda: chromium_element.rect)

                elem_x, elem_y = rect.location
                elem_w, elem_h = rect.size

                if line_type == "vertical":
                    # 检查竖线是否穿过元素
                    if elem_x - tolerance <= position <= elem_x + elem_w + tolerance:
                        crossed_elements.append(
                            (element_wrapper, elem_y)
                        )  # 保存Y坐标用于排序
                else:  # horizontal
                    # 检查横线是否穿过元素
                    if elem_y - tolerance <= position <= elem_y + elem_h + tolerance:
                        crossed_elements.append(
                            (element_wrapper, elem_x)
                        )  # 保存X坐标用于排序

            except Exception as e:
                self.logger.debug(f"Error checking element crossed by line: {e}")
                continue

        # 按坐标排序
        crossed_elements.sort(key=lambda x: x[1])

        # 只返回元素对象
        result = [item[0] for item in crossed_elements]

        self.logger.debug(
            f"Found {len(result)} elements crossed by {line_type} line at {position}"
        )
        return result

    async def get_interactive_elements(self, tab: TabHandle) -> dict:
        """
        获取页面上所有可交互元素（去重后）。

        Args:
            tab: 标签页句柄

        Returns:
            dict: {"links": {url: text}, "buttons": {text: PageElement}}
        """
        if not tab:
            tab = await self.get_tab()

        return await self.scan_elements(tab)

    async def draw_crosshair_at(self, tab: TabHandle, x: float, y: float) -> str:
        """
        在指定位置画十字坐标线

        Args:
            tab: 标签页句柄
            x: 竖线位置（像素）
            y: 横线位置（像素）

        Returns:
            str: 注入的 crosshair 元素的 ID
        """
        if not tab:
            tab = await self.get_tab()

        # 获取视口大小
        viewport_size = await asyncio.to_thread(lambda: tab.rect.size)

        # 注入 CSS 和 HTML（参考旧代码，去掉 Promise）
        crosshair_js = f"""
        (function() {{
            console.log('Drawing crosshair at x={x}, y={y}');

            // 创建容器
            const container = document.createElement('div');
            container.id = 'agentmatrix-crosshair-container';
            container.style.position = 'absolute';
            container.style.left = '0px';
            container.style.top = '0px';
            container.style.width = '100%';
            container.style.height = '100%';
            container.style.pointerEvents = 'none';
            container.style.zIndex = '999999';

            // 竖线
            const vLine = document.createElement('div');
            vLine.style.position = 'absolute';
            vLine.style.left = '{x}px';
            vLine.style.top = '0px';
            vLine.style.width = '3px';
            vLine.style.height = '100%';
            vLine.style.backgroundColor = '#FFD700';
            vLine.style.boxShadow = '0 0 5px rgba(255, 215, 0, 0.8)';
            vLine.style.opacity = '0.9';

            // 横线
            const hLine = document.createElement('div');
            hLine.style.position = 'absolute';
            hLine.style.left = '0px';
            hLine.style.top = '{y}px';
            hLine.style.width = '100%';
            hLine.style.height = '3px';
            hLine.style.backgroundColor = '#FFD700';
            hLine.style.boxShadow = '0 0 5px rgba(255, 215, 0, 0.8)';
            hLine.style.opacity = '0.9';

            container.appendChild(vLine);
            container.appendChild(hLine);
            document.body.appendChild(container);

            console.log('Crosshair appended to body');

            return 'agentmatrix-crosshair-container';
        }})();
        """

        try:
            self.logger.info(f"About to draw crosshair at x={x:.0f}, y={y:.0f}")
            element_id = await asyncio.to_thread(tab.run_js, crosshair_js)
            self.logger.info(f"Crosshair drawn at ({x:.0f}, {y:.0f}), ID: {element_id}")
            return element_id
        except Exception as e:
            self.logger.error(f"Failed to draw crosshair at ({x}, {y}): {e}")
            raise

    async def draw_mouse_cursor_at(self, tab: TabHandle, x: float, y: float) -> str:
        """
        在指定位置画鼠标光标

        Args:
            tab: 标签页句柄
            x: 鼠标尖端位置（像素）
            y: 鼠标尖端位置（像素）

        Returns:
            str: 注入的鼠标元素 ID
        """
        if not tab:
            tab = await self.get_tab()

        # 定义鼠标光标的形状（使用 SVG）
        # 鼠标尖端指向 (x, y)，向左上方延伸
        mouse_js = f"""
        (function() {{
            console.log('Drawing mouse cursor at x={x}, y={y}');

            // 移除旧的鼠标
            const oldMouse = document.getElementById('agentmatrix-mouse-cursor');
            if (oldMouse) {{
                oldMouse.remove();
            }}

            // 创建鼠标容器（使用 SVG）
            const container = document.createElement('div');
            container.id = 'agentmatrix-mouse-cursor';
            container.style.position = 'absolute';
            container.style.left = '0px';
            container.style.top = '0px';
            container.style.pointerEvents = 'none';
            container.style.zIndex = '999999';

            // 鼠标尺寸
            const width = 24;
            const height = 24;

            // 标准鼠标光标：箭头 + 斜尾巴（基于Bootstrap Icons和Windows标准光标）
            // 坐标说明：尖端(0,0) -> 左边(0,20) -> 内收(6,14) -> 尾巴(9,17) -> (9,14) -> (14,14) -> (6,6) -> 闭合
            const svg = `
            <svg width="${{width}}" height="${{height}}" viewBox="0 0 ${{width}} ${{height}}" xmlns="http://www.w3.org/2000/svg">
                <polygon points="0,0 0,20 6,14 9,17 9,14 14,14 6,6"
                         fill="white"
                         stroke="#FF0000"
                         stroke-width="1.5"
                         style="filter: drop-shadow(2px 2px 2px rgba(0,0,0,0.5));"/>
            </svg>
            `;

            container.innerHTML = svg;
            // 尖端在 x, y，所以容器要向左上方偏移
            container.style.left = ({x} - width) + 'px';
            container.style.top = ({y} - height) + 'px';

            document.body.appendChild(container);

            console.log('Mouse cursor appended to body');

            return 'agentmatrix-mouse-cursor';
        }})();
        """

        try:
            self.logger.info(f"About to draw mouse cursor at x={x:.0f}, y={y:.0f}")
            element_id = await asyncio.to_thread(tab.run_js, mouse_js)
            self.logger.info(
                f"Mouse cursor drawn at ({x:.0f}, {y:.0f}), ID: {element_id}"
            )
            return element_id
        except Exception as e:
            self.logger.error(f"Failed to draw mouse cursor at ({x}, {y}): {e}")
            raise

    async def get_all_clickable_elements(self, tab: TabHandle) -> list:
        """
        获取页面上所有可点击的元素

        Args:
            tab: 标签页句柄

        Returns:
            list: PageElement 对象列表
        """
        if not tab:
            tab = await self.get_tab()

        # JavaScript 查找所有可点击元素
        find_clickable_js = """
        return (function() {
            const clickable = [];
            const selectors = [
                'a[href]',
                'button:not([disabled])',
                'input:not([disabled])',
                'textarea:not([disabled])',
                'select:not([disabled])',
                '[onclick]',
                '[role="button"]',
                '[contenteditable="true"]'
            ];

            selectors.forEach(selector => {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    // 检查元素是否可见
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        const style = window.getComputedStyle(el);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            clickable.push(el);
                        }
                    }
                });
            });

            // 去重
            return [...new Set(clickable)];
        })();
        """

        try:
            chromium_elements = await asyncio.to_thread(tab.run_js, find_clickable_js)
            self.logger.info(
                f"Found {len(chromium_elements) if chromium_elements else 0} clickable elements"
            )

            if not chromium_elements:
                return []

            # 转换为 DrissionPageElement 对象
            elements = [DrissionPageElement(elem) for elem in chromium_elements]
            return elements

        except Exception as e:
            self.logger.warning(f"Failed to get clickable elements: {e}")
            return []

    async def get_element_rect(self, tab: TabHandle, element: "PageElement") -> dict:
        """
        获取元素的位置和大小

        Args:
            tab: 标签页句柄
            element: PageElement 对象

        Returns:
            dict: {'x': x, 'y': y, 'width': w, 'height': h}
        """
        if not tab:
            tab = await self.get_tab()

        # 获取 Chromium 元素
        chromium_element = element.get_element()

        # 获取元素位置
        rect = await asyncio.to_thread(lambda: chromium_element.rect)

        return {
            "x": rect.location[0],
            "y": rect.location[1],
            "width": rect.size[0],
            "height": rect.size[1],
        }
