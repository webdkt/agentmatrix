"""
基于 DrissionPage 库的 BrowserAdapter 实现类。

该实现使用 DrissionPage 的 ChromiumPage 来提供浏览器自动化功能。
支持使用指定的 Chrome profile 路径启动浏览器。
"""

from typing import List, Optional, Any, Union
import time
import os
import hashlib
import requests
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
    KeyAction
)
from core.log_util import AutoLoggerMixin
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


class DrissionPageAdapter(BrowserAdapter,AutoLoggerMixin):
    """
    基于 DrissionPage 库的浏览器适配器实现。

    使用 DrissionPage 的 ChromiumPage 来驱动 Chrome 浏览器。
    支持指定 Chrome profile 路径来实现会话持久化。
    """
    _custom_log_level = logging.DEBUG
    def __init__(self, profile_path: Optional[str] = None, download_path: Optional[str] = None):
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


    async def start(self, headless: bool = False):
        """
        启动浏览器进程。

        Args:
            headless: 是否以无头模式启动浏览器
        """
        os.environ["no_proxy"] = "localhost,127.0.0.1" 
        co = ChromiumOptions().set_user_data_path(self.profile_path)

        # 配置下载路径
        if self.download_path:
            co.set_download_path(self.download_path)

        if headless:
            co.headless()

        # 创建浏览器实例
        self.browser = ChromiumPage(addr_or_opts=co)

    async def close(self):
        """关闭浏览器进程并清理资源"""
        if self.browser:
            try:
                self.browser.quit()
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

        # TODO: 实现创建标签页的逻辑
        pass

    

    async def close_tab(self, tab: TabHandle):
        """关闭指定的标签页"""
        # TODO: 实现关闭标签页的逻辑
        pass

    async def get_tab(self) -> TabHandle:
        """获取当前焦点标签页的句柄"""
        if not self.browser:
            raise RuntimeError("Browser not started. Call start() first.")

        return self.browser.latest_tab

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
            old_url = tab.url if hasattr(tab, 'url') else ""

            

            # 导航到指定URL - DrissionPage 使用 get() 方法
            tab.get(url)

            # 等待页面加载完成 - 简单等待，实际实现可能需要更复杂的等待逻辑
            time.sleep(2)  # 等待页面加载

            # 检查URL是否改变
            new_url = tab.url if hasattr(tab, 'url') else ""
            is_url_changed = old_url != new_url

            # 创建交互报告
            report = InteractionReport(
                is_url_changed=is_url_changed,
                is_dom_changed=is_url_changed  # URL改变通常意味着DOM也改变了
            )

            return report

        except Exception as e:
            self.logger.exception(f"Navigation failed for URL: {url}")
            return InteractionReport(
                error=f"Navigation failed: {str(e)}"
            )

    

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
                if hasattr(tab.states, 'ready_state'):
                    if tab.states.ready_state == 'complete':
                        self.logger.info("DOM is ready (complete)")
                        return True

                # 备用检查：尝试访问 body 元素
                body = tab.ele('body', timeout=0.5)
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
        [Phase 2] 页面稳定化。
        """
        if not tab:
            return False # 防御

        self.logger.info(f"⚓ Stabilizing page: {tab.url}")

        # 1. 基础加载等待
        try:
            # DrissionPage 的 wait.load_start() 有时会卡住，不如直接 wait.doc_loaded()
            # 设置较短超时，因为我们后面有滚动循环
            tab.wait.doc_loaded(timeout=35)
        except Exception:
            pass # 超时也继续，有些页面 JS 加载永远不 finish
        try:
            # 2. 暴力抗干扰 (Anti-Obstruction)
            # 在滚动前先尝试清理一波明显的遮挡
            await self._handle_popups(tab)

            # 3. 智能滚动 (Smart Scroll)
            # 我们不仅要到底，还要确保中间的内容都被触发加载 (Lazy Load)
            start_time = time.time()
            max_duration = 45 # 45秒足够了
            
            # 记录上次高度和指纹，双重校验
            last_height = tab.run_js("return document.body.scrollHeight;")
            no_change_count = 0 
            
            # 分段滚动策略：不像人类那样慢慢滑，直接分段跳跃
            # 每次向下滚动一屏的高度
            viewport_height = tab.run_js("return window.innerHeight;")
            current_scroll_y = 0

            while time.time() - start_time < max_duration:
                # 向下滚动一屏
                current_scroll_y += viewport_height
                tab.scroll(current_scroll_y) 
                
                # 稍微等待内容渲染
                await asyncio.sleep(0.8)

                # 检查弹窗 (滚动可能触发新的弹窗)
                await self._handle_popups(tab)
                
                # 检查是否到底
                new_height = tab.run_js("return document.body.scrollHeight;")
                current_pos = tab.run_js("return window.scrollY + window.innerHeight;")
                
                # 如果当前位置已经接近页面总高度 (允许 50px 误差)
                if current_pos >= new_height - 50:
                    # 再次确认高度是否真的不再增长了 (有些无限加载需要等一会)
                    if new_height == last_height:
                        no_change_count += 1
                        if no_change_count >= 2: # 连续两次没变，才算真的到底了
                            break
                    else:
                        no_change_count = 0 # 高度变了，重置计数
                        last_height = new_height
                
            # 4. 回到顶部
            tab.scroll.to_top()
            await asyncio.sleep(0.5)
            
            self.logger.info("✅ Page stabilized.")
            return True
        except Exception as e:
            self.logger.exception(f"Page stabilization failed: {e}")
            return True

    async def _handle_popups(self, tab: TabHandle):
        """
        智能弹窗处理：基于文本语义和元素属性，而非死板的 CSS 选择器。
        DrissionPage 的优势在于它可以极快地获取元素文本。
        """
        # 1. 定义我们想点击的“关键词”
        # 这些词通常出现在 Consent 弹窗的按钮上
        allow_keywords = ['accept', 'agree', 'allow', 'consent', 'i understand', 'got it', 'cookie', '接受', '同意', '知道']
        # 这些词出现在关闭按钮上
        close_keywords = ['close', 'later', 'no thanks', 'not now', '关闭', '取消']
        
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
            '.close-icon',
            '[id*="cookie"] button', # Cookie 栏里的按钮通常都是要点的
            '[class*="consent"] button'
        ]
        
        try:
            for selector in common_popup_close_selectors:
                # 查找可见的元素
                eles = tab.eles(selector,timeout=2)
                for ele in eles:
                    # 关键：检查是否可见
                    if ele.states.is_displayed:
                        # 检查文本是否匹配“拒绝”或“关闭”或“同意”
                        txt = ele.text.lower()
                        # 如果是 Cookie 区域的按钮，通常点第一个可见的就行（大概率是 Accept）
                        if 'cookie' in selector or 'consent' in selector:
                            ele.click(by_js=True) # 用 JS 点更稳，不会被遮挡
                            self.logger.info(f"Clicked cookie consent: {txt}")
                            await asyncio.sleep(0.5)
                            return True
                        
                        # 如果是关闭按钮
                        if any(k in txt for k in close_keywords) or not txt: # 有些关闭按钮没字，只有X
                            ele.click(by_js=True)
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
        # 获取当前渲染后的 HTML (包含 JS 执行后的结果)
        raw_html = tab.html

        # A. 尝试使用 Trafilatura 提取高质量 Markdown
        # include_links=True: 保留正文里的链接，这对小脑判断"是否有价值的引用"很有用
        # include_formatting=True: 保留加粗、标题等
        extracted_text = trafilatura.extract(
            raw_html,
            include_links=True,
            include_formatting=True,
            output_format='markdown',
            url=url # 传入 URL 有助于 trafilatura 处理相对路径
        )

        # B. 备选方案 (Fallback)
        if not extracted_text or len(extracted_text) < 50:
            self.logger.info(f"Trafilatura extraction failed or too short for {url}, falling back to simple cleaning.")
            extracted_text = self._fallback_text_extraction(tab)

        # 4. 最终组装
        # 可以在这里加一个 Token 截断，比如保留前 15000 字符，
        # 因为用来做“价值判断”不需要读完几万字的长文。
        final_text = extracted_text[:20000] 
        
        return PageSnapshot(
            url=url,
            title=title,
            content_type=content_type,
            main_text=final_text,
            raw_html=raw_html[:2000] # 只保留一点点头部 HTML 用于 debug，不需要全存
        )

    async def analyze_page_type(self, tab: TabHandle) -> PageType:
        """
        判断页面类型。
        Chrome 浏览器打开 PDF 时，DOM 结构非常特殊。
        """
        try:
            
        
            # 1. 检查 URL 特征
            url = tab.url.lower()
            if url == "about:blank" or url.startswith("chrome://") or url.startswith("data:"):
                self.logger.warning(f"⚠️ Empty/System URL detected: {url}")
                return PageType.ERRO_PAGE

            # 2. 检查 Title 特征 (HTTP 错误通常会反映在标题)
            title = tab.title.lower()
            error_keywords = [
                "404 not found", "page not found", "500 internal server error", 
                "502 bad gateway", "site can't be reached", "privacy error",
                "无法访问", "找不到页面", "服务器错误", "网站无法连接"
            ]
            if any(k in title for k in error_keywords):
                self.logger.warning(f"⚠️ Error Page Title detected: {title}")
                return PageType.ERRO_PAGE

 


            # 1. 获取 MIME Type
            # 这里的 timeout 要极短，因为如果页面还在加载，我们不希望卡住，
            # 但通常 contentType 是 header 返回后就有的
            content_type = tab.run_js("return document.contentType;", timeout=1)
            content_type = content_type.lower() if content_type else ""

            # 2. 判定逻辑
            if "text/html" in content_type or "application/xhtml+xml" in content_type:
                # 特殊情况：有时服务器配置错误，把 JSON 当 HTML 发，
                # 或者这是个纯展示代码的 HTML 页。
                # 但一般按 HTML 处理没错，大不了 Scout 不出东西。
                return PageType.NAVIGABLE
            
            # 常见的非 HTML 类型
            if any(t in content_type for t in ["application/pdf", "image/", "text/plain", "application/json", "text/xml"]):
                return PageType.STATIC_ASSET

            # 3. 兜底：如果 JS 失败（比如 XML 有时不能运行 JS），回退到 URL 后缀
            url = tab.url.lower()
            if any(url.endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.json', '.xml', '.txt']):
                return PageType.STATIC_ASSET

            # 默认视为网页
            return PageType.NAVIGABLE

        except Exception:
            # 如果出错了（比如页面卡死），保守起见当作网页处理，或者根据 URL 判
            return PageType.NAVIGABLE

    

    def _fallback_text_extraction(self, tab: TabHandle) -> str:
        """
        当智能提取失败时，使用 DrissionPage 暴力提取可见文本。
        并做简单的清洗。
        """
        # 移除 script, style 等无关标签
        # DrissionPage 的 .text 属性其实已经处理了大部分，但我们可以更彻底一点
        try:
            # 获取 body 元素
            body = tab.ele('tag:body')

            # 这里的 text 获取的是 "innerText"，即用户可见的文本
            raw_text = body.text

            # 简单的后处理：去除连续空行
            lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
            return "\n".join(lines)
        except Exception as e:
            return f"[Error extracting text: {e}]"

    def _detect_asset_subtype(self, url: str) -> str:
        """
        通过 URL 判断静态资源的子类型。
        """
        url_lower = url.lower()

        if url_lower.endswith('.pdf'):
            return 'pdf'
        elif url_lower.endswith('.json'):
            return 'json'
        elif url_lower.endswith('.xml'):
            return 'xml'
        elif any(url_lower.endswith(ext) for ext in ['.txt', '.log', '.md']):
            return 'text'
        else:
            # 尝试从 content-type 判断（如果有）
            # 这里简化处理，默认为 text
            return 'text'

    async def _get_static_asset_snapshot(self, tab: TabHandle, url: str, title: str, content_type: PageType) -> PageSnapshot:
        """
        处理静态资源的 snapshot。
        """
        subtype = self._detect_asset_subtype(url)

        self.logger.info(f"Creating snapshot for static asset: {subtype} - {url}")

        if subtype == 'pdf':
            return await self._snapshot_pdf_browser(tab, url, title, content_type)
        elif subtype == 'json':
            return await self._snapshot_json(tab, url, title, content_type)
        elif subtype == 'xml':
            return await self._snapshot_xml(tab, url, title, content_type)
        else:
            return await self._snapshot_text(tab, url, title, content_type)

    async def _snapshot_pdf_browser(self, tab: TabHandle, url: str, title: str, content_type: PageType) -> PageSnapshot:
        """
        使用浏览器提取 PDF 文本。
        Chrome 的 PDF viewer 会将 PDF 渲染为 DOM，可以直接提取文本。
        """
        try:
            # 通过 JavaScript 提取 PDF 文本
            text = tab.run_js("return document.body.innerText || ''")

            # 清理和格式化
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            cleaned_text = "\n".join(lines)

            # 限制在 5K 字符
            max_length = 5000
            if len(cleaned_text) > max_length:
                cleaned_text = cleaned_text[:max_length] + "\n\n... (truncated)"

            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text=f"[PDF Document]\n\n{cleaned_text}",
                raw_html=""
            )

        except Exception as e:
            self.logger.exception(f"Failed to extract PDF text: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[PDF Document] (Text extraction failed)",
                raw_html=""
            )

    async def _snapshot_json(self, tab: TabHandle, url: str, title: str, content_type: PageType) -> PageSnapshot:
        """
        提取并格式化 JSON。
        """
        try:
            # 获取原始文本
            text = tab.ele('tag:body').text.strip()

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
                    raw_html=""
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
                    raw_html=""
                )

        except Exception as e:
            self.logger.exception(f"Failed to extract JSON: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[JSON/Text Data] (Extraction failed)",
                raw_html=""
            )

    async def _snapshot_xml(self, tab: TabHandle, url: str, title: str, content_type: PageType) -> PageSnapshot:
        """
        提取并格式化 XML。
        """
        try:
            # 获取原始文本
            text = tab.ele('tag:body').text.strip()

            # 限制在 5K
            max_length = 5000
            if len(text) > max_length:
                text = text[:max_length] + "\n\n... (truncated)"

            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text=f"[XML Data]\n\n```xml\n{text}\n```",
                raw_html=""
            )

        except Exception as e:
            self.logger.exception(f"Failed to extract XML: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[XML Data] (Extraction failed)",
                raw_html=""
            )

    async def _snapshot_text(self, tab: TabHandle, url: str, title: str, content_type: PageType) -> PageSnapshot:
        """
        处理纯文本文件。
        """
        try:
            # 获取文本
            text = tab.ele('tag:body').text.strip()

            # 限制在 5K
            max_length = 5000
            if len(text) > max_length:
                text = text[:max_length] + "\n\n... (truncated)"

            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text=f"[Text File]\n\n```\n{text}\n```",
                raw_html=""
            )

        except Exception as e:
            self.logger.exception(f"Failed to extract text: {e}")
            return PageSnapshot(
                url=url,
                title=title,
                content_type=content_type,
                main_text="[Text File] (Extraction failed)",
                raw_html=""
            )

    async def save_view_as_file(self, tab: TabHandle, save_dir: str) -> Optional[str]:
        """
        如果当前页面是 PDF 预览或纯文本，将其保存为本地文件。
        """
        # TODO: 实现保存视图为文件的逻辑
        pass

    async def save_static_asset(self, tab: TabHandle) -> Optional[str]:
        """
        [针对 STATIC_ASSET]
        保存当前 Tab 显示的内容为文件。

        支持的文件类型：
        - PDF 文件
        - 图片文件 (jpg, png, gif, webp, etc.)
        - 文本文件 (json, txt, xml, etc.)
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

            # 2. 确定保存目录
            save_dir = self.download_path if self.download_path else "downloads"
            Path(save_dir).mkdir(parents=True, exist_ok=True)

            # 3. 解析 URL 获取文件名
            parsed_url = urlparse(url)
            filename = unquote(os.path.basename(parsed_url.path))

            # 如果 URL 没有清晰的文件名，生成一个
            if not filename or '.' not in filename:
                # 根据 URL 路径或生成 UUID
                ext = self._get_extension_from_url(url)
                filename = f"{uuid.uuid4().hex[:8]}{ext}"

            # 4. 判断资源类型并保存
            file_path = os.path.join(save_dir, filename)

            # 判断是否是文本类型
            if self._is_text_content_type(url):
                # 文本类型：直接提取 body 文本
                await self._save_text_asset(tab, file_path)
            else:
                
                tab.download(url, file_path)
                #await self._save_binary_asset(url, file_path)

            self.logger.info(f"Static asset saved to: {file_path}")
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
            '.pdf': '.pdf',
            '.jpg': '.jpg', '.jpeg': '.jpg',
            '.png': '.png',
            '.gif': '.gif',
            '.webp': '.webp',
            '.svg': '.svg',
            '.json': '.json',
            '.txt': '.txt',
            '.xml': '.xml',
            '.html': '.html', '.htm': '.html'
        }

        for ext, file_ext in extensions.items():
            if ext in url_lower:
                return file_ext

        # 默认扩展名
        return '.bin'

    def _is_text_content_type(self, url: str) -> bool:
        """
        判断 URL 是否指向文本内容。
        """
        url_lower = url.lower()
        text_extensions = ['.json', '.txt', '.xml', '.html', '.htm', '.svg']
        return any(url_lower.endswith(ext) for ext in text_extensions)

    async def _save_text_asset(self, tab: TabHandle, file_path: str):
        """
        保存文本类型的资源。
        """
        try:
            # 提取 body 文本
            body = tab.ele('tag:body')
            if not body:
                raise ValueError("No body element found")

            text_content = body.text

            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)

            self.logger.info(f"Text asset saved: {file_path} ({len(text_content)} chars)")

        except Exception as e:
            self.logger.exception(f"Failed to save text asset: {e}")
            raise

    async def _save_binary_asset(self, url: str, file_path: str):
        """
        使用 requests 下载二进制资源。
        """
        try:
            # 使用 requests 下载
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            # 写入文件
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size = os.path.getsize(file_path)
            self.logger.info(f"Binary asset saved: {file_path} ({file_size} bytes)")

        except Exception as e:
            self.logger.exception(f"Failed to save binary asset: {e}")
            raise

    # --- Scouting & Interaction (侦察与交互) ---
    async def scan_elements(self, tab: TabHandle) :
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
            '登录', 'login', 'signin', 'sign in', 'register', '注册', 'sign up', 'signup',
            # 退出/关闭
            'exit', '退出', 'logout', 'log out', 'cancel', '取消', 'close', '关闭',
            # 通用导航
            'home', '首页', 'back', '返回', 'skip', '跳过',
            # 同意/拒绝
            'accept', '接受', 'agree', '同意', 'decline', '拒绝'
        ]

        if not tab: return {}, {}

        # 1. 定义统一选择器 (Method B)
        # 覆盖：链接, 按钮, 图片输入, 提交按钮, 以及伪装成按钮/链接的 div/span
        # 注意：排除 href 为 javascript: mailto: tel: 的链接，这些通常 Agent 处理不了
        selector = (
            '@|tag()=a'  # 所有带 href 属性的 a 标签
            '@|tag()=button'  # 所有 button 标签
            'input@type=button||'  # type=button 的 input
            'input@type=submit||'  # type=submit 的 input
            'input@type=image||'   # type=image 的 input
            '@role=button||'       # role=button 的元素
            '@role=link||'         # role=link 的元素
            '@role=menuitem'       # role=menuitem 的元素
        )
        selector1 = '@|tag()=a@|tag()=button'
        selector2 = 'css:input[type="button"],input[type="submit"], input[type="image"]'
        selector3 = 'css:[role="button"],[role="link"],[role="menuitem"]'
        
        raw_elements = []
        try:
            # 2. 批量获取元素 (DrissionPage 的 eles 方法)
            # timeout 设短点，找不到就算了
            for css_selector in [selector1, selector2, selector3]:
                self.logger.debug(f"Checking: {css_selector}")
                elements = tab.eles(css_selector, timeout=2)
                self.logger.debug(f"Found {len(elements)} elements")
                raw_elements.extend(elements)
            #raw_elements = list(set(raw_elements))  # 去重
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
                # --- 快速过滤 (无网络交互) ---
                tag = ele.tag
                # 获取文本，如果没有可见文本，尝试获取 title 或 aria-label
                # DrissionPage 的 .text 获取的是可见文本，这步其实隐含了可见性检查的一部分，但有些隐藏元素也有 text
                text = ele.text.strip()
                
                # 补充文本源 (针对图标按钮)
                if not text:
                    text = ele.attr('aria-label') or ele.attr('title') or ele.attr('alt') or ""
                    text = text.strip()
                
                # 如果还是没字，跳过 (除非是 input image)
                if not text and tag != 'input':
                    continue

                # --- 黑名单过滤 ---
                # 检查文本是否匹配无价值模式
                text_lower = text.lower()
                should_skip = False
                for pattern in IGNORED_PATTERNS:
                    # 检查是否包含模式（部分匹配）
                    if pattern in text_lower:
                        self.logger.debug(f"⛔ Filtering ignored element: '{text}' (matched '{pattern}')")
                        should_skip = True
                        break
                    # 检查完全匹配
                    if text_lower.strip() == pattern:
                        self.logger.debug(f"⛔ Filtering ignored element: '{text}' (exact match '{pattern}')")
                        should_skip = True
                        break

                if should_skip:
                    continue

                # --- 慢速过滤 (网络交互) ---
                # 检查可见性 (is_displayed 内部会 check visibility, display, opacity)
                # 还要检查尺寸，防止 1x1 的跟踪点
                if not ele.states.is_displayed:
                    continue
                
                rect = ele.rect
                if rect.size[0] < 5 or rect.size[1] < 5: # 忽略极小元素
                    continue

                # --- 分类处理 ---
                
                # A. 链接 (Links) -> 需去重
                if tag == 'a' or ele.attr('role') == 'link':
                    href = ele.attr('href')
                    
                    if not href or len(href) < 2 or href.startswith('#'):
                        continue
                        
                    # 绝对路径化 (DrissionPage 拿到的 href 通常已经是绝对路径，或者是 property)
                    # 如果不是，可以在这里做 urljoin，但 DrissionPage 的 .link 属性通常是好的
                    full_url = ele.link 
                    if not full_url: continue

                    # 去重逻辑：保留描述最长的
                    if full_url in seen_links:
                        existing_link_text = seen_links[full_url]
                        if len(text) > existing_link_text:
                            seen_links[full_url] = text # 更新为更长文本的
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

        

        self.logger.info(f"🔍 Scanned {len(seen_links) + len(button_elements)} elements ({len(seen_links)} links, {len(button_elements)} buttons)")
        return seen_links, button_elements

    async def get_target_element(self,tab, element: Union[str, PageElement] ):
        # 根据 element 类型获取 ChromiumElement
        if isinstance(element, str):
            # 如果是字符串选择器，使用 find_element 查找
            target_element = (await self.find_element(tab, element)).get_element()
        else:
            # 如果是 PageElement 对象，直接获取底层元素
            target_element = element.get_element()

        return target_element


    async def click_and_observe(self, tab: TabHandle, element: Union[str, PageElement]) -> InteractionReport:
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
            raw_text = f"{tab.title}|{tab.ele('body', timeout=0.1).text}" 
            old_fingerprint = hashlib.md5(raw_text.encode('utf-8')).hexdigest()
        except:
            old_fingerprint = ""

        target_element = await self.get_target_element(tab, element)

        # 点击元素
        try:
            target_element.click()
        except Exception as e:
            self.logger.exception(f"Click failed for element: {element}")
            #但不管有啥错，我们继续
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
                new_tabs = self.browser.get_tabs()[old_tab_count:]

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
                    is_dom_changed=is_dom_changed 
                )
            #url 没变化，那等到DOM Ready
            waited_time = time.time()-start_time
            while tab.states.ready_state != 'complete' and waited_time < timeout:
                await asyncio.sleep(0.2)


            # 这时候，可能是dom ready，也可能是超时了，不要紧，直接比较text指纹

            try:
                new_text = f"{tab.title}|{tab.ele('body', timeout=0.1).text}"
                new_fingerprint = hashlib.md5(new_text.encode('utf-8')).hexdigest()
                if old_fingerprint != new_fingerprint:
                    is_dom_changed = True
            except:
                pass # 获取失败视作没变


            # 创建交互报告
            report = InteractionReport(
                new_tabs=new_tabs,
                is_url_changed=is_url_changed,
                is_dom_changed=is_dom_changed 
            )

            return report
        except Exception as e:
            self.logger.exception(f"Click and observe failed for element: {element}")
            return InteractionReport(
                new_tabs=new_tabs,
                is_url_changed=is_url_changed,
                is_dom_changed=is_dom_changed
            )

    # ==========================================
    # Input & Control (精确输入与控制)
    #    用于 Phase 0 (搜索) 或特定表单交互
    # ==========================================

    async def type_text(self, tab: TabHandle, selector: str, text: str, clear_existing: bool = True) -> bool:
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
        ele = tab.ele(selector)
        if ele:
            ele.click()
            await asyncio.sleep(random.uniform(0.1,0.3) )
            ele.input(vals=text,clear=clear_existing)
            return True 
        return False

    async def press_key(self, tab: TabHandle, key: Union[KeyAction, str]) -> InteractionReport:
        """
        在当前页面模拟按键。
        通常用于输入搜索词后按回车。

        Returns:
            InteractionReport: 按键可能会导致页面刷新或跳转 (如按回车提交表单)，
            所以必须返回后果报告，供逻辑层判断是否需要 Soft Restart。
        """
        # TODO: 实现按键逻辑
        pass

    async def click_by_selector(self, tab: TabHandle, selector: str) -> InteractionReport:
        """
        [精确点击] 通过选择器点击特定元素。
        区别于 click_and_observe (那个是基于侦察出的 PageElement 对象)，
        这个方法用于已知页面结构的场景 (如点击搜索按钮)。
        """
        # TODO: 实现选择器点击逻辑
        pass

    async def scroll(self, tab: TabHandle, direction: str = "bottom", distance: int = 0):
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
                # 滚动到页面底部
                tab.scroll.to_bottom()
            elif direction == "top":
                # 滚动到页面顶部
                tab.scroll.to_top()
            elif direction == "down":
                # 向下滚动指定像素
                if distance <= 0:
                    distance = 500  # 默认向下滚动500像素
                tab.scroll.down(distance)
            elif direction == "up":
                # 向上滚动指定像素
                if distance <= 0:
                    distance = 500  # 默认向上滚动500像素
                tab.scroll.up(distance)
            else:
                self.logger.warning(f"Unsupported scroll direction: {direction}")
                return False

            # 短暂等待滚动完成
            await asyncio.sleep(0.5)
            return True

        except Exception as e:
            self.logger.warning(f"Scroll failed: {e}")
            return False

    async def find_element(self, tab: TabHandle, selector: str) -> PageElement:
        """
        根据选择器查找元素。
        用于验证页面是否加载正确 (例如：检查是否存在 'input[name="q"]' 来确认是否在 Google 首页)。

        Args:
            tab: 标签页句柄
            selector: CSS选择器或XPath等定位符

        Returns:
            PageElement: 找到的元素对象

        Raises:
            Exception: 如果元素未找到或查找过程中出现错误
        """
        if not tab:
            tab = await self.get_tab()

        # 使用 DrissionPage 的 ele 方法查找元素
        chromium_element = tab.ele(selector)

        # 如果找不到元素，DrissionPage 会抛出异常，这里我们让它自然抛出
        return DrissionPageElement(chromium_element)