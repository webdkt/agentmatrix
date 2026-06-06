# 开发者指南

如果你想理解 AgentMatrix 的系统架构、扩展功能、开发自定义 Skill 或 Agent，或者把 Core 引擎集成到自己的应用里，从这里开始。

---

## 快速路径

**理解架构**
- [系统架构总览](architecture.md) — 三层架构、数据流、扩展点

**理解 Core 引擎**
- [MicroAgent](core/micro-agent.md) — 执行引擎的 think-negotiate-act 循环
- [AgentShell Protocol](core/agent-shell.md) — Core 与外界的接口边界
- [Cerebellum](core/cerebellum.md) — 意图解析与参数协商
- [Action 系统](core/action-system.md) — Action 注册、发现、执行
- [SessionStore](core/session-store.md) — 会话持久化
- [压缩机制](core/compression.md) — Working Notes 与上下文管理
- [Signal 系统](core/signals.md) — 事件驱动通信

**理解 Desktop 运行时**
- [Runtime](desktop-runtime/runtime.md) — 总控模块
- [PostOffice](desktop-runtime/post-office.md) — 邮件总线
- [Session Manager](desktop-runtime/session-manager.md) — 会话管理
- [容器系统](desktop-runtime/container.md) — Docker/Podman 隔离
- [BaseAgent](desktop-runtime/base-agent.md) — Agent 生命周期与状态机

**开发扩展**
- [Skill 概览](skills/overview.md) — Skill 体系与内置技能清单
- [Python Skill](skills/python-skill.md) — 开发自定义 Python Skill
- [Markdown Skill](skills/markdown-skill.md) — 编写无代码 Skill

**理解前后端**
- [Server 概览](server/api-overview.md) — FastAPI 服务
- [前端架构](frontend/architecture.md) — Tauri + Vue 3

**最小示例**
- [CLI 教程](../../tutorial/cli-agent/) — 约 200 行代码的完整 AgentShell 实现

---

**提示**：如果你需要查术语，先看 [术语表](../reference/glossary.md)。如果你想了解数据模型关系，看 [核心概念](../reference/concepts.md)。
