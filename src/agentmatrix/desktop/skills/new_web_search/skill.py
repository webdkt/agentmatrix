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

from agentmatrix.core.action import register_action
from agentmatrix.desktop.browser.browser_adapter import PageType
from agentmatrix.desktop.browser.drission_page_adapter import DrissionPageAdapter
from agentmatrix.desktop.browser.browser_common import TabSession
from agentmatrix.core.exceptions import LLMServiceConnectionError
from agentmatrix.core.utils.token_utils import estimate_tokens

from .utils import detect_visited_links, extract_domain
from .page_processor import (
    extract_markdown,
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

    _skill_description = "网络搜索：搜索、访问页面、提取信息"

    def _ns(self):
        """获取本 skill 在 skill_context 中的名字空间"""
        if "new_web_search" not in self.skill_context:
            self.skill_context["new_web_search"] = {
                "browser": None,
                "tab": None,
                "search_state": {},
                "page_cache": {},
                "last_search_query": None,
                "link_map": {},
                "link_map_need_clear": True,
                "browser_lock": asyncio.Lock(),
            }
        return self.skill_context["new_web_search"]

    # ==========================================
    # 浏览器初始化
    # ==========================================

    async def _ensure_browser(self):
        """懒初始化浏览器标签页（浏览器由 BaseAgent 管理）"""
        ns = self._ns()
        if ns.get("tab") is not None:
            return

        # 从 BaseAgent 获取共享浏览器（懒启动）
        await self.root_agent.ensure_browser_started()
        browser = self.root_agent.get_browser()

        # 创建本 MicroAgent 专属的 tab
        tab = await browser.create_tab()

        ns["browser"] = browser
        ns["tab"] = tab
        self.logger.info("Browser tab created")

    async def _get_tab(self):
        """获取本 MicroAgent 的浏览器标签页"""
        await self._ensure_browser()
        return self._ns()["tab"]

    async def skill_cleanup(self):
        """关闭本 MicroAgent 创建的 tab"""
        ns = self._ns()
        tab = ns.pop("tab", None)
        browser = ns.get("browser")
        if tab and browser:
            try:
                await browser.close_tab(tab)
                self.logger.info("Browser tab closed")
            except Exception as e:
                self.logger.warning(f"Failed to close tab: {e}")
        ns["browser"] = None

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
        ns = self._ns()

        async with ns["browser_lock"]:
            try:
                # 判断是否翻页
                is_next_page = (
                    ns["last_search_query"] == query and query in ns["search_state"]
                )

                if is_next_page:
                    # 翻页：点击"下一页"
                    self.logger.info(f"Trying next page for: {query}")

                    has_next = await self._click_next_page(tab)
                    if not has_next:
                        return f'搜索 "{query}" 没有下一页了（已到末尾）。'

                    ns["search_state"][query] += 1
                    current_page = ns["search_state"][query]
                    self.logger.info(f"Search page {current_page} for: {query}")
                    await ns["browser"].stabilize(tab)
                else:
                    # 新搜索
                    ns["search_state"][query] = 1
                    ns["last_search_query"] = query
                    current_page = 1
                    self.logger.info(f"New search ({search_engine}): {query}")

                    # 执行搜索
                    from agentmatrix.desktop.browser.bing import search_bing
                    from agentmatrix.desktop.browser.google import search_google

                    search_fun = search_google if search_engine == "google" else search_bing
                    await search_fun(adapter=ns["browser"], tab=tab, query=query)

                # 检查搜索页面是否加载成功
                page_type = await ns["browser"].analyze_page_type(tab)
                if page_type == PageType.ERRO_PAGE:
                    other = (
                        "search_with_bing"
                        if search_engine == "google"
                        else "search_with_google"
                    )
                    engine_name = "Google" if search_engine == "google" else "Bing"
                    return f'{engine_name} 无法访问（页面加载失败或网络不通）。建议尝试 {other}("{query}")。'

                # 提取搜索结果
                from agentmatrix.desktop.browser.bing import extract_search_results as extract_bing
                from agentmatrix.desktop.browser.google import extract_search_results as extract_google

                extract_fun = extract_google if search_engine == "google" else extract_bing
                raw_results = await extract_fun(ns["browser"], tab)

                if not raw_results:
                    return f'搜索 "{query}" 未找到任何结果。'

                # 提取 Bing AI 知识卡片（如有）
                knowledge_card = None
                if search_engine == "bing":
                    from agentmatrix.desktop.browser.bing import extract_knowledge_card

                    knowledge_card = await extract_knowledge_card(tab)

                # 检测 visited 状态
                urls = [r["url"] for r in raw_results if r.get("url")]
                visited_map = await detect_visited_links(tab, ns["browser"], urls)

                # 建立 link_to_resultN → 实际 URL 的映射
                # begin: 如果上一轮 visit 已经"结束"，清空 link_map
                if ns.get("link_map_need_clear", True):
                    ns["link_map"] = {}
                    ns["link_map_need_clear"] = False

                existing = ns["link_map"]
                offset = len(existing)
                for i, r in enumerate(raw_results, start=1):
                    existing[f"link_to_result{i + offset}"] = r.get("url", "")

                # 估算总页数（从页面底部的分页控件获取）
                total_pages = await self._get_total_pages(tab)
                search_number = ns["search_state"].get(query, 1)

                # 格式化为可读文本
                total_str = f"/共{total_pages}页" if total_pages > 0 else ""
                lines = [
                    f'搜索 "{query}" (第{search_number}次, 第{current_page}页{total_str})',
                    "",
                ]

                # 如果有知识卡片，放在结果前面
                if knowledge_card:
                    lines.append("[AI知识卡片]")
                    lines.append(knowledge_card)
                    lines.append("")
                    lines.append("---")
                    lines.append("")

                for i, r in enumerate(raw_results, start=1):
                    title = r.get("title", "").strip()
                    url = r.get("url", "")
                    snippet = r.get("snippet", "").strip()
                    domain = r.get("domain", "") or extract_domain(url)
                    visited = visited_map.get(url, False)

                    tag = " [已访问]" if visited else ""
                    lines.append(f"{i + offset}. {title}{tag}")
                    lines.append(f"   {domain}")
                    if snippet and snippet != "No description available":
                        lines.append(f"   {snippet}")
                    lines.append(f"   link_to_result{i + offset}")
                    lines.append("")

                self.logger.info(
                    f"Search returned {len(raw_results)} results (page {current_page})"
                )
                return "\n".join(lines)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                err = str(e)
                self.logger.error(f"Search ({search_engine}) failed: {err}")

                # 提供有用的错误提示
                if (
                    "search box" in err
                    or "navigate" in err.lower()
                    or "timeout" in err.lower()
                ):
                    hint = f"无法访问 {search_engine.capitalize()}，可能是网络问题或页面未加载。"

                    return f"搜索失败: {hint}"
                return f'搜索 "{query}" 失败: {err[:200]}'

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
                el = await asyncio.to_thread(tab.ele, selector, timeout=2)
                if el:
                    await asyncio.to_thread(el.click)
                    await asyncio.sleep(2)
                    return True
            except Exception:
                continue
        return False

    async def _get_total_pages(self, tab) -> int:
        """尝试从页面获取总页数"""
        try:
            # Bing: 分页数字
            page_nums = await asyncio.to_thread(tab.eles, "css:a.sb_pag")
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
        short_desc="[url] 打开网页（支持 link_to_resultN 或完整 URL）",
        description="""访问一个网页，返回页面内容摘要。

接受两种参数：
- 搜索结果中的引用：如 link_to_result1、link_to_result2（来自搜索结果）
- 完整 URL：如 https://nature.com/articles/...

返回摘要后判断：
- 如果预览已包含所需信息，可直接使用
- 如果需要更深入的内容，调用 deep_read() 进行详细阅读
- 如果页面不相关，跳过即可""",
        param_infos={"url": "网页 URL 或搜索结果引用（link_to_resultN）"},
    )
    async def open_url(self, url: str) -> str:
        # 解析 link_to_resultN 引用
        if url.startswith("link_to_result"):
            ns = self._ns()
            link_map = ns.get("link_map", {})
            actual_url = link_map.get(url)
            if not actual_url:
                return f"未知的链接引用: {url}。请先搜索，然后使用搜索结果中的 link_to_resultN。"
            self.logger.info(f"Resolved {url} -> {actual_url[:80]}...")
            url = actual_url
            # end: 标记下次新 search 应清空 link_map
            ns["link_map_need_clear"] = True

        await self._ensure_browser()
        tab = await self._get_tab()
        ns = self._ns()

        async with ns["browser_lock"]:
            self.logger.info(f"Visiting: {url}")

            # 导航
            try:
                await ns["browser"].navigate(tab, url)
                await ns["browser"].stabilize(tab)
            except Exception as e:
                self.logger.error(f"Navigation failed for {url}: {e}")
                return f"无法访问 {url}: {str(e)[:200]}"

            final_url = ns["browser"].get_tab_url(tab)

            # 检查错误页
            page_type = await ns["browser"].analyze_page_type(tab)
            if page_type == PageType.ERRO_PAGE:
                return f"无法访问 {url}: 页面返回错误（404、超时或连接失败）。"

            # 提取 markdown
            is_pdf = page_type == PageType.STATIC_ASSET
            try:
                # 构造 PDF 下载目录：基于 agent 的 work_files/task_id/downloads
                pdf_save_dir = None
                if is_pdf and self.current_task_id and hasattr(self, "runtime"):
                    pdf_save_dir = str(
                        self.runtime.paths.get_agent_work_files_dir(
                            self.name, self.current_task_id
                        )
                        / "downloads"
                    )
                markdown = await extract_markdown(
                    tab, ns["browser"], url, save_dir=pdf_save_dir
                )
            except Exception as e:
                self.logger.error(f"Failed to extract markdown: {e}")
                markdown = ""

            # 无法转换
            if not markdown or len(markdown.strip()) < 10:
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
            ns["page_cache"][final_url] = markdown

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
        short_desc="[instruction] 启用阅读Agent阅读当前打开的页面并提取信息，Agent不了解前因后果，需要对Agent提供明确的指引和要求，以及你期望得到的内容包括格式",
        description="""对当前浏览器中打开的页面进行深度阅读，流式分批处理，提取特定信息。

使用前提：先用 visit() 获取页面摘要，确认值得深入阅读后再调用此方法。
浏览器必须停留在要阅读的页面上。

instruction 参数要求：明确说明要提取什么，越具体越好。如"提取所有量子比特数量数据"。
如果找到特别有价值但较长的内容，子agent可以用 file skill 保存到文件。""",
        param_infos={"instruction": "要从当前页面提取什么信息，描述越具体越好"},
    )
    async def read_current_page(self, instruction: str) -> str:
        from agentmatrix.core.micro_agent import MicroAgent

        await self._ensure_browser()
        tab = await self._get_tab()
        ns = self._ns()

        async with ns["browser_lock"]:
            url = ns["browser"].get_tab_url(tab)
            self.logger.info(f"Deep reading: {url}")
            self.logger.info(f"Instruction: {instruction}")

            # 获取 markdown（优先用缓存）
            if url in ns["page_cache"]:
                markdown = ns["page_cache"][url]
                self.logger.info(f"Using cached markdown ({len(markdown)} chars)")
            else:
                self.logger.info("No cache, extracting markdown...")
                pdf_save_dir = None
                if self.current_task_id and hasattr(self, "runtime"):
                    pdf_save_dir = str(
                        self.runtime.paths.get_agent_work_files_dir(
                            self.name, self.current_task_id
                        )
                        / "downloads"
                    )
                markdown = await extract_markdown(
                    tab, ns["browser"], url, save_dir=pdf_save_dir
                )
                ns["page_cache"][url] = markdown

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

                task = f"""你需要按照要求阅读以下网页内容，并按要求查找记录信息或总结。阅读的时候带着思考：
                1. 本次阅读的目的是什么
                2. 阅读的内容和目的相关吗？
                3. 需要留意和记录的是什么

[要求]
{instruction}

[网页信息]
标题: {title}
URL: {url}
当前: 第{i}部分 / 共{total_batches}部分

[已有笔记]
{notebook_text}

[当前阅读内容]
{batch_text}


重要：
- 对于值得记录的信息，用 take_note 积累发现
- provide_final_summary 是最终答案，内容应包含所有重要发现，调用这个action表明阅读目的已经达到
- 读完本页如果不能提供最终答案，思考决定选择：
    - 如果估计后面的内容与目标完全无关，用 no_need_to_read_further 退出
    - 如果后面还值得探索，用 goto_next_section 继续
"""

                # 创建并执行子 agent
                sub_agent = MicroAgent(
                    parent=self.root_agent,
                    name=f"{self.name}_deep_read_{i}",
                    available_skills=["new_web_search.deep_reader", "file"],
                )
                sub_agent.notes = []
                sub_agent.answer = None

                try:
                    await sub_agent.execute(
                        run_label=f"deep_read_batch_{i}",
                        task=task,
                        persona=getattr(self, "persona", None),
                        simple_mode=True,
                        exit_actions=[
                            "provide_final_summary",
                            "goto_next_section",
                            "no_need_to_read_further",
                        ],
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
