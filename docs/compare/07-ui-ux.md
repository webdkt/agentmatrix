# 07 — 用户界面与体验

## 桌面应用 / Web 仪表盘

### AgentMatrix: Tauri + Vue 3 桌面应用

`agentmatrix-desktop/` 提供原生桌面应用：

**技术栈**：Tauri（Rust 后端）+ Vue 3（前端）+ Pinia（状态管理）

**核心功能**：
- 实时 Agent 状态监控（通过 WebSocket）
- 邮件式交互界面（支持拖拽附件）
- System Prompt 预览（调试用）
- LLM 和邮件代理配置 GUI
- Matrix 主题首次运行向导（字符雨动画 + 打字机效果）
- 双语支持（中文/英文）

**前端架构**：
- 9 个 Pinia Store（agent、session、email、config、settings、ui、matrix、backend、websocket）
- 组件按领域组织（email/、session/、agent/、dialog/、settings/、wizard/）

**关键特性**：原生应用体验（系统托盘、原生窗口、离线可用），对"数字办公室"场景非常自然——用户就像在使用邮件客户端。

### Hermes Agent: React Web 仪表盘

`web/` 目录提供 React + TypeScript 仪表盘：

**核心页面**：
- Status：系统状态概览
- Sessions：会话历史浏览
- Analytics：使用分析和图表
- Logs：日志查看器
- Cron：定时任务管理
- Skills：技能浏览器
- Config：配置编辑器
- Env：API 密钥/凭证管理

由 `hermes_cli/web_server.py`（~80KB，FastAPI + uvicorn）提供后端。

**关键特性**：Web 访问（任何浏览器都能用）、i18n 支持、React Router 路由。

## CLI 体验

### AgentMatrix

AgentMatrix 有基础的 CLI 入口（`main.py` 启动 uvicorn），但 CLI 不是主要交互方式。用户主要通过桌面应用或 REST API 交互。

### Hermes Agent: 成熟的 TUI CLI

Hermes 的 CLI（`hermes_cli/main.py`, ~259KB）是核心交互方式：

- **TUI 界面**：基于 `prompt_toolkit` 的交互式终端
- **皮肤系统**（`skin_engine.py`, ~40KB）：数据驱动的视觉主题（default、ares、mono、slate + 用户自定义 YAML）
- **自动补全**：命令、技能、模型名称的智能补全
- **斜杠命令注册表**：统一的 `COMMAND_REGISTRY` 同时服务于 CLI、gateway、Telegram、Slack
- **Doctor 诊断工具**（~52KB）：环境健康检查
- **Skills Hub**（~47KB）：技能浏览、搜索、安装
- **Profile 管理**：多实例切换

## 实时可观测性

### AgentMatrix: WebSocket AgentEvent 流

AgentMatrix 通过 `AgentEvent` 数据类（`src/agentmatrix/core/events.py`）实现实时可观测性：

- Agent 的每个思考步骤、action 调用、邮件收发都产生事件
- 事件通过异步回调推送
- FastAPI WebSocket（`/ws`）将事件流式传输到桌面应用
- 用户可以实时看到 Agent 的推理过程和工作进度

### Hermes Agent: Web 仪表盘 + 对话历史

Hermes 通过 Web 仪表盘提供会话浏览和分析：
- Sessions 页面显示所有对话历史
- Analytics 页面展示使用量和成本图表
- 实时更新依赖轮询或 SSE（`stream_consumer.py`）

## 多 Agent 可视化

### AgentMatrix

邮件线程是天然的多 Agent 可视化方式。桌面应用的邮件列表界面可以直接展示：
- 哪些 Agent 在互相通信
- 邮件线程的完整回复链
- 附件和任务上下文

### Hermes Agent

Hermes 是单 Agent 架构，不存在多 Agent 可视化需求。委派的子任务在同一对话历史中显示为 tool call 和 tool result。

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **主要 UI** | Tauri/Vue 3 桌面应用 | React Web 仪表盘 + TUI CLI |
| **访问方式** | 需安装桌面应用 | 浏览器 + 终端 |
| **CLI 成熟度** | 基础 | 非常成熟（TUI/skins/补全/诊断） |
| **实时性** | WebSocket 事件流 | 轮询/SSE |
| **多 Agent 可视化** | 邮件线程天然支持 | 不适用（单 Agent） |
| **优势** | 原生体验、实时事件流 | Web 无安装、CLI 功能强大 |
| **劣势** | 需安装客户端、CLI 简陋 | 非原生体验、实时性依赖网络 |
