"""
!!! 过时待删除或者重做 !!!

爬虫技能的公共辅助方法

提供链接筛选、按钮选择等 LLM 决策功能。
"""

import json
import re
import asyncio
from collections import deque
from typing import Dict, List, Optional, Any


class CrawlerHelperMixin:
    """
    爬虫技能的公共辅助方法 Mixin

    依赖：
    - self.cerebellum.backend.think() - LLM 调用
    - self.logger - 日志记录
    """

    async def _get_full_page_markdown(self, tab, ctx, original_url: str = None) -> str:
        """
        获取完整页面的 Markdown，自动识别 HTML/PDF

        Args:
            tab: 浏览器标签页句柄
            ctx: 上下文对象（可选，用于临时文件保存）
            original_url: 原始URL（可选，用于处理Chrome PDF viewer等转换后的URL）

        Returns:
            str: Markdown 格式的页面内容
        """
        from ...core.browser.browser_adapter import PageType

        content_type = await self.browser.analyze_page_type(tab)

        if content_type == PageType.STATIC_ASSET:
            return await self._pdf_to_full_markdown(tab, ctx, original_url)
        else:
            return await self._html_to_full_markdown(tab)



    async def _html_to_full_markdown(self, tab) -> str:
        """
        将 HTML 页面转换为完整 Markdown（带智能回退机制）

        策略：
        1. 如果是 Google/Bing 搜索结果页：直接用 html2text（不使用 trafilatura）
        2. 否则：优先使用 trafilatura（智能提取正文），失败则回退到 html2text

        Args:
            tab: 浏览器标签页句柄

        Returns:
            str: Markdown 格式的页面内容
        """
        import trafilatura
        import re
        import html2text

        raw_html = tab.html
        url = self.browser.get_tab_url(tab)

        # 判断是否是搜索结果页
        is_google_search = 'google.com/search' in url or 'www.google.' in url
        is_bing_search = 'bing.com/search' in url
        is_search_results = is_google_search or is_bing_search

        # 预处理：移除翻译按钮（字符串替换方式）
        if is_search_results:
            if is_google_search:
                # Google: <a><span>翻译此页</span></a> - 删除整个a标签
                raw_html = re.sub(
                    r'<a\s+[^>]*><span[^>]*>\s*翻译此页\s*</span></a>',
                    '',
                    raw_html,
                    flags=re.IGNORECASE
                )
                raw_html = re.sub(
                    r'<a\s+[^>]*href="https://translate\.google\.com[^"]*"[^>]*>.*?</a>',
                    '',
                    raw_html,
                    flags=re.IGNORECASE | re.DOTALL
                )
                # 也处理单引号的情况
                raw_html = re.sub(
                    r"<a\s+[^>]*href='https://translate\.google\.com[^']*'[^>]*>.*?</a>",
                    '',
                    raw_html,
                    flags=re.IGNORECASE | re.DOTALL
                )
                #self.logger.debug("✓ Removed Google translate buttons via string replacement")
            elif is_bing_search:
                # Bing: <span>翻译此结果</span> - 只删除span
                raw_html = re.sub(
                    r'<span[^>]*>\s*翻译此结果\s*</span>',
                    '',
                    raw_html,
                    flags=re.IGNORECASE
                )
                #self.logger.debug("✓ Removed Bing translate buttons via string replacement")

            # 搜索结果页直接使用 html2text
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            converter.body_width = 0
            converter.ignore_emphasis = False

            markdown = converter.handle(raw_html)
            self.logger.info(f"✓ Search results page converted with html2text: {len(markdown)} chars")
            return markdown or ""

        
            

        # 尝试 trafilatura 提取正文
        markdown = trafilatura.extract(
            raw_html,
            include_links=True,
            include_formatting=True,
            output_format='markdown',
            url=url
        )
        #self.logger.debug(f"\n\n {markdown} \n\n")

        # ✅ 回退机制：如果 trafilatura 提取失败或内容太少，使用 html2text
        if not markdown or len(markdown.strip()) < 150:
            self.logger.debug("⚠️ Trafilatura 提取失败或内容太少，回退到 html2text")
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = False
            converter.body_width = 0
            converter.ignore_emphasis = False
            markdown = converter.handle(raw_html)
            self.logger.debug(f"✓ html2text 回退成功: {len(markdown)} chars")

        return markdown or ""

    async def _pdf_to_full_markdown(self, tab, ctx, original_url: str = None) -> str:
        """
        将 PDF 转换为完整 Markdown

        Args:
            tab: 浏览器标签页句柄
            ctx: 上下文对象（可选，用于临时文件保存）
            original_url: 原始URL（可选，用于处理Chrome PDF viewer等转换后的URL）

        Returns:
            str: Markdown 格式的 PDF 内容
        """
        # 下载 PDF 到本地
        pdf_path = await self.browser.save_static_asset(tab, original_url)

        # 检查tab是否卡在PDF viewer页面（chrome-extension://）
        # 在开始长时间PDF转换前检查，避免转换完成后tab已经异常
        current_url = tab.url if hasattr(tab, 'url') else ""
        if current_url.startswith('chrome-extension://'):
            self.logger.warning(f"⚠️ Tab卡在PDF viewer页面 ({current_url})，正在修复...")
            # Navigate到about:blank让tab脱离PDF viewer状态
            await self.browser.navigate(tab, "about:blank")
            await asyncio.sleep(0.5)
            self.logger.info("✓ Tab已修复，脱离PDF viewer状态")

        # 调用 PDF 转换（在线程池中执行，避免阻塞）
        markdown = await asyncio.to_thread(
            self._convert_pdf_to_markdown_text,
            pdf_path
        )

        # 可选：保存到临时文件（如果 ctx 支持）
        if hasattr(ctx, 'temp_file_dir') and ctx.temp_file_dir:
            self._save_temp_markdown(markdown, pdf_path, ctx.temp_file_dir)

        return markdown

    def _convert_pdf_to_markdown_text(self, pdf_path: str) -> str:
        """
        将 PDF 文件转换为 Markdown 文本（核心实现）

        Args:
            pdf_path: PDF 文件路径

        Returns:
            str: Markdown 格式的文本

        Raises:
            Exception: PDF 转换失败
        """
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
        import fitz

        try:
            # 获取 PDF 总页数
            with fitz.open(pdf_path) as doc:
                total_pages = len(doc)

            self.logger.debug(f"PDF总页数: {total_pages}")

            # 初始化 marker 模型
            self.logger.debug("加载 marker 模型...")
            converter = PdfConverter(
                artifact_dict=create_model_dict(),
            )

            # 执行转换
            self.logger.debug("正在转换 PDF 到 Markdown...")
            rendered = converter(pdf_path)

            # 从渲染结果中提取文本
            text, _, images = text_from_rendered(rendered)

            self.logger.debug(f"转换完成! 共 {len(text)} 个字符")

            return text

        except Exception as e:
            self.logger.error(f"PDF 转换失败: {e}")
            raise

    def _save_temp_markdown(self, markdown: str, pdf_path: str, temp_dir: str):
        """
        保存临时 Markdown 文件（用于调试）

        Args:
            markdown: Markdown 文本
            pdf_path: 原始 PDF 路径
            temp_dir: 临时目录
        """
        import os
        from slugify import slugify

        os.makedirs(temp_dir, exist_ok=True)
        filename = slugify(f"pdf_{os.path.basename(pdf_path)}") + ".md"
        temp_path = os.path.join(temp_dir, filename)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        self.logger.info(f"📄 保存临时 Markdown: {temp_path}")


    async def is_navigation_page(self, tab, url: str) -> tuple:
        """
        判断页面是否为导航页（首页/频道页/目录页）

        判断标准：
        1. URL深度检查：首页(path长度 <= 1)很可能是导航页
        2. Open Graph检查：og:type="website" 通常是首页或频道页
        3. 链接密度检查：如果30%以上的文字都是链接，或总字数很少，极大概率是导航页

        Args:
            tab: 浏览器标签页
            url: 当前页面URL

        Returns:
            (is_navigation, reason): 是否为导航页及判断原因
        """
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        path = parsed_url.path

        # 标准1: URL深度检查 - 首页通常是导航页
        if len(path) <= 1 or path == "/":
            return True, "URL is homepage (root path)"

        # 标准2: Open Graph 检查
        try:
            og_type_tag = tab.ele('css:meta[property="og:type"]', timeout=1)
            if og_type_tag:
                og_content = og_type_tag.attr('content')
                if og_content == 'website':
                    return True, f"Open Graph type is 'website' (not 'article')"
        except:
            pass  # 如果找不到或出错，继续其他检查

        # 标准3: 链接密度检查
        try:
            # 获取所有文本 - DrissionPage 需要使用正确的方法
            # 先获取 body 元素，再获取文本
            try:
                body = tab.ele('tag:body', timeout=2)
                if body:
                    all_text = body.text.strip()
                else:
                    all_text = ""
            except:
                all_text = ""

            total_length = len(all_text)

            if total_length > 0:
                # 获取所有链接文本
                link_elements = tab.eles('tag:a')
                link_text_length = 0

                for link in link_elements:
                    try:
                        link_text = link.text.strip()
                        link_text_length += len(link_text)
                    except:
                        continue

                # 计算链接密度
                link_density = link_text_length / total_length

                #self.logger.debug(f"Link density check: {link_density:.1%}, total length: {total_length}")

                # 判断：链接密度 > 30% 或总字数很少 (<500字符)
                if link_density > 0.3:
                    return True, f"Link density {link_density:.1%} > 30%"
                elif total_length < 500:
                    return True, f"Total text length ({total_length}) is very short"

        except Exception as e:
            self.logger.debug(f"Link density check failed: {e}")
            pass  # 链接密度检查失败，不判定

        # 如果都不满足，判定为内容页
        return False, "Does not meet navigation page criteria"


    async def get_markdown_via_jina(self, url: str, timeout: int = 30) -> str:
        """
        通过 r.jina.ai API获取页面的 Markdown 格式
        支持使用 JINA_API_KEY 环境变量（如果配置了则使用，否则使用免费API）

        Args:
            url: 目标页面URL
            timeout: 超时时间（秒）

        Returns:
            Markdown 格式的页面内容
        """
        import aiohttp
        import os

        jina_url = f"https://r.jina.ai/{url}"

        # 获取 API Key（可选）
        api_key = os.getenv("JINA_API_KEY")

        # 设置请求头
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            self.logger.debug(f"Using Jina API key for request")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    jina_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    response.raise_for_status()
                    markdown = await response.text()
                    return markdown
            except asyncio.TimeoutError:
                raise Exception(f"Timeout fetching markdown from jina.ai for URL: {url}")
            except Exception as e:
                raise Exception(f"Failed to fetch markdown from jina.ai: {e}")


    def extract_navigation_links(self, markdown: str) -> list:
        """
        从 Markdown 文本中提取所有链接

        过滤规则：
        1. 忽略纯图片链接（text 以 "![", ".png", ".jpg", ".jpeg", ".gif", ".svg" 等开头）
        2. 图片+文本链接：只保留文本部分（移除图片标记）
        3. 去重

        Args:
            markdown: Markdown 格式的文本

        Returns:
            链接列表，每个链接包含 {"url": str, "title": str}
        """
        from dataclasses import dataclass

        @dataclass
        class NavigationLink:
            url: str
            title: str

        # Markdown 链接格式: [text](url)
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        matches = re.findall(link_pattern, markdown)

        # 去重并过滤
        seen_urls = set()
        unique_links = []

        for raw_text, url in matches:
            if url in seen_urls:
                continue

            # 清理链接文本
            text = raw_text.strip()

            # 规则1: 忽略纯图片链接
            # 检查是否是图片标记（![...] 或以图片扩展名结尾）
            if text.startswith('!['):
                # 纯图片链接，跳过
                continue

            # 检查是否只包含图片扩展名（常见的图片文件名）
            image_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp']
            if any(text.lower().endswith(ext) for ext in image_extensions):
                # 看起来像纯图片文件名，跳过
                continue

            # 规则2: 图片+文本链接，移除图片标记
            # 移除嵌套的图片标记 ![alt](url)
            text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

            # 清理多余的空格
            text = ' '.join(text.split())

            # 如果清理后文本为空或太短，跳过
            if not text or len(text) < 2:
                continue

            seen_urls.add(url)
            unique_links.append(NavigationLink(url=url, title=text))

        return unique_links

    def format_navigation_links_as_markdown(self, links: list, page_url: str = "") -> str:
        """
        将导航页链接格式化为 Markdown（类似搜索结果格式）

        Args:
            links: extract_navigation_links() 返回的链接列表
            page_url: 当前页面URL（用于提取域名）

        Returns:
            格式化的 Markdown 文本，链接格式为 [🔗Link1 To: example.com]
        """
        from urllib.parse import urlparse

        lines = []

        # 从URL提取域名
        domain = ""
        if page_url:
            try:
                parsed = urlparse(page_url)
                domain = parsed.netloc
            except:
                pass

        # 标题
        if domain:
            lines.append(f"# 导航页链接 - {domain}")
        else:
            lines.append("# 导航页链接")
        lines.append("")
        lines.append("")

        # 格式化每个链接
        for idx, link in enumerate(links, start=1):
            # 提取域名用于 link_id
            try:
                link_domain = urlparse(link.url).netloc
            except:
                link_domain = "unknown"

            # 生成链接ID（与搜索结果格式一致）
            link_id = f"Link{idx} To: {link_domain}"

            # 格式：[🔗Link1 To: example.com]
            lines.append(f"[🔗{link_id}]")
            lines.append(f"**{link.title}**")
            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def build_navigation_link_mapping(self, links: list) -> dict:
        """
        构建导航页链接ID到URL的映射（与搜索结果格式一致）

        Args:
            links: extract_navigation_links() 返回的链接列表

        Returns:
            {"Link1 To: example.com": "https://example.com/..."}
        """
        from urllib.parse import urlparse

        mapping = {}
        for idx, link in enumerate(links, start=1):
            # 提取域名用于 link_id
            try:
                link_domain = urlparse(link.url).netloc
            except:
                link_domain = "unknown"

            # 生成链接ID（与搜索结果格式一致）
            link_id = f"Link{idx} To: {link_domain}"
            mapping[link_id] = link.url

        return mapping

