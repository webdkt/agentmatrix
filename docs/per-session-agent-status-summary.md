# 每个 Session 显示 Agent 状态 - 实现总结

## 🎯 目标

每个会话底部显示该会话涉及的所有 Agent 的状态，根据 `current_user_session_id` 判断 Agent 是否正在为当前会话工作。

---

## ✅ 已完成的工作

### 1. 后端实现

#### SystemStatusCollector (`src/agentmatrix/core/system_status_collector.py`)
- ✅ 添加 `current_user_session_id` 字段到 agent_info
- ✅ 添加 `status_history` 字段到 agent_info
- ✅ WebSocket 每 2 秒广播完整状态

#### BaseAgent (`src/agentmatrix/agents/base.py`)
- ✅ 添加 `current_user_session_id` 变量
- ✅ 在 `process_email()` 中设置逻辑：
  - 邮件来自 User → `current_user_session_id = email.sender_session_id`
  - 邮件来自 Agent → `current_user_session_id = None`

### 2. 前端实现

#### uiStore.js (`web/js/stores/uiStore.js`)
- ✅ 改用 `askUserDialogs: {}` Map（每个 session 一个对话框）
- ✅ 实现 `getAgentStatusDisplay(agentName, sessionId)` 方法
- ✅ 实现 `getAgentStatusHistory(agentName)` 方法
- ✅ 更新 `handleAskUser()` - 只在对应 session 显示对话框
- ✅ 更新 `checkForWaitingUser()` - 检查 `current_user_session_id`

#### app.js (`web/js/app.js`)
- ✅ 移除旧的全局状态显示代码
- ✅ 移除 `showCurrentAgentStatus()` 方法
- ✅ 移除 `formatStatusTime()` 方法（已移到 uiStore）
- ✅ 清理 `loadSessionEmails()` 中的调用

---

## 🔍 核心逻辑

### 状态显示判断

```
如果 Agent.status == 'IDLE':
  显示 "空闲"

否则:
  如果 Agent.current_user_session_id == 当前查看的 session_id:
    显示 "正在思考..." / "正在工作..." / "等待你的回答"
  否则:
    显示 "正在为其他会话思考/工作/等待用户回答"
```

### ask_user 对话框显示

```
只在以下情况显示对话框:
1. Agent.pending_question 存在
2. Agent.current_user_session_id == 当前查看的 session_id
```

---

## 📊 数据结构

### Session 数据
```javascript
{
    session_id: "xxx",
    subject: "任务：写代码",
    participants: ["Mark", "Planner"]  // 涉及的 Agent 列表
}
```

### WebSocket 广播数据
```javascript
systemStatus: {
    timestamp: "2026-03-15T20:00:00",
    agents: {
        "Mark": {
            status: "THINKING",
            current_user_session_id: "user_session_789",  // 关键字段
            pending_question: "...",
            status_history: [...]
        }
    }
}
```

---

## 🎨 场景示例

### 场景 1: Agent 正在为当前会话工作
```
Session 789 (当前查看)
  Participants: [Mark]

WebSocket: Mark.status = "WORKING"
         Mark.current_user_session_id = "session_789"

显示: Mark: 正在工作... ✓ (蓝色脉冲)
      • 正在初始化...
      • 正在分析任务...
```

### 场景 2: Agent 正在为其他会话工作
```
Session 789 (当前查看)
  Participants: [Mark]

WebSocket: Mark.status = "WORKING"
         Mark.current_user_session_id = "session_456"

显示: Mark: 正在为其他会话工作 (灰色斜体)
```

### 场景 3: Agent 等待当前会话用户回答
```
Session 789 (当前查看)
  Participants: [Mark]

WebSocket: Mark.status = "WAITING_FOR_USER"
         Mark.current_user_session_id = "session_789"
         Mark.pending_question = "请确认预算范围"

显示: ✓ ask_user 对话框在 session_789 底部显示
     Mark: 等待你的回答 (粉色脉冲)
```

