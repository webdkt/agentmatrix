# 每个 Session 显示 Agent 状态 - 实现指南

## 概述

**日期**: 2026-03-15
**状态**: ✅ 后端完成，前端待实现

每个会话底部显示该会话涉及的所有 Agent 的状态。

---

## 核心逻辑

### 1. 状态显示逻辑

```javascript
// 获取 Agent 的状态显示文案
getAgentStatusDisplay(agentName, sessionId) {
    const agentInfo = systemStatus.agents[agentName];

    // 情况 1: Agent 空闲
    if (agentInfo.status === 'IDLE') {
        return { text: '空闲', status: 'idle' };
    }

    // 情况 2: Agent 正在为当前会话工作
    if (agentInfo.current_user_session_id === sessionId) {
        const statusMap = {
            'THINKING': '正在思考...',
            'WORKING': '正在工作...',
            'WAITING_FOR_USER': '等待你的回答'
        };
        return {
            text: statusMap[agentInfo.status],
            status: agentInfo.status.toLowerCase()
        };
    }

    // 情况 3: Agent 正在为其他会话工作
    const statusMap = {
        'THINKING': '正在为其他会话思考',
        'WORKING': '正在为其他会话工作',
        'WAITING_FOR_USER': '正在为其他会话等待用户回答'
    };
    return {
        text: statusMap[agentInfo.status],
        status: 'busy-on-other'
    };
}
```

### 2. ask_user 对话框显示逻辑

```javascript
// 对话框存储在 Map 中，每个 session 一个
askUserDialogs: {
    "session_123": {
        show: true,
        agent_name: "Mark",
        question: "...",
        answer: "",
        submitting: false,
        error: null
    }
}

// 只在对应的 session 显示对话框
<div x-show="askUserDialogs[currentSession?.session_id]?.show">
    <!-- 对话框内容 -->
</div>
```

---

## 数据结构

### Session 数据

```javascript
{
    session_id: "xxx",
    subject: "任务：写代码",
    last_email_time: "2026-03-15T20:00:00",
    participants: ["Mark", "Planner"]  // 🆕 涉及的 Agent 列表
}
```

### WebSocket 广播数据

```javascript
systemStatus: {
    timestamp: "2026-03-15T20:00:00",
    agents: {
        "Mark": {
            status: "THINKING",
            pending_question: null,
            current_session_id: "agent_session_123",
            current_task_id: "task_456",
            current_user_session_id: "user_session_789",  // 🆕 关键字段
            status_history: [
                { message: "正在初始化...", timestamp: "..." },
                { message: "正在分析任务...", timestamp: "..." }
            ]
        },
        "Planner": {
            status: "IDLE",
            current_user_session_id: null
        }
    }
}
```

---

## UI 实现示例

### 1. Session 列表项（显示每个 session 的 Agent 状态）

```html
<!-- Session 列表 -->
<template x-for="session in sessions" :key="session.session_id">
    <div @click="selectSession(session)">
        <h3 x-text="session.subject"></h3>

        <!-- 🆕 显示该 session 涉及的 Agent 状态 -->
        <template x-for="agentName in session.participants" :key="agentName">
            <div class="agent-status-badge"
                 :class="getAgentStatusDisplay(agentName, session.session_id).status">
                <span x-text="agentName"></span>:
                <span x-text="getAgentStatusDisplay(agentName, session.session_id).text"></span>
            </div>
        </template>
    </div>
</template>
```

### 2. 当前会话底部（显示 Agent 状态面板）

```html
<!-- 当前会话的 Agent 状态面板 -->
<div x-show="currentSession">
    <!-- 遍历当前会话涉及的所有 Agent -->
    <template x-for="agentName in currentSession.participants" :key="agentName">
        <div class="agent-status-panel">
            <!-- Agent 名称和状态 -->
            <div class="flex items-center gap-2">
                <div class="status-dot"
                     :class="getAgentStatusDisplay(agentName, currentSession.session_id).status">
                </div>
                <span class="font-semibold" x-text="agentName"></span>
                <span x-text="getAgentStatusDisplay(agentName, currentSession.session_id).text"></span>
            </div>

            <!-- 状态历史（如果 Agent 正在为当前会话工作） -->
            <div x-show="systemStatus.agents[agentName]?.current_user_session_id === currentSession.session_id">
                <template x-for="(statusItem, index) in getAgentStatusHistory(agentName)" :key="index">
                    <div class="status-history-item">
                        <span x-text="formatStatusTime(statusItem.timestamp)"></span>
                        <span x-text="statusItem.message"></span>
                    </div>
                </template>
            </div>
        </div>
    </template>
</div>
```

### 3. ask_user 对话框（在对应 session 显示）

