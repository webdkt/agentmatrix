# Agent 开发者指南

本文档包含每个 Agent 和 Skill 开发者**必须知道的核心信息**。

## 1. 核心架构

AgentMatrix 使用**双层架构**：

```
BaseAgent (会话层)
  └─ 管理用户会话和对话历史
  └─ 将任务委托给 MicroAgent
  └─ 持久化状态到 session

MicroAgent (执行层)
  └─ 执行单个任务
  └─ 临时执行上下文（执行后消失）
  └─ 通过 think-negotiate-act 循环工作
```

**关键洞察**：`_run_micro_agent()` 就像调用一个**函数**——接收任务并返回结果。可以递归嵌套这些调用。

## 2. 创建 Agent

### 2.1 YAML 配置文件

最小示例 (`profiles/my_agent.yml`)：

```yaml
name: MyAgent
description: 一个有用的助手
module: agentmatrix.agents.base
class_name: BaseAgent

# 加载技能
mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin

# Agent 的人格
system_prompt: |
  你是一个有用的助手。

# 后端模型
backend_model: gpt-4
cerebellum_model: gpt-3.5-turbo
```

**必填字段**：
- `name`：唯一的 Agent 标识符
- `description`：这个 Agent 做什么
- `module`：基类所在的 Python 模块路径
- `class_name`：基类名称
- `system_prompt`：Agent 的人格
- `backend_model`：用于推理的 LLM
- `cerebellum_model`：用于参数协商的 SLM

**可选字段**：
- `mixins`：技能 mixin 类列表
- `max_steps`：最大执行步数（默认：10）
- `temperature`：LLM 温度（默认：0.7）

### 2.2 运行 Agent

```python
from agentmatrix import AgentMatrix

# 初始化
matrix = AgentMatrix(
    agent_profile_path="profiles",
    matrix_path="MyWorld"
)

# 发送任务
email = Email(
    sender="user@example.com",
    recipient="MyAgent",
    subject="你好",
    body="你能帮我吗？",
    user_session_id="session_123"
)

await matrix.post_office.send_email(email)
```

## 3. 编写 Skills

Skills 是带有 `@register_action` 装饰器方法的 Python mixin 类。

### 3.1 基本 Skill 结构

```python
# my_skills.py
class MySkillMixin:
    """包含动作的技能模块"""

    @register_action(
        description="搜索网络信息",
        param_infos={
            "query": "搜索查询字符串",
            "num_results": "结果数量（默认10）"
        }
    )
    async def web_search(self, query: str, num_results: int = 10) -> str:
        """搜索网络并返回结果"""
        results = await self._search_api(query, num_results)
        return f"找到 {len(results)} 个结果"
```

### 3.2 **关键：description 和 param_info 的设计原则**

这是开发 Skill 最重要的部分。

#### description（给 Micro Agent 的 LLM 看）

- **目的**：告诉 LLM 这个 action 能干什么、有哪些选择
- **不要写参数名**：LLM 不知道也不需要知道参数名
- **要充分描述功能**：让 LLM 能决定何时调用、如何描述意图

**示例对比**：

❌ **不好的描述**：
```python
description="写入文件"
# 问题：太简单，LLM 不知道有覆盖/追加两种模式
```

❌ **不好的描述**：
```python
description="通过 target 参数控制是按文件名搜索还是在文件内容中搜索"
# 问题：不应该提 "target 参数"，LLM 不知道什么是参数名
```

✅ **好的描述**：
```python
description="写入内容到文件。支持覆盖写入或追加模式。如果要覆盖已存在的文件，必须明确说明允许覆盖"
# 优点：
# 1. 告诉了 LLM 有两种模式（覆盖/追加）
# 2. 明确说明了行为约束（覆盖已存在文件需要明确说明）
```

✅ **好的描述**：
```python
description="读取文件内容。可指定读取行范围（默认读取前 200 行）。会显示文件统计信息（大小、总行数）"
# 优点：
# 1. 告诉了 LLM 可以指定行范围
# 2. 说明了默认行为
# 3. 提到了额外功能（统计信息）
```

