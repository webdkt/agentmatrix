# Agent 和 MicroAgent 设计

**文档版本**: v0.3.0 | **最后更新**: 2026-03-01 | **状态**: ✅ 已实现

## 概述

### 核心概念

AgentMatrix 采用双层架构来分离会话管理和任务执行：

- **Agent（会话层）**: 长期运行，管理多个会话，提供能力
- **MicroAgent（执行层）**: 临时执行单个任务，独立上下文

### 为什么分离

一次对话可能包含多个任务，每个任务又分多步执行。如果混在一起：
- 状态混乱：对话历史、任务状态、执行步数堆在一起
- 难以维护：修改一个可能破坏另一个
- 无法嵌套：无法支持任务的递归分解

### 架构价值

| 价值 | 说明 |
|------|------|
| **职责清晰** | Agent 管对话，MicroAgent 管执行 |
| **状态隔离** | 对话历史不被执行步骤污染 |
| **递归嵌套** | MicroAgent 可创建子 MicroAgent，支持任务层层分解 |
| **失败隔离** | 任务失败不影响会话 |

## 核心实体

### Agent（会话管理者）

**代码位置**: `src/agentmatrix/agents/base.py`

**核心职责**：
- 管理多个独立的会话（sessions）
- 拥有技能包（Skills）和动作注册表
- 创建 MicroAgent 执行具体任务
- 维护可持久化的对话记忆

**初始化代码**：

```python
class BaseAgent(AutoLoggerMixin):
    def __init__(self, profile):
        # 基本信息
        self.name = profile["name"]
        self.description = profile["description"]

        # Persona 系统（支持多 persona）
        self.persona_config = profile.get("persona", {"base": ""})

        # 其他 prompts（如 task_prompt）
        self.other_prompts = profile.get("prompts", {})

        # 双脑架构
        self.brain = None           # LLM - 高级推理
        self.cerebellum = None      # SLM - 参数协商
        self.vision_brain = None    # 视觉模型 ✨

        # 能力注册
        self.action_registry = {}   # name -> bound_method
        self.actions_meta = {}      # name -> metadata

        # 会话管理
        self.session_manager = None

        # 事件回调 ✨
        self.async_event_callback = None

        # 扫描所有 actions
        self._scan_all_actions()
```

**Persona 系统** ✨：

支持多个可切换的 persona，每个 persona 是独立的 prompt 模板：

```python
# 配置文件
persona:
  base: "你是一个有帮助的助手"
  planner: "你是项目规划专家，擅长任务分解"
  researcher: "你是信息收集专家"

# 代码中使用
persona = self.get_persona(
    persona_name="researcher",
    task_type="web_search"
)
```

**Skill Prompt 系统** ✨：

每个 skill 可以有独立的 prompt 模板，存储在 `prompts/skills/{skill_name}/{prompt_name}.txt`：

```python
# 获取 skill prompt
prompt = self.get_skill_prompt(
    skill_name="browser_use",
    prompt_name="task_optimization",
    task_description="搜索论文"
)
```

### Agent 控制机制 ✨

Agent 提供运行时控制能力，可以随时暂停/恢复执行，并查询当前状态。

**核心功能**：
- **暂停执行**：随时暂停 Agent 及其所有嵌套的 MicroAgent
- **恢复执行**：从暂停点恢复，继续执行
- **状态查询**：实时获取当前执行状态（嵌套层次、当前任务等）

**工作原理**：

```
检查点机制
├─ 循环开始：每次 MicroAgent 循环开始时检查
├─ Think 之前：LLM 调用前检查
└─ Action 之前：每个 action 执行前检查

暂停标志（BaseAgent._paused）
├─ True：所有检查点会挂起协程
└─ False：正常执行
```

**控制方法**：

```python
# 暂停 Agent
await agent.pause()

# 恢复 Agent
await agent.resume()

# 查询状态
status = agent.current_status
# 返回：
# {
#     "agent_name": "Tom",
#     "status": "paused" | "running" | "idle",
#     "paused": True,
#     "stack_depth": 2,
#     "current_frame": {
#         "micro_agent_id": "...",
#         "task": "搜索论文",
#         "action": "web_search",
#         "llm_thinking": False
#     },
#     "execution_stack": [...]
# }
```

**嵌套处理**：

所有 MicroAgent 共享同一个暂停标志，但检查点只在最内层有效：

