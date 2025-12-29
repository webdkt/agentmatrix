import asyncio
import time
import os
import json
import textwrap
import logging
import random
import re
from urllib.parse import urljoin, urlparse
import trafilatura
from slugify import slugify
from core.action import register_action
from skills.search_tool import SmartSearcherMixin
from core.log_util import AutoLoggerMixin

# DrissionPage 依赖
from DrissionPage import ChromiumPage, ChromiumOptions

# ==========================================
# 1. 静态配置与工具函数
# ==========================================

DOMAIN_BLACKLIST = {
    'taobao.com', 'jd.com', 'tmall.com', 'amazon.com', 'ebay.com', 'temu.com',
    'youtube.com', 'bilibili.com', 'netflix.com', 'iqiyi.com',
    'facebook.com', 'instagram.com', 'twitter.com', 'x.com', 'tiktok.com', 'douyin.com',
    'linkedin.com/login', 'weibo.com'
}

def _is_safe_url(url: str) -> bool:
    """安全检查：避开电商、社媒和功能页"""
    if not url or len(url) < 5: return False
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if any(bl in domain for bl in DOMAIN_BLACKLIST): return False
    # 简单的扩展名过滤（图片等）
    if parsed.path.lower().endswith(('.jpg', '.png', '.gif', '.css', '.js')): return False
    return True

class ClickableCandidate:
    """数据类：封装页面上的可交互对象"""
    def __init__(self, element, text, ctype, url=None):
        self.element = element
        self.text = text.strip()
        self.type = ctype  # 'link' or 'interaction'
        self.url = url     # 仅 link 有效

    def __repr__(self):
        return f"[{self.type.upper()}] {self.text[:20]}..."

# ==========================================
# 2. HumanBrowserAgent (核心逻辑)
# ==========================================

class BrowserState:
    """记录 Agent 的认知状态，防止死循环"""
    def __init__(self):
        self.visited_urls = set()          # 已访问的 URL
        self.clicked_interactions = set()  # 已点击的交互 (URL + ButtonText)
        self.summarized_hashes = set()     # 已总结的内容 Hash

