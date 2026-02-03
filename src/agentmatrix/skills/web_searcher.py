import asyncio
import time
import os
import json
import textwrap
import re
from typing import List, Set, Dict, Optional, Any, Deque
from collections import deque
from dataclasses import dataclass, field
from ..skills.utils import sanitize_filename
from ..skills.parser_utils import multi_section_parser

from urllib.parse import quote_plus, urlparse

from ..core.browser.browser_adapter import (
    BrowserAdapter, TabHandle, PageElement, PageSnapshot, PageType
)
from ..core.browser.browser_common import TabSession, BaseCrawlerContext
from ..skills.crawler_helpers import CrawlerHelperMixin
from ..core.browser.drission_page_adapter import DrissionPageAdapter
from ..core.action import register_action

# Search engine configuration
SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}"
}
DEFAULT_SEARCH_ENGINE = "bing"  # Can be configured via environment variable or parameter

# ==========================================
# Prompt 集中管理
# ==========================================

class WebSearcherPrompts:
    """Web Searcher Prompt 集中管理"""

    # ==========================================
    # 1. 章节选择
    # ==========================================

    CHAPTER_SELECTION = """You are searching for information to answer: "{question}"

Current page URL: {url}

Below is the table of contents for a document:

{toc_list}

[Document Preview - First 500 Characters]
{preview}

[Important Note]
The table of contents above was AUTOMATICALLY EXTRACTED from the web page by analyzing heading levels.
Web pages often have messy or inconsistent heading structures. Some "chapters" may not be real content sections.

Use the preview above to help assess whether this document is worth reading.

[Task]
Select the chapters that are LIKELY to contain information relevant to answering the question.

[Rules]
1. First, assess whether this document is relevant by examining the TOC and preview
2. If the document seems irrelevant, select "SKIP_DOC" to skip the entire document
3. If the TOC looks random or unhelpful, select "SKIP_TOC" to process the full document
4. You can select multiple chapters
5. Be conservative - only select chapters that seem directly relevant
6. If you select a parent chapter, ALL its sub-chapters will be included automatically

[Output Format]

First, explain your reasoning (assess document relevance + TOC quality + why you selected these chapters).

Then, output your selections using following format:

====章节选择====
你选择的章节名称1(replace with your choice)
你选择的章节名称2(replace with your choice)
...
====章节选择结束====
One chapter name per line. The chapter names must EXACTLY match the names shown in the TOC above.

OR, if you decided 这个文档不相关:
====章节选择====
SKIP_DOC
====章节选择结束====

OR, if you decided 这个目录没什么用:
====章节选择====
SKIP_TOC
====章节选择结束====

"""

    

    CHAPTER_ERROR_FORMAT = """Your output format is incorrect.

Please use this EXACT format:

====章节选择====
章节名称1(replace with your choice)
章节名称2(replace with your choice)
====章节选择结束====

Make sure:
1. The markers are EXACTLY '====章节选择====' and '====章节选择结束===='
2. One chapter name per line
3. Chapter names EXACTLY match the TOC

Try again."""

    # ==========================================
    # 2. 批处理
    # ==========================================

    BATCH_PROCESSING = """You are reading a document to answer: "{question}"

[Document Info]
- Title: {doc_title}
- Source URL: {url}
- Progress: Page {current_batch} of {total_batches} ({progress_pct}% complete)

{toc_info}

[Notebook - What We Already Know]
{notebook}

[Current Page Content - Page {current_batch}]
(Note: Links are marked as [🔗LinkText]. If you want to visit a link, copy its text (without 🔗) and list it in the "推荐链接" section below.)
====BEGIN OF PAGE====

{batch_text}

====END OF PAGE====

[Task]
Based on the Notebook, Current Page, AND your reading progress, provide a brief summary.

Consider your progress:
- How deep are you in the document?
- Does this document seem relevant to the question?
- Based on document info and toc and current page, is this document likely to contain useful information?

Your response MUST start with ONE of these four headings:

##对问题的回答
If you can provide a clear, complete answer based on the Notebook and Current Page:
- Use this heading
- Provide your answer below
- Keep it concise but complete
- Keep key references (urls) for key information

##值得记录的笔记
If you cannot answer yet, but found NEW and USEFUL information:
- Use this heading
- 记录下有价值的信息到小本本，保持精简概要
- Focus on facts, data, definitions, explanations
- Only extract information NOT already in Notebook
- Always include the source URL

##没有值得记录的笔记继续阅读
If the page doesn't contain new or useful information, but the document still shows promise:
- Use this heading
- Briefly explain why (1 sentence)


##完全不相关的文档应该放弃
If the page is completely irrelevant to the question (navigation, ads, unrelated topics) and you believe the document is not worth reading further:
- Use this heading
- Explain why (1 sentence)
- Skip the rest of this document


[Output Format]

##对问题的回答 (or one of the other three headings)

Your content here...

====推荐链接====
(Optional. If you see links in the text above that are worth visiting, list the LinkText (without 🔗) of those links here, one per line.)
示例链接文本
另一个链接文本
====推荐链接结束====

"""

    BATCH_ERROR_FORMAT = """Your output format is incorrect.

Please start your response with ONE of these four headings (EXACTLY as shown):

##对问题的回答
##值得记录的笔记
##没有值得记录的笔记继续阅读
##完全不相关的文档应该放弃

Then provide your content below the heading.

Examples:

Example 1 (can answer):
##对问题的回答
Python装饰器是一种...

Example 2 (useful info):
##值得记录的笔记
装饰器使用@符号语法...

Example 3 (no new info):
##没有值得记录的笔记继续阅读
这段内容介绍了网站导航，但没有新的有用信息。

Example 4 (irrelevant):
##完全不相关的文档应该放弃
这是一段购物网站的广告内容，完全与装饰器无关。

Try again."""

    # ==========================================
    # 3. 搜索结果页处理
    # ==========================================

    SEARCH_RESULT_BATCH = """You are reviewing SEARCH RESULTS from {search_engine} to answer: "{question}"



[Notebook - What We Already Know]
{notebook}

(Note: Links are marked as [🔗LinkText]. If you want to visit a link, copy its text (without 🔗) and list it in the "##推荐链接" section.)
====BEGIN OF SEARCH RESULTS====

{batch_text}

====END OF SEARCH RESULTS====

[Task]
Review these search results and decide which links are worth visiting to help answer the question.

[Important Rules]
1. If NONE of the search results are relevant to the question, select "SKIP_PAGE" to skip this batch
2. Be SELECTIVE - only choose links that have HIGH probability of containing useful information
3. It's OK to skip if the results don't seem helpful

[Output Format]

If you found relevant links:
##推荐链接
第一个链接(replace with your choice)
另一个链接(replace with your choice)

If NONE of the results are relevant:
##推荐链接
SKIP_PAGE
"""

    # ==========================================
    # 4. 导航页处理
    # ==========================================

    NAVIGATION_PAGE = """You are reviewing a NAVIGATION PAGE to answer: "{question}"


[Notebook - What We Already Know]
{notebook}

(Note: Links are marked as [🔗LinkText]. If you want to visit a link, copy its text (without 🔗) and list it in the "##推荐链接" section.)
====BEGIN OF NAVIGATION PAGE====

{navigation_text}

====END OF NAVIGATION PAGE====

[Task]
This is a navigation/index page containing links to other content. Review these links and select the ones most likely to contain relevant information to answer the question.

[Important Rules]
1. If NONE of the links on this page are relevant to the question, select "SKIP_PAGE" to skip this navigation page
2. Be SELECTIVE - only choose links that have HIGH probability of containing useful information
3. Navigation pages often contain many irrelevant links (home, about, login, etc.) - ignore those
4. It's OK to skip if this navigation page doesn't seem helpful

[Output Format]

If you found relevant links:
##推荐链接
第一个链接(replace with your choice)
另一个链接(replace with your choice)

If NONE of the links are relevant:
##推荐链接
SKIP_PAGE
"""


# ==========================================
# 结构化链接管理器（用于搜索结果和导航页）
# ==========================================

