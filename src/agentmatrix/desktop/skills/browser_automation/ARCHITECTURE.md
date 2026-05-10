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
  → 解析 target_id（从 session_id 反查）
  → 更新 current_tab（所有事件自动触发）
  → BrowserSignal(agent_name, agent_session_id, event_type, ...)
  → agent.input_queue.put_nowait(signal)
  → BaseAgent._main_loop → _route_signal → _resolve_session
```

**特殊事件处理**（不进 queue）：
- `tab_activated`：仅更新 current_tab，不投递到 agent
- `tab_assign_choice`：触发 orphan tab 分配流程

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
| Dom_explorerSkillMixin | `dom_explorer/skill.py` | DOM 探索 actions（eval_js, return_selector） |
| _agent_current_tab | `skill.py` 模块变量 | 按 agent_name 索引的当前 tab 状态 |
| _agent_last_session | `skill.py` 模块变量 | 按 agent_name 索引的上次 session_id，用于检测 session 切换 |
| _update_current_tab | `skill.py` 模块函数 | 回调函数，由 BrowserEventListener 调用以更新 current_tab |

### 前端组件

| 组件 | 路径 | 职责 |
|------|------|------|
| bridge.js | `interfaces/common/bridge.js` | 通信协议：`__bh_emit__`、`__bh_on_event__`、`__bh_agent_meta__`、`visibilitychange` → `tab_activated`、DOM 探索工具函数、`__bh_confirm`（支持 CSS + XPath） |
| agent_button.js | `interfaces/common/agent_button.js` | IIFE 开头 + 共享状态 + 4 个 helper 函数（_createBubble, _bindSubmit, _posBubbleRightOf, _makeDraggable） |
| agent_button_splash.js | `interfaces/common/agent_button_splash.js` | 发送过渡动画 |
| agent_button_speech.js | `interfaces/common/agent_button_speech.js` | Agent 说话气泡（CSS `::after` 实现尾巴） |
| agent_button_indicator.js | `interfaces/common/agent_button_indicator.js` | 指示器（十字准心） |
| agent_button_instruct.js | `interfaces/common/agent_button_instruct.js` | 给AI指示（居中输入框） |
| agent_button_range.js | `interfaces/common/agent_button_range.js` | 范围选择器 |
| agent_button_dialog.js | `interfaces/common/agent_button_dialog.js` | 提问对话框 |
| agent_button_init.js | `interfaces/common/agent_button_init.js` | DOM 构建 + 事件绑定 + IIFE 结尾 |
| agent_button.css | `interfaces/common/agent_button.css` | 所有前端 UI 组件样式 |

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
| `agent_name` | tab 归属的 agent | `TabManager.create_tab(agent_name, url)` 或 `_adopt_new_tab()` |
| `agent_session_id` | tab 创建时的 Desktop session | `_set_tab_agent_meta(tab)` 或从父 tab 继承 |
| `session_id` | CDP session（用于发送 CDP 命令） | `TabManager.create_tab()` 或 `adopt_tab()` |
| `target_id` | Chrome tab 标识 | Chrome 分配 |

`agent_session_id` 在前端通过 `window.__bh_agent_meta__` 持有，每次 `__bh_emit__` 自动附带。后端收到 BrowserSignal 后通过此 ID 路由到正确的 Desktop session。

---

## current_tab 自动维护

`_agent_current_tab` 按 `agent_name` 索引，记录每个 agent 当前正在交互的 tab。系统自动维护，无需 agent 手动管理。

### 更新时机

| 事件 | 动作 |
|------|------|
| 任何前端事件（indicator_result, chat_message 等） | 更新 current_tab 到事件来源 tab |
| `tab_activated`（visibilitychange visible） | 更新 current_tab（不进 queue） |
| `tab_closed` | 如果关的是 current_tab，自动切到剩余 tab |
| orphan tab 分配完成 | 更新 current_tab 到新分配的 tab |
| session 切换清理旧 tab | 如果 current_tab 被关，更新到剩余 tab |

### 前端可见性追踪

bridge.js 监听 `visibilitychange`，页面变为可见时 emit `tab_activated`。这处理了用户在浏览器中手动切换 tab 的场景（不经过我们的 UI）。

---

## Orphan Tab 追踪与分配

Orphan tab 是用户在浏览器中手动新建的 tab（无 `openerId`），不由页面链接触发。

### 追踪流程

```
Target.targetCreated（无 openerId）
  → BrowserEventListener._on_target_created()
  → 加入 _orphan_tabs 集合（等待导航）

Target.targetInfoChanged（orphan tab URL 变为 http/https）
  → BrowserEventListener._on_target_info_changed()
  → 从 _orphan_tabs 移除
  → 触发 _assign_orphan_tab()
```

### 分配策略

| 场景 | 行为 |
|------|------|
| 只有 1 个活跃 agent | 自动分配（`_finalize_orphan_assignment`） |
| 多个活跃 agent | 注入选择对话框（`_show_orphan_assign_dialog`），用户选择后分配 |
| 用户选择"不分配" | tab 保持无主状态 |

分配完成后：adopt tab → 注入 bridge + agent_button → 设置 meta → 更新 current_tab → 发送 `tab_opened` 信号。

---

## Session 切换自动清理

基于设计前提：**每个 Agent 的工作在一个 session 内持续完成，不会并行多个 session**。

### 清理机制

在 `_ensure_browser()` 中检测 session 切换：

```
_ensure_browser()
  → 获取当前 agent 的 session_id（current_sid）
  → 与 _agent_last_session[agent_name] 比较
  → 如果不同（包括首次连接/后端重启）
    → _cleanup_old_session_tabs(agent_name, current_sid)
    → 关闭所有 agent_session_id != current_sid 的 tab
    → 更新 current_tab
    → 记录 _agent_last_session
