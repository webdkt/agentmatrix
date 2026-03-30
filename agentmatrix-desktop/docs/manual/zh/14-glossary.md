# 术语表

AgentMatrix Desktop 中使用的术语定义。

| 术语 | 定义 |
|------|------|
| **智能体 (Agent)** | 一个自主 AI 实体，配置了名称、人格、技能和语言模型。智能体执行任务并通过邮件通信。 |
| **后端 (Backend)** | Python 运行时服务器，管理智能体执行、处理 API 请求并协调 WebSocket 连接。 |
| **大脑 (Brain / LLM)** | 用于复杂推理任务的大语言模型。配置为 `default_llm`。 |
| **小脑 (Cerebellum / SLM)** | 用于轻量级快速任务的小语言模型。配置为 `default_slm`。 |
| **冷启动 (Cold-Start)** | 当 AgentMatrix 检测到不存在配置时运行的首次设置流程。 |
| **容器运行时 (Container Runtime)** | 在隔离环境中运行智能体的软件（Podman 或 Docker）。 |
| **邮件 (Email)** | 会话中的消息 —— 您和智能体之间的主要通信方式。 |
| **邮件代理 (Email Proxy)** | 通过 IMAP/SMTP 连接 AgentMatrix 和真实邮箱的可选桥梁。 |
| **IMAP** | 互联网消息访问协议 —— 用于从邮件服务器接收邮件。 |
| **LLM** | 大语言模型 —— 强大的 AI 模型（如 GPT-4o、Claude Sonnet），用于复杂推理。 |
| **Matrix 视图 (Matrix View)** | 监控仪表板，显示所有智能体、其状态、日志和会话历史。 |
| **Matrix World** | 包含所有智能体数据、配置和生成文件的工作空间目录。 |
| **MERIDIAN** | AgentMatrix Desktop 使用的自定义设计系统（羊皮纸 + 墨水 + 朱砂调色板）。 |
| **人格 (Persona)** | 定义智能体性格、角色、职责和行为约束的文本描述。 |
| **Podman** | 无根容器引擎 —— AgentMatrix 的首选容器运行时。 |
| **会话 (Session)** | 对话线程 —— 您与一个或多个智能体之间的邮件序列。 |
| **技能 (Skill)** | 智能体可以使用的能力，如网页搜索、文件管理或邮件处理。 |
| **SLM** | 小语言模型 —— 更快、更便宜的 AI 模型，用于简单任务。 |
| **SMTP** | 简单邮件传输协议 —— 用于通过邮件服务器发送邮件。 |
| **系统提示词 (System Prompt)** | 每个智能体在运行时加载的基础指令模板，定义通信协议和认知模型。 |
| **Tauri** | 用于构建 AgentMatrix 的桌面应用框架（Rust 后端 + WebView 前端）。 |
| **WebSocket** | 用于前端和后端之间实时更新的通信协议。 |
| **向导 (Wizard)** | 引导式首次运行设置流程（冷启动向导），用于配置基本设置。 |
