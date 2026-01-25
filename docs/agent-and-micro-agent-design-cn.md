# Agent 和 Micro Agent 设计

## 概述

### 为什么要分两层

做 Agent 的时候有个实际问题：**一次对话可能包含多个任务，而每个任务又要分多步执行。**

比如说用户和 Researcher Agent 正在对话（这是一个 session），用户说"帮我研究一下 AI 安全"。这个任务本身可能需要多步：先搜索资料、再阅读论文、最后整理报告。这些是 MicroAgent 的执行步骤。

如果把这些混在一起，状态会很乱：session 级别的对话历史、任务级别的执行状态、步数计数器……全都堆在 BaseAgent 里，代码很难维护，bug 也难找。

常见的两种做法都不太理想：

1. **全塞进 BaseAgent**：session 历史、任务状态、执行步数全在一个对象里。状态一大堆，职责不清，改一个地方可能影响另一个。

2. **每个任务起个新 Agent**：干净倒是干净，但新 Agent 得重新配置、重新加载技能，而且访问不到原 Agent 的上下文。

### 我们的方案：BaseAgent（会话层）+ MicroAgent（执行层）

我们把"会话管理"和"任务执行"分开：

**BaseAgent = 会话层**
- 管理 session 级别的状态（可以有多个独立的 session）
- 每个 session 有自己的对话历史、上下文
- 拥有技能、动作等能力（这些是全局的，跨 session 共享）
- 收到用户任务后，委托给 MicroAgent 执行

**MicroAgent = 执行层**
- 专门跑单个任务（一次 think-act 循环）
- 继承 BaseAgent 的所有能力（brain、cerebellum、action registry）
- 有自己独立的执行上下文（任务描述、执行历史、步数计数）
- 任务完成或超限就结束，返回结果

关键点：**MicroAgent 不是另一个 Agent 类**，它是 BaseAgent 为了执行某个任务而创建的"临时执行上下文"。你可以把它理解为 BaseAgent 进入"专注干活模式"，干完活就回到正常状态。

### 为什么要这么分

**1. 职责清晰**
- BaseAgent 管 session：这是哪个会话、历史消息是什么、用户在聊什么
- MicroAgent 管执行：我现在在干嘛、下一步是什么、到第几步了
- 不同层次的状态分开管理，代码好懂

**2. 状态隔离**
- BaseAgent 的 session 历史不会被执行步数、中间结果污染
- MicroAgent 的执行状态（步数、中间结果）不会进 session 历史
- MicroAgent 完事就消失，不用操心状态清理

**3. 支持并发**
- 一个 BaseAgent 可以同时维护多个 session
- 每个 session 可以有自己的 MicroAgent 在执行任务
- 互不干扰，各自管各自的状态

**4. 失败不伤 session**
- 任务失败了（超限、解析错误等），只影响这次 MicroAgent 执行
- BaseAgent 的 session 还在，可以报告失败、让用户澄清、或者换个方式重试
- 用户对话不受影响

**5. 🔥 递归嵌套与 "LLM 函数"（革命性特性）**

这是双层架构最强大的方面：

**MicroAgent 调用可以递归嵌套**：

```
MicroAgent 第 1 层
  ├─ 执行: web_search() 动作
  │   └─ 这个动作内部调用:
  │       └─ MicroAgent 第 2 层（处理和分析搜索结果）
  │           ├─ 执行: summarize_content() 动作
  │           │   └─ 这个动作内部调用:
  │           │       └─ MicroAgent 第 3 层（提取关键信息）
  │           │           └─ 返回结构化数据给第 2 层
  │           └─ 返回分析结果给第 1 层
  └─ 返回最终结果给 BaseAgent
```

**关键特性**：

1. **完美状态隔离**：每一层的执行历史都完全隔离：
   - 第 3 层的推理过程不会污染第 2 层的上下文
   - 第 2 层的中间步骤不会干扰第 1 层的上下文
   - 每层只看到下层的最终结果

