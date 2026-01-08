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

from ..core.browser.google import search_google
from ..core.browser.bing import search_bing
from ..core.browser.browser_adapter import (
    BrowserAdapter, TabHandle, PageElement, PageSnapshot, PageType
)
from ..core.browser.browser_common import TabSession, BaseCrawlerContext
from ..skills.crawler_helpers import CrawlerHelperMixin
from ..core.browser.drission_page_adapter import DrissionPageAdapter
from ..core.action import register_action

search_func = search_google

# ==========================================
# Prompt 集中管理
# ==========================================

class WebSearcherPrompts:
    """Web Searcher Prompt 集中管理"""

    # ==========================================
    # 1. 章节选择
    # ==========================================

    CHAPTER_SELECTION = """You are searching for information to answer: "{question}"

Below is the table of contents for a document:

{toc_list}

[Task]
Select the chapters that are MOST LIKELY to contain information relevant to answering the question.

[Rules]
1. You can select multiple chapters
2. Be conservative - only select chapters that seem directly relevant
3. If unsure, you can select multiple chapters to be safe

[Output Format]

First, explain your reasoning (why you selected these chapters).

Then, output your selections using following format:

====章节选择====
你选择的章节名称1(replace with your choice)
你选择的章节名称2(replace with your choice)
...
====章节选择结束====

One chapter name per line. The chapter names must EXACTLY match the names shown in the TOC above."""

    CHAPTER_ERROR_HALLUCINATION = """Your selection contains chapters that don't exist in the TOC:

Invalid chapters:
{invalid_chapters}

Please select ONLY from the available chapters listed in the TOC. Try again."""

    CHAPTER_ERROR_FORMAT = """Your output format is incorrect.

Please use this EXACT format:

====章节选择====
章节名称1
章节名称2
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

[Notebook - What We Already Know]
{notebook}

[Current Page Content - Page {current_batch}]
{batch_text}

[Task]
Based on the Notebook, Current Page, AND your reading progress, provide a brief summary.

Consider your progress:
- If you're early in the document (first 20%), keep exploring even if this page is weak
- If you're late in the document (last 30%) and found nothing useful, consider skipping
- If you're in the middle, continue unless the content is completely irrelevant

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
- Provide a concise summary (2-5 sentences)
- Focus on facts, data, definitions, explanations
- Only extract information NOT already in Notebook
- Always include the source URL

##没有值得记录的笔记继续阅读
If the page doesn't contain new or useful information, but the document still shows promise:
- Use this heading
- Briefly explain why (1 sentence)
- Consider: If you're late in the document (>70%), you might want to skip

##完全不相关的文档应该放弃
If the page is completely irrelevant to the question (navigation, ads, unrelated topics):
- Use this heading
- Explain why (1 sentence)
- Skip the rest of this document
- Especially consider this if you're already deep into the document (>50%) and found nothing useful

[Output Format]

##对问题的回答 (or one of the other three headings)

Your content here...

[Important]
- Start with ONE of the four headings above (EXACTLY as shown)
- Provide your content below the heading
- Consider your reading progress when deciding whether to continue or skip"""

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
# 1. 状态与上下文定义
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

    def add_to_notebook(self, info: str):
        """添加信息到小本本"""
        if info:
            timestamp = time.strftime("%H:%M:%S")
            self.notebook += f"\n\n[{timestamp}] {info}\n"


# ==========================================
# 2. Web Searcher 核心逻辑
# ==========================================

