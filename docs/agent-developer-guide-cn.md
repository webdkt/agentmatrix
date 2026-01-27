# Agent 开发者指南

本文档包含每个 Agent 和 Skill 开发者**必须知道的核心信息**。在编写你的第一个 Agent 之前请先阅读本文。

## 1. 核心概念

AgentMatrix 使用**双层架构**：

```
BaseAgent (会话层)
  └─ 管理对话和用户会话
  └─ 拥有技能和能力
  └─ 将任务委托给 MicroAgent

MicroAgent (执行层)
  └─ 执行单个任务
  └─ 继承 BaseAgent 的能力
  └─ 有独立的执行上下文
  └─ 完成后终止
```

**执行流程**：
```
用户发送邮件
  → BaseAgent 接收
  → 委托给 MicroAgent
  → MicroAgent 执行动作
  → 返回结果给 BaseAgent
  → BaseAgent 回复用户
```

**关键洞察**：`MicroAgent.execute()` 就像调用一个**函数**——它接收任务并返回结果。你可以递归嵌套这些调用。

## 2. 创建 Agent

### 2.1 创建 YAML 配置文件

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

### 2.2 运行你的 Agent

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
        # 实现
        results = await self._search_api(query, num_results)
        return f"找到 {len(results)} 个结果"
```

**关键点**：
- Skills 是 **mixin 类**（可以组合）
- 动作是带 `@register_action` 装饰器的 **async 方法**
- 返回类型通常是 `str`（自然语言）或 `dict`（结构化数据）

### 3.2 @register_action 装饰器

```python
@register_action(
    description="这个动作做什么的清晰自然语言描述",
    param_infos={
        "param1": "参数 1 的描述",
        "param2": "参数 2 的描述（默认值在描述中说明）"
    }
)
async def my_action(self, param1: str, param2: int = 10) -> str:
    pass
```

**参数**：
- `description`：这个动作做什么（自然语言）。MicroAgent 的 LLM 会读取这个描述来决定何时调用它。
- `param_infos`：可选的参数描述字典。帮助 Cerebellum 协商参数值。

### 3.3 在 Skill 中调用 MicroAgent（关键！）

这是**最重要的模式**：Skills 可以调用 `self._run_micro_agent()` 来执行子任务。

**示例：递归任务分解**

```python
class ResearchSkillMixin:
    @register_action(
        description="深入研究一个主题",
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
                available_actions=["web_search"],
                result_params={
                    "expected_schema": {
                        "summary": "简要摘要",
                        "key_points": ["主要观点"]
                    }
                }
            )
        
        # 递归情况：分解为子主题
        subtopics_result = await self._run_micro_agent(
            persona="你是一个研究规划师",
            task=f"将 '{topic}' 分解为 3-5 个子主题",
            available_actions=["think_only"],
            result_params={
                "expected_schema": {
                    "subtopics": ["子主题列表"]
                }
            }
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
    initial_history=[],                  # 可选：之前的对话历史
    result_params={                      # 可选：期望的输出格式
        "expected_schema": {
            "field1": "字段描述",
            "field2": ["项目列表"]
        }
    }
)
```

**关键点**：
- 每次 `_run_micro_agent()` 调用都会创建一个**新的隔离执行上下文**
- 嵌套调用不会互相污染历史
- 使用 `result_params["expected_schema"]` 请求结构化输出
- 鼓励使用递归嵌套来处理复杂任务

### 3.4 返回格式

**自然语言（最简单）**：
```python
async def simple_action(self, query: str) -> str:
    return f"已处理：{query}"
```

**结构化数据（推荐用于组合）**：
```python
async def structured_action(self, query: str) -> dict:
    result = await self._run_micro_agent(
        task=f"处理 {query}",
        result_params={
            "expected_schema": {
                "status": "成功/失败",
                "data": "结果数据",
                "metadata": {"key": "value"}
            }
        }
    )
    return result  # 返回匹配模式的字典
```

## 4. 重要约束

### 4.1 状态隔离

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

### 4.2 MicroAgent 生命周期

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

**❌ 不应该**：尝试重用 MicroAgent
```python
micro_agent = self._run_micro_agent(...)  # 返回结果，不是 agent
# 你不能再次调用 micro_agent
```

### 4.3 不要混用层的概念

**✅ 应该**：BaseAgent 用于会话，MicroAgent 用于执行
```python
# 在 BaseAgent 方法中
async def process_email(self, email):
    session = self._get_session(email)  # 会话：BaseAgent
    result = await self._run_micro_agent(...)  # 执行：MicroAgent
    session.add_result(result)  # 更新会话
```

**❌ 不应该**：在 BaseAgent 中处理执行状态
```python
# 避免这样
async def process_email(self, email):
    self.step_count = 0  # 不好：在 BaseAgent 中执行
    while self.step_count < 10:
        # ...
```

## 5. 快速参考

### 5.1 YAML 配置字段

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

### 5.2 @register_action 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `description` | 是 | 动作做什么的自然语言描述 |
| `param_infos` | 否 | 参数名到描述的映射字典 |

### 5.3 _run_micro_agent() 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `persona` | 是 | MicroAgent 的人格（自然语言） |
| `task` | 是 | 任务描述（自然语言） |
| `available_actions` | 否 | 它可以使用的动作名称列表（默认：所有动作） |
| `max_steps` | 否 | 最大步数（默认：来自 BaseAgent） |
| `initial_history` | 否 | 要继续的之前的对话（默认：空） |
| `result_params` | 否 | 输出格式规范，包括 `expected_schema` |

## 6. 常见模式

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
    # 使用 MicroAgent 处理子任务
    sub_result = await self._run_micro_agent(
        persona="你是一个专家",
        task=f"分析：{input}",
        result_params={"expected_schema": {"analysis": "字符串"}}
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
        task=f"分解：{task}",
        result_params={"expected_schema": {"subtasks": ["字符串"]}}
    )
    
    # 递归执行
    results = {}
    for subtask in subtasks["subtasks"]:
        results[subtask] = await self.recursive_task(subtask, depth + 1)
    
    return results
```

## 7. 故障排除

**问题**：MicroAgent 返回意外的输出
- **解决方案**：使用 `result_params["expected_schema"]` 指定期望的格式

**问题**：任务耗时太长
- **解决方案**：减少 `max_steps` 或分解为更小的子任务

**问题**：上下文变得混乱
- **解决方案**：使用递归 MicroAgent 调用——每个都有隔离的上下文

**问题**：执行后无法访问 MicroAgent 状态
- **解决方案**：捕获结果——MicroAgent 执行后就消失了

---

更多详情，请参阅：
- [Agent 和 Micro Agent 设计](agent-and-micro-agent-design-cn.md)
- [Think-With-Retry 模式](think-with-retry-pattern-cn.md)
- [Matrix World 架构](matrix-world-cn.md)
