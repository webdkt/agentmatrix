# AgentMatrix Desktop - UI交互设计

**版本**: v1.0
**最后更新**: 2026-03-18
**状态**: 已实施

---

## 📋 目录

- [普通交互模式](#普通交互模式)
- [Agent问答流程](#agent问答流程)
- [WebSocket实时更新流程](#websocket实时更新流程)
- [会话切换流程](#会话切换流程)
- [邮件回复的三种模式](#邮件回复的三种模式)
- [附件处理流程](#附件处理流程)
- [Agent状态监控流程](#agent状态监控流程)
- [错误处理与重试](#错误处理与重试)

---

## 普通交互模式

### 1. 会话选择流程

**触发条件**: 用户点击SessionList中的会话项

**流程步骤**:
```
1. 用户点击 SessionItem
   ↓
2. SessionItem emit @click 事件
   ↓
3. SessionList 调用 sessionStore.selectSession(session)
   ↓
4. sessionStore 设置 currentSession = session
   ↓
5. EmailList watch(currentSession) 触发
   ↓
6. EmailList.loadEmails(sessionId) 加载邮件
   ↓
7. await nextTick() + requestAnimationFrame()
   ↓
8. EmailList.scrollToBottom() 滚动到底部
```

**关键代码位置**:
- `SessionItem.vue`: 第118-120行
- `sessionStore.selectSession()`: `stores/session.js` 第108-122行
- `EmailList.vue`: 第68-102行

**状态变化**:
- `sessionStore.currentSession`: null → session对象
- `EmailList.emails`: [] → 邮件数组
- UI: 空状态 → 邮件列表

---

### 2. 邮件发送流程

**触发条件**: 用户填写邮件内容并点击发送

**流程步骤**:
```
1. 用户填写 EmailReply 表单
   - 选择收件人（Agent）
   - 填写主题（新邮件）
   - 填写正文
   - 可选：上传附件
   ↓
2. 用户点击"发送"按钮（或按Ctrl+Enter）
   ↓
3. EmailReply 调用 emailStore.sendEmail(emailData)
   ↓
4. emailAPI.sendEmail() 发送到后端
   ↓
5. 后端处理并返回
   ↓
6. EmailReply emit @sent 事件
   ↓
7. EmailList.handleReplySent() 触发
   ↓
8. EmailList.refreshEmails() 重新加载邮件
   ↓
9. scrollToBottom() 滚动到最新邮件
```

**关键代码位置**:
- `EmailReply.vue`: 发送按钮点击处理
- `emailStore.sendEmail()`: `stores/email.js`
- `EmailList.handleReplySent()`: 第110-112行

**数据格式**:
```javascript
{
  recipient: "AgentName",
  subject: "Email Subject",
  body: "Email content",
  attachments: [
    { filename: "file.txt", size: 1024 }
  ],
  task_id: "current_task_id",
  in_reply_to: null  // 如果是回复邮件
}
```

---

### 3. 设置修改流程

**触发条件**: 用户在Settings面板修改配置

**流程步骤**:
```
1. 用户打开 SettingsPanel
   ↓
2. 选择配置类型（LLM配置）
   ↓
3. 修改表单字段
   ↓
4. 点击"保存"按钮
   ↓
5. LLMConfigForm 调用 settingsStore.saveLLMConfig(configName, config)
   ↓
6. configAPI.updateLLMConfig() 发送到后端
   ↓
7. 后端验证并保存
   ↓
8. settingsStore 重新加载配置
   ↓
9. 显示成功通知
```

**关键代码位置**:
- `LLMConfigForm.vue`: 表单提交处理
- `settingsStore.saveLLMConfig()`: `stores/settings.js` 第82-96行

---

## WebSocket实时更新流程

### 连接建立

**时机**: 应用启动时（`App.vue` onMounted）

**URL**: `ws://localhost:8000/ws`

**流程**:
```
1. App.vue onMounted()
   ↓
2. 检查后端是否运行（backendStore.checkBackend()）
   ↓
3. 如果后端运行，建立WebSocket连接
   ↓
4. WebSocketStore.setConnected(true)
   ↓
5. 监听消息: ws.on('message', handle_message)
```

### 消息处理流程

```
WebSocket 推送消息
   ↓
WebSocketStore.handle_message(data)
   ↓
判断消息类型
   ├─ type === 'new_email'
   │  └→ handleNewEmail(emailData)
   │     └→ 通知所有注册的回调
   │
   ├─ type === 'runtime_event'
   │  └→ handleRuntimeEvent(eventData)
   │
   ├─ type === 'SYSTEM_STATUS'
   │  └→ handleSystemStatus(statusData)
   │     └→ 遍历所有Agent状态
   │
   └─ type === 'AGENT_STATUS_UPDATE'
      └→ handleAgentStatusUpdate(message)
         ├→ AgentStore.updateAgentStatus()
         └→ SessionStore.setPendingQuestion() (如果有)
```

### 消息类型详解

#### 1. NEW_EMAIL

**用途**: 新邮件通知

**数据格式**:
```javascript
{
  type: 'new_email',
  data: {
    id: 'email_001',
    sender: 'AgentName',
    recipient: 'User',
    subject: 'Hello',
    body: 'How are you?',
    timestamp: '2026-03-18T10:00:00Z',
    task_id: 'task_001'
  }
}
```

**处理逻辑**:
```javascript
handleNewEmail(emailData) {
  // 通知所有注册的回调
  this.newEmailCallbacks.forEach(callback => {
    callback(emailData)
  })
}
```

#### 2. SYSTEM_STATUS

**用途**: 系统状态推送（包含所有Agent状态）

**数据格式**:
```javascript
{
  type: 'SYSTEM_STATUS',
  data: {
    timestamp: '2026-03-18T10:00:00Z',
    agents: {
      'Planner': {
        status: 'THINKING',
        current_user_session_id: 'session_001',
        current_task_id: 'task_001'
      },
      'Coder': {
        status: 'WORKING',
        current_user_session_id: 'session_002',
        current_task_id: 'task_002'
      }
    }
  }
}
```

**处理逻辑**:
```javascript
handleSystemStatus(statusData) {
  Object.entries(statusData.agents).forEach(([agentName, agentInfo]) => {
    agentStore.updateAgentStatus(agentName, agentInfo)
  })
}
```

#### 3. AGENT_STATUS_UPDATE

**用途**: Agent状态增量更新

**数据格式**:
```javascript
{
  type: 'AGENT_STATUS_UPDATE',
  agent_name: 'Planner',
  data: {
    status: 'WORKING',
    current_user_session_id: 'session_001',
    current_task_id: 'task_001'
  }
}
```

**处理逻辑**:
```javascript
handleAgentStatusUpdate(message) {
  const { agent_name, data } = message
  agentStore.updateAgentStatus(agent_name, data)
}
```

### 回调注册机制

**目的**: 允许组件监听新邮件事件

**实现**:
```javascript
// 注册回调
const unsubscribe = websocketStore.onNewEmail((emailData) => {
  console.log('New email received:', emailData)
  // 更新UI
})

// 取消订阅
onUnmounted(() => {
  unsubscribe()
})
```

---

## 会话切换流程

### 流程图

```
用户点击 SessionItem
   ↓
SessionItem emit @click
   ↓
SessionList.selectSession(session)
   ↓
检查是否为同一会话
   ├─ 是 && !force → 跳过
   │
   └─ 否 || force → 继续
      ↓
      重置对话框标记 (resetDialogShown)
      ↓
      设置 currentSession = session
      ↓
      EmailList watch(currentSession) 触发
      ↓
      EmailList.loadEmails(sessionId)
      ├─ isLoading = true
      ├─ sessionAPI.getEmails(sessionId)
      ├─ emails.value = result.emails
      ├─ await nextTick()
      ├─ scrollToBottom()
      └─ isLoading = false
```

### 强制刷新机制

**用途**: 强制重新加载当前会话的邮件

**调用方式**:
```javascript
sessionStore.selectSession(currentSession, true)  // force = true
```

**使用场景**:
- 用户点击"刷新"按钮
- 邮件发送后重新加载
- 需要清除缓存数据

---

## 邮件回复的三种模式

### 1. 底部悬浮回复（默认）

**显示位置**: EmailList底部固定

**组件**: EmailReply.vue

**特点**:
- 固定在底部
- 默认回复最后一个非用户发件人
- 可滚动邮件列表

**样式**:
```css
.email-list__bottom-area {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  border-top: 1px solid var(--neutral-100);
  padding: var(--spacing-md);
}
```

### 2. Inline回复

**触发**: 用户点击邮件卡片的"Reply"按钮

**显示位置**: 邮件卡片下方

**组件**: EmailReply.vue（复用）

**特点**:
- 出现在被回复邮件下方
- 底部悬浮回复隐藏
- 明确显示回复关系

**实现**:
```vue
<EmailItem
  @reply="handleInlineReply"
  :email="email"
/>

<!-- EmailReply 显示在邮件下方 -->
<EmailReply
  v-if="showInlineReply"
  :inline-email="inlineReplyEmail"
  :show-inline="true"
  @sent="handleInlineReplySent"
  @cancel-inline="cancelInlineReply"
/>
```

**互斥逻辑**:
```javascript
handleInlineReply(email) {
  inlineReplyEmail.value = email
  showInlineReply.value = true
  // 底部回复自动隐藏
}

cancelInlineReply() {
  inlineReplyEmail.value = null
  showInlineReply.value = false
  // 底部回复自动显示
}
```

---

## 附件处理流程

### 拖拽上传

**组件**: NewEmailModal.vue, EmailReply.vue

**实现**:
```vue
<div
  @drop="handleDrop"
  @dragover.prevent
  @dragenter.prevent
  class="upload-area"
>
  Drop files here
</div>
```

### 文件验证

**验证逻辑**:
```javascript
function validateFile(file) {
  // 检查文件大小
  if (file.size > MAX_FILE_SIZE) {
    throw new Error('File too large')
  }

  // 检查文件类型
  const allowedTypes = ['image/*', 'application/pdf', 'text/*']
  if (!allowedTypes.some(type => file.type.match(type))) {
    throw new Error('File type not allowed')
  }

  return true
}
```

### 上传进度

**实现**:
```javascript
async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch('/api/upload', {
      method: 'POST',
      body: formData,
      // 监听上传进度
      onUploadProgress: (progressEvent) => {
        const progress = (progressEvent.loaded / progressEvent.total) * 100
        updateUploadProgress(file.name, progress)
      }
    })
    return await response.json()
  } catch (error) {
    console.error('Upload failed:', error)
    throw error
  }
}
```

### 附件显示

**位置**: EmailItem.vue

**显示内容**:
- 文件名
- 文件大小
- 文件类型图标

**图标映射**:
```javascript
function getAttachmentIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase()
  const iconMap = {
    'pdf': 'ti-file-pdf',
    'doc': 'ti-file-doc',
    'docx': 'ti-file-doc',
    'txt': 'ti-file-text',
    'jpg': 'ti-file-image',
    'png': 'ti-file-image',
    // ...
  }
  return iconMap[ext] || 'ti-file'
}
```

### 附件打开

**函数**: `openAttachment(recipient, taskId, filename)`

**路径**: `/workspace/agent_files/{recipient}/work_files/{taskId}/attachments/{filename}`

**实现**:
```javascript
async function openAttachment(recipient, taskId, filename) {
  const path = `/workspace/agent_files/${recipient}/work_files/${taskId}/attachments/${filename}`

  try {
    // 通过Tauri API打开文件
    await invoke('open_file', { path })
  } catch (error) {
    console.error('Failed to open file:', error)
    throw error
  }
}
```

---

## Agent状态监控流程

### 状态推送

**触发**: 后端Agent状态变化

**方式**: WebSocket推送 `AGENT_STATUS_UPDATE` 消息

### 前端处理

**流程**:
```
WebSocket 推送 AGENT_STATUS_UPDATE
   ↓
WebSocketStore.handleAgentStatusUpdate(message)
   ↓
AgentStore.updateAgentStatus(agentName, data)
   ├─ agents[agentName] = {
   │    status: data.status,
   │    status_history: [...],
   │    current_user_session_id: data.current_user_session_id,
   │    lastUpdated: new Date().toISOString()
   │  }
   ↓
AgentStatusIndicator 自动更新（响应式）
```

### 状态历史

**存储位置**: `agentStore.agents[agentName].status_history`

**格式**:
```javascript
[
  { status: 'IDLE', timestamp: '2026-03-18T10:00:00Z' },
  { status: 'THINKING', timestamp: '2026-03-18T10:01:00Z' },
  { status: 'WORKING', timestamp: '2026-03-18T10:02:00Z' },
  { status: 'WAITING_FOR_USER', timestamp: '2026-03-18T10:03:00Z' }
]
```

**显示**: 最多显示最近3条状态

---

## 错误处理与重试

### 网络错误

**检测**: API调用失败

**处理**:
```javascript
try {
  await sessionAPI.getSessions()
} catch (error) {
  console.error('Failed to load sessions:', error)
  uiStore.showNotification('Failed to load sessions', 'error')
  sessionStore.error = error.message
}
```

**UI反馈**:
- 显示错误通知
- 显示错误状态（如果有错误状态UI）
- 提供"重试"按钮

### 后端错误

**检测**: API返回错误响应

**处理**:
```javascript
if (response.status >= 400) {
  const error = await response.json()
  alert(error.message || 'Backend error')
  throw new Error(error.message)
}
```

**UI反馈**:
- Alert弹窗（使用 `alert()`）
- 控制台日志

### WebSocket断开

**检测**: WebSocket `onclose` 事件

**处理**:
```javascript
ws.onclose = () => {
  console.log('WebSocket disconnected')
  websocketStore.setConnected(false)

  // 尝试重连
  setTimeout(() => {
    console.log('Attempting to reconnect...')
    connectWebSocket()
  }, 3000)
}
```

**UI反馈**:
- 显示连接状态指示器
- 通知用户连接断开

### 用户提示

**通知类型**:
```javascript
uiStore.showNotification(
  'Message',  // 通知内容
  'type',     // 'info' | 'success' | 'warning' | 'error'
  3000        // 持续时间（毫秒）
)
```

**显示位置**: 右上角或右下角（根据UI实现）

---

## 最佳实践

### 1. 状态管理

- ✅ 使用Store管理全局状态
- ✅ 使用computed派生状态
- ✅ 避免直接修改props
- ✅ 使用watch监听状态变化

### 2. 错误处理

- ✅ 总是使用try-catch包装异步操作
- ✅ 提供有意义的错误消息
- ✅ 显示用户友好的错误提示
- ✅ 记录详细的错误日志

### 3. 性能优化

- ✅ 使用`nextTick()`等待DOM更新
- ✅ 使用`requestAnimationFrame()`优化滚动
- ✅ 避免不必要的重新渲染
- ✅ 使用debounce/throttle限制频繁操作

### 4. 用户体验

- ✅ 提供加载状态指示
- ✅ 显示操作反馈
- ✅ 保持交互一致性
- ✅ 支持键盘快捷键（Ctrl+Enter发送）

---

## 相关文档

- **[UI设计系统](./ui-design-system.md)** - 设计规范和样式指南
- **[组件参考](./component-reference.md)** - 组件和Store详细说明
- **[核心概念](../concepts/CONCEPTS.md)** - Email, Session, Agent定义

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
