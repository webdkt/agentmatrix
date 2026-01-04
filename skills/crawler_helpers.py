"""
爬虫技能的公共辅助方法

提供链接筛选、按钮选择等 LLM 决策功能。
"""

import re
from typing import Dict, List


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
        prompt_template: str = None
    ) -> List[str]:
        """
        [Brain] 批量筛选链接（统一实现）

        Args:
            candidates: 候选链接字典 {url: link_text}
            page_summary: 当前页面摘要
            ctx: 上下文对象（MissionContext 或 WebSearcherContext）
            prompt_template: 可选的自定义 prompt（用于特殊需求）

        Returns:
            筛选后的 URL 列表
        """
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

        # 2. 分批 LLM 过滤
        batch_size = 10
        selected_urls = []
        url_pattern = re.compile(r'(https?://[^\s"\'<>]+)')
        candidates_list = list(clean_candidates.items())

        for i in range(0, len(candidates_list), batch_size):
            batch = candidates_list[i:i + batch_size]
            list_str = "\n".join([f"- [{text}] ({url})" for url, text in batch])
            batch_url_map = {url.strip(): text for url, text in batch}

            # 使用自定义或默认 prompt
            if prompt_template:
                prompt = prompt_template.format(
                    purpose=ctx.purpose,
                    page_summary=page_summary,
                    list_str=list_str
                )
            else:
                # 默认 prompt
                prompt = f"""
                Mission: Find links relevant to "{ctx.purpose}".

                Below is a list of links found on a webpage.
                This page is about: {page_summary}.
                Select ONLY the links that are likely to contain information related to the Mission or worth to explore.

                [Candidates]
                {list_str}

                [Instructions]
                1. Select links that are likely to contain information related to the Mission. Or may lead to information related to the Mission (destination worth explore).
                2. Ignore links clearly point to non-relevant pages or destinations
                3. 注意，如果是百度百科这样的网页，上面的链接很多是无关的，要仔细甄别，只选择确定有关的
                4. OUTPUT FORMAT: Just list the full URLs of the selected links, one per line.
                """

            try:
                # 调用小脑
                resp = await self.cerebellum.backend.think(
                    messages=[{"role": "user", "content": prompt}]
                )
                raw_reply = resp.get('reply', '')
                self.logger.debug(f"LLM reply: {raw_reply}")

                # 3. 正则提取与验证
                found_urls = url_pattern.findall(raw_reply)
                for raw_url in found_urls:
                    clean_url = raw_url.strip('.,;)]}"\'')

                    if clean_url in batch_url_map:
                        selected_urls.append(clean_url)
                    else:
                        # 容错匹配
                        for original_url in batch_url_map.keys():
                            if clean_url in original_url and len(clean_url) > 15:
                                selected_urls.append(original_url)
                                break

            except Exception as e:
                self.logger.error(f"Link filtering batch failed: {e}")
                continue

        self.logger.debug(f"Selected links: {selected_urls}")
        return list(set(selected_urls))
