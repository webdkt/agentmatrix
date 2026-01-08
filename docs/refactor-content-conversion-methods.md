# 内容转换方法重构计划

**创建日期**: 2025-01-08
**状态**: 📝 计划中

---

## 1. 概述

### 重构目标
将 `web_searcher.py` 中的内容转换类方法迁移到 `crawler_helpers.py`，同时将 PDF 转换实现从 `report_writer_utils.py` 集成进来，让 `crawler_helpers` 更加自包含。

**核心收益**:
- 减少 150+ 行重复代码
- 统一 HTML/PDF 转 Markdown 的处理逻辑
- 不再依赖外部模块的 `pdf_to_markdown` import

### 重构范围
**迁移方法**:
1. `_get_full_page_markdown()` - 统一入口，自动识别 HTML/PDF
2. `_html_to_full_markdown()` - HTML 转 Markdown（使用 trafilatura）
3. `_pdf_to_full_markdown()` - PDF 转 Markdown（调用内部方法）
4. `_convert_pdf_to_markdown_text()` - PDF 转换的核心实现（从 report_writer_utils 迁移）

---

## 2. 当前状态

### 源文件：web_searcher.py

**位置**: `src/agentmatrix/skills/web_searcher.py:409-465`

```python
async def _get_full_page_markdown(self, tab: TabHandle, ctx: WebSearcherContext) -> str:
    content_type = await self.browser.analyze_page_type(tab)
    if content_type == PageType.STATIC_ASSET:
        return await self._pdf_to_full_markdown(tab, ctx)
    else:
        return await self._html_to_full_markdown(tab)

async def _html_to_full_markdown(self, tab: TabHandle) -> str:
    import trafilatura
    raw_html = tab.html
    url = self.browser.get_tab_url(tab)
    markdown = trafilatura.extract(raw_html, include_links=True,
                                    include_formatting=True,
                                    output_format='markdown', url=url)
    if not markdown or len(markdown) < 50:
        markdown = tab.text
    return markdown or ""

async def _pdf_to_full_markdown(self, tab: TabHandle, ctx: WebSearcherContext) -> str:
    from skills.report_writer_utils import pdf_to_markdown
    pdf_path = await self.browser.save_static_asset(tab)
    markdown = pdf_to_markdown(pdf_path)
    if ctx.temp_file_dir:
        # 保存临时文件...
    return markdown
```

**被调用位置**:
- `web_searcher.py:1048` - 静态资源分支
- `web_searcher.py:1068` - 交互式网页分支

### PDF 转换实现：report_writer_utils.py

**位置**: `src/agentmatrix/skills/report_writer_utils.py:185-257`

```python
def pdf_to_markdown(pdf_path, start_page=None, end_page=None, lang=None):
    """使用 marker 库将 PDF 转换为 Markdown"""
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    import fitz

    # 获取总页数，处理页面范围...
    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(pdf_to_convert)
    text, _, images = text_from_rendered(rendered)
    return text
```

### 目标文件：crawler_helpers.py

**位置**: `src/agentmatrix/skills/crawler_helpers.py`

**现有内容**: `CrawlerHelperMixin` 类（3 个方法）
- `_filter_relevant_links()` - 批量筛选链接
- `_choose_best_interaction()` - 选择最佳按钮
- `_evaluate_button_batch()` - 评估按钮批次

---

## 3. 重构方案

### 实施方案

**更新 crawler_helpers.py**:

```python
# 在文件顶部添加导入
from ..core.browser.browser_adapter import PageType

class CrawlerHelperMixin:
    """爬虫技能的公共辅助方法 Mixin"""

    # ... 现有方法保持不变 ...

    async def _get_full_page_markdown(self, tab, ctx) -> str:
        """
        获取完整页面的 Markdown，自动识别 HTML/PDF

        Args:
            tab: 浏览器标签页句柄
            ctx: 上下文对象（可选，用于临时文件保存）

        Returns:
            str: Markdown 格式的页面内容
        """
        content_type = await self.browser.adapter.analyze_page_type(tab)

        if content_type == PageType.STATIC_ASSET:
            return await self._pdf_to_full_markdown(tab, ctx)
        else:
            return await self._html_to_full_markdown(tab)

    async def _html_to_full_markdown(self, tab) -> str:
        """
        将 HTML 页面转换为完整 Markdown

        Args:
            tab: 浏览器标签页句柄

        Returns:
            str: Markdown 格式的页面内容
        """
        import trafilatura

        raw_html = tab.html
        url = self.browser.adapter.get_tab_url(tab)

        markdown = trafilatura.extract(
            raw_html,
            include_links=True,
            include_formatting=True,
            output_format='markdown',
            url=url
        )

        # 降级方案：如果 trafilatura 失败，使用纯文本
        if not markdown or len(markdown) < 50:
            markdown = tab.text

        return markdown or ""

    async def _pdf_to_full_markdown(self, tab, ctx) -> str:
        """
        将 PDF 转换为完整 Markdown

        Args:
            tab: 浏览器标签页句柄
            ctx: 上下文对象（可选，用于临时文件保存）

        Returns:
            str: Markdown 格式的 PDF 内容
        """
        # 下载 PDF 到本地
        pdf_path = await self.browser.adapter.save_static_asset(tab)

        # 调用 PDF 转换（在线程池中执行，避免阻塞）
        import asyncio
        markdown = await asyncio.to_thread(
            self._convert_pdf_to_markdown_text,
            pdf_path
        )

        # 可选：保存到临时文件（如果 ctx 支持）
        if hasattr(ctx, 'temp_file_dir') and ctx.temp_file_dir:
            self._save_temp_markdown(markdown, pdf_path, ctx.temp_file_dir)

        return markdown

    def _convert_pdf_to_markdown_text(self, pdf_path: str) -> str:
        """
        将 PDF 文件转换为 Markdown 文本（核心实现）

        Args:
            pdf_path: PDF 文件路径

        Returns:
            str: Markdown 格式的文本

        Raises:
            Exception: PDF 转换失败
        """
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
        import fitz

        try:
            # 获取 PDF 总页数
            with fitz.open(pdf_path) as doc:
                total_pages = len(doc)

            self.logger.debug(f"PDF总页数: {total_pages}")

            # 初始化 marker 模型
            self.logger.debug("加载 marker 模型...")
            converter = PdfConverter(
                artifact_dict=create_model_dict(),
            )

            # 执行转换
            self.logger.debug("正在转换 PDF 到 Markdown...")
            rendered = converter(pdf_path)

            # 从渲染结果中提取文本
            text, _, images = text_from_rendered(rendered)

            self.logger.debug(f"转换完成! 共 {len(text)} 个字符")

            return text

        except Exception as e:
            self.logger.error(f"PDF 转换失败: {e}")
            raise

    def _save_temp_markdown(self, markdown: str, pdf_path: str, temp_dir: str):
        """
        保存临时 Markdown 文件（用于调试）

        Args:
            markdown: Markdown 文本
            pdf_path: 原始 PDF 路径
            temp_dir: 临时目录
        """
        import os
        from slugify import slugify

        os.makedirs(temp_dir, exist_ok=True)
        filename = slugify(f"pdf_{os.path.basename(pdf_path)}") + ".md"
        temp_path = os.path.join(temp_dir, filename)

        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        self.logger.info(f"📄 保存临时 Markdown: {temp_path}")
```

