# AgentMatrix Documentation

## 文档结构

```
docs/
├── core/                    # Core 框架 (agentmatrix-core)
│   ├── 01-大脑小脑与动作.md
│   ├── 02-事件驱动的执行循环.md
│   ├── 03-System-Prompt的构成.md
│   ├── 04-会话自动压缩机制.md
│   ├── 05-Python-Skill机制.md
│   └── 06-无限嵌套的MicroAgent模式.md
│
├── desktop/                 # Desktop App (Tauri + Vue 3)
│   ├── architecture/        # 架构文档
│   │   ├── 01-整体架构概览.md
│   │   ├── 02-运行时与邮局.md
│   │   ├── 03-邮件作为信息模式.md
│   │   ├── 04-会话管理与关系.md
│   │   ├── 05-容器与文件系统.md
│   │   ├── 06-内外邮件映射.md
│   │   └── 07-Collab模式.md
│   ├── services/            # 服务层
│   │   ├── Config-Service与管理技能.md
│   │   └── SystemAdmin用户.md
│   ├── skills/              # 专属技能实现
│   │   └── Memory-Skill的实现.md
│   ├── cold-start-wizard/   # 冷启动向导
│   ├── ui-*.md              # UI 设计文档
│   └── archive/             # 历史归档
│
├── tutorial/ → ../tutorial/cli-agent/README.md  # CLI 教程
├── concepts/                # 核心概念定义
├── developer/               # 开发者指南
├── user/                    # 用户指南
├── compare/                 # 对比分析
└── architecture/            # 通用架构文档
```

## 按角色导航

### 想理解 Core 框架（所有人）

[docs/core/](./core/) — 6 篇文档，由浅入深介绍 Core 引擎的工作原理。

1. [大脑小脑与动作](./core/01-大脑小脑与动作.md) — Brain/Cerebellum 双脑架构、think_with_retry
2. [事件驱动的执行循环](./core/02-事件驱动的执行循环.md) — Signal 系统、Think-Negotiate-Act 循环
3. [System Prompt 的构成](./core/03-System-Prompt的构成.md) — 动态 Prompt 生成、技能注入
4. [会话自动压缩机制](./core/04-会话自动压缩机制.md) — Working Notes、Scratchpad
5. [Python Skill 机制](./core/05-Python-Skill机制.md) — 技能注册、Mixin、装饰器
6. [无限嵌套的 MicroAgent 模式](./core/06-无限嵌套的MicroAgent模式.md) — 嵌套调用、动态技能组合

### 想理解 Desktop App

[docs/desktop/](./desktop/) — 架构、服务层、UI、专属技能。

**架构**：[整体架构概览](./desktop/architecture/01-整体架构概览.md) → [运行时与邮局](./desktop/architecture/02-运行时与邮局.md) → [邮件信息模式](./desktop/architecture/03-邮件作为信息模式.md) → ...

**服务层**：[Config Service](./desktop/services/Config-Service与管理技能.md) · [SystemAdmin](./desktop/services/SystemAdmin用户.md)

**UI**：[设计系统](./desktop/ui-design-system.md) · [组件参考](./desktop/component-reference.md) · [交互流程](./desktop/ui-interaction-flows.md)

### 想用 Core 构建自己的应用

[tutorial/cli-agent/](../tutorial/cli-agent/README.md) — 最小可运行示例，~200 行代码。

### 其他

- [核心概念](./concepts/CONCEPTS.md) — 术语定义
- [开发者指南](./developer/) — 开发 Agent/Skill 指南
- [用户指南](./user/) — 安装、配置、使用
