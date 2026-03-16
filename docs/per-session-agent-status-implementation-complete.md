# 每个 Session 显示 Agent 状态 - 实现完成 ✅

## 概述

**日期**: 2026-03-15
**状态**: ✅ 完全实现
**测试**: ⏳ 待测试

已成功实现每个会话独立显示相关 Agent 的状态，并根据 `current_user_session_id` 判断 Agent 是否正在为当前会话工作。

---

## ✅ 完成的工作

### 1. 后端实现（已完成）

✅ **SystemStatusCollector** (`src/agentmatrix/core/system_status_collector.py`)
- 收集 `current_user_session_id` 字段
- 收集 `status_history` 字段
- WebSocket 每 2 秒广播完整状态

✅ **BaseAgent** (`src/agentmatrix/agents/base.py`)
- 添加 `current_user_session_id` 变量
- 在 `process_email()` 中设置逻辑

### 2. 前端逻辑（已完成）

✅ **uiStore.js** (`web/js/stores/uiStore.js`)
- 改用 `askUserDialogs: {}` Map
- 实现 `getAgentStatusDisplay(agentName, sessionId)`
- 实现 `getAgentStatusHistory(agentName)`
- 实现 `formatStatusTime(timestamp)`
- 更新 `handleAskUser()` 和 `checkForWaitingUser()`

✅ **app.js** (`web/js/app.js`)
- 移除旧的全局状态显示代码

### 3. 前端 UI（刚刚完成）

✅ **index.html** - 24 处修改：

#### A. 会话列表（添加 Agent 状态徽章）
```html
<!-- 在每个 session 项中显示 Agent 状态 -->
<template x-for="agentName in session.participants">
    <div :class="getAgentStatusDisplay(agentName, session.session_id).status">
        <span x-text="agentName"></span>:
        <span x-text="getAgentStatusDisplay(agentName, session.session_id).text"></span>
    </div>
</template>
```

#### B. 当前会话底部（Agent 状态面板）
```html
<!-- 遍历当前会话的所有 Agent -->
<template x-for="agentName in currentSession.participants">
    <div class="agent-status-panel">
        <!-- Agent 名称和状态 -->
        <div :class="getAgentStatusDisplay(agentName, currentSession.session_id).status">
            <span x-text="agentName"></span>:
            <span x-text="getAgentStatusDisplay(agentName, currentSession.session_id).text"></span>
        </div>

        <!-- 状态历史（只在 Agent 为当前会话工作时显示） -->
        <template x-for="statusItem in getAgentStatusHistory(agentName)">
            <div x-text="statusItem.message"></div>
        </template>
    </div>
</template>
```

#### C. ask_user 对话框（使用 Map）
```html
<!-- 全局弹窗对话框 -->
<div x-show="currentSession && askUserDialogs[currentSession.session_id]?.show">
    <h4 x-text="askUserDialogs[currentSession.session_id]?.agent_name"></h4>
    <p x-text="askUserDialogs[currentSession.session_id]?.question"></p>
    <textarea x-model="askUserDialogs[currentSession.session_id]?.answer"></textarea>
    <button @click="submitUserAnswer(currentSession.session_id)">提交</button>
</div>

<!-- 最小化到会话底部 -->
<div x-show="currentSession && askUserDialogs[currentSession.session_id]?.show">
    <!-- 同样的结构 -->
</div>
```

#### D. 待回答标志
```html
<!-- 会话列表中的待回答标志 -->
<span x-show="askUserDialogs[session.session_id]?.show">
    🔔 待回答
</span>
```

---

## 🎨 UI 展示

### 状态颜色方案

| 状态 | 颜色 | 动画 | 文案示例 |
|------|------|------|----------|
| **IDLE** | 灰色 | 无 | "空闲" |
| **THINKING** | 蓝色 | 脉冲 | "正在思考..." |
| **WORKING** | 琥珀色 | 脉冲 | "正在工作..." |
| **WAITING_FOR_USER** | 粉色 | 脉冲 | "等待你的回答" |
| **busy-on-other** | 浅灰 | 无 | "正在为其他会话思考" |

### 状态指示器

```html
<!-- 脉冲动画（THINKING/WORKING/WAITING_FOR_USER） -->
<div class="w-3 h-3 rounded-full bg-blue-500 animate-pulse"></div>
<div class="absolute inset-0 w-3 h-3 rounded-full animate-ping opacity-75"></div>

<!-- 静态（IDLE/busy-on-other） -->
<div class="w-3 h-3 rounded-full bg-surface-300"></div>
```

---

## 📊 场景示例

### 场景 1: Agent 正在为当前会话工作

```
Session 789 (当前查看)
├─ Participants: ["Mark", "Planner"]
└─ WebSocket 广播:
   ├─ Mark.status = "WORKING"
   ├─ Mark.current_user_session_id = "session_789" ✓
   └─ Planner.status = "IDLE"

UI 显示:
┌─────────────────────────────────┐
│ Mark: 正在工作... ● (蓝色脉冲)  │
│   • 正在初始化...              │
│   • 正在分析任务...            │
│                                 │
│ Planner: 空闲 ● (灰色)         │
└─────────────────────────────────┘
```

