# Session Event System

## 概述

session_events 是 agent session 的 append-only 事件日志。它记录一个 agent session 生命周期中的所有活动：收到邮件、思考、执行 action、会话压缩、用户中断等。

**与 history.json 的关系**：两者是独立的。history.json 是 LLM 上下文（有压缩机制）；session_events 是永久不可变的审计日志，也用于前端 UI 展示。

## 数据库

### 表结构

```sql
CREATE TABLE session_events (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,          -- agent name
    session_id TEXT NOT NULL,     -- agent session id
    event_type TEXT NOT NULL,     -- 分类：email / think / action / session
    event_name TEXT NOT NULL,     -- 具体事件名
    event_detail TEXT,            -- JSON 字符串，可为 null
    timestamp TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
)

CREATE INDEX idx_session_events_lookup
ON session_events(owner, session_id, timestamp)
```

### 查询

- `get_session_events(owner, session_id, limit, offset)` — 按时间正序获取事件
- `get_session_events_by_type(owner, session_id, event_type, limit, offset)` — 按 event_type 过滤

### API

```
GET /api/agents/{agent_name}/sessions/{session_id}/events?limit=200&offset=0
→ { "events": [...] }
```

## 事件分类

### event_type = "email"

| event_name | event_detail | 写入位置 |
|---|---|---|
| `received` | `{email_ids, sender, recipient, subject, body_preview(200字符), has_more}` | micro_agent.py `_inject_signal` |
| `sent` | `{email_id, subject, body_preview, sender, recipient}` | email/skill.py `send_internal_mail` |

### event_type = "think"

| event_name | event_detail | 写入位置 |
|---|---|---|
| `brain` | `{step_count, raw_reply(2000字符)}` | micro_agent.py `_run_loop` |

### event_type = "action"

| event_name | event_detail | 写入位置 |
|---|---|---|
| `detected` | `{actions: [...], step_count}` | micro_agent.py `_run_loop` |
| `started` | `{action_name, step_count}` | micro_agent.py `_execute_actions` |
| `completed` | `{action_name, action_label, result_preview(500字符), status}` | micro_agent.py `_execute_actions` |
| `error` | `{action_name, error_message(500字符)}` | micro_agent.py `_execute_actions` |

### event_type = "session"

| event_name | event_detail | 写入位置 |
|---|---|---|
| `activated` | `{task_id, original_sender}` | base.py `_activate_session` |
| `deactivated` | `{task_id}` | base.py `_deactivate_session` |
| `user_interrupt` | `{task_id}` | base.py interrupt handler |
| `message_auto_compress` | `{step_count, working_notes_preview(500字符)}` | micro_agent.py `_maybe_compress_messages` |

## 后端写入机制

### 两个 helper

**MicroAgent._log_event()** (`micro_agent.py`)

```python
def _log_event(self, event_type, event_name, event_detail=None):
    # DB 写入（asyncio.to_thread，不阻塞主流程）
    # WebSocket 广播 SESSION_EVENT
```

**BaseAgent._log_session_event()** (`base.py`)

```python
def _log_session_event(self, session_id, event_type, event_name, event_detail=None):
    # 同上：DB 写入 + WebSocket 广播
```

两者模式相同：`asyncio.create_task(asyncio.to_thread(db.insert, ...))` + `_broadcast_message_callback`。

### WebSocket 广播格式

```json
{
  "type": "SESSION_EVENT",
  "agent_name": "AgentName",
  "session_id": "agent_session_id",
  "data": {
    "event_type": "email",
    "event_name": "received",
    "event_detail": { "email_ids": [...], "sender": "User", "recipient": "AgentName", "subject": "...", "body_preview": "...", "has_more": true },
    "timestamp": "2026-04-20T12:00:00"
  }
}
```

- 广播给所有 WebSocket 客户端
- 前端负责过滤（通过 agent_name + session_id → user_session_id 映射）

## 前端数据流

```
WebSocket message (type=SESSION_EVENT)
  → websocketStore.handle_message()
    → websocketStore.handleSessionEvent(message)
      → sessionStore.agentSessionLookup(agent_name, agent_session_id)
        → 有映射 → 按 event_type 分发
        → 无映射 → sessionStore.fetchSessions()（Agent 发起的新 session）
```

