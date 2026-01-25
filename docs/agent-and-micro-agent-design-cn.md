# Agent 和 Micro Agent 设计

## 概述

AgentMatrix 实现了一个双层 Agent 系统，包含 **BaseAgent** 和 **MicroAgent**。MicroAgent 被设计为 BaseAgent 的"临时人格"——复用相同的能力，但拥有独立的任务上下文和专注的执行循环。

## 设计理念

- **双脑架构**: 将推理(LLM)与参数协商(SLM)分离
- **Micro Agent 作为临时人格**: 相同能力，不同上下文，独立生命周期
- **基于邮件的通信**: 所有 Agent 间协调使用自然语言消息
- **动态技能组合**: Skills 作为 mixins 在运行时动态加载

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
