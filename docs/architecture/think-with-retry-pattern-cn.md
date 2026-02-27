# Think-With-Retry 模式

**文档版本**: v0.2.0 | **最后更新**: 2026-02-26 | **状态**: ✅ 已实现

## 概述

### 核心思想

通过**软性约束**让 LLM 自然输出，然后用 parser 解析并**自动重试**，直到输出符合预期。

### 为什么需要

传统方法要求 LLM 输出严格 JSON 格式存在两个问题：

1. **出错概率高**：复杂结构容易出错
2. **占用注意力**：格式约束占用 LLM 的"脑力"，导致输出质量下降

**Think-With-Retry 的优势**：
- ✅ LLM 用自然语言思考，不受格式约束
- ✅ Parser 负责解析和验证
- ✅ 自动重试机制，对话式修正错误
- ✅ 不污染主对话历史

### 使用场景

**适合用 Think-With-Retry**：
- 需要结构化输出（计划、列表、字段等）
- 输出格式相对固定
- 可以容忍少量重试成本

**不适合用**：
- 简单的问答对话
- 不需要结构化的输出
- 对延迟极度敏感

## 核心概念

### 软性约束输出

**思想**：让 LLM 用自然方式输出，用轻量级标记区分内容边界

**推荐格式**：

```markdown
[研究计划]
1. 研究 AI 安全的技术方案
2. 调研现有实现
3. 评估风险

[时间安排]
第1周：技术方案
第2周：调研
第3周：评估
```

**关键点**：
- 使用 `[SECTION NAME]` 或 `====` 分隔
- 提供**示例**让 LLM 模仿
- 不要说"只输出什么"，允许自由发挥

### Parser 契约

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

# 返回多 section（字典）
{"status": "success", "content": {"[研究计划]": "...", "[时间安排]": "..."}}
```

**失败示例**：

```python
{"status": "error", "feedback": "缺少必需的section: [研究计划]"}
```

**最佳实践**：
- 错误信息要具体、可操作
- 告诉 LLM **缺什么**、**怎么改**
- 不要只说"解析失败"

### 自动重试机制

**流程**：

```
1. 调用 LLM
   ↓
2. Parser 解析
   ↓
3. status == "success"?
    ├─ Yes → 返回 content
    └─ No  → 追加 feedback 到消息 → 重新调用 LLM
                ↓
            最多重试 max_retries 次
```

**关键**：
- 失败时自动将 LLM 的输出和 feedback 追加到对话历史
- LLM 看到"自己的输出 + 错误提示"，自然地修正
- 整个过程对调用者透明

## 使用方法

### 基本用法

```python
from agentmatrix.backends.llm_client import LLMClient
from agentmatrix.skills.parser_utils import multi_section_parser

# 初始化客户端
llm_client = LLMClient(...)

# 调用 think_with_retry
result = await llm_client.think_with_retry(
    initial_messages="你的prompt",
    parser=multi_section_parser,
    section_headers=["[研究计划]", "[时间安排]"],
    match_mode="ALL",
    max_retries=3
)

# result 就是 parser 返回的 content
print(result["[研究计划]"])
```

**参数说明**：
- `initial_messages`：初始 prompt（可以是字符串或消息列表）
- `parser`：parser 函数（直接传函数引用，不要用 lambda）
- `max_retries`：最大重试次数（默认 3）
- `**parser_kwargs`：传给 parser 的额外参数

### 完整示例

**场景**：让 LLM 制定项目计划

```python
async def create_project_plan(topic: str) -> Dict:
    """创建项目计划"""

    # 1. 设计 prompt（包含示例）
    prompt = f"""
请为以下主题制定项目计划：{topic}

请按以下格式输出（示例）：

[研究计划]
1. 第一步
2. 第二步
3. 第三步

[时间安排]
- 第1周：...
- 第2周：...
- 第3周：...

[资源需求]
- 人力：...
- 设备：...
"""

    # 2. 调用 think_with_retry
    result = await llm_client.think_with_retry(
        initial_messages=prompt,
        parser=multi_section_parser,
        section_headers=["[研究计划]", "[时间安排]", "[资源需求]"],
        match_mode="ALL",  # 必须全部存在
        max_retries=3
    )

    # 3. 使用结果
    # result = {
    #     "[研究计划]": "1. ...\n2. ...",
    #     "[时间安排]": "- 第1周：...",
    #     "[资源需求]": "- 人力：..."
    # }

    return result