**更新 web_searcher.py**:

删除 `web_searcher.py:409-465` 的三个方法，所有调用保持不变。

---

## 4. 实施步骤

### 前置要求：创建 Git Tag

```bash
# 1. 确保工作区干净
git status

# 2. 如有未提交更改，先提交
git add .
git commit -m "WIP: before content conversion refactor"

# 3. 创建标签
git tag -a refactor/pre-content-conversion -m "Before refactoring content conversion methods"

# 4. 验证并推送
git show refactor/pre-content-conversion --stat
git push origin refactor/pre-content-conversion
```

### 步骤 1: 更新 crawler_helpers.py

```bash
# 编辑文件，添加四个方法
vim src/agentmatrix/skills/crawler_helpers.py

# 语法检查
python -m py_compile src/agentmatrix/skills/crawler_helpers.py

# 导入检查
python -c "from agentmatrix.skills.crawler_helpers import CrawlerHelperMixin; print('✓ Import OK')"
```

### 步骤 2: 更新 web_searcher.py

```bash
# 删除三个方法（行 409-465）
vim src/agentmatrix/skills/web_searcher.py

# 语法检查
python -m py_compile src/agentmatrix/skills/web_searcher.py

# 导入检查
python -c "from agentmatrix.skills.web_searcher import WebSearcherMixin; print('✓ Import OK')"
```

### 步骤 3: 提交更改

```bash
# 查看改动
git diff

# 提交
git add .
git commit -m "Refactor: Move content conversion methods to crawler_helpers

- Move _get_full_page_markdown() from web_searcher to crawler_helpers
- Move _html_to_full_markdown() from web_searcher to crawler_helpers
- Move _pdf_to_full_markdown() from web_searcher to crawler_helpers
- Add _convert_pdf_to_markdown_text() to crawler_helpers (from report_writer_utils)
- Remove duplicate code in web_searcher.py (~150 lines)
- Make crawler_helpers self-contained for PDF conversion

See docs/refactor-content-conversion-methods.md for details"

# 创建后置标签
git tag -a refactor/post-content-conversion -m "After refactoring content conversion methods"

# 推送
git push origin main
git push origin refactor/post-content-conversion
```

### 步骤 4: 验证

**测试用例 1**: HTML 搜索
```python
from agentmatrix.agents.digital_intern import DigitalIntern

agent = DigitalIntern()
result = await agent.web_search(
    purpose="什么是 Python？",
    search_phrase="Python programming",
    max_time=2,
    max_search_pages=1
)
```

**测试用例 2**: PDF 处理
```python
result = await agent.web_search(
    purpose="查找 PDF 文档",
    search_phrase="example.com filetype:pdf",
    max_time=2
)
```

**验证点**:
- ✅ HTML 转 Markdown 正常
- ✅ PDF 转 Markdown 正常
- ✅ 无导入错误
- ✅ 无明显性能下降

---

## 5. 依赖清单

**新增依赖** (crawler_helpers.py):
- `trafilatura` - HTML 解析
- `marker.converters.pdf.PdfConverter` - PDF 转换
- `marker.models.create_model_dict` - 模型加载
- `marker.output.text_from_rendered` - 文本提取
- `fitz` (PyMuPDF) - PDF 信息读取

**现有依赖**:
- `PageType` (from `core.browser.browser_adapter`)
- `slugify` - 文件名处理

**检查依赖**:
```bash
pip list | grep -E "trafilatura|marker|PyMuPDF|slugify"
```

---

## 6. 后续优化建议

1. **模型缓存**: marker 模型可以全局缓存，避免每次转换都重新加载
2. **更多降级策略**: 为 PDF 添加更多转换方案（如 pdfplumber）
3. **配置化**: 允许自定义转换参数
4. **性能监控**: 添加转换时间统计
5. **扩展到 data_crawler**: 让 data_crawler 也使用这些方法

---

**文档版本**: 1.0
**最后更新**: 2025-01-08
