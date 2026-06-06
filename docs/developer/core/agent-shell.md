# AgentShell Protocol

AgentShell Protocol 是 Core 层与外部世界之间的接口。它的设计目的是让 Core 保持纯粹（只做执行，不做 I/O），同时让不同的应用场景都能接入 Core 引擎。

---

## 设计目的

Core 层的 MicroAgent 在执行过程中需要与外部世界交互：

- 需要获取 System Prompt 模板
- 需要在上下文过长时生成 Working Notes
- 需要在安全检查点判断是否暂停
- 需要获取 Markdown Skill 的内容

但这些交互的方式在不同场景中完全不同：

- Desktop 场景：从本地文件系统读取模板，用 SQLite 存储会话
- CLI 场景：从本地文件读取模板，用内存或 JSON 文件存储会话
- Server 场景：从数据库或配置中心读取模板，用远程数据库存储会话

AgentShell Protocol 把这些差异封装在一组接口方法后面，MicroAgent 只调用方法，不关心具体实现。

---

## 协议方法

协议定义了以下核心能力：

### 获取 Prompt 模板

MicroAgent 需要加载各种 Prompt 模板（System Prompt、协作模式 Prompt、压缩 Prompt 等）。它通过协议方法向 Shell 请求，而不是直接读取文件。

不同 Shell 可以用不同方式提供模板：从文件系统、数据库、内存、远程配置中心等。

### 生成 Working Notes

当对话历史超过 token 阈值时，MicroAgent 调用此方法请求压缩。Shell 提供具体的 Prompt 和上下文，LLM 生成结构化的工作笔记。

不同 Shell 可以定制压缩策略。例如，邮件场景的 Shell 可能保留更多历史邮件摘要，而纯任务场景的 Shell 可能更关注任务状态。

### 压缩消息

生成 Working Notes 后，MicroAgent 调用此方法执行实际的压缩操作：保留 System Message，用原始用户消息加上 Working Notes 重建对话历史。

Shell 可以覆盖默认实现来自定义压缩行为（如保留特定类型的消息）。

### Checkpoint（检查点）

MicroAgent 在执行循环的关键位置调用 Checkpoint，给 Shell 一个介入的机会。Shell 可以：

- 检查是否有暂停请求，如果有就阻塞等待恢复
- 检查是否有停止请求，如果有就抛出异常终止执行
- 什么都不做，让执行继续

Checkpoint 是协作式的，不是强制中断。MicroAgent 在安全的逻辑边界主动询问，避免了在动作执行中途被强制终止导致的状态不一致。

### 获取 Markdown Skill 内容

MicroAgent 需要加载 Markdown Skill 文件时，通过协议方法向 Shell 请求。Shell 决定从哪里加载（本地文件、数据库、网络等）。

---

## Shell 实现差异

### Desktop Shell

- 从 MatrixWorld 的模板目录加载 Prompt
- 使用 SQLite 持久化会话历史
- 支持完整的暂停/恢复/停止
- 通过事件总线向前端推送状态更新

### CLI Shell

- 从本地文件或内存加载 Prompt
- 使用内存 SessionStore（进程结束数据丢失）或文件 SessionStore
- 支持基本的暂停/停止（通过键盘信号）
- 直接打印到终端

### Server Shell

- 从数据库或环境变量加载 Prompt
- 使用远程数据库持久化
- 支持 API 触发的暂停/停止
- 通过 WebSocket 推送事件

---

## 实现自己的 Shell

如果你想把 MicroAgent 引擎集成到自己的应用中，需要：

1. 创建一个类实现 AgentShell Protocol 的方法
2. 配置 Brain 和 Cerebellum（LLM 客户端）
3. 配置 Action Registry（注册你需要的 Skill）
4. 创建 MicroAgent，把 Shell 实例作为 parent 传入
5. 调用 MicroAgent 的执行方法

CLI 教程 (`tutorial/cli-agent/`) 是一个完整的工作示例，展示了如何在约 200 行代码中实现一个可用的 Shell。
