"""
搜索结果页解析器

专门用于解析 Google/Bing 搜索结果页的 HTML，提取结构化的搜索结果数据。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re
import base64
from urllib.parse import urlparse, unquote


@dataclass
class SearchResultItem:
    """单个搜索结果"""
    title: str
    url: str
    snippet: str
    site_info: str = ""  # 如 "www.example.com - 2 days ago"
    link_id: str = ""  # 如 "Link1 To: www.example.com"


def decode_bing_redirect_url(bing_url: str) -> Optional[str]:
    """
    解析 Bing 重定向 URL，提取真实 URL

    Bing 重定向 URL 格式：
    https://www.bing.com/ck/a?!&&p=...&u=a1aHR0cHM6Ly93d3cud2Vmb3J1bS5vcmcv...&ntb=1

    其中 u 参数的值是真实 URL 的 base64 编码（去掉前缀 "a1"）

    Args:
        bing_url: Bing 的重定向 URL

    Returns:
        真实 URL，如果解析失败则返回 None
    """
    try:
        # 提取 u 参数
        parsed = urlparse(bing_url)
        if 'bing.com' not in parsed.netloc:
            return bing_url  # 不是 Bing 重定向 URL，直接返回

        # 从查询参数中提取 u 参数
        params = dict([p.split('=', 1) if '=' in p else (p, '')
                      for p in parsed.query.split('&')])
        u_param = params.get('u', '')

        if not u_param:
            return None

        # 去掉 "a1" 前缀
        if u_param.startswith('a1'):
            u_param = u_param[2:]

        # URL decode
        u_param = unquote(u_param)

        # Base64 解码
        # 添加 padding 以确保长度是 4 的倍数
        padding = 4 - len(u_param) % 4
        if padding != 4:
            u_param += '=' * padding

        decoded_bytes = base64.b64decode(u_param)
        real_url = decoded_bytes.decode('utf-8')

        return real_url

    except Exception as e:
        # 解析失败，返回原始 URL
        return None


class SearchResultsParser:
    """
    搜索结果解析器

    支持 Google 和 Bing 搜索结果页的 HTML 解析
    """

    def __init__(self, logger=None):
        self.logger = logger
        self.should_process_url = None  # 回调函数，用于过滤URL

    def set_url_filter(self, should_process_url_func):
        """
        设置URL过滤函数

        Args:
            should_process_url_func: 回调函数，接受URL参数，返回bool
                                     True=应该处理，False=跳过
        """
        self.should_process_url = should_process_url_func

    def parse(self, html: str, url: str) -> Dict[str, Any]:
        """
        解析搜索结果页 HTML

        Args:
            html: 搜索结果页的 HTML 内容
            url: 当前页面的 URL（用于判断搜索引擎）

        Returns:
            {
                "search_engine": "google" | "bing",
                "featured_snippet": str or None,
                "results": List[SearchResultItem],
                "filtered_count": int  # 被过滤掉的搜索结果数量
            }
        """
        # 判断搜索引擎
        is_google = 'google.com/search' in url or 'www.google.' in url
        is_bing = 'bing.com/search' in url

        if is_google:
            return self._parse_google_results(html, url)
        elif is_bing:
            return self._parse_bing_results(html, url)
        else:
            self.logger.warning(f"Unknown search engine for URL: {url}")
            return {
                "search_engine": "unknown",
                "featured_snippet": None,
                "results": [],
                "filtered_count": 0
            }

    def _parse_google_results(self, html: str, url: str) -> Dict[str, Any]:
        """
        解析 Google 搜索结果

        策略：使用稳定的HTML结构特征，不依赖动态class名称
        - 搜索结果必定有 <h3> 标题
        - 标题附近必定有 <a href> 链接
        - 智能回答是较长的文本块，通常在特殊位置
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse

        soup = BeautifulSoup(html, 'html.parser')
        results = []
        featured_snippet = None
        filtered_count = 0  # 被过滤的搜索结果数量

        # 1. 提取智能回答（Featured Snippet）
        # 策略：寻找包含较长文本的div，且在前面（接近body开始）
        # 智能回答通常是独立的结构，文本长度在100-1000字符之间
        all_divs = soup.find_all('div')
        for div in all_divs[:50]:  # 只检查前50个div（智能回答通常在前面）
            text = div.get_text(strip=True)
            # 智能回答特征：
            # - 文本长度适中（100-1000字符）
            # - 包含完整的句子
            # - 不太短（不是单个词或标题）
            if 100 < len(text) < 1000:
                # 检查是否包含完整的句子（有句号或换行）
                if '.' in text or '\n' in text:
                    # 避免重复（检查是否已经被记录为featured_snippet）
                    if not featured_snippet or len(text) > len(featured_snippet):
                        # 确保这个div不是搜索结果的一部分（搜索结果通常有链接）
                        if not div.find('a'):
                            featured_snippet = text
                            self.logger.debug(f"Found featured snippet: {featured_snippet[:100]}...")
                            break

        # 2. 提取搜索结果
        # 核心策略：所有搜索结果都有 <h3> 标题
        h3_elements = soup.find_all('h3')

        self.logger.debug(f"Found {len(h3_elements)} <h3> elements")

        seen_titles = set()  # 用于去重

        for idx, h3 in enumerate(h3_elements, start=1):
            try:
                # 提取标题
                title = h3.get_text(strip=True)
                if not title or len(title) < 5:  # 过滤太短的标题
                    continue

                # 去重：避免重复处理相同标题
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                # 查找对应的链接
                result_url = None

                # 情况1: <h3><a href="...">标题</a></h3>
                link_elem = h3.find('a')
                if link_elem and link_elem.get('href'):
                    result_url = link_elem.get('href')
                else:
                    # 情况2: <a><h3>标题</h3></a>
                    parent_a = h3.find_parent('a')
                    if parent_a and parent_a.get('href'):
                        result_url = parent_a.get('href')
                    else:
                        # 情况3: h3的兄弟元素中有链接
                        parent = h3.parent
                        if parent:
                            sibling_a = parent.find('a')
                            if sibling_a and sibling_a.get('href'):
                                result_url = sibling_a.get('href')

                if not result_url or not result_url.startswith('http'):
                    continue

                # 【新增】过滤已访问/评估的URL
                if self.should_process_url and not self.should_process_url(result_url):
                    filtered_count += 1
                    self.logger.debug(f"Filtered result {idx}: {title[:50]}... (URL: {result_url})")
                    continue

                # 查找包含这个h3的搜索结果容器
                # 向上查找，找到一个包含多个子元素的div
                container = h3
                level = 0
                while container and level < 5:
                    container = container.find_parent('div')
                    if not container:
                        break
                    # 检查是否是一个合理的结果容器
                    # 应该有多个子div或有 <cite> 元素（显示URL）
                    div_count = len(container.find_all('div'))
                    has_cite = container.find('cite') is not None
                    if div_count >= 2 or has_cite:
                        break
                    level += 1

                if not container:
                    container = h3.parent

                # 从容器中提取摘要和站点信息
                snippet = ""
                site_info = ""

                if container:
                    # 提取站点信息（优先从 <cite> 元素）
                    cite_elem = container.find('cite')
                    if cite_elem:
                        cite_text = cite_elem.get_text(strip=True)
                        # 清理cite文本，移除URL路径，只保留域名
                        if '›' in cite_text:
                            site_info = cite_text.split('›')[0].strip()
                        elif '/' in cite_text:
                            site_info = cite_text.split('/')[0].strip()
                        else:
                            site_info = cite_text

                        # 如果cite包含完整URL，提取域名
                        if site_info.startswith('http'):
                            parsed = urlparse(site_info)
                            site_info = parsed.netloc

                    if not site_info:
                        # 尝试从URL提取域名
                        parsed = urlparse(result_url)
                        site_info = parsed.netloc if parsed.netloc else ""

                    # 提取摘要
                    # 策略：查找包含较长纯文本的span或div，避免包含链接cite元素
                    # 摘要通常在特定结构的span中，不包含其他HTML元素
                    for elem in container.find_all(['span', 'div']):
                        # 跳过cite元素和包含链接的元素
                        if elem.name == 'cite' or elem.find('a') or elem.find('cite'):
                            continue

                        text = elem.get_text(strip=True)
                        # 摘要特征：
                        # - 长度适中（50-600字符）
                        # - 不是标题本身
                        # - 不是纯URL或域名
                        # - 包含完整句子
                        if 50 < len(text) < 600:
                            # 避免URL、域名等
                            text_lower = text.lower()
                            if not any(skip in text_lower for skip in [
                                'translate', 'translation', 'cookie', 'privacy',
                                'sign in', 'login', 'skip to', 'http', 'https',
                                'www.', '.com', '.org', '.net'
                            ]):
                                # 检查是否包含有意义的文本内容（字母比例高）
                                alpha_ratio = sum(c.isalpha() or c.isspace() for c in text) / len(text)
                                if alpha_ratio > 0.7:  # 至少70%是字母或空格
                                    snippet = text
                                    break

                # 生成链接ID
                site_name = site_info.split(' ›')[0].strip() if site_info else urlparse(result_url).netloc
                link_id = f"Link{idx} To: {site_name}"

                result = SearchResultItem(
                    title=title,
                    url=result_url,
                    snippet=snippet,
                    site_info=site_info,
                    link_id=link_id
                )
                results.append(result)

                self.logger.debug(f"Parsed result {idx}: {title[:50]}...")

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to parse h3 element: {e}")
                continue

        self.logger.info(f"✓ Parsed {len(results)} Google search results")
        if filtered_count > 0:
            self.logger.info(f"  ↳ Filtered {filtered_count} already visited/evaluated results")

        # 查找"下一页"链接（传入当前页面 URL 用于处理相对路径）
        next_page_url = self._find_next_page_link(soup, url)
        if next_page_url:
            # 将"下一页"作为一个特殊的搜索结果追加到列表中
            results.append(SearchResultItem(
                title="→ 下一页",
                url=next_page_url,
                snippet="点击查看更多搜索结果",
                site_info="",
                link_id="翻页: 下一页"
            ))
            self.logger.info(f"✓ Found next page link: {next_page_url}")

        return {
            "search_engine": "google",
            "featured_snippet": featured_snippet,
            "results": results,
            "filtered_count": filtered_count
        }

    def _parse_bing_results(self, html: str, url: str) -> Dict[str, Any]:
        """
        解析 Bing 搜索结果

        Bing 搜索结果结构：
        - <li class="b_algo"> 单个搜索结果
        - <h2><a href="...">标题</a></h2>
        - <div class="b_caption"> 摘要
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse

        soup = BeautifulSoup(html, 'html.parser')
        results = []
        featured_snippet = None
        filtered_count = 0  # 被过滤的搜索结果数量

        # 1. 提取智能回答（Bing 可能没有明显的 Featured Snippet）
        # 暂时跳过

        # 2. 提取搜索结果
        result_items = soup.find_all('li', class_='b_algo')

        for idx, item in enumerate(result_items, start=1):
            try:
                # 查找标题和链接
                # 结构：<h2><a href="...">标题</a></h2>
                h2 = item.find('h2')
                if not h2:
                    continue

                link_elem = h2.find('a')
                if not link_elem or not link_elem.get('href'):
                    continue

                result_url = link_elem.get('href')
                title = link_elem.get_text(strip=True)

                # 尝试解析 Bing 重定向 URL
                real_url = decode_bing_redirect_url(result_url)
                if real_url:
                    result_url = real_url

                # 【新增】过滤已访问/评估的URL
                if self.should_process_url and not self.should_process_url(result_url):
                    filtered_count += 1
                    self.logger.debug(f"Filtered result {idx}: {title[:50]}... (URL: {result_url})")
                    continue

                # 提取摘要
                caption_div = item.find('div', class_='b_caption')
                snippet = ""
                site_info = ""

                if caption_div:
                    # 提取描述文本
                    # 通常在 <p> 或 <div> 中
                    p_elem = caption_div.find('p')
                    if p_elem:
                        # 获取纯文本，但排除某些元信息
                        snippet_parts = []
                        for child in p_elem.children:
                            if hasattr(child, 'name') and child.name in ['span', 'cite']:
                                continue
                            if hasattr(child, 'get_text'):
                                text = child.get_text(strip=True)
                                if text:
                                    snippet_parts.append(text)
                        snippet = ' '.join(snippet_parts)

                    # 提取站点信息（通常是 <cite> 标签）
                    cite_elem = caption_div.find('cite')
                    if cite_elem:
                        site_info = cite_elem.get_text(strip=True)

                # 如果没有站点信息，从真实URL提取域名
                if not site_info:
                    parsed_url = urlparse(result_url)
                    site_info = parsed_url.netloc if parsed_url.netloc else ""

                # 生成链接ID（使用真实URL的域名）
                parsed_url = urlparse(result_url)
                site_name = parsed_url.netloc if parsed_url.netloc else (site_info.split(' ')[0] if site_info else "unknown")
                link_id = f"Link{idx} To: {site_name}"

                result = SearchResultItem(
                    title=title,
                    url=result_url,
                    snippet=snippet,
                    site_info=site_info,
                    link_id=link_id
                )
                results.append(result)

            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Failed to parse a Bing search result: {e}")
                continue

        self.logger.info(f"✓ Parsed {len(results)} Bing search results")
        if filtered_count > 0:
            self.logger.info(f"  ↳ Filtered {filtered_count} already visited/evaluated results")

        # 查找"下一页"链接（传入当前页面 URL 用于处理相对路径）
        next_page_url = self._find_next_page_link(soup, url)
        if next_page_url:
            # 将"下一页"作为一个特殊的搜索结果追加到列表中
            results.append(SearchResultItem(
                title="→ 下一页",
                url=next_page_url,
                snippet="点击查看更多搜索结果",
                site_info="",
                link_id="翻页: 下一页"
            ))
            self.logger.info(f"✓ Found next page link: {next_page_url}")

        return {
            "search_engine": "bing",
            "featured_snippet": featured_snippet,
            "results": results,
            "filtered_count": filtered_count
        }

    def format_as_markdown(self, parsed_data: Dict[str, Any]) -> str:
        """
        将解析结果格式化为 Markdown

        Args:
            parsed_data: parse() 返回的数据

        Returns:
            格式化的 Markdown 文本
        """
        lines = []

        # 1. 智能回答（如果有）
        if parsed_data.get("featured_snippet"):
            lines.append("# 智能回答")
            lines.append("")
            lines.append(parsed_data["featured_snippet"])
            lines.append("")
            lines.append("")

        # 2. 搜索结果列表
        results = parsed_data.get("results", [])
        if not results:
            return "# 未找到搜索结果\n\n"

        lines.append(f"# 搜索结果 (共 {len(results)} 条)")
        lines.append("")

        for idx, result in enumerate(results, start=1):
            # 链接ID
            link_id = result.link_id
            lines.append(f"[🔗{link_id}]")
            lines.append(f"**{result.title}**")

            # 站点信息（如果有）
            if result.site_info:
                lines.append(f"*{result.site_info}*")

            # 摘要（如果有）
            if result.snippet:
                lines.append(result.snippet)

            # 空行分隔
            lines.append("")

        return "\n".join(lines)

    def build_link_mapping(self, parsed_data: Dict[str, Any]) -> Dict[str, str]:
        """
        构建链接ID到URL的映射

        Args:
            parsed_data: parse() 返回的数据

        Returns:
            {"Link1 To: www.example.com": "https://www.example.com/..."}
        """
        mapping = {}
        for result in parsed_data.get("results", []):
            if result.link_id:
                mapping[result.link_id] = result.url
        return mapping

    def _find_next_page_link(self, soup, base_url: str) -> Optional[str]:
        """
        查找"下一页"链接

        Args:
            soup: BeautifulSoup 对象
            base_url: 当前页面的 URL（用于处理相对路径）

        Returns:
            下一页的 URL，如果没找到则返回 None
        """
        try:
            all_links = soup.find_all('a')

            for link in all_links:
                text = link.get_text(strip=True)
                aria_label = link.get('aria-label', '')

                href = link.get('href', '')
                if not href:
                    continue

                # 判断是否是"下一页"链接
                is_next = (
                    'next' in text.lower() or
                    'next' in aria_label.lower() or
                    '下一页' in text or
                    '下一页' in aria_label
                )

                if not is_next:
                    continue

                # 处理相对路径
                if href.startswith('/'):
                    # 相对路径，拼接 base URL
                    try:
                        parsed_base = urlparse(base_url)
                        absolute_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                        href = absolute_url
                    except Exception:
                        continue

                # Bing: 解码重定向 URL
                real_url = decode_bing_redirect_url(href)
                if real_url:
                    href = real_url

                # 确保最终是 http/https URL
                if not href.startswith('http'):
                    continue

                return href

        except Exception as e:
            if self.logger:
                self.logger.warning(f"Failed to find next page link: {e}")

        return None  # 没有找到"下一页"链接
