# CDP Browser Skill — 架构文档

## 一句话概述

让 Agent 能**操控浏览器**且**接收浏览器事件**，实现用户/前端/Agent 三方协作的交互模式。

---

## 整体架构

```
                        ┌──────────────────────────────┐
                        │         BaseAgent             │
                        │   input_queue (asyncio.Queue) │
                        │   _main_loop → _route_signal  │
                        └──────────┬───────────────────┘
                                   │
                 ┌─────────────────┼─────────────────┐
                 │                 │                   │
          PostOffice        BrowserEventListener   (未来)
          投递 Email         投递 BrowserSignal      其他信号源
                                   │
                        ┌──────────┴───────────────────┐
                        │    进程级单例基础设施          │
                        │  ChromeManager / CDPClient   │
                        │  TabManager / BrowserEvent    │
                        │  Listener                    │
                        └──────────┬───────────────────┘
                                   │ WebSocket
                        ┌──────────┴───────────────────┐
                        │     Chrome (共享实例)          │
                        │  ┌─ Tab A (agent_x, sess_1)  │
                        │  ├─ Tab B (agent_x, sess_2)  │
                        │  └─ Tab C (agent_y, sess_3)  │
                        └──────────────────────────────┘
```

---

## 信号流

### 前端 → 后端（浏览器事件）

```
用户操作 / UI 交互
  → window.__bh_emit__(eventType, data)
  → console.log('__BH_EVENT__ ' + JSON.stringify(payload))
      payload 自动附带: type, url, title, agent_name, agent_session_id
  → CDP Runtime.consoleAPICalled
  → BrowserEventListener._on_console()
  → BrowserSignal(agent_name, agent_session_id, event_type, ...)
  → agent.input_queue.put_nowait(signal)
  → BaseAgent._main_loop → _route_signal → _resolve_session
```

### 后端 → 前端（Agent 指令）

```
Agent action (如 show_interface)
  → CDPClient.send("Runtime.evaluate", {expression: js}, session_id=...)
  → 浏览器执行 JS
  → window.__bh_on_event__(type, data)  // Interface 注册的回调
```

### 邮件（对照）

```
外部邮件 → PostOffice → agent.input_queue.put(email) → _main_loop → _route_signal
```

**关键统一点**: Email 和 BrowserSignal 都进同一个 `input_queue`，`_main_loop` 按 `isinstance` 判断类型后统一路由。

---

## 组件说明

### 进程级单例（`skill.py` 模块全局变量）

整个 Desktop 应用共享一个 Chrome 进程。不管有多少 Agent，底层基础设施只有一份。

| 组件 | 文件 | 职责 |
|------|------|------|
| ChromeManager | `chrome_manager.py` | 启动/管理 Chrome 进程（`--remote-debugging-port`） |
| CDPClient | `cdp_client.py` | WebSocket 客户端，发送 CDP 命令/接收 CDP 事件 |
| TabManager | `tab_manager.py` | 跟踪 tab 归属（哪个 agent 拥有哪个 tab） |
| BrowserEventListener | `browser_events.py` | 双向事件引擎：接收前端事件 → 路由到 agent；注入 bridge.js |

### Skill Mixin（per-Agent-per-MicroAgent 实例）

| 组件 | 文件 | 职责 |
|------|------|------|
| Cdp_browserSkillMixin | `skill.py` | Agent actions（open_browser, open_url 等） |
| _agent_current_tab | `skill.py` 模块变量 | 按 agent_name 索引的当前 tab 状态 |

### 前端组件

| 组件 | 路径 | 职责 |
|------|------|------|
| bridge.js | `interfaces/common/bridge.js` | 通信协议：`__bh_emit__` 发送事件，`__bh_on_event__` 接收事件，`__bh_agent_meta__` 存储 agent 元数据 |
| Interface | `interfaces/{name}/` | 可插拔的前端 UI 应用（如 browser_learning），通过 bridge 与后端通信 |
| ask_dialog.js | `interfaces/common/ask_dialog.js` | 用户问答对话框组件 |

---

## 多 Agent 共享模型

