# Collab 模式

## 什么是 Collab 模式

在 AgentMatrix 中，Agent 默认以邮件模式工作：用户发送邮件，Agent 处理后回复邮件。这种模式适合异步的、长程的任务，用户不需要实时参与。

Collab 模式是 Agent 的另一种行为模式。在这种模式下，Agent 和用户"坐在一起"工作，就像两个人在电脑前协作完成一个任务。用户可以实时看到 Agent 的操作过程，Agent 也会频繁地向用户展示中间成果、征求反馈。

你可以把 Collab 模式想象成一个视频通话中的屏幕共享：Agent 在操作，用户在看，随时可以插话。而邮件模式则像发邮件委托任务，Agent 做完了再回复你。

## 设计哲学：行为模式，不是会话模式

Collab 模式是一个关键的架构决策：它是 Agent 的行为模式，而不是会话（Session）的模式。

这意味着什么？会话是一串对话记录，由 session_id 标识。如果 Collab 是会话模式，那一个会话要么是邮件会话、要么是 Collab 会话，用户需要"新建一个 Collab 会话"来开始协作。

但 Collab 是行为模式。同一个会话中，Agent 可以在邮件风格和协作风格之间切换。用户在普通对话中说"帮我做 PPT"，Agent 进入 Collab 模式，频繁预览、频繁确认。做完后回到普通模式，继续异步处理其他任务。

这种设计的好处是对话的连续性。用户不需要管理会话的类型，只需要和 Agent 交互，Agent 根据场景选择合适的行为方式。

## Collab 模式是 Agent 级别的运行时状态

Collab 模式的开关存储在 BaseAgent 的 `collab_mode` 属性上。这是一个布尔值，默认为 False（邮件模式），可以通过 API 切换为 True（Collab 模式）。

这个属性是运行时状态，不持久化。系统重启后回到默认的邮件模式。前端连接时通过 API 设置，断开时可以清除。

一个 Agent 同一时刻只能处于一种模式。但模式的切换是即时的，不需要重启或重建会话。

## 与邮件模式的差异

Collab 模式和邮件模式共享相同的核心机制：同样的邮件系统、同样的信号驱动循环、同样的 MicroAgent 执行流程。差异体现在三个层面。

### 层面一：System Prompt 不同

当 Agent 处于 Collab 模式时，MicroAgent 在构建 system prompt 时会加载专门的 `collab_mode.md` 模板，而不是默认的 `system_prompt.md`。

这个 Collab prompt 强调几个核心原则：

- **边做边说**：每做一步操作，简要告诉用户在做什么、为什么。
- **频繁预览**：每当产出一个可视化的中间成果，立即用 `open_file_for_user_preview` 展示。
- **主动确认**：在关键决策点用 `ask_user` 向用户确认，不替用户做决定。
- **保持参与感**：用户能实时看到终端操作，重要操作前用一句话说明意图。

而默认的邮件 prompt 强调的是通过邮件异步沟通、记忆管理、单次执行等原则。

MicroAgent 的 `_build_system_prompt` 方法在构建 prompt 时，会检查 `root_agent.collab_mode`，如果为 True，从 PromptRegistry 加载 `COLLAB_MODE` 模板。PromptRegistry 自动扫描配置目录下的 `collab_mode.md` 文件，注册为 `COLLAB_MODE`。

### 层面二：容器输出实时镜像

这是 Collab 模式最具特色的机制。在邮件模式下，Agent 执行 bash 命令后，用户只能在邮件中看到最终结果。在 Collab 模式下，命令的输出会被实时"镜像"到前端。

实现原理是 ContainerSession 的 output mirror 机制。ContainerSession 维护着一个持久的 shell 进程，通过两个后台线程（`_read_stdout` 和 `_read_stderr`）持续读取进程输出。正常情况下，这些输出只进入内部队列供 `execute` 方法收集。

当 Collab 模式启用时，BaseAgent 通过 `_setup_collab_output_mirror` 方法，在 ContainerSession 上注册一个 output callback。这个 callback 在 reader 线程中被调用——每读到一行输出，就同时推送给 callback。

