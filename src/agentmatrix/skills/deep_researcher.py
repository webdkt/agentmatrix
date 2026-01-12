import asyncio
import time
import os,json,textwrap
import re
import sqlite3
from typing import List, Set, Dict, Optional, Any, Deque
from collections import deque
from enum import Enum, auto
from dataclasses import dataclass, field
from ..core.browser.google import search_google
from ..core.browser.bing import search_bing

from pathlib import Path


# 引入之前的 Adapter 定义 (假设在 drission_page_adapter 或 browser_adapter 中)
from ..core.browser.browser_adapter import (
    BrowserAdapter, TabHandle, PageElement, InteractionReport, PageSnapshot, PageType
)
# 引入公共数据结构
from ..core.browser.browser_common import TabSession, BaseCrawlerContext
# 引入爬虫辅助方法
from .crawler_helpers import CrawlerHelperMixin
# 引入具体的 Adapter 实现
from ..core.browser.drission_page_adapter import DrissionPageAdapter
from ..core.action import register_action
from .deep_researcher import DeepResearchHelper,ResearchContext
from .utils import sanitize_filename

search_func = search_bing

# ==========================================
# 1. 状态与上下文定义 (State & Context)
# ==========================================

class ContentVerdict(Enum):
    """Phase 3: 页面价值判断结果"""
    TRASH = auto()              # 垃圾/无关/登录墙 -> 关掉或跳过
    RELEVANT_INDEX = auto()     # 索引页/列表页 -> 不值得总结，但值得挖掘链接
    HIGH_VALUE = auto()         # 高价值内容 -> 总结并保存



    def _load_assessed_history(self):
        """从数据库加载已评估历史到内存"""
        # 加载已评估的链接
        cursor = self._db_conn.execute("SELECT url FROM assessed_links")
        self.assessed_links = {row[0] for row in cursor}

        # 加载已评估的按钮
        cursor = self._db_conn.execute("SELECT button_key FROM assessed_buttons")
        self.assessed_buttons = {row[0] for row in cursor}

    def cleanup(self):
        """清理资源，关闭数据库连接"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None


# ==========================================
# 2. 逻辑核心 (Logic Mixin)
# ==========================================

class DeepResearcher(DeepResearchHelper):
    """
    Deep Researcher 核心逻辑
    主流程：目标理解->人设生成（高级研究员，研究导师）->研究计划制定-> 研究循环 -> 写报告循环 

    context: 研究blueprint, 目标内容分类，research task list (completed)
    对每个 reasearch task:
        task 内研究循环：
            - context: bluerpint, 内容结构分类, current task
            - 搜索、浏览、阅读循环
                - 每一次读完：
                    - 要不要更新笔记本和专有名词
                - 如果Page Full （达到threashold）：
                    - Summarize Page
                    - Any new question or update to blueprint?
                    - 如果有，Discuss with 导师 (当前blueprint, current task, new question, draft 0)
                        - 如果讨论有更改必要，这里会比较复杂，要修改已有的研究，需要修改blue / task list， 笔记 and Draft 0 (draft 0是从笔记summarize生成的）
                        - 如果需要修改笔记，是cost比较高的工程，理论上需要每一页都去回溯。因为笔记是客观的记录，不存在修改的需要，只存在要么有用要么没用。所以如果
                        需要改变研究方向或者问题，通常不需要改笔记，要改也是删掉没用的。所以修改已有笔记是剔除无用信息，而不是修改信息。对于每一页，应该：
                            - 删除无用笔记，根据研究blueprint和分类，生成新的page summary（i.e draft 0)
                    - 每一页完成，都思考，current task 要不要继续，不继续就提前返回（报告task 结束）
                
                会不停循环，直到超时返回
            下一次task 内循环会知道：当前task状态：（一轮浏览阅读结束、完成、提前结束），后两者会导致task循环退出。如果是一轮阅读结束，可以读一次本轮的新page 总结，和未总结page，决定是否继续


    研究循环完成后，进入写报告循环
        番茄钟拼接法：对每一个章节：找到所有相关页的Summary，组成章节草稿，然后扩写润色，不要在写的时候查文献，在文档里打三个大大的 XXX 或者 [待查]， 写完了统一回去补数据。
        最后汇总成报告
    """



    
    @register_action(
        "在充分理解用户的需求后，开始进行研究。为这次研究起一个简短的名字，并写清楚研究目的和需求",
        param_infos={
            "research_title":"研究的名字",
            "research_purpose": "研究的具体目的和需求"
        }
    )
    async def start_research(self, research_title, research_purpose):
        
        ctx = ResearchContext(research_title=research_title,research_purpose=research_purpose)
        director_persona, researcher_persona = self._generate_personas(ctx)
        ctx.director_persona = director_persona
        ctx.researcher_persona = researcher_persona


    async def _discuss_research_plan(self, ctx: ResearchContext):
        #生成初步计划
        plan_prompt = self._format_prompt(self.START_PLAN_PROMPT, ctx)
        resp = self.brain.think(plan_prompt)
        self.logger.debug(f"🤖 {resp['reasoning']}")
        plan_draft = resp['reply']
        self.logger.debug(f'{plan_draft}')
        #让导师review计划
        director_review_prompt = self._format_prompt(self.DIRECTOR_REVIEW_PROMPT, ctx, plan_draft = plan_draft)
        resp = self.brain.think(director_review_prompt)
        self.logger.debug(f"🤖 {resp['reasoning']}")
        director_suggestion = resp['reply']
        self.logger.debug(f'{director_suggestion}')
        
        




    



    @register_action(
        "为研究做准备，上网搜索并下载相关资料，要提供研究的目标和搜索关键词",
        param_infos={
            "purpose": "研究的具体目标",
            "search_phrase": "在搜索引擎输入的初始关键词",
            "topic": "保存资料的文件夹名称",
            "max_time": "最大运行时间(分钟)"
        }
    )
    async def research_crawler(self, purpose: str, search_phrase: str, topic: str, max_time: int = 30):
        """
        [Entry Point] 外部调用的入口
        """
        # 1. 准备环境
        save_dir = os.path.join(self.workspace_root, "downloads", sanitize_filename(topic))

        os.makedirs(save_dir, exist_ok=True)

        profile_path = os.path.join(self.workspace_root ,".matrix", "browser_profile", self.name)
        
        self.browser_adapter = DrissionPageAdapter(
            profile_path=profile_path,
            download_path=save_dir
        )
        
        ctx = MissionContext(
            purpose=purpose,
            save_dir=save_dir,
            deadline=time.time() + int(max_time) * 60
        )
        
        self.logger.info(f"🚀 Mission Start: {purpose}")
        
        # 2. 启动浏览器
        await self.browser_adapter.start(headless=False) # 调试模式先开有头
        
        try:
            # 3. 初始阶段：执行搜索 (Phase 0)
            # 我们把搜索结果页当做第一个 Tab 的初始页面
            first_tab = await self.browser_adapter.get_tab()
            
            search_result = await search_func(self.browser_adapter, first_tab, search_phrase)
            # 创建初始 Session
            initial_session = TabSession(handle=first_tab, current_url="")
            # 把搜索页直接推入队列，让 lifecycle 去处理 navigate
            for result in search_result:
                initial_session.pending_link_queue.append(result['url'])

            
            
            
            
            
            
            # 4. 进入递归循环
            await self._run_tab_lifecycle(initial_session, ctx)
            
            # 5. 生成报告
            return self._generate_final_report(ctx)

        except Exception as e:
            self.logger.exception("Crawler crashed")
            return f"Mission failed with error: {e}"
        finally:
            self.logger.info("🛑 Closing browser...")
            await self.browser_adapter.close()
            ctx.cleanup()  # 关闭数据库连接

    async def _run_tab_lifecycle(self, session: TabSession, ctx: MissionContext):
        """
        [The Core Loop] 物理 Tab 的生命周期管理。
        只要队列不空，或者页面上有交互要做，就一直在这转。
        """
        
        while not ctx.is_time_up():
            
            # --- Phase 1: Navigation (从队列取任务) ---
            # 如果当前没有在浏览特定页面，或者当前页面的交互都处理完了（Flag），则从队列取下一个
            if not session.pending_link_queue:
                self.logger.info(f"Tab {session.handle} queue empty. Closing tab.")
                break # 队列空了，结束这个 Tab
                
            next_url = session.pending_link_queue.popleft()
            print(next_url)
            
            # 1.1 门禁检查
            if ctx.has_visited(next_url) or any(bl in next_url for bl in ctx.blacklist):
                continue
            
            self.logger.info(f"🔗 Navigating to: {next_url}")
            nav_report = await self.browser_adapter.navigate(session.handle, next_url)
            final_url =  self.browser_adapter.get_tab_url(session.handle)
            session.current_url = final_url # 更新当前

            # 1.2 标记已访问    
            ctx.mark_visited(next_url)
            ctx.mark_visited(final_url)
            self.logger.info(f"🔗 Landed on: {final_url}")
            # 2. 二次黑名单检查 (防止跳转到 Facebook/Login 页)
            if any(bl in final_url for bl in ctx.blacklist):
                self.logger.warning(f"🚫 Redirected to blacklisted URL: {final_url}. Aborting tab.")
                # 这种情况下，直接 break 还是 continue?
                # 这是一个 Dead End，所以应该结束当前页面的处理，去处理队列里的下一个
                continue 

            # === Phase 2: Identify Logic Branch ===
            # 先稳一手，不用全页面 stabilize，只要能拿到 contentType 就行
            page_type = await self.browser_adapter.analyze_page_type(session.handle)

            if page_type == PageType.ERRO_PAGE:
                self.logger.warning(f"🚫 Error Page: {final_url}. Skipping.")
                continue

            # === 分支 A: 静态资源 (Dead End) ===
            if page_type == PageType.STATIC_ASSET:
                self.logger.info(f"📄 Detected Static Asset: {session.current_url}")
                
                # 1. 尝试获取内容 (Snapshot)
                #    对于 PDF，如果浏览器能提取文字最好，提取不到就拿文件名和 URL 做摘要
                snapshot = await self.browser_adapter.get_page_snapshot(session.handle)
                
                # 2. 小脑判断 (Assess)
                #    "这是一个 PDF，标题是 xxx，前 500 字是 xxx... 值得存吗？"
                #    注意：对于无法提取文字的 Image/PDF，只能让小脑根据 URL/Title 盲猜
                verdict_dict = await self._assess_page_value(snapshot, ctx)
                verdict = verdict_dict["verdict"]
                
                if verdict == ContentVerdict.HIGH_VALUE:
                    self.logger.info("💾 Saving Asset...")
                    # 保存文件
                    await self.browser_adapter.save_static_asset(session.handle)
                    # 记录到 Context
                    ctx.knowledge_base.append({"type": "file", "url": session.current_url, "title": snapshot.title})
                
                # 3. 结束当前 URL 的处理
                #    因为是 Static Asset，没有交互，没有 scout，直接 break (如果是单页) 或 continue (如果还要处理队列)
                #    但在我们的逻辑里，Asset 是终点，处理完就可以从 Queue 取下一个了
                #    不需要 break Loop (Loop 是处理 Queue 的)，而是 continue Outer Loop
                continue 


            # === 分支 B: 交互式网页 (Infinite Possibilities) ===
            elif page_type == PageType.NAVIGABLE:
                
                # 进入我们之前的复杂循环：Stabilize -> Assess -> Scout -> Act
                # 这里就是原来的 Inner Loop 代码
                self.logger.debug("🌐 Detected Navigable Page. Entering complex loop.")
                page_active = True
                page_changed = True
                one_line_summary=""
                while page_active and not ctx.is_time_up():
                    # 1. Stabilize (滚动加载)
                    
                    
                    if page_changed: 
                        #第一次永远是page_changed，但如果点过一个button没什么变化，从头再来一次，就是False了
                        #这时候不需要再去stablize,也不用再看assess了，直接看scout
                        await self.browser_adapter.stabilize(session.handle)
                        # 2. Assess (HTML Extract -> Brain)
                        snapshot = await self.browser_adapter.get_page_snapshot(session.handle)
                        verdict_dict = await self._assess_page_value(snapshot, ctx)
                        verdict = verdict_dict["verdict"]
                        one_line_summary = verdict_dict["reason"]
                        
                        if verdict == ContentVerdict.HIGH_VALUE:
                            await self._save_content(snapshot, ctx) # 保存 Summary
                        elif verdict == ContentVerdict.TRASH:
                            page_active = False; 
                            continue

                    # === Phase 4: Scouting (Look) ===
                    # 扫描所有元素
                    links, buttons = await self.browser_adapter.scan_elements(session.handle)
                    #links的格式：{url: text}
                    #buttons的格式：{text: button_element}
                    self.logger.debug(f"🔍 Found {len(links)} links and {len(buttons)} buttons.")



                    # 4.1 处理 Links -> 入队 (不立即访问)
                    # 如果page_changed = False，这个可以跳过了

                    if page_changed:
                        filtered_links = {}
                        for link in links:

                            # 过滤掉已评估过的链接（避免重复调用 LLM）
                            if ctx.has_link_assessed(link):
                                continue
                            #先判断这个link是否已经访问过，或者是否在黑名单中，以及是不是已经在pending_link_queue里
                            if ctx.has_visited(link):
                                continue
                            if link in session.pending_link_queue:
                                continue
                            if any(bl in link for bl in ctx.blacklist):
                                continue
                            
                            
                            filtered_links[link] = links[link]

                        selected_links = await self._filter_relevant_links(filtered_links,one_line_summary, ctx)

                        # 记录所有评估过的链接（无论是否被选中）
                        for link in filtered_links:
                            ctx.mark_link_assessed(link)

                        new_links_count = 0
                        for link in selected_links:

                            session.pending_link_queue.append(link)
                            new_links_count += 1
                        self.logger.info(f"👀 Scouted {new_links_count} relevant links (enqueued).")

                    # 4.2 处理 Buttons -> 候选列表
                    candidate_buttons=[]
                    #只保留没评估过的按钮
                    for button_text in buttons:
                        # 过滤掉已评估过的按钮
                        if not ctx.has_button_assessed(session.current_url, button_text):
                            candidate_buttons.append({
                                button_text: buttons[button_text]
                            })
                

                    
                    # === Phase 5: Execution (Act) ===
                    # 尝试点击最有价值的按钮
                    # 如果小脑决定不点任何按钮，或者没按钮可点，Inner Loop 结束
                    if not candidate_buttons:
                        self.logger.info("🤔 No worthy interactions found. Moving to next page in queue.")
                        page_active = False # 结束当前页
                        continue

                    chosen_button = await self._choose_best_interaction(candidate_buttons,one_line_summary, ctx)

                    # 记录所有评估过的按钮（无论是否被选中）
                    assessed_button_texts = [list(btn.keys())[0] for btn in candidate_buttons]
                    ctx.mark_buttons_assessed(session.current_url, assessed_button_texts)

                    if not chosen_button:
                        self.logger.info("🤔 No worthy interactions found. Moving to next page in queue.")
                        page_active = False # 结束当前页
                        continue
                    
                    # 执行点击
                    self.logger.info(f"point_up: Clicking button: [{chosen_button.get_text()}]")
                    ctx.mark_interacted(session.current_url, chosen_button.get_text())
                    
                    report = await self.browser_adapter.click_and_observe(session.handle, chosen_button)
                    
                    # 5.1 处理后果: 新 Tab
                    if report.new_tabs:
                        self.logger.info(f"✨ New Tab(s) detected: {len(report.new_tabs)}")
                        for new_tab_handle in report.new_tabs:
                            # 递归！创建新的 Session
                            new_session = TabSession(handle=new_tab_handle, current_url="", depth=session.depth + 1)
                            # 等待递归返回
                            await self._run_tab_lifecycle(new_session, ctx)
                            # 递归回来后，关闭那个 tab (通常 lifecycle 结束时会自杀，这里可以做个保险)
                            await self.browser_adapter.close_tab(new_tab_handle)
                    
                    # 5.2 处理后果: 页面变动 (Soft Restart)
                    if report.is_dom_changed or report.is_url_changed:
                        self.logger.info("🔄 Page mutated. Triggering Soft Restart (Re-assess).")
                        # 不设置 page_active = False，而是直接 continue Inner Loop
                        # 这会导致重新 Stabilize -> Assess -> Scout
                        # 注意更新 URL
                        page_changed = True
                        if report.is_url_changed:
                            session.current_url =  self.browser_adapter.get_tab_url(session.handle) # 获取最新 URL
                        continue 

                    # 5.3 处理后果: 无事发生或仅下载
                    # 如果没变动，也没弹窗，我们假设这个按钮点完了。
                    # 继续 Inner Loop 的下一次迭代？不，因为 DOM 没变，candidate_buttons 也没变。
                    # 我们应该继续从 candidate_buttons 里选下一个吗？
                    # 为了简单起见，如果点了一个按钮没反应，我们就认为“这页没啥好点的了”，或者让小脑在下一轮重新选（反正已经 mark interacted 了）
                    # 这里选择：继续循环，让 Assess/Scout 再跑一遍（成本不高），确保万无一失
                    page_changed = False
                    continue

            
            # End Inner Loop
        
        # End Outer Loop (Queue Empty or Time Up)
        self.logger.info(f"🏁 Tab Session ended. visited: {len(ctx.visited_urls)}")
        # 这里的 close_tab 交给调用方处理，或者 adapter.close_tab(session.handle)


    # ==========================================
    # 3. 小脑决策辅助 (Brain Power)
    # ==========================================

    async def _assess_page_value(self, snapshot: PageSnapshot, ctx: MissionContext):
        """
        [Brain] 评估页面价值。
        输入：页面快照 (URL, Title, Text Preview)
        输出：ContentVerdict (TRASH | RELEVANT_INDEX | HIGH_VALUE)
        """
        
        # 1. 极简启发式过滤 (Heuristics)
        # 如果是 NAVIGABLE 类型，且内容极短 (例如 < 50 字符)，
        # 往往是脚本没加载出来，或者确实是空页。
        # 为了防止漏掉只有图片的页面，我们稍微宽容一点，交给 LLM，
        # 但如果连 Title 都是空的，直接扔掉。
        if not snapshot.title and len(snapshot.main_text) < 10:
            self.logger.warning(f"🗑️ Empty title and content: {snapshot.url}")
            return {"verdict":ContentVerdict.TRASH, "reason":"Empty title and content"}

        # 2. 构造 Prompt
        # 截断文本，避免 Token 溢出。2000字通常足够判断价值。
        # 如果是文件，main_text 可能是空的或者只有元数据，没关系。
        preview_text = snapshot.main_text[:2500]
        
        # 针对静态资源和普通网页使用略微不同的 Prompt 侧重
        if snapshot.content_type == PageType.STATIC_ASSET:
            evaluation_guide = textwrap.dedent("""
            Type: STATIC FILE (PDF/Image/Doc).
            Task: Decide if this file is relevant to [Research Goal] and should be DOWNLOADED based on its Title and URL.
            Allowed Verdict Value:
            - TRASH: Completely unrelated.
            - HIGH_VALUE: The file seems relevant to the Research Goal (e.g., specific data, report, paper) or not enough information to judge. (Download anyway.)
            
            (Note: Use HIGH_VALUE if you are not sure.)
            """)
        else:
            evaluation_guide = textwrap.dedent("""
            Type: WEBPAGE.
            Task: Analyze content relevance.
            Allowed Verdict Value:
            - TRASH: 
                * Login/Signup walls, Captchas.
                * 404/Errors, "Site under construction".
                * Pure SEO spam, generic ads, "Buy now" product pages (unless research goal is shopping).
                * Completely off-topic content.
            - RELEVANT_INDEX: 
                * Hub pages, Directories, List of links (e.g., "Top 10 resources").
                * Content is relevant but short/shallow (not worth summarizing, but worth exploring links).
                * If unsure or info is sparse but looks relevant -> Choose THIS.
            - HIGH_VALUE: 
                * Detailed articles, Reports, Data tables, Technical documentation.
                * Directly answers the Research Goal with substance.
            """)

        prompt = textwrap.dedent(f"""
        You are a Research Assistant.
        
        [Research Goal]
        "{ctx.purpose}"

        [Target Info]
        URL: {snapshot.url}
        Title: {snapshot.title}

        [Evaluation Guide]
        {evaluation_guide}

        [Content Preview]
        {preview_text}
        

        [Output Requirement]
        Return JSON ONLY. Format: {{"verdict": "one of allowed verdict values", "reason": "One line summary about the page"}}
        """)

        # 3. 调用小脑
        try:
            # 假设 self.cerebellum.think 返回 dict: {'reply': '...', 'reasoning': '...'}
            # 这里的 messages 格式取决于你的底层 LLM 接口，这里按常见格式写
            response = await self.cerebellum.backend.think(
                messages=[{"role": "user", "content": prompt}]
            )
            raw_reasoning = response.get('reasoning', '').strip()
            raw_reply = response.get('reply', '').strip()
            #self.logger.debug(f"🧠 Brain Reply: {raw_reply} \n\n Reasoning: {raw_reasoning}")
            
            # 4. 解析结果
            # 简单的 JSON 清洗（防止 LLM 加 markdown code block）
            json_str = raw_reply.replace("```json", "").replace("```", "").strip()
            result = json.loads(json_str)
            
            verdict_str = result.get("verdict", "RELEVANT_INDEX").upper()
            reason = result.get("reason", "No reason provided")
            
            self.logger.info(f"🧠 Brain Assess [{verdict_str}]: {snapshot.title[:30]}... | Reason: {reason}")

            if verdict_str == "HIGH_VALUE":
                return {"verdict": ContentVerdict.HIGH_VALUE, "reason": reason}
            elif verdict_str == "TRASH":
                return {"verdict": ContentVerdict.TRASH, "reason": reason}
            else:
                return {"verdict": ContentVerdict.RELEVANT_INDEX, "reason": snapshot.main_text[:800]}

        except Exception as e:
            self.logger.error(f"🧠 Brain Assessment Failed: {e}. Defaulting to RELEVANT_INDEX.")
            # 发生异常（如 JSON 解析失败、网络超时）时，
            # 遵循“默认宽容原则”，只要不是静态资源，就当作 INDEX 继续探索，避免漏掉。
            if snapshot.content_type == PageType.STATIC_ASSET:
                # 文件如果判断不出，通常为了保险起见，可以设为 TRASH 或者 HIGH_VALUE
                # 这里为了防止下垃圾文件，设为 TRASH (或者你可以改为 HIGH_VALUE)
                return {"verdict": ContentVerdict.HIGH_VALUE, "reason": "Static Asset"}
            return {"verdict": ContentVerdict.TRASH, "reason": "Possible related info"}

    async def _save_content(self, snapshot: PageSnapshot, ctx: MissionContext):
        """
        [Action] 保存内容到文件系统。
        策略：
        1. 短文 (< 1k chars): 直接存原文，不总结。
        2. 中文 (1k - 15k chars): 小脑进行深度总结 (Deep Summary)。
        3. 长文 (> 15k chars): 生成简介 (Abstract) + 附上全文。
        """
        
        # === 1. 文件名生成策略 ===
        # 使用 slugify 保证文件名安全，截断防止过长
        safe_title = sanitize_filename(snapshot.title,60)
        # 加个时间戳防止重名覆盖 (比如两个页面标题一样)
        timestamp_suffix = str(int(time.time()))[-4:] 
        filename = f"{safe_title}_{timestamp_suffix}.md"
        save_path = os.path.join(ctx.save_dir, filename)

        text_len = len(snapshot.main_text)
        final_content = ""
        summary_type = ""

        # === 2. 分级处理 ===

        # --- Tier A: 短文 (直接保存) ---
        if text_len < 1000:
            self.logger.info(f"💾 Saving Short Content ({text_len} chars): {filename}")
            summary_type = "Raw (Short)"
            final_content = self._format_markdown(snapshot, "No summary generated (Content too short).", snapshot.main_text)

        # --- Tier B: 中篇 (深度总结) ---
        elif text_len < 15000:
            self.logger.info(f"📝 Summarizing Medium Content ({text_len} chars)...")
            summary_type = "AI Summary"
            
            summary = await self._generate_summary(snapshot.main_text, ctx.purpose, mode="deep")
            final_content = self._format_markdown(snapshot, summary, snapshot.main_text)

        # --- Tier C: 长篇 (简介 + 原文) ---
        else:
            self.logger.info(f"📚 Archiving Long Content ({text_len} chars)...")
            summary_type = "Abstract + Full Text"
            
            # 策略：取前 5000 字（包含介绍）和后 2000 字（包含结论），跳过中间细节
            # 这样小脑能读懂大概在讲什么，而不会被中间的细节淹没
            partial_text = snapshot.main_text[:5000] + "\n\n...[Middle section omitted for summarization]...\n\n" + snapshot.main_text[-2000:]
            
            abstract = await self._generate_summary(partial_text, ctx.purpose, mode="abstract")
            
            note = f"**Note**: Document is very long ({text_len} chars). Below is an AI generated abstract based on intro/outro, followed by the full raw text."
            final_content = self._format_markdown(snapshot, f"{note}\n\n{abstract}", snapshot.main_text)

        # === 3. 写入文件 ===
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(final_content)
            
            # === 4. 更新知识库索引 ===
            # 这是给 Brain 最后看的 Manifest
            ctx.knowledge_base.append({
                "type": "page",
                "title": snapshot.title,
                "url": snapshot.url,
                "file_path": filename, # 相对路径
                "summary_type": summary_type,
                "size_kb": round(text_len / 1024, 1)
            })
            
        except Exception as e:
            self.logger.error(f"Failed to write file {save_path}: {e}")

    # --- 辅助函数 ---

    def _format_markdown(self, snapshot: PageSnapshot, summary_part: str, raw_part: str) -> str:
        """
        统一的 Markdown 文件格式
        """
        return textwrap.dedent(f"""
        # {snapshot.title}
        
        > Source: {snapshot.url}
        > Captured: {time.strftime("%Y-%m-%d %H:%M:%S")}
        
        ## 🤖 AI Summary / Notes
        {summary_part}
        
        ---
        
        ## 📄 Original Content
        {raw_part}
        """).strip()

    async def _generate_summary(self, text: str, purpose: str, mode: str = "deep") -> str:
        """
        调用小脑生成总结
        """
        if mode == "deep":
            task_desc = "Create a detailed structured summary (Markdown). Focus on facts, data, and answers relevant to the Research Goal."
        else:
            task_desc = "Create a brief Abstract/Overview (1-2 paragraphs). Explain what this document is about and its potential value."

        prompt = f"""
        You are a Research Assistant.
        Research Goal: "{purpose}"
        
        Task: {task_desc}
        
        Content:
        {text}
        
        Output Markdown only.
        """
        
        try:
            resp = await self.cerebellum.backend.think(messages=[{"role": "user", "content": prompt}])
            return resp.get('reply', '').strip()
        except Exception:
            return "[Error: AI Summary Generation Failed]"

    import re

    def _generate_final_report(self, ctx: MissionContext) -> str:
        return f"Mission Complete. Found {len(ctx.knowledge_base)} items."