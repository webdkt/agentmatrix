"""
New Web Search Skill — 极简三动作架构

三个 Action：
- search_with_google(query) / search_with_bing(query)  → 搜索，返回结果列表
- visit(url)     → 访问网页，返回页面内容预览
- deep_read(instruction) → 深度阅读当前页面，提取特定信息

设计理念：
- 外层 Agent 做所有策略决策
- 内层只做机械执行
- 通过结构化数据通信
"""

import re
import time
import asyncio
from typing import List, Dict, Optional, Any
from urllib.parse import quote_plus, urlparse

from ...core.action import register_action
from ...core.browser.browser_adapter import PageType
from ...core.browser.drission_page_adapter import DrissionPageAdapter
from ...core.browser.browser_common import TabSession
from ...core.exceptions import LLMServiceConnectionError
from ...utils.token_utils import estimate_tokens

from .utils import detect_visited_links, extract_domain
from .page_processor import (
    extract_markdown,
    analyze_page_structure,
    generate_preview,
    split_into_batches,
)

# MicroAgent 延迟导入（避免循环依赖），在 deep_read 中动态导入


# ==========================================
# Skill 主类
# ==========================================


class New_web_searchSkillMixin:
    """
    New Web Search Skill — 极简三动作架构

    search → visit → deep_read
    """

    _skill_description = "网络搜索：搜索、访问页面、深度阅读"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 内部状态
        self._search_state: Dict[str, int] = {}  # {query: current_page_number}
        self._page_cache: Dict[str, str] = {}  # {url: markdown}
        self._last_search_query: Optional[str] = None  # 上一次搜索的关键词
        self.browser = None  # 浏览器实例（懒初始化）

    # ==========================================
    # 浏览器初始化
    # ==========================================

    async def _ensure_browser(self):
        """懒初始化浏览器"""
        if self.browser is not None:
            return

        agent_name = self.root_agent.name
        task_id = self.root_agent.current_task_id or "default"

        profile_path = str(
            self.root_agent.runtime.paths.get_browser_profile_dir(agent_name)
        )
        work_files_dir = self.root_agent.runtime.paths.get_agent_work_files_dir(
            agent_name, task_id
        )
        download_path = str(work_files_dir / "downloads")

        self.browser = DrissionPageAdapter(
            profile_path=profile_path, download_path=download_path
        )
        await self.browser.start(headless=False)
        self.logger.info("Browser initialized")

    async def _get_tab(self):
        """获取浏览器标签页"""
        await self._ensure_browser()
        return await self.browser.get_tab()

    # ==========================================
    # Action: search_with_google / search_with_bing
    # ==========================================

    @register_action(
        short_desc="[query] 用 Google 搜索，返回结果列表",
        description="""用 Google 搜索，返回当前页的搜索结果。

结果包含每个链接的标题、URL、摘要和访问状态（已访问的会标记 visited）。
用同一个关键词再次调用会自动翻到下一页。

注意：这是一个纯粹的搜索动作，只返回结果列表。用哪个链接、是否访问、是否深度阅读，由你决定。""",
        param_infos={"query": "搜索关键词"},
    )
    async def search_with_google(self, query: str) -> str:
        return await self._search(query, search_engine="google")

    @register_action(
        short_desc="[query] 用 Bing 搜索，返回结果列表",
        description="""用 Bing 搜索，返回当前页的搜索结果。

结果包含每个链接的标题、URL、摘要和访问状态（已访问的会标记 visited）。
用同一个关键词再次调用会自动翻到下一页。

注意：这是一个纯粹的搜索动作，只返回结果列表。用哪个链接、是否访问、是否深度阅读，由你决定。""",
        param_infos={"query": "搜索关键词"},
    )
    async def search_with_bing(self, query: str) -> str:
        return await self._search(query, search_engine="bing")

    async def _search(self, query: str, search_engine: str) -> str:
        """搜索的公共实现，被 search_with_google 和 search_with_bing 调用"""
        await self._ensure_browser()
        tab = await self._get_tab()

        try:
            # 判断是否翻页
            is_next_page = (
                self._last_search_query == query and query in self._search_state
            )

            if is_next_page:
                # 翻页：点击"下一页"
                self.logger.info(f"Trying next page for: {query}")

                has_next = await self._click_next_page(tab)
                if not has_next:
                    return f'搜索 "{query}" 没有下一页了（已到末尾）。'

                self._search_state[query] += 1
                current_page = self._search_state[query]
                self.logger.info(f"Search page {current_page} for: {query}")
                await self.browser.stabilize(tab)
            else:
                # 新搜索
                self._search_state[query] = 1
                self._last_search_query = query
                current_page = 1
                self.logger.info(f"New search ({search_engine}): {query}")

                # 执行搜索
                from ...core.browser.bing import search_bing
                from ...core.browser.google import search_google

                search_fun = search_google if search_engine == "google" else search_bing
                await search_fun(adapter=self.browser, tab=tab, query=query)

            # 提取搜索结果
            from ...core.browser.bing import extract_search_results as extract_bing
            from ...core.browser.google import extract_search_results as extract_google

            extract_fun = extract_google if search_engine == "google" else extract_bing
            raw_results = await extract_fun(self.browser, tab)

            if not raw_results:
                return f'搜索 "{query}" 未找到任何结果。'

            # 检测 visited 状态
            urls = [r["url"] for r in raw_results if r.get("url")]
            visited_map = await detect_visited_links(tab, self.browser, urls)

            # 估算总页数（从页面底部的分页控件获取）
            total_pages = await self._get_total_pages(tab)
            search_number = self._search_state.get(query, 1)

            # 格式化为可读文本
            total_str = f"/共{total_pages}页" if total_pages > 0 else ""
            lines = [
                f'搜索 "{query}" (第{search_number}次, 第{current_page}页{total_str})',
                "",
            ]

            for i, r in enumerate(raw_results, start=1):
                title = r.get("title", "").strip()
                url = r.get("url", "")
                snippet = r.get("snippet", "").strip()
                domain = extract_domain(url)
                visited = visited_map.get(url, False)

                tag = " [已访问]" if visited else ""
                lines.append(f"{i}. {title}{tag}")
                lines.append(f"   {domain}")
                if snippet and snippet != "No description available":
                    lines.append(f"   {snippet}")
                lines.append(f"   {url}")
                lines.append("")

            self.logger.info(
                f"Search returned {len(raw_results)} results (page {current_page})"
            )
            return "\n".join(lines)

        except Exception as e:
            self.logger.error(f"Search failed: {e}")
            return f'搜索 "{query}" 失败: {str(e)[:200]}'

    async def _click_next_page(self, tab) -> bool:
        """点击搜索结果页的"下一页"按钮，成功返回 True，没有下一页返回 False"""
        next_selectors = [
            "css:a.sb_pagN",  # Bing
            'css:a[aria-label="Next page"]',
            'css:a[id="pnnext"]',  # Google
            'css:a[aria-label="下一页"]',
        ]
        for selector in next_selectors:
            try:
                el = tab.ele(selector, timeout=2)
                if el:
                    el.click()
                    time.sleep(2)
                    return True
            except Exception:
                continue
        return False

    async def _get_total_pages(self, tab) -> int:
        """尝试从页面获取总页数"""
        try:
            # Bing: 分页数字
            page_nums = tab.eles("css:a.sb_pag")
            if page_nums:
                nums = []
                for p in page_nums:
                    try:
                        n = int(p.text.strip())
                        nums.append(n)
                    except ValueError:
                        continue
                if nums:
                    return max(nums)

            # Google: 估算（通常10页）
            return 10
        except Exception:
            return -1  # 未知

    # ==========================================
    # Action 2: visit
    # ==========================================

    @register_action(
        short_desc="[url] 访问网页，返回页面内容",
        description="""访问一个网页，返回页面摘要，包含：页面类型、文档结构、内容预览。

同时会缓存页面内容，后续调用 deep_read 时可直接使用（无需重新获取）。

根据摘要判断是否值得深入阅读：
- 如果预览已包含所需信息，可直接使用
- 如果需要更深入的内容，调用 deep_read() 进行详细阅读
- 如果页面类型是导航页或不相关，跳过即可""",
        param_infos={"url": "要访问的网页 URL"},
    )
    async def visit(self, url: str) -> str:
        await self._ensure_browser()
        tab = await self._get_tab()

        self.logger.info(f"Visiting: {url}")

        # 导航
        try:
            await self.browser.navigate(tab, url)
            await self.browser.stabilize(tab)
        except Exception as e:
            self.logger.error(f"Navigation failed for {url}: {e}")
            return f"无法访问 {url}: {str(e)[:200]}"

        final_url = self.browser.get_tab_url(tab)

        # 检查错误页
        page_type = await self.browser.analyze_page_type(tab)
        if page_type == PageType.ERRO_PAGE:
            return f"无法访问 {url}: 页面返回错误（404、超时或连接失败）。"

        # 提取 markdown
        is_pdf = page_type == PageType.STATIC_ASSET
        try:
            markdown = await extract_markdown(tab, self.browser, url)
        except Exception as e:
            self.logger.error(f"Failed to extract markdown: {e}")
            markdown = ""

        # 无法转换
        if not markdown or len(markdown.strip()) < 10:
            # 尝试收集一些辅助信息
            aux_info = []
            try:
                title = tab.title if hasattr(tab, "title") else ""
                if title:
                    aux_info.append(f"标题: {title}")
            except Exception:
                pass
            aux_info.append(f"URL: {final_url}")
            if is_pdf:
                aux_info.append("这是一个PDF文件，无法自动提取文本。")
            else:
                aux_info.append("页面无法转换为可阅读的文本格式。")

            return "页面无法转换为可阅读markdown\n" + "\n".join(aux_info)

        # 缓存 markdown（供 deep_read 使用）
        self._page_cache[final_url] = markdown

        # 分析结构（精简）
        total_chars = len(markdown)

        # 生成预览
        preview = generate_preview(markdown, max_chars=2000)

        # 提取标题（从 markdown 的第一个 h1）
        title = "未命名页面"
        for line in markdown.split("\n"):
            m = re.match(r"^#\s+(.+)$", line)
            if m:
                title = m.group(1).strip()
                break

        # 格式化输出
        label = "PDF文档内容" if is_pdf else "页面主要内容"
        lines = [
            f"{label}: {title}",
            f"共 {total_chars} 字符 | URL: {final_url}",
            "",
            preview,
        ]

        self.logger.info(f"Page: {title} ({total_chars} chars)")
        return "\n".join(lines)

    # ==========================================
    # Action 3: deep_read
    # ==========================================

    @register_action(
        short_desc="[instruction] 深度阅读当前页面提取特定信息",
        description="""对当前浏览器中打开的页面进行深度阅读，流式分批处理，提取特定信息。

使用前提：先用 visit() 获取页面摘要，确认值得深入阅读后再调用此方法。
浏览器必须停留在要阅读的页面上。

instruction 参数要求：明确说明要提取什么，越具体越好。如"提取所有量子比特数量数据"。
如果找到特别有价值但较长的内容，子agent可以用 file skill 保存到文件。""",
        param_infos={"instruction": "要从当前页面提取什么信息，描述越具体越好"},
    )
    async def deep_read(self, instruction: str) -> str:
        from ...agents.micro_agent import MicroAgent

        await self._ensure_browser()
        tab = await self._get_tab()

        url = self.browser.get_tab_url(tab)
        self.logger.info(f"Deep reading: {url}")
        self.logger.info(f"Instruction: {instruction}")

        # 获取 markdown（优先用缓存）
        if url in self._page_cache:
            markdown = self._page_cache[url]
            self.logger.info(f"Using cached markdown ({len(markdown)} chars)")
        else:
            self.logger.info("No cache, extracting markdown...")
            markdown = await extract_markdown(tab, self.browser, url)
            self._page_cache[url] = markdown

        if not markdown or len(markdown.strip()) < 50:
            return "页面内容为空或过短，无法进行深度阅读。"

        # 分析标题
        title = "未命名文档"
        for line in markdown.split("\n"):
            m = re.match(r"^#\s+(.+)$", line)
            if m:
                title = m.group(1).strip()
                break

        # 分批
        chunks = split_into_batches(markdown, threshold=32000)
        total_batches = len(chunks)
        self.logger.info(f"Split into {total_batches} batches")

        # 循环处理每批
        all_notes = []

        for i, batch_text in enumerate(chunks, start=1):
            self.logger.info(f"Processing batch {i}/{total_batches}")

            # 构造子 agent 的 task
            notebook_text = (
                "\n".join(f"- {n}" for n in all_notes)
                if all_notes
                else "(空，尚未收集到笔记)"
            )

            task = f"""你需要阅读以下文章内容，提取与目标相关的信息。

[目标]
{instruction}

[文章信息]
标题: {title}
URL: {url}
当前: 第{i}部分 / 共{total_batches}部分

[已有笔记]
{notebook_text}

[当前内容]
{batch_text}

[可用操作]
- take_note(note): 记录有价值的发现（事实、数据、关键信息）
- provide_final_summary(content): 提供最终总结。调用后阅读结束。
- goto_next_section: 跳到下一个章节继续阅读
- no_need_to_read_further: 没有继续阅读的必要

重要：
- 先用 take_note 积累发现，确认足够后再用 provide_final_summary
- provide_final_summary 是最终答案，内容应包含所有重要发现
- 不要什么都没找到就调用 no_need_to_read_further
- 如果内容与目标完全无关，用 no_need_to_read_further 退出
- 如果内容有价值但当前部分不够，用 goto_next_section 继续
"""

            # 创建并执行子 agent
            sub_agent = MicroAgent(
                parent=self.root_agent,
                name=f"{self.name}_deep_read_{i}",
            )
            sub_agent.notes = []
            sub_agent.answer = None

            try:
                await sub_agent.execute(
                    run_label=f"deep_read_batch_{i}",
                    task=task,
                    persona=getattr(self, "persona", None),
                    available_skills=["deep_reader", "file"],
                    simple_mode=True,
                    exit_actions=[
                        "provide_final_summary",
                        "goto_next_section",
                        "no_need_to_read_further",
                    ],
                    max_steps=10,
                    max_time=5,
                )
            except Exception as e:
                self.logger.error(f"Sub-agent batch {i} failed: {e}")
                continue

            # 收集笔记
            sub_notes = getattr(sub_agent, "notes", [])
            all_notes.extend(sub_notes)

            # 检查退出信号
            action = getattr(sub_agent, "return_action_name", None)
            answer = getattr(sub_agent, "answer", None)

            self.logger.info(f"Batch {i} exit action: {action}")

            if action == "provide_final_summary":
                content = answer or "\n".join(all_notes)
                return self._format_deep_read_result(
                    "answer", content, url, i, total_batches
                )

            elif action == "no_need_to_read_further":
                if all_notes:
                    return self._format_deep_read_result(
                        "skipped",
                        "\n".join(all_notes),
                        url,
                        i,
                        total_batches,
                    )
                else:
                    return self._format_deep_read_result(
                        "skipped",
                        "文章内容与目标无关，无需继续阅读。",
                        url,
                        i,
                        total_batches,
                    )

            # goto_next_section → 继续循环

        # 处理完所有批次
        if all_notes:
            return self._format_deep_read_result(
                "notes", "\n".join(all_notes), url, total_batches, total_batches
            )
        else:
            return self._format_deep_read_result(
                "nothing",
                "已阅读全文，未找到与目标相关的信息。",
                url,
                total_batches,
                total_batches,
            )

    def _format_deep_read_result(
        self, status: str, content: str, url: str, batches_read: int, total_batches: int
    ) -> str:
        """格式化 deep_read 的返回结果"""
        coverage = f"{batches_read}/{total_batches}" if total_batches > 0 else "0/0"

        if status == "answer":
            return f"[深度阅读结果 - 已找到答案]\n来源: {url}\n阅读进度: {coverage}\n\n{content}"
        elif status == "notes":
            return f"[深度阅读结果 - 收集到笔记]\n来源: {url}\n阅读进度: {coverage}\n\n{content}"
        elif status == "skipped":
            return f"[深度阅读结果 - 已放弃]\n来源: {url}\n阅读进度: {coverage}\n原因: {content}"
        else:
            return f"[深度阅读结果 - 未找到相关信息]\n来源: {url}\n阅读进度: {coverage}\n{content}"
