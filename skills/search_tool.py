import os
import asyncio
import urllib.parse
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
import xml.etree.ElementTree as ET # 用于解析 ArXiv API

class SmartSearcherMixin:
    def _is_chinese_query(self, text: str) -> bool:
        """
        [Helper] 检测 query 是否包含中文字符。
        只要包含哪怕一个汉字，就倾向于认为用户想要中文结果。
        """
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False

    # === 1. Google Search (VIP, 需要代理) ===
    async def _search_google(self, session, query, limit=10):
        """
        [Hard Mode] 伪装爬取 Google。
        Google 反爬极严，需要高质量的 IP 和指纹。
        """
        # Google 的搜索结果结构经常变，但 h3 -> a 的结构相对稳定
        base_url = "https://www.google.com/search"
        params = {"q": query, "num": str(limit + 5)}

        # 语言适配
        if self._is_chinese_query(query):
            params["hl"] = "zh-CN" # Interface Language
            params["gl"] = "sg" # Language Restrict (可选，看你是否想要强制纯中文)
            # 建议只设 hl=zh-CN，Google 很聪明，会自己混合结果
        else:
            params["hl"] = "en"
            params["gl"] = "us" # Geo Location preference
        
        try:
            # 必须带 Header，否则 Google 以为是脚本
            headers = {
                #"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8" if self._is_chinese_query(query) else "en-US,en;q=0.9",
                "Referer": "https://www.google.com/"
            }
            
            resp = await session.get(base_url, params=params, headers=headers, timeout=15)
            
            if resp.status_code == 429:
                self.logger.warning("Google Search: CAPTCHA triggered (429). Proxy might be dirty.")
                return []
            if resp.status_code != 200:
                self.logger.warning(f"Google Search failed: {resp.status_code}")
                return []

            soup = BeautifulSoup(resp.content, "lxml")
            results = []
            
            # Google 标准结果通常在 div.g 里
            for g in soup.select("div.g"):
                if len(results) >= limit: break
                try:
                    # 提取标题和链接
                    h3 = g.select_one("h3")
                    link = g.select_one("a")
                    
                    if h3 and link and link.has_attr("href"):
                        title = h3.get_text()
                        href = link["href"]
                        
                        # 跳过 Google 的相关搜索推荐等无效链接
                        if href.startswith("/search") or "google.com" in href:
                            continue

                        # 尝试提取摘要 (Google 的摘要 class 很乱，通常是 div 里的文本)
                        # 这里用一种比较粗暴但有效的方法：找 h3 后面最大的那段字
                        snippet = "No snippet"
                        text_divs = g.select("div[style*='-webkit-line-clamp']") # 很多时候摘要有这个属性
                        if not text_divs:
                             # Fallback: 找所有 span/div
                             text_divs = g.select("div span")
                        
                        for t in text_divs:
                            txt = t.get_text()
                            if len(txt) > 20: # 认为是摘要
                                snippet = txt
                                break

                        results.append({"title": title, "href": href, "body": snippet, "source": "Google"})
                except:
                    continue
            
            return results
        except Exception as e:
            self.logger.warning(f"Google Scrape Exception: {e}")
            return []

    # === 2. Bing Search (Fallback, 中国直连) ===
    async def _search_bing(self, session, query, limit=10):
        """
        [Easy Mode] 优化版 Bing 搜索。
        强制使用国际版参数，防止被重定向到国内版。
        """
        base_url = "https://www.bing.com/search"
        # 1. 基础配置：强制连接 US 服务器以获取完整的索引库 (Global Index)
        # 'cc=US' 主要是为了物理层面告诉 Bing "我想要国际版的库"，防止被重定向到阉割版
        params = {
            "q": query, 
            "count": str(limit + 5),
            "cc": "US" 
        }
        
        # 2. 语言自适应：根据 Query 决定“市场偏好”
        if self._is_chinese_query(query):
            self.logger.info(f"🇨🇳 Detected Chinese Query: '{query}'. Tuning for Chinese results.")
            # 显式告诉 Bing：虽然我连的是 US 服务器，但请优先给我中文内容
            params["setlang"] = "zh-CN"
            # 甚至可以不设 setmkt，让它自然匹配；或者设为 zh-CN
            # 注意：如果设了 setmkt=zh-CN，有些时候可能会被 Bing 强转回 cn.bing.com，
            # 所以保守策略是：只设 setlang，不设 setmkt，或者 setmkt 留空
        else:
            self.logger.info(f"🇺🇸 Detected Non-Chinese Query: '{query}'. Tuning for Global/English results.")
            params["setlang"] = "en"
            params["setmkt"] = "en-US" # 英文搜索时，强制 US 市场结果质量最高

        try:
            # 必须带 Header，否则 Bing 可能会根据 IP 强行锁定语言
            headers = {
                #"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8" if self._is_chinese_query(query) else "en-US,en;q=0.9"
            }
            
            resp = await session.get(base_url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200: return []

            soup = BeautifulSoup(resp.content, "lxml")
            results = []
            
            for item in soup.select("li.b_algo"):
                if len(results) >= limit: break
                try:
                    h2 = item.select_one("h2 a")
                    if not h2: continue
                    
                    results.append({
                        "title": h2.get_text(),
                        "href": h2['href'],
                        "body": item.select_one(".b_caption p").get_text() if item.select_one(".b_caption p") else "",
                        "source": "Bing"
                    })
                except: continue
            return results
        except Exception as e:
            self.logger.error(f"Bing Search Error: {e}")
            return []

    # === 3. ArXiv API (STEM 增强) ===
    async def _search_arxiv(self, session, query, limit=5):
        """
        [Bonus] 针对 STEM 领域，直接查 ArXiv API。
        这是极其高质量的源，绝对没有营销号。
        """
        # ArXiv API 不需要代理，也不需要 Cookie，非常稳
        api_url = "http://export.arxiv.org/api/query"
        # 简单的预处理：把空格换成 AND
        safe_query = urllib.parse.quote(query)
        params = f"search_query=all:{safe_query}&start=0&max_results={limit}"
        
        try:
            # ArXiv 很快，不需要伪装，普通 get 即可
            resp = await session.get(f"{api_url}?{params}", timeout=10)
            if resp.status_code != 200: return []
            
            # 解析 XML
            root = ET.fromstring(resp.content)
            results = []
            # XML 命名空间
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns).text.replace('\n', ' ').strip()
                summary = entry.find('atom:summary', ns).text.replace('\n', ' ').strip()[:200]
                link = entry.find('atom:id', ns).text # ArXiv 的 ID url
                
                # 优先找 PDF 链接
                pdf_link = link
                for l in entry.findall('atom:link', ns):
                    if l.attrib.get('title') == 'pdf':
                        pdf_link = l.attrib['href']
                
                results.append({
                    "title": f"[ArXiv] {title}",
                    "href": pdf_link,
                    "body": summary,
                    "source": "ArXiv API"
                })
            return results
        except Exception as e:
            self.logger.warning(f"ArXiv Search Error: {e}")
            return []

    async def _search_baidu_xueshu(self, session, query, limit=5):
        """
        [CN Scholar] 百度学术搜索。
        聚合了知网、万方等元数据，且能找到部分免费 PDF 链接。
        """
        base_url = "https://xueshu.baidu.com/s"
        params = {"wd": query, "tn": "SE_baiduxueshu_c1gjeupa", "ie": "utf-8"}
        
        try:
            # 百度学术对 header 比较敏感，建议模拟完整 header
            headers = {
                #"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/110.0.0.0 Safari/537.36",
                "Referer": "https://xueshu.baidu.com/"
            }
            
            resp = await session.get(base_url, params=params, headers=headers, timeout=10)
            if resp.status_code != 200: return []
            
            soup = BeautifulSoup(resp.content, "lxml")
            results = []
            
            # 百度学术的结果卡片通常是 div.sc_content
            for item in soup.select("div.sc_content"):
                if len(results) >= limit: break
                try:
                    # 1. 标题和详情页链接
                    h3 = item.select_one("h3.t a")
                    if not h3: continue
                    
                    title = h3.get_text().strip()
                    # 这是百度学术的详情页链接
                    detail_url = h3['href'] 
                    
                    # 2. 摘要
                    abstract_div = item.select_one("div.c_abstract")
                    snippet = abstract_div.get_text().strip() if abstract_div else "No abstract"
                    
                    # 3. 尝试提取“来源”信息 (例如：知网、万方、或者是 pdf 链接)
                    # 百度学术有时候会直接给出下载链接，但更多时候在详情页里
                    # 对于 Agent，先把详情页给它，让递归爬虫进去找下载链接是更稳的策略
                    
                    results.append({
                        "title": f"[百度学术] {title}",
                        "href": detail_url, # 注意：这是中间页，需要 Hunter 进去 Deep Hunt
                        "body": snippet,
                        "source": "Baidu Xueshu"
                    })
                except:
                    continue
            return results
        except Exception as e:
            self.logger.warning(f"Baidu Xueshu Error: {e}")
            return []

    # === 4. 智能路由入口 ===
    async def _smart_search_entry(self, query: str, limit: int = 10, domain: str = "STEM"):
        """
        [Master Controller] 智能决定走哪条路。
        """
        # 检测代理
        proxy = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("ALL_PROXY")
        has_proxy = proxy is not None and len(proxy) > 0
        is_chinese = self._is_chinese_query(query)
        should_search_arxiv = (domain == "STEM") and (not is_chinese)
        all_results = []
        
        
        # 使用 impersonate="chrome110" 是最稳的
        # 如果有代理，curl_cffi 会自动读取环境变量，也可以显式传入 proxies=...
        async with AsyncSession(impersonate="chrome") as session:
            
            # --- 策略 A: 代理优先 (Google) ---
            if has_proxy:
                self.logger.info(f"🌍 Proxy detected. Attempting Google Search for: {query}")
                google_results = await self._search_google(session, query, limit)
                if google_results:
                    all_results.extend(google_results)
                else:
                    self.logger.warning("Google failed despite proxy. Falling back to Bing.")
            
            # --- 策略 B: 兜底/直连 (Bing) ---
            # 如果 Google 没搜到，或者没代理，用 Bing 补位
            if not all_results:
                self.logger.info(f"🌏 Using Bing Search (Global Mode) for: {query}")
                bing_results = await self._search_bing(session, query, limit)
                all_results.extend(bing_results)

            # --- 策略 C: 领域增强 (ArXiv) ---
            # 如果是理工科，强行注入 ArXiv 结果 (这个 API 在国内通常能直连，不行就走代理)
            if should_search_arxiv:
                self.logger.info(f"🧪 STEM domain detected. Injecting ArXiv results...")
                # ArXiv 结果少而精，取 3-5 个即可
                arxiv_results = await self._search_arxiv(session, query, limit=5)
                # 把 ArXiv 结果插到最前面！因为它们质量最高
                all_results = arxiv_results + all_results

            # === 策略 D: 中文学术增强 (百度学术) ===
            # 如果是中文搜索，且属于 STEM 或 Humanities (历史/文学更需要学术搜索)
            if is_chinese and domain in ["STEM", "HUMANITIES"]:
                self.logger.info(f"📚 Chinese Academic query detected. Injecting Baidu Xueshu results...")
                
                # 百度学术结果通常比较精准，取 3-5 个即可
                baidu_results = await self._search_baidu_xueshu(session, query, limit=5)
                
                # 插入到结果列表前面，赋予高优先级
                all_results = baidu_results + all_results

        # 简单的去重 (以 href 为 key)
        seen_urls = set()
        unique_results = []
        for r in all_results:
            if r['href'] not in seen_urls:
                seen_urls.add(r['href'])
                unique_results.append(r)
        
        self.logger.info(f"✅ Smart Search finished. Found {len(unique_results)} URLs from {[r['source'] for r in unique_results[:3]]}...")
        return unique_results[:limit] # 返回请求的数量