```

### 边界情况

| 场景 | 行为 |
|------|------|
| Agent 首次连接（无旧 tab） | 触发清理，但无 tab 可关（no-op） |
| Agent 首次连接（Chrome 有旧 tab） | 关闭旧 tab |
| 同一 session 内多次 `_ensure_browser()` | session_id 相同，跳过 |
| 后端重启后重连 | `current_sid != last_sid`（last_sid 为空），清理 Chrome 中残留 tab |

---

## Agent Actions

### CDP Browser Actions（`Cdp_browserSkillMixin`）

| Action | 说明 |
|--------|------|
| `open_browser()` | 启动/连接 Chrome，注册 agent input_queue，确保至少一个 tab |
| `open_url(url)` | 在当前 tab（复用）或新 tab 打开 URL，注入 bridge + 设置 agent 元数据 |
| `list_tabs()` | 列出当前 agent 的所有 tab |
| `close_tab(target_id)` | 关闭指定 tab |
| `switch_to_tab(target_id)` | 切换到指定 tab |
| `show_interface(name)` | 注入前端 Interface 到当前页面 |
| `ask_user_and_wait(question, options)` | 在浏览器弹出对话框向用户提问 |
| `find_selector(instruction_text, tab_id)` | 启动 MicroAgent 探索 DOM，找到目标元素的稳定 selector |
| `find_unique_selector_by_xy(additional_info, tab_id, x, y)` | 启动 MicroAgent 从坐标出发，找到用户指向元素的唯一 selector |
| `confirm_element(selector, tab_id)` | 高亮元素并弹出确认对话框（支持 CSS selector 和 XPath） |

### DOM Explorer Actions（`Dom_explorerSkillMixin`）

供 MicroAgent 在 DOM 探索过程中使用：

| Action | 说明 |
|--------|------|
| `eval_js(code, tab_id)` | 在浏览器页面中执行 JavaScript 并返回结果 |
| `return_selector(selector, additional_info)` | 返回找到的稳定定位表达式（CSS selector 或 XPath），探索结束 |

---

## Interface 系统

Interface 是可插拔的前端 UI 应用，注入到网页中运行。

**目录结构**:
```
interfaces/
├── common/
│   ├── bridge.js              # 通信协议 + DOM 探索工具 + visibilitychange
│   ├── agent_button.js        # IIFE 开头 + 共享状态 + helpers
│   ├── agent_button_splash.js # 发送过渡动画
│   ├── agent_button_speech.js # 说话气泡
│   ├── agent_button_indicator.js  # 指示器
│   ├── agent_button_instruct.js   # 给AI指示
│   ├── agent_button_range.js      # 范围选择器
│   ├── agent_button_dialog.js     # 提问对话框
│   ├── agent_button_init.js       # IIFE 结尾
│   ├── agent_button.css           # 所有前端 UI 样式
│   └── ask_dialog.js         # 问答对话框
└── {name}/
    ├── manifest.json   # {name, description, requires: ["indicator", ...]}
    └── main.js         # 入口 JS
```

**加载流程**: `show_interface(name)` → `interfaces/__init__.py:load_interface()` → bridge.js + requires 组件 + main.js → 注入到页面。

**agent_button 模块结构**: 所有 agent_button_*.js 在同一 IIFE 闭包内拼接，共享变量。bridge.js 始终注入，agent_button.js 按需注入。

---

## 关键设计决策

1. **进程级 Chrome 单例**: 所有 agent 共享一个 Chrome 进程，节省资源，避免端口冲突
2. **Tab 按 agent 隔离**: TabManager 追踪归属，agent 只能操作自己的 tab
3. **input_queue 统一入口**: 邮件和浏览器事件走同一个 queue，BaseAgent 不需要关心信号来源
4. **前端自动附带元数据**: bridge.js 注入后设置 `__bh_agent_meta__`，每次事件自动带 agent_name + agent_session_id
5. **MicroAgent 持久化**: MicroAgent 创建一次复用，browser skill 的 signal_queue 不在 cleanup 注销
6. **BrowserSignal fire-and-forget**: 无 signal_id，不需要投递确认
7. **current_tab 自动维护**: 所有前端事件和 visibilitychange 自动更新，agent 无需手动管理
8. **Orphan tab 自动分配**: 用户手动新建的 tab 在导航到真实页面时自动分配（单 agent）或弹出选择框（多 agent）
9. **Session 切换清理**: 新 session 启动时自动关闭旧 session 的 tab，防止 tab 累积

---

## 相关外部文件

| 文件 | 关系 |
|------|------|
| `core/message.py` — `Email` | 实现 Signal 协议，直接进入 input_queue |
| `desktop/signals.py` — `BrowserSignal` | 浏览器事件信号类型 |
| `desktop/base_agent.py` | `_main_loop` 统一消费 input_queue；`_resolve_session` 按 Email/BrowserSignal 分发 |
| `core/basic_agent.py` — `BasicAgent` | 提供 `_route_signal` 三段路由 |
| `core/signals.py` | Signal 协议定义 + TextSignal, ActionCompletedSignal |
| `desktop/browser_collab_agent.py` — `BrowserCollabAgent` | 支持浏览器内嵌聊天的 Agent，自动转发状态和事件到浏览器前端 |