✅ **好的描述**：
```python
description="搜索文件或内容。可选择按文件名搜索（支持 Glob 模式如 *.txt）或在文件内容中搜索关键词（支持正则表达式）。默认在文件内容中搜索。可选择递归或非递归搜索"
# 优点：
# 1. 不提参数名，直接说功能
# 2. 给出具体示例（*.txt）
# 3. 说明默认行为和可选项
```

#### param_info（给 Cerebellum/小脑 看）

- **目的**：帮助小脑理解每个参数的含义，将 LLM 的意图映射到参数（"填空"）
- **要清楚说明**：参数的含义、可能的值、默认值

**好的 param_info**：
```python
param_infos={
    "file_path": "文件路径",
    "content": "文件内容",
    "mode": "写入模式（可选，默认 'overwrite'）。可选值：'overwrite' 覆盖，'append' 追加",
    "allow_overwrite": "是否允许覆盖已存在文件（可选，默认 False）。如果文件存在且mode为overwrite，必须设置为True才能覆盖"
}
```

**检查清单**：
- [ ] description 充分描述了功能，没有提参数名？
- [ ] description 告诉了 LLM 有哪些选择？
- [ ] description 说明了默认行为和约束？
- [ ] param_info 清楚解释了每个参数的含义和可能的值？

### 3.3 调用 MicroAgent

Skills 可以调用 `self._run_micro_agent()` 来执行子任务。

**示例：递归任务分解**

```python
class ResearchSkillMixin:
    @register_action(
        description="深入研究一个主题。可以指定研究深度，默认为2层",
        param_infos={
            "topic": "研究主题",
            "depth": "研究深度（默认2层）"
        }
    )
    async def deep_research(self, topic: str, depth: int = 2) -> dict:
        """通过递归调用 MicroAgent 进行研究"""

        if depth <= 0:
            # 基础情况：简单搜索
            return await self._run_micro_agent(
                persona="你是一个研究员",
                task=f"搜索关于 {topic} 的信息",
                available_actions=["web_search"]
            )

        # 递归情况：分解为子主题
        subtopics_result = await self._run_micro_agent(
            persona="你是一个研究规划师",
            task=f"将 '{topic}' 分解为 3-5 个子主题",
            available_actions=["think_only"]
        )

        # 递归研究每个子主题
        results = {}
        for subtopic in subtopics_result["subtopics"]:
            results[subtopic] = await self.deep_research(subtopic, depth - 1)

        return {
            "topic": topic,
            "sub_research": results
        }
```

**`_run_micro_agent()` 参数**：

```python
await self._run_micro_agent(
    persona="你是...",                   # 必需：这个 MicroAgent 是谁？
    task="做这个任务",                   # 必需：它应该做什么？
    available_actions=["action1", ...], # 可选：它可以使用哪些动作？
    max_steps=10,                       # 可选：最大执行步数
    max_time=5.0,                       # 可选：最大执行时间（分钟）
    exclude_actions=["action2", ...]    # 可选：排除某些动作
)
```

**关键点**：
- 每次调用都会创建一个**新的隔离执行上下文**
- 嵌套调用不会互相污染历史
- 鼓励使用递归嵌套来处理复杂任务

## 4. Session 管理

BaseAgent 通过 session 管理会话状态：

```python
# 获取 session context
context = self.get_session_context()

# 更新 session context（自动持久化）
await self.update_session_context(
    key1="value1",
    key2="value2"
)

# 获取 transient context（不持久化）
value = self.get_transient("notebook")

# 设置 transient context
self.set_transient("notebook", notebook_obj)
```

**MicroAgent 的 session 支持**：

MicroAgent 的 `execute()` 方法支持 session 参数，用于持久化对话历史：

```python
# 在 MicroAgent.execute() 层面
result = await micro_core.execute(
    persona="...",
    task="...",
    available_actions=[...],
    session=session_obj,           # 可选：session 对象
    session_manager=session_mgr    # 可选：session manager
)
```

这允许 MicroAgent 在多次执行间恢复对话历史。

