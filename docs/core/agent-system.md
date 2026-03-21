# Agent系统详解

**版本**: v2.1
**最后更新**: 2026-03-19 (v2.1: 精简 Skill 内容，引用 skill-system.md)

---

## 📋 目录

- [核心概念](#核心概念)
- [BaseAgent vs MicroAgent](#baseagent-vs-microagent)
- [执行流程](#执行流程)
- [调用链条](#调用链条)
- [控制机制](#控制机制)
- [Skill系统](#skill系统)
- [状态管理](#状态管理)
- [开发指南](#开发指南)

---

## 核心概念

### Agent的本质

AgentMatrix 中有两种 Agent 类型，它们有不同的职责和生命周期：

**BaseAgent（持久化Agent）**：
- 长期运行，管理会话状态
- 拥有独立的 inbox、session_manager、post_office 连接
- 每次收到邮件时，创建一个临时的 MicroAgent 来处理
- 本身不执行 think-act 循环，只负责调度和管理

**MicroAgent（临时Agent）**：
- 短期存在，只为了完成一个具体任务
- 无状态，直接继承 parent（BaseAgent）的组件
- 执行 think-negotiate-act 循环
- 可以递归创建新的 MicroAgent

### 核心设计原则

1. **分离关注点**：BaseAgent 管理"外围"（会话、邮件、状态），MicroAgent 执行"内核"（思考、行动）
2. **临时性**：MicroAgent 用完即弃，避免状态污染
3. **组件继承**：MicroAgent 通过 parent 链继承所有必要组件
4. **递归能力**：Action 可以创建新的 MicroAgent，形成递归调用链

---

## BaseAgent vs MicroAgent

### BaseAgent 特征

**职责**：
- 维护长期会话状态
- 管理 email inbox
- 提供 Brain、Cerebellum 等共享组件
- 处理暂停/恢复、ask_user 等控制机制
- 协调 MicroAgent 的创建和销毁

**生命周期**：
- 随系统启动而创建
- 持续运行直到系统关闭
- 处理多封邮件，跨越多个会话

**关键组件**：
```
BaseAgent
├── inbox (asyncio.Queue)        # 邮件队列
├── session_manager              # 会话管理器
├── current_session              # 当前会话状态
├── brain                        # LLM 推理引擎
├── cerebellum                   # 参数解析器
├── post_office                  # 邮件系统连接
├── action_registry              # Action 注册表
└── _paused / _pause_event       # 暂停控制机制
```

### MicroAgent 特征

**职责**：
- 执行具体的 think-act 循环
- 调用 skills 的 actions
- 可以递归创建子 MicroAgent
- 无状态，任务完成后即销毁

**生命周期**：
- 在 BaseAgent.process_email() 中创建
- 执行一个任务（最多 N 步或 M 分钟）
- 任务完成后返回结果并销毁

**继承关系**：
```
MicroAgent
├── parent → BaseAgent (或其他 MicroAgent)
│   ├── brain (继承)
│   ├── cerebellum (继承)
│   ├── logger (继承)
│   └── action_registry (继承)
├── name (唯一标识)
├── skills (动态组合的 Mixin)
└── messages (对话历史)
```

---

## 执行流程

### BaseAgent 处理邮件流程

```
1. BaseAgent 收到邮件
   └─ inbox.put(email)

2. email_worker 被唤醒
   └─ 从 inbox 取出邮件

3. process_email(email)
   ├─ 恢复 session 状态
   ├─ 唤醒 Docker 容器（如果使用容器化）
   └─ 创建 MicroAgent

4. 创建 MicroAgent
   ├─ micro_core = MicroAgent(parent=self, name="...", available_skills=[...])
   └─ 注入 skills（动态 Mixin）

5. 执行 MicroAgent
   └─ result = await micro_core.execute(task, session, ...)

6. 保存 session 状态
   └─ session_manager.save_session(session)

7. 休眠 Docker 容器（如果使用容器化）
```

### MicroAgent 执行循环

```
MicroAgent.execute()
└─ _run_loop()
   ├─ while not should_stop():
   │  ├─ 【检查暂停点】
   │  │  └─ if parent.is_paused: await parent._checkpoint()
   │  │
   │  ├─ 【思考阶段】
   │  │  └─ brain.think(messages)
   │  │     └─ LLM 返回：action_name + parameters
   │  │
   │  ├─ 【协商阶段】
   │  │  └─ cerebellum.negotiate_params(action_name, user_input)
   │  │     └─ 解析和验证参数
   │  │
   │  ├─ 【执行阶段】
   │  │  └─ action(**parameters)
   │  │     ├─ 可能是 skill 的 action
   │  │     ├─ 可能递归创建新的 MicroAgent
   │  │     └─ 返回执行结果
   │  │
   │  ├─ 【反馈阶段】
   │  │  └─ 准备反馈消息
   │  │     └─ 包含执行结果和时间提示
   │  │
   │  └─ 【检查退出条件】
   │     ├─ max_steps 达到？
   │     ├─ max_time 达到？
   │     ├─ action 是 "all_finished"？
   │     └─ action 是 "take_a_break"？
   │
   └─ 返回最终结果
```

---

## 调用链条

### 典型调用链

```
User 发送邮件
   ↓
PostOffice 路由
   ↓
BaseAgent.inbox
   ↓
BaseAgent.process_email()
   ↓
创建 MicroAgent (Level 1)
   ↓
MicroAgent._run_loop()
   ↓
调用 action: file_read()
   ↓
FileSkill.file_read()
   ↓
创建 MicroAgent (Level 2) 用于解析文件内容
   ↓
MicroAgent._run_loop()
   ↓
调用 action: take_a_break
   ↓
返回到 Level 1
   ↓
继续执行...
```

### 递归 MicroAgent 示例

**场景**: SomeSkill 的 `analyze_project` action 需要分析整个项目

```
Level 1: BaseAgent 创建的 MicroAgent
└─ 调用 some_skill.analyze_project(path="/project")
   │
   └─ Level 2: analyze_project 内部创建 MicroAgent
      └─ 任务：遍历目录，总结每个文件
         │
         ├─ 调用 file_read(file1)
         ├─ 调用 file_read(file2)
         └─ 调用 file_read(file3)
            │
            └─ Level 3: file_read 内部可能创建 MicroAgent
               └─ 任务：解析文件内容，提取关键信息
```

### 调用链关键点

1. **组件继承**：子 MicroAgent 继承 parent 的 brain、cerebellum
2. **独立性**：每个 MicroAgent 有独立的 messages、max_steps、max_time
3. **暂停传播**：如果 BaseAgent 被暂停，所有 MicroAgent 都会在 checkpoint 暂停
4. **ask_user 传播**：任何层级的 MicroAgent 都可以调用 `parent.ask_user()`

---

## 控制机制

### 暂停/恢复机制

**BaseAgent 级别**：
```python
# 暂停 BaseAgent
await base_agent.pause()
# → 所有 MicroAgent 会在下一个 checkpoint 暂停

# 恢复 BaseAgent
await base_agent.resume()
# → 所有等待的 MicroAgent 继续执行
```

**MicroAgent 级别**：
```python
# MicroAgent 在关键位置检查暂停
async def _run_loop():
    while not should_stop():
        # 检查暂停点
        if parent.is_paused:
            await parent._checkpoint()  # 阻塞直到恢复
```

**暂停时机**：
- 每次 action 执行前
- 每次 think 前
- 每次反馈前

### ask_user 机制

**流程**：
```
MicroAgent 执行到需要用户输入的地方
   ↓
调用 parent.ask_user("请确认预算范围")
   ↓
BaseAgent.ask_user()
├─ 更新状态为 WAITING_FOR_USER
├─ (如果配置了Email Proxy服务）发送特殊邮件给用户（#ASK_USER# 标记）
├─ 创建 Future 并挂起
└─ 等待 submit_user_input(answer)
   ↓
用户回复 via frontend or 外部邮件
   ↓
(如果via 外部邮件）EmailProxy 识别 #ASK_USER# 标记 
   ↓
调用 base_agent.submit_user_input(answer)
   ↓
Future.set_result(answer)
   ↓
MicroAgent 继续执行
```

**特点**：
- 支持 MicroAgent 递归调用：Level 2 的 MicroAgent 也可以 ask_user
- 自动传播到 BaseAgent：最终由 BaseAgent 统一管理
- 不影响暂停机制：ask_user 期间仍可以暂停

### 退出机制

**MicroAgent 退出条件**：
1. **正常退出**：执行 `all_finished` action
2. **主动休息**：执行 `take_a_break` action
3. **超时退出**：达到 max_time 或 max_steps
4. **强制退出**：parent 被停止或取消


---

## Skill系统

### Skill 注入机制

**动态 Mixin 模式**：
```python
# 创建 MicroAgent 时指定 skills
micro_agent = MicroAgent(
    parent=self,
    name="Worker",
    available_skills=["file", "browser"]  # ← 指定 skills
)

# MicroAgent 内部动态组合 Mixin
# 1. 找到 FileSkill、BrowserSkill 类
# 2. 创建动态类：class _MicroAgentWithSkills(MicroAgent, FileSkill, BrowserSkill)
# 3. 实例化并返回
```

**Skill 注册表**：
```
SKILL_REGISTRY = {
    "base": BaseSkill,
    "file": FileSkill,
    "browser": BrowserSkill,
    "email": EmailSkill,
    # ... 更多 skills
}
```

### Action 调用流程

```
1. MicroAgent.think()
   └─ LLM 返回："file_read(path='/tmp/test.txt')"

2. MicroAgent._execute_action()
   ├─ 从 action_registry 查找 "file_read"
   │  └─ 找到 FileSkill.file_read 方法
   │
   ├─ cerebellum.negotiate_params()
   │  └─ 确保参数正确
   │
   └─ 调用 action
      └─ result = await self.file_read(path='/tmp/test.txt')

3. Action 返回结果
   └─ "文件内容：..."
```

### Skill 创建子 MicroAgent

**示例**：FileSkill 的 `analyze_project` action

```python
class FileSkill:
    async def analyze_project(self, project_path: str) -> str:
        # 1. 创建子 MicroAgent
        analyzer = MicroAgent(
            parent=self.root_agent,  # ← 递归到 BaseAgent
            name="ProjectAnalyzer",
            available_skills=["file"]
        )

        # 2. 定义子任务
        task = f"分析项目 {project_path} 的结构和内容"

        # 3. 执行子 MicroAgent
        result = await analyzer.execute(
            task=task,
            session=self.current_session,  # ← 共享 session
            max_steps=50
        )

        return result
```

**递归规则**：
- 子 MicroAgent 的 parent 可以是 BaseAgent 或另一个 MicroAgent
- 通过 `self.root_agent` 找到最终的 BaseAgent
- 所有层级的 MicroAgent 共享同一个 brain、cerebellum

---

## 状态管理

### BaseAgent 状态

**持久化状态**（保存到磁盘）：
```python
session = {
    "session_id": "...",
    "task_id": "...",
    "history": [...],           # 对话历史
    "context": {...},           # 自定义上下文
    "last_sender": "...",       # 最后发送者
    "metadata": {...}
}
```

**运行时状态**（不持久化）：
```python
BaseAgent
├── _status                    # 当前状态 (IDLE/THINKING/...)
├── _paused                    # 是否暂停
├── _pending_user_question     # 等待用户的问题
├── _user_input_future         # 用户输入的 Future
└── current_session            # 当前加载的 session
```

### MicroAgent 状态

**临时状态**（不持久化）：
```python
MicroAgent
├── messages                   # 当前对话历史
├── step_count                 # 已执行步数
├── start_time                 # 开始时间
├── last_action_name           # 最后执行的 action
└── result                     # 最终结果
```

**状态共享**：
- `current_session`: 从 parent 继承，可读写
- `current_task_id`: 从 parent 继承
- `current_user_session_id`: 从 parent 继承

### 状态更新时机

```
MicroAgent 每步执行
   ↓
更新 session["history"]
   ↓
session_manager.save_session_context_only(session)
   ↓
立即持久化到磁盘
```

**关键点**：
- 每个 MicroAgent 的 action 执行后都会保存 session
- BaseAgent.process_email() 结束时再次保存
- 确保状态不丢失

---

## 开发指南

### 创建自定义 BaseAgent

**最小示例**：
```python
from agentmatrix.agents.base import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        # profile 包含：name, description, persona, skills 等
```

**配置文件**：
```yaml
agents:
  MyAgent:
    description: "一个自定义 Agent"
    persona:
      base: "你是一个有帮助的助手"
    skills:
      - file
      - browser
```

### 创建自定义 MicroAgent

**通常不需要直接创建**：
- BaseAgent.process_email() 会自动创建
- Skill 的 action 内部可以创建子 MicroAgent

**手动创建示例**：
```python
# 在 Skill 的 action 中
async def my_action(self, task: str) -> str:
    # 创建子 MicroAgent
    worker = MicroAgent(
        parent=self.root_agent,
        name="Worker",
        available_skills=["file"]
    )

    # 执行任务
    result = await worker.execute(
        task=task,
        session=self.current_session,
        max_steps=100
    )

    return result
```

### 开发自定义 Skill

> 💡 **详细指南**: 完整的 Skill 开发流程请参考 **[技能系统详解](./skill-system.md)**

**在 Agent 系统中的特殊考虑**：

当你的 Skill 需要执行复杂任务时，可以创建子 MicroAgent：

**关键点**：
1. Skill 继承 `BaseSkill`（详见 [Skill 开发指南](./skill-system.md#自定义skill)）
2. Actions 可以访问 `self.root_agent`（最终的 BaseAgent）
3. Actions 可以创建子 MicroAgent（见上方 "Skill 创建子 MicroAgent"）
4. 子 MicroAgent 继承 parent 的所有组件（brain、cerebellum 等）

**快速示例**：
```python
from agentmatrix.skills.base.base import BaseSkill
from agentmatrix.core.action import register_action

class MySkill(BaseSkill):
    @register_action(
        description="执行一个复杂任务",
        param_infos={"task": "任务描述"}
    )
    async def complex_task(self, task: str) -> str:
        # 创建子 MicroAgent（递归）
        worker = MicroAgent(
            parent=self.root_agent,
            name="ComplexTaskWorker",
            available_skills=["file", "browser"]
        )

        result = await worker.execute(
            task=task,
            session=self.current_session
        )

        return result
```

**更多内容**：
- Skill 设计原则 → [Skill 最佳实践](./skill-system.md#最佳实践)
- Action 参数验证 → [Action 机制](./skill-system.md#action机制)
- 内置 Skills 参考 → [内置 Skills](./skill-system.md#内置skills)

### 调试技巧

**查看调用链**：
```python
# 在 MicroAgent 中打印调用栈
import traceback
print("".join(traceback.format_stack()))
```

**监控状态**：
```python
# BaseAgent 状态
print(f"Status: {base_agent.status}")
print(f"Paused: {base_agent.is_paused}")
print(f"Pending question: {base_agent._pending_user_question}")

# MicroAgent 状态
print(f"Step: {micro_agent.step_count}")
print(f"Time: {time.time() - micro_agent.start_time:.1f}s")
```

**日志级别**：
```python
# BaseAgent 使用 DEBUG 级别
base_agent._custom_log_level = logging.DEBUG

# MicroAgent 继承 parent 的 logger
# 无需单独设置
```

---

## 常见问题

### Q1: 为什么需要 MicroAgent？

**A**: 分离关注点和临时性：
- BaseAgent 管理"外围"（会话、邮件、状态）
- MicroAgent 执行"内核"（思考、行动）
- 每次任务都是新的 MicroAgent，避免状态污染

### Q2: MicroAgent 递归会无限创建吗？

**A**: 不会，因为有保护机制：
- `max_steps`: 默认 50 步
- `max_time`: 默认无限制，但可以设置
- DeepResearcher 有特殊的 `take_a_break` 机制

### Q3: 如何暂停一个正在运行的 MicroAgent？

**A**: 暂停 BaseAgent：
```python
await base_agent.pause()
# → 所有 MicroAgent 会在下一个 checkpoint 暂停
```

### Q4: ask_user 会阻塞整个系统吗？

**A**: 不会：
- 只阻塞当前 MicroAgent
- 其他 Agent 可以继续工作
- BaseAgent 的状态变为 WAITING_FOR_USER
- 用户回复后继续执行

### Q5: 如何在 Skill 中访问 session？

**A**: 通过 `self.current_session`：
```python
class MySkill(BaseSkill):
    async def my_action(self) -> str:
        # 读取 session
        context = self.current_session.get("context", {})

        # 更新 session
        context["my_key"] = "my_value"
        self.current_session["context"] = context

        # SessionManager 会自动保存
```

---

## 相关文档

- **[架构概览](./architecture.md)** - 系统架构
- **[组件参考](./component-reference.md)** - 组件API
- **[消息系统](./message-system.md)** - Email 传递机制
- **[会话管理](./session-management.md)** - SessionManager 详解
- **[技能系统](./skill-system.md)** - Skill 开发指南

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
