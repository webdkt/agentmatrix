# 08 — 外部生态与集成

## 协议支持

### Hermes Agent: MCP + ACP

Hermes 实现了两个重要的开放协议：

**MCP Server**（`mcp_serve.py`, ~31KB）：将 Hermes 的消息对话暴露为 MCP 工具，供其他 AI 客户端（Claude Desktop、Cursor 等）调用。提供的工具包括：
- `conversations_list` / `conversation_get`
- `messages_read` / `messages_send`
- `attachments_fetch`
- `events_poll` / `events_wait`
- `channels_list`
- `permissions_list_open` / `permissions_respond`

**ACP Adapter**（`acp_adapter/`）：Agent Client Protocol 服务器，支持 VS Code、Zed、JetBrains 编辑器集成。通过 `hermes acp` 或 `hermes-acp` 命令启动。

### AgentMatrix: 邮件协议

AgentMatrix 通过 `EmailProxyService` 支持标准邮件协议：
- IMAP（接收邮件，含 IDLE 实时推送）
- SMTP（发送邮件）
- 支持 Gmail、Outlook、QQ 邮箱

没有实现 MCP 或 ACP 协议。

## 消息平台覆盖

### Hermes Agent: 22 个平台适配器

`gateway/platforms/` 下的完整列表：

| 类别 | 平台 |
|------|------|
| 国际主流 | Telegram, Discord, Slack, WhatsApp, Signal |
| 企业协作 | Mattermost, WeCom, WeCom-callback |
| 中国生态 | 微信(Weixin), QQ Bot, 飞书(Feishu), 钉钉(DingTalk) |
| 去中心化 | Matrix |
| 通信协议 | Email, SMS, Webhook |
| 智能家居 | HomeAssistant |
| 即时通信 | BlueBubbles |
| API | api_server |

每个适配器需要实现 16 个集成点（适配器、枚举、工厂、认证、会话源、prompt 提示、toolset、cron 投递、发送消息工具、频道目录、状态显示、设置向导、电话脱敏、文档、测试）。

### AgentMatrix: 邮件通道

AgentMatrix 的外部通信仅限邮件，通过 IMAP/SMTP 与真实邮箱交互。主题标记规则（`@Agent` 入站、`#Agent` 出站）实现路由。

## 插件架构

### Hermes Agent: 插件系统

`plugins/` 目录提供结构化的插件系统：

- `memory/`：记忆提供者插件（含 Honcho 集成、本地记忆）
- `context_engine/`：上下文引擎插件

插件系统允许第三方开发者扩展 Agent 的核心能力（记忆、上下文管理），而不仅仅是添加新工具。

### AgentMatrix: SkillRegistry 搜索路径

AgentMatrix 通过 `SkillRegistry.add_search_path()` 支持第三方技能：

```python
SKILL_REGISTRY.add_search_path("/opt/company_skills")
SKILL_REGISTRY.add_search_path("./my_app/skills")
```

这是一种轻量级的扩展机制——将包含 Mixin 类的 Python 模块放到指定目录即可自动发现。但没有独立的"插件"概念，所有扩展都是技能。

## ML/AI 训练集成

### Hermes Agent: RL 训练环境

Hermes 拥有完整的强化学习训练集成（`environments/` + `tinker-atropos/`）：

- **Atropos 兼容训练环境**：`agent_loop.py`、`hermes_swe_env/`、`web_research_env.py`、`agentic_opd_env.py`
- **轨迹压缩器**（`trajectory_compressor.py`, ~63KB）：将对话轨迹压缩为 RL 训练数据
- **批量运行器**（`batch_runner.py`, ~55KB）：数据集的并行批处理
- **RL CLI**（`rl_cli.py`）：训练管理命令行
- **基准测试环境**：tblite、yc_bench

这让 Hermes 可以**自我改进**——通过 RL 训练优化工具调用策略。

### AgentMatrix: 无等价物

AgentMatrix 没有 ML 训练集成。Agent 的行为改进依赖于修改 YAML 配置和技能代码，没有数据驱动的自动改进机制。

## 依赖生态

### AgentMatrix 核心依赖

```
fastapi, uvicorn, websockets, pyyaml, python-dotenv, requests,
aiohttp, jinja2, docker, html2text, markdown-it-py, trafilatura,
DrissionPage, beautifulsoup4, marker-pdf, PyMuPDF, libtmux,
imap-tools, pydantic, aiosqlite
```

### Hermes Agent 核心依赖

```
openai, anthropic, python-dotenv, fire, httpx, rich, tenacity,
pyyaml, requests, jinja2, pydantic, prompt_toolkit,
exa-py, firecrawl-py, parallel-web, fal-client, edge-tts, PyJWT
```

可选依赖组（16 个）：modal, daytona, messaging, cron, slack, matrix, cli, tts-premium, voice, pty, honcho, mcp, homeassistant, sms, acp, mistral, bedrock, termux, dingtalk, feishu, web, rl, yc-bench

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **核心依赖数** | ~18 | ~16 |
| **可选依赖组** | 无 | 16 组 |
| **外部工具集成** | DrissionPage（浏览器）、imap-tools（邮件） | exa-py, firecrawl, parallel-web, fal-client 等 |
| **生态设计** | 尽量精简 | 模块化可选，按需安装 |

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **开放协议** | 无（仅邮件协议） | MCP + ACP（编辑器集成） |
| **消息平台** | 邮件（Gmail/Outlook） | 22 个平台 |
| **扩展机制** | SkillRegistry 搜索路径 | 插件系统 + 技能搜索路径 |
| **RL 训练** | 无 | 完整（Atropos/Tinker） |
| **可选依赖** | 无 | 16 组按需安装 |
| **优势** | 依赖精简、邮件协议成熟 | 生态广泛、可自我进化 |
| **劣势** | 生态封闭、无协议标准 | 依赖管理复杂度高 |