# 使用
plan = await create_project_plan("AI 安全研究")
print(plan["[研究计划]"])
```

### 高级用法

#### 用法1：ANY 模式（可选 sections）

```python
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    section_headers=["[方案A]", "[方案B]", "[方案C]"],
    match_mode="ANY",  # 有什么返回什么，不报错
    max_retries=3
)
# 可能只返回 {"[方案A]": "...", "[方案C]": "..."}
```

#### 用法2：单 section 模式

```python
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    # 不传 section_headers，自动查找 "====" 分隔符
    max_retries=3
)
# 返回 {"status": "success", "content": "分隔符后的内容"}
```

#### 用法3：自定义 Parser

```python
def my_custom_parser(raw_reply: str) -> dict:
    """自定义 parser"""

    # 先用 multi_section_parser 提取
    sections = multi_section_parser(
        raw_reply,
        section_headers=["[计划]", "[清单]"],
        match_mode="ALL"
    )

    if sections["status"] == "error":
        return sections

    # 再做额外的验证和处理
    content = sections["content"]

    # 验证 [计划] 至少有3项
    plan_items = [line for line in content["[计划]"].split('\n') if line.strip()]
    if len(plan_items) < 3:
        return {
            "status": "error",
            "feedback": f"[计划] 至少需要3项，当前只有{len(plan_items)}项"
        }

    # 提取 [清单] 的第一项
    first_item = content["[清单]"].split('\n')[0].strip()

    return {
        "status": "success",
        "content": {
            "plan": content["[计划]"],
            "first_item": first_item
        }
    }

# 使用
result = await llm_client.think_with_retry(
    prompt="...",
    parser=my_custom_parser,
    max_retries=3
)
```

## Parser 工具

### multi_section_parser

**位置**: `src/agentmatrix/skills/parser_utils.py`

通用的多 section 解析器，支持两种模式。

#### 模式1：多 section 解析

```python
result = multi_section_parser(
    raw_reply,
    section_headers=['[研究计划]', '[时间安排]'],
    match_mode="ALL"  # 或 "ANY"
)
```

**match_mode 参数**：
- `"ALL"`（默认）：所有指定的 headers 都必须存在
- `"ANY"`：只要匹配到即可，有多少返回多少

#### 模式2：单 section 解析

```python
result = multi_section_parser(raw_reply)
```

自动查找 `=====` 分隔符，提取最后一个分隔符后的内容。

#### 高级参数

```python
result = multi_section_parser(
    raw_reply,
    section_headers=['[研究计划]', '[时间安排]'],
    match_mode="ALL",
    regex_mode=False,      # 是否使用正则匹配（默认 False）
    return_list=False,     # 是否返回行列表（默认 False）
    allow_empty=False      # 是否允许空内容（默认 False）
)
```

**参数说明**：
- `regex_mode`：
  - `False`（默认）：精确匹配，一行必须完全等于 header
  - `True`：正则表达式匹配
- `return_list`：
  - `False`（默认）：返回字符串
  - `True`：返回行列表
- `allow_empty`：
  - `False`（默认）：空内容返回错误
  - `True`：允许空内容

### 自定义 Parser

**模板**：

```python
def my_parser(raw_reply: str, **kwargs) -> dict:
    """
    自定义 parser

    Args:
        raw_reply: LLM 的原始输出
        **kwargs: 额外参数（从 think_with_retry 传入）

    Returns:
        {
            "status": "success" | "error",
            "content": ...,  # 成功时
            "feedback": str  # 失败时
        }
    """

    # 1. 尝试解析
    try:
        # 解析逻辑
        content = parse_something(raw_reply)

        # 2. 验证
        if not validate(content):
            return {
                "status": "error",
                "feedback": "验证失败：xxx"
            }

        # 3. 成功
        return {
            "status": "success",
            "content": content
        }

    except Exception as e:
        return {
            "status": "error",
            "feedback": f"解析错误：{str(e)}"
        }
```

**最佳实践**：
1. **组合使用**：先用 `multi_section_parser` 提取，再自定义验证
2. **具体反馈**：错误信息要告诉 LLM 具体缺什么、怎么改
3. **容错处理**：用 try-except 包裹解析逻辑

## 实现机制

### think_with_retry 流程

**代码位置**: `src/agentmatrix/backends/llm_client.py`

```python
async def think_with_retry(
    self,
    initial_messages: Union[str, List[str]],
    parser: callable,
    max_retries: int = 3,
    debug: bool = True,
    **parser_kwargs
) -> any:
    """
    循环调用 LLM 直到输出成功解析

    Returns:
        parser 返回的 content 字段（不是整个 dict）
    """

    # 1. 标准化 messages
    if isinstance(initial_messages, str):
        messages = [{"role": "user", "content": initial_messages}]
    else:
        messages = initial_messages

    # 2. 循环重试
    for attempt in range(max_retries):
        # 2.1 调用 LLM
        response = await self.think(messages=messages)
        raw_reply = response['reply']

        # 2.2 Parser 解析
        parsed_result = parser(raw_reply, **parser_kwargs)

        # 2.3 检查结果
        if parsed_result["status"] == "success":
            # 成功：返回 content
            return parsed_result["content"]
        else:
            # 失败：追加反馈到消息，重试
            feedback = parsed_result["feedback"]
            messages.append({"role": "assistant", "content": raw_reply})
            messages.append({"role": "user", "content": f"你的回答很有帮助，但{feedback}"})

    # 3. 超过最大重试次数
    raise ValueError(f"无法在 {max_retries} 次重试内获得有效输出")
