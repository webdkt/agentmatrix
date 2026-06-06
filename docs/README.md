# AgentMatrix 文档

根据你的角色选择入口：

---

## 我是普通用户

想安装、配置并使用 AgentMatrix 的 Desktop App，与 AI Agent 对话、管理任务。

→ 从 **[用户指南](user/)** 开始

**快速路径：**
- [安装与首次启动](user/getting-started.md) — 环境要求、安装、冷启动向导
- [Desktop App 使用](user/desktop-guide.md) — 界面说明、写邮件、查看状态
- [与 Agent 交互](user/interacting-with-agents.md) — 如何写出有效的任务描述
- [自然语言管理配置](user/system-admin.md) — 用说话的方式改配置
- [自然语言管理 Agent](user/agent-admin.md) — 用说话的方式创建和修改 Agent
- [邮件代理](user/email-proxy.md) — 用真实邮箱与 Agent 通信

---

## 我是开发者

想理解系统架构、扩展功能、开发自定义 Skill 或 Agent，或者把 Core 引擎集成到自己的应用里。

→ 从 **[开发者指南](developer/)** 开始

**快速路径：**
- [系统架构总览](developer/architecture.md) — 三层架构、数据流、扩展点
- [Core 引擎](developer/core/) — MicroAgent、AgentShell、Cerebellum、Action、Signals
- [Desktop 运行时](developer/desktop-runtime/) — PostOffice、Session、容器、BaseAgent
- [Skill 开发](developer/skills/) — Python Skill、Markdown Skill
- [Server 概览](developer/server/api-overview.md) — FastAPI 服务
- [前端架构](developer/frontend/architecture.md) — Tauri + Vue 3

**最小示例：**
- [CLI 教程](../tutorial/cli-agent/) — 约 200 行代码的完整 AgentShell 实现

---

## 我想查参考信息

需要术语解释、项目目录说明或核心概念的定义。

→ 查看 **[参考文档](reference/)**

- [术语表](reference/glossary.md) — 系统中所有专有名词的解释
- [项目目录结构](reference/directory-layout.md) — 每个目录和模块的职责
- [核心概念](reference/concepts.md) — Email、Session、Task、Agent 的关系与设计
