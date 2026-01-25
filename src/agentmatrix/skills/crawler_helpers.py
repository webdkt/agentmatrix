"""
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
    


    async def _filter_relevant_links(
        self,
        candidates: Dict[str, str],
        page_summary: str,
        ctx,
        current_url: str = None,
        prompt_template: str = None
    ) -> List[str]:
        """
        [Brain] 批量筛选链接（统一实现）

        改进：使用文本映射机制，不让 LLM 看长 URL，提升 Token 效率

        Args:
            candidates: 候选链接字典 {url: link_text}
            page_summary: 当前页面摘要
            ctx: 上下文对象（MissionContext 或 WebSearcherContext）
            current_url: 当前页面 URL（用于判断链接是否指向本站）
            prompt_template: 可选的自定义 prompt（用于特殊需求）

        Returns:
            筛选后的 URL 列表
        """
        from urllib.parse import urlparse

        # 1. 规则预过滤
        ignored_keywords = [
            "login", "signin", "sign up", "register", "password",
            "privacy policy", "terms of use", "contact us", "about us",
            "customer service", "language", "sitemap", "javascript:",
            "mailto:", "tel:", "unsubscribe"
        ]

        clean_candidates = {}
        for link, link_text in candidates.items():
            if not link or len(link_text) < 2:
                continue
            text_lower = link_text.lower()
            if any(k in text_lower for k in ignored_keywords):
                continue
            clean_candidates[link] = link_text

        if not clean_candidates:
            self.logger.debug(f"No clean links found for {ctx.purpose}")
            return []

        # 2. 提取当前域名（用于判断链接是否指向本站）
        current_domain = None
        if current_url:
            try:
                current_domain = urlparse(current_url).netloc
            except:
                pass

        # 3. 为所有候选链接构建增强文本映射
        text_to_url = {}
        candidates_with_enhanced_text = []
        for url, text in clean_candidates.items():
            # 解析链接的域名
            link_domain = None
            try:
                link_domain = urlparse(url).netloc
            except:
                pass

            # 生成增强的显示文本
            if link_domain == current_domain:
                # 本站链接
                display_text = f"{text}（本站）"
            elif link_domain:
                # 外部链接
                display_text = f"{text}（跳转到 {link_domain}）"
            else:
                # 无法解析域名
                display_text = text

            # 处理重名（如果多个链接有相同的增强文本）
            base_text = display_text
            counter = 2
            while display_text in text_to_url:
                display_text = f"{base_text}({counter})"
                counter += 1

            text_to_url[display_text] = url
            candidates_with_enhanced_text.append((url, display_text))

        # 4. 根据候选数量确定提前终止阈值
        total_candidates = len(candidates_with_enhanced_text)
        if total_candidates <= 20:
            # 少量候选：不设阈值，全部处理完
            early_stop_threshold = None
        else:
            # 大量候选：设低阈值，达到即停止
            early_stop_threshold = 3

        # 5. 分批 LLM 过滤
        batch_size = 10
        selected_urls = []
        candidates_list = candidates_with_enhanced_text

        for i in range(0, len(candidates_list), batch_size):
            batch = candidates_list[i:i + batch_size]

            # 构建给 LLM 看的列表（只显示增强文本，不显示 URL）
            list_str = "\n".join([f"- {enhanced_text}" for url, enhanced_text in batch])

            # 构建 batch 的文本到URL映射
            batch_text_to_url = {enhanced_text: url for url, enhanced_text in batch}

            # 6. 构建完整的上下文信息
            context_info = f"Mission: Find links relevant to \"{ctx.purpose}\".\n\n"
            if current_domain:
                context_info += f"Current website: {current_domain}\n"
            context_info += f"This page is about: {page_summary}\n\n"

            # 使用自定义或默认 prompt
            if prompt_template:
                prompt = prompt_template.format(
                    purpose=ctx.purpose,
                    current_domain=current_domain or "unknown",
                    page_summary=page_summary,
                    list_str=list_str
                )
            else:
                # 默认 prompt（适配新的文本格式）
                prompt = f"""{context_info}[Candidates]
{list_str}