```python
BaseAgent (Tom)
└─ MicroAgent_A (第1层)
    └─ await MicroAgent_B.execute() (第2层)
        └─ await web_search() (挂起等待)

# 暂停时：
# - MicroAgent_B 在下一次循环检查时挂起
# - MicroAgent_A 和 MicroAgent_A 的父层本来就在 await，自动"暂停"
```

**Server API**：

```bash
# 暂停
POST /api/agents/{name}/pause

# 恢复
POST /api/agents/{name}/resume

# 查询状态
GET /api/agents/{name}/status
```

**使用场景**：
- 调试：暂停 Agent 查看中间状态
- 资源控制：临时释放资源
- 人工干预：暂停后手动调整再恢复
- 监控：实时查看 Agent 在做什么

### ask_user 交互机制 💬

Agent 可以在执行过程中向用户提问，等待用户回答后继续执行。

**核心功能**：
- **LLM 主动提问**：Agent 根据任务需要，决定何时询问用户
- **执行挂起**：提问后 Agent 挂起执行，等待用户输入
- **恢复继续**：用户回答后，Agent 自动恢复并继续执行
- **嵌套支持**：支持嵌套 MicroAgent 中的 ask_user

**工作原理**：

```
MicroAgent 执行流程
  ↓
think() → LLM 决定需要 ask_user
  ↓
detect_actions() → 检测到 action_name="ask_user"
  ↓
execute_action("ask_user", {"question": "..."})
  ↓
调用 root_agent.ask_user(question)
  ├─ 设置 _pending_user_question（供 API 查询）
  ├─ 创建 _user_input_future
  └─ await future（挂起！）

【此时 Agent 停在这里等待】

【用户通过 API 提交回答】
  ↓
submit_user_input(answer)
  ├─ 设置 Future 结果（唤醒 Agent）
  └─ ask_user 返回 answer

Agent 继续执行（下一次 think 能看到完整的 Q&A）
```

**关键设计**：

1. **使用 asyncio.Future 传递数据**
   - `ask_user()` 返回用户回答（不是 Event，而是 Future）
   - `submit_user_input()` 通过 `set_result()` 传递数据并唤醒

2. **与暂停机制兼容**
   - `ask_user()` 内部循环检查 `_checkpoint()`
   - 即使在等待用户输入时，也能响应全局暂停

3. **嵌套自动恢复**
   - 外层 MicroAgent 在 `await child.execute()` 等待
   - 内层 `ask_user` 返回后，外层自动恢复

**控制方法**：

```python
# 在 MicroAgent 中（由 LLM 决定调用）
answer = await self.root_agent.ask_user("请确认预算范围")
# 返回: "5万-10万"

# 通过 Server API 提交用户回答
await agent.submit_user_input("5万-10万")
```

**Server API**：

```bash
# 查询是否有等待用户输入的问题
GET /api/agents/{name}/pending_user_input
# 返回：
# {
#     "success": True,
#     "agent_name": "Tom",
#     "waiting": True,
#     "question": "请确认预算范围"
# }

# 提交用户回答
POST /api/agents/{name}/user_input
# Body: {"answer": "5万-10万"}
# 返回：
# {
#     "success": True,
#     "message": "User input submitted to agent 'Tom'"
# }
```

**使用场景**：
- 信息确认：Agent 需要用户确认关键信息（如预算、偏好）
- 决策辅助：Agent 需要用户提供决策依据
- 交互式任务：需要用户在执行过程中提供输入

**注意**：
- ask_user 走特殊通道（UI 弹窗），不通过邮件流程
- 同时只能有一个 ask_user 在等待（执行是串行的）
- 用户回答会自动记录到 MicroAgent 的 messages 中
- ask_user 注册在 **BaseSkillMixin** 中（base skill），自动被所有 MicroAgent 加载

**实现细节**：
- **Action 注册**：`ask_user` action 在 `BaseSkillMixin` 中定义（`src/agentmatrix/skills/base/skill.py`）
- **执行逻辑**：`MicroAgent._execute_action` 检测到 `ask_user` 时，特殊处理并调用 `root_agent.ask_user()`
- **核心机制**：`BaseAgent.ask_user()` 使用 `asyncio.Future` 等待用户输入
- **Server API**：通过 `/api/agents/{name}/pending_user_input` 和 `/api/agents/{name}/user_input` 交互

### Skills 架构 🎁

AgentMatrix 通过 **Skill Mixins** 机制为 MicroAgent 提供可复用的能力。