```

### 返回值约定

**重要**：`think_with_retry` 只返回 parser 的 `"content"` 字段，不返回整个 dict。

```python
# 如果 parser 返回 {"status": "success", "content": "text"}
# think_with_retry 返回： "text"

# 如果 parser 返回 {"status": "success", "content": {"key": "value"}}
# think_with_retry 返回： {"key": "value"}
```

这样调用代码更简洁，不用每次都访问 `["content"]`。

### 错误处理

#### 重试失败

超过 `max_retries` 后抛出异常：

```python
try:
    result = await llm_client.think_with_retry(
        prompt="...",
        parser=multi_section_parser,
        max_retries=3
    )
except ValueError as e:
    print(f"解析失败：{e}")
    # 处理失败情况
```

#### Parser 异常

Parser 内部应该捕获所有异常，返回 `{"status": "error"}`：

```python
def my_parser(raw_reply: str) -> dict:
    try:
        # 解析逻辑
        return {"status": "success", "content": ...}
    except Exception as e:
        return {"status": "error", "feedback": str(e)}
```

### 性能优化

#### 减少 LLM 调用次数

**方法1**：优化 prompt，减少出错概率

```python
# ❌ 不好：缺少示例
prompt = "请输出[计划]和[时间]两个section"

# ✅ 好：有完整示例
prompt = """
请输出项目计划，格式如下：

[计划]
1. 第一步
2. 第二步

[时间]
第1周：...
第2周：...
"""
```

**方法2**：降低 `match_mode` 严格度

```python
# ❌ 严格：必须全部匹配，容易重试
match_mode="ALL"

# ✅ 宽松：部分匹配即可
match_mode="ANY"
```

#### Debug 模式

```python
# 开启 debug 查看详细日志
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    debug=True  # 输出 LLM 的输入输出
)
```

**debug 输出示例**：
```
=== think_with_retry DEBUG START ===
Initial messages (1 messages):
  [0] user: 请制定计划...

LLM Response (raw_reply):
  [计划]
  1. ...
  [时间]
  第1周：...

Parser result:
  {'status': 'success', 'content': {...}}
```

## 最佳实践

### Prompt 设计

#### ✅ 好的 Prompt

**特征**：
1. 有完整的格式示例
2. 示例与实际需求一致
3. 使用轻量级分隔符
4. 明确但不过度约束

```python
prompt = """
请为以下主题制定项目计划：{topic}

输出格式（请严格按此格式）：

[研究计划]
1. 第一步：描述
2. 第二步：描述
3. 第三步：描述

[时间安排]
- 第1周：任务
- 第2周：任务
- 第3周：任务

[资源需求]
- 人力：人数
- 设备：清单
"""
```

#### ❌ 不好的 Prompt

```python
# ❌ 缺少示例
prompt = "请输出研究计划、时间安排和资源需求"

# ❌ 过度约束
prompt = "只输出以下格式，不要有其他内容：[研究计划]..."

# ❌ 使用复杂格式（JSON）
prompt = "请输出JSON格式：{'plan': [...], 'time': {...}}"
```

### Parser 设计

#### 原则

1. **先提取，后验证**：先用 `multi_section_parser` 提取，再验证
2. **具体反馈**：错误信息要精确
3. **容错处理**：捕获所有异常

#### 示例

```python
def project_plan_parser(raw_reply: str) -> dict:
    """项目计划 parser"""

    # 1. 先提取 sections
    sections = multi_section_parser(
        raw_reply,
        section_headers=["[研究计划]", "[时间安排]", "[资源需求]"],
        match_mode="ALL"
    )

    if sections["status"] == "error":
        return sections

    content = sections["content"]

    # 2. 验证 [研究计划]
    plan_text = content["[研究计划]"]
    plan_items = [line for line in plan_text.split('\n') if line.strip() if line.strip()[0].isdigit()]

    if len(plan_items) < 3:
        return {
            "status": "error",
            "feedback": f"[研究计划] 至少需要3项，当前只有{len(plan_items)}项，请补充完整计划"
        }

    # 3. 验证 [时间安排]
    time_text = content["[时间安排]"]
    if "第1周" not in time_text or "第2周" not in time_text:
        return {
            "status": "error",
            "feedback": "[时间安排] 必须包含第1周和第2周的任务，请补充"
        }

    # 4. 成功，返回结构化数据
    return {
        "status": "success",
        "content": {
            "plan": plan_items,
            "timeline": time_text,
            "resources": content["[资源需求]"]
        }
    }
