# Micro Agent 设计说明

## 核心理念：Micro Agent 是 BaseAgent 的"临时人格"

### 设计动机

当某些 action 需要多步 LLM 决策时，我们面临两个选择：
1. **直接用 Python code**：步骤固定、确定，适合简单任务
2. **用 Micro Agent**：需要多步决策，步骤不确定，需要 LLM 动态规划

Micro Agent 本质上是 BaseAgent 的一个**临时人格**：
- **相同的能力**（Actions）：可以做的事情和 BaseAgent 一样
- **不同的个性**（Persona）：思维模式、关注点不同
- **独立的任务**（Task）：专注于完成特定的子任务
- **独立的上下文**：不污染 BaseAgent 的主 session

### 架构设计

```
BaseAgent (主 Agent)
│
├─ 核心组件（共享）
│  ├─ brain: LLM 接口
│  ├─ cerebellum: 参数协商器
│  └─ actions_map: 可用 actions 注册表
│
├─ 默认人格
│  └─ system_prompt: "你是一个编程助手..."
│
└─ _run_micro_agent() 方法
     │
     ├─ 创建 MicroAgent 实例（复用核心组件）
     ├─ 继承所有 actions（默认，排除等待类）
     ├─ 注入临时 persona
     ├─ 注入临时 task
     └─ 返回结果给 BaseAgent
```

### Actions 继承机制

**默认行为**（推荐）：
```python
# Micro Agent 自动继承 BaseAgent 的所有 actions
await self._run_micro_agent(
    persona="You are a code expert...",
    task="Analyze this code",
    # available_actions = None（默认）
)
# 结果：Micro Agent 可以使用所有 BaseAgent 的 actions
```

**实际执行**：
```python
# _run_micro_agent 内部逻辑
if available_actions is None:
    # 从 BaseAgent 的 actions_map 中获取所有 actions
    available_actions = list(self.actions_map.keys())

    # 排除等待类 actions（会导致 Micro Agent 无法返回）
    available_actions = [
        a for a in available_actions
        if a not in ["rest_n_wait", "take_a_break"]
    ]

    # 确保 finish_task 存在
    available_actions.append("finish_task")
```

### 为什么排除等待类 Actions？

等待类 actions（如 `rest_n_wait`）在 BaseAgent 中用于：
- 暂停主循环，等待下一封邮件
- 释放控制权给事件循环

但在 Micro Agent 中：
- 没有"邮件"概念
- 不需要等待外部事件
- 必须主动调用 `finish_task` 返回结果

如果 Micro Agent 调用 `rest_n_wait`，会导致：
- Micro Agent 无法正常返回
- BaseAgent 的 action 永远拿不到结果
- 整个任务链卡住

### 三种使用模式

#### 1. 完全继承（默认）

```python
# Micro Agent 拥有和 BaseAgent 完全相同的能力
result = await self._run_micro_agent(
    persona="You are a security expert...",
    task="Analyze this code for security issues"
)
```

**适用场景**：
- 需要利用 BaseAgent 的全部能力
- 不确定具体需要哪些 actions
- 希望 Micro Agent 有最大灵活性

#### 2. 限制 Actions（提高准确率）

```python
# 只给必要的 actions，减少 LLM 的选择困难
result = await self._run_micro_agent(
    persona="You are a researcher...",
    task="Research this topic",
    available_actions=[
        "web_search",
        "read_webpage",
        "summarize",
        "finish_task"
    ]
)
```

**适用场景**：
- 任务明确，知道需要哪些 tools
- 希望提高 action 选择准确率
- 需要限制 Micro Agent 的行为范围

#### 3. 排除 Actions（减少干扰）

```python
# 排除不需要的 actions
result = await self._run_micro_agent(
    persona="You are a code reviewer...",
    task="Review this code",
    exclude_actions=[
        "send_email",
        "web_search",
        "git_commit"
    ]
)
```

**适用场景**：
- 大部分 actions 都需要，只有少数不需要
- 防止 Micro Agent 做某些操作
- 基于安全或策略考虑

### 对比：BaseAgent vs Micro Agent

| 特性 | BaseAgent | Micro Agent |
|------|-----------|-------------|
| **生命周期** | 长期运行，处理多封邮件 | 临时执行，完成任务即销毁 |
| **Session** | 维护多个 session | 无 session，每次独立 |
| **Persona** | 固定的 system_prompt | 每次执行可指定不同 persona |
| **Actions** | 固定的 actions_map | 默认继承 BaseAgent，可限制 |
| **返回机制** | rest_n_wait（等待邮件） | finish_task（返回结果） |
| **上下文** | 跨邮件的会话历史 | 独立的对话历史 |
| **用途** | 主任务协调、邮件处理 | 子任务执行、多步决策 |

