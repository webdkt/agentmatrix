# Think-With-Retry 模式

和LLM进行自然对话并最终从LLM的自然语言输出中获得结构化输出的一种模式。

目前，比较常见的让LLM输出结构化数据的方式是通过指定JSON输出格式这样的prompt方式。他有几个问题
1. 不能百分百保证输出格式正确，而且对于复杂结构的JSON，出错概率会加大
2. 会降智，会浪费智力。大语言模型的注意力是有限的，如果需要施加严格的约束，会必然分走一部分注意力，导致输出的质量下降（这当然是未经证实的规律，是来自我的经验和直觉）

所以，我提出了一种新的模式，叫做Think-With-Retry模式。这个模式的核心逻辑是，通过软性的约束，让大模型按照大致的结构输出，然后利用parser 对输出进行解析，对于结构确实或者错误，让LLM补充或者重新输出，直到输出符合预期。

并且这个过程自动完成，并且不会污染主对话历史

# 接口和参数

## think的模式
就是第一步让LLM输出的prompt如何设计。我建议不要每次要求他严格的格式（例如“只输出什么什么”）。而是允许它先输出自己的想法，然后把需要的内容用section 的形式，例如
```
[SECTION HEAD]
SECTION CONTENT
```
这样的。或者用 ==== 分割的形式，总之用LLM很自然的输出方式来区分内容边界。并且一定要给示例。

## parser的模式 （控制何时retry）
parser的目的是校验LLM的输出是否有我们想要的内容，并且提取成我们想要的结构（不论是dict还是List还是只是str）。
一般可以直接用multi_section_parser 或者 simple_parser， 如果有更复杂的结构，可以写一个Parser先调用multi_section_parser或者simple_parser，得到自己想要的输入块，然后进一步的去解析结构

## 传入parser的动态参数

parser 可以通过 `**parser_kwargs` 接收参数。

```python
# 示例：向 multi_section_parser 传递参数
result = await brain.think_with_retry(
    prompt,
    multi_section_parser,
    section_headers=["[研究计划]", "[章节大纲]"],
    match_mode="ALL"
)
# 等价于调用：multi_section_parser(raw_reply, section_headers=[...], match_mode="ALL")
```

**注意**：直接传函数引用，不要用 lambda 包装。

---

# Parser 契约

所有 parser 必须遵循统一格式：

```python
{
    "status": "success" | "error",
    "content": ...,      # 成功时：提取的内容
    "feedback": str      # 失败时：错误反馈
}
```

**成功示例**：
```python
# 返回单个值
{"status": "success", "content": "提取的文本"}

# 返回多section（字典）
{"status": "success", "content": {"[研究计划]": "...", "[章节大纲]": "..."}}
```

**失败示例**：
```python
{"status": "error", "feedback": "缺少必需的section: [研究计划]"}
```

**最佳实践**：
- 错误信息要具体、可操作
- 告诉 LLM 缺什么、怎么改
- 不要只说"解析失败"这种模糊信息

---

# multi_section_parser

**位置**：`src/agentmatrix/skills/parser_utils.py`

通用的多 section 解析器，支持两种模式。

## 模式1：多section解析

指定 `section_headers` 列表，提取多个 section。

```python
result = multi_section_parser(
    raw_reply,
    section_headers=['[研究计划]', '[章节大纲]'],
    match_mode="ALL"  # 或 "ANY"
)
```

**match_mode 参数**：
- `"ALL"`：所有指定的 headers 都必须存在（默认）
- `"ANY"`：只要匹配到即可，有多少返回多少

## 模式2：单section解析

不指定 `section_headers`，自动查找 `=====` 分隔符，提取最后一个分隔符后的内容。

```python
result = multi_section_parser(raw_reply)
# 返回：{"status": "success", "content": "分隔符后的内容"}
```

## 性能优化

1. **快速预检查**：ALL 模式下先用 `in` 操作检查所有 headers 是否存在
2. **倒序遍历 + 提前终止**：从后往前找，找到所有需要的 sections 后立即停止

---

# think_with_retry 实现机制

## 返回值约定

`think_with_retry` **只返回** parser 的 `"content"` 字段值，不返回整个 dict。

```python
# 如果 parser 返回 {"status": "success", "content": "text"}
# think_with_retry 返回： "text"

# 如果 parser 返回 {"status": "success", "content": {"key": "value"}}
# think_with_retry 返回： {"key": "value"}
```

这样调用代码更简洁，不用每次都访问 `["content"]`。

## 重试流程

```
1. 调用 LLM
   ↓
2. Parser 解析
   ↓
3. status == "success"?
    ├─ Yes → 返回 content
    └─ No  → 追加反馈到消息 → 重新调用 LLM（最多 max_retries 次）
```

失败时，自动将 LLM 的输出和错误反馈追加到对话历史，让 LLM 自然地修正。

---

# 核心要点（3条规则）

1. **直接传函数**：`think_with_retry(prompt, parser, arg=value)`，不要用 lambda 包装

2. **Prompt 必须包含示例**：给 LLM 提供格式示例让其模仿，比只给约束更可靠

3. **组合验证**：`multi_section_parser` + 额外验证（先提取，再校验）

---

# 参见

- **实现源码**：`src/agentmatrix/backends/llm_client.py` 的 `think_with_retry()` 方法
- **通用 parser**：`src/agentmatrix/skills/parser_utils.py` 的 `multi_section_parser()`
- **使用示例**：`src/agentmatrix/skills/deep_researcher.py` 中大量使用此模式
