# Dialog-With-Retry Pattern 实现总结

## 概述

成功实现了 `dialog_with_retry` pattern，这是一个"多人对话版本的think_with_retry"模式，通过两个LLM personas之间的智能对话循环，实现深度验证和迭代改进。

## 核心概念

### 与 think_with_retry 的对比

| 特性 | think_with_retry | dialog_with_retry |
|------|------------------|-------------------|
| **验证方式** | parser函数（代码规则） | LLM对话（智能评估） |
| **角色** | 单个LLM + parser | 两个LLM personas（Producer + Verifier） |
| **反馈质量** | 固定的error message | 智能分析和建议 |
| **适用场景** | 格式验证 | 质量验证、创意改进、计划评估 |
| **终止条件** | parser返回success | Verifier的approver_parser返回success |

### 设计原则

1. **A（Producer）的历史管理**：
   - 第1轮：只有初始任务
   - 第2轮+：初始任务 + A上次输出 + **B的最新feedback**（只保留最新）

2. **B（Verifier）的无状态设计**：
   - 每轮都是：`system: B的人设` + `user: A的当前输出`
   - 不保留历史，只看当前A的输出

3. **不需要复杂的DialogHistory**：
   - 只需 `last_a_output` 和 `last_b_feedback` 两个变量

## 实现细节

### 1. LLMClient.dialog_with_retry()

**位置**：`src/agentmatrix/backends/llm_client.py` (line 107-221)

**签名**：
```python
async def dialog_with_retry(
    self,
    producer_task: str,              # A的初始任务
    producer_persona: str,           # A的人设
    verifier_task_template: str,     # B的评估任务模板（包含{producer_output}）
    verifier_persona: str,           # B的人设
    approver_parser: callable,       # 判断B是否批准的parser
    max_rounds: int = 3              # 最大对话轮数
) -> dict
```

**返回值**：
```python
{
    "status": "success" | "max_rounds_reached",
    "content": A的最终输出（成功时）,
    "rounds_used": 实际使用的轮数,
    "last_feedback": B的最后反馈（失败时）
}
```

**核心逻辑**：
```python
for round_num in range(1, max_rounds + 1):
    # Phase 1: A生成输出
    if round_num == 1:
        a_messages = [{"role": "user", "content": producer_task}]
    else:
        a_messages = [
            {"role": "user", "content": producer_task},
            {"role": "assistant", "content": last_a_output},
            {"role": "user", "content": last_b_feedback}  # 只有最新feedback
        ]

    last_a_output = await brain.think(a_messages)

    # Phase 2: B评估
    b_messages = [
        {"role": "system", "content": verifier_persona},
        {"role": "user", "content": verifier_task_template.format(producer_output=last_a_output)}
    ]

    b_output = await brain.think(b_messages)

    # Phase 3: 检查是否批准
    parser_result = approver_parser(b_output)
    if parser_result["status"] == "success":
        return {"status": "success", "content": last_a_output, ...}
    else:
        last_b_feedback = parser_result["feedback"]
        # 继续下一轮
```

### 2. director_approval_parser()

**位置**：`src/agentmatrix/skills/deep_researcher_helper.py` (line 188-244)

**职责**：解析director（Verifier）的输出，判断是否批准研究计划

**期望的B输出格式**：
```
[决策]
批准 / 不批准

[理由]
评估理由

[反馈]
具体的改进建议（如果不批准）
```

**返回值**：
```python
# 批准时
{
    "status": "success",  # ← dialog_with_retry会终止
    "decision": "approved",
    "reason": "..."
}

# 不批准时
{
    "status": "error",  # ← dialog_with_retry会继续
    "decision": "rejected",
    "reason": "...",
    "feedback": "请根据以下建议改进研究计划：\n\n..."
}
```

**关键逻辑**：
```python
approved_keywords = ["批准", "同意", "通过", "approved", "accept", "approve", "ok", "可以"]
is_approved = any(keyword in decision.lower() for keyword in approved_keywords)

if is_approved:
    return {"status": "success", ...}
else:
    return {"status": "error", "feedback": ...}
```

### 3. 在Deep Researcher中的应用

**位置**：`src/agentmatrix/skills/deep_researcher.py` (line 136-258)

**修改前**（旧的_planning_stage）：
```python
# 1. 研究员生成计划
draft_plan = await self._run_micro_agent(...)

# 2. 导师review（一次性）
director_feedback = await self._run_micro_agent(...)

# 3. 研究员综合意见
final_plan = await self.brain.think_with_retry(...)
```

**修改后**（使用dialog_with_retry）：
```python
result = await self.brain.dialog_with_retry(
    producer_task=format_prompt(START_PLAN_PROMPT, ctx),
    producer_persona=ctx.researcher_persona,
    verifier_task_template=format_prompt(DIRECTOR_REVIEW_PROMPT, ctx),
    verifier_persona=ctx.director_persona,
    approver_parser=director_approval_parser,
    max_rounds=3
)

if result["status"] == "success":
    # Director批准了！
    final_plan_text = result["content"]
    # 解析并保存...
else:
    # 降级处理：使用最后一次输出
    last_output = result["last_output"]
    # ...
```

## 使用示例

### 基础用法

```python
result = await llm_client.dialog_with_retry(
    producer_task="写一个研究计划",
    producer_persona="你是一个专业的研究员",
    verifier_task_template="评估以下研究计划：\n{producer_output}",
    verifier_persona="你是一个严格的研究导师",
    approver_parser=my_approval_parser,
    max_rounds=3
)

if result["status"] == "success":
    print(f"✅ 在第{result['rounds_used']}轮获得批准")
    print(f"最终输出:\n{result['content']}")
else:
    print(f"❌ 未能在{result['rounds_used']}轮内获得批准")
    print(f"最后反馈: {result['last_feedback']}")
```