### 实现细节

#### MicroAgent 类

```python
class MicroAgent:
    def __init__(self, brain, cerebellum, action_registry, name, default_max_steps):
        # 一次性设置核心组件（可重用）
        self.brain = brain
        self.cerebellum = cerebellum
        self.action_registry = action_registry

    async def execute(self, persona, task, available_actions, task_context, max_steps):
        # 每次执行时设置任务参数
        self.persona = persona
        self.task = task
        self.available_actions = available_actions
        # ... 执行 think-act 循环
```

#### BaseAgent._run_micro_agent()

```python
async def _run_micro_agent(self, persona, task, available_actions=None, ...):
    # 1. 创建或复用 MicroAgent 实例
    if not hasattr(self, '_micro_agent_instance'):
        self._micro_agent_instance = MicroAgent(
            brain=self.brain,
            cerebellum=self.cerebellum,
            action_registry=self.actions_map
        )

    # 2. 默认继承所有 actions（排除等待类）
    if available_actions is None:
        available_actions = [
            a for a in self.actions_map.keys()
            if a not in ["rest_n_wait", "take_a_break"]
        ]
    available_actions.append("finish_task")

    # 3. 执行并返回结果
    return await self._micro_agent_instance.execute(
        persona=persona,
        task=task,
        available_actions=available_actions,
        ...
    )
```

### 关键设计决策

#### 1. 为什么不继承 BaseAgent？

**不使用 `class MicroAgent(BaseAgent)` 的原因**：
- BaseAgent 有太多 Micro Agent 不需要的复杂逻辑（邮箱、session 管理、事件循环）
- Micro Agent 是一次性任务，不需要长期状态
- 保持简洁，易于理解和维护

**采用组合而非继承**：
- MicroAgent 持有 brain、cerebellum、action_registry 的引用
- 复用核心能力，但独立实现执行逻辑

#### 2. 为什么 available_actions 默认为 None？

**优点**：
- **最简 API**：只需提供 `persona` 和 `task`
- **自动同步**：BaseAgent 新增 action 后，Micro Agent 自动获得
- **临时人格**：真正体现"相同能力，不同个性"的理念

**对比**：
```python
# 设计 A：必须指定 actions（旧设计）
await self._run_micro_agent(
    persona="...",
    task="...",
    available_actions=["list_files", "read_file", ...]  # 繁琐
)

# 设计 B：默认继承所有 actions（新设计）
await self._run_micro_agent(
    persona="...",
    task="..."
    # available_actions 自动继承，简单！
)
```

#### 3. 为什么需要 finish_task？

**问题**：Micro Agent 如何知道任务完成了？

**方案 1：固定步数**
- 缺点：可能步数不够，或浪费步数

**方案 2：LLM 自行判断**
- 问题：如何明确传达"完成"信号？

**方案 3：专门的 finish_task action（采用）**
```python
# LLM 的思考输出
"I have analyzed the code. I will use finish_task to return the result."

# Micro Agent 检测到 "finish_task"
# 提取结果并返回
```

**优点**：
- 明确的完成信号
- 可以附带返回结果
- LLM 容易理解和使用

### 实际使用示例

#### 场景：代码审查

```python
@register_action("深度代码审查")
async def deep_code_review(self, path: str):
    # BaseAgent 收到任务：审查代码
    # 但审查本身需要多步分析，不适合直接写 code

    # 创建临时人格：资深代码审查专家
    result = await self._run_micro_agent(
        persona="""You are a senior code reviewer with 15 years of experience.
        You focus on:
        1. Security vulnerabilities
        2. Performance issues
        3. Code maintainability
        4. Best practices adherence
        You provide constructive, actionable feedback.""",

        task=f"""Perform a comprehensive code review of the code at {path}

        Review process:
        1. List all files in the project
        2. Read each file systematically
        3. Identify issues in each category
        4. For each issue:
           - Describe the problem
           - Explain the impact
           - Suggest a fix
           - Rate severity
        5. Compile a final report

        Use finish_task when you have completed the review.""",

        # 使用所有 BaseAgent 的 actions
        # Micro Agent 可以 list_files, read_file, search_code 等等
        max_steps=50
    )

    # Micro Agent 完成后，BaseAgent 获得结果并返回
    return f"Code Review Report:\n{result}"
```

### 总结

**Micro Agent = BaseAgent 的临时人格**

- **核心能力继承**：brain、cerebellum、actions_map
- **个性可定制**：通过 persona 参数
- **任务独立**：独立的对话历史和上下文
- **自动返回**：通过 finish_task 返回结果

这个设计使得：
- BaseAgent 可以专注于主任务协调
- 复杂的子任务交给 Micro Agent 处理
- 代码简洁，易于理解和维护
- 灵活性高，可适应各种场景
