# AgentMatrix

[English](readme.md) | 中文

**让大模型思考，不要让它们写 JSON。**

让大模型做事之前，通常得先教它 JSON 语法。这很别扭：你问 GPT 研究一个话题，它既要理解你的意图，又要小心翼翼输出格式正确的 JSON。两种完全不同的能力——推理和格式化——被硬塞进同一个输出通道。AgentMatrix 把这两件事分开：大模型只管思考，格式化交给另一个专门的模块。就这么简单。

---

## 这能做什么

### 自由思考

Agent 的"大脑"（大模型）完全用自然语言推理，不需要输出 JSON，也不受格式约束。另一个"小脑"（较小的模型）负责把意图翻译成可执行的参数。如果意图模糊，小脑会向大脑请求澄清。两个模型，各干各擅长的事。

### 像邮件一样协作

Agent 之间不调用 API，它们发邮件——自然语言的邮件。

你可以看到 Agent 之间说了什么，追踪对话线程，理解某个 Agent 为什么做了某个决定。它不会只返回一个状态码，而是解释自己的推理过程。调试多 Agent 系统第一次变得直观。

### 随时暂停、恢复、停止

任何运行中的 Agent 都可以暂停、恢复或停止。暂停时，它在安全检查点停下，保存状态，之后可以恢复。停止当前任务不会影响 Agent 接收新邮件。

### 长任务不会撑爆上下文

当对话历史太长，系统会自动把它压缩成"工作笔记"——由 LLM 动态生成的状态快照。这不是固定模板，LLM 会分析对话类型（研究、知识整理、创意写作）并生成最适合该场景的结构。任务可以运行几小时甚至几天，上下文窗口不会溢出。

### 执行中向你提问

Agent 可以在任务执行到一半时暂停，向你提问，然后等你的回答再继续。桌面应用会弹出对话框，你也可以通过邮件回复。双通道通知，不会漏掉。

### 每个任务有独立的工作空间

每个任务都有自己的私有工作目录。任务 A 创建的文件不会干扰任务 B。Agent 在不同任务之间切换时，工作空间自动切换。

### 在隔离容器中运行

每个 Agent 运行在自己的 Docker/Podman 容器里。文件操作在容器内执行，Agent 之间不会互相干扰。容器在空闲时休眠，收到新邮件时自动激活。

### 重启后自动恢复

对话历史通过 SessionStore 自动持久化。关机重启后，Agent 从断点继续，正在执行的任务不会丢失。

### LLM 服务中断后自动恢复

如果 LLM 服务在执行过程中宕机，Agent 进入等待模式，周期性检测恢复。服务恢复后，执行自动继续，不会丢失进度。

---

## 自然语言管理系统配置

因为 LLM 天然能读懂 YAML/JSON，系统配置可以完全通过自然语言管理。

### SystemAdmin Agent

不需要手动编辑配置文件，直接告诉它你想要什么：

- "添加一个使用 GPT-4o 的 LLM 模型"
- "关闭邮件代理"
- "显示当前系统配置"

SystemAdmin 会读取配置、验证格式、测试连接、备份旧版本、写入新版本。每一步都有自然语言反馈。

### AgentAdmin Agent

用自然语言管理其他 Agent 的生命周期：

- "创建一个叫 Researcher 的 Agent，带 web_search 和 memory 技能"
- "把 Writer 克隆成 Editor"
- "停止 Researcher 的当前任务"
- "删除 Editor"

创建时会验证技能是否存在、模型是否可达。修改自动备份。支持回滚——可以查看和恢复任意历史配置版本。

---

## 技能系统

### 内置技能

| 技能 | 能力 |
|------|------|
| base | 日期时间工具 |
| file | 文件读写、搜索、命令执行 |
| shell | Shell 命令执行 |
| browser | 浏览器自动化 |
| web_search | 网页搜索 |
| email | 向其他 Agent 发送邮件（支持附件） |
| memory | 知识与记忆管理 |
| vision | 图像分析 |
| markdown | Markdown 处理 |
| scheduler | 定时任务（支持周期性执行） |
| system_admin | 系统配置管理 |
| agent_admin | Agent 生命周期管理 |

### 用代码扩展

写自定义 Python 技能来实现领域特定能力。技能之间可以声明依赖关系——系统会自动解析。

### 用 Markdown 扩展（推荐）

不需要写代码。在工作区的 `SKILLS/` 目录下放一个 `skill.md` 文件，用 Markdown 描述流程和工作流。Agent 会把它当作过程性知识来读取。定义 SOP、工作流、领域专业知识——纯文本就够了。

---

## 快速开始

### 试用 CLI 教程

```bash
cd tutorial/cli-agent

# 设置 API Key
export OPENAI_API_KEY=sk-xxx

# 运行
python main.py -m openai:gpt-4o
```

这是一个完整的终端 Agent，带 file、shell、base 三个技能。如果安装了 Textual 会自动使用 TUI 界面，否则回落到简单模式。

### Desktop App

```bash
cd agentmatrix-desktop
npm install
npm run tauri:dev
```

首次启动会自动进入配置向导。

### 作为库使用

```bash
pip install agentmatrix-core
```

然后实现 `AgentShell` 协议，创建你自己的 Agent 应用。`tutorial/cli-agent/` 是一个完整的工作示例。

---

## 邮件代理：通过真实邮件与 Agent 对话

配置邮件代理后，你可以用 Gmail、Outlook、QQ 邮箱等任何邮件客户端与 Agent 交互：

- 邮件主题里写 `@AgentName` → Agent 收到并处理
- Agent 的回复转发到你的邮箱，保持邮件线程
- Agent 向你提问时，直接回复邮件即可
- 附件双向自动传输

---

## 项目结构

```
agentmatrix/
├── src/agentmatrix/              # Core 框架（pip install agentmatrix-core）
│   ├── core/                     # MicroAgent、AgentShell、Cerebellum、Actions
│   └── desktop/                  # BaseAgent、PostOffice、容器管理、技能
├── agentmatrix-desktop/          # 桌面应用（Tauri + Vue 3）
│   ├── src/                      # Vue 3 前端
│   └── src-tauri/                # Rust 后端
├── tutorial/cli-agent/           # CLI 教程与演示
├── server_handlers/              # FastAPI 后端服务
├── docs/                         # 文档
└── examples/                     # 示例
```

---

## 文档

- **[用户指南](docs/user/)** — 安装、Desktop App 使用、与 Agent 交互、邮件代理
- **[开发者指南](docs/developer/)** — 架构、Core 引擎、运行时、Skill 开发
- **[参考文档](docs/reference/)** — 术语表、目录结构、核心概念
- **[CLI 教程](tutorial/cli-agent/)** — 最小可运行示例

---

## License

Apache License 2.0 — 详见 [LICENSE](LICENSE)