```

### 常见错误

#### 错误1：用 lambda 包装 parser

```python
# ❌ 错误
result = await llm_client.think_with_retry(
    prompt="...",
    parser=lambda x: multi_section_parser(x, section_headers=["[A]"]),
    max_retries=3
)
```

**问题**：lambda 会影响错误日志，难以调试

**正确做法**：直接传函数引用，用 `**parser_kwargs` 传参

```python
# ✅ 正确
result = await llm_client.think_with_retry(
    prompt="...",
    parser=multi_section_parser,
    section_headers=["[A]"],
    max_retries=3
)
```

#### 错误2：Prompt 缺少示例

```python
# ❌ 只有约束，没有示例
prompt = "请输出[研究计划]section"
```

**正确**：提供完整示例

```python
# ✅ 有示例
prompt = """
请输出研究计划，格式如下：

[研究计划]
1. 第一步
2. 第二步
"""
```

#### 错误3：Parser 反馈不具体

```python
# ❌ 模糊的错误信息
return {"status": "error", "feedback": "解析失败"}
```

**正确**：告诉 LLM 具体缺什么

```python
# ✅ 具体的错误信息
return {
    "status": "error",
    "feedback": "缺少[时间安排]section，请补充第1周、第2周的任务安排"
}
```

#### 错误4：过度使用重试

```python
# ❌ max_retries 太大，浪费成本
max_retries=10
```

**建议**：
- 简单任务：`max_retries=2`
- 复杂任务：`max_retries=3`
- 非常复杂：`max_retries=5`

### 实战技巧

#### 技巧1：组合多个 parser

```python
def combined_parser(raw_reply: str) -> dict:
    """先提取 sections，再做业务逻辑验证"""

    # 1. 提取
    sections = multi_section_parser(raw_reply, ...)
    if sections["status"] == "error":
        return sections

    # 2. 业务逻辑
    content = sections["content"]

    # 3. 提取字段
    items = extract_items(content["[清单]"])
    if not items:
        return {"status": "error", "feedback": "[清单] 不能为空"}

    # 4. 计算派生字段
    total = calculate_total(items)

    # 5. 返回结构化数据
    return {
        "status": "success",
        "content": {
            "items": items,
            "total": total
        }
    }
```

#### 技巧2：分阶段获取结构化数据

```python
# 第1步：获取大纲
outline = await llm_client.think_with_retry(
    prompt="制定大纲...",
    parser=multi_section_parser,
    section_headers=["[大纲]"],
    max_retries=2
)

# 第2步：基于大纲获取详细内容
detail = await llm_client.think_with_retry(
    prompt=f"基于以下大纲制定详细计划：{outline['[大纲]']}",
    parser=multi_section_parser,
    section_headers=["[步骤]", "[时间]"],
    max_retries=2
)
```

#### 技巧3：在 Action 中使用

```python
@register_action(description="制定项目计划")
async def create_project_plan(self, topic: str) -> str:
    """在 action 中使用 think_with_retry"""

    plan = await self.brain.think_with_retry(
        initial_messages=f"为{topic}制定项目计划...",
        parser=multi_section_parser,
        section_headers=["[研究计划]", "[时间安排]"],
        max_retries=3
    )

    # plan 是 dict：{"[研究计划]": "...", "[时间安排]": "..."}

    return f"计划已创建：\n{plan['[研究计划]']}\n{plan['[时间安排]']}"
```

## 总结

### 核心要点

1. **直接传函数**：`think_with_retry(prompt, parser, arg=value)`，不要用 lambda
2. **Prompt 必须包含示例**：给 LLM 提供格式示例让其模仿
3. **组合验证**：`multi_section_parser` + 额外验证（先提取，再校验）

### 使用流程

```
1. 设计 prompt（包含格式示例）
   ↓
2. 选择或编写 parser
   ↓
3. 调用 think_with_retry
   ↓
4. 处理返回值（parser 的 content）
```

### API 参考

```python
await llm_client.think_with_retry(
    initial_messages: Union[str, List[str]],  # prompt
    parser: callable,                          # parser 函数
    max_retries: int = 3,                     # 最大重试次数
    debug: bool = True,                       # 是否输出调试信息
    **parser_kwargs                           # 传给 parser 的参数
) -> Any
```

### 参见

- **实现源码**：`src/agentmatrix/backends/llm_client.py:think_with_retry()`
- **通用 parser**：`src/agentmatrix/skills/parser_utils.py:multi_section_parser()`
- **使用示例**：`src/agentmatrix/skills/deep_researcher.py`