```html
<!-- ask_user 对话框（🆕 在对应 session 显示） -->
<div x-show="currentSession && askUserDialogs[currentSession.session_id]?.show"
     x-transition:enter="transition ease-out duration-300"
     x-transition:enter-start="opacity-0 translate-y-4"
     x-transition:enter-end="opacity-100 translate-y-0">

    <div class="ask-user-dialog">
        <h4>
            <span x-text="askUserDialogs[currentSession.session_id]?.agent_name"></span>
            需要你的帮助
        </h4>

        <p x-text="askUserDialogs[currentSession.session_id]?.question"></p>

        <textarea x-model="askUserDialogs[currentSession.session_id]?.answer"
                  placeholder="输入你的回答..."></textarea>

        <div class="flex gap-2">
            <button @click="submitUserAnswer(currentSession.session_id)"
                    :disabled="askUserDialogs[currentSession.session_id]?.submitting">
                提交回答
            </button>
            <button @click="closeAskUserDialog(currentSession.session_id)">
                关闭
            </button>
        </div>

        <div x-show="askUserDialogs[currentSession.session_id]?.error"
             class="error-message"
             x-text="askUserDialogs[currentSession.session_id]?.error">
        </div>
    </div>
</div>
```

---

## 状态样式

```css
/* Agent 状态徽章 */
.agent-status-badge {
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}

.agent-status-badge.idle {
    background-color: #e5e7eb;
    color: #374151;
}

.agent-status-badge.thinking {
    background-color: #dbeafe;
    color: #1e40af;
    animation: pulse 2s infinite;
}

.agent-status-badge.working {
    background-color: #fef3c7;
    color: #92400e;
    animation: pulse 2s infinite;
}

.agent-status-badge.waiting_for_user {
    background-color: #fce7f3;
    color: #9f1239;
    animation: pulse 2s infinite;
}

.agent-status-badge.busy-on-other {
    background-color: #f3f4f6;
    color: #6b7280;
    font-style: italic;
}

/* 状态面板 */
.agent-status-panel {
    padding: 12px;
    border-radius: 8px;
    background-color: #f9fafb;
    border: 1px solid #e5e7eb;
    margin-top: 12px;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
}

.status-dot.idle {
    background-color: #9ca3af;
}

.status-dot.thinking,
.status-dot.working,
.status-dot.waiting_for_user {
    background-color: #3b82f6;
    animation: ping 1s cubic-bezier(0, 0, 0.2, 1) infinite;
}

@keyframes ping {
    75%, 100% {
        transform: scale(2);
        opacity: 0;
    }
}
```

---

## 场景示例

### 场景 1: Agent 正在为当前会话工作

```javascript
// Session 1 (当前查看)
{
    session_id: "session_789",
    participants: ["Mark"]
}

// WebSocket 广播
systemStatus.agents.Mark = {
    status: "WORKING",
    current_user_session_id: "session_789"  // 正在为当前会话工作
}

// 显示
// Mark: 正在工作... ✓ (蓝色脉冲)
//   • 正在初始化...
//   • 正在分析任务...
```

### 场景 2: Agent 正在为其他会话工作

```javascript
// Session 1 (当前查看)
{
    session_id: "session_789",
    participants: ["Mark"]
}

// WebSocket 广播
systemStatus.agents.Mark = {
    status: "WORKING",
    current_user_session_id: "session_456"  // 正在为其他会话工作
}

// 显示
// Mark: 正在为其他会话工作 (灰色斜体)
```

### 场景 3: Agent 等待当前会话用户回答

```javascript
// Session 1 (当前查看)
{
    session_id: "session_789",
    participants: ["Mark"]
}

// WebSocket 广播
systemStatus.agents.Mark = {
    status: "WAITING_FOR_USER",
    current_user_session_id: "session_789",
    pending_question: "请确认预算范围"
}

// 显示
// ✓ ask_user 对话框在 session_789 底部显示
// Mark: 等待你的回答 (粉色脉冲)
```

### 场景 4: Agent 等待其他会话用户回答

```javascript
// Session 1 (当前查看)
{
    session_id: "session_789",
    participants: ["Mark"]
}

// WebSocket 广播
systemStatus.agents.Mark = {
    status: "WAITING_FOR_USER",
    current_user_session_id: "session_456",  // 等待其他会话
    pending_question: "请确认预算范围"
}

// 显示
// ✓ ask_user 对话框在 session_456 底部显示（当前 session 不显示）
// Mark: 正在为其他会话等待用户回答 (灰色斜体)
```

---

## API 方法

### uiStore 提供的方法

```javascript
// 获取 Agent 状态显示文案
getAgentStatusDisplay(agentName, sessionId)
// 返回: { text: string, status: string }

// 获取 Agent 状态历史
getAgentStatusHistory(agentName)
// 返回: [{ message: string, timestamp: string }]

// 格式化时间戳
formatStatusTime(timestamp)
// 返回: "20:00:00"

// 提交用户回答
submitUserAnswer(sessionId)

// 关闭对话框
closeAskUserDialog(sessionId)
```

---

## 后端已完成的修改

✅ `SystemStatusCollector` - 收集 `current_user_session_id`
✅ `BaseAgent` - 设置 `current_user_session_id`
✅ WebSocket 广播 - 每 2 秒推送状态

---

## 前端待完成的工作

- [ ] 更新 index.html，在每个 session 底部显示 Agent 状态
- [ ] 更新 session 列表，显示每个 session 的 Agent 状态徽章
- [ ] 更新 ask_user 对话框，使用 `askUserDialogs` Map
- [ ] 添加状态样式 CSS

---

**实现完成后，每个 session 都能实时显示相关 Agent 的状态！** 🎉