### 自定义approver_parser

```python
def my_approval_parser(raw_reply: str) -> dict:
    """
    自定义的批准parser

    期望B的输出：
    [决策]
    通过 / 不通过
    [理由]
    ...
    [反馈]
    ...
    """
    sections = multi_section_parser(
        raw_reply,
        section_headers=["[决策]", "[理由]", "[反馈]"],
        match_mode="ANY"
    )

    decision = sections['sections'].get("[决策]", "").lower()

    if "通过" in decision or "ok" in decision:
        return {"status": "success"}  # ← 批准
    else:
        feedback = sections['sections'].get("[反馈]", "请改进")
        return {
            "status": "error",  # ← 不批准
            "feedback": feedback
        }
```

## 应用场景

### 1. 研究计划制定（已实现）
- **A**: 研究员生成研究计划
- **B**: 导师评估计划质量（逻辑闭环、可操作性等）
- **优势**: 智能评估，而不仅仅是格式检查

### 2. 代码审查
```python
result = await brain.dialog_with_retry(
    producer_task="写一个函数实现X",
    producer_persona="你是一个程序员",
    verifier_task_template="审查以下代码：\n{producer_output}",
    verifier_persona="你是一个资深的代码审查员",
    approver_parser=code_review_approval_parser
)
```

### 3. 文档优化
```python
result = await brain.dialog_with_retry(
    producer_task="写一份API文档",
    producer_persona="你是一个技术写作者",
    verifier_task_template="评估这份文档：\n{producer_output}",
    verifier_persona="你是一个技术文档专家",
    approver_parser=doc_approval_parser
)
```

### 4. 创意改进
```python
result = await brain.dialog_with_retry(
    producer_task="设计一个logo",
    producer_persona="你是一个设计师",
    verifier_task_template="评估这个设计：\n{producer_output}",
    verifier_persona="你是一个创意总监",
    approver_parser=design_approval_parser
)
```

## 关键优势

### 1. 智能验证
- B不仅仅是格式检查，而是深度理解和评估
- 可以发现A的输出中的逻辑问题、遗漏等

### 2. 迭代改进
- 每一轮都是基于真实反馈的改进
- 而不是一次性生成

### 3. 灵活性
- 可以调整max_rounds控制成本
- B的评估标准可以很复杂（通过prompt控制）

### 4. 简洁性
- 不需要复杂的对话历史管理
- A只保留最新feedback，B是无状态的

## 设计亮点

### 1. B的无状态设计
```python
# B永远只看当前A的输出，不保留历史
b_messages = [
    {"role": "system", "content": verifier_persona},
    {"role": "user", "content": current_a_output}  # ← 只看当前
]
```

**优势**：
- 简化实现
- 避免历史积累导致的context膨胀
- B的评估更客观（不受之前轮次的影响）

### 2. A的最小化历史
```python
# 第1轮
a_messages = [{"role": "user", "content": task}]

# 第2轮及以后（只保留最新feedback）
a_messages = [
    {"role": "user", "content": task},
    {"role": "assistant", "content": last_a_output},
    {"role": "user", "content": latest_feedback}  # ← 替换，不是追加
]
```

**优势**：
- A能看到上次自己写了什么
- A只看到最新的B的反馈（避免混淆）
- 保持上下文简洁

### 3. 特例退化
如果B第1轮就批准，流程等价于think_with_retry：
```
Round 1:
  A输出 → B批准 → 结束
```

## 测试建议

### 单元测试

```python
async def test_dialog_with_retry_first_round_approval():
    """测试第1轮就批准的情况"""
    result = await brain.dialog_with_retry(
        producer_task="简单任务",
        producer_persona="A",
        verifier_task_template="批准: {producer_output}",
        verifier_persona="B（总是批准）",
        approver_parser=lambda x: {"status": "success"},
        max_rounds=3
    )

    assert result["status"] == "success"
    assert result["rounds_used"] == 1


async def test_dialog_with_retry_multi_round():
    """测试多轮对话"""
    call_count = {"A": 0, "B": 0}

    async def mock_think(messages):
        # 模拟A和B的输出
        if "producer" in str(messages):
            call_count["A"] += 1
            return {"reply": f"A output {call_count['A']}"}
        else:
            call_count["B"] += 1
            # 第1、2轮不批准，第3轮批准
            if call_count["B"] < 3:
                return {"reply": "[决策]\n不批准\n[反馈]\n改进"}
            else:
                return {"reply": "[决策]\n批准"}

    # 使用mock测试...
```

## 后续改进

1. **成本控制**：根据token使用量动态调整max_rounds
2. **部分批准**：B可以批准某些部分，要求修改其他部分
3. **多Verifier**：A同时被多个B评估（代码审查、安全审查、性能审查）
4. **异步评估**：多个B并行评估，然后汇总反馈

## 总结

`dialog_with_retry` 是 `think_with_retry` 的自然进化，从"格式验证"升级到"智能对话验证"，适用于需要深度评估和迭代改进的场景。

**核心价值**：
- ✅ 智能验证（LLM评估 vs 代码规则）
- ✅ 迭代改进（真实反馈 vs 静态错误）
- ✅ 简洁设计（无状态B + 最小化历史）
- ✅ 广泛适用（研究计划、代码审查、文档优化等）

这是一个powerful的pattern，可以被任何需要质量验证的skill使用！