2. **MicroAgent 作为 "LLM 函数"**：
   - 把 `micro_agent.execute()` 看作**自然语言函数**
   - 不是传统的 Python 函数（确定性逻辑）
   - 不是聊天机器人对话（来回对话）
   - 它是一个**概率性推理单元**，具有：
     - **输入**：自然语言任务描述
     - **处理**：LLM 推理 + 多步 think-act 循环
     - **输出**：自然语言结果 或 结构化数据（通过 `expected_schema`）

3. **可组合性**：
   - 通过组合简单的 LLM 函数构建复杂工作流
   - 每个函数都有独立的上下文和执行历史
   - 自然递归：任务可以递归分解为子任务

**示例：递归任务分解**

```python
async def breakdown_task(task: str, depth: int = 0) -> Dict:
    """用于递归任务分解的 LLM 函数"""
    if depth > 3:  # 递归终止条件
        return await execute_simple_task(task)

    # 使用 MicroAgent 分解任务
    subtask_result = await self._run_micro_agent(
        persona="你是一个任务规划师",
        task=f"将 '{task}' 分解为 3-5 个子任务",
        result_params={
            "expected_schema": {
                "subtasks": ["子任务列表"],
                "priority": "优先级"
            }
        }
    )

    # 递归处理每个子任务
    results = {}
    for subtask in subtask_result["subtasks"]:
        # 递归调用 MicroAgent - 每个都有隔离的上下文
        results[subtask] = await breakdown_task(subtask, depth + 1)

    return results
```

**为什么这很重要**：

- ✅ **简洁性**：复杂的多步工作流变成简单的函数组合
- ✅ **清晰性**：每一层都有干净、隔离的上下文
- ✅ **健壮性**：第 3 层失败不会破坏第 1 或第 2 层
- ✅ **灵活性**：像搭积木一样组合 LLM 函数
- ✅ **可扩展性**：从简单原语构建任意复杂的工作流

这从根本上不同于传统函数调用或聊天机器人交互——这是一个新范式：**具有概率性推理和完美隔离的自然语言函数**。

### 实际执行流程

用户发邮件给 BaseAgent 时：

```
1. BaseAgent 收到邮件
   ├─ 看 in_reply_to，这是哪个 session？
   ├─ 恢复或创建 TaskSession（session 级别的对话历史）
   └─ 委托给 MicroAgent 执行本次任务

2. MicroAgent 执行
   ├─ 继承 BaseAgent 的能力（brain、cerebellum、actions）
   ├─ 初始化本次任务的执行上下文
   ├─ 跑 think-negotiate-act 循环
   │  ├─ 思考：下一步该干嘛？
   │  ├─ 从 LLM 输出检测动作
   │  ├─ 协商参数（通过 Cerebellum）
   │  ├─ 执行动作
   │  └─ 重复直到 finish_task 或到步数上限
   └─ 返回结果给 BaseAgent

3. BaseAgent 更新 session
   ├─ 把 MicroAgent 的结果写入 session 历史
   └─ 给用户发回复邮件
```

注意：MicroAgent 执行过程中的中间思考、动作调用等，不会进 session 历史。只有最终结果会记录到 session 中。

## 设计理念

这个双层架构的核心思想：

**1. 会话和执行分离**
- 会话（session）是对话级别的，可能持续很长时间
- 执行（task）是任务级别的，通常几分钟就完成
- 一次对话可能包含多次任务执行

**2. 能力继承，状态独立**
- MicroAgent 复用 BaseAgent 的能力，不影响 BaseAgent 的状态
- 就像公司员工：用公司的技能和工具干活，但工作记录是自己的

**3. 自然语言协调**
- BaseAgent 和 MicroAgent 通过同样的 LLM 接口交流
- 不需要特殊的 API —— 就是提示词和上下文管理
- MicroAgent 本质上是 BaseAgent 内部的一次"专注对话"

**4. 双脑架构**
- **Brain (LLM)**：负责推理、理解、生成
- **Cerebellum (SLM)**：负责参数解析、JSON 生成
- 不同任务用不同能力的模型，成本和效果都更好