```
BrowserEventListener (进程单例)
  ├─ _agent_queues["agent_x"] → agent_x.input_queue  ← Tab A, B 的事件
  └─ _agent_queues["agent_y"] → agent_y.input_queue  ← Tab C 的事件
```

- **Tab 隔离**: 每个 tab 属于一个 agent（`TabInfo.agent_name`）
- **Session 关联**: 每个 tab 记录创建时的 Desktop session（`TabInfo.agent_session_id`）
- **事件路由**: 前端事件带 `agent_name`（优先）或通过 tab 归属查找
- **注册时机**: Agent 调用 `open_browser()` 时，将自己的 `input_queue` 注册到 BrowserEventListener

---

## Tab 的 Session 关联

每个 tab 关联两个 ID：

| 字段 | 含义 | 设置时机 |
|------|------|---------|
| `agent_name` | tab 归属的 agent | `TabManager.create_tab(agent_name, url)` |
| `agent_session_id` | tab 创建时的 Desktop session | `_set_tab_agent_meta(tab)` |
| `session_id` | CDP session（用于发送 CDP 命令） | `TabManager.create_tab()` |
| `target_id` | Chrome tab 标识 | `TabManager.create_tab()` |

`agent_session_id` 在前端通过 `window.__bh_agent_meta__` 持有，每次 `__bh_emit__` 自动附带。后端收到 BrowserSignal 后通过此 ID 路由到正确的 Desktop session。

---

## Agent Actions

通过 `Cdp_browserSkillMixin` 注册到 MicroAgent 的 action registry：

| Action | 说明 |
|--------|------|
| `open_browser()` | 启动/连接 Chrome，注册 agent input_queue，确保至少一个 tab |
| `open_url(url)` | 在新 tab 打开 URL，注入 bridge + 设置 agent 元数据 |
| `list_tabs()` | 列出当前 agent 的所有 tab |
| `close_tab(target_id)` | 关闭指定 tab |
| `switch_to_tab(target_id)` | 切换到指定 tab |
| `show_interface(name)` | 注入前端 Interface 到当前页面 |
| `ask_user_and_wait(question, options)` | 在浏览器弹出对话框向用户提问 |

---

## Interface 系统

Interface 是可插拔的前端 UI 应用，注入到网页中运行。

**目录结构**:
```
interfaces/
├── common/
│   ├── bridge.js       # 通信协议（始终注入）
│   ├── indicator.js    # 指示器组件（按需）
│   ├── dialog.js       # 对话框组件（按需）
│   ├── selector.js     # 选择框组件（按需）
│   └── ask_dialog.js   # 问答对话框（按需）
└── {name}/
    ├── manifest.json   # {name, description, requires: ["indicator", ...]}
    └── main.js         # 入口 JS
```

**加载流程**: `show_interface(name)` → `interfaces/__init__.py:load_interface()` → bridge.js + requires 组件 + main.js → 注入到页面。

---

## 关键设计决策

1. **进程级 Chrome 单例**: 所有 agent 共享一个 Chrome 进程，节省资源，避免端口冲突
2. **Tab 按 agent 隔离**: TabManager 追踪归属，agent 只能操作自己的 tab
3. **input_queue 统一入口**: 邮件和浏览器事件走同一个 queue，BaseAgent 不需要关心信号来源
4. **前端自动附带元数据**: bridge.js 注入后设置 `__bh_agent_meta__`，每次事件自动带 agent_name + agent_session_id
5. **MicroAgent 持久化**: MicroAgent 创建一次复用，browser skill 的 signal_queue 不在 cleanup 注销
6. **BrowserSignal fire-and-forget**: 无 signal_id，不需要投递确认

---

## 相关外部文件

| 文件 | 关系 |
|------|------|
| `core/message.py` — `Email` | 实现 Signal 协议，直接进入 input_queue |
| `desktop/signals.py` — `BrowserSignal` | 浏览器事件信号类型 |
| `desktop/base_agent.py` | `_main_loop` 统一消费 input_queue；`_resolve_session` 按 Email/BrowserSignal 分发 |
| `core/basic_agent.py` — `BasicAgent` | 提供 `_route_signal` 三段路由 |
| `core/signals.py` | Signal 协议定义 + TextSignal, ActionCompletedSignal |