class StructuredLinkManager:
    """
    结构化链接管理器

    用于搜索结果页和导航页的链接解析，支持灵活的链接文本匹配：

    1. 完全匹配 - 例如 "[🔗Link1 To: www.example.com]"
    2. Link编号匹配 - 例如 "Link1", "🔗Link1", "Link 1"
    3. 域名匹配 - 例如 "www.example.com"（匹配第一个）

    这个类是搜索结果和导航页通用的链接解析工具。
    """

    def __init__(self, link_mapping: dict):
        """
        Args:
            link_mapping: 链接ID到URL的映射字典
                         例如 {"Link1 To: www.example.com": "https://example.com/..."}
        """
        self.link_mapping = link_mapping

    def get_url(self, link_text: str) -> Optional[str]:
        """
        灵活的链接文本匹配，支持三种模式

        Args:
            link_text: LLM 返回的链接文本

        Returns:
            匹配的 URL，如果未匹配则返回 None
        """
        import re

        # 模式1: 完全匹配（去掉 🔗 和前后空格）
        exact_match = link_text.replace("🔗", "").strip()
        if exact_match in self.link_mapping:
            return self.link_mapping[exact_match]

        # 模式2: Link编号匹配
        # 提取 "Link1", "Link2" 等编号
        # 支持格式: "Link1", "🔗Link1", "Link 1", "Link 1 To: ..."
        link_pattern = r"Link\s*(\d+)"
        match = re.search(link_pattern, link_text, re.IGNORECASE)
        if match:
            link_num = match.group(1)
            # 在 link_mapping 中找到匹配的
            for link_id in self.link_mapping.keys():
                if link_id.startswith(f"Link{link_num} To:"):
                    return self.link_mapping[link_id]

        # 模式3: 域名匹配
        # 提取域名并查找第一个匹配的
        # 域名可能出现在 "To: www.example.com" 这样的格式中
        to_pattern = r"To:\s*([^\s\]]+)"
        to_match = re.search(to_pattern, link_text)
        if to_match:
            domain = to_match.group(1)
            # 在 link_mapping 中查找包含该域名的第一个
            for link_id, url in self.link_mapping.items():
                if domain in link_id:
                    return url

        # 模式4: 如果直接提供的是纯域名（没有 "To:" 前缀）
        # 也尝试匹配
        clean_text = link_text.strip().strip("[]").replace("🔗", "").strip()
        if clean_text and "." in clean_text and not clean_text.startswith("Link"):
            # 看起来像域名
            for link_id, url in self.link_mapping.items():
                if clean_text in link_id:
                    return url

        # 未匹配
        return None


# ==========================================
# Markdown 链接管理器
# ==========================================

class MarkdownLinkManager:
    """
    Markdown 链接管理器

    核心职责：
    * 去噪：过滤已访问、黑名单链接
    * 语义化替换：将 [Text](Long-URL) 替换为 [🔗Text]
    * 防重名：处理相同 Anchor Text 的情况
    * 信息增强：为无意义文本补充 URL 信息
    * 相对链接转换：将相对URL转换为绝对URL
    """

    def __init__(self, ctx: 'WebSearcherContext', logger=None):
        self.ctx = ctx
        self.logger = logger  # 可选的 logger
        # 核心映射：{ "显示给LLM的唯一文本": "真实URL" }
        self.text_to_url: Dict[str, str] = {}
        # 匹配 Markdown 链接 [text](url) - 包括相对URL和空锚文本
        self.link_pattern = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
        # 无意义文本列表
        self.generic_terms = {
            "click here", "here", "read more", "more", "link", "details",
            "点击这里", "点击", "更多", "详情", "这里", "下载", "download"
        }

    def process(self, markdown_text: str, base_url: str) -> str:
        """
        处理 Markdown：清洗链接，生成唯一文本，建立映射

        Args:
            markdown_text: 原始 Markdown 文本
            base_url: 当前页面的URL，用于处理相对链接

        Returns:
            处理后的 Markdown 文本（链接已替换为 [🔗Text] 格式）
        """
        link_count = 0

        def replace_match(match):
            nonlocal link_count
            text = match.group(1).strip()
            url = match.group(2).strip()

            # 清理链接文本：移除换行符和多余空白
            text = re.sub(r'\s+', ' ', text)  # 多个空白字符替换为单个空格
            text = text.strip()

            # 0. 过滤非HTTP链接（mailto:, javascript: 等）
            if url.startswith(('mailto:', 'javascript:', '#', 'tel:')):
                # 返回纯文本，移除链接
                return text

            # 1. 处理空锚文本：从URL生成描述性文本
            if not text:
                try:
                    parsed_url = urlparse(url)
                    # 尝试从URL提取有意义的文本
                    if parsed_url.netloc:
                        # 使用域名
                        text = parsed_url.netloc
                    else:
                        # 使用URL路径的最后一部分
                        path_parts = parsed_url.path.split('/')
                        text = next((p for p in reversed(path_parts) if p), "链接")
                except Exception:
                    text = "链接"

            # 2. 处理相对URL，转换为绝对URL
            if url.startswith('/'):
                # 相对URL，拼接base URL
                try:
                    parsed_base = urlparse(base_url)
                    absolute_url = f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
                    url = absolute_url
                except Exception:
                    # 解析失败，返回纯文本
                    return text
            elif not url.startswith('http'):
                # 其他格式（如 //example.com 或其他协议），返回纯文本
                return text

            # 3. 过滤逻辑：跳过已访问或黑名单链接
            if not self.ctx.should_process_url(url):
                return text  # 仅保留纯文本，移除链接属性

            # 4. 生成唯一文本键
            unique_text = self._generate_unique_text(text, url)

            # 5. 记录映射
            self.text_to_url[unique_text] = url

            # 6. 替换为 [🔗Text] 格式
            link_count += 1
            return f"[🔗{unique_text}]"

        result = self.link_pattern.sub(replace_match, markdown_text)
        if self.logger:
            self.logger.info(f"🔗 Processed {link_count} links in Markdown")
        return result

    def _generate_unique_text(self, text: str, url: str) -> str:
        """
        生成唯一的文本标识

        Args:
            text: 链接的 Anchor Text
            url: 链接的真实 URL

        Returns:
            唯一的文本标识
        """
        # A. 处理无意义文本 (Generic Terms)
        # 文本过短或无意义时，从 URL 提取提示
        if len(text) < 2 or text.lower() in self.generic_terms:
            try:
                path = urlparse(url).path
                hint = path.split('/')[-1]  # 尝试拿文件名
                if not hint:
                    hint = urlparse(url).netloc  # 拿不到文件名拿域名
                # 限制 hint 长度防止过长
                if len(hint) > 20:
                    hint = hint[:17] + "..."
                text = f"{text}({hint})"
            except Exception:
                pass

        # B. 处理重名 (Duplicate Handling)
        # 如果 URL 完全一致，复用同一个文本
        if text in self.text_to_url and self.text_to_url[text] == url:
            return text

        # 如果文本存在但 URL 不同，加序号区分
        base_text = text
        counter = 2
        while text in self.text_to_url:
            text = f"{base_text}({counter})"
            counter += 1

        return text

    def get_url(self, text: str) -> Optional[str]:
        """
        根据文本获取 URL

        Args:
            text: LLM 输出的链接文本（可能包含 🔗 符号）

        Returns:
            对应的真实 URL，如果不存在则返回 None
        """
        # 容错：移除可能被 LLM 带上的 🔗 符号和标点
        clean_text = text.replace("🔗", "").strip()
        clean_text = clean_text.strip("。，、；：""''""（）")
        return self.text_to_url.get(clean_text)


# ==========================================
# 状态与上下文定义
# ==========================================