**5. 动态组合技能**
- 技能是 mixins，通过 YAML 配置加载
- BaseAgent 的能力可组合、可扩展
- MicroAgent 自动拥有 BaseAgent 的所有技能

**6. 用邮件通信**
- Agent 之间的通信都用自然语言（Email）
- 通过 `in_reply_to` 维护线程关系
- 靠"解释"而不是"API 调用"来协调 —— 更好理解，也更好调试

## BaseAgent

**位置**: `src/agentmatrix/agents/base.py`

### 核心组件

```python
class BaseAgent(FileSkillMixin, AutoLoggerMixin):
    def __init__(self, profile):
        # 身份信息
        self.name = profile["name"]
        self.description = profile["description"]
        self.system_prompt = profile["system_prompt"]

        # 双脑架构
        self.brain = None      # LLM 客户端，用于高层推理
        self.cerebellum = None # SLM，用于参数协商

        # 动作注册表
        self.actions_map = {}   # 名称 -> 方法引用
        self.actions_meta = {}  # 名称 -> 元数据(描述、参数)

        # 会话管理
        self.sessions = {}      # 每个对话一个 TaskSession
        self.reply_mapping = {} # 邮件线程(in_reply_to -> 会话)

        # Micro Agent 核心(懒初始化)
        self._micro_core = None
```

### 动作注册

动作是使用 `@register_action` 装饰器标记的方法:

```python
@register_action(
    description="搜索网络信息",
    param_infos={
        "query": "搜索查询字符串",
        "num_results": "返回结果数量"
    }
)
async def web_search(self, query: str, num_results: int = 10):
    # 实现
    pass
```

装饰器将方法标记为动作并存储元数据。初始化期间，`_scan_methods()` (89-105行) 发现所有装饰的方法并构建动作注册表。

### 邮件处理流程

**主入口**: `process_email()` (244-286行)

1. **接收邮件**: 来自 PostOffice 的传入邮件
2. **线程处理**: 检查 `in_reply_to` 以恢复对话上下文
3. **Micro Agent 执行**: 将任务委托给 MicroAgent
4. **响应**: 发送回复邮件并附带结果

```python
async def process_email(self, email: Email):
    # 恢复或创建会话
    session = self._get_or_create_session(email)

    # 使用 Micro Agent 执行
    result = await self._run_micro_agent(
        persona=self.system_prompt,
        task=email.body,
        available_actions=self.actions_map.keys(),
        session_history=session.history
    )

    # 更新会话并发送回复
    session.add_message(email.body, result)
    await self._send_reply(email, result)
```

### 便捷方法

**`_run_micro_agent()`** (597-683行): 懒初始化 MicroAgent 并执行任务。

```python
async def _run_micro_agent(self, persona, task, available_actions,
                           initial_history=None, result_params=None):
    if self._micro_core is None:
        self._micro_core = MicroAgent(
            brain=self.brain,
            cerebellum=self.cerebellum,
            action_registry=self.actions_map,
            name=self.name,
            default_max_steps=10
        )

    return await self._micro_core.execute(
        persona=persona,
        task=task,
        available_actions=available_actions,
        initial_history=initial_history,
        result_params=result_params
    )
```

## MicroAgent

**位置**: `src/agentmatrix/agents/micro_agent.py`

### 设计概念

MicroAgent 不是一个独立的 Agent 类——它是一个临时执行模式:

- 复用 BaseAgent 的 brain、cerebellum 和 action registry
- 拥有独立的执行上下文(任务、历史、步数)
- 任务完成或达到 max_steps 时终止
- 无持久状态——结果流回 BaseAgent

### 执行机制

**主方法**: `execute()` (68-152行)