**核心 Skills**：

| Skill | Actions | 说明 | 强制注入 |
|-------|---------|------|---------|
| **base** | get_current_datetime, take_a_break, ask_user | 所有 MicroAgent 必备的基础功能 | ✅ Top-level |
| **email** | send_email | 邮件发送（未来扩展 check_email 等） | ✅ Top-level |
| **all_finished** | all_finished | 硬编码在 MicroAgent 中，所有 MicroAgent 都有 | ✅ 所有层级 |

**注入策略**：

```python
# Top-level MicroAgent（process_email 创建）
available_skills = ["base", "email"] + profile.skills

# 内部 MicroAgent（如 WebSearchSkill 创建）
available_skills = ["browser", "file"]  # 不包含 base, email
# → 只有 all_finished（硬编码）
```

**设计原则**：
- **Top-level MicroAgent**：需要 base + email（和用户通信、基础能力）
- **内部 MicroAgent**：不需要 email（返回结果给父级），可选择性注入 base
- **all_finished**：所有 MicroAgent 都有（硬编码），用于任务终止

### MicroAgent（执行者）

**代码位置**: `src/agentmatrix/agents/micro_agent.py`

**核心职责**：
- 执行单个任务（思考-行动循环）
- 使用 Agent 的能力
- 有独立的工作上下文
- 任务完成即销毁

**创建方式**：

```python
from agentmatrix.agents.micro_agent import MicroAgent

# 方式1：共享父级的所有能力
micro_agent = MicroAgent(
    parent=self,  # Agent 或另一个 MicroAgent
    working_context=None,  # None 表示使用父级的
    default_max_steps=50
)

# 方式2：动态选择可用 skills ✨
micro_agent = MicroAgent(
    parent=self,
    working_context=None,
    available_skills=["file", "browser"],  # 只用这两个 skill
    default_max_steps=50
)
```

**动态 Skill 组合** ✨：

通过 `available_skills` 参数，MicroAgent 可以只加载需要的 skills：

```python
# 只加载文件和浏览器技能
micro = MicroAgent(
    parent=self,
    available_skills=["file", "browser"]
)

# 这会动态加载 file 和 browser 两个技能
# 其他 skills 不会被加载
```

**执行任务**：

```python
result = await micro_agent.execute(
    persona="你是网络搜索专家",  # 人设
    task="搜索 AI 安全的最新论文",  # 任务
    available_actions=["search", "open_page"],  # 可用 action
    max_steps=20,  # 最大步数
    result_params={
        "expected_schema": {  # 期望的结构化输出
            "papers": ["string"],
            "summary": "string"
        }
    }
)
```

### 状态管理

#### 对话记忆（Session Context）

**核心机制**：

1. **共享记忆**（默认）：通过层级链共享同一份记忆
2. **自动保存**：每次更新自动持久化到磁盘
3. **独立模式**（可选）：创建独立的临时记忆

**代码示例**：

```python
# 默认：共享父级的记忆（可持久化）
micro1 = MicroAgent(parent=self)  # 共享
micro2 = MicroAgent(parent=self)  # 共享
# micro1 和 micro2 共享同一份记忆

# 独立模式：创建独立的记忆（不持久化）
micro3 = MicroAgent(
    parent=self,
    independent_session_context=True  # 独立记忆
)
# micro3 有独立的记忆，不会持久化
```

**使用场景**：
- **共享模式**（默认）：大部分场景，需要记忆持久化
- **独立模式**：临时计算、中间步骤，不需要保存的记忆

#### 工作空间（Working Context）

**层级目录结构**：

```
workspace_root/
├── {task_id}/
│   └── agents/
│       └── {agent_name}/  # Agent 的私有工作目录
│           ├── 20250226_143022/  # MicroAgent 子任务目录（带时间戳）
│           │   └── files/
│           └── 20250226_143545/  # 另一个子任务目录
│               └── files/
```

**创建子目录**：

```python
# 带时间戳（默认）：每次执行创建新目录
micro = MicroAgent(parent=self)
# 工作目录：workspace/.../agent_name/20250226_143022/

# 不带时间戳：多轮执行共享同一目录
micro = MicroAgent(
    parent=self,
    working_context=WorkingContext(
        base_dir=str(self.private_workspace),
        current_dir=str(subtask_dir)  # 不带时间戳的目录
    )
)
```

## Skills 和 Actions

### Action（能力）

