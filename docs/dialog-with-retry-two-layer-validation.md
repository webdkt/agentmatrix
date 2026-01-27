# Dialog-With-Retry 双层验证设计

## 核心洞察

用户提出了一个非常重要的观察：`dialog_with_retry` 需要**双层验证机制**：

### 第一层：结构验证（Structural Validation）
- **目的**：确保输出格式正确
- **工具**：parser函数（如`research_plan_parser`）
- **时机**：在B看到A的输出**之前**
- **作用**：如果格式都不对（比如缺少必要的section），就没有必要让B去评估语义质量

### 第二层：语义验证（Semantic Validation）
- **目的**：确保内容质量达标
- **工具**：Verifier (B) + approver_parser
- **时机**：在A的输出格式正确**之后**
- **作用**：深度评估和改进（逻辑闭环、可操作性等）

## 当前实现的问题

```python
# 当前的流程（有问题）
A生成 → 直接传给B → B评估 → 返回raw text → 外部再parse
         ↑
         没有验证格式！
```

**问题**：
1. A的输出没有经过结构验证就直接给B看
2. B可能收到格式错误的输出（缺少section等）
3. 返回的是raw text，还需要在外部再parse一次

## 改进的流程

```python
# 改进的流程
A生成 → [结构验证: producer_parser] → 如果格式错误，A重试
     ↓ (格式正确)
B评估 → [语义验证: approver_parser] → 如果不批准，A重试
     ↓ (语义正确)
返回已parse的结构化数据
```

**关键点**：
1. A的输出在给B看之前，先用`producer_parser`验证结构
2. B只看到格式正确的输出
3. 返回的是已解析的数据，不需要外部再parse

## API 改进

### 新增参数

```python
async def dialog_with_retry(
    self,
    producer_task: str,
    producer_persona: str,
    verifier_task_template: str,
    verifier_persona: str,
    producer_parser: Optional[callable] = None,  # ← 新增：A的结构验证
    approver_parser: Optional[callable] = None,  # B的语义验证
    max_rounds: int = 3
) -> dict:
```

### 内部实现

```python
for round_num in range(1, max_rounds + 1):
    # Phase 1: A生成输出（带结构验证）
    if producer_parser:
        # 使用think_with_retry确保格式正确
        parsed_result = await self.think_with_retry(
            messages=a_messages,
            parser=producer_parser,
            max_retries=2
        )
        # parsed_result是已解析的数据（如{"[研究计划]": ..., "[章节大纲]": ...}）

        # 获取raw output用于给B看
        raw_output = await self.think(messages=a_messages)
    else:
        # 没有结构验证，直接使用raw output
        raw_output = await self.think(messages=a_messages)
        parsed_result = raw_output

    # Phase 2: B评估（看到格式化的输出）
    b_input = str(parsed_result) if producer_parser else raw_output
    # B评估b_input...

    # Phase 3: 检查B是否批准
    if approver_parser:
        parser_result = approver_parser(b_output)
        if parser_result["status"] == "success":
            return {"content": parsed_result, ...}  # ← 返回已解析的数据
```

### 返回值变化

**改进前**：
```python
{
    "content": "raw text...",  # 原始文本
}
# 需要在外部再parse
final_plan = await brain.think_with_retry(result["content"], research_plan_parser)
```

**改进后**：
```python
{
    "content": {"[研究计划]": "...", "[章节大纲]": "..."},  # 已解析的数据
}
# 不需要再parse，直接使用
ctx.research_plan = result["content"]["[研究计划]"]
```

## 使用示例

### 改进前（需要两步）

```python
# Step 1: dialog_with_retry
result = await brain.dialog_with_retry(
    producer_task=...,
    producer_persona=...,
    verifier_task_template=...,
    verifier_persona=...,
    approver_parser=director_approval_parser
)

# Step 2: 还要再parse
final_plan_text = result["content"]
final_plan = await brain.think_with_retry(
    final_plan_text,
    research_plan_parser  # ← 重复parse
)

ctx.research_plan = final_plan["[研究计划]"]
```

### 改进后（一步到位）

```python
result = await brain.dialog_with_retry(
    producer_task=...,
    producer_persona=...,
    verifier_task_template=...,
    verifier_persona=...,
    producer_parser=research_plan_parser,    # ← A的结构验证
    approver_parser=director_approval_parser  # B的语义验证
)

# 直接使用，不需要再parse
final_plan = result["content"]  # ← 已经是 {"[研究计划]": ..., "[章节大纲]": ...}
ctx.research_plan = final_plan["[研究计划]"]
```

## 设计优势

### 1. 明确的分层验证

**结构层**：
- 确保输出包含必要的sections
- 由代码规则验证（parser）
- 快速失败

**语义层**：
- 确保内容质量达标
- 由LLM智能评估（Verifier）
- 深度改进

### 2. 避免浪费B的时间

```
场景：A生成的计划缺少"[章节大纲]" section

改进前：
  A生成(缺少章节) → B评估 → B困惑：怎么没有章节大纲？ → B反馈
  浪费了B的一次调用！

改进后：
  A生成(缺少章节) → producer_parser验证失败 → A重试
  B根本不会看到格式错误的输出
```

### 3. 简化调用代码

不需要在外部再次parse，`dialog_with_retry`内部已经处理了。

### 4. 更好的类型安全

返回的是已解析的结构化数据（dict），而不是raw text。

## 实现细节

### think_with_retry的嵌入

```python
if producer_parser:
    # 使用think_with_retry进行结构验证
    parsed_result = await self.think_with_retry(
        messages=a_messages,
        parser=producer_parser,
        max_retries=2  # 最多重试2次确保格式正确
    )
```

**好处**：
- A会自动重试直到格式正确
- B只看到格式正确的输出
- 嵌套的retry机制（内层：格式，外层：语义）

### Raw vs Parsed

```python
# 保存两个版本
last_a_output_raw = ...      # 用于给B看和下一轮的history
last_a_output_parsed = ...   # 用于最终返回

# B看到格式化的输出
b_input = str(last_a_output_parsed) if producer_parser else last_a_output_raw

# 返回解析后的数据
return {"content": last_a_output_parsed, ...}
```

## _planning_stage 的简化

### 改进前

```python
result = await brain.dialog_with_retry(...)

# 需要再parse
final_plan_text = result["content"]
final_plan = await brain.think_with_retry(
    final_plan_text,
    research_plan_parser
)
ctx.research_plan = final_plan["[研究计划]"]
```

### 改进后

```python
result = await brain.dialog_with_retry(
    ...,
    producer_parser=research_plan_parser,  # ← 内部parse
    ...
)

# 直接使用
final_plan = result["content"]
ctx.research_plan = final_plan["[研究计划]"]  # ← 已经是parsed data
```

**减少了一次LLM调用！**

## 总结

这个改进体现了**关注点分离**（Separation of Concerns）：

- **结构验证**：由代码规则保证（parser）
- **语义验证**：由LLM智能评估（Verifier）

两层验证各司其职，协同工作，确保最终输出的质量和格式都符合预期。

这是一个非常优雅的设计！🎯