class HumanBrowser(AutoLoggerMixin):
    # 定义阈值：超过这个长度就不让小脑做总结了，太累且容易幻觉
    SUMMARY_THRESHOLD = 15000 

    # === 预设的领域评估标准 (Prompt Templates) ===
    PRESET_CRITERIA = {
        "STEM": textwrap.dedent("""
            [DOMAIN: SCIENCE, TECH, ENGINEERING, MATH]
            - **High Value Content**: Architecture diagrams, Mathematical formulas, Code snippets, Benchmark tables, Dataset specifications, Implementation details.
            - **Summary Style**: Structured bullet points with specific numbers and parameters.
            - **Trash**: Marketing fluff ("AI is the future"), Surface-level intros, SEO spam.
        """),

        "HUMANITIES": textwrap.dedent("""
            [DOMAIN: HISTORY, LITERATURE, PHILOSOPHY, ARTS]
            - **High Value Content**: Primary historical sources, Direct quotes, Critical analysis, Novel arguments, Chronology of events, Historiography.
            - **Summary Style**: Narrative summary capturing the core argument + Key Quotes.
            - **Trash**: Wikipedia-style generic summaries, Shallow listicles, Product sales.
        """),

        "BUSINESS": textwrap.dedent("""
            [DOMAIN: BUSINESS, FINANCE, NEWS]
            - **High Value Content**: Financial reports (10-K/10-Q), Official press releases, Executive statements, Market share data, Strategic analysis, Event timelines.
            - **Summary Style**: Executive Summary style. Focus on outcomes, numbers, and dates.
            - **Trash**: Clickbait headlines, Rumors without sources, Generic investment advice.
        """),
        "GENERAL": textwrap.dedent("""
            [DOMAIN: GENERAL KNOWLEDGE / LIFESTYLE / HOW-TO]
            - **High Value Content**: Comprehensive guides (Step-by-step), Verified factual data, Neutral encyclopedic overviews, Deep investigative reporting, High-quality tutorials.
            - **Summary Style**: Clear "How-to" steps, List of key facts, or Structured overview.
            - **Trash**: SEO Spam ("Top 10 products"), Shallow clickbait, User comments/Forum arguments (unless highly technical), Login walls.
        """)
    }
    def __init__(self, browser, context, save_dir, purpose, loop):
        self.browser = browser
        self.ctx = context
        self.save_dir = save_dir
        self.purpose = purpose
        self.state = BrowserState()
        
        # 保存 asyncio 事件循环，以便在同步线程中调用异步的小脑
        self.loop = loop 

    def start(self, seed_urls):
        """[入口] 启动单线程递归浏览"""
        tab = self.browser.new_tab()
        # 初始待办栈
        initial_stack = [u for u in reversed(seed_urls) if _is_safe_url(u)]
        
        try:
            self._explore_tab_loop(tab, initial_stack)
        finally:
            # 根 Tab 关闭，任务结束
            try: tab.close() 
            except: pass

    def _explore_tab_loop(self, tab, pending_urls):
        """
        [递归核心] 在一个 Tab 内的生命周期循环
        """
        while self.ctx.is_active():
            
            # --- Phase 1: 导航控制 (Navigation) ---
            # 如果当前是空页，或者之前的交互结束了需要去新地方
            if tab.url in ['about:blank', 'data:,'] or not _is_safe_url(tab.url):
                if not pending_urls:
                    self.logger.info("💤 No more pending URLs in this tab.")
                    break
                
                next_url = pending_urls.pop()
                if next_url in self.state.visited_urls: continue
                
                self.logger.info(f"➡ Navigating to: {next_url}")
                try:
                    tab.get(next_url, timeout=20)
                except:
                    continue

            # 页面加载后的基础处理（关弹窗等）
            self._optimize_page(tab)
            current_url = tab.url
            self.state.visited_urls.add(current_url)

            # --- Phase 2: 观察与总结 (Observation) ---
            # 获取内容
            html = tab.html
            text_content = trafilatura.extract(html) or ""
            
            # 只有当内容是新的，且长度足够时，才进行总结
            content_hash = hash(text_content)
            if content_hash not in self.state.summarized_hashes and len(text_content) > 300:
                self.state.summarized_hashes.add(content_hash)
                # 调用小脑总结并保存
                self._analyze_and_save(current_url, tab.title, text_content)

            # --- Phase 3: 发现候选者 (Discovery) ---
            # 获取所有 Link 和 Interaction
            link_candidates, interact_candidates = self._scan_page(tab)

            # --- Phase 4: 规划链接 (Planning - Links) ---
            # [关键逻辑] 在点击任何按钮之前，先把本页有价值的链接存起来！
            
            # 过滤掉已访问的链接
            new_links = [c for c in link_candidates if c.url not in self.state.visited_urls and c.url not in pending_urls]
            
            if new_links:
                # 问小脑：这些链接哪些值得以后看？
                chosen_urls = self._call_ai_filter_links(new_links)
                if chosen_urls:
                    self.logger.info(f"📌 Queued {len(chosen_urls)} links for later")
                    # 将选中的链接加入待办栈。
                    # 策略：extend 到末尾，意味着作为一个 Stack，它们会被优先访问（深度优先）。
                    # 如果希望广度优先，可以用 insert(0, ...) 但人类浏览通常是深度的。
                    for u in chosen_urls:
                         if u not in pending_urls: # 双重去重检查
                             pending_urls.append(u)

            # --- Phase 5: 规划交互 (Planning - Interaction) ---
            # 问小脑：现在有没有必须点的按钮？
            
            # 过滤掉已点击过的按钮
            valid_interactions = []
            for c in interact_candidates:
                key = (current_url, c.text)
                if key not in self.state.clicked_interactions:
                    valid_interactions.append(c)
            
            target_interaction = None
            if valid_interactions:
                target_interaction = self._call_ai_pick_interaction(valid_interactions)

            # --- Phase 6: 执行交互 (Execution) ---
            if target_interaction:
                # 记录点击，防止死循环
                key = (current_url, target_interaction.text)
                self.state.clicked_interactions.add(key)
                
                self.logger.info(f"👆 Clicking: [{target_interaction.text}]")
                
                # 记录点击前的 Tab 状态
                pre_tab_id = tab.tab_id
                pre_tab_count = self.browser.tabs_count
                
                try:
                    # 点击!
                    target_interaction.element.click(by_js=False) # 优先模拟真实点击
                    time.sleep(2) # 等待反应
                except Exception as e:
                    self.logger.warning(f"Click failed: {e}")
                    continue

                # 检查结果：
                # 情况 A: 弹出了新标签页 -> 递归进去处理
                if self.browser.tabs_count > pre_tab_count:
                    self.logger.info("🔀 New Tab detected, recursing...")
                    new_tab = self.browser.tabs[-1]
                    # 递归调用！新 Tab 从空栈开始
                    self._explore_tab_loop(new_tab, []) 
                    # 递归返回后，确保新 Tab 关闭
                    try: new_tab.close()
                    except: pass
                    # 回到当前循环，继续处理当前页（因为之前的链接已经存了，不怕丢）
                
                # 情况 B: 还是同一个 Tab，但 URL 变了或者内容变了
                else:
                    # 什么都不用做，直接 continue。
                    # 下一次循环开头会检测 URL 变化，或者重新 hash 内容。
                    pass
            
            else:
                # 没有值得点的交互了
                # 此时应该去处理 pending_urls
                if pending_urls:
                    # 强制跳转到下一个 URL
                    next_url = pending_urls.pop()
                    if next_url not in self.state.visited_urls:
                        self.logger.info(f"➡ Page exhausted, going next: {next_url}")
                        try:
                            tab.get(next_url)
                        except: pass
                else:
                    # 当前 Tab 既没有交互，也没有待办 URL -> 结束 Tab
                    self.logger.info("✅ Tab finished.")
                    break

    def _scan_page(self, tab):
        """扫描页面元素，返回 (links, interactions)"""
        links = []
        interactions = []
        
        # 1. Links
        for a in tab.eles('tag:a@@visibility:visible'):
            try:
                txt = a.text.strip()
                href = a.link
                if not txt or len(txt) < 2: continue
                # 如果是 javascript: 或者是空链接，视为交互按钮
                if not href or len(href) < 5 or href.startswith('javascript'):
                    interactions.append(ClickableCandidate(a, txt, 'interaction'))
                elif _is_safe_url(href):
                    links.append(ClickableCandidate(a, txt, 'link', href))
            except: continue
            
        # 2. Buttons / Inputs
        for btn in tab.eles('css:button, input[type="submit"], [role="button"]'):
            try:
                if not btn.is_visible: continue
                txt = btn.text.strip() or btn.attr('title') or btn.attr('value')
                if txt and len(txt) > 2:
                    interactions.append(ClickableCandidate(btn, txt, 'interaction'))
            except: continue
            
        return links, interactions

    def _optimize_page(self, tab):
        """清除弹窗，展开内容"""
        # 简单实现，可扩展
        try:
            # 关遮罩
            for txt in ['Accept', 'Agree', 'Close', '关闭', '同意']:
                btn = tab.ele(f'tag:button@@text():{txt}@@visibility:visible')
                if btn: btn.click(by_js=True)
            # 展开
            for txt in ['Read More', 'Show Full', '展开']:
                btn = tab.ele(f'text:{txt}@@visibility:visible')
                if btn: btn.click(by_js=True)
        except: pass

    # ============================
    # Sync-Async Bridge & AI Calls
    # ============================

    def _call_ai_sync(self, coro):
        """在同步线程中调用异步协程并等待结果"""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def _analyze_and_save(self, url, title, text):
        """调用 Brain 判断价值并保存"""

        async def _judge_content_relevance() -> str:
            """
            [智能小脑]
            1. 如果文章短，生成 Summary，返回 {"action": "save_summary", "content": "..."}
            2. 如果文章长，只判断相关性，返回 {"action": "save_full", "content": "(original text)"}
            3. 如果无关，返回 {"action": "skip"}
            """
            text_len = len(text)
            criteria = self.ctx.criteria
            lang = self.ctx.lang
            #self.logger.debug(f"评估： {text[:200]} for {query} , criteria: {criteria}")
            # 共同的评估标准（High Value Criteria）
            
            
            # === 分支 A: 长文模式 (只判断，不总结) ===
            if text_len > self.SUMMARY_THRESHOLD:
                # 只看开头，判断是否值得存
                preview = text[:4000] 
                prompt = textwrap.dedent(f"""
                    Mission: Researching "{self.purpose}".
                    
                    EVALUATION STANDARDS:
                    {criteria}

                    Content Preview (First 4k chars of {text_len} chars):
                    {preview}
                    ...
                    
                    Task: Strictly evaluate if this content meets the High Value standards above.
                    
                    Output JSON ONLY:
                    - If High Value: {{"decision": "save_full"}}
                    - Otherwise: {{"decision": "skip"}}
                """)
                
                try:
                    # 假设 backend 返回 JSON
                    resp = await self.cerebellum.backend.think(messages=[{"role": "user", "content": prompt}])
                    self.logger.debug(f"小脑思考: {resp['reasoning']}")
                    decision = json.loads(resp['reply'].replace("```json", "").replace("```", "").strip())
                    self.logger.debug(f"小脑判断: {decision}")
                    return decision
                except:
                    self.logger.exception(f"小脑判断失败")
                    return {"decision": "skip"}

            # === 分支 B: 短文模式 (生成摘要) ===
            else:
                prompt = textwrap.dedent(f"""
                    Mission: Researching "{self.purpose}".
                    
                    EVALUATION STANDARDS:
                    {criteria}
                    
                    Content:
                    {text}
                    
                    Task:
                    1. If content is low value/trash based on standards -> SKIP.
                    2. If high value -> Generate a dense Markdown Summary following the "Summary Style" above. Summary prefer to use {lang}
                    
                    Output JSON ONLY:
                    - If high value: {{"decision": "save_summary", "title":"generate a short title", "summary": "..."}}
                    - If low value/trash: {{"decision": "skip"}}
                """)
                
                try:
                    resp = await self.cerebellum.backend.think(messages=[{"role": "user", "content": prompt}])
                    self.logger.debug(f"小脑思考: {resp['reasoning']}")
                    decision = json.loads(resp['reply'].replace("```json", "").replace("```", "").strip())
                    self.logger.debug(f"小脑判断: {decision}")

                    return decision
                    
                    
                except:
                    self.logger.exception(f"小脑判断失败")
                    return {"decision": "skip"}
        

        try:
            result = self._call_ai_sync(_judge_content_relevance())
            if result.get('decision') == 'save_summary':
                title = result.get('title') or title
                #fname = f"{slugify(title)[:50]}.md"
                fname = re.sub(r'[<>:"/\\|?*.\s]', '_', title)[:50] + ".md"
                path = os.path.join(self.save_dir, fname)
                with open(path, "w", encoding='utf-8') as f:
                    f.write(f"# {title}\nSource: {url}\n\n{result.get('summary')}")
                self.logger.info(f"💾 Saved summary: {fname}")
            elif result.get('decision') == 'save_full':
                fname = re.sub(r'[<>:"/\\|?*.\s]', '_', title)[:50] + ".md"
                path = os.path.join(self.save_dir, fname)
                with open(path, "w", encoding='utf-8') as f:
                    f.write(f"# {title}\nSource: {url}\n\n{text}")
        except Exception as e:
            self.logger.error(f"AI Save failed: {e}")

    def _call_ai_filter_links(self, candidates):
        """让小脑筛选链接 (Return list of URLs)"""
        if not candidates: return []
        
        async def _task():
            # 只提供文本，不提供 URL，防止模型根据 URL 瞎猜
            items_str = "\n".join([f"{i}. {c.text}" for i, c in enumerate(candidates)])
            prompt = textwrap.dedent(f"""
                Goal: "{self.purpose}"
                I am on a webpage. Which of these links are likely to lead to relevant information or sub-categories (like 'Investor Relations', 'Reports')?
                
                Candidates:
                {items_str}
                
                Return the INDICES of the best links as a JSON list, e.g. [0, 5, 8].
                If none, return [].
            """)
            try:
                resp = await self.ctx.backend.think(messages=[{"role": "user", "content": prompt}])
                indices = json.loads(resp['reply'])
                return [candidates[i].url for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
            except:
                return []
        
        return self._call_ai_sync(_task())

    def _call_ai_pick_interaction(self, candidates):
        """让小脑选择一个 Interaction (Return One Candidate)"""
        async def _task():
            items_str = "\n".join([f"{i}. {c.text}" for i, c in enumerate(candidates)])
            prompt = textwrap.dedent(f"""
                Goal: "{self.purpose}"
                I am on a webpage. Which button should I click to reveal more content or navigate to the next part?
                Focus on: "Next Page", "Load More", "Expand", "Download Report".
                Ignore: "Share", "Like", "Comment".
                
                Candidates:
                {items_str}
                
                Return the INDEX of the single best candidate as JSON, e.g. 5. 
                If none are worth clicking, return -1.
            """)
            try:
                resp = await self.ctx.backend.think(messages=[{"role": "user", "content": prompt}])
                idx = int(resp['reply'].strip())
                if 0 <= idx < len(candidates):
                    return candidates[idx]
            except:
                pass
            return None

        return self._call_ai_sync(_task())


# ==========================================
# 3. 集成到 Crawler Logic
# ==========================================

class MissionContext:
    def __init__(self, timeout_minutes, backend):
        self.deadline = time.time() + timeout_minutes * 60
        self.backend = backend # 传递 AI 后端供 HumanBrowser 调用
    
    def is_active(self):
        return time.time() < self.deadline

class RecursiveCrawlerMixin(SmartSearcherMixin):
    
    @register_action("从网上搜索并下载对研究目标有用的相关资料", param_infos={...})
    async def research_crawler(self, search_phrase, purpose, topic, seed_urls=None, timeout=30, **kwargs):
        
        save_dir = os.path.join(self.workspace_root, "downloads", slugify(topic))
        os.makedirs(save_dir, exist_ok=True)
        
        # 1. 获取种子
        if not seed_urls:
            search_res = await self._smart_search_entry(search_phrase, limit=10)
            if isinstance(search_res, str): return search_res
            seed_urls = [item['href'] for item in search_res]

        # 2. 初始化环境
        # 注意：这里需要传入 self.cerebellum.backend 以便 Agent 调用 LLM
        ctx = MissionContext(timeout, self.cerebellum.backend)
        
        # 启动 DrissionPage (无头模式)
        co = ChromiumOptions()
        co.headless(True)
        co.set_argument('--no-sandbox')
        browser = ChromiumPage(co)
        
        # 获取当前 asyncio loop，以便传给 sync thread
        loop = asyncio.get_running_loop()
        
        agent = HumanBrowser(browser, ctx, save_dir, purpose, loop)
        
        try:
            self.logger.info("🤖 HumanBrowserAgent starting...")
            # 关键：将整个同步的浏览过程放入线程池执行，不阻塞主线程
            await asyncio.to_thread(agent.start, seed_urls)
        
        except Exception as e:
            self.logger.error(f"Crawler crashed: {e}")
        finally:
            browser.quit()

        # 3. 汇报
        file_count = len([n for n in os.listdir(save_dir) if n.endswith('.md')])
        return f"Mission Complete. Saved {file_count} documents to {save_dir}."