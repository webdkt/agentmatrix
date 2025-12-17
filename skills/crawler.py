import asyncio
import time
import os
import json
import textwrap
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import trafilatura
from slugify import slugify
from core.action import register_action
from skills.search_tool import SmartSearcherMixin
import random
from urllib.parse import unquote
import re


# === 1. 共享上下文对象 ===
class MissionContext:
    
    def __init__(self,  timeout_minutes: int, criteria, lang, max_concurrency: int = 5):
        
        self.visited = set()  # 全局去重
        self.results = [] # 存储字典: {'type': 'file'|'page', 'title':..., 'path':..., 'url':...}
        self.start_time = time.time()
        self.deadline = self.start_time + timeout_minutes*60
        # === 全局并发锁 ===
        # 这意味着同时最多只有 5 个 HTTP 请求在跑
        # 其他的 task 可以在后台逻辑处理（小脑思考），但网络请求必须排队
        self.sem = asyncio.Semaphore(max_concurrency)
        self.criteria = criteria
        self.lang = lang
        
        
    def is_active(self):
        """检查任务是否应该继续（超时）"""
        
        if time.time() > self.deadline:
            self.logger.info(f"任务超时，终止")
            return False
        return True



class RecursiveCrawlerMixin(SmartSearcherMixin):

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

    _custom_log_level = logging.DEBUG

    async def _judge_content_relevance(self, text: str, query: str, context) -> str:
        """
        [智能小脑]
        1. 如果文章短，生成 Summary，返回 {"action": "save_summary", "content": "..."}
        2. 如果文章长，只判断相关性，返回 {"action": "save_full", "content": "(original text)"}
        3. 如果无关，返回 {"action": "skip"}
        """
        text_len = len(text)
        criteria = context.criteria
        lang = context.lang
        #self.logger.debug(f"评估： {text[:200]} for {query} , criteria: {criteria}")
        # 共同的评估标准（High Value Criteria）
        
        
        # === 分支 A: 长文模式 (只判断，不总结) ===
        if text_len > self.SUMMARY_THRESHOLD:
            # 只看开头，判断是否值得存
            preview = text[:4000] 
            prompt = textwrap.dedent(f"""
                Mission: Researching "{query}".
                
                EVALUATION STANDARDS:
                {criteria}

                Content Preview (First 4k chars of {text_len} chars):
                {preview}
                ...
                
                {criteria}
                
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
                if decision.get("decision") == "save_full":
                    # 返回原文
                    return {"action": "save_full", "content": text}
                else:
                    return {"action": "skip"}
            except:
                self.logger.exception(f"小脑判断失败")
                return {"action": "skip"}

        # === 分支 B: 短文模式 (生成摘要) ===
        else:
            prompt = textwrap.dedent(f"""
                Mission: Researching "{query}".
                
                EVALUATION STANDARDS:
                {criteria}
                
                Content:
                {text}
                
                Task:
                1. If content is low value/trash based on standards -> SKIP.
                2. If high value -> Generate a dense Markdown Summary following the "Summary Style" above. Summary prefer to use {lang}
                
                Output JSON ONLY:
                - If high value: {{"decision": "save_summary", "summary": "..."}}
                - If low value/trash: {{"decision": "skip"}}
            """)
            
            try:
                resp = await self.cerebellum.backend.think(messages=[{"role": "user", "content": prompt}])
                self.logger.debug(f"小脑思考: {resp['reasoning']}")
                decision = json.loads(resp['reply'].replace("```json", "").replace("```", "").strip())
                self.logger.debug(f"小脑判断: {decision}")
                
                if decision.get("decision") == "save_summary":
                    return {"action": "save_summary", "content": decision.get("summary")}
                else:
                    return {"action": "skip"}
            except:
                self.logger.exception(f"小脑判断失败")
                return {"action": "skip"}

    async def _filter_links_by_cerebellum(self, links: list, query: str) -> list:
        """
        [小脑] 从一堆链接中挑选值得继续访问的。
        """
        if not links: return []
        
        # 1. 预处理：生成 Markdown 供 LLM 阅读，同时维护 URL 白名单
        candidates_display = [] # 给 LLM 看的
        
        # 过滤垃圾链接
        filtered_links = []
        for text, href in links:
            if len(text) < 2 or "login" in href or "signup" in href or "javascript:" in href:
                continue
            filtered_links.append((text, href))
            
        if not filtered_links: return []

        # 2. 分批处理
        batch_size = 20
        selected_hrefs = []
        
        # 优化后的正则：允许 URL 中出现括号 (处理 Wiki 链接)，但排除末尾标点
        # 策略：捕获非空白字符，后续再清洗
        URL_PATTERN = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')

        for i in range(0, len(filtered_links), batch_size):
            batch = filtered_links[i:i+batch_size]
            
            # 构建该批次的“白名单集合”，用于精准验证
            # 这样无论 LLM 输出什么幻觉，只要不是原封不动的 URL，都会被过滤掉
            valid_href_set = {href for _, href in batch}
            
            # 构建 Prompt 文本
            batch_str = "\n".join([f"- {href} (Content: {text})" for text, href in batch])
            
            prompt = textwrap.dedent(f"""
                Mission: Researching "{query}".
                
                Candidate Links:
                {batch_str}
                
                Task: output the URLs from the list above that are most likely to contain valuable information (PDFs, Articles, Documentation).
                
                Rules:
                1. Output ONLY the URLs. One per line.
                2. Do NOT output bullet points or explanations.
                3. If none are relevant, output "NONE".
            """)
            
            try:
                resp = await self.cerebellum.backend.think(messages=[{"role": "user", "content": prompt}])
                content = resp['reply']
                # self.logger.debug(f"小脑筛选结果:\n{content}")

                # 3. 提取与验证
                found_candidates = URL_PATTERN.findall(content)
                
                valid_count = 0
                for url in found_candidates:
                    # 清洗：有些模型喜欢在 URL 后面加句号或逗号
                    clean_url = url.rstrip('.,;)]}') 
                    
                    # 维基百科特例：如果原链接里确实有括号，正则可能没切好，或者 strip 切多了
                    # 但最稳妥的办法是：直接去 valid_href_set 里查
                    
                    # A. 直接匹配
                    if clean_url in valid_href_set:
                        selected_hrefs.append(clean_url)
                        valid_count += 1
                        continue
                        
                    # B. 容错匹配：如果模型输出了 `https://.../foo)` (被正则捕获了右括号)
                    # 我们可以尝试恢复它。或者简单点，直接遍历 batch 查找子串
                    # (由于 batch 只有 20 个，遍历开销可忽略)
                    for original_href in valid_href_set:
                        # 如果模型输出的 url 包含在原始 url 里，或者原始 url 包含在输出里
                        # 且长度差异很小，我们就认为是同一个
                        if original_href == url or original_href == clean_url:
                            if original_href not in selected_hrefs: # 防止重复添加
                                selected_hrefs.append(original_href)
                                valid_count += 1
                            break
                            
                self.logger.info(f"✅ Cerebellum filtered: kept {valid_count}/{len(batch)} links")

            except Exception as e:
                self.logger.error(f"Link filtering failed: {e}")
                continue
                
        return selected_hrefs
    
    

    def _generate_manifest(self, save_dir: str, topic: str, results: list):
        """
        生成机器可读的 JSON 和人类可读的 Markdown 索引
        """
        # 1. 生成 JSON (数据库)
        json_path = os.path.join(save_dir, "manifest.json")
        with open(json_path, "w", encoding='utf-8') as f:
            json.dump({
                "topic": topic,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_items": len(results),
                "items": results
            }, f, indent=2, ensure_ascii=False)

        # 2. 生成 Markdown (README.md) - 这是给 Brain 以后阅读用的索引
        md_path = os.path.join(save_dir, "README.md")
        with open(md_path, "w", encoding='utf-8') as f:
            f.write(f"# Data Collection Manifest: {topic}\n\n")
            f.write(f"> Collection Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"> Total Items: {len(results)}\n\n")
            f.write("| Type | Title / Local Path | Original URL | Notes |\n")
            f.write("| :--- | :--- | :--- | :--- |\n")
            
            for item in results:
                icon = "📄" if item['type'] == 'page' else "💾"
                # 相对路径链接
                local_link = f"[{item['title']}](./{item['path']})"
                # 截断长 URL
                short_url = item['url'][:30] + "..." if len(item['url']) > 30 else item['url']
                note = item.get('summary', '') or f"{item.get('size_kb', 0):.1f} KB"
                # 清洗 note 中的换行符以免破坏表格
                note = note.replace('\n', ' ').replace('|', '/')[:50]
                
                f.write(f"| {icon} {item['type']} | {local_link} | [{short_url}]({item['url']}) | {note} |\n")
        
        return md_path

    # === 2. 核心递归函数 ===
    async def _recursive_explore(self, session, url: str, context: MissionContext, purpose: str, save_dir: str):
        # A. 熔断检查
        #self.logger.info(f"🔎 [Active: {url}] Exploring...")
        if not context.is_active() or url in context.visited:
            self.logger.info(f"🛑 [{url}] Already visited or mission terminated.")
            return
        
        
        context.visited.add(url)
        
        

        try:
            # B. 访问 (执行)
            content = None
            resp = None
            async with context.sem:
                self.logger.info(f"🚀 [Active] Fetching: {url}")
                
                # === 改进点 1: 重试机制 ===
                max_retries = 3
                resp = None
                
                for attempt in range(max_retries):
                    try:
                        # === 改进点 2: 启用 stream=True 和更长的 timeout ===
                        # stream=True 意味着只要连上并拿到 Header 就算成功，不会等 body 下载完
                        # timeout=60 对文件下载更友好
                        await asyncio.sleep(random.uniform(0.4, 2.5)) # 避免请求过快被封 IP
                        resp = await session.get(url, allow_redirects=True, timeout=60, stream=True)
                        if resp.status_code == 200:
                            break # 成功拿到响应头，跳出重试循环
                    except Exception as e:
                        if attempt < max_retries - 1:
                            self.logger.warning(f"⚠️ Retry {attempt+1}/{max_retries} for {url}: {e}")
                            await asyncio.sleep(2) # 避让一下
                        else:
                            raise e # 最后一次还失败，抛出异常

                if not resp or resp.status_code != 200:
                    self.logger.warning(f"❌ HTTP {resp.status_code}: {url}")
                    return

                # 获取跳转后的最终 URL
                final_url = str(resp.url)
                context.visited.add(final_url)
                content_type = resp.headers.get("content-type", "").lower()

                # --- 分支 1: 是文件 (PDF/Doc/Zip) ---
                if "text/html" not in content_type:
                    # 自动推断文件名
                    path_name = os.path.basename(urlparse(final_url).path)
                    # 简单的清洗，防止文件名为空或非法
                    if not path_name or len(path_name) < 2:
                        path_name = f"file_{hash(final_url)}.bin"
                    
                    # 加上扩展名修正（如果 url 里没后缀，content-type 里有）
                    if "pdf" in content_type and not path_name.endswith(".pdf"): path_name += ".pdf"
                    
                    fname = unquote(path_name) # 解码中文文件名 (例如 %E5%AE... -> 安利.pdf)
                    save_path = os.path.join(save_dir, fname)

                    # === 改进点 3: 流式下载写入 (Chunked Write) ===
                    # 这种方式不会因为文件大而超时，只要数据还在流转，连接就保持
                    file_size = 0
                    with open(save_path, "wb") as f:
                        async for chunk in resp.aiter_content():
                            f.write(chunk)
                            file_size += len(chunk)
                    
                    self.logger.info(f"💾 File Saved: {fname} ({file_size/1024:.1f} KB)")
                    
                    context.results.append({
                        "type": "file",
                        "title": fname,
                        "path": fname,
                        "url": final_url,
                        "size_kb": file_size / 1024,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    return # 文件是终点
                else:
                # --- 分支 2: 是网页 ---
                # 对于网页，我们需要读取全文来做分析
                    content = b""
                    async for chunk in resp.aiter_content():
                        content += chunk
                    #读完要释放了context.sem
                
            html = content
    
            # 1. 尝试提取内容 (Harvest)
            text = trafilatura.extract(html)
            # 小脑快速扫一眼：这页内容本身有用吗？
            if text and len(text) > 100:
                # 智能判断与处理
                judgment = await self._judge_content_relevance(text, purpose,context)
                self.logger.info(f"🤖 [{url}] Relevance Judged: {judgment}")
                action = judgment.get("action")
                
                if action != "skip":
                    title = BeautifulSoup(html, 'lxml').title.string or "Untitled"
                    # 安全文件名
                    safe_title = slugify(title)[:50]
                    fname = f"{safe_title}.md"
                    save_path = os.path.join(save_dir, fname)
                    
                    # 构造文件头部元数据
                    header = f"# {title}\n> Source: {final_url}\n> Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    
                    # 根据类型写入不同的 Tag
                    if action == "save_summary":
                        header += "> Type: AI Summary (Original text discarded)\n\n"
                        # 这里写入的是小脑生成的 Summary
                        body = judgment.get("content")
                        note_for_manifest = "AI Summary"
                    else:
                        header += "> Type: Full Text (Too long for summary)\n\n"
                        # 这里写入的是原始 Text
                        body = text 
                        note_for_manifest = "Full Text"

                    with open(save_path, "w", encoding='utf-8') as f:
                        f.write(header + body)
                    
                    # 记录到 Context
                    context.results.append({
                        "type": "page",
                        "title": title,
                        "path": fname,
                        "url": final_url,
                        "summary": note_for_manifest, 
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    })
                else:
                    # self.logger.debug(f"Skipped irrelevant page: {final_url}")
                    pass

            # 2. 寻找下一步 (Exploration)
            
            soup = BeautifulSoup(html, 'lxml')
            raw_links = []
            for a in soup.find_all('a', href=True):
                abs_url = urljoin(final_url, a['href'])
                txt = a.get_text(strip=True)
                if abs_url not in context.visited:
                    raw_links.append((txt, abs_url))
            
            # 让小脑筛选下一步去哪 (这是“递归不需要限深”的关键)
            # 小脑会自动过滤掉“联系我们”、“首页”等无关链接，只保留相关性高的
            targets = await self._filter_links_by_cerebellum(raw_links, purpose)
            self.logger.info(f"🤖 [{url}] Found {len(targets)} relevant links")
            # C. 递归调用 (并发分叉)
            # 我们并发地去探索这些有价值的分支
            tasks = []
            for target_url in targets:
                # 递归！
                tasks.append(self._recursive_explore(session, target_url, context, purpose, save_dir))
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.logger.warning(f"Crawling failed for {url}: {e}")

    # === 3. 对外暴露的 Action ===
    @register_action(
        "从网上搜索并下载对研究目标有用的相关资料",
        param_infos={
            "search_phrase": "搜索关键词",
            "purpose": "研究或搜索的目的",
            "topic": "保存文件夹",
            "domain": "研究领域，优先从以下选择一个: 'STEM', 'HUMANITIES', 'BUSINESS'，如果都不匹配，使用 'GENERAL' ",
            "seed_urls": "可选，种子URL列表 (如果有)",
            "max_steps": "可选，最大访问页面数 (默认 1000)",
            "timeout": "可选最大耗时分钟 (默认 30)"
        }
    )
    async def research_crawler(self, search_phrase, purpose: str, topic: str, domain: str="STEM", seed_urls: list = None, max_steps: int = 1000, timeout: int = 30):
        domain = domain.upper()
        search_phrase_in_chinese = self._is_chinese_query(search_phrase)
        purpose_in_chinese = self._is_chinese_query(purpose)
        lang = "中文" if search_phrase_in_chinese or purpose_in_chinese else "English"
        if domain not in self.PRESET_CRITERIA:
            self.logger.warning(f"Unknown domain '{domain}', defaulting to STEM")
            domain = "STEM"
        criteria_text = self.PRESET_CRITERIA[domain]
        # 初始化上下文
        ctx = MissionContext( timeout_minutes=timeout, criteria=criteria_text, lang=lang)
        save_dir = os.path.join(self.workspace_root, "downloads", slugify(topic))
        os.makedirs(save_dir, exist_ok=True)
        
        

        # 如果没有种子，先搜一波
        if not seed_urls:
            search_res = await self._smart_search_entry(search_phrase, limit=20)
            if isinstance(search_res, str): return search_res
            seed_urls = [item['href'] for item in search_res]

        # 启动并发递归
        async with AsyncSession(impersonate="chrome") as session:
            tasks = []
            for url in seed_urls:
                tasks.append(self._recursive_explore(session, url, ctx, purpose, save_dir))
            
            await asyncio.gather(*tasks, return_exceptions=True)

        # 生成清单
        manifest_path = self._generate_manifest(save_dir, topic, ctx.results)
            
        # 2. 构造给 Brain 的最终汇报
        # 此时 Brain 不需要看那几十条的具体内容，只需要知道“活儿干完了，东西在哪”
        
        file_count = sum(1 for r in ctx.results if r['type'] == 'file')
        page_count = sum(1 for r in ctx.results if r['type'] == 'page')
        
        report_msg = textwrap.dedent(f"""
            ✅ **Collection Mission Complete**
            
            **Topic**: {topic}
            **Status**: Gathered {len(ctx.results)} items.
            - Files (PDF/Docs/etc): {file_count}
            - Pages (Markdown): {page_count}
            
            **Artifacts**:
            - All data saved to: `downloads/{topic}/`
            - Index file created: `downloads/{topic}/README.md` (See this file for details)
            
            采集工作完成，回复邮件后就可以休息了！

        """)
        
        return report_msg