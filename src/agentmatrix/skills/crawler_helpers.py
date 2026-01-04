"""
爬虫技能的公共辅助方法

提供链接筛选、按钮选择等 LLM 决策功能。
"""

import json
import re
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