```python
async def execute(self, persona, task, available_actions,
                 max_steps=None, initial_history=None, result_params=None):
    # 初始化上下文
    self.persona = persona
    self.task = task
    self.available_actions = available_actions
    self.max_steps = max_steps or self.default_max_steps
    self.history = initial_history or []
    self.result_params = result_params

    # 运行思考-协商-行动循环
    await self._run_loop()

    return self.result
```

### 思考-协商-行动循环

**`_run_loop()`** (208-256行)

```python
async def _run_loop(self):
    for self.step_count in range(1, self.max_steps + 1):
        # 1. 思考 - 调用 brain 进行推理
        thought = await self._think()

        # 2. 从思考输出中检测动作
        action_name = self._detect_action(thought)

        # 3. 执行或完成
        if action_name == "finish_task":
            result = await self._execute_action(action_name, thought)
            self.result = result
            break  # 返回到 BaseAgent
        elif action_name:
            result = await self._execute_action(action_name, thought)
            # 添加反馈并继续循环
        else:
            # 未检测到动作 - 重试或请求澄清
            pass
```

### 动作检测

**`_detect_action()`** (262-285行)

在 LLM 输出中使用简单的子串匹配:

```python
def _detect_action(self, thought: str) -> Optional[str]:
    """使用子串匹配在思考输出中查找动作名称"""
    for action in sorted(self.available_actions, key=len, reverse=True):
        if action in thought:
            return action
    return None
```

- 动作按长度排序(最长优先)以避免部分匹配
- 如果未检测到动作则返回 `None`
- 返回 `"finish_task"` 以终止执行

### 带参数协商的动作执行

**`_execute_action()`** (288-378行)

1. **解析动作意图**: 提取要执行的动作
2. **参数协商**(通过 Cerebellum):
   - 获取动作参数模式
   - 循环直到参数清晰或达到最大轮次
   - 使用 SLM(Cerebellum)生成 JSON
   - 如需要则向 brain(LLM)请求澄清
3. **执行动作**: 使用协商的参数调用实际方法
4. **返回结果**: 为下一次迭代提供反馈

## Skills 系统

### 定义

Skills 是具有内置智能的自然语言接口函数，可动态挂载到 agents。

**关键特征**:
- 使用 `@register_action` 装饰
- 包含自然语言描述
- 在 agent 初始化期间自动发现
- 通过 mixins 在 agents 之间复用

### Skill 示例

**位置**: `src/agentmatrix/skills/web_searcher.py`

```python
class WebSearcherMixin:
    @register_action(
        description="使用搜索引擎搜索网络信息",
        param_infos={
            "query": "搜索查询",
            "num_results": "返回结果数量(默认10)"
        }
    )
    async def web_search(self, query: str, num_results: int = 10) -> str:
        # 使用搜索 API 实现
        results = await self._search_api(query, num_results)
        return self._format_results(results)
```

### 通过 Mixins 动态加载

**位置**: `src/agentmatrix/core/loader.py` (66-188行)

Agent 配置文件(YAML)指定 mixins:

```yaml
# profiles/planner.yml
name: Planner
description: 一个规划 agent
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.project_management.ProjectManagementMixin
```

**动态类创建**:

```python
# 加载 mixin 类
mixin_classes = []
for mixin_path in profile["mixins"]:
    mixin_class = import_module(mixin_path)
    mixin_classes.append(mixin_class)

# 使用多重继承创建 agent 类
agent_class = type(
    f"Dynamic{class_name}",
    (base_agent_class, *mixin_classes),  # 多重继承
    {}  # 类属性
)

# 实例化 agent
agent = agent_class(profile)
```

这允许灵活组合能力而无需修改基类。

### Skill 组合

优势:
- **模块化**: 每个 skill 是自包含的
- **可复用性**: 同一个 skill 被多个 agents 使用
- **可扩展性**: 添加新 skills 而无需更改核心
- **关注点分离**: Skills 独立于 agent 逻辑

## 通信机制

### 基于邮件的消息传递

**位置**: `src/agentmatrix/core/message.py`

所有 Agent 间通信使用 `Email` 数据类:

