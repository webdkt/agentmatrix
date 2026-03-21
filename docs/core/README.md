# AgentMatrix Core 文档

欢迎来到 AgentMatrix 核心库文档。本文档集帮助开发者理解和使用 AgentMatrix 核心框架的架构、组件和扩展机制。

## 📚 快速导航

### 核心文档

| 文档 | 描述 | 目标受众 |
|------|------|---------|
| **[架构概览](./architecture.md)** | 系统架构、设计原则、模块关系 | 所有开发者 |
| **[组件参考](./component-reference.md)** | 核心组件、Agent类型、技能系统、API接口 | 后端开发者 |
| **[Agent系统](./agent-system.md)** | Agent类型、生命周期、状态管理 | Agent开发者 |
| **[消息系统](./message-system.md)** | Email模型、PostOffice、消息路由 | 系统集成者 |
| **[会话管理](./session-management.md)** | SessionManager、状态持久化 | 后端开发者 |
| **[技能系统](./skill-system.md)** | Skill Mixin、Action注册、技能开发 | 技能开发者 |

### 使用指南

#### 1️⃣ 新手开发者
建议按以下顺序阅读：
1. [架构概览](./architecture.md) - 了解系统架构和核心概念
2. [组件参考](./component-reference.md) - 熟悉核心组件和API
3. [Agent系统](./agent-system.md) - 理解Agent的工作原理

#### 2️⃣ Agent开发者
如果你正在开发新的Agent：
1. [Agent系统](./agent-system.md) - 了解Agent类型和选择
2. [技能系统](./skill-system.md) - 学习如何开发技能
3. [会话管理](./session-management.md) - 理解状态管理机制

#### 3️⃣ 系统集成者
如果你正在集成AgentMatrix到现有系统：
1. [架构概览](./architecture.md) - 理解整体架构
2. [消息系统](./message-system.md) - 了解消息传递机制
3. [组件参考](./component-reference.md) - 查看API接口

## 🔗 相关文档

- **[核心概念](../concepts/CONCEPTS.md)** - Email, Session, Agent, Task等核心概念定义
- **[Desktop文档](../desktop/)** - Desktop应用文档
- **[项目主文档](../)** - AgentMatrix项目总体文档

## 🚀 快速开始

### 基本使用

```python
from agentmatrix import AgentMatrix, Email, PostOffice

# 创建Runtime
matrix = AgentMatrix(config_path="config.yaml")

# 启动系统
matrix.start()

# 发送邮件
email = Email(
    sender="User",
    recipient="AgentA",
    subject="Hello",
    body="How are you?"
)
matrix.post_office.send_email(email)

# 关闭系统
matrix.stop()
```

### 创建自定义Agent

```python
from agentmatrix.agents import BaseAgent
from agentmatrix.skills import BaseSkill

class MyAgent(BaseAgent):
    agent_name = "MyAgent"
    persona = "You are a helpful assistant."

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 添加技能
        self.add_skill(BaseSkill())

# 注册Agent
matrix.register_agent(MyAgent)
```

---

**文档版本**: v1.0
**最后更新**: 2026-03-19
**维护者**: AgentMatrix Team