Action 是 Agent 能执行的具体操作，用 `@register_action` 装饰器标记：

```python
from agentmatrix.core.action import register_action

@register_action(
    description="搜索网络信息",
    param_infos={
        "query": "搜索查询字符串",
        "num_results": "返回结果数量（默认10）"
    }
)
async def web_search(self, query: str, num_results: int = 10) -> str:
    """搜索网络并返回结果"""
    results = await self._search_api(query, num_results)
    return self._format_results(results)
```

### Skill（技能包）

Skill 是一组相关 Actions 的集合，以 Mixin 类形式实现：

```python
# src/agentmatrix/skills/web_searcher.py
class WebSearcherMixin:
    """网络搜索技能包"""

    @register_action(description="搜索网络")
    async def web_search(self, query: str) -> str:
        # 实现
        pass

    @register_action(description="打开网页")
    async def open_page(self, url: str) -> str:
        # 实现
        pass

    @register_action(description="提取内容")
    async def extract_content(self, html: str) -> str:
        # 实现
        pass
```

### 配置方式

在 Agent 的 YAML 配置中指定需要的 skills（使用简化名称）：

```yaml
# profiles/researcher.yml
name: Researcher
description: 信息收集专家

# Persona 配置 ✨
persona:
  base: "你是一个研究助手"
  planner: "你是规划专家"
  researcher: "你是信息收集专家"

# 加载的 skills（新架构：简化名称）
skills:
  - file           # 文件操作技能
  - web_search     # 网络搜索技能
  - browser        # 浏览器自动化技能

# 后端配置
backend_model: default_llm
cerebellum:
  backend_model: mimo
```

### 自动发现机制

新架构使用 SKILL_REGISTRY 自动发现技能，无需手动导入模块：

- **技能定义**：在 `src/agentmatrix/skills/` 目录下创建模块
- **自动注册**：使用 `@register_skill` 装饰器自动注册
- **按需加载**：运行时根据配置动态加载

可用的技能名称：
- `file` - 文件操作技能
- `web_search` - 网络搜索技能
- `browser` - 浏览器自动化技能
- `notebook` - 笔记本管理技能
- `deep_research` - 深度研究技能

## 执行机制

### "灵魂注入"三要素

每次执行 MicroAgent 时，动态注入三个要素：

```python
result = await micro_agent.execute(
    persona="...",      # 1. 人设：这次执行的身份
    task="...",         # 2. 任务：具体要做什么
    available_actions=[...]  # 3. 可用能力：这次允许用哪些 actions
)
```

**人设（Persona）**：
- 决定执行者的思考方式和行为风格
- 可以从 `persona_config` 中选择不同的 persona
- 支持模板变量

**任务（Task）**：
- 初始的 User Message
- 具体要完成的目标
- 可以包含结构化要求

**可用能力（Available Actions）**：
- 可以是全部 actions，也可以是子集
- 限制能力可以让执行者更专注

### 执行流程

```
1. 创建 MicroAgent（parent = Agent）
   └─ 获得：所有 actions、brain、cerebellum、记忆

2. 注入"灵魂"（execute() 参数）：
   ├─ persona："你是网络搜索专家"
   ├─ task："搜索 AI 安全论文"
   └─ available_actions：["search", "open_page"]

3. 思考-行动循环：
   循环（最多 max_steps 次）：
   ├─ Think：调用 brain 思考下一步
   ├─ Detect：从思考输出中识别 action
   ├─ Negotiate：通过 cerebellum 协商参数
   ├─ Execute：执行 action
   ├─ Feedback：获得执行结果
   └─ 重复：直到 all_finished 或超时

4. 返回结果并销毁
```

### 参数协商

MicroAgent 通过 Cerebellum（小脑模型）进行参数协商：

```python
# 1. 从 brain 的思考输出中识别 action
action_name = "search"

# 2. 获取 action 的参数定义
param_schema = self.actions_meta[action_name]["params"]

# 3. 通过 cerebellum 协商参数
params = await self.cerebellum.negotiate_params(
    thought=brain_output,  # brain 的原始思考
    action_schema=param_schema,  # action 的参数定义
    context=...  # 上下文信息
)

# 4. 执行 action
result = await self.actions_map[action_name](**params)
```

## 递归嵌套

### "自然语言函数"概念

把 `micro_agent.execute()` 看作自然语言函数：
- **输入**：自然语言任务描述
- **处理**：AI 推理 + 多步思考-行动循环
- **输出**：自然语言结果或结构化数据