由于 reader 线程是同步线程，不能直接调用 asyncio 代码，callback 使用 `asyncio.run_coroutine_threadsafe` 将 WebSocket 广播操作安全地调度到事件循环中。广播的消息类型是 `COLLAB_BASH_OUTPUT`，包含 stream 类型（stdout 或 stderr）和行内容。

当前端收到这些消息时，可以渲染成一个实时终端视图，让用户像看直播一样看到 Agent 的命令执行过程。

当 Collab 模式关闭时，`_teardown_collab_output_mirror` 清除 callback，输出不再被镜像。这个机制对 ContainerSession 的 `execute` 方法完全透明——方法签名和返回值不变，所有现有的调用方无需任何修改。

### 层面三：预览状态追踪

Agent 有一个 `current_preview_file` 属性，记录当前正在预览的文件路径。每当 Agent 调用 `open_file_for_user_preview` 打开文件预览时，这个属性被设置为临时文件路径。当 Agent 的会话结束或预览被清理时，属性被重置为 None。

这个属性包含在 `get_status_snapshot` 的返回值中，通过 `AGENT_STATUS_UPDATE` WebSocket 消息推送给前端。前端可以根据这个信息显示"Agent 正在预览：xxx.pptx"之类的状态提示。

## 激活和关闭

Collab 模式通过 Server API 控制。

`POST /api/agents/{agent_name}/collab` 接受一个 JSON body，包含 `enabled` 字段。设置为 True 时，Agent 的 `collab_mode` 被设为 True，同时调用 `_setup_collab_output_mirror` 注册容器输出镜像。设置为 False 时，清除 `collab_mode` 并调用 `_teardown_collab_output_mirror`。

前端 Collab UI 在用户进入协作界面时调用此 API 开启模式，退出时关闭。用户也可以在普通对话中通过消息触发模式切换——Collab UI 发送消息时可以隐含地设置 Agent 为 Collab 模式。

## Workspace 文件浏览

Collab 模式下，前端通常需要展示 Agent 的工作目录文件树。Server 提供了 `GET /api/agents/{agent_name}/workspace` 接口，返回 Agent 当前 `private_workspace` 目录下的文件列表，包括文件名、路径、是否为目录、大小和修改时间。

前端可以定期轮询这个接口，或在收到 `AGENT_STATUS_UPDATE` 消息时刷新文件树。

## 数据流总览

Collab 模式下的数据流分为几个通道：

**状态更新通道**（复用现有）：Agent 的状态变化（thinking、working、waiting_for_user）通过 `AGENT_STATUS_UPDATE` WebSocket 消息推送给前端。`current_preview_file` 也包含在这个消息中。

**容器输出通道**（新增）：命令的 stdout/stderr 通过 `COLLAB_BASH_OUTPUT` WebSocket 消息实时推送给前端。这是流式的，命令执行期间就能看到输出。

**用户输入通道**（复用现有）：用户通过 `POST /api/agents/{agent_name}/submit_user_input` 提交回答，唤醒正在 `ask_user` 中等待的 Agent。

**文件浏览通道**（新增）：前端通过 `GET /api/agents/{agent_name}/workspace` 获取工作目录文件树。

所有通道都走同一个 WebSocket 连接和 REST API，不需要独立的 Collab 通信协议。

## 与已有功能的关系

Collab 模式不替代邮件模式，而是补充。邮件模式继续负责异步的、长程的、多会话的任务处理。Collab 模式负责实时的、交互式的、需要频繁反馈的协作任务。

两种模式共享同一个 BaseAgent、同一个 PostOffice、同一个 Session 系统。切换模式只是改变 Agent 的行为风格，不影响底层架构。

`collab_with_user` skill 中的 `open_file_for_user_preview` 和 `ask_user` 在两种模式下都能工作，但 Collab prompt 会鼓励 Agent 更频繁地使用它们。
