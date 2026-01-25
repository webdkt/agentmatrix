# Think-With-Retry 模式

## 概述

Think-With-Retry 模式是一个健壮的机制，用于调用 LLM 并从自然语言响应中提取结构化输出。它处理验证、错误反馈和自动重试，确保可靠地解析 LLM 输出。

## LLM 客户端封装

**位置**: `src/agentmatrix/backends/llm_client.py`

`LLMClient` 类为与各种 LLM 提供商(OpenAI、Gemini 等)交互提供统一接口。

### 核心功能

```python
class LLMClient(AutoLoggerMixin):
    def __init__(self, url: str, api_key: str, model_name: str):
        self.url = url
        self.api_key = api_key
        self.model_name = model_name

    async def think(self, messages: List[Dict]) -> Dict[str, str]:
        """
        调用 LLM 并返回包含推理和回复的响应

        返回:
            {
                "reasoning": "思维链(如果有)",
                "reply": "主要响应内容"
            }
        """
```

### 异步流式支持

客户端支持 OpenAI 和 Gemini API 的异步流式响应:

**OpenAI 流式** (268-335行):

```python
async def _stream_openai_response(self, messages, model):
    async for chunk in openai_completion.stream(...):
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content
```

**Gemini 流式** (170-266行):

```python
async def _stream_gemini_response(self, messages, model):
    async for chunk in await gemini_model.generate_content_async(...):
        yield chunk.text
```

### 推理内容提取

对于支持思维链的模型(如 o1)，客户端提取推理内容:

```python
# 从 o1 模型提取推理
if hasattr(response, 'reasoning') and response.reasoning:
    reasoning = response.reasoning
else:
    reasoning = None

return {
    "reasoning": reasoning,
    "reply": content
}
```

## Think-With-Retry 模式

**位置**: `src/agentmatrix/backends/llm_client.py` (33-105行)

`think_with_retry()` 方法实现了一个通用的微 Agent，循环直到 LLM 输出成功解析。

### 核心机制

```python
async def think_with_retry(
    self,
    initial_messages: Union[str, List[str]],
    parser: callable,          # 解析器函数
    max_retries: int = 3,
    **parser_kwargs
) -> any:
    """
    通用微 Agent，循环直到 LLM 输出成功解析

    参数:
        initial_messages: 初始用户消息
        parser: 用于提取结构化输出的解析器
        max_retries: 最大重试次数
        **parser_kwargs: 解析器的额外参数

    返回:
        解析的数据(来自 parser["data"] 或 parser["sections"])
    """
    messages = self._prepare_messages(initial_messages)

    for attempt in range(max_retries):
        # 1. 调用 LLM
        response = await self.think(messages=messages)
        raw_reply = response['reply']

        # 2. 使用提供的解析器解析
        parsed_result = parser(raw_reply, **parser_kwargs)

        # 3. 检查结果
        if parsed_result.get("status") == "success":
            # 成功 - 返回数据
            return (
                parsed_result.get("data") or
                parsed_result.get("sections")
            )

        elif parsed_result.get("status") == "error":
            # 4. 添加反馈并重试
            feedback = parsed_result.get("feedback")
            messages.append({
                "role": "assistant",
                "content": raw_reply
            })
            messages.append({
                "role": "user",
                "content": feedback
            })
            # 带反馈继续循环

    # 超过最大重试次数
    raise Exception(f"超过最大重试次数 ({max_retries})")
```

### 解析器契约

解析器必须遵循此接口:

```python
def parser(raw_reply: str, **kwargs) -> dict:
    """
    解析 LLM 输出并返回状态字典

    返回:
        {
            "status": "success" | "error",
            "data": ...,              # 可选: 单个解析数据
            "sections": {...},        # 可选: 多个部分
            "feedback": str           # status=error 时必需
        }
    """
```

**成功响应**:

```python
{
    "status": "success",
    "data": "解析结果"              # 单个值
    # 或
    "sections": {                  # 多部分
        "第1部分": "内容1",
        "第2部分": "内容2"
    }
}
```

**错误响应**:

```python
{
    "status": "error",
    "feedback": "缺少必填字段: [行动计划]。请包含此部分。"
}
```

### 重试流程