[Instructions]
1. Select ONLY links that are DIRECTLY relevant to the Mission
2. Each link must have HIGH probability of containing useful information
3. IGNORE ambiguous or generic links (e.g., "Learn More", "Click Here"）
4. AVOID links that clearly point to non-relevant content
5. 如果是百度百科这类网页，上面的链接很多是无关的，要仔细甄别，只选择确定有关的
6. Be SELECTIVE - only choose links you are CONFIDENT will help
7. Note: Links marked with （本站）stay on the same website, others navigate away

OUTPUT FORMAT: Just list the link text exactly as shown above, one per line.
"""

            try:
                # 调用小脑
                resp = await self.cerebellum.backend.think(
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_reply = resp.get('reply', '')
                self.logger.debug(f"LLM reply: {raw_reply}")

                # 7. 解析 LLM 返回的文本，映射回 URL
                reply_lines = [line.strip() for line in raw_reply.split('\n') if line.strip()]

                for reply_text in reply_lines:
                    # 容错：移除可能的序号前缀（如 "1. ", "- "）
                    clean_reply_text = reply_text.strip()
                    if clean_reply_text.startswith('- '):
                        clean_reply_text = clean_reply_text[2:].strip()
                    if '. ' in clean_reply_text[:5]:  # 只在开头检查序号
                        try:
                            parts = clean_reply_text.split('. ', 1)
                            if parts[0].isdigit():
                                clean_reply_text = parts[1].strip()
                        except:
                            pass

                    # 从本批次的映射中查找 URL
                    if clean_reply_text in batch_text_to_url:
                        url = batch_text_to_url[clean_reply_text]
                        if url not in selected_urls:
                            selected_urls.append(url)
                    else:
                        # 模糊匹配（容错 LLM 输出时的微小变化）
                        for display_text, url in batch_text_to_url.items():
                            if clean_reply_text in display_text or display_text in clean_reply_text:
                                if url not in selected_urls:
                                    selected_urls.append(url)
                                break

                # 8. 提前终止：达到阈值后停止
                if early_stop_threshold and len(selected_urls) >= early_stop_threshold:
                    self.logger.info(
                        f"✓ Early stop: selected {len(selected_urls)} links "
                        f"(threshold: {early_stop_threshold}) from {total_candidates} candidates"
                    )
                    return selected_urls[:early_stop_threshold]

            except Exception as e:
                self.logger.error(f"Link filtering batch failed: {e}")
                continue

        self.logger.debug(f"Selected {len(selected_urls)} links from {total_candidates} candidates")
        return selected_urls

    async def _choose_best_interaction(
        self,
        candidates: List[Dict],
        page_summary: str,
        ctx,
        prompt_template: str = None
    ) -> Optional:
        """
        [Brain] 选择最佳按钮点击（统一实现）

        使用串行淘汰机制 + 三级筛选策略：
        1. Immediate (立即访问): 高度吻合，直接返回
        2. Potential (潜在相关): 可能相关，放回队列头部继续竞争
        3. None (无价值): 删除，继续下一组

        Args:
            candidates: List[Dict] 格式，每个 Dict 是 {button_text: PageElement}
            page_summary: 当前页面摘要
            ctx: 上下文对象（MissionContext 或 WebSearcherContext）
            prompt_template: 可选的自定义 prompt 模板

        Returns:
            选中的 PageElement，如果没有合适的则返回 None
        """
        if not candidates:
            return None

        BATCH_SIZE = 10

        # 转换为列表格式: [(button_text, element), ...]
        all_candidates = []
        for candidate_dict in candidates:
            for text, element in candidate_dict.items():
                all_candidates.append((text, element))

        # 使用 deque 支持高效的头部操作
        candidate_deque = deque(all_candidates)

        while candidate_deque:
            # 取前 batch_size 个（如果不足则取全部）
            batch_size = min(BATCH_SIZE, len(candidate_deque))
            batch = [candidate_deque.popleft() for _ in range(batch_size)]

            # 评估这批
            if prompt_template:
                result = await self._evaluate_button_batch(
                    batch, page_summary, ctx, prompt_template
                )
            else:
                result = await self._evaluate_button_batch(
                    batch, page_summary, ctx
                )

            if result["priority"] == "immediate":
                # 找到最佳匹配，立即返回
                self.logger.info(
                    f"⚡ Immediate match found: [{result['text']}] | "
                    f"Reason: {result['reason']}"
                )
                return result["element"]

            elif result["priority"] == "potential":
                # 将 winner 放回队列头部，参与下一轮竞争
                winner_tuple = (result["text"], result["element"])
                if len(candidate_deque) > 0:
                    candidate_deque.appendleft(winner_tuple)
                    self.logger.debug(
                        f"    Potential: [{result['text']}] → Put back to queue front. "
                        f"Queue size: {len(candidate_deque)}"
                    )
                else:
                    return result["element"]
            # else: None，这批全部丢弃，继续下一轮

        return None

    async def _evaluate_button_batch(
        self,
        batch: List[tuple],
        page_summary: str,
        ctx,
        prompt_template: str = None
    ) -> Dict[str, Any]:
        """
        评估一批按钮（统一实现）

        Args:
            batch: [(button_text, element), ...]
            page_summary: 页面摘要
            ctx: 上下文对象
            prompt_template: 可选的自定义 prompt 模板

        Returns:
            {
                "priority": "immediate" | "potential" | "none",
                "text": str,
                "element": PageElement,
                "reason": str
            }
        """
        if not batch:
            return {"priority": "none", "text": None, "element": None, "reason": "Empty batch"}

        options_str = ""
        for idx, (text, element) in enumerate(batch):
            options_str += f"{idx + 1}. [{text}]\n"
        options_str += "0. [None of these are useful]"

        # 使用自定义或默认 prompt
        if prompt_template:
            prompt = prompt_template.format(
                purpose=ctx.purpose,
                page_summary=page_summary,
                options_str=options_str,
                batch_size=len(batch)
            )
        else:
            # 默认 prompt（取 data_crawler 的版本，更详细）
            prompt = f"""
            You are evaluating buttons on a webpage to see if it can help with your research topic:
            [Research Topic]
                 {ctx.purpose}

            [Page Context]
            {page_summary}

            [Task]
            Categorize your choice into THREE levels:

            **LEVEL 1 - IMMEDIATE** (应立即访问)
            - Button clearly leads to information that achieves the purpose

            **LEVEL 2 - POTENTIAL** (可能相关)
            - Button might lead to relevant information
            - Examples: "Learn More", "Details", "Next", "View Resources"

            **LEVEL 3 - NONE** (都不相关)
            - Buttons unrelated to the purpose
            - Examples: "Share", "Login", "Home", "Contact"

            [Options]
            {options_str}

            [Output Format]
            JSON:
            {{
                "choice_id": <number 0-{len(batch)}>,
                "priority": "immediate" | "potential" | "none",
                "reason": "short explanation"
            }}
            """

        try:
            resp = await self.cerebellum.backend.think(
                messages=[{"role": "user", "content": prompt}]
            )
            raw_reply = resp.get('reply', '')

            # 提取 JSON（兼容各种格式）
            json_str = raw_reply.replace("```json", "").replace("```", "").strip()
            result = json.loads(json_str)

            choice_id = int(result.get("choice_id", 0))
            priority = result.get("priority", "none").lower()
            reason = result.get("reason", "")

            if priority not in ["immediate", "potential", "none"]:
                priority = "none"

            if choice_id == 0 or priority == "none":
                return {"priority": "none", "text": None, "element": None, "reason": reason}

            selected_index = choice_id - 1

            if 0 <= selected_index < len(batch):
                selected_text, selected_element = batch[selected_index]
                return {
                    "priority": priority,
                    "text": selected_text,
                    "element": selected_element,
                    "reason": reason
                }
            else:
                return {"priority": "none", "text": None, "element": None, "reason": "Invalid choice"}

        except Exception as e:
            self.logger.exception(f"Batch evaluation failed: {e}")
            return {"priority": "none", "text": None, "element": None, "reason": f"Error: {e}"}

    async def _get_full_page_markdown(self, tab, ctx) -> str:
        """
        获取完整页面的 Markdown，自动识别 HTML/PDF

        Args:
            tab: 浏览器标签页句柄
            ctx: 上下文对象（可选，用于临时文件保存）

        Returns:
            str: Markdown 格式的页面内容
        """
        from ..core.browser.browser_adapter import PageType

        content_type = await self.browser.analyze_page_type(tab)

        if content_type == PageType.STATIC_ASSET:
            return await self._pdf_to_full_markdown(tab, ctx)
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
                self.logger.debug("✓ Removed Google translate buttons via string replacement")
            elif is_bing_search:
                # Bing: <span>翻译此结果</span> - 只删除span
                raw_html = re.sub(
                    r'<span[^>]*>\s*翻译此结果\s*</span>',
                    '',
                    raw_html,
                    flags=re.IGNORECASE
                )
                self.logger.debug("✓ Removed Bing translate buttons via string replacement")

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
        self.logger.debug(f"\n\n {markdown} \n\n")

        

        return markdown or ""

    async def _pdf_to_full_markdown(self, tab, ctx) -> str:
        """
        将 PDF 转换为完整 Markdown

        Args:
            tab: 浏览器标签页句柄
            ctx: 上下文对象（可选，用于临时文件保存）

        Returns:
            str: Markdown 格式的 PDF 内容
        """
        # 下载 PDF 到本地
        pdf_path = await self.browser.save_static_asset(tab)

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
