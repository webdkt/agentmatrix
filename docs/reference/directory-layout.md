# 项目目录结构

本文档说明项目顶层及各关键目录的职责，帮助开发者和贡献者快速定位代码。

---

## 顶层目录

```
agentmatrix/
├── src/agentmatrix/           # Core 框架 + Desktop 运行时（Python 包）
├── agentmatrix-desktop/       # 桌面应用（Tauri + Vue 3）
├── server_handlers/           # FastAPI 后端服务
├── tutorial/cli-agent/        # CLI 最小示例
├── docs/                      # 文档
├── examples/                  # 示例（待补充）
├── matrix-template/           # MatrixWorld 模板目录
├── scripts/                   # 构建脚本
├── SKILLS/                    # 项目级 Markdown Skill 目录
├── design-preview/            # UI 设计预览原型
└── 根目录配置文件（pyproject.toml、server.py 等）
```

---

## `src/agentmatrix/` — Python 包

这是 `agentmatrix-core` 的源代码目录，安装后可通过 `import agentmatrix` 使用。

### `src/agentmatrix/core/` — Core 执行引擎

纯执行层，不包含任何 I/O、文件系统或网络逻辑。所有外部交互通过 `AgentShell` 协议进行。

| 模块 | 职责 |
|------|------|
| `micro_agent.py` | MicroAgent 执行引擎，think-negotiate-act 循环 |
| `basic_agent.py` | BasicAgent，信号路由 + Session 管理 + MicroAgent 持久化的参考实现 |
| `agent_shell.py` | AgentShell Protocol 接口定义 |
| `cerebellum.py` | Cerebellum，意图解析与参数协商 |
| `action.py` | Action 注册表、装饰器和执行逻辑 |
| `signals.py` | Signal 类型定义与事件模型 |
| `session_store.py` | SessionStore 持久化接口 |
| `state_manager.py` | 暂停、恢复、停止的状态管理 |
| `message.py` | Email 数据模型 |
| `events.py` | AgentEvent 事件模型 |
| `backends/` | LLM 后端客户端（OpenAI 兼容接口） |
| `skills/` | Core 层 Skill 基础（注册表、基类） |
| `utils/` | 工具函数（token 估算、解析、MicroAgent 辅助） |

### `src/agentmatrix/desktop/` — Desktop 运行时

在 Core 层之上构建的完整运行时，包含邮件系统、会话管理、容器隔离和内置技能。

| 模块 | 职责 |
|------|------|
| `runtime.py` | AgentMatrix 总控，初始化、Agent 加载、生命周期 |
| `base_agent.py` | BaseAgent，Desktop 场景下的 Agent 实现，状态机、信号路由 |
| `post_office.py` | PostOffice 邮件总线，注册、分发、持久化 |
| `session_manager.py` | Session 管理与查询 |
| `loader.py` | Agent 配置文件加载与验证 |
| `config.py` | 运行时配置管理 |
| `config_schemas.py` | 配置数据模型与校验 |
| `paths.py` | 路径管理 |
| `container/` | 容器运行时适配器（Docker、Podman、本地模式） |
| `db/` | SQLite 数据库封装（邮件、定时任务存储） |
| `services/` | 运行时服务（LLM 服务、Agent 服务、邮件代理配置、代理服务） |
| `skills/` | 内置 Skill 实现（见下方详表） |
| `browser/` | 浏览器适配器（Bing、Google、DrissionPage） |
| `utils/` | 运行时工具（备份等） |

### `src/agentmatrix/desktop/skills/` — 内置技能

| 目录 | 技能 | 能力 |
|------|------|------|
| `base/` | base | 获取当前日期时间 |
| `file_skill.py` | file | 文件读写、搜索、目录操作 |
| `email/` | email | 向其他 Agent 发送邮件（含附件） |
| `browser_automation/` | browser | 浏览器自动化（CDP、标签页管理） |
| `browser_control/` | browser_control | 浏览器控制（高阶封装） |
| `new_web_search/` | web_search | 网页搜索与页面内容提取 |
| `deep_researcher/` | deep_researcher | 深度研究（多轮搜索与综合） |
| `memory/` | memory | 知识与记忆管理（读写、检索） |
| `vision/` | vision | 图像分析与理解 |
| `markdown/` | markdown | Markdown 解析与处理 |
| `scheduler/` | scheduler | 定时任务与周期性任务 |
| `system_admin/` | system_admin | 系统配置管理 |
| `agent_admin/` | agent_admin | Agent 生命周期管理 |
| `sub_agent/` | sub_agent | 子 Agent 调用 |
| `basic_planning/` | basic_planning | 基础任务规划 |
| `glm_image/` | glm_image | 图像生成 |
| `git-workflow/` | git-workflow | Git 工作流（Markdown Skill） |

---

## `agentmatrix-desktop/` — 桌面应用

Tauri 应用，Rust 后端 + Vue 3 前端。

### Rust 后端 (`src-tauri/src/`)

| 文件/目录 | 职责 |
|-----------|------|
| `main.rs` | 应用入口、窗口管理、菜单、系统托盘 |
| `config.rs` | Tauri 配置与常量 |
| `commands/` | Tauri 命令（前后端通信接口） |
| `ws/` | WebSocket 客户端（连接后端服务） |

### Vue 3 前端 (`src/`)

| 目录 | 职责 |
|------|------|
| `api/` | API 封装（HTTP 请求） |
| `components/` | Vue 组件（按功能分组：email、session、agent、settings、wizard 等） |
| `composables/` | 组合式函数 |
| `stores/` | Pinia 状态管理（agent、session、email、ui） |
| `i18n/` | 国际化（中英文） |
| `styles/` | 全局样式 |
| `utils/` | 前端工具函数 |

---

## `server_handlers/` — FastAPI 后端服务

| 文件/目录 | 职责 |
|-----------|------|
| `app_factory.py` | FastAPI 应用工厂，中间件、路由注册 |
| `lifecycle.py` | 应用生命周期（启动、关闭、资源清理） |
| `state.py` | 共享状态（路径、运行时对象） |
| `models.py` | Pydantic 数据模型 |
| `utils.py` | 通用工具函数 |
| `routes/` | API 路由模块（agents、sessions、skills、config、websocket 等） |

---

## `tutorial/cli-agent/` — CLI 最小示例

| 文件 | 职责 |
|------|------|
| `main.py` | 入口 + Textual TUI / 简单模式 |
| `cli_shell.py` | AgentShell 协议实现 |
| `cli_config.py` | 配置管理 |
| `cli_session.py` | 内存 SessionStore |
| `skills/` | 基础 Skill（file、shell、base） |

这是理解 AgentShell 协议和 Core 引擎用法的最佳起点。