### agent → user session 映射

Session Store 维护本地映射表：

```
state: agentToUserSessionMap = { "agentName:agentSessionId": "userSessionId" }
```

- `loadSessions()` 完成后调用 `buildAgentSessionMap()` 构建映射
- `agentSessionLookup(agentName, agentSessionId)` 返回 user_session_id 或 null
- 映射来源：API 返回的 session 对象中的 `agent_name` 和 `agent_session_id` 字段

### event_type 分发（当前实现）

#### email.received / email.sent

```
isCurrentSession?
  → true:
      1. sessionStore.selectSession(currentSession, force=true)  // 触发 EmailList watch 重新加载
      2. 延迟 3s → markSessionRead + sessionAPI.markAsRead
  → false:
      1. sessionStore.markSessionUnread(userSessionId)
      2. uiStore.emailToast = { show: true, emailData: {...} }  // toast 通知
```

#### think / action / session

ChatHistory 通过 `sessionStore.lastSessionEvent` watch 增量 append 所有类型的事件。

前端可通过 `GET /api/agents/{agent_name}/sessions/{session_id}/events` 拉取历史事件。

## AGENT_STATUS_UPDATE vs SESSION_EVENT

两个独立的 WebSocket 机制，职责不同：

| | AGENT_STATUS_UPDATE | SESSION_EVENT |
|---|---|---|
| 用途 | Agent 级状态变化 | Session 级事件日志 |
| 触发 | `update_status()` | `_log_event()` / `_log_session_event()` |
| 数据 | status, current_task_id, pending_question | event_type, event_name, event_detail |
| 消费者 | Agent Status Panel, Agent Store | ChatHistory, EmailList, Session List |
| 持久化 | 否（纯实时状态） | 是（session_events 表） |

### update_status 清理

`update_status()` 已简化为纯状态变更，不再携带消息内容：

```python
# base.py
def update_status(self, new_status=None):
    # 只改 _status + _status_since，广播 AGENT_STATUS_UPDATE

# micro_agent.py — 同样清理
def update_status(self, new_status=None):
    # 同上
```

之前通过 `update_status(new_message=...)` 传递的 think 内容、action 结果等，现在改用 `session_events` 记录。

## 清理：user_session_updated

`user_session_updated` 已从前端移除：

- **websocket.js**: 移除 `handleSessionUpdate`、`onSessionUpdate`、`sessionUpdateCallbacks`
- **App.vue**: 移除 `onSessionUpdate` callback 注册
- **session.js**: `updateSessionFromEvent()` 保留但无调用方（后续重构可删除）

后端 `user_session_update_callback`（server.py）保留了 DB 操作，但前端不再消费其 WebSocket 推送。

## 后续重构方向

### ChatHistory 重构 — 已完成

ChatHistory 已改为基于 session_events 驱动：
- 数据源：`sessionAPI.getSessionEvents(agentName, agentSessionId)` 加载历史 + `sessionStore.lastSessionEvent` 增量 append
- 渲染分类（renderType）：
  - `bubble-user`: email.received + sender == User → 右侧绿色气泡
  - `bubble-agent`: email.sent + recipient == User → 左侧 parchment 气泡
  - `agent-comm`: Agent 间邮件通信 → 淡色居中事件说明
  - `pill`: action 事件 → 状态胶囊
  - `thought`: think.brain → Agent 自言自语（虚线边框、斜体）
  - `system`: session.* → 极淡居中系统提示
- 底部 agent status indicator 保留，由 AGENT_STATUS_UPDATE 驱动
- EmailReply 组件保留，发送后通过 SESSION_EVENT WebSocket 增量更新 timeline

### EmailList 重构

- 从监听 `user_session_updated` 改为监听 `SESSION_EVENT` 中的 `email.*` 事件
- 用 session_events 的 email 事件增量更新列表
- 与 ChatHistory 共享同一个事件流，按 event_type 过滤

### SessionList 重构

- `SESSION_EVENT` 到达时，通过 `agentSessionLookup` 确定影响的 user_session
- 更新 unread 状态、last_email_time、subject 等
- 不再依赖 `user_session_updated` 推送