## 5. 重要约束

### 5.1 状态隔离

**✅ 应该**：在 BaseAgent 中存储会话级状态
```python
class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        self.user_preferences = {}  # OK：会话级状态
```

**❌ 不应该**：在 BaseAgent 中存储执行状态
```python
# 避免这样
class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        self.current_step = 0  # 不好：执行状态
```

**为什么**：BaseAgent 管理多个会话。执行状态属于 MicroAgent（它是临时的）。

### 5.2 MicroAgent 生命周期

**MicroAgent 在执行后消失**：
```python
# MicroAgent 执行
result = await self._run_micro_agent(task="做某事")

# 这行之后，MicroAgent 就消失了
# 不要尝试访问它的内部状态
```

**✅ 应该**：捕获结果
```python
result = await self._run_micro_agent(task="...")
self.last_result = result  # OK：存储结果，不是 MicroAgent
```

## 6. 快速参考

### 6.1 YAML 配置字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 唯一的 Agent 标识符 |
| `description` | 是 | 这个 Agent 做什么 |
| `module` | 是 | Python 模块路径（例如 `agentmatrix.agents.base`） |
| `class_name` | 是 | 基类名称（例如 `BaseAgent`） |
| `system_prompt` | 是 | Agent 的人格和行为 |
| `backend_model` | 是 | 用于推理的 LLM（例如 `gpt-4`） |
| `cerebellum_model` | 是 | 用于参数协商的 SLM（例如 `gpt-3.5-turbo`） |
| `mixins` | 否 | 技能 mixin 类列表 |
| `max_steps` | 否 | 最大 MicroAgent 步数（默认：10） |
| `temperature` | 否 | LLM 温度（默认：0.7） |

### 6.2 @register_action 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `description` | 是 | **给 LLM 看的**功能描述，不要提参数名 |
| `param_infos` | 否 | **给小脑看的**参数名到描述的映射字典 |

### 6.3 _run_micro_agent() 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `persona` | 是 | MicroAgent 的人格（自然语言） |
| `task` | 是 | 任务描述（自然语言） |
| `available_actions` | 否 | 它可以使用的动作名称列表（默认：所有动作） |
| `max_steps` | 否 | 最大步数（默认：来自 BaseAgent） |
| `max_time` | 否 | 最大时间（分钟） |
| `exclude_actions` | 否 | 要排除的 actions（默认排除等待类） |

## 7. 常见模式

### 模式 1：简单动作
```python
@register_action(description="做简单任务")
async def simple_task(self, input: str) -> str:
    return f"已处理：{input}"
```

### 模式 2：带 MicroAgent 子任务的动作
```python
@register_action(description="做复杂任务")
async def complex_task(self, input: str) -> dict:
    sub_result = await self._run_micro_agent(
        persona="你是一个专家",
        task=f"分析：{input}"
    )
    return sub_result
```

### 模式 3：递归分解
```python
@register_action(description="分解并执行")
async def recursive_task(self, task: str, depth: int = 0) -> dict:
    if depth > 3:
        return await self._run_micro_agent(task=f"执行：{task}")

    # 分解
    subtasks = await self._run_micro_agent(
        task=f"分解：{task}"
    )

    # 递归执行
    results = {}
    for subtask in subtasks["subtasks"]:
        results[subtask] = await self.recursive_task(subtask, depth + 1)

    return results
```

## 8. 故障排除

**问题**：MicroAgent 返回意外的输出
- **解决方案**：改进 description，让它更清楚

**问题**：MicroAgent 选错 action
- **解决方案**：改进 description，说明什么时候用哪个 action

**问题**：Cerebellum 提取参数错误
- **解决方案**：改进 param_info，更清楚地说明参数含义

**问题**：任务耗时太长
- **解决方案**：减少 `max_steps` 或分解为更小的子任务

---

更多详情，请参阅：
- [Agent 和 Micro Agent 设计](agent-and-micro-agent-design-cn.md)
- [Think-With-Retry 模式](think-with-retry-pattern-cn.md)
- [Matrix World 架构](matrix-world-cn.md)