class WebSearcherContext(BaseCrawlerContext):
    """
    Web 搜索任务上下文
    用于回答问题的搜索任务，带有"小本本"机制记录有用信息
    """

    def __init__(self, purpose: str, deadline: float, chunk_threshold: int = 5000,
                 temp_file_dir: Optional[str] = None):
        super().__init__(deadline)
        self.purpose = purpose  # 改名：question -> purpose
        self.notebook = ""
        self.chunk_threshold = chunk_threshold
        self.temp_file_dir = temp_file_dir
        # 用于存储待处理的链接（在流式阅读过程中发现）
        self.pending_links_from_reading: List[str] = []

    def add_to_notebook(self, info: str):
        """添加信息到小本本"""
        if info:
            timestamp = time.strftime("%H:%M:%S")
            self.notebook += f"\n\n[{timestamp}] {info}\n"

    def add_pending_link(self, url: str):
        """
        添加待处理的链接（从流式阅读中发现）

        Args:
            url: 待访问的 URL
        """
        if url and url not in self.pending_links_from_reading:
            self.pending_links_from_reading.append(url)

    def get_pending_links(self) -> List[str]:
        """
        获取所有待处理的链接并清空列表

        Returns:
            待处理的链接列表
        """
        links = self.pending_links_from_reading.copy()
        self.pending_links_from_reading.clear()
        return links


# ==========================================
# 2. Web Searcher 核心逻辑
# ==========================================