### 嵌套示例

```
用户："研究 AI 安全"

Agent
  └─ MicroAgent 第 1 层（规划师）
      task："制定研究计划"
      可用 actions：全部

      ├─ 创建子 MicroAgent 第 2 层（搜索专家）
      │   task："搜索相关论文"
      │   可用 actions：["search", "open_page"]
      │
      │   └─ 创建子 MicroAgent 第 3 层（分析师）
      │       task："分析搜索结果"
      │       可用 actions：["summarize", "extract_info"]
      │       expected_schema: {...}
      │
      │       └─ 返回结构化数据
      │
      └─ 整合结果，生成报告
```

**代码示例**：

```python
async def research_ai_safety(topic: str) -> Dict:
    """递归研究函数"""

    # 第1层：制定计划
    plan = await micro_agent.execute(
        persona="你是研究规划师",
        task=f"为'{topic}'制定研究计划",
        available_actions=["plan"]
    )

    # 第2层：搜索信息
    papers = await micro_agent.execute(
        persona="你是搜索专家",
        task=plan["search_task"],
        available_actions=["search", "open_page"]
    )

    # 第3层：分析内容
    analysis = await micro_agent.execute(
        persona="你是内容分析师",
        task=f"分析以下论文：{papers}",
        available_actions=["summarize", "extract_info"],
        result_params={
            "expected_schema": {
                "key_findings": ["string"],
                "summary": "string"
            }
        }
    )

    return analysis
```

### 状态隔离

每层 MicroAgent 都有独立的执行上下文：
- 第 3 层的思考过程不会污染第 2 层
- 第 2 层的中间步骤不会影响第 1 层
- 每层只看到下层的最终结果

## 通信和协作

### 基于邮件的通信

**代码位置**: `src/agentmatrix/core/message.py`

所有 Agent 间通信使用 Email 数据结构：

```python
@dataclass
class Email:
    id: str                  # 唯一 ID
    sender: str              # 发送者 Agent 名称
    recipient: str           # 接收者 Agent 名称
    subject: str             # 邮件主题
    body: str                # 正文（自然语言）
    in_reply_to: str         # 回复关系（维护对话线程）
    task_id: str             # 任务ID（全局任务标识符）
```

**特性**：
- **Threading**：`in_reply_to` 维护对话线程
- **自然语言**：body 包含自由文本
- **任务跟踪**：`task_id` 跟踪全局任务

### 会话ID的两种概念

**task_id（任务ID）**
- 全局任务标识符，用于文件空间划分
- 任何Agent都可以发起（User、Daemon、普通Agent）
- 一个task = 一件"正在协作的事情"
- 文件路径：`{workspace_root}/{task_id}/`

**session_id（会话ID）**
- 每个Agent视角的对话历史ID
- 一个task下可以有多个session（每个Agent一个）
- 文件路径：`.matrix/{agent_name}/{task_id}/history/{session_id}/`

### PostOffice 系统

**代码位置**: `src/agentmatrix/agents/post_office.py`

```python
class PostOffice:
    def __init__(self):
        self.yellow_page = {}      # 服务注册表（name -> agent）
        self.inboxes = {}           # Agent 收件箱（name -> queue）
        self.vector_db = None       # 邮件搜索
        self.user_sessions = {}     # 用户会话跟踪

    async def send_email(self, email: Email):
        """路由邮件到接收者的收件箱"""
        inbox = self.inboxes.get(email.recipient)
        if inbox:
            await inbox.put(email)

    def register_agent(self, agent: BaseAgent):
        """注册 Agent 到服务注册表"""
        self.yellow_page[agent.name] = agent
        self.inboxes[agent.name] = asyncio.Queue()
```

### 自然语言协调示例

```python
# Planner Agent 的 action
@register_action(description="委托研究任务")
async def delegate_research(self, task_description: str) -> str:
    # 发送邮件
    email = Email(
        id=str(uuid.uuid4()),
        sender=self.name,
        recipient="Researcher",
        subject=f"研究任务：{task_description}",
        body=task_description,
        task_id=self.current_task_id
    )

    # 通过 PostOffice 发送
    await self.post_office.send_email(email)

    # 等待回复
    reply = await self.post_office.get_email(
        self.name,
        timeout=300
    )

    return reply.body
```

### Event 回调机制 ✨

**代码位置**: `base.py:59`

```python
self.async_event_callback: Optional[Callable] = None
```

