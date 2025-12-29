import asyncio
import time
import os,json,textwrap
import re
import sqlite3
from typing import List, Set, Dict, Optional, Any, Deque
from collections import deque
from enum import Enum, auto
from dataclasses import dataclass, field
from core.browser.google import search_google
from core.browser.bing import search_bing

# 引入之前的 Adapter 定义 (假设在 drission_page_adapter 或 browser_adapter 中)
from core.browser.browser_adapter import (
    BrowserAdapter, TabHandle, PageElement, InteractionReport, PageSnapshot, PageType
)
# 引入具体的 Adapter 实现
from core.browser.drission_page_adapter import DrissionPageAdapter
from core.action import register_action
from slugify import slugify

search_func = search_google

# ==========================================
# 1. 状态与上下文定义 (State & Context)
# ==========================================

class ContentVerdict(Enum):
    """Phase 3: 页面价值判断结果"""
    TRASH = auto()              # 垃圾/无关/登录墙 -> 关掉或跳过
    RELEVANT_INDEX = auto()     # 索引页/列表页 -> 不值得总结，但值得挖掘链接
    HIGH_VALUE = auto()         # 高价值内容 -> 总结并保存

@dataclass
class MissionContext:
    """
    全局任务上下文 (Global Memory)
    跨越所有递归层级共享的数据。
    """
    purpose: str
    save_dir: str
    deadline: float

    # 历史记录 (去重用)
    visited_urls: Set[str] = field(default_factory=set)
    interaction_history: Set[str] = field(default_factory=set) # "URL|ButtonText"

    # 已评估过的链接和按钮（避免重复调用 LLM）
    assessed_links: Set[str] = field(default_factory=set)
    assessed_buttons: Set[str] = field(default_factory=set)  # "URL|ButtonText"

    # 成果库
    knowledge_base: List[Dict] = field(default_factory=list)

    # 黑名单 (不可配置的硬规则)
    blacklist: Set[str] = field(default_factory=lambda: {
        "facebook.com", "twitter.com", "instagram.com", "taobao.com",
        "jd.com", "amazon.com", "signin", "login", "signup"
    })

    # SQLite 数据库连接
    _db_conn: Optional[sqlite3.Connection] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """初始化后自动调用，设置 SQLite 数据库"""
        self._init_database()
        self._load_assessed_history()

    def _init_database(self):
        """初始化 SQLite 数据库"""
        db_path = os.path.join(self.save_dir, ".crawler_assessment.db")
        self._db_conn = sqlite3.connect(db_path)
        self._db_conn.execute("PRAGMA journal_mode=WAL")  # 提升并发性能

        # 创建表
        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS assessed_links (
                url TEXT PRIMARY KEY,
                assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._db_conn.execute("""
            CREATE TABLE IF NOT EXISTS assessed_buttons (
                button_key TEXT PRIMARY KEY,
                assessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self._db_conn.commit()

    def _load_assessed_history(self):
        """从数据库加载已评估历史到内存"""
        # 加载已评估的链接
        cursor = self._db_conn.execute("SELECT url FROM assessed_links")
        self.assessed_links = {row[0] for row in cursor}

        # 加载已评估的按钮
        cursor = self._db_conn.execute("SELECT button_key FROM assessed_buttons")
        self.assessed_buttons = {row[0] for row in cursor}

    def is_time_up(self) -> bool:
        return time.time() > self.deadline

    def mark_visited(self, url: str):
        self.visited_urls.add(url)

    def has_visited(self, url: str) -> bool:
        # 简单去除末尾斜杠和参数进行比较可能更稳健，这里先做精确匹配
        return url in self.visited_urls

    def mark_interacted(self, url: str, button_text: str):
        key = f"{url}|{button_text}"
        self.interaction_history.add(key)

    def has_interacted(self, url: str, button_text: str) -> bool:
        key = f"{url}|{button_text}"
        return key in self.interaction_history

    def mark_link_assessed(self, url: str):
        """标记链接为已评估"""
        if url not in self.assessed_links:
            self.assessed_links.add(url)
            self._db_conn.execute(
                "INSERT OR IGNORE INTO assessed_links (url) VALUES (?)",
                (url,)
            )
            self._db_conn.commit()

    def has_link_assessed(self, url: str) -> bool:
        """检查链接是否已评估过"""
        return url in self.assessed_links

    def mark_buttons_assessed(self, url: str, button_texts: List[str]):
        """批量标记按钮为已评估"""
        timestamp = time.time()
        for button_text in button_texts:
            key = f"{url}|{button_text}"
            if key not in self.assessed_buttons:
                self.assessed_buttons.add(key)
                self._db_conn.execute(
                    "INSERT OR IGNORE INTO assessed_buttons (button_key) VALUES (?)",
                    (key,)
                )
        self._db_conn.commit()

    def has_button_assessed(self, url: str, button_text: str) -> bool:
        """检查按钮是否已评估过"""
        key = f"{url}|{button_text}"
        return key in self.assessed_buttons

    def cleanup(self):
        """清理资源，关闭数据库连接"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None


@dataclass
class TabSession:
    """
    物理标签页上下文 (Physical Tab Context)
    """
    handle: TabHandle
    current_url: str = ""
    depth: int = 0
    # 待访问链接队列 (FIFO)
    # 存储的是纯 URL，当当前页面交互做完了，就从这里 pop
    pending_link_queue: Deque[str] = field(default_factory=deque) 


# ==========================================
# 2. 逻辑核心 (Logic Mixin)
# ==========================================

class DigitalInternCrawlerMixin:
    """
    数字实习生逻辑核心。
    实现了 "Observation -> Thought -> Action" 的递归循环。
    """

    # 依赖注入：假设 self.cerebellum 和 self.logger 已经由主类提供
    
    
        

    #def start_browser(self, ctx: MissionContext):
    #    profile_path = os.path.join(self.workspace_root ,".matrix", "browser_profile", self.name)
    #    download_path = os.path.join(self.workspace_root ,"download")
    #    self.browser_adapter = DrissionPageAdapter(
    #        profile_path=profile_path,
    #        download_path=download_path
    #    )

    def sanitize_filename(self, name: str, max_length: int = 200) -> str:
        """
        清洗字符串，使其可以作为合法的文件名/目录名，同时保留中文。
        
        规则:
        1. 去除 Windows/Linux 非法字符
        2. 去除不可见字符 (换行、Tab等)
        3. 去除首尾的空格和点 (Windows 不喜欢文件名以点或空格结尾)
        4. 截断长度，防止路径过长
        """
        if not name:
            return "untitled"

        # 1. 替换文件系统非法字符为下划线
        # Windows非法字符: < > : " / \ | ? *
        name = re.sub(r'[<>:"/\\|?*]', '_', name)

        # 2. 替换不可见控制字符 (如换行符 \n, \r, \t) 为空格
        name = "".join(ch if ch.isprintable() else " " for ch in name)

        # 3. 将连续的空格或下划线合并为一个 (美观优化)
        name = re.sub(r'[\s_]+', '_', name)

        # 4. 去除首尾的空格和点 (Windows文件名不能以点结尾)
        name = name.strip(' .')

        # 5. 如果清洗后为空 (比如原文件名全是非法字符)，给个默认值
        if not name:
            name = "untitled_file"

        # 6. 截断长度 (通常文件系统限制 255 字节，考虑到路径长度，限制在 200 字符比较安全)
        return name[:max_length]



    @register_action(
        "上网搜索并下载资料",
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
        save_dir = os.path.join(self.workspace_root, "downloads", self.sanitize_filename(topic))

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
        safe_title = self.sanitize_filename(snapshot.title,60)
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

    async def _filter_relevant_links(self, candidates, one_line_summary, ctx: MissionContext) -> List[str]:
        """
        [Brain] 批量筛选链接。
        输入：一批候选元素
        输出：值得访问的 URL 列表
        策略：Hard Filter (规则) -> Batch LLM Filter (小脑)
        """
        # 1. 规则预清洗 (Hard Filter)
        # 过滤掉明显无关的导航词，节省 Token
        # 也可以过滤掉已经访问过的 (visited)
        clean_candidates = {}
        ignored_keywords = [
            "login", "signin", "sign up", "register", "password", 
            "privacy policy", "terms of use", "contact us", "about us", 
            "customer service", "language", "sitemap", "javascript:", 
            "mailto:", "tel:", "unsubscribe"
        ]
        
        for link, link_text in candidates.items():
            # 基础校验
            if not link or len(link_text) < 2: continue
            
            # 黑名单关键词过滤
            text_lower = link_text.lower()
            if any(k in text_lower for k in ignored_keywords):
                continue
            
            # 全局去重过滤 (如果已经访问过，就不需要再判断了)
            if ctx.has_visited(link):
                continue

            clean_candidates[link]=link_text

        if not clean_candidates:
            self.logger.debug(f"No clean links found for {ctx.purpose}")
            return {}

        # 2. 分批调用小脑 (Batch Processing)
        # 本地模型上下文有限，建议每批 15-20 个链接
        batch_size = 10
        selected_urls = []
        
        # 预编译正则，提取 http/https 开头的链接
        # 允许 URL 包含常见字符，遇到换行或引号停止
        url_pattern = re.compile(r'(https?://[^\s"\'<>]+)')
        candidates_list = list(clean_candidates.items())

        for i in range(0, len(candidates_list), batch_size):
            batch = candidates_list[i : i + batch_size]
            
            # 构造给 LLM 看的清单
            # 格式: - [Link Text] (URL)
            list_str = "\n".join([f"- [{text}] ({url})" for url,text in batch])
            self.logger.debug(f"Processing batch: {list_str}")
            
            # 构造当前批次的“白名单”，用于验证 LLM 的输出
            # 这样即使 LLM 输出了幻觉 URL，也会被这里拦住
            batch_url_map = {url.strip(): text for url,text in batch}
            
            prompt = f"""
            Mission: Find links relevant to "{ctx.purpose}".
            
            Below is a list of links found on a webpage. 
            This page is about: {one_line_summary}.
            Select ONLY the links that are likely to contain information related to the Mission or worth to explore.
            
            [Candidates]
            {list_str}
            
            [Instructions]
            1. Select links that are likely to contain information related to the Mission. Or may lead to information related to the Mission (destinatioin worth explore).
            2. Ignore links clearly point to non-relavant pages or destinations
            3. 注意，如果是百度百科这样的网页，上面的链接很多是无关的，要仔细甄别，只选择确定有关的
            4. OUTPUT FORMAT: Just list the full URLs of the selected links, one per line.
            """

            try:
                # 调用小脑
                resp = await self.cerebellum.backend.think(messages=[{"role": "user", "content": prompt}])
                raw_reply = resp.get('reply', '')
                self.logger.debug(f"LLM reply: {raw_reply}")
                
                # 3. 正则提取与验证 (Extraction & Validation)
                found_urls = url_pattern.findall(raw_reply)
                
                for raw_url in found_urls:
                    # 清洗：有些 LLM 喜欢在 URL 后面加句号或逗号
                    clean_url = raw_url.strip('.,;)]}"\'')
                    
                    # 验证：这个 URL 真的在我们的输入批次里吗？
                    # 1. 精确匹配
                    if clean_url in batch_url_map:
                        selected_urls.append(clean_url)
                    else:
                        # 2. 容错匹配 (有时 LLM 会截断 URL 参数)
                        # 如果 batch 里有 https://a.com/b?id=1，LLM 输出了 https://a.com/b
                        # 我们尝试找“最相似”的，或者直接忽略。为了安全，这里只做精确匹配或简单的包含匹配。
                        # 考虑到 URL 可能很长，LLM 可能会抄错，我们可以反向查：
                        # 看看 batch 里有没有哪个 URL 包含了这个 clean_url
                        for original_url in batch_url_map.keys():
                            if clean_url in original_url and len(clean_url) > 15: # 长度保护防止匹配到 'http'
                                selected_urls.append(original_url)
                                break
            
            except Exception as e:
                self.logger.error(f"Link filtering batch failed: {e}")
                continue
        self.logger.debug(f"Selected links: {selected_urls}")
        # 去重返回
        return list(set(selected_urls))

    async def _choose_best_interaction(
        self,
        candidates: List[Dict],
        one_line_summary: str,
        ctx: MissionContext
    ) -> Optional[PageElement]:
        """
        [Brain] 从候选按钮中选择最值得点击的一个。
        使用串行淘汰机制 + 三级筛选策略：
        1. Immediate (立即访问): 高度吻合，直接返回
        2. Potential (潜在相关): 可能相关，放回队列头部继续竞争
        3. None (无价值): 删除，继续下一组

        Args:
            candidates: List[Dict] 格式，每个 Dict 是 {button_text: PageElement}
        """
        if not candidates:
            return None

        from collections import deque

        BATCH_SIZE = 10  # 每批评估的数量

        # 转换为列表格式: [(button_text, element), ...]
        # candidates 是 [{"text1": element1}, {"text2": element2}, ...]
        all_candidates = []
        for candidate_dict in candidates:
            # 每个 dict 只有一个键值对
            for text, element in candidate_dict.items():
                all_candidates.append((text, element))

        # 使用 deque 支持高效的头部操作
        candidate_deque = deque(all_candidates)

        self.logger.info(f"🔍 Sequential filtering started with {len(candidate_deque)} candidates")

        iteration = 0
        while candidate_deque:
            iteration += 1

            # 取前 batch_size 个（如果不足则取全部）
            batch_size = min(BATCH_SIZE, len(candidate_deque))
            batch = [candidate_deque.popleft() for _ in range(batch_size)]

            self.logger.debug(f"  Iter {iteration}: Evaluating {len(batch)} candidates, {len(candidate_deque)} remaining")

            # 评估这批
            result = await self._evaluate_batch(batch, one_line_summary, ctx)

            if result["priority"] == "immediate":
                # 找到最佳匹配，立即返回
                self.logger.info(f"⚡ Immediate match found: [{result['text']}] | Reason: {result['reason']}")
                return result["element"]

            elif result["priority"] == "potential":
                # 将 winner 放回队列头部，参与下一轮竞争
                winner_tuple = (result["text"], result["element"])
                if len(candidate_deque)>0:
                    candidate_deque.appendleft(winner_tuple)
                    self.logger.debug(f"    Potential: [{result['text']}] → Put back to queue front. Queue size: {len(candidate_deque)}")
                else:
                    return result["element"]
            # else: None，这批全部丢弃，继续下一轮

        # 队列为空，没有找到任何有价值的按钮
        self.logger.info("❌ Queue exhausted. No worthy buttons found.")
        return None

    async def _evaluate_batch(
        self,
        batch: List[tuple],
        one_line_summary: str,
        ctx: MissionContext
    ) -> Dict[str, Any]:
        """
        评估一批候选按钮，返回最佳选择（带优先级）。

        三级筛选策略：
        1. IMMEDIATE: 高度吻合，应该立即访问（优先级最高）
        2. POTENTIAL: 可能相关，值得考虑（中等优先级）
        3. NONE: 都不相关（最低优先级）

        Args:
            batch: [(button_text, element), ...] 格式的候选列表
            one_line_summary: 当前页面摘要
            ctx: 任务上下文

        Returns:
            {
                "priority": "immediate" | "potential" | "none",
                "text": str,
                "element": PageElement,
                "reason": str
            }
            如果 priority == "none"，text 和 element 为 None
        """
        if not batch:
            return {"priority": "none", "text": None, "element": None, "reason": "Empty batch"}

        # 构造选项字符串
        options_str = ""
        for idx, (text, element) in enumerate(batch):
            options_str += f"{idx + 1}. [{text}]\n"

        # 添加"弃权"选项
        options_str += "0. [None of these are useful]"

        # 构造 Prompt
        prompt = f"""
You are a Research Crawler evaluating buttons for a web crawling mission.

[Mission]
"{ctx.purpose}"

[Current Page Context]
{one_line_summary}

[Task]
Evaluate the buttons below and categorize your choice into THREE levels:

**LEVEL 1 - IMMEDIATE (应立即访问)**
- Criteria: 按钮描述与 Mission 目标高度匹配，明确指向你需要的核心信息
- Examples: "Python Tutorial", "Machine Learning Guide", "API Documentation"
- Action: 选择该按钮，返回 priority="immediate"

**LEVEL 2 - POTENTIAL (可能相关)**
- Criteria: 按钮可能导向相关内容，但不够明确
- Examples: "Learn More", "Details", "Next Page", "View Resources"
- Action: 选择最相关的一个按钮，返回 priority="potential"

**LEVEL 3 - NONE (都不相关)**
- Criteria: 所有按钮都与 Mission 无关，或是纯导航/社交功能
- Examples: "Share", "Login", "Home", "Contact Us", generic navigation
- Action: 返回 choice_id=0, priority="none"

[Options]
{options_str}

[Output Requirement]
Return JSON ONLY. Format:
{{
    "choice_id": <number 0-{len(batch)}>,
    "priority": "immediate" | "potential" | "none",
    "reason": "short explanation (one line)"
}}

IMPORTANT:
- If choice_id is 0, set priority="none"
- If choice_id is 1-{len(batch)}, set priority based on your evaluation
"""

        try:
            # 调用小脑
            resp = await self.cerebellum.backend.think(messages=[{"role": "user", "content": prompt}])
            raw_reason = resp.get('reasoning',''   )
            raw_reply = resp.get('reply', '')
            self.logger.debug(f"Reasong: {raw_reason}")
            self.logger.debug(f"Reply: {raw_reply}")

            # 解析结果
            json_str = raw_reply.replace("```json", "").replace("```", "").strip()
            result = json.loads(json_str)

            choice_id = int(result.get("choice_id", 0))
            priority = result.get("priority", "none").lower()
            reason = result.get("reason", "")

            # 验证 priority 值
            if priority not in ["immediate", "potential", "none"]:
                priority = "none"

            if choice_id == 0 or priority == "none":
                self.logger.debug(f"    No worthy button. Reason: {reason}")
                return {"priority": "none", "text": None, "element": None, "reason": reason}

            # 转换为 0-based index
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
                self.logger.warning(f"    Invalid choice_id: {choice_id}")
                return {"priority": "none", "text": None, "element": None, "reason": "Invalid choice"}

        except Exception as e:
            self.logger.exception(f"    Batch evaluation failed: {e}")
            return {"priority": "none", "text": None, "element": None, "reason": f"Error: {e}"}

    def _generate_final_report(self, ctx: MissionContext) -> str:
        return f"Mission Complete. Found {len(ctx.knowledge_base)} items."