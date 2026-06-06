# 系统架构总览

AgentMatrix 采用三层架构，将执行引擎、应用适配和具体应用形态清晰地分离。同一套 Core 代码可以在桌面应用、命令行工具或服务端程序中运行，不需要修改。

---

## 三层架构

```
┌─────────────────────────────────────────────────────┐
│  App Layer                                          │
│  桌面应用 (Tauri + Vue 3) / CLI / Server            │
├─────────────────────────────────────────────────────┤
│  Shell Layer                                        │
│  AgentShell Protocol — Core 与外界的接口            │
├─────────────────────────────────────────────────────┤
│  Core Layer                                         │
│  MicroAgent 引擎 — 纯执行，无 I/O                   │
└─────────────────────────────────────────────────────┘
```

### Core Layer — 执行引擎

Core 层只关心一件事：给定一个任务，如何执行它。

核心组件：

- **MicroAgent**：任务执行引擎。接收一个任务描述，执行 think-negotiate-act 循环，直到任务完成或失败。MicroAgent 不知道桌面应用、文件系统或网络的存在。
- **Action Registry**：所有可执行动作的注册表。MicroAgent 从这里查找匹配的动作并调用。
- **Cerebellum**：将自然语言意图解析为结构化动作参数。当意图模糊时，向 Brain 请求澄清。
- **Signals**：事件驱动的通信机制。输入通过 Signal 进入，输出通过 Signal 离开。

Core 层不直接进行任何 I/O。所有外部交互都通过 AgentShell Protocol 委托给上层。

### Shell Layer — 接口协议

Shell 层是 Core 与外界的边界。它定义了一组接口方法，Core 通过这些方法与外部世界交互。

主要职责：

- 提供 Prompt 模板（Core 不直接读取文件）
- 生成 Working Notes（上下文压缩）
- 执行 Checkpoint（暂停/恢复协作）
- 提供 Markdown Skill 的内容
- 管理 Session 持久化

不同的应用形态实现不同的 Shell：

- **Desktop Shell**：从 MatrixWorld 目录加载模板，使用 SQLite 持久化会话
- **CLI Shell**：从本地文件加载模板，使用内存或文件持久化
- **Server Shell**：从配置中心加载模板，使用数据库存储

这种设计意味着你可以为新的应用场景（如移动端、嵌入式设备）实现一个新的 Shell，而不需要改动 Core 的任何代码。

### App Layer — 具体应用

App 层把一切都组装起来，面向最终用户。

**Desktop App**：Tauri（Rust）+ Vue 3 的桌面应用。Rust 端管理窗口和系统集成，Vue 端提供用户界面。前端通过 HTTP/WebSocket 与 FastAPI 后端通信，后端运行 AgentMatrix Runtime。

**CLI Tutorial**：一个最小示例，展示如何在终端中实现 Shell 协议并运行 MicroAgent。约 200 行代码，适合理解架构。

**Server**：FastAPI 服务，提供 REST API 和 WebSocket 实时推送。可以被 Desktop App 连接，也可以独立部署作为后端服务。

---

## 数据流

一条用户消息从发达到 Agent 执行完毕，经历以下流程：

```
用户输入
   │
   ▼
Desktop App / CLI / 邮件代理
   │
   ▼
PostOffice（邮件总线）
   │
   ▼
BaseAgent 的 inbox
   │
   ▼
信号路由 → 解析 Session → 激活/复用 MicroAgent
   │
   ▼
MicroAgent 执行循环
   │
   ├─→ Brain 思考（自然语言）
   ├─→ Cerebellum 解析（意图 → 动作 + 参数）
   ├─→ Action 执行（调用 Skill）
   ├─→ 结果反馈到对话
   └─→ 循环直到完成
   │
   ▼
生成回复邮件
   │
   ▼
PostOffice 分发
   │
   ▼
用户收到回复
```

---

## 扩展点

系统在设计时考虑了扩展性，以下是主要的扩展入口：

### 接入新的应用形态

实现 `AgentShell` 协议接口，创建你自己的应用。你需要提供：
- Prompt 模板加载方式
- Session 持久化实现
- Checkpoint 行为（是否支持暂停/恢复）
- Working Notes 生成策略

CLI 教程是一个完整的参考实现。

### 开发新的 Skill

Skill 是扩展 Agent 能力的主要方式。有两种路径：

- **Python Skill**：编写一个 Python Mixin 类，用装饰器注册 Action。系统会自动解析依赖并动态组合到 MicroAgent。
- **Markdown Skill**：编写 Markdown 文件描述过程性知识，不需要写代码。

### 接入新的容器后端

容器系统使用适配器模式。当前支持 Docker 和 Podman，通过实现 `ContainerAdapter` 接口可以接入新的容器运行时（如 containerd、LXC）。

### 接入新的 LLM 后端

Brain 和 Cerebellum 通过统一的 LLM 客户端接口与模型服务通信。当前支持所有 OpenAI 兼容接口的服务（包括 OpenAI、Claude via 适配器、Ollama、vLLM 等）。通过扩展 LLM 客户端可以接入新的模型服务。

---

## 设计原则

1. **Core 无 I/O**：Core 层只做纯计算，所有 I/O 通过 Shell 协议委托
2. **邮件即 API**：Agent 之间不调用函数，而是发送邮件。这让多 Agent 协作可追踪、可调试
3. **动态组合**：MicroAgent 在创建时根据可用技能列表动态组合 Mixin，不需要预先定义类
4. **检查点协作**：暂停/恢复不是强制中断，而是 MicroAgent 在关键位置主动询问 Shell 是否应该暂停
5. **上下文自治**：压缩策略由 LLM 自主决定，系统只提供触发条件和重建框架