---

## 📝 待完成的工作

### 前端 UI 实现

#### 1. 更新 index.html

**Session 列表项**（显示 Agent 状态徽章）:
```html
<template x-for="session in sessions">
    <div>
        <h3 x-text="session.subject"></h3>
        <!-- Agent 状态徽章 -->
        <template x-for="agentName in session.participants">
            <div :class="getAgentStatusDisplay(agentName, session.session_id).status">
                <span x-text="agentName"></span>:
                <span x-text="getAgentStatusDisplay(agentName, session.session_id).text"></span>
            </div>
        </template>
    </div>
</template>
```

**当前会话底部**（显示 Agent 状态面板）:
```html
<div x-show="currentSession">
    <template x-for="agentName in currentSession.participants">
        <div class="agent-status-panel">
            <div :class="getAgentStatusDisplay(agentName, currentSession.session_id).status">
                <span x-text="agentName"></span>:
                <span x-text="getAgentStatusDisplay(agentName, currentSession.session_id).text"></span>
            </div>
            <!-- 状态历史 -->
            <div x-show="systemStatus.agents[agentName]?.current_user_session_id === currentSession.session_id">
                <template x-for="status in getAgentStatusHistory(agentName)">
                    <div x-text="status.message"></div>
                </template>
            </div>
        </div>
    </template>
</div>
```

**ask_user 对话框**（在对应 session 显示）:
```html
<div x-show="askUserDialogs[currentSession?.session_id]?.show">
    <h4 x-text="askUserDialogs[currentSession.session_id]?.agent_name"></h4>
    <p x-text="askUserDialogs[currentSession.session_id]?.question"></p>
    <textarea x-model="askUserDialogs[currentSession.session_id]?.answer"></textarea>
    <button @click="submitUserAnswer(currentSession.session_id)">提交</button>
    <button @click="closeAskUserDialog(currentSession.session_id)">关闭</button>
</div>
```

#### 2. 添加 CSS 样式

```css
/* Agent 状态徽章 */
.agent-status-badge.idle { background: #e5e7eb; }
.agent-status-badge.thinking { background: #dbeafe; animation: pulse; }
.agent-status-badge.busy-on-other { background: #f3f4f6; font-style: italic; }

/* 状态面板 */
.agent-status-panel { padding: 12px; border: 1px solid #e5e7eb; }

/* 脉冲动画 */
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```

---

## 🧪 测试清单

- [ ] 场景 1: Agent 正在为当前会话工作
- [ ] 场景 2: Agent 正在为其他会话工作
- [ ] 场景 3: Agent 空闲
- [ ] 场景 4: Agent 等待当前会话用户回答
- [ ] 场景 5: Agent 等待其他会话用户回答
- [ ] 场景 6: 多 Agent 会话（不同 Agent 有不同状态）

---

## 📁 修改文件清单

### 后端文件 (2 个)
1. ✅ `src/agentmatrix/core/system_status_collector.py`
2. ✅ `src/agentmatrix/agents/base.py`

### 前端文件 (3 个)
3. ✅ `web/js/stores/uiStore.js`
4. ✅ `web/js/app.js`
5. ⏳ `web/index.html` - 待更新
6. ⏳ CSS 样式 - 待添加

### 文档 (2 个)
7. ✅ `docs/per-session-agent-status-guide.md` - 实现指南
8. ✅ `docs/per-session-agent-status-summary.md` - 本文档

---

## 🎉 核心成就

- ✅ **每个 session 独立显示 Agent 状态**
- ✅ **根据 `current_user_session_id` 判断工作对象**
- ✅ **ask_user 对话框只在对应 session 显示**
- ✅ **移除全局状态显示，改为 per-session 显示**
- ✅ **支持多 Agent 会话**

---

**后端逻辑已完成，前端 UI 待实现！** 🚀