```
┌─────────────────────────────────────────────┐
│  1. 使用消息调用 LLM                        │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  2. 解析输出        │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  状态 = success?    │
        └─────────┬───────────┘
             │    │
      是      │    │   否
             ▼    │
    ┌────────────┐ │
    │ 返回       │ │
    │ data       │ │
    └────────────┘ │
                  │
                  ▼
        ┌─────────────────────┐
        │  3. 添加反馈        │
        │     到消息          │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │  4. 重试 LLM 调用   │
        └─────────┬───────────┘
                  │
                  └──────► 循环回步骤 1
```

### 使用示例

```python
# 定义解析器
def extract_plan(raw_reply: str) -> dict:
    if "[研究计划]" not in raw_reply:
        return {
            "status": "error",
            "feedback": "缺少 [研究计划] 部分。请包含它。"
        }
    # 提取内容
    content = raw_reply.split("[研究计划]")[1].strip()
    return {
        "status": "success",
        "data": content
    }

# 使用 think_with_retry
result = await llm_client.think_with_retry(
    initial_messages="创建一个 AI 安全的研究计划",
    parser=extract_plan,
    max_retries=3
)

# result 包含解析的计划
```

## 解析器设计

### 解析器签名

```python
def parser(
    raw_reply: str,
    **kwargs  # 解析器特定参数
) -> dict:
    # 实现
    pass
```

### 错误报告

解析器应提供具体、可操作的反馈:

```python
# 坏例子
return {
    "status": "error",
    "feedback": "解析失败"  # 没有帮助
}

# 好例子
return {
    "status": "error",
    "feedback": "缺少必需部分: [研究计划]。"
                "请使用此部分标题格式化您的响应。"
}
```

### 解析器最佳实践

1. **具体化**: 准确告诉 LLM 错误在哪里
2. **提供示例**: 在反馈中展示预期格式
3. **检查要求**: 验证所有必填字段
4. **处理边界情况**: 空输出、格式错误的内容等

## 多部分解析器

**位置**: `src/agentmatrix/skills/parser_utils.py` (10-186行)

`multi_section_parser()` 是一个强大的工具，用于从 LLM 输出中提取多个部分。

### 函数签名

```python
def multi_section_parser(
    raw_reply: str,
    section_headers: List[str] = None,
    regex_mode: bool = False,
    match_mode: str = "ALL"  # 或 "ANY"
) -> dict
```

### 两种操作模式

#### 1. 多部分模式

当提供 `section_headers` 时:

```python
text = """
[研究计划]
1. AI 安全文献综述
2. 采访专家
3. 进行实验

[章节大纲]
第1章: 简介
第2章: 背景
第3章: 方法论
"""

result = multi_section_parser(
    text,
    section_headers=['[研究计划]', '[章节大纲]'],
    match_mode="ALL"  # 所有标题必须存在
)

# 返回:
{
    "status": "success",
    "sections": {
        "[研究计划]": "1. AI 安全文献综述\n2. 采访专家\n3. 进行实验",
        "[章节大纲]": "第1章: 简介\n第2章: 背景\n第3章: 方法论"
    }
}
```

**匹配模式**:
- `"ALL"`: 所有指定的标题必须存在(默认)
- `"ANY"`: 至少一个标题必须存在

**错误示例**:

```python
# 缺少 [章节大纲]
result = multi_section_parser(
    text,
    section_headers=['[研究计划]', '[章节大纲]'],
    match_mode="ALL"
)

# 返回:
{
    "status": "error",
    "feedback": "缺少必需的部分: ['[章节大纲]']"
}
```

#### 2. 单部分模式

当 `section_headers` 为 `None` 时(向后兼容):

```python
text = """
一些介绍文本...
===========
要提取的内容
更多内容...
===========

页脚文本
"""

result = multi_section_parser(text)

# 返回:
{
    "status": "success",
    "data": "要提取的内容\n更多内容..."
}
```

查找最后一个 `"====="` 分隔符并提取它和下一个分隔符之间的内容。

### 性能优化

解析器包含几个效率优化:

**1. 反向迭代** (101-136行):

```python
# 从文本末尾向后迭代
for i in range(len(lines) - 1, -1, -1):
    line = lines[i]
    # 检查部分标题
    # ...
```

