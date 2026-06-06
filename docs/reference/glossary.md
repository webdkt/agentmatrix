# 术语表

## Agent

系统中的自主参与者，可以是 AI Agent 或人类用户。每个 Agent 有一个名字、一段描述（description）、一段人设（persona），以及一组技能。Agent 通过接收邮件来触发任务执行。

## BaseAgent

Desktop 运行时的 Agent 基类，继承自 Core 层的 BasicAgent。负责管理 Agent 的生命周期、状态机、信号路由和 MicroAgent 的激活/切换。所有实际运行的 Agent（包括 UserProxy）都是 BaseAgent 的实例。

## Brain

Agent 的"大脑"，即与大语言模型交互的模块。负责生成思考内容、工作笔记和对话回复。Brain 只处理自然语言，不关心输出格式。

## Cerebellum

Agent 的"小脑"，负责将 Brain 的自然语言输出解析为结构化的动作意图和参数。当意图模糊时，Cerebellum 会向 Brain 请求澄清。Cerebellum 可以由较小的模型担任，与大模型 Brain 形成分工。

## MicroAgent

Core 层的任务执行引擎。每个待处理的任务会创建一个 MicroAgent 实例，它执行 think-negotiate-act 循环直到任务完成。MicroAgent 从父 Agent 继承 Brain、Cerebellum、Action 注册表等组件，自身只关注执行逻辑。

## AgentShell Protocol

Core 层与外部世界之间的接口协议。定义了获取 Prompt 模板、生成工作笔记、压缩消息、检查点等方法。不同的应用形态（Desktop、CLI、Server）通过实现这个协议来接入 Core 引擎。

## Action

Agent 可调用的能力单元。每个 Action 有一个名字、一段描述和参数说明。Action 被注册到 ActionRegistry 中，MicroAgent 在执行阶段从注册表里查找并调用匹配的 Action。

## Skill

Action 的容器。一个 Skill 是一组相关 Action 的集合，通常对应一个领域能力（如文件操作、浏览器控制、网页搜索）。Skill 可以用 Python 实现（作为 Mixin 动态组合到 MicroAgent），也可以用 Markdown 编写（作为过程性知识供 Agent 读取）。

## Email

Agent 之间通信的基本单位。包含发件人、收件人、主题、正文、会话 ID、任务 ID 和附件等字段。所有通信都通过 Email 进行，无论是用户给 Agent 发任务，还是 Agent 之间的协作。

## Session

单个 Agent 的邮件往来视图，是主观视角。同一个对话在发送方和接收方各有自己的 Session。Session 由会话 ID 标识，用于组织邮件列表和查询历史。

## Task

一个完整的工作任务或上下文范围，是客观工作单元。一个 Task 可能涉及多个 Agent 和多组 Session，所有相关邮件共享同一个任务 ID。Task 也是文件隔离的边界。

## PostOffice

系统的邮件总线。负责 Agent 的注册与发现（黄页机制）、邮件的接收、持久化存储和分发。所有邮件先进入 PostOffice 的队列，再由 PostOffice 派发给目标 Agent。

## Runtime (AgentMatrix)

Desktop 运行时的总控模块。负责初始化路径、加载 Agent、启动 PostOffice、管理系统状态、连接前端事件推送。它是整个 Desktop 应用的后端大脑。

## SessionStore

会话持久化接口。负责将 MicroAgent 的对话历史保存到存储介质（文件、数据库或内存），并在系统重启后恢复。SessionStore 的实现由具体的 Shell 提供。

## Working Notes

上下文压缩后的状态快照。当对话历史超过 token 阈值时，系统让 LLM 生成一段结构化的工作笔记来替代冗长的历史消息。工作笔记的格式由 LLM 根据对话类型自主决定。

## Compression

自动压缩机制。当 MicroAgent 的消息历史超过预设阈值时触发，保留 system message，用原始用户消息加上生成的 Working Notes 重建对话历史，从而防止上下文溢出。

## Checkpoint

协作式检查点。MicroAgent 在执行循环的关键位置调用 checkpoint，让 Shell 有机会暂停或停止执行。暂停时 Agent 在安全位置停下，保存状态，等待恢复信号。

## Signal

事件驱动的通信单元。Core 层使用 Signal 来传递输入、输出和事件。input_queue 接收外部信号，event_queue 向 Shell 输出事件。Signal 机制使得 Agent 的响应是异步和事件化的。

## MatrixWorld

AgentMatrix 的工作空间根目录。包含系统配置、Agent 配置、LLM 配置、邮件数据库、任务文件等所有运行时数据。路径可以通过 `--matrix-world` 参数指定。

## Workspace

Agent 的任务工作目录。每个任务在文件系统中有独立的目录，任务内创建的文件不会泄漏到其他任务。Agent 在不同任务间切换时，工作目录自动切换。

## Container

Agent 的运行隔离环境。每个 Agent 可以运行在独立的 Docker 或 Podman 容器中，文件操作和命令执行在容器内进行。容器支持休眠（空闲时停止）和唤醒（收到邮件时启动）。目前实际上基本不再使用，而是直接使用local mode。

## Local Mode

容器的替代运行模式。Agent 直接在宿主机上运行，不创建容器。适用于开发调试或没有容器环境的场景。通过配置切换本地模式与容器模式。目前主要的配置模式

## UserProxy

代表人类用户的 Agent。它接收来自桌面应用或邮件的输入，转发给目标 Agent，并将 Agent 的回复返回给用户。UserProxy 本身不执行复杂推理，是用户与系统之间的代理。

## SystemAdmin

一个特殊的内置 Agent，专门用于管理系统配置。用户可以用自然语言向它发出配置变更请求，它会自动读取、验证、测试、备份和写入配置。

## AgentAdmin

一个特殊的内置 Agent，专门用于管理其他 Agent 的生命周期。用户可以用自然语言创建、克隆、编辑、删除 Agent，或控制 Agent 的任务状态。

## Yellow Page

PostOffice 维护的 Agent 目录。每个注册的 Agent 都会在其中留下条目，包含名称和描述。Agent 可以通过黄页查找其他 Agent 的联系方式和职责描述。

## Persona

Agent 的人设描述，定义了 Agent 的角色、性格、工作方式和约束条件。Persona 是 System Prompt 的重要组成部分，直接影响 Agent 的行为风格。

## Skill Registry

技能注册表。维护系统中所有可用 Skill 的元信息，包括 Skill 名称、描述、Action 列表和依赖关系。Skill Registry 在 MicroAgent 创建时用于动态组合 Skill Mixin。
