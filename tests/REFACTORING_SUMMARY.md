# Web Searcher 重构完成总结

## 重构概述

本次重构成功实现了 **Web Searcher 上下文感知链接处理** 方案,将链接选择逻辑从"阅读与导航决策分离"改为"内嵌到流式阅读过程"。

## 关键发现与架构改进

### 1. trafilatura 的真实行为

通过实际测试发现：
- ✅ **trafilatura 是正文提取器，不是格式转换器**
- ✅ 当内容足够长（像真实文章）时，trafilatura **正确生成** `[text](url)` 格式
- ❌ 当内容太短或像列表页时，trafilatura 认为是"噪音"，**丢弃链接**
- 🎯 **结论**：需要智能回退机制

### 2. 智能回退策略（HTML → Markdown）

在 `crawler_helpers.py` 的 `_html_to_full_markdown` 方法中实现：

```python
# 策略
1. 优先使用 trafilatura（智能提取正文，保留有用链接）
2. 判断回退条件：
   - 输出 < 100 字符
   - HTML 有链接但 Markdown 没有（trafilatura 误判）
3. 回退到 html2text（保真转换，保留所有链接）
```

**依赖**：需要安装 `html2text`
```bash
pip install html2text
```

### 3. Google 搜索页面特殊处理

添加预处理步骤，在 trafilatura 之前移除干扰链接：
- 移除所有 `https://translate.google.com/*` 链接（"翻译此页"按钮）
- 只对 Google 域名生效
- 使用正则表达式完全删除 `<a>` 标签

## 实施的变更

### 1. 新增 `MarkdownLinkManager` 类 (第193-304行)

**核心功能:**
- **去噪**: 自动过滤已访问和黑名单链接
- **语义化替换**: 将 `[Text](Long-URL)` 替换为 `[🔗Text]`
- **防重名**: 处理相同 Anchor Text 的情况,自动添加序号
- **信息增强**: 为无意义文本(如"点击这里")补充 URL 信息

**关键方法:**
- `process(markdown_text)`: 预处理 Markdown,建立文本到 URL 的映射
- `get_url(text)`: 根据 LLM 输出的文本获取真实 URL,带容错处理

### 2. 更新 `WebSearcherContext` 类 (第313-354行)

**新增方法:**
- `add_pending_link(url)`: 添加从流式阅读中发现的待处理链接
- `get_pending_links()`: 获取并清空待处理链接列表

**新增字段:**
- `pending_links_from_reading: List[str]`: 临时存储发现的链接

### 3. 更新 `WebSearcherPrompts.BATCH_PROCESSING` (第95-163行)

**新增内容:**
- 在 `[Current Page Content]` 部分添加链接格式说明
- 新增 `====推荐链接====` 输出格式,允许 LLM 在阅读时推荐要访问的链接
- 提供示例说明如何使用此功能

### 4. 修改 `_parse_batch_output` 方法 (第918-981行)

**变更:**
- 返回值新增 `found_links` 字段
- 解析 `====推荐链接====` 和 `====推荐链接结束====` 之间的内容
- 自动过滤示例文本("示例链接文本", "另一个链接文本")

### 5. 重构 `_stream_process_markdown` 方法 (第1001-1127行)

**核心变更:**
1. 在处理前使用 `MarkdownLinkManager` 预处理 Markdown
2. 传递 `session` 参数以支持动态添加链接到队列
3. 在每批处理完成后,检查 `found_links` 并:
   - 通过 `link_manager.get_url()` 获取真实 URL
   - 如果有 session,直接加入队列
   - 否则暂存到 `ctx.pending_links_from_reading`
4. 记录 LLM 幻觉(引用不存在的链接文本)

### 6. 优化链接扫描逻辑 (第1214-1251行)

**变更:**
- 将 `scan_elements` 的链接处理降级为只关注**功能性导航元素**
- 识别导航关键词: "next", "load more", "下一页", "加载更多"等
- 不再处理正文中的内容链接(已由流式阅读处理)
- 自动过滤已评估、已访问、在队列中、黑名单链接

### 7. 更新 `_run_search_lifecycle` 方法 (第1167-1212行)

**变更:**
- 调用 `_stream_process_markdown` 时传递 `session` 参数
- 在静态资源和交互式网页两个分支中,都处理从流式阅读发现的链接
- 将发现的链接添加到 `session.pending_link_queue`

## 测试验证

### 测试文件
1. **tests/test_markdown_link_manager.py**: 测试 `MarkdownLinkManager` 的核心功能
   - 链接清洗和替换
   - 重名处理
   - 无意义文本增强
   - URL 查询和容错

2. **tests/test_batch_parsing.py**: 测试批处理输出的解析
   - 各种标题类型的识别
   - 推荐链接的提取
   - 边界情况处理

### 测试结果
✅ 所有测试通过,无语法错误

## 预期效果

### 改进点
1. **上下文感知**: LLM 在阅读正文时可以直接决定是否访问链接,而不是在阅读结束后凭记忆猜测
2. **Token 效率**: 长URL 被替换为 `[🔗Text]`,节省上下文窗口
3. **准确性提升**: 基于周围文本的上下文做决策,减少误判
4. **效率提升**: 正文链接在流式阅读中处理,扫描阶段只关注功能性按钮

### 行为流程
1. 爬虫获取页面 Markdown
2. `MarkdownLinkManager` 将 `[详情](http://long-url...)` 替换为 `[🔗详情]`
3. LLM 阅读:"...关于2023年的业绩,请参阅 [🔗详情]..."
4. LLM 认为重要,输出:
   ```
   ##值得记录的笔记
   ...
   ====推荐链接====
   详情
   ====推荐链接结束====
   ```
5. 代码查表得 `http://long-url...`,加入队列
6. 正文读完,`scan_elements` 只寻找"下一页"等导航按钮

## 兼容性

- ✅ 向后兼容:现有代码无需修改
- ✅ 可选功能:LLM 可以选择不推荐链接
- ✅ 容错处理:LLM 幻觉的链接会被记录但不影响主流程

## 后续建议

1. **监控日志**: 关注 `🔗 Context-aware link discovered` 和 `⚠️ LLM hallucinated link text` 日志
2. **性能评估**: 对比重构前后的搜索效率和准确性
3. **Prompt 优化**: 根据实际使用情况调整链接推荐策略
4. **关键词扩展**: 根据需要添加更多导航关键词

## 文件变更

### 主要代码文件
- **src/agentmatrix/skills/web_searcher.py**: 主要重构文件
  - 新增 `MarkdownLinkManager` 类
  - 修改 `WebSearcherContext`, `WebSearcherPrompts`
  - 更新 `_parse_batch_output`, `_process_batch`, `_stream_process_markdown`, `_run_search_lifecycle`

- **src/agentmatrix/skills/crawler_helpers.py**: HTML 转换改进
  - `_html_to_full_markdown` 方法添加智能回退机制
  - 添加 Google 翻译链接预处理
  - 新增依赖：`html2text`

### 测试文件
- **tests/test_markdown_link_manager.py**: 测试 `MarkdownLinkManager` 的核心功能 ✅
- **tests/test_batch_parsing.py**: 测试批处理输出的链接解析 ✅
- **tests/test_trafilatura_params.py**: 测试 trafilatura 参数组合
- **tests/test_google_preprocess.py**: 测试 Google 预处理功能 ✅
- **tests/REFACTORING_SUMMARY.md**: 本文档

### 依赖变更
```bash
# 新增依赖
pip install html2text
```
