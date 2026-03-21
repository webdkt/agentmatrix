# AgentMatrix Documentation

AgentMatrix 是一个多 Agent 编排框架，用于管理 AI agents 的生命周期、通信和协调。

## 文档结构

| 路径 | 目标读者 | 内容 |
|------|----------|------|
| [`core/`](./core/) | 所有开发者 | 核心库架构、组件参考、系统详解 |
| [`desktop/`](./desktop/) | 前端开发者 | Desktop 应用文档、UI 组件、交互流程 |
| [`concepts/`](./concepts/) | 所有读者 | 核心概念定义、术语对照 |
| [`developer/`](./developer/) | 后端开发者 | 系统架构、开发指南、API 参考 |
| [`user/`](./user/) | 终端用户 | 安装、配置、使用指南 |

## 快速导航

**核心库**
- [架构概览](./core/architecture.md) - 系统架构、设计原则、模块关系
- [组件参考](./core/component-reference.md) - 核心组件、Agent 类型、技能系统
- [Agent 系统](./core/agent-system.md) - Agent 类型、生命周期、状态管理
- [消息系统](./core/message-system.md) - Email 模型、PostOffice、消息路由
- [会话管理](./core/session-management.md) - SessionManager、状态持久化
- [技能系统](./core/skill-system.md) - Skill 开发、Action 机制

**Desktop 应用**
- [UI 设计系统](./desktop/ui-design-system.md) - 设计规范、样式指南
- [组件参考](./desktop/component-reference.md) - Vue 组件、Store、API
- [交互设计](./desktop/ui-interaction-flows.md) - 交互流程、状态管理
- [Settings View 实现](./SETTINGS_VIEW_IMPLEMENTATION.md) - Settings View 完整实现文档
- [Settings View 架构](./SETTINGS_VIEW_ARCHITECTURE.md) - Settings View 架构详解
- [Settings View 测试](./SETTINGS_VIEW_TESTING_GUIDE.md) - Settings View 测试指南
- [Settings View 迁移](./SETTINGS_VIEW_MIGRATION.md) - Settings View 迁移指南

**核心概念**
- [核心概念](./concepts/CONCEPTS.md) - Email、Session、Agent、Task 定义

**Developer**
- [系统架构](./developer/guide/architecture.md)
- [开发 Agent](./developer/guide/agent.md)
- [开发 Skill](./developer/guide/skill.md)
- [目录结构参考](./developer/reference/directory-structure.md)

**User**
- [安装](./user/guide/installation.md)
- [配置 Profile](./user/guide/profiles.md)
- [使用 SystemAdmin](./user/how-to/use-system-admin.md)