### 场景 2: Agent 正在为其他会话工作

```
Session 789 (当前查看)
├─ Participants: ["Mark"]
└─ WebSocket 广播:
   └─ Mark.current_user_session_id = "session_456" ✗

UI 显示:
┌─────────────────────────────────┐
│ Mark: 正在为其他会话工作 (灰色) │
└─────────────────────────────────┘
```

### 场景 3: Agent 等待当前会话用户回答

```
Session 789 (当前查看)
├─ Participants: ["Mark"]
└─ WebSocket 广播:
   ├─ Mark.status = "WAITING_FOR_USER"
   ├─ Mark.current_user_session_id = "session_789" ✓
   └─ Mark.pending_question = "请确认预算范围"

UI 显示:
┌─────────────────────────────────┐
│ Mark: 等待你的回答 ● (粉色脉冲) │
│   • 正在处理任务...            │
│                                 │
│ ╔═════════════════════════════╗ │
│ ║ Mark 需要你的输入           ║ │
│ ║ 问题: 请确认预算范围        ║ │
│ ║ [输入框]                    ║ │
│ ║ [提交] [关闭]              ║ │
│ ╚═════════════════════════════╝ │
└─────────────────────────────────┘
```

### 场景 4: 多 Agent 会话（不同状态）

```
Session 789 (当前查看)
├─ Participants: ["Mark", "Planner", "Coder"]
└─ WebSocket 广播:
   ├─ Mark.status = "IDLE"
   ├─ Planner.status = "THINKING"
   │  Planner.current_user_session_id = "session_789" ✓
   └─ Coder.status = "WORKING"
      Coder.current_user_session_id = "session_456" ✗

UI 显示:
┌─────────────────────────────────┐
│ Mark: 空闲 ● (灰色)            │
│                                 │
│ Planner: 正在思考... ● (蓝色)   │
│   • 分析任务需求...            │
│                                 │
│ Coder: 正在为其他会话工作 (灰) │
└─────────────────────────────────┘
```

---

## 🎯 核心特性

### ✅ 每个 session 独立显示
- 不再是全局显示一个 Agent 状态
- 每个 session 底部显示该 session 涉及的所有 Agent 状态

### ✅ 智能判断工作对象
- 根据 `current_user_session_id` 判断 Agent 是否正在为当前会话工作
- 显示不同的文案和样式

### ✅ ask_user 对话框精确定位
- 只在对应的 session 显示对话框
- 使用 `askUserDialogs` Map 存储

### ✅ 支持多 Agent 会话
- 自动遍历 `session.participants`
- 每个都有独立的状态显示

### ✅ 实时更新
- WebSocket 每 2 秒推送
- 无需轮询

---

## 📁 修改文件清单

### 后端文件 (2 个)
1. ✅ `src/agentmatrix/core/system_status_collector.py`
2. ✅ `src/agentmatrix/agents/base.py`

### 前端文件 (3 个)
3. ✅ `web/js/stores/uiStore.js`
4. ✅ `web/js/app.js`
5. ✅ `web/index.html` - **24 处修改**

### 文档 (3 个)
6. ✅ `docs/per-session-agent-status-guide.md`
7. ✅ `docs/per-session-agent-status-summary.md`
8. ✅ `docs/per-session-agent-status-implementation-complete.md` (本文档)

---

## 🧪 测试清单

### 基础功能
- [ ] 会话列表显示 Agent 状态徽章
- [ ] 当前会话底部显示 Agent 状态面板
- [ ] 状态历史正确显示
- [ ] 状态颜色和动画正确

### 状态判断
- [ ] Agent 空闲时显示"空闲"
- [ ] Agent 为当前会话工作时显示正常状态
- [ ] Agent 为其他会话工作时显示"为其他会话工作"

### ask_user 对话框
- [ ] 对话框只在对应 session 显示
- [ ] 提交回答功能正常
- [ ] 关闭对话框功能正常

### 多 Agent 会话
- [ ] 正确显示多个 Agent 的状态
- [ ] 每个 Agent 的状态独立显示

### 实时更新
- [ ] WebSocket 每 2 秒更新状态
- [ ] 状态变化时 UI 实时更新

---

## 🚀 下一步

1. **重启服务器**
   ```bash
   python server.py
   ```

2. **刷新浏览器**
   - 访问 http://localhost:8000
   - 查看 console 是否有错误

3. **测试场景**
   - 发送邮件给 Agent
   - 查看 Agent 状态是否正确显示
   - 测试 ask_user 对话框

4. **检查样式**
   - 状态颜色是否正确
   - 动画是否流畅
   - 布局是否美观

---

## 📊 代码统计

| 类型 | 数量 |
|------|------|
| 后端修改 | 2 个文件 |
| 前端逻辑修改 | 2 个文件 |
| 前端 UI 修改 | 1 个文件（24 处） |
| 新增方法 | 3 个（uiStore） |
| 总代码行数 | ~200 行 |

---

**每个 Session 显示 Agent 状态功能完全实现！** 🎉

现在可以启动服务器并测试了！