Agent 可以通过事件回调通知外部系统：

```python
# 在 server.py 中注入回调
agent.async_event_callback = self._on_agent_event

async def _on_agent_event(self, event: AgentEvent):
    """处理 Agent 事件"""
    # 发送到前端
    await websocket.send_json(event.to_dict())
```

**支持的事件类型**：
- 任务开始/完成
- Action 执行
- 错误发生
- 状态更新

## 最佳实践

### 配置建议

**1. Persona 设计**

```yaml
# 好的 persona 设计
persona:
  base: |
    你是一个有帮助的助手。
    你的目标是：{{ goal }}

  planner: |
    你是项目规划专家。
    请将任务分解为 3-5 个子任务。
    每个子任务应该：{{ criteria }}

  researcher: |
    你是信息收集专家。
    搜索时关注：{{ focus_areas }}
```

**2. Skill 选择**

```yaml
# 根据任务选择合适的 skills（使用简化名称）
skills:
  # 文件处理任务
  - file        # 文件操作技能
  - notebook    # 笔记本管理技能

  # 网络研究任务
  - web_search  # 网络搜索技能
  - browser     # 浏览器自动化技能
```

### 代码模式

**1. 创建 MicroAgent**

```python
# 推荐：使用 parent 参数
micro = MicroAgent(
    parent=self,
    default_max_steps=50
)

# 可选：限制可用 skills
micro = MicroAgent(
    parent=self,
    available_skills=["file", "browser"]
)
```

**2. 执行任务**

```python
# 简单任务
result = await micro.execute(
    persona="你是搜索专家",
    task="搜索 AI 论文",
    available_actions=["search"]
)

# 复杂任务（期望结构化输出）
result = await micro.execute(
    persona="你是分析师",
    task="分析以下内容",
    available_actions=["analyze", "summarize"],
    result_params={
        "expected_schema": {
            "summary": "string",
            "key_points": ["string"]
        }
    }
)
```

**3. 递归任务分解**

```python
async def process_complex_task(task: str, depth: int = 0):
    """递归处理复杂任务"""
    if depth > 3:
        return await execute_simple(task)

    # 分解任务
    subtasks = await micro.execute(
        persona="你是任务规划师",
        task=f"将'{task}'分解为子任务",
        result_params={"expected_schema": {"subtasks": ["string"]}}
    )

    # 递归处理
    results = []
    for subtask in subtasks["subtasks"]:
        result = await process_complex_task(subtask, depth + 1)
        results.append(result)

    return results
```

### 调试技巧

**1. 查看执行日志**

```python
# MicroAgent 会记录每一步的思考
# 日志级别设为 DEBUG 可看到详细信息
import logging
logging.getLogger("agentmatrix").setLevel(logging.DEBUG)
```

**2. 检查 Action 注册**

```python
# 查看已注册的 actions
print(agent.actions_meta.keys())

# 查看特定 action 的元数据
print(agent.actions_meta["web_search"])
```

**3. 测试单个 Action**

```python
# 直接调用 action 测试
result = await agent.web_search(
    query="AI safety",
    num_results=5
)
```

## 总结

### 核心组件

| 组件 | 位置 | 职责 |
|------|------|------|
| BaseAgent | agents/base.py | 会话管理、能力注册 |
| MicroAgent | agents/micro_agent.py | 任务执行、思考-行动循环 |
| @register_action | core/action.py | 标记 action |
| PostOffice | agents/post_office.py | 消息路由 |
| Email | core/message.py | 通信数据结构 |

### 设计原则

1. **会话和执行分离**：长期会话 vs 短期任务
2. **能力继承，状态独立**：复用能力，隔离状态
3. **自然语言协调**：邮件式通信，易理解
4. **双脑架构**：LLM 推理 + SLM 协商
5. **动态组合**：通过 mixins 灵活配置能力

### API 快速参考

```python
# 创建 MicroAgent
micro = MicroAgent(parent=self)

# 执行任务
result = await micro.execute(
    persona="人设",
    task="任务",
    available_actions=["action1", "action2"],
    max_steps=50,
    result_params={"expected_schema": {...}}
)

# 发送邮件
await self.post_office.send_email(
    Email(sender="A", recipient="B", body="...")
)

# 获取 persona
persona = self.get_persona("planner", task_type="X")

# 获取 skill prompt
prompt = self.get_skill_prompt("browser_use", "task_optimization")
```