优势:
- 更快找到内容(通常在末尾附近)
- 启用提前终止

**2. 提前终止** (132行):

```python
if len(found_sections) == len(required_headers):
    break  # 找到所有部分
```

一旦找到所有必需部分就停止搜索。

**3. 快速预检查** (89-94行):

```python
if match_mode == "ALL":
    # 快速检查所有标题是否存在
    for header in section_headers:
        if header not in raw_reply:
            return {
                "status": "error",
                "feedback": f"缺少必需部分: {header}"
            }
```

如果标题缺失则避免昂贵的迭代。

### 实现细节

```python
def multi_section_parser(
    raw_reply: str,
    section_headers: List[str] = None,
    regex_mode: bool = False,
    match_mode: str = "ALL"
) -> dict:
    # 单部分模式
    if section_headers is None:
        # 查找最后一个 "=====" 分隔符
        divider_count = raw_reply.count("=====")
        if divider_count < 2:
            return {"status": "error", "feedback": "未找到内容分隔符"}

        # 提取最后两个分隔符之间的内容
        parts = raw_reply.split("=====")
        content = parts[-2].strip()
        return {"status": "success", "data": content}

    # 多部分模式
    if match_mode == "ALL":
        # 快速预检查
        for header in section_headers:
            if header not in raw_reply:
                return {
                    "status": "error",
                    "feedback": f"缺少必需部分: {header}"
                }

    # 反向迭代以提取部分
    lines = raw_reply.split('\n')
    found_sections = {}

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()

        # 检查行是否为部分标题
        if line in section_headers:
            # 提取内容直到下一个标题
            content = []
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if next_line in section_headers:
                    break
                content.append(lines[j])

            found_sections[line] = '\n'.join(content).strip()

            # 提前终止
            if match_mode == "ALL" and len(found_sections) == len(section_headers):
                break

    # 验证结果
    if match_mode == "ALL" and len(found_sections) != len(section_headers):
        return {
            "status": "error",
            "feedback": f"缺少部分: {set(section_headers) - set(found_sections.keys())}"
        }

    if match_mode == "ANY" and len(found_sections) == 0:
        return {
            "status": "error",
            "feedback": "未找到任何部分"
        }

    return {
        "status": "success",
        "sections": found_sections
    }
```

## 示例: 搜索结果解析器

**位置**: `src/agentmatrix/skills/search_results_parser.py`

一个自定义解析器的实际例子，用于从 HTML 搜索结果中提取结构化数据。

### 数据结构

```python
@dataclass
class SearchResultItem:
    title: str       # 结果标题
    url: str         # 结果 URL
    snippet: str     # 结果摘要
    site_info: str   # 站点信息
    link_id: str     # 唯一链接 ID
```

### 解析器功能

```python
def parse_search_results(html_content: str) -> dict:
    """
    解析 HTML 搜索结果(Google/Bing)

    提取:
    - 特色摘要
    - 自然结果(标题、url、摘要)
    - 下一页链接
    - Bing 重定向 URL(解码)
    """
```

**关键特性**:
1. **HTML 解析**: 使用 BeautifulSoup 解析 HTML
2. **特色摘要提取**: 识别特殊的特色结果
3. **URL 过滤**: 过滤已访问/已评估的链接
4. **下一页检测**: 查找分页链接
5. **Bing 重定向解码** (24-73行): 处理 Bing 的重定向 URL

```python
# 解码 Bing 重定向 URL
if "bing.com/ck/a?" in url:
    # 提取 u 参数
    u_param = extract_u_param(url)
    # 解码 base64
    decoded_url = base64.b64decode(u_param).decode('utf-8')
    # 提取真实 URL
    real_url = extract_real_url(decoded_url)
    return real_url
```

### 使用示例

```python
# 在 MicroAgent 动作中
@register_action(description="搜索网络")
async def web_search(self, query: str, num_results: int = 10) -> str:
    # 调用搜索 API
    html = await self._search_api(query, num_results)

    # 解析结果
    result = await self.brain.think_with_retry(
        initial_messages=f"解析这些搜索结果:\n{html}",
        parser=parse_search_results,
        max_retries=2
    )

    # result 是 SearchResultItem 列表
    return format_results(result)
```

