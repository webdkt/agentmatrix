# AgentMatrix

[English](readme.md) | [中文](readme_zh.md)

**让 LLM 专注于思考，而不是格式。**

我们一直在想：为什么让一个强大的语言模型做点事，非要先教会它写 JSON？

你让 GPT 帮你做研究，它得先理解你的意图，然后还得小心翼翼地输出符合格式的 JSON。推理能力和格式能力，两种完全不同的能力被硬塞进同一个输出通道。就像让人一边解数学题一边写书法——两个任务互相干扰，哪个都做不好。

AgentMatrix 把这两件事分开了。大模型只管思考，小模型处理格式。就这么简单。

---

## 它是什么

AgentMatrix 是一个多 Agent 框架，带一个原生桌面应用。

它不只是又一个 "AI Agent SDK"。它重新定义了 Agent 之间、Agent 与人之间的协作方式。

---

## Agent 能做什么

### 自由地思考

Agent 的"大脑"（大模型）完全用自然语言推理。不需要输出 JSON，不需要遵守任何格式约束。想说什么就说什么。一个独立的"小脑"（小模型）负责把意图翻译成可执行的参数。如果意图不够清晰，小脑会反问大脑。两个模型各司其职。

### 像写邮件一样协作

Agent 之间不调用 API，而是发邮件。自然语言的邮件。

你能看懂 Agent 之间在说什么，能追踪对话线程，能理解它为什么要这么做。它不只是返回一个状态码——它解释自己的推理过程。这让调试和理解多 Agent 系统变得前所未有地自然。

### 随时暂停、恢复、终止

任何一个正在运行的 Agent 都可以被暂停、恢复或立即终止。暂停时，它会在安全的检查点停下，保存当前状态，随时可以恢复。终止当前任务不会影响 Agent 继续接收新邮件。

### 跑超长任务，不会撑爆上下文

Agent 可以执行上千步甚至不限时长的任务。当对话历史增长到一定程度，系统会自动压缩——用一个"白板"（状态快照）替代冗长的历史记录。这个白板不是固定模板，而是由 LLM 根据当前对话的性质动态生成的。研究型对话、知识型对话、创作型对话——每种类型都有最合适的压缩方式。任务可以持续数小时、数天，上下文永远不会溢出。

### 主动向你提问

Agent 在执行过程中可以暂停，主动向你提问，等你回答后再继续。桌面应用会弹出对话框，你也可以通过邮件回复。双通道通知——桌面端实时弹窗 + 邮件提醒，你不会错过。

### 每个任务独立的工作空间

每个任务都有自己的私有工作目录。Agent 在任务 A 中创建的文件不会干扰任务 B。切换任务时，工作空间自动切换。

### 运行在隔离的容器里

每个 Agent 运行在独立的 Docker 容器中。文件操作在容器内执行，Agent 之间互不干扰。容器按需唤醒和休眠——空闲时休眠省资源，有新邮件时自动唤醒。

### 状态持久化，不怕重启

对话历史自动保存到磁盘。关机重启后，Agent 从断点恢复。正在处理的任务不会丢失。

### LLM 服务挂了也不怕

如果 LLM 服务在执行过程中宕机，Agent 会自动进入等待模式，定期检测服务恢复。服务恢复后自动继续执行，不丢失任何进度。

---

## 系统管理：用自然语言搞定

AgentMatrix 有一个独特的设计理念：因为 LLM 天然能读懂 YAML/JSON，系统配置完全可以通过自然语言来管理。

### SystemAdmin Agent

不用手动编辑配置文件。告诉 SystemAdmin 你想做什么就行：

- "帮我加一个新的 LLM 模型，用 GPT-4o"
- "把邮件代理关掉"
- "查看当前的系统配置"
- "重启系统"

SystemAdmin 会读取配置、验证格式、测试连接、自动备份旧配置，然后写入新的。每一步都有自然语言的反馈。

### AgentAdmin Agent

管理其他 Agent 的生命周期，同样用自然语言：

- "创建一个叫 Researcher 的 Agent，技能是 web_search 和 memory"
- "克隆 Writer 这个 Agent，新名字叫 Editor"
- "停掉 Researcher 的当前任务"
- "重新加载 Writer，用新的配置"
- "删掉 Editor"

创建 Agent 时会自动验证技能是否存在、模型是否可用。修改配置前会自动备份。支持回滚——随时可以查看和恢复历史配置版本。

### 配置安全

每次配置写入都经过完整的验证流水线：解析 → 格式校验 → 内容校验（技能是否存在、模型是否可达） → 连接测试 → 备份旧文件 → 写入新文件。自动保留最近 5 个备份版本，随时可以回滚。

