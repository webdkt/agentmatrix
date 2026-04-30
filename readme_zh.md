# AgentMatrix

[English](readme.md) | [中文](readme_zh.md)

**让 LLM 专注于思考，而不是格式。**

为什么让一个强大的语言模型做点事，非要先教会它写 JSON？你让 GPT 帮你做研究，它得先理解你的意图，然后还得小心翼翼地输出符合格式的 JSON。推理能力和格式能力，两种完全不同的能力被硬塞进同一个输出通道。就像让人一边解数学题一边写书法——两个任务互相干扰，哪个都做不好。

AgentMatrix 把这两件事分开了。大模型只管思考，小模型处理格式。就这么简单。

---

## 架构

经过最新重构，AgentMatrix 采用清晰的三层架构：

```
┌─────────────────────────────────────────────┐
│  App 层       Desktop App / CLI / Server    │
├─────────────────────────────────────────────┤
│  Shell 层     AgentShell 协议               │
│               （层间接口）                    │
├─────────────────────────────────────────────┤
│  Core 层      MicroAgent 引擎               │
│               （纯执行，无 I/O）             │
└─────────────────────────────────────────────┘
```

- **Core 层** — `MicroAgent` 是执行引擎。它不知道桌面应用、CLI 或文件系统的存在。纯推理循环：思考 → 检测动作 → 执行 → 重复。
- **Shell 层** — `AgentShell` 是连接 Core 与外部世界的协议。每种应用形态（Desktop、CLI、Server）实现这个接口，提供 LLM 客户端、prompt 模板、检查点逻辑、压缩策略和会话存储。
- **App 层** — 具体的应用程序，把一切组装起来：桌面应用、CLI 工具或 FastAPI 服务器。

这种分离意味着相同的 Core 代理行为可以在桌面、终端或云端运行，Core 代码一行都不用改。

---

## Agent 能做什么

### 自由地思考

Agent 的"大脑"（大模型）完全用自然语言推理。不需要输出 JSON，不需要遵守任何格式约束。一个独立的"小脑"（小模型）负责把意图翻译成可执行的参数。如果意图不够清晰，小脑会反问大脑。两个模型各司其职。

### 像写邮件一样协作

Agent 之间不调用 API，而是发邮件。自然语言的邮件。

你能看懂 Agent 之间在说什么，能追踪对话线程，能理解它为什么要这么做。它不只是返回一个状态码——它解释自己的推理过程。调试和理解多 Agent 系统变得前所未有地自然。

### 随时暂停、恢复、终止

任何一个正在运行的 Agent 都可以被暂停、恢复或立即终止。暂停时，它会在安全的检查点停下，保存当前状态，随时可以恢复。终止当前任务不会影响 Agent 继续接收新邮件。

### 跑超长任务，不会撑爆上下文

当对话历史增长到一定程度，系统会自动压缩成"工作笔记"（Working Notes）——由 LLM 根据当前对话的性质动态生成的状态快照。不是固定模板，而是针对研究型、知识型、创作型等不同类型生成最优结构。任务可以持续数小时、数天，上下文永远不会溢出。

### 主动向你提问

Agent 在执行过程中可以暂停，主动向你提问，等你回答后再继续。桌面应用会弹出对话框，你也可以通过邮件回复。双通道通知——桌面端实时弹窗 + 邮件提醒，你不会错过。

### 每个任务独立的工作空间

每个任务都有自己的私有工作目录。Agent 在任务 A 中创建的文件不会干扰任务 B。切换任务时，工作空间自动切换。

### 运行在隔离的容器里

每个 Agent 运行在独立的 Docker 容器中。文件操作在容器内执行，Agent 之间互不干扰。容器按需唤醒和休眠——空闲时休眠省资源，有新邮件时自动唤醒。

### 状态持久化，不怕重启

对话历史通过 `SessionStore` 自动持久化。关机重启后，Agent 从断点恢复。正在处理的任务不会丢失。

### LLM 服务挂了也不怕

如果 LLM 服务在执行过程中宕机，Agent 会自动进入等待模式，定期检测服务恢复。服务恢复后自动继续执行，不丢失任何进度。

---

## 系统管理：用自然语言搞定

因为 LLM 天然能读懂 YAML/JSON，系统配置完全可以通过自然语言来管理。

### SystemAdmin Agent

不用手动编辑配置文件。告诉 SystemAdmin 你想做什么就行：

- "帮我加一个新的 LLM 模型，用 GPT-4o"
- "把邮件代理关掉"
- "查看当前的系统配置"

SystemAdmin 会读取配置、验证格式、测试连接、自动备份旧配置，然后写入新的。每一步都有自然语言的反馈。

### AgentAdmin Agent

管理其他 Agent 的生命周期，同样用自然语言：

- "创建一个叫 Researcher 的 Agent，技能是 web_search 和 memory"
- "克隆 Writer 这个 Agent，新名字叫 Editor"
- "停掉 Researcher 的当前任务"
- "删掉 Editor"

创建 Agent 时会自动验证技能是否存在、模型是否可用。修改配置前会自动备份。支持回滚——随时可以查看和恢复历史配置版本。

---

## 技能系统

### 内置技能

| 技能 | 能力 |
|------|------|
| base | 日期/时间工具 |
| file | 文件读写、搜索、命令执行 |
| shell | Shell 命令执行 |
| browser | 浏览器自动化 |
| web_search | 网络搜索 |
| email | 给其他 Agent 发邮件（支持附件） |
| memory | 知识与记忆管理 |
| vision | 图像分析 |
| markdown | Markdown 处理 |
| scheduler | 定时任务（支持周期性重复） |
| system_admin | 系统配置管理 |
| agent_admin | Agent 生命周期管理 |

