"""
页面处理模块 — 内容提取、结构分析、preview 生成、分批
"""

import re
import asyncio
from typing import List, Dict, Any, Optional


async def extract_markdown(tab, browser, url: str = None) -> str:
    """
    从页面提取 Markdown，自动识别 HTML/PDF

    策略：
    - trafilatura 优先（智能提取正文）
    - html2text 兜底
    - PDF 使用 marker 转换

    Args:
        tab: 浏览器标签页
        browser: BrowserAdapter 实例
        url: 页面 URL（可选，用于 PDF 处理）
    """
    from ...core.browser.browser_adapter import PageType

    content_type = await browser.analyze_page_type(tab)

    if content_type == PageType.STATIC_ASSET:
        return await _pdf_to_markdown(tab, browser, url)
    else:
        return await _html_to_markdown(tab, browser)


async def _html_to_markdown(tab, browser) -> str:
    """
    HTML → Markdown
    trafilatura 优先，html2text 兜底
    """
    import trafilatura
    import html2text

    raw_html = tab.html
    url = browser.get_tab_url(tab)

    # trafilatura 提取正文
    markdown = trafilatura.extract(
        raw_html,
        include_links=True,
        include_formatting=True,
        output_format="markdown",
        url=url,
    )

    # 回退：trafilatura 失败或内容太少
    if not markdown or len(markdown.strip()) < 150:
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = False
        converter.body_width = 0
        converter.ignore_emphasis = False
        markdown = converter.handle(raw_html)

    return markdown or ""


async def _pdf_to_markdown(tab, browser, original_url: str = None) -> str:
    """
    PDF → Markdown（使用 marker）
    """
    import asyncio as aio

    pdf_path = await browser.save_static_asset(tab, original_url)

    # 修复可能卡在 PDF viewer 的 tab
    current_url = tab.url if hasattr(tab, "url") else ""
    if current_url.startswith("chrome-extension://"):
        await browser.navigate(tab, "about:blank")
        await aio.sleep(0.5)

    # 在线程池中执行 PDF 转换
    markdown = await aio.to_thread(_convert_pdf, pdf_path)
    return markdown


def _convert_pdf(pdf_path: str) -> str:
    """PDF 转换核心实现"""
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered

    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(pdf_path)
    text, _, _ = text_from_rendered(rendered)
    return text


def analyze_page_structure(markdown: str) -> Dict[str, Any]:
    """
    分析页面结构

    Returns:
        {
            "title": str,
            "sections": [str],       # h1-h3 标题列表
            "total_chars": int,
            "link_count": int,
            "has_tables": bool,
            "has_code": bool,
            "language": str
        }
    """
    lines = markdown.split("\n")

    # 提取标题
    title = "未命名文档"
    sections = []
    for line in lines:
        match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if match:
            heading_text = match.group(2).strip()
            if len(match.group(1)) == 1 and title == "未命名文档":
                title = heading_text
            sections.append(heading_text)

    # 统计
    total_chars = len(markdown)
    link_count = len(re.findall(r"\[([^\]]*)\]\([^)]+\)", markdown))
    has_tables = "|" in markdown and "---" in markdown
    has_code = "```" in markdown

    # 语言检测（简单）
    chinese_chars = len([c for c in markdown if "\u4e00" <= c <= "\u9fff"])
    if chinese_chars > total_chars * 0.1:
        language = "zh" if chinese_chars > total_chars * 0.3 else "mixed"
    else:
        language = "en"

    return {
        "title": title,
        "sections": sections[:20],  # 最多返回20个
        "total_chars": total_chars,
        "link_count": link_count,
        "has_tables": has_tables,
        "has_code": has_code,
        "language": language,
    }


def generate_preview(markdown: str, max_chars: int = 2000) -> str:
    """
    生成内容预览

    策略：
    1. 找第一个 h1/h2 标题
    2. 从该标题开始截取 max_chars 字符
    3. 如果没有标题，直接截取前 max_chars
    4. 确保不在段落中间截断
    """
    if not markdown:
        return ""

    lines = markdown.split("\n")
    start_idx = 0

    # 找第一个标题
    for i, line in enumerate(lines):
        if re.match(r"^#{1,2}\s+", line):
            start_idx = i
            break

    # 从 start_idx 开始累积
    result_lines = []
    total = 0
    for line in lines[start_idx:]:
        total += len(line) + 1
        if total > max_chars:
            # 尝试在段落边界截断
            if line.strip() == "":
                break
            result_lines.append(line)
            break
        result_lines.append(line)

    preview = "\n".join(result_lines)

    # 如果还是太长，硬截断
    if len(preview) > max_chars + 500:
        preview = preview[:max_chars] + "\n\n... (内容截断)"

    return preview


def split_into_batches(markdown: str, threshold: int = 32000) -> List[str]:
    """
    按段落边界将文本分段，每段 <= threshold 字符
    """
    if len(markdown) <= threshold:
        return [markdown]

    paragraphs = markdown.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        test_chunk = current_chunk + ("\n\n" if current_chunk else "") + para

        if len(test_chunk) <= threshold:
            current_chunk = test_chunk
        else:
            if current_chunk:
                chunks.append(current_chunk)

            # 单个段落超过阈值，按句子细分
            if len(para) > threshold:
                sentences = re.split(r"(?<=[。.!！?？])\s*", para)
                temp_chunk = ""
                for sent in sentences:
                    test_sent = temp_chunk + sent
                    if len(test_sent) <= threshold:
                        temp_chunk = test_sent
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk)
                        temp_chunk = sent
                current_chunk = temp_chunk
            else:
                current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
