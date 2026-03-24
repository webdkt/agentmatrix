# AgentMatrix 架构概览

**版本**: v1.0
**最后更新**: 2026-03-19

---

## 📋 目录

- [系统架构](#系统架构)
- [设计原则](#设计原则)
- [核心概念](#核心概念)
- [模块组织](#模块组织)
- [数据流向](#数据流向)
- [技术栈](#技术栈)

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentMatrix Runtime                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              MatrixConfig (配置管理)                  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              PostOffice (消息中心)                    │  │
│  │  ┌──────────────┐  ┌──────────────────────────────┐  │  │
│  │  │ Agent Directory│  │   Email Queue (asyncio)     │  │  │
│  │  └──────────────┘  └──────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                    Agents                             │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐  │  │
│  │  │  BaseAgent   │  │ MicroAgent   │  │UserProxy  │  │  │
│  │  │  (持久化)    │  │  (临时)      │  │           │  │  │
│  │  └──────────────┘  └──────────────┘  └───────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Services (后台服务)                       │  │
│  │  ┌──────────────────┐  ┌──────────────────────────┐  │  │
│  │  │  ConfigService   │  │ EmailProxyService        │  │  │
│  │  └──────────────────┘  └──────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    Storage Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   SQLite DB  │  │ File System  │  │   Config Files   │  │
│  │ (邮件持久化)  │  │ (附件存储)    │  │   (YAML/JSON)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                    应用层 (Application)                      │
│  Desktop App, CLI, Custom Applications                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    框架层 (Framework)                        │
│  AgentMatrix Runtime, Agent Classes, Skill System           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    核心层 (Core)                             │
│  PostOffice, SessionManager, Config, Events                 │
└─────────────────────────────────────────────────────────────┘
                              │
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    后端层 (Backend)                          │
│  LLM Clients, Database, File System                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 设计原则

### 1. 消息驱动 (Message-Driven)

- **核心机制**: Agent间通过Email异步通信
- **解耦设计**: Agent不需要直接引用其他Agent
- **可追溯性**: 所有通信都有历史记录

### 2. 技能组合 (Skill Composition)

- **Mixin模式**: 技能作为可插拔的Mixin类
- **动态组合**: 运行时动态组合技能
- **Action注册**: 统一的Action注册和调用机制

### 3. 会话隔离 (Session Isolation)

- **独立状态**: 每个Agent维护独立的会话状态
- **透明持久化**: 自动保存和加载会话状态
- **上下文传递**: Session数据结构提供状态共享机制

### 4. 配置驱动 (Configuration-Driven)

- **YAML配置**: 支持YAML格式的配置文件
- **环境变量**: 支持环境变量覆盖
- **多环境**: 支持开发和生产环境配置

### 5. 可扩展性 (Extensibility)

- **插件化**: 技能和Agent都是可插拔的
- **继承体系**: 清晰的类继承体系
- **接口抽象**: 定义清晰的抽象接口

---

## 核心概念

### Agent (智能体)

系统中自主的参与者，可以是AI Agent或人类用户。

**类型**:
- **BaseAgent**: 持久化的、有状态的Agent
- **MicroAgent**: 临时的、无状态的Agent
- **UserProxy**: 用户代理，连接人类用户

**状态**:
- `IDLE`: 空闲
- `THINKING`: 思考中
- `WORKING`: 工作中
- `WAITING_FOR_USER`: 等待用户输入

### Email (邮件)

Agent间通信的基本单位。

**核心字段**:
- `sender`: 发件人
- `recipient`: 收件人
- `subject`: 主题
- `body`: 正文
- `task_id`: 任务ID（跨Agent的任务边界）
- `sender_session_id`: 发件人的会话ID
- `recipient_session_id`: 收件人的会话ID

### Session (会话)

单个Agent的邮件往来视图（主观视角）。

**特点**:
- 每个Agent有自己的Session视图
- A和B对话 → 有2个Session（A的和B的）
- 支持自动持久化

### Task (任务)

一个完整的工作任务（客观工作单元）。

**用途**:
- 跨Agent的任务追踪
- 文件隔离边界
- 任务关联查询

### Skill (技能)

Agent的功能模块，提供一组相关的Actions。

**特点**:
- Mixin模式设计
- 可插拔组合
- 统一的Action注册

---

## 模块组织

### 目录结构

```
src/agentmatrix/
├── core/                  # 核心组件
│   ├── runtime.py         # AgentMatrix主类
│   ├── message.py         # Email定义
│   ├── config.py          # 配置管理
│   ├── session_manager.py # 会话管理
│   ├── cerebellum.py      # 参数解析
│   └── ...
├── agents/                # Agent类型
│   ├── base.py           # BaseAgent
│   ├── micro_agent.py    # MicroAgent
│   ├── post_office.py    # PostOffice
│   └── user_proxy.py     # UserProxy
├── skills/                # 技能模块
│   ├── base/             # 基础技能
│   ├── markdown/         # Markdown技能
│   ├── scheduler/        # 调度技能
│   └── ...
├── services/              # 服务层
│   ├── config_service.py
│   └── email_proxy_service.py
├── backends/              # 后端组件
│   ├── llm_client.py
│   └── mock_llm.py
├── db/                    # 数据库
│   └── agent_matrix_db.py
└── utils/                 # 工具模块
```

### 模块职责

| 模块 | 职责 | 关键类 |
|------|------|--------|
| **core** | 核心组件和基础设施 | AgentMatrix, Email, MatrixConfig |
| **agents** | Agent类型定义 | BaseAgent, MicroAgent, PostOffice |
| **skills** | 可重用的功能模块 | BaseSkill, MarkdownSkill |
| **services** | 后台服务 | ConfigService, EmailProxyService |
| **backends** | 外部服务集成 | LLMClient |
| **db** | 数据持久化 | AgentMatrixDB |
| **utils** | 工具函数 | token_utils, parser_utils |

---

## 数据流向

### 消息传递流程

```
1. 用户发送邮件
   UserProxy → PostOffice

2. PostOffice处理
   ├─ 查找recipient
   ├─ 加入邮件队列
   └─ 持久化到数据库

3. Agent接收邮件
   PostOffice → Agent.inbox

4. Agent处理邮件
   ├─ Brain分析邮件
   ├─ Cerebellum解析参数
   ├─ 执行Action
   └─ 发送回复邮件

5. 循环继续
   Agent → PostOffice → Agent ...
```

### 会话管理流程

```
1. Agent启动
   ├─ SessionManager加载Session
   └─ 恢复上次状态

2. Agent处理邮件
   ├─ 读取Session状态
   └─ 更新Session状态

3. 自动持久化
   ├─ 定期保存到磁盘
   └─ 关键操作后立即保存

4. Agent关闭
   └─ SessionManager保存Session
```

### 技能执行流程

```
1. Action注册
   Skill.__init__() → self.register_action()

2. Agent思考
   Brain → 选择Action

3. 参数解析
   Cerebellum → 解析参数

4. 执行Action
   Agent.execute_action() → Skill.action()

5. 返回结果
   Action结果 → Email回复
```

---

## 技术栈

### 核心技术

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 主要开发语言 |
| asyncio | - | 异步编程 |
| dataclasses | - | 数据类定义 |
| PyYAML | - | 配置文件解析 |
| aiohttp | - | 异步HTTP客户端 |

### 存储技术

| 技术 | 用途 |
|------|------|
| SQLite | 邮件和状态持久化 |
| 文件系统 | 附件存储、配置文件 |



---

## 扩展点

### 1. 自定义Agent

继承 `BaseAgent` 或 `MicroAgent`：

```python
class MyAgent(BaseAgent):
    agent_name = "MyAgent"
    persona = "You are a custom agent."
```

### 2. 自定义Skill

继承 `BaseSkill` 并注册Actions：

```python
class MySkill(BaseSkill):
    def __init__(self):
        super().__init__()
        self.register_action("my_action", self.my_action)

    def my_action(self, **params):
        # 实现逻辑
        pass
```

### 3. 自定义Backend

继承 `LLMClient` 或实现自定义接口：

```python
class MyLLMClient(LLMClient):
    def chat(self, messages, **kwargs):
        # 自定义LLM调用
        pass
```

---

## 相关文档

- **[组件参考](./component-reference.md)** - 详细的组件API文档
- **[Agent系统](./agent-system.md)** - Agent系统详解
- **[消息系统](./message-system.md)** - 消息传递机制
- **[会话管理](./session-management.md)** - 状态管理详解
- **[技能系统](./skill-system.md)** - 技能开发指南
- **[LLM-Managed Config](./llm-managed-config.md)** - ConfigService + SystemAdmin Agent 设计模式
- **[核心概念](../concepts/CONCEPTS.md)** - 核心概念定义

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