---

## 技能系统

### 内置技能

系统自带一组 Python 技能，覆盖文件操作、浏览器、搜索、邮件、记忆管理、系统管理等。这些是框架的一部分，开箱即用。

| 技能 | 能力 |
|------|------|
| file | 文件读写、搜索、执行命令（容器内） |
| browser | 浏览器自动化 |
| web_search | 网络搜索 |
| email | 给其他 Agent 发邮件（支持附件） |
| memory | 知识与记忆管理 |
| system_admin | 系统配置管理 |
| agent_admin | Agent 生命周期管理 |
| scheduler | 定时任务（支持周期性重复） |

### 扩展技能：写代码

开发者可以编写自定义 Python 技能，实现特定领域的能力。技能之间可以声明依赖，系统自动解析。需要代码开发。

### 扩展技能：写 Markdown（推荐）

不需要写代码。在工作空间的 `/home/SKILLS/` 目录下放一个 `skill.md` 文件，用 Markdown 写清楚操作步骤和流程，Agent 就能把它当作程序化知识来使用。定义 SOP、工作流、领域知识——纯文本就够。这是最方便的扩展方式。

---

## 桌面应用

原生桌面应用，基于 Tauri (Rust) + Vue 3 构建。

### Matrix 风格初始化

第一次启动时，你会看到一个全屏的 Matrix 主题引导：字符雨动画、打字机效果、逐步配置——用户名、工作目录、大脑模型、小脑模型。不是冷冰冰的 CLI 提示，是一种仪式感。

### 实时状态

Agent 的状态（思考中、工作中、等待输入、暂停……）通过 WebSocket 实时推送到桌面。你能看到 Agent 正在做什么，每一步的进展。不需要刷新，不需要轮询。

### 邮件式交互

给 Agent 发邮件，就像给同事写邮件一样。支持拖拽附件上传。对话以线程形式组织，回复自动归类到对应的会话。

### Prompt 预览

可以查看任何 Agent 的完整 System Prompt，不用执行任务。调试配置时很有用。

### Settings

图形化管理 LLM 配置（模型、API Key、端点）和邮件代理设置。不用碰配置文件。

### 中英双语

完整支持中文和英文界面切换。

---

## 邮件代理：用真实邮件和 Agent 交互

配置邮件代理后，你可以用 Gmail、Outlook、QQ 邮箱等真实邮件客户端和 Agent 交互：

- 给 Agent 发一封邮件，主题里写 `@AgentName`，Agent 就会收到并处理
- Agent 的回复会转发到你的邮箱，保持邮件线程
- Agent 向你提问时，你直接回复邮件就行
- 附件自动双向传递

内部的 Agent 邮件系统和外部的邮件世界就这样打通了。

---

## 快速开始

### 桌面应用（推荐）

```bash
cd agentmatrix-desktop
npm install
npm run tauri:dev
```

首次启动进入初始化向导，按提示完成即可。

### 作为 Python 库

```bash
pip install matrix-for-agents
```

---

## 项目结构

```
agentmatrix/
├── src/agentmatrix/          # 核心框架
│   ├── agents/               # BaseAgent + MicroAgent
│   ├── core/                 # 运行时、小脑、动作系统
│   ├── skills/               # 内置技能
│   └── services/             # ConfigService 等
├── agentmatrix-desktop/      # 原生桌面应用
│   ├── src/                  # Vue 3 前端
│   └── src-tauri/            # Tauri (Rust) 后端
├── server.py                 # FastAPI 服务
├── examples/                 # 示例
└── docs/                     # 文档
```

---

## 这不是什么

- 不是一个 wrapper。我们不封装 LLM API，我们重新定义了 Agent 的思考方式。
- 不是一个 no-code 工具。你写 Python、写 YAML、写自然语言。
- 不是一个 toy project。Docker 隔离、会话管理、持久化、实时同步——都是认真实现的。

---

## 文档

- [Agent 与 MicroAgent 设计](docs/architecture/agent-and-micro-agent-design-cn.md)
- [Matrix World 架构](docs/matrix-world-cn.md)
- [Think-With-Retry 模式](docs/architecture/think-with-retry-pattern-cn.md)
- [配置服务与管理技能](docs/core/config-service-and-admin-skill.md)

---

## 许可证

Apache License 2.0 — 详见 [LICENSE](LICENSE)

---

**版本**: v0.3.0 | **状态**: Alpha  
**仓库**: https://github.com/webdkt/agentmatrix