class WebSearcherMixin(CrawlerHelperMixin):
    """
    Web 搜索器技能
    用于回答问题的网络搜索
    """

    @register_action(
        "针对特定目的上网搜索，提供明确的搜索目的和（可选但建议提供的）搜索关键字词",
        param_infos={
            "purpose": "搜索的目的",
            "search_phrase": "可选，初始搜索关键词",
            "max_time": "可选，最大搜索分钟，默认20",
            "search_engine": "可选，搜索引擎（google 或 bing），默认使用 agent 配置的 default_search_engine 或 bing",
        }
    )
    async def web_search(
        self,
        purpose: str,
        search_phrase: str = None,
        max_time: int = 20,
        search_engine: str = None,
        temp_file_dir: Optional[str] = None
    ):
        """
        [Entry Point] 上网搜索回答问题（统一流程版本）

        Args:
            purpose: 要回答的问题（或研究目标）
            search_phrase: 初始搜索关键词
            max_time: 最大搜索时间（分钟）
            search_engine: 搜索引擎（"google" 或 "bing"），如果为 None 则使用配置的默认引擎
            chunk_threshold: 分段阈值（字符数）
            temp_file_dir: 临时文件保存目录（可选，用于调试）
        """
        # 0. 确定 search_engine（优先级：参数 > 配置 > 默认）
        if search_engine is None:
            # 尝试从实例属性读取配置
            search_engine = getattr(self, 'default_search_engine', DEFAULT_SEARCH_ENGINE)
            self.logger.info(f"Using configured default search engine: {search_engine}")
        # 1. 准备环境
        profile_path = os.path.join(self.workspace_root, ".matrix", "browser_profile", self.name)
        download_path = os.path.join(self.current_workspace, "downloads")
        chunk_threshold = 5000

        # 2. 确定 search_phrase
        if not search_phrase:
            resp = await self.brain.think(f"""
            我们现在的目的是 {purpose}，打算上网搜索一下，需要你设计一下最合适的关键词或者关键字组合。输出的时候可以先简单解释一下这么设计的理由，但是最后一行必须是也只能是要搜索的内容（也就是输入到搜索引擎搜索栏的内容）。例如你认为应该搜索"Keyword"，那么最后一行就只能是"Keyword"
            """)
            reply = resp['reply']
            #get last line of reply
            if '\n' in reply:
                search_phrase = reply.split('\n')[-1].strip()
        #如果还是有问题,我们直接搜索问题：
        if not search_phrase:
            search_phrase = purpose

        # 3. 验证搜索引擎
        if search_engine.lower() not in SEARCH_ENGINES:
            self.logger.warning(f"Unknown search engine '{search_engine}', using default '{DEFAULT_SEARCH_ENGINE}'")
            search_engine = DEFAULT_SEARCH_ENGINE

        self.logger.info(f"🔍 准备搜索: {search_phrase}")
        self.logger.info(f"🔍 搜索引擎: {search_engine}")

        # 4. 初始化浏览器和上下文
        self.browser = DrissionPageAdapter(
            profile_path=profile_path,
            download_path=download_path
        )

        ctx = WebSearcherContext(
            purpose=purpose,
            deadline=time.time() + int(max_time) * 60,
            chunk_threshold=chunk_threshold,
            temp_file_dir=temp_file_dir
        )

        self.logger.info(f"🔍 Web Search Start: {purpose}")
        self.logger.info(f"🔍 Initial search phrase: {search_phrase}")
        self.logger.info(f"🔍 Max search time: {max_time} minutes")

        # 5. 启动浏览器
        await self.browser.start(headless=False)

        try:
            # 6. 创建 Tab 和 Session
            tab = await self.browser.get_tab()
            session = TabSession(handle=tab, current_url="")

            # 7. 生成虚拟搜索URL并加入队列
            # 支持多个搜索关键字组合：用逗号分隔 search_phrase，为每个短语生成独立的搜索URL
            # 虚拟URL协议格式: "search:{search_engine}:{search_phrase}"
            # 例如: "search:bing:2026年1月24日 政治 新闻"

            # 分割 search_phrase（支持中英文逗号）
            search_phrases = [p.strip() for p in search_phrase.replace('，', ',').split(',')]
            # 过滤空字符串
            search_phrases = [p for p in search_phrases if p]

            self.logger.info(f"✓ Parsed {len(search_phrases)} search phrase(s) from input: {search_phrases}")

            # 为每个搜索短语生成虚拟搜索URL并加入队列
            for phrase in search_phrases:
                search_virtual_url = f"search:{search_engine.lower()}:{phrase}"
                session.pending_link_queue.append(search_virtual_url)
                self.logger.info(f"✓ Added virtual search URL to queue: {search_virtual_url}")

            # 8. 运行统一的搜索生命周期
            # _run_search_lifecycle 会识别虚拟URL并调用相应的搜索函数
            answer = await self._run_search_lifecycle(session, ctx)

            # 9. 返回结果
            if answer:
                self.logger.info(f"✅ Found answer!")
                return f"Answer: {answer}\n\n---\nNotebook:\n{ctx.notebook}"
            else:
                self.logger.info("⏸ Search completed without finding complete answer")
                return f"Could not find a complete answer.\n\nHere's what I found:\n{ctx.notebook}"

        except Exception as e:
            self.logger.exception("Web searcher crashed")
            return f"Search failed with error: {e}"
        #finally:
        #    self.logger.info("🛑 Closing browser...")
        #    await self.browser.close()

    @register_action(
        "访问一个网页并查看网页内容，如果是pdf文件就下载",
        param_infos={
            "url": "要访问的网页 URL"
        }
    )
    async def visit_url(self,url: str):
        # 1. 准备环境
        profile_path = os.path.join(self.workspace_root, ".matrix", "browser_profile", self.name)
        download_path = os.path.join(self.current_workspace, "downloads")


        
        self.logger.info(f"🔍 准备访问: {url}")

        self.browser = DrissionPageAdapter(
            profile_path=profile_path,
            download_path=download_path
        )
        await self.browser.start(headless=False)

        tab = await self.browser.get_tab()
        

        nav_report = await self.browser.navigate(tab, url)
        final_url = self.browser.get_tab_url(tab)
        

        # === Phase 2: Identify Page Type ===
        page_type = await self.browser.analyze_page_type(tab)

        if page_type == PageType.ERRO_PAGE:
            self.logger.warning(f"🚫 Error Page: {final_url}")
            return f"Error Accessing Page: {url}"

        # === 分支 A: 静态资源 ===
        if page_type == PageType.STATIC_ASSET:
            self.logger.info(f"📄 Static Asset: {final_url}")

            download_file = await self.browser.save_static_asset(tab)
            return f"文件已下载到： {download_file}"

  

        # === 分支 B: 交互式网页 ===
        elif page_type == PageType.NAVIGABLE:
            await self.browser.stabilize(tab)
            markdown = await self._html_to_full_markdown(tab)
            
            #用markdown第一行作为文件名字
            filename = markdown.split('\n')[0].strip().replace("#","")
            filename = sanitize_filename(filename) + ".md"

            #把markdown保存为文件
            with open(os.path.join(self.current_workspace, filename), "w", encoding="utf-8") as f:
                f.write(markdown)
            return f"网页摘要已保存到： {filename}"

    # ==========================================
    # 2. 辅助方法（目录、选择章节、分段）
    # ==========================================

    def _generate_document_toc(self, markdown: str) -> List[Dict[str, Any]]:
        """
        从 Markdown 中提取目录结构
        返回: [
            {"level": 1, "title": "第一章", "start": 0, "end": 1234},
            {"level": 2, "title": "1.1 简介", "start": 1235, "end": 2345},
            ...
        ]
        """
        toc = []
        lines = markdown.split("\n")
        current_pos = 0

        for line in lines:
            # 匹配 Markdown 标题
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                toc.append({
                    "level": level,
                    "title": title,
                    "start": current_pos,
                    "line": line
                })

            current_pos += len(line) + 1  # +1 for newline

        # 计算每个章节的结束位置
        for i in range(len(toc) - 1):
            toc[i]["end"] = toc[i + 1]["start"]
        if toc:
            toc[-1]["end"] = len(markdown)

        return toc

    async def _let_llm_select_chapters(
        self,
        toc: List[Dict],
        ctx: WebSearcherContext,
        markdown_preview: str = "",
        url: str = ""
    ) -> List[int]:
        """
        让 LLM 根据问题选择相关章节（使用 think_with_retry 自动重试）

        Args:
            toc: 目录列表
            ctx: 搜索上下文
            markdown_preview: Markdown开头500字预览（帮助判断文档是否有用）
            url: 当前页面URL（帮助LLM理解页面来源）

        Returns:
            选中的章节索引列表（0-based），或特殊值：
            - None: 跳过章节选择（使用全文）
            - "SKIP_DOC": 跳过整个文档（文档不相关）
        """
        # 构造 TOC 列表（不用数字编号，保留缩进）
        toc_lines = []
        for chapter in toc:
            indent = "  " * (chapter["level"] - 1)
            toc_lines.append(f"{indent}{chapter['title']}")
        toc_list = "\n".join(toc_lines)

        # 构造章节名字到索引的映射（用于验证）
        chapter_name_to_index = {
            chapter["title"]: i
            for i, chapter in enumerate(toc)
        }

        # 使用 prompt 模板
        prompt = WebSearcherPrompts.CHAPTER_SELECTION.format(
            question=ctx.purpose,
            toc_list=toc_list,
            url=url,
            preview=markdown_preview
        )

        self.logger.debug(f"【Chapter Selection Prompt】:\n{prompt}")

        try:
            # 使用 think_with_retry 自动处理重试
            result = await self.cerebellum.backend.think_with_retry(
                initial_messages=prompt,
                parser=self._chapter_parser,
                max_retries=5,
                chapter_name_to_index = chapter_name_to_index
            )

            # result 可能是：
            # - None: 跳过章节选择（使用全文）
            # - "SKIP_DOC": 跳过整个文档
            # - 章节索引列表
            if result is None:
                self.logger.info("📋 Skipping chapter selection (TOC not helpful)")
                return None  # None 表示跳过章节选择，使用全文

            if result == "SKIP_DOC":
                self.logger.info("🚫 LLM decided to skip entire document (not relevant)")
                return "SKIP_DOC"

            self.logger.info(f"✅ Successfully selected {len(result)} chapters: {result}")
            return result

        except ValueError as e:
            # think_with_retry 在所有重试失败后会抛出 ValueError
            self.logger.error(f"❌ Chapter selection failed after all retries: {e}")
            # 返回空列表（会触发全文处理）
            return []

    def _chapter_parser(self, llm_output: str, chapter_name_to_index: Dict[str, int]) -> Dict[str, Any]:
        """
        Parser for think_with_retry - 遵循 Parser Contract
        解析 LLM 的章节选择输出

        Args:
            llm_output: LLM 的原始输出
            chapter_name_to_index: 章节名到索引的映射

        Returns:
        {
            "status": "success" | "error",
            "content": List[int],              # 当 status="success" 时，返回选中的章节索引
            "feedback": str                 # 当 status="error" 时，返回反馈信息
        }
        """
        # 宽松处理：先检查整个输出是否包含 SKIP_DOC 或 SKIP_TOC
        output_upper = llm_output.upper()
        if "SKIP_DOC" in output_upper:
            self.logger.info("🚫 LLM decided to skip entire document (not relevant)")
            return {
                "status": "success",
                "content": "SKIP_DOC"  # 特殊值：跳过整个文档
            }

        if "SKIP_TOC" in output_upper:
            self.logger.info("📋 LLM chose to skip chapter selection (TOC not helpful)")
            return {
                "status": "success",
                "content": None  # None 表示跳过章节选择，使用全文
            }

        # 使用 multi_section_parser 提取章节选择部分
        result = multi_section_parser(
            llm_output,
            section_headers=["====章节选择===="],
            match_mode="ANY"
        )

        if result["status"] == "error":
            return {
                "status": "error",
                "feedback": WebSearcherPrompts.CHAPTER_ERROR_FORMAT
            }

        # 提取章节选择内容
        chapter_section = result["content"]["====章节选择===="]

        # 如果有结束标记，只取结束标记之前的部分
        if "====章节选择结束====" in chapter_section:
            chapter_section = chapter_section.split("====章节选择结束====")[0].strip()

        # 按行分割
        chapter_lines = [
            line.strip()
            for line in chapter_section.split('\n')
            if line.strip()
        ]

        if not chapter_lines:
            return {
                "status": "error",
                "feedback": "没有选择任何章节。请至少选择一个相关章节。"
            }

        # 验证章节是否存在于 TOC 中
        selected_indices = []
        invalid_chapters = []

        for chapter_name in chapter_lines:
            # 特殊处理：SKIP_TOC 表示跳过章节选择，使用全文
            if chapter_name == "SKIP_TOC":
                self.logger.info("📋 LLM chose to skip chapter selection (TOC not helpful)")
                return {
                    "status": "success",
                    "content": None  # None 表示跳过章节选择
                }

            if chapter_name in chapter_name_to_index:
                selected_indices.append(chapter_name_to_index[chapter_name])
            else:
                invalid_chapters.append(chapter_name)

        # 判断结果
        if invalid_chapters:
            # 有幻觉 - 返回具体反馈

            return {
                "status": "error",
                "feedback": f"选择错误，以下章节不存在于TOC中：{', '.join(invalid_chapters)}。\n\n如果TOC中没有合适的章节，可以直接输出 SKIP_TOC 跳过章节选择。"
            }

        if not selected_indices:
            return {
                "status": "error",
                "feedback": "没有有效的章节选择。\n\n如果TOC中没有合适的章节，可以直接输出 SKIP_TOC 跳过章节选择。"
            }

        # 成功 - 返回章节索引列表
        return {
            "status": "success",
            "content": selected_indices
        }

    
    def _split_by_paragraph_boundaries(
        self,
        text: str,
        threshold: int
    ) -> List[str]:
        """
        按段落边界将文本分段，每段 ≤ threshold

        策略：
        1. 按 \\n\\n 分割段落
        2. 逐步添加段落，直到接近阈值
        3. 在最近的双换行处断开
        4. 超长段落按句子（。）细分
        """
        if len(text) <= threshold:
            return [text]

        # 按双换行分段
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""

        for para in paragraphs:
            test_chunk = current_chunk + ("\n\n" if current_chunk else "") + para

            if len(test_chunk) <= threshold:
                current_chunk = test_chunk
            else:
                # 当前段落会超出阈值
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果单个段落就超过阈值，强制在中间断开
                if len(para) > threshold:
                    # 按句子分割
                    sentences = para.split('。')
                    temp_chunk = ""
                    for sent in sentences:
                        test_sent = temp_chunk + ('。' if temp_chunk else '') + sent
                        if len(test_sent) <= threshold:
                            temp_chunk = test_sent
                        else:
                            if temp_chunk:
                                chunks.append(temp_chunk)
                            temp_chunk = sent
                    current_chunk = temp_chunk
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    # ==========================================
    # 4. 核心流式处理
    # ==========================================

    def _find_chapters_in_batch(
        self,
        toc: List[Dict[str, Any]],
        batch_start: int,
        batch_end: int,
        content_start: int = 0
    ) -> List[Dict[str, Any]]:
        """
        查找 batch 中涉及的所有章节（可能跨多个章节）

        Args:
            toc: 目录结构
            batch_start: batch 在内容中的起始位置
            batch_end: batch 在内容中的结束位置
            content_start: 内容的起始位置（用于处理选中章节的情况）

        Returns:
            batch 涉及的所有章节列表（按出现顺序）
        """
        adjusted_start = batch_start + content_start
        adjusted_end = batch_end + content_start

        # 找到所有与 batch 有交集的章节
        chapters_in_batch = []
        for chapter in toc:
            # 检查章节是否与 batch 有交集
            # 有交集的条件：章节的结束位置 > batch起始 且 章节的起始位置 < batch结束
            if chapter["end"] > adjusted_start and chapter["start"] < adjusted_end:
                chapters_in_batch.append(chapter)

        return chapters_in_batch

    async def _process_batch(
        self,
        batch_text: str,
        ctx: WebSearcherContext,
        doc_title: str,
        current_batch: int,
        total_batches: int,
        url,
        toc: List[Dict[str, Any]] = None,
        current_chapters: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        统一的批处理函数（使用 think_with_retry 自动重试）

        参数:
            batch_text: 当前批次文本
            ctx: 搜索上下文
            doc_title: 文档名称
            current_batch: 当前批次（页码，从 1 开始）
            total_batches: 总批次数（总页数）
            url: 当前页面 URL
            toc: 可选的文档目录结构
            current_chapters: 可选的当前页涉及的所有章节（可能跨多个章节）

        返回:
        {
            "heading_type": "answer" | "note" | "continue" | "skip_doc",
            "content": str,
            "found_links": List[str]  # LLM 推荐的链接文本列表
        }
        """
        # 计算进度百分比
        progress_pct = int((current_batch / total_batches) * 100)

        # 构造 TOC 信息
        toc_info = ""
        if toc and current_chapters:
            # 获取当前涉及的第一个和最后一个章节
            first_chapter = current_chapters[0]
            last_chapter = current_chapters[-1]

            first_index = toc.index(first_chapter)
            last_index = toc.index(last_chapter)

            toc_info = f"\n[Document Structure - Table of Contents]\n"

            # 显示前 2 个章节（在第一个当前章节之前）
            if first_index > 0:
                toc_info += "- Previous chapters:\n"
                for ch in toc[max(0, first_index - 2):first_index]:
                    toc_info += f"  - {ch['title']}\n"

            # 显示当前涉及的章节（高亮，可能多个）
            toc_info += "- >>> CURRENT SECTION (this page contains): <<<\n"
            for ch in current_chapters:
                # 根据 level 缩进
                indent = "  " * (ch.get("level", 1) - 1)
                toc_info += f"{indent}→ {ch['title']}\n"

            # 显示后 2 个章节（在最后一个当前章节之后）
            if last_index < len(toc) - 1:
                toc_info += "- Next chapters:\n"
                for ch in toc[last_index + 1:min(len(toc), last_index + 3)]:
                    toc_info += f"  - {ch['title']}\n"

            toc_info += "\n\n"

        # 构造初始 prompt
        prompt = WebSearcherPrompts.BATCH_PROCESSING.format(
            question=ctx.purpose,
            doc_title=doc_title,
            current_batch=current_batch,
            total_batches=total_batches,
            progress_pct=progress_pct,
            toc_info=toc_info,
            notebook=ctx.notebook,
            batch_text=batch_text,
            url=url
        )
        self.logger.debug(f"【Batch Processing Prompt】:\n{prompt}")
        try:
            # 使用 think_with_retry 自动处理重试
            # parser 返回: {"status": "success", "content": {"heading_type": ..., "content": ..., "found_links": [...]}}
            result_data = await self.cerebellum.backend.think_with_retry(
                initial_messages=prompt,
                parser=self._batch_parser,
                max_retries=5
            )

            # 根据类型记录日志
            heading_type = result_data["heading_type"]
            if heading_type == "answer":
                self.logger.info(f"✅ Found answer in batch")
            elif heading_type == "note":
                self.logger.info(f"📝 Found useful info in batch")
            elif heading_type == "continue":
                self.logger.debug(f"👀 No new info, continuing")
            else:  # skip_doc
                self.logger.warning(f"🚫 Document irrelevant, skipping")

            return result_data

        except ValueError as e:
            # think_with_retry 在所有重试失败后会抛出 ValueError
            self.logger.error(f"❌ Batch processing failed after all retries: {e}")
            # 返回默认值（继续阅读）
            return {"heading_type": "continue", "content": "", "found_links": []}

    def _batch_parser(self, llm_output: str) -> Dict[str, Any]:
        """
        Parser for think_with_retry - 遵循 Parser Contract
        使用 multi_section_parser 实现，更健壮且不依赖标题位置

        Args:
            llm_output: LLM 的原始输出

        Returns:
        {
            "status": "success" | "error",
            "content": {
                "heading_type": "answer" | "note" | "continue" | "skip_doc",
                "content": str,
                "found_links": List[str]
            },
            "feedback": str  # 当 status="error" 时返回反馈信息
        }
        """
        # 1. 定义4个主标题
        main_headings = [
            "##对问题的回答",
            "##值得记录的笔记",
            "##没有值得记录的笔记继续阅读",
            "##完全不相关的文档应该放弃"
        ]

        # 2. 使用 ANY 模式调用 multi_section_parser（只需要一个主标题）
        result = multi_section_parser(
            llm_output,
            section_headers=main_headings,
            match_mode="ANY"
        )

        if result["status"] == "error":
            return {"status": "error", "feedback": result["feedback"]}

        sections = result["content"]

        # 3. 获取第一个匹配的 section（通常只有一个）
        heading_map = {
            "##对问题的回答": "answer",
            "##值得记录的笔记": "note",
            "##没有值得记录的笔记继续阅读": "continue",
            "##完全不相关的文档应该放弃": "skip_doc"
        }

        chosen_heading = None
        content = ""
        for heading in main_headings:
            if heading in sections:
                chosen_heading = heading
                content = sections[heading].strip()
                break

        # 4. 从 content 中分离出推荐链接（如果有）
        found_links = []
        if "====推荐链接====" in content:
            parts = content.split("====推荐链接====")
            content = parts[0].strip()

            if len(parts) > 1:
                # 提取链接部分
                links_section = parts[1]
                if "====推荐链接结束====" in links_section:
                    links_section = links_section.split("====推荐链接结束====")[0]

                link_lines = [line.strip() for line in links_section.split('\n') if line.strip()]
                # 过滤掉示例文本和空行
                found_links = [line for line in link_lines
                               if line not in ["示例链接文本", "另一个链接文本"]]

        # 5. 验证内容非空
        if not content:
            return {
                "status": "error",
                "feedback": "内容不能为空，请在标题下提供实际内容"
            }

        # 6. 返回符合 Parser Contract 的格式
        return {
            "status": "success",
            "content": {
                "heading_type": heading_map[chosen_heading],
                "content": content,
                "found_links": found_links
            }
        }

    

    def _extract_document_title(self, markdown: str) -> str:
        """
        从 Markdown 中提取文档标题
        优先级：第一个 # 标题 > 前 50 字符 > "未命名文档"
        """
        # 1. 尝试找到第一个 # 标题
        lines = markdown.split('\n')
        for line in lines:
            if line.startswith('# '):
                return line[2:].strip()

        # 2. 如果没有标题，使用前 50 字符作为标题
        if len(markdown) > 50:
            return markdown[:50].strip()

        # 3. 默认标题
        return "未命名文档"

    async def _stream_process_markdown(
        self,
        markdown: str,
        ctx: WebSearcherContext,
        url: str,
        session: TabSession = None
    ) -> Optional[str]:
        """
        流式处理 Markdown 文档（统一入口）

        流程：
        1. 判断长度 → 决定是否需要选章节
        2. 链接预处理：使用 MarkdownLinkManager 清洗链接
        3. 准备待处理内容（全文 OR 选中章节）
        4. 按段落边界分成批次
        5. 逐批流式处理，并处理发现的链接

        Args:
            markdown: 原始 Markdown 文本
            ctx: 搜索上下文
            url: 当前页面 URL
            session: 可选的 TabSession，用于将发现的链接加入队列

        Returns:
            找到的答案，如果未找到则返回 None
        """
        # 1. 初始化 Link Manager 并预处理 Markdown
        link_manager = MarkdownLinkManager(ctx, logger=self.logger)
        clean_markdown = link_manager.process(markdown, url)

        # 2. 判断长度
        is_long = len(clean_markdown) > ctx.chunk_threshold

        # 3. 准备待处理内容
        if not is_long:
            # 短文档：全文处理
            self.logger.info(f"📄 Short document ({len(clean_markdown)} chars). Processing full text.")
            content_to_process = clean_markdown
        else:
            # 长文档：生成目录 → 选择章节
            self.logger.info(f"📚 Long document ({len(clean_markdown)} chars). Generating TOC...")
            toc = self._generate_document_toc(clean_markdown)

            if not toc or len(toc)<2:
                # 无标题结构或者只有一个标题，全文处理
                self.logger.info("📋 No headers found. Processing full text.")
                content_to_process = clean_markdown
            else:
                # 让 LLM 选择章节（传入预览和URL）
                self.logger.info(f"📑 Found {len(toc)} chapters. Asking LLM to select...")
                self.logger.debug(f"【Document TOC】: {toc}")

                # 提取前500字符作为预览
                markdown_preview = clean_markdown[:500] if len(clean_markdown) > 500 else clean_markdown

                selected_indices = await self._let_llm_select_chapters(
                    toc,
                    ctx,
                    markdown_preview=markdown_preview,
                    url=url
                )

                # 处理 LLM 的选择结果
                if selected_indices == "SKIP_DOC":
                    # LLM 认为整个文档不相关，跳过
                    self.logger.warning("🚫 LLM decided to skip entire document (not relevant)")
                    # 标记所有链接为已评估
                    for link_url in link_manager.text_to_url.values():
                        ctx.mark_evaluated(link_url)
                        #self.logger.debug(f"✓ Marked as evaluated: {link_url}")
                    return None  # 相当于 skip_doc

                elif selected_indices is None or not selected_indices:
                    # None 表示 LLM 认为TOC没用，空列表表示没选任何章节
                    self.logger.warning("⚠️ No chapters selected or TOC skipped. Processing full text.")
                    content_to_process = clean_markdown
                else:
                    self.logger.info(f"✅ Selected {len(selected_indices)} chapters")
                    # 提取选中章节（包含所有子章节）
                    selected_parts = []

                    for idx in selected_indices:
                        chapter = toc[idx]
                        chapter_level = chapter["level"]

                        # 查找该章节的所有子章节（level > current_level，直到遇到同级或上级章节）
                        chapter_start = chapter["start"]
                        chapter_end = chapter["end"]

                        # 向后查找，找到该章节的结束位置
                        for j in range(idx + 1, len(toc)):
                            next_chapter = toc[j]
                            if next_chapter["level"] <= chapter_level:
                                # 遇到同级或上级章节，停止
                                chapter_end = next_chapter["start"]
                                break
                            # 否则是子章节，继续向后查找

                        # 提取内容（包含所有子章节）
                        content = clean_markdown[chapter_start:chapter_end]
                        selected_parts.append(f"# {chapter['title']}\n\n{content}")

                        self.logger.debug(
                            f"Extracted chapter '{chapter['title']}' "
                            f"(level {chapter_level}, {len(content)} chars, "
                            f"positions {chapter_start}-{chapter_end})"
                        )

                    content_to_process = "\n\n".join(selected_parts)

        # 4. 按段落边界分成批次
        self.logger.info(f"🔪 Splitting content into batches (max {ctx.chunk_threshold} chars each)...")
        batches = self._split_by_paragraph_boundaries(content_to_process, ctx.chunk_threshold)
        total_batches = len(batches)
        self.logger.info(f"📊 Split into {total_batches} batches")

        # 5. 获取文档标题和 TOC（用于 LLM 上下文）
        doc_title = self._extract_document_title(content_to_process)

        # 生成或复用 TOC
        toc = None
        if is_long:
            # 长文档，已经生成过 TOC（第 1064 行）
            toc = self._generate_document_toc(clean_markdown)
        else:
            # 短文档，也生成 TOC（如果有的话）
            toc = self._generate_document_toc(content_to_process)

        # 6. 逐批流式处理，追踪位置
        current_position = 0  # 当前 batch 在 content_to_process 中的起始位置

        for i, batch in enumerate(batches, start=1):  # 从 1 开始计数
            current_batch = i
            batch_start = current_position
            batch_end = current_position + len(batch)
            current_position = batch_end  # 更新位置

            progress_pct = int((current_batch / total_batches) * 100)
            self.logger.info(
                f"🔄 Processing batch {current_batch}/{total_batches} "
                f"({progress_pct}%, {len(batch)} chars)..."
            )

            # 查找当前 batch 涉及的章节
            current_chapters = []
            if toc:
                current_chapters = self._find_chapters_in_batch(
                    toc,
                    batch_start,
                    batch_end,
                    content_start=0  # content_to_process 是独立的，从 0 开始
                )

            # 统一的批处理（传入 TOC 和章节信息）
            result = await self._process_batch(
                batch,
                ctx,
                doc_title=doc_title,
                current_batch=current_batch,
                total_batches=total_batches,
                url=url,
                toc=toc if toc else None,
                current_chapters=current_chapters if current_chapters else None
            )

            # 处理结果
            if result["heading_type"] == "answer":
                # 找到答案，立即返回
                self.logger.info(f"✅ Answer found in batch {current_batch}!")
                return result["content"]

            elif result["heading_type"] == "note":
                # 有用信息，添加到小本本
                ctx.add_to_notebook(f"[Batch {current_batch}] {result['content']}")
                self.logger.info(f"📝 Added useful info from batch {current_batch}")

            elif result["heading_type"] == "skip_doc":
                # 文档不相关，放弃整个文档
                self.logger.warning(f"🚫 Document irrelevant. Skipping rest of document.")
                break

            # 7. 处理发现的链接（新增逻辑）
            if result.get("found_links"):
                for link_text in result["found_links"]:
                    target_url = link_manager.get_url(link_text)
                    if target_url:
                        self.logger.info(f"🔗 Context-aware link discovered: [{link_text}] -> {target_url}")
                        # 如果有 session，直接加入队列；否则暂存到 ctx
                        if session:
                            session.pending_link_queue.append(target_url)
                        else:
                            ctx.add_pending_link(target_url)
                    else:
                        self.logger.warning(f"⚠️ LLM hallucinated link text: {link_text}")

            # heading_type == "continue": 什么都不做，继续下一批

        # 8. 标记所有链接为已评估（重要！）
        # _stream_process_markdown 是一个完整的评估过程
        # 所有 link_manager 中的链接都已被 LLM 评估过（要么推荐，要么未推荐）
        for url in link_manager.text_to_url.values():
            ctx.mark_evaluated(url)
            #self.logger.debug(f"✓ Marked as evaluated: {url}")

        # 未找到答案
        return None

    def _search_result_links_parser(self, llm_reply, link_manager) -> callable:


        # 1. 调用 multi_section_parser 提取 ##推荐链接
        result = multi_section_parser(
            llm_reply,
            section_headers=["##推荐链接"],
            match_mode="ANY"
        )

        self.logger.debug(f"【Search Result Links Parser Output】:\n{result}")

        if result["status"] == "error":
            return result

        # 2. 提取链接列表
        links_section = result["content"].get("##推荐链接", "")

        # 按行分割并清理
        link_lines = [
            line.strip()
            for line in links_section.split('\n')
            if line.strip()
        ]

        # 3. 检查是否选择跳过
        if "SKIP_PAGE" in link_lines:
            self.logger.info("⏭️ LLM decided to skip this search result batch (no relevant results)")
            return {
                "status": "success",
                "content": {
                    "found_links": []  # 空列表表示没有找到相关链接
                }
            }

        # 4. 过滤掉示例文本
        found_links = [
            line for line in link_lines
            if line not in ["第一个链接", "另一个链接", "SKIP_PAGE"]
        ]
        self.logger.debug(f"【Extracted Links (raw)】:\n{found_links}")

        # 5. 宽松验证：过滤掉无效链接，保留有效链接
        valid_links = []

        for link_text in found_links:
            if link_manager.get_url(link_text):
                # 有效链接
                valid_links.append(link_text)

        # 6. 判断结果
        if valid_links:
            # 有有效链接，成功（忽略无效链接）

            self.logger.info(f"✅ Extracted {len(valid_links)} valid links from LLM output")
            return {
                "status": "success",
                "content": {
                    "found_links": valid_links
                }
            }
        else:
            # 没有任何有效链接，但LLM也没有选择SKIP_PAGE
            # 视为"没有找到相关链接"，返回成功但空列表
            self.logger.info("⏭️ No valid links found (LLM didn't explicitly SKIP, but no relevant links)")
            return {
                "status": "success",
                "content": {
                    "found_links": []
                }
            }

        return parser

    async def _stream_process_search_result(
        self,
        html: str,
        ctx: WebSearcherContext,
        url: str,
        session: TabSession = None,
        search_engine: str = "unknown"
    ) -> Optional[str]:
        """
        流式处理搜索引擎结果页（重构版）

        新的流程：
        1. 使用 SearchResultsParser 直接解析 HTML，提取结构化数据
        2. 重新格式化为易读的 Markdown
        3. 建立链接ID到URL的映射
        4. 分批处理，让 LLM 选择值得访问的链接

        Args:
            html: 搜索结果页的原始 HTML
            ctx: 搜索上下文
            url: 当前页面 URL
            session: 可选的 TabSession，用于将发现的链接加入队列
            search_engine: 搜索引擎名称 ("google" 或 "bing")

        Returns:
            找到的答案，如果未找到则返回 None
        """
        from .search_results_parser import SearchResultsParser

        # 1. 使用专门的解析器解析搜索结果
        parser = SearchResultsParser(logger=self.logger)

        # 【新增】设置URL过滤函数
        parser.set_url_filter(ctx.should_process_url)

        parsed_data = parser.parse(html, url)

        filtered_count = parsed_data.get('filtered_count', 0)
        self.logger.info(f"✓ Parsed {len(parsed_data['results'])} search results from {search_engine}")
        if filtered_count > 0:
            self.logger.info(f"  ↳ {filtered_count} results filtered (already visited/evaluated)")

        # 2. 检查是否所有结果都被过滤了
        if len(parsed_data['results']) == 0:
            self.logger.warning("⚠️ All search results have been visited/evaluated. Skipping this page.")
            # 标记所有链接为已评估（虽然已经没有了）
            return None

        # 3. 格式化为 Markdown
        formatted_markdown = parser.format_as_markdown(parsed_data)

        # 4. 构建链接映射
        link_mapping = parser.build_link_mapping(parsed_data)

        self.logger.debug(f"✓ Built link mapping with {len(link_mapping)} entries")
        for link_id, url in list(link_mapping.items())[:3]:  # 显示前3个
            self.logger.debug(f"  {link_id} -> {url}")

        # 5. 按段落边界分成批次
        self.logger.info(f"🔪 Splitting search results into batches (max {ctx.chunk_threshold} chars each)...")
        batches = self._split_by_paragraph_boundaries(formatted_markdown, ctx.chunk_threshold)
        total_batches = len(batches)
        self.logger.info(f"📊 Split into {total_batches} batches")

        # 6. 逐批流式处理
        for i, batch in enumerate(batches, start=1):
            current_batch = i
            progress_pct = int((current_batch / total_batches) * 100)
            self.logger.info(
                f"🔄 Processing search results batch {current_batch}/{total_batches} "
                f"({progress_pct}%, {len(batch)} chars)..."
            )

            # 构造搜索结果批处理 prompt
            prompt = WebSearcherPrompts.SEARCH_RESULT_BATCH.format(
                question=ctx.purpose,
                search_engine=search_engine,
                notebook=ctx.notebook,
                batch_text=batch
            )
            self.logger.debug(f"【Search Result Batch Prompt】:\n{prompt}")

            try:
                # 创建 Link Manager 实例
                link_manager = StructuredLinkManager(link_mapping)

                # 使用 think_with_retry 自动处理重试
                # 使用专门的 parser，会验证链接是否存在，避免幻觉
                result_data = await self.cerebellum.backend.think_with_retry(
                    initial_messages=prompt,
                    parser=self._search_result_links_parser,
                    link_manager=link_manager,
                    max_retries=5
                )
                self.logger.debug(f"【Search Result Batch LLM Output】:\n{result_data}")

                # 提取找到的链接
                found_links = result_data.get("found_links", [])
                self.logger.info(f"✅ Found {len(found_links)} recommended links from search results")

            except ValueError as e:
                import traceback
                traceback.print_exc()
                self.logger.error(f"❌ Search results batch processing failed after all retries: {e}")
                found_links = []

            # 处理发现的链接
            if found_links:
                for link_id in found_links:
                    # 从 link_id 中提取实际URL
                    target_url = link_manager.get_url(link_id)
                    if target_url:
                        self.logger.info(f"🔗 Search result link discovered: [{link_id}] -> {target_url}")
                        # 如果有 session，直接加入队列；否则暂存到 ctx
                        if session:
                            session.pending_link_queue.append(target_url)
                        else:
                            ctx.add_pending_link(target_url)
                    else:
                        self.logger.warning(f"⚠️ Could not find URL for link_id: {link_id}")

        # 7. 标记所有链接为已评估（重要！）
        for url in link_mapping.values():
            ctx.mark_evaluated(url)
            #self.logger.debug(f"✓ Marked as evaluated: {url}")

        # 未找到答案
        return None

    async def _process_navigation_page(
        self,
        tab,
        ctx: WebSearcherContext,
        url: str,
        session: TabSession = None
    ) -> Optional[str]:
        """
        处理导航页/索引页（首页、频道页等）

        流程：
        1. 通过 jina.ai 获取页面的 Markdown
        2. 提取所有链接（过滤纯图片链接）
        3. 格式化为类似搜索结果的格式（带链接ID）
        4. 构建链接ID到URL的映射
        5. 让 LLM 选择值得访问的链接

        Args:
            tab: 浏览器标签页
            ctx: 搜索上下文
            url: 当前页面 URL
            session: TabSession，用于将发现的链接加入队列

        Returns:
            找到的答案，如果未找到则返回 None
        """
        # 1. 通过 jina.ai 获取 markdown
        self.logger.info(f"📥 Fetching navigation page markdown from jina.ai...")
        try:
            markdown = await self.get_markdown_via_jina(url, timeout=30)
            self.logger.info(f"✓ Received {len(markdown)} characters from jina.ai")
        except Exception as e:
            self.logger.error(f"❌ Failed to fetch markdown from jina.ai: {e}")
            return None

        # 2. 提取链接
        self.logger.info(f"🔍 Extracting links from navigation page...")
        links = self.extract_navigation_links(markdown)
        self.logger.info(f"✓ Extracted {len(links)} links (pure images filtered)")

        if len(links) == 0:
            self.logger.warning("⚠️ No links found in navigation page")
            return None

        # 3. 过滤已访问/已评估的链接
        filtered_links = []
        for link in links:
            if ctx.should_process_url(link.url, session.pending_link_queue if session else []):
                filtered_links.append(link)

        filtered_count = len(links) - len(filtered_links)
        if filtered_count > 0:
            self.logger.info(f"  ↳ Filtered {filtered_count} already visited/evaluated links")

        if len(filtered_links) == 0:
            self.logger.warning("⚠️ All navigation links have been visited/evaluated. Skipping this page.")
            return None

        # 4. 格式化为 Markdown（类似搜索结果格式）
        formatted_markdown = self.format_navigation_links_as_markdown(filtered_links, url)

        # 5. 构建链接映射
        link_mapping = self.build_navigation_link_mapping(filtered_links)

        self.logger.debug(f"✓ Built link mapping with {len(link_mapping)} entries")
        for link_id, mapped_url in list(link_mapping.items())[:3]:  # 显示前3个
            self.logger.debug(f"  {link_id} -> {mapped_url}")

        # 6. 按段落边界分成批次
        self.logger.info(f"🔪 Splitting navigation links into batches (max {ctx.chunk_threshold} chars each)...")
        batches = self._split_by_paragraph_boundaries(formatted_markdown, ctx.chunk_threshold)
        total_batches = len(batches)
        self.logger.info(f"📊 Split into {total_batches} batches")

        # 7. 逐批流式处理
        for i, batch in enumerate(batches, start=1):
            current_batch = i
            progress_pct = int((current_batch / total_batches) * 100)
            self.logger.info(
                f"🔄 Processing navigation batch {current_batch}/{total_batches} "
                f"({progress_pct}%, {len(batch)} chars)..."
            )

            # 构造导航页批处理 prompt
            prompt = WebSearcherPrompts.NAVIGATION_PAGE.format(
                question=ctx.purpose,
                notebook=ctx.notebook,
                navigation_text=batch
            )
            self.logger.debug(f"【Navigation Page Batch Prompt】:\n{prompt}")

            try:
                # 创建通用的 StructuredLinkManager 实例
                link_manager = StructuredLinkManager(link_mapping)

                # 使用 think_with_retry 自动处理重试
                result_data = await self.cerebellum.backend.think_with_retry(
                    initial_messages=prompt,
                    parser=self._search_result_links_parser,
                    link_manager=link_manager,
                    max_retries=5
                )
                self.logger.debug(f"【Navigation Page Batch LLM Output】:\n{result_data}")

                # 提取找到的链接
                found_links = result_data.get("found_links", [])
                self.logger.info(f"✅ Found {len(found_links)} recommended links from navigation page")

            except ValueError as e:
                import traceback
                traceback.print_exc()
                self.logger.error(f"❌ Navigation page batch processing failed after all retries: {e}")
                found_links = []

            # 处理发现的链接
            if found_links:
                for link_id in found_links:
                    target_url = link_manager.get_url(link_id)
                    if target_url:
                        self.logger.info(f"🔗 Navigation link discovered: [{link_id}] -> {target_url}")
                        session.pending_link_queue.append(target_url)
                    else:
                        self.logger.warning(f"⚠️ Could not find URL for link_id: {link_id}")

        # 8. 标记所有链接为已评估（重要！）
        for nav_link in filtered_links:
            ctx.mark_evaluated(nav_link.url)
            #self.logger.debug(f"✓ Marked as evaluated: {nav_link.url}")

        # 未找到答案
        return None

    async def _run_search_lifecycle(self, session: TabSession, ctx: WebSearcherContext) -> Optional[str]:
        """
        [NEW VERSION - Simplified]
        [The Core Loop] 搜索生命周期（简化版）

        核心理念：每种页面类型一次性完成所有决策，不需要额外的 Scouting 阶段

        页面类型处理流程：
        1. 搜索结果页 → 解析结果 → LLM选择链接 → 加入队列 → 结束
        2. 导航页 → jina.ai获取markdown → 提取链接 → LLM选择 → 加入队列 → 结束
        3. 内容页 → LLM阅读内容 → 推荐链接(已在阅读中) → 得到answer → 结束

        相比旧版本的优势：
        - 不再需要Scouting阶段（1958-2041行）
        - 每种页面类型都有专门的LLM交互，一次性完成决策
        - 减少重复让LLM看链接
        - 流程更清晰、更高效
        """
        while not ctx.is_time_up():
            # --- Phase 1: Navigation ---
            if not session.pending_link_queue:
                self.logger.info("Queue empty. Ending search.")
                break

            next_url = session.pending_link_queue.popleft()
            self.logger.info(f"🔗 Processing: {next_url}")

            # 1.1 门禁检查（next_url）
            if ctx.has_visited(next_url):
                self.logger.debug(f"✓ Already visited: {next_url}")
                continue

            # 1.2 检查是否是虚拟搜索URL
            if next_url.startswith("search:"):
                parts = next_url.split(":", 2)
                if len(parts) != 3:
                    self.logger.error(f"Invalid virtual search URL format: {next_url}")
                    continue

                _, search_engine, search_phrase = parts
                self.logger.info(f"🔍 Executing search on {search_engine}: {search_phrase}")

                from agentmatrix.core.browser.google import search_google
                from agentmatrix.core.browser.bing import search_bing

                search_fun = search_google if search_engine.lower() == "google" else search_bing
                await search_fun(adapter=self.browser, tab=session.handle, query=search_phrase)
            else:
                await self.browser.navigate(session.handle, next_url)

            final_url = self.browser.get_tab_url(session.handle)
            session.current_url = final_url

            # 1.3 从队列中移除 final_url（如果存在）
            if final_url in session.pending_link_queue:
                temp_list = list(session.pending_link_queue)
                temp_list.remove(final_url)
                session.pending_link_queue = deque(temp_list)

            # 1.4 检查 final_url 是否应该被处理
            if ctx.has_visited(final_url):
                self.logger.debug(f"✓ Already visited after redirect: {final_url}")
                continue

            # 1.5 标记已访问
            ctx.mark_visited(next_url)
            ctx.mark_visited(final_url)

            # === Phase 2: Identify Page Type ===
            page_type = await self.browser.analyze_page_type(session.handle)

            if page_type == PageType.ERRO_PAGE:
                self.logger.warning(f"🚫 Error Page: {final_url}")
                continue

            # === 分支 A: 静态资源 ===
            if page_type == PageType.STATIC_ASSET:
                self.logger.info(f"📄 Static Asset: {final_url}")
                markdown = await self._get_full_page_markdown(session.handle, ctx, next_url)
                answer = await self._stream_process_markdown(markdown, ctx, final_url, session)

                if answer:
                    return answer

                # 处理从流式阅读中发现的链接
                pending_links = ctx.get_pending_links()
                for pending_link in pending_links:
                    session.pending_link_queue.append(pending_link)
                    ctx.mark_evaluated(pending_link)

                continue

            # === 分支 B: 交互式网页 ===
            elif page_type == PageType.NAVIGABLE:
                self.logger.debug("🌐 Navigable Page")
                await self.browser.stabilize(session.handle)

                # 判断页面类型
                is_google = 'google.com/search' in final_url or 'www.google.' in final_url
                is_bing = 'bing.com/search' in final_url

                if is_google or is_bing:
                    # === 类型1: 搜索结果页 ===
                    search_engine = "Google" if is_google else "Bing"
                    self.logger.info(f"🔍 {search_engine} Search Results")

                    raw_html = session.handle.html
                    answer = await self._stream_process_search_result(raw_html, ctx, final_url, session, search_engine)

                    if answer:
                        return answer

                    # 搜索结果页处理完成，继续下一个URL
                    continue

                else:
                    # === 统一处理：先 extract 内容，根据长度判断页面类型 ===
                    # 默认当做内容页，先尝试提取内容
                    self.logger.info(f"📄 Attempting to extract content: {final_url}")
                    markdown = await self._get_full_page_markdown(session.handle, ctx, next_url)

                    # 根据提取的内容长度判断页面类型
                    content_length = len(markdown.strip()) if markdown else 0
                    self.logger.debug(f"Extracted content length: {content_length} chars")

                    # 阈值：如果提取的内容少于 150 字符，认为是导航页
                    if content_length < 150:
                        # === 类型2: 导航页（extract 内容太少） ===
                        self.logger.info(f"🧭 Navigation Page: {final_url} (extracted only {content_length} chars < 150 threshold)")
                        answer = await self._process_navigation_page(session.handle, ctx, final_url, session)

                        if answer:
                            return answer

                        # 导航页处理完成，继续下一个URL
                        continue

                    else:
                        # === 类型3: 内容页（extract 成功） ===
                        self.logger.info(f"📖 Content Page: {final_url} (extracted {content_length} chars)")
                        answer = await self._stream_process_markdown(markdown, ctx, final_url, session)

                        if answer:
                            return answer

                        # 处理从流式阅读中发现的链接
                        pending_links = ctx.get_pending_links()
                        for pending_link in pending_links:
                            session.pending_link_queue.append(pending_link)
                            ctx.mark_evaluated(pending_link)

                        # 内容页处理完成，继续下一个URL
                        continue

        # 未找到答案
        return None

    

    # ==========================================
    # 3. 小脑决策辅助
    # ==========================================