### 扩展技能：写代码

编写自定义 Python 技能，实现特定领域的能力。技能之间可以声明依赖，系统自动解析。

### 扩展技能：写 Markdown（推荐）

不需要写代码。在工作空间的 `SKILLS/` 目录下放一个 `skill.md` 文件，用 Markdown 写清楚操作步骤和流程，Agent 就能把它当作程序化知识来使用。定义 SOP、工作流、领域知识——纯文本就够。

---

## 组件

### 1. Core 框架 (`src/agentmatrix/`)

Python 包 `agentmatrix-core`。安装后构建你自己的 Agent 应用。

```bash
pip install agentmatrix-core
```

核心模块：
- `core/micro_agent.py` — 执行引擎
- `core/agent_shell.py` — Shell 协议（为你的应用实现这个接口）
- `core/cerebellum.py` — 意图到动作的参数协商
- `core/action.py` — 动作注册与执行
- `core/session_store.py` — 会话持久化接口
- `core/signals.py` — 事件驱动通信
- `skills/` — 内置技能（Python Mixin）

### 2. 桌面应用 (`agentmatrix-desktop/`)

原生桌面应用，基于 Tauri (Rust) + Vue 3。

- **Matrix 风格初始化向导** — 全屏字符雨动画、打字机效果、逐步配置
- **实时状态** — Agent 状态通过 WebSocket 推送，无需刷新
- **邮件式交互** — 像给同事写邮件一样给 Agent 发消息，支持拖拽附件
- **Prompt 预览** — 查看任何 Agent 的完整 System Prompt
- **设置 GUI** — 图形化管理 LLM 配置和邮件代理，不用碰配置文件
- **中英双语** — 完整支持中文和英文界面切换

### 3. CLI 教程 (`tutorial/cli-agent/`)

一个最小可运行的示例，展示如何用 Core 框架构建终端 Agent。约 200 行代码，实现了 `AgentShell`，把 `MicroAgent` 和三个基础技能组装起来。

想理解架构或构建自己的应用，从这里开始。

---

## 快速开始

### 试试 CLI 教程

```bash
cd tutorial/cli-agent

# 设置 API Key
export OPENAI_API_KEY=sk-xxx

# 运行
python main.py -m openai:gpt-4o
```

你会得到一个功能完整的终端 Agent，拥有 file、shell、base 三个技能。支持 Textual TUI（如果安装了）或自动降级到简单模式。

### 桌面应用

```bash
cd agentmatrix-desktop
npm install
npm run tauri:dev
```

首次启动进入初始化向导，按提示完成即可。

### 作为 Python 库使用

```bash
pip install agentmatrix-core
```

然后实现 `AgentShell` 接口，创建你自己的 Agent 应用。完整示例见 `tutorial/cli-agent/`。

---

## 邮件代理：用真实邮件和 Agent 交互

配置邮件代理后，你可以用 Gmail、Outlook、QQ 邮箱等真实邮件客户端和 Agent 交互：

- 给 Agent 发一封邮件，主题里写 `@AgentName`，Agent 就会收到并处理
- Agent 的回复会转发到你的邮箱，保持邮件线程
- Agent 向你提问时，你直接回复邮件就行
- 附件自动双向传递

---

## 项目结构

```
agentmatrix/
├── src/agentmatrix/              # Core 框架 (pip install agentmatrix-core)
│   ├── core/                     # MicroAgent、AgentShell、小脑、动作系统
│   ├── skills/                   # 内置技能 (Python Mixin)
│   ├── agents/                   # BaseAgent
│   ├── backends/                 # LLM 后端集成
│   ├── profiles/                 # Agent 配置文件
│   └── services/                 # ConfigService 等
├── agentmatrix-desktop/          # 桌面应用 (Tauri + Vue 3)
│   ├── src/                      # Vue 3 前端
│   └── src-tauri/                # Rust 后端
├── tutorial/cli-agent/           # CLI 教程和演示
│   ├── main.py                   # 入口 + TUI
│   ├── cli_shell.py              # AgentShell 实现
│   ├── cli_config.py             # 配置管理
│   └── skills/                   # 基础技能 (file, shell, base)
├── docs/                         # 文档
├── examples/                     # 示例
└── server.py                     # FastAPI 服务
```

---

## 文档

**Core 框架** (`docs/core/`)
- [大脑小脑与动作](docs/core/01-大脑小脑与动作.md)
- [事件驱动的执行循环](docs/core/02-事件驱动的执行循环.md)
- [System Prompt 的构成](docs/core/03-System-Prompt的构成.md)
- [会话自动压缩机制](docs/core/04-会话自动压缩机制.md)
- [Python Skill 机制](docs/core/05-Python-Skill机制.md)
- [无限嵌套的 MicroAgent 模式](docs/core/06-无限嵌套的MicroAgent模式.md)

**Desktop App** (`docs/desktop/`)
- [整体架构概览](docs/desktop/architecture/01-整体架构概览.md)
- [运行时与邮局](docs/desktop/architecture/02-运行时与邮局.md)
- [Config Service 与管理技能](docs/desktop/services/Config-Service与管理技能.md)
- [Collab 模式](docs/desktop/architecture/07-Collab模式.md)

**教程**
- [CLI Agent 教程](tutorial/cli-agent/README.md)

**完整索引**: [docs/README.md](docs/README.md)

---

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)

---

**仓库**: https://github.com/webdkt/agentmatrix
