"""
工具函数 — URL 处理、visited 检测
"""

import re
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse


def normalize_url(url: str) -> str:
    """
    URL 归一化：移除 tracking 参数，统一格式
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        # 移除常见 tracking 参数
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "mc_cid",
            "mc_eid",
            "ref",
            "source",
            "spm",
        }

        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered = {
                k: v for k, v in params.items() if k.lower() not in tracking_params
            }
            new_query = urlencode(filtered, doseq=True)
        else:
            new_query = ""

        # 移除 trailing slash（根路径除外）
        path = parsed.path
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # 转小写 host
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=path,
            query=new_query,
            fragment="",  # 移除 fragment
        )
        return urlunparse(normalized)

    except Exception:
        return url.lower().rstrip("/")


def extract_domain(url: str) -> str:
    """从 URL 提取域名"""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return "unknown"


async def detect_visited_links(tab, browser, urls: List[str]) -> Dict[str, bool]:
    """
    通过 JS 检测浏览器原生 :visited 状态

    方法：对页面上所有 <a> 元素，检查 computed color
    visited 链接通常颜色不同（紫色 vs 蓝色）

    Args:
        tab: 浏览器标签页
        browser: BrowserAdapter 实例
        urls: 要检测的 URL 列表

    Returns:
        {url: is_visited}
    """
    result = {url: False for url in urls}

    if not urls:
        return result

    try:
        # 构造 JS：获取所有链接的 href 和 computed color
        js_code = """
        (function() {
            var links = document.querySelectorAll('a[href]');
            var results = [];
            var defaultColors = ['rgb(0, 0, 238)', 'rgb(0, 0, 255)', '#0000ee', '#0000ff',
                                 'rgb(25, 0, 255)', '#1900ff', 'rgb(26, 13, 170)', '#1a0daa'];
            for (var i = 0; i < links.length; i++) {
                var a = links[i];
                var href = a.href;
                var color = window.getComputedStyle(a).color;
                // visited links typically have different (purple-ish) color
                var isDefaultColor = false;
                for (var j = 0; j < defaultColors.length; j++) {
                    if (color === defaultColors[j]) {
                        isDefaultColor = true;
                        break;
                    }
                }
                results.push({
                    href: href,
                    color: color,
                    isDefault: isDefaultColor
                });
            }
            return JSON.stringify(results);
        })()
        """

        raw = tab.run_js(js_code)
        import json

        link_data = json.loads(raw)

        # 构建 href -> is_visited 的映射
        visited_hrefs = set()
        for item in link_data:
            if not item.get("isDefault", True):
                # 颜色不是默认蓝色，可能是 visited
                visited_hrefs.add(normalize_url(item["href"]))

        # 匹配目标 URLs
        for url in urls:
            norm = normalize_url(url)
            if norm in visited_hrefs:
                result[url] = True
            # 也检查不带 normalize 的原始匹配
            for href in visited_hrefs:
                if url in href or href in url:
                    result[url] = True
                    break

    except Exception:
        # JS 检测失败，fallback: 全部标记为未访问
        pass

    return result