class WebSearcherMixin(CrawlerHelperMixin):
    """
    Web 搜索器技能
    用于回答问题的网络搜索
    """

    @register_action(
        "针对一个问题上网搜索答案，提供要解决的问题和（可选但建议提供的）搜索关键字词",
        param_infos={
            "purpose": "要回答的问题（或研究目标）",
            "search_phrase": "可选，初始搜索关键词",
            "max_time": "可选，最大搜索分钟，默认20",
            "max_search_pages": "可选，最大搜索页数（默认5）",

        }
    )
    async def web_search(
        self,
        purpose: str,
        search_phrase: str = None,
        max_time: int = 20,
        max_search_pages: int = 5,
        temp_file_dir: Optional[str] = None
    ):
        """
        [Entry Point] 上网搜索回答问题（流式处理版本）

        Args:
            purpose: 要回答的问题（或研究目标）
            search_phrase: 初始搜索关键词
            max_time: 最大搜索时间（分钟）
            max_search_pages: 最大搜索页数（默认5）
            chunk_threshold: 分段阈值（字符数）
            temp_file_dir: 临时文件保存目录（可选，用于调试）
        """
        # 1. 准备环境
        profile_path = os.path.join(self.workspace_root, ".matrix", "browser_profile", self.name)
        download_path = os.path.join(self.current_workspace, "downloads")
        chunk_threshold = 5000

        if not search_phrase:
            resp = await self.brain.think(f"""
            现在我们要研究个新问题：{purpose}，打算上网搜索一下，需要你设计一下最合适的关键词或者关键字组合。输出的时候可以先简单解释一下这么设计的理由，但是最后一行必须是也只能是要搜索的内容（也就是输入到搜索引擎搜索栏的内容）。例如你认为应该搜索"Keyword"，那么最后一行就只能是"Keyword"
            """)
            reply = resp['reply']
            #get last line of reply
            if '\n' in reply:
                search_phrase = reply.split('\n')[-1].strip()
        #如果还是有问题,我们直接搜索问题：
        if not search_phrase:
            search_phrase = purpose
        self.logger.info(f"🔍 准备搜索: {search_phrase}")

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
        self.logger.info(f"🔍 Max search pages: {max_search_pages}")

        # 2. 启动浏览器
        await self.browser.start(headless=False)

        try:
            # 3. 创建 Tab 和 Session
            tab = await self.browser.get_tab()
            session = TabSession(handle=tab, current_url="")

            # 4. 外层循环：逐页处理搜索结果
            for page_num in range(1, max_search_pages + 1):
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"🔍 Fetching search results page {page_num}/{max_search_pages}")
                self.logger.info(f"{'='*60}\n")

                # 4.1 获取第 page_num 页的搜索结果
                search_result = await search_func(
                    self.browser,
                    tab,
                    search_phrase,
                    max_pages=max_search_pages,
                    page=page_num  # 指定只获取第 page_num 页
                )

                if not search_result:
                    self.logger.warning(f"⚠️ No results found on page {page_num}")
                    break

                # 4.2 将 URL 添加到 pending_link_queue
                added_count = 0
                for result in search_result:
                    url = result['url']
                    if not ctx.has_visited(url):
                        session.pending_link_queue.append(url)
                        added_count += 1

                self.logger.info(f"✓ Added {added_count} URLs from page {page_num} to queue")

                # 4.3 运行 _run_search_lifecycle 处理这些 URL
                self.logger.info(f"\n🌐 Processing URLs from page {page_num}...")
                answer = await self._run_search_lifecycle(session, ctx)

                # 4.4 如果找到答案，提前返回
                if answer:
                    self.logger.info(f"✅ Found answer on page {page_num}!")
                    return f"Answer: {answer}\n\n---\nNotebook:\n{ctx.notebook}"

                # 4.5 检查时间和资源限制
                if ctx.is_time_up():
                    self.logger.info("⏰ Time up!")
                    break

                self.logger.info(f"✓ Completed page {page_num}, continuing to next page...")

            # 5. 未找到答案，返回 notebook
            self.logger.info("⏸ Exhausted all search pages without finding complete answer")
            return f"Could not find a complete answer.\n\nHere's what I found:\n{ctx.notebook}"

        except Exception as e:
            self.logger.exception("Web searcher crashed")
            return f"Search failed with error: {e}"
        finally:
            self.logger.info("🛑 Closing browser...")
            await self.browser.close()

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
    # 2. 获取完整页面内容
    # ==========================================

    async def _get_full_page_markdown(self, tab: TabHandle, ctx: WebSearcherContext) -> str:
        """
        获取完整页面的 Markdown，无字符限制
        - HTML: 使用 trafilatura 提取完整 Markdown
        - PDF: 使用 pdf_to_markdown 转换完整文档
        """
        content_type = await self.browser.analyze_page_type(tab)

        if content_type == PageType.STATIC_ASSET:
            return await self._pdf_to_full_markdown(tab, ctx)
        else:
            return await self._html_to_full_markdown(tab)

    async def _html_to_full_markdown(self, tab: TabHandle) -> str:
        """将 HTML 页面转换为完整 Markdown"""
        import trafilatura

        raw_html = tab.html
        url = self.browser.get_tab_url(tab)

        # 使用 trafilatura 提取完整 Markdown
        markdown = trafilatura.extract(
            raw_html,
            include_links=True,
            include_formatting=True,
            output_format='markdown',
            url=url
        )

        # 备选方案
        if not markdown or len(markdown) < 50:
            markdown = tab.text

        return markdown or ""

    async def _pdf_to_full_markdown(self, tab: TabHandle, ctx: WebSearcherContext) -> str:
        """将 PDF 转换为完整 Markdown（独立实现，便于后续优化）"""
        from skills.report_writer_utils import pdf_to_markdown

        # 下载 PDF 到本地
        pdf_path = await self.browser.save_static_asset(tab)

        # 转换完整 PDF 为 Markdown
        markdown = pdf_to_markdown(pdf_path)

        # 可选：保存到临时文件（调试用）
        if ctx.temp_file_dir:
            import os
            from slugify import slugify
            os.makedirs(ctx.temp_file_dir, exist_ok=True)
            filename = slugify(f"pdf_{os.path.basename(pdf_path)}") + ".md"
            temp_path = os.path.join(ctx.temp_file_dir, filename)
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(markdown)
            self.logger.info(f"📄 Saved markdown to: {temp_path}")

        return markdown

    # ==========================================
    # 3. 辅助方法（目录、选择章节、分段）
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
        ctx: WebSearcherContext
    ) -> List[int]:
        """
        让 LLM 根据问题选择相关章节（带重试机制）
        返回: 选中的章节索引列表（0-based）
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
        initial_prompt = WebSearcherPrompts.CHAPTER_SELECTION.format(
            question=ctx.purpose,
            toc_list=toc_list
        )

        # 初始化消息列表
        messages = [{"role": "user", "content": initial_prompt}]

        # 最大重试次数
        MAX_RETRIES = 5

        for attempt in range(MAX_RETRIES):
            try:
                # 调用 LLM
                response = await self.cerebellum.backend.think(messages=messages)
                reply = response.get('reply', '').strip()

                self.logger.debug(f"Chapter selection attempt {attempt + 1}:\n{reply}")

                # 将 LLM 的回复作为 assistant 消息加入历史
                messages.append({"role": "assistant", "content": reply})

                # 解析输出
                result = self._parse_chapter_selection(reply, chapter_name_to_index)

                if result["status"] == "success":
                    # 情况 (1): 解析成功，所有章节都是真的
                    selected_indices = result["selected_indices"]
                    self.logger.info(f"✅ Successfully selected {len(selected_indices)} chapters: {selected_indices}")
                    return selected_indices

                elif result["status"] == "hallucination":
                    # 情况 (2): 解析成功，但有些章节是假的（幻觉）
                    invalid_chapters = result["invalid_chapters"]
                    self.logger.warning(f"⚠️ LLM hallucinated chapters: {invalid_chapters}")

                    # 使用错误提示模板
                    invalid_chapters_str = "\n".join(f"- {ch}" for ch in invalid_chapters)
                    error_msg = WebSearcherPrompts.CHAPTER_ERROR_HALLUCINATION.format(
                        invalid_chapters=invalid_chapters_str
                    )

                    messages.append({"role": "user", "content": error_msg})
                    continue

                else:  # result["status"] == "parse_error"
                    # 情况 (3): 解析失败（格式不对）
                    self.logger.warning(f"⚠️ LLM output format incorrect")

                    # 使用错误提示模板
                    error_msg = WebSearcherPrompts.CHAPTER_ERROR_FORMAT

                    messages.append({"role": "user", "content": error_msg})
                    continue

            except Exception as e:
                self.logger.error(f"Chapter selection failed: {e}")

                if attempt < MAX_RETRIES - 1:
                    messages.append({
                        "role": "user",
                        "content": "An error occurred. Please try again. Make sure to follow the output format exactly."
                    })
                    continue
                else:
                    # 所有重试都失败，返回空列表
                    return []

        # 超过最大重试次数，返回空列表（会触发全文处理）
        self.logger.error(f"❌ Max retries ({MAX_RETRIES}) exceeded. Falling back to full text processing.")
        return []

    def _parse_chapter_selection(
        self,
        llm_output: str,
        chapter_name_to_index: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        解析 LLM 的章节选择输出

        返回:
        {
            "status": "success" | "hallucination" | "parse_error",
            "selected_indices": List[int],      # 如果成功
            "invalid_chapters": List[str]       # 如果有幻觉
        }
        """
        # 查找分隔符
        start_marker = "====章节选择===="
        end_marker = "====章节选择结束===="

        start_idx = llm_output.find(start_marker)
        end_idx = llm_output.find(end_marker)

        # 检查分隔符是否存在
        if start_idx == -1 or end_idx == -1:
            return {"status": "parse_error", "selected_indices": [], "invalid_chapters": []}

        # 提取章节列表部分
        start_idx += len(start_marker)
        chapter_section = llm_output[start_idx:end_idx].strip()

        # 按行分割
        chapter_lines = [
            line.strip()
            for line in chapter_section.split('\n')
            if line.strip()
        ]

        if not chapter_lines:
            return {"status": "parse_error", "selected_indices": [], "invalid_chapters": []}

        # 验证章节是否存在于 TOC 中
        selected_indices = []
        invalid_chapters = []

        for chapter_name in chapter_lines:
            if chapter_name in chapter_name_to_index:
                selected_indices.append(chapter_name_to_index[chapter_name])
            else:
                invalid_chapters.append(chapter_name)

        # 判断结果
        if invalid_chapters:
            # 有幻觉
            return {
                "status": "hallucination",
                "selected_indices": selected_indices,
                "invalid_chapters": invalid_chapters
            }
        elif selected_indices:
            # 成功
            return {
                "status": "success",
                "selected_indices": selected_indices,
                "invalid_chapters": []
            }
        else:
            # 没有选中任何章节（也可能是格式错误）
            return {
                "status": "parse_error",
                "selected_indices": [],
                "invalid_chapters": []
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

    async def _process_batch(
        self,
        batch_text: str,
        ctx: WebSearcherContext,
        doc_title: str,
        current_batch: int,
        total_batches: int,
        url
    ) -> Dict[str, Any]:
        """
        统一的批处理函数（带重试机制）

        参数:
            batch_text: 当前批次文本
            ctx: 搜索上下文
            doc_title: 文档名称
            current_batch: 当前批次（页码，从 1 开始）
            total_batches: 总批次数（总页数）

        返回:
        {
            "heading_type": "answer" | "note" | "continue" | "skip_doc",
            "content": str
        }
        """
        # 计算进度百分比
        progress_pct = int((current_batch / total_batches) * 100)

        # 初始化消息列表
        messages = [
            {
                "role": "user",
                "content": WebSearcherPrompts.BATCH_PROCESSING.format(
                    question=ctx.purpose,
                    doc_title=doc_title,
                    current_batch=current_batch,
                    total_batches=total_batches,
                    progress_pct=progress_pct,
                    notebook=ctx.notebook,
                    batch_text=batch_text,
                    url=url
                )
            }
        ]

        # 最大重试次数
        MAX_RETRIES = 5

        for attempt in range(MAX_RETRIES):
            try:
                # 调用 LLM
                response = await self.cerebellum.backend.think(messages=messages)
                reply = response.get('reply', '').strip()

                self.logger.debug(f"Batch processing attempt {attempt + 1}:\n{reply}")

                # 将 LLM 的回复作为 assistant 消息加入历史
                messages.append({"role": "assistant", "content": reply})

                # 解析输出
                result = self._parse_batch_output(reply)

                if result["status"] == "success":
                    # 成功
                    heading_type = result["heading_type"]
                    content = result["content"]

                    # 根据类型记录日志
                    if heading_type == "answer":
                        self.logger.info(f"✅ Found answer in batch")
                    elif heading_type == "note":
                        self.logger.info(f"📝 Found useful info in batch")
                    elif heading_type == "continue":
                        self.logger.debug(f"👀 No new info, continuing")
                    else:  # skip_doc
                        self.logger.warning(f"🚫 Document irrelevant, skipping")

                    return {
                        "heading_type": heading_type,
                        "content": content
                    }

                else:  # result["status"] == "parse_error"
                    # 格式错误
                    self.logger.warning(f"⚠️ LLM output format incorrect")

                    error_msg = WebSearcherPrompts.BATCH_ERROR_FORMAT
                    messages.append({"role": "user", "content": error_msg})
                    continue

            except Exception as e:
                self.logger.error(f"Batch processing failed: {e}")

                if attempt < MAX_RETRIES - 1:
                    messages.append({
                        "role": "user",
                        "content": "An error occurred. Please try again. Make sure to start with one of the four headings."
                    })
                    continue
                else:
                    # 所有重试都失败，返回默认值
                    return {"heading_type": "continue", "content": ""}

        # 超过最大重试次数，返回默认值（继续阅读）
        self.logger.error(f"❌ Max retries ({MAX_RETRIES}) exceeded. Defaulting to 'continue'.")
        return {"heading_type": "continue", "content": ""}

    def _parse_batch_output(self, llm_output: str) -> Dict[str, Any]:
        """
        解析 LLM 的批处理输出

        返回:
        {
            "status": "success" | "parse_error",
            "heading_type": "answer" | "note" | "continue" | "skip_doc",
            "content": str
        }
        """
        # 定义四种标题
        HEADINGS = {
            "##对问题的回答": "answer",
            "##值得记录的笔记": "note",
            "##没有值得记录的笔记继续阅读": "continue",
            "##完全不相关的文档应该放弃": "skip_doc"
        }

        # 检查输出以哪个标题开头
        heading_type = None
        heading_used = None

        for heading, htype in HEADINGS.items():
            if llm_output.startswith(heading):
                heading_type = htype
                heading_used = heading
                break

        if heading_type is None:
            # 没有找到任何标题
            return {"status": "parse_error", "heading_type": None, "content": ""}

        # 提取标题下面的内容
        content_start = len(heading_used)
        content = llm_output[content_start:].strip()

        # 如果内容为空，也算解析错误
        if not content:
            return {"status": "parse_error", "heading_type": None, "content": ""}

        # 成功
        return {
            "status": "success",
            "heading_type": heading_type,
            "content": content
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
        url: str
    ) -> Optional[str]:
        """
        流式处理 Markdown 文档（统一入口）

        流程：
        1. 判断长度 → 决定是否需要选章节
        2. 准备待处理内容（全文 OR 选中章节）
        3. 按段落边界分成批次
        4. 逐批流式处理
        """
        # 1. 判断长度
        is_long = len(markdown) > ctx.chunk_threshold

        # 2. 准备待处理内容
        if not is_long:
            # 短文档：全文处理
            self.logger.info(f"📄 Short document ({len(markdown)} chars). Processing full text.")
            content_to_process = markdown
        else:
            # 长文档：生成目录 → 选择章节
            self.logger.info(f"📚 Long document ({len(markdown)} chars). Generating TOC...")
            toc = self._generate_document_toc(markdown)

            if not toc or len(toc)<2:
                # 无标题结构或者只有一个标题，全文处理
                self.logger.info("📋 No headers found. Processing full text.")
                content_to_process = markdown
            else:
                # 让 LLM 选择章节
                self.logger.info(f"📑 Found {len(toc)} chapters. Asking LLM to select...")
                selected_indices = await self._let_llm_select_chapters(toc, ctx)

                if not selected_indices:
                    self.logger.warning("⚠️ No chapters selected. Processing full text.")
                    content_to_process = markdown
                else:
                    self.logger.info(f"✅ Selected {len(selected_indices)} chapters")
                    # 提取选中章节
                    selected_parts = []
                    for idx in selected_indices:
                        chapter = toc[idx]
                        content = markdown[chapter["start"]:chapter["end"]]
                        selected_parts.append(f"# {chapter['title']}\n\n{content}")
                    content_to_process = "\n\n".join(selected_parts)

        # 3. 按段落边界分成批次
        self.logger.info(f"🔪 Splitting content into batches (max {ctx.chunk_threshold} chars each)...")
        batches = self._split_by_paragraph_boundaries(content_to_process, ctx.chunk_threshold)
        total_batches = len(batches)
        self.logger.info(f"📊 Split into {total_batches} batches")

        # 4. 获取文档标题（用于 LLM 上下文）
        doc_title = self._extract_document_title(content_to_process)

        # 5. 逐批流式处理
        for i, batch in enumerate(batches, start=1):  # 从 1 开始计数
            current_batch = i
            progress_pct = int((current_batch / total_batches) * 100)
            self.logger.info(
                f"🔄 Processing batch {current_batch}/{total_batches} "
                f"({progress_pct}%, {len(batch)} chars)..."
            )

            # 统一的批处理（传入进度信息）
            result = await self._process_batch(
                batch,
                ctx,
                doc_title=doc_title,
                current_batch=current_batch,
                total_batches=total_batches,
                url=url
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

            # heading_type == "continue": 什么都不做，继续下一批

        # 未找到答案
        return None

    async def _run_search_lifecycle(self, session: TabSession, ctx: WebSearcherContext) -> Optional[str]:
        """
        [The Core Loop] 搜索生命周期
        核心逻辑：访问页面 → 尝试回答问题 → 不能回答则记录信息 → 继续探索
        """
        while not ctx.is_time_up():
            # --- Phase 1: Navigation ---
            if not session.pending_link_queue:
                self.logger.info("Queue empty. Ending search.")
                break

            next_url = session.pending_link_queue.popleft()
            self.logger.info(f"🔗 Navigating to: {next_url}")

            # 1.1 门禁检查
            if ctx.has_visited(next_url) or any(bl in next_url for bl in ctx.blacklist):
                continue

            # 1.2 导航到页面
            nav_report = await self.browser.navigate(session.handle, next_url)
            final_url = self.browser.get_tab_url(session.handle)
            session.current_url = final_url

            ctx.mark_visited(next_url)
            ctx.mark_visited(final_url)

            # 1.3 二次黑名单检查
            if any(bl in final_url for bl in ctx.blacklist):
                self.logger.warning(f"🚫 Redirected to blacklisted URL: {final_url}")
                continue

            # === Phase 2: Identify Page Type ===
            page_type = await self.browser.analyze_page_type(session.handle)

            if page_type == PageType.ERRO_PAGE:
                self.logger.warning(f"🚫 Error Page: {final_url}")
                continue

            # === 分支 A: 静态资源 ===
            if page_type == PageType.STATIC_ASSET:
                self.logger.info(f"📄 Static Asset: {final_url}")

                # 获取完整 Markdown 并流式处理
                markdown = await self._get_full_page_markdown(session.handle, ctx)
                answer = await self._stream_process_markdown(markdown, ctx,final_url)

                if answer:
                    return answer  # 找到答案，直接返回

                continue  # 继续处理下一个 URL

            # === 分支 B: 交互式网页 ===
            elif page_type == PageType.NAVIGABLE:
                self.logger.debug("🌐 Navigable Page. Entering processing loop.")
                page_active = True
                page_changed = True

                while page_active and not ctx.is_time_up():
                    # 1. Stabilize (滚动加载)
                    if page_changed:
                        await self.browser.stabilize(session.handle)

                        # 2. 获取完整 Markdown 并流式处理
                        markdown = await self._get_full_page_markdown(session.handle, ctx)
                        answer = await self._stream_process_markdown(markdown, ctx,final_url)

                        # 3. 如果找到答案，直接返回
                        if answer:
                            return answer

                        # 4. 生成页面摘要（用于后续链接筛选）
                        page_summary = markdown[:500] if markdown else ""

                    # === Phase 4: Scouting ===
                    links, buttons = await self.browser.scan_elements(session.handle)
                    self.logger.debug(f"🔍 Found {len(links)} links and {len(buttons)} buttons")

                    # 4.1 处理 Links
                    if page_changed:
                        filtered_links = {}
                        for link in links:
                            if ctx.has_link_assessed(link):
                                continue
                            if ctx.has_visited(link):
                                continue
                            if link in session.pending_link_queue:
                                continue
                            if any(bl in link for bl in ctx.blacklist):
                                continue
                            filtered_links[link] = links[link]

                        # 评估链接相关性
                        selected_links = await self._filter_relevant_links(filtered_links, page_summary, ctx)

                        # 标记已评估
                        for link in filtered_links:
                            ctx.mark_link_assessed(link)

                        # 添加到队列
                        new_links_count = 0
                        for link in selected_links:
                            session.pending_link_queue.append(link)
                            new_links_count += 1
                        self.logger.info(f"👀 Added {new_links_count} links to queue")

                    # 4.2 处理 Buttons
                    candidate_buttons = []
                    for button_text in buttons:
                        if not ctx.has_button_assessed(session.current_url, button_text):
                            candidate_buttons.append({button_text: buttons[button_text]})

                    # === Phase 5: Execution ===
                    if not candidate_buttons:
                        self.logger.info("🤔 No worthy buttons. Moving to next page.")
                        page_active = False
                        continue

                    chosen_button = await self._choose_best_interaction(candidate_buttons, page_summary, ctx)

                    # 标记已评估
                    assessed_button_texts = [list(btn.keys())[0] for btn in candidate_buttons]
                    ctx.mark_buttons_assessed(session.current_url, assessed_button_texts)

                    if not chosen_button:
                        self.logger.info("🤔 No worthy buttons. Moving to next page.")
                        page_active = False
                        continue

                    # 执行点击
                    self.logger.info(f"🖱️ Clicking: [{chosen_button.get_text()}]")
                    ctx.mark_interacted(session.current_url, chosen_button.get_text())

                    report = await self.browser.click_and_observe(session.handle, chosen_button)

                    # 5.1 处理新 Tab
                    if report.new_tabs:
                        self.logger.info(f"✨ New Tab(s): {len(report.new_tabs)}")
                        for new_tab_handle in report.new_tabs:
                            new_session = TabSession(handle=new_tab_handle, current_url="", depth=session.depth + 1)
                            answer = await self._run_search_lifecycle(new_session, ctx)
                            if answer:  # 如果在递归中找到答案，向上传递
                                return answer
                            await self.browser.close_tab(new_tab_handle)

                    # 5.2 处理页面变动
                    if report.is_dom_changed or report.is_url_changed:
                        self.logger.info("🔄 Page changed. Re-assessing.")
                        page_changed = True
                        if report.is_url_changed:
                            session.current_url = self.browser.get_tab_url(session.handle)
                        continue

                    # 5.3 无变化
                    page_changed = False
                    continue

        # 未找到答案
        return None

    # ==========================================
    # 3. 小脑决策辅助
    # ==========================================

