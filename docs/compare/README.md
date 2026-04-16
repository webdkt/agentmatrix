# AgentMatrix vs Hermes Agent — 深度对比

本文档集对两个 AI Agent 框架进行系统性对比分析。

## 项目概览

| | AgentMatrix | Hermes Agent |
|---|---|---|
| **版本** | v0.6.9.41 (Alpha) | v0.9.0 |
| **团队** | Agent-Matrix Contributors | Nous Research |
| **许可证** | Apache 2.0 | MIT |
| **Python** | >= 3.12 | >= 3.11 |
| **定位** | 多 Agent 邮件协作框架 | 自进化 AI Agent |
| **核心隐喻** | 数字办公室（Agent 间邮件通信） | 自进化工具调用 Agent |
| **UI** | Tauri/Vue 3 桌面应用 + FastAPI 后端 | React Web 仪表盘 + TUI CLI |

## 对比维度

| # | 维度 | 文件 | 核心问题 |
|---|------|------|----------|
| 1 | 核心 Agent 范式 | [01-core-paradigm.md](01-core-paradigm.md) | Agent *是*什么？ |
| 2 | 通信模型 | [02-communication.md](02-communication.md) | Agent 之间如何交流？ |
| 3 | LLM 架构 | [03-llm-architecture.md](03-llm-architecture.md) | 推理如何组织？ |
| 4 | 技能/工具系统 | [04-skills-tools.md](04-skills-tools.md) | 如何扩展能力？ |
| 5 | 执行环境 | [05-execution-isolation.md](05-execution-isolation.md) | 代码在哪里运行？ |
| 6 | 持久化与状态 | [06-persistence-state.md](06-persistence-state.md) | 什么能从崩溃中恢复？ |
| 7 | 用户界面 | [07-ui-ux.md](07-ui-ux.md) | 人如何参与？ |
| 8 | 生态与集成 | [08-ecosystem-integration.md](08-ecosystem-integration.md) | 能连接什么？ |
| 9 | 总结与借鉴 | [09-summary.md](09-summary.md) | 各自优势与交叉学习 |
| 10 | 会话生命周期 | [10-session-lifecycle.md](10-session-lifecycle.md) | 会话何时开始、何时结束？ |
| 11 | Prompt 设计 | [11-prompt-design.md](11-prompt-design.md) | System Prompt 如何构建？ |

## 快速结论

- **AgentMatrix** 的独特价值在于 **双脑分离**（Brain+Cerebellum）和 **邮件通信隐喻**，适合构建多 Agent 协作的"数字办公室"
- **Hermes Agent** 的独特价值在于 **自进化技能系统**、**22 个消息平台适配器** 和 **RL 训练集成**，适合构建全渠道自主 Agent