```python
@dataclass
class Email:
    id: str                  # 唯一邮件 ID
    sender: str              # 发送者 agent 名称
    recipient: str           # 接收者 agent 名称
    subject: str             # 邮件主题
    body: str                # 邮件正文(自然语言)
    in_reply_to: str         # 线程 ID 用于对话上下文
    user_session_id: str     # 用户会话跟踪
```

**关键特性**:
- **线程化**: `in_reply_to` 链接相关消息
- **自然语言**: 正文包含自由格式文本
- **用户会话**: 跨 agents 跟踪用户对话

### PostOffice

**位置**: `src/agentmatrix/agents/post_office.py`

PostOffice 提供异步消息路由和服务发现:

```python
class PostOffice:
    def __init__(self):
        self.yellow_page = {}      # 服务注册表(名称 -> agent)
        self.inboxes = {}           # Agent 收件箱(名称 -> 队列)
        self.vector_db = None       # 用于邮件搜索
        self.user_sessions = {}     # 用户会话跟踪

    async def send_email(self, email: Email):
        """将邮件路由到接收者的收件箱"""
        recipient_inbox = self.inboxes.get(email.recipient)
        if recipient_inbox:
            await recipient_inbox.put(email)

    async def get_email(self, agent_name: str, timeout: float = None):
        """从 agent 的收件箱检索下一封邮件"""
        inbox = self.inboxes.get(agent_name)
        return await inbox.get()

    def register_agent(self, agent: BaseAgent):
        """注册 agent 以进行通信"""
        self.yellow_page[agent.name] = agent
        self.inboxes[agent.name] = asyncio.Queue()
```

**关键特性**:
- **服务发现**: 黄页将 agent 名称映射到实例
- **异步路由**: 非阻塞消息传递
- **向量搜索**: 按内容查找相关邮件
- **会话管理**: 跟踪用户对话

### Agent 间协作模式

示例: Planner agent 委托给 Researcher agent

```python
# Planner 的动作
@register_action(description="将研究任务委托给 Researcher agent")
async def delegate_research(self, task_description: str) -> str:
    # 组成邮件
    email = Email(
        id=str(uuid.uuid4()),
        sender=self.name,
        recipient="Researcher",
        subject=f"研究任务: {task_description}",
        body=task_description,
        user_session_id=self.current_session_id
    )

    # 通过 PostOffice 发送
    await self.post_office.send_email(email)

    # 等待回复
    reply_email = await self.post_office.get_email(
        self.name,
        timeout=300  # 5 分钟
    )

    return reply_email.body
```

这种自然语言协调实现了灵活、可解释的协作。

## 总结

| 组件 | 位置 | 职责 |
|------|------|------|
| BaseAgent | agents/base.py | 主 agent，处理邮件和动作注册表 |
| MicroAgent | agents/micro_agent.py | 临时任务执行器，具有思考-行动循环 |
| @register_action | core/action.py | 将方法标记为动作的装饰器 |
| AgentLoader | core/loader.py | 使用 mixins 进行动态类组合 |
| PostOffice | agents/post_office.py | 消息路由和服务发现 |
| Email | core/message.py | Agent 间通信数据结构 |

### 关键设计决策

1. **双脑架构**: 将推理(LLM)与参数解析(SLM)分离
2. **Micro Agent 作为临时人格**: 使用独立上下文复用组件
3. **基于邮件的通信**: Agents 之间使用自然语言协调
4. **基于 Mixin 的 Skills**: 灵活的能力组合
5. **通过子串匹配进行动作检测**: 对 LLM 输出简单有效

### 开发指南

添加新功能时:

1. **定义动作**: 使用带有清晰描述的 `@register_action`
2. **创建 Skills**: 实现为带有 `*SkillMixin` 命名的 mixin 类
3. **在配置文件中注册**: 添加到 YAML `mixins` 列表
4. **使用 MicroAgent 测试**: 使用 `_run_micro_agent()` 进行单任务执行
5. **通过邮件通信**: 使用 PostOffice 进行 agent 间协调