## 创建自定义解析器

### 分步指南

**1. 定义解析器函数**:

```python
def my_custom_parser(raw_reply: str, **kwargs) -> dict:
    # 验证输入
    if not raw_reply or not raw_reply.strip():
        return {
            "status": "error",
            "feedback": "空响应。请提供输出。"
        }

    # 检查必需标记
    if "[REQUIRED_SECTION]" not in raw_reply:
        return {
            "status": "error",
            "feedback": "缺少必需部分: [REQUIRED_SECTION]。"
                       "请使用此部分标题格式化您的响应。"
        }

    # 提取数据
    content = extract_content(raw_reply)

    # 验证数据
    if not content or len(content) < 10:
        return {
            "status": "error",
            "feedback": "提取的内容太短。"
                       "请提供更详细的信息。"
        }

    # 返回成功
    return {
        "status": "success",
        "data": content
    }
```

**2. 与 think_with_retry 一起使用**:

```python
result = await llm_client.think_with_retry(
    initial_messages="你的任务在这里...",
    parser=my_custom_parser,
    max_retries=3
)
```

### 解析器模板

```python
def parser_template(raw_reply: str, **kwargs) -> dict:
    """
    解析器模板

    参数:
        raw_reply: 要解析的 LLM 输出
        **kwargs: 解析器特定参数

    返回:
        包含成功/错误信息的状态字典
    """

    # 1. 验证输入
    if not raw_reply:
        return {
            "status": "error",
            "feedback": "空响应"
        }

    # 2. 检查必需结构
    required_markers = kwargs.get("required_markers", [])
    for marker in required_markers:
        if marker not in raw_reply:
            return {
                "status": "error",
                "feedback": f"缺少 {marker}。请包含它。"
            }

    # 3. 提取数据
    try:
        data = extract_data(raw_reply, **kwargs)
    except Exception as e:
        return {
            "status": "error",
            "feedback": f"解析错误: {str(e)}。请检查格式。"
        }

    # 4. 验证提取的数据
    if not validate_data(data, **kwargs):
        return {
            "status": "error",
            "feedback": "无效数据。请确保所有字段都存在。"
        }

    # 5. 返回成功
    return {
        "status": "success",
        "data": data
    }
```

## 总结

### 组件职责

| 组件 | 位置 | 职责 |
|------|------|------|
| LLMClient | backends/llm_client.py | 带流式的 LLM API 封装 |
| think_with_retry | backends/llm_client.py | 用于解析的通用重试循环 |
| multi_section_parser | skills/parser_utils.py | 提取多个部分 |
| search_results_parser | skills/search_results_parser.py | 解析 HTML 搜索结果 |

### 关键优势

1. **健壮性**: 带有具体反馈的自动重试
2. **灵活性**: 可插拔的解析器接口
3. **效率**: 带提前终止的优化解析
4. **可靠性**: 清晰的错误消息指导 LLM 生成正确输出
5. **可复用性**: 通用模式适用于任何解析任务

### 最佳实践

1. **提供具体反馈**: 准确告诉 LLM 错误在哪里
2. **彻底验证**: 在返回成功之前检查所有要求
3. **使用多部分解析器**: 尽可能利用现有解析器
4. **处理边界情况**: 空输出、格式错误的内容等
5. **限制重试**: 设置合理的 max_retries 以避免无限循环

### 常见模式

**提取单个值**:
```python
result = await brain.think_with_retry(
    messages="提取日期...",
    parser=lambda text: extract_date(text),
    max_retries=2
)
```

**提取多个部分**:
```python
result = await brain.think_with_retry(
    messages="创建部分 [计划]、[时间线]、[预算]",
    parser=multi_section_parser,
    section_headers=['[计划]', '[时间线]', '[预算]'],
    match_mode="ALL",
    max_retries=3
)
# result 是部分的字典
```

**解析复杂数据**:
```python
result = await brain.think_with_retry(
    messages="提取结构化数据...",
    parser=custom_structured_parser,
    max_retries=3
)
```

这种模式确保从 LLM 自然语言响应中可靠地提取结构化输出。
