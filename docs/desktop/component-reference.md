# AgentMatrix Desktop - 组件参考手册

**版本**: v1.0
**最后更新**: 2026-03-18
**状态**: 已实施

---

## 📋 目录

- [架构概览](#架构概览)
- [核心布局组件](#核心布局组件)
- [Email相关组件](#email相关组件)
- [Session相关组件](#session相关组件)
- [Agent相关组件](#agent相关组件)
- [Settings组件](#settings组件)
- [Dialog组件](#dialog组件)
- [Stores状态管理](#stores状态管理)
- [概念映射表](#概念映射表)
- [API层](#api层)
- [路由与导航](#路由与导航)
- [样式资源](#样式资源)

---

## 架构概览

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      App.vue                             │
│  ┌───────────────────────────────────────────────────┐  │
│  │              ViewSelector.vue (72px)              │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │              ViewContainer.vue                    │  │
│  │  ┌──────────────┐  ┌──────────────────────────┐  │  │
│  │  │SessionList   │  │   EmailList / Settings   │  │  │
│  │  │  (280px)     │  │      (flex)              │  │  │
│  │  └──────────────┘  └──────────────────────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 目录结构

```
agentmatrix-desktop/src/
├── components/
│   ├── view-selector/      # 视图选择器
│   ├── view-container/     # 视图容器
│   ├── session/            # 会话组件
│   ├── email/              # 邮件组件
│   ├── agent/              # Agent组件
│   ├── settings/           # 设置组件
│   └── dialog/             # 对话框组件
├── stores/                 # Pinia状态管理
│   ├── session.js          # 会话状态
│   ├── email.js            # 邮件状态
│   ├── agent.js            # Agent状态
│   ├── ui.js               # UI状态
│   ├── settings.js         # 设置状态
│   ├── backend.js          # 后端连接状态
│   └── websocket.js        # WebSocket状态
├── api/                    # API接口
│   ├── session.js
│   ├── email.js
│   ├── agent.js
│   └── config.js
├── styles/                 # 样式文件
│   ├── tokens.css          # 设计变量
│   └── global.css          # 全局样式
└── utils/                  # 工具函数
    ├── attachmentHelper.js
    └── ...
```

### 核心依赖关系

```
App.vue
├── ViewSelector.vue
├── ViewContainer.vue
│   ├── SessionList.vue
│   │   ├── SessionItem.vue
│   │   └── useSessionStore
│   └── EmailView (动态组件)
│       ├── EmailList.vue
│       │   ├── EmailItem.vue
│       │   ├── EmailReply.vue
│       │   ├── AgentStatusIndicator.vue
│       │   └── useSessionStore, useAgentStore
│       └── AskUserDialog.vue
│           └── useSessionStore
└── SettingsView (动态组件)
    └── SettingsPanel.vue
        └── useSettingsStore
```

---

## 核心布局组件

### App.vue

**位置**: `src/App.vue`

**描述**: 根组件，管理应用级别的状态和布局

**关键功能**:
- WebSocket连接初始化
- 后端服务状态监控
- 主题管理
- 国际化配置

**使用的Store**:
- `useBackendStore`: 后端连接状态
- `useWebSocketStore`: WebSocket连接
- `useUIStore`: UI主题

---

### ViewSelector.vue

**位置**: `src/components/view-selector/ViewSelector.vue`

**描述**: 左侧垂直视图选择器（72px宽）

**Props**: 无

**关键功能**:
- 视图切换（Email/Matrix/Magic/Settings）
- 图标导航
- 激活状态指示

**样式规范**:
- 宽度: `--view-selector-width: 72px`
- 图标大小: `--icon-lg: 24px`
- 激活状态: 背景色 `--primary-50`

---

### ViewContainer.vue

**位置**: `src/components/view-container/ViewContainer.vue`

**描述**: 视图容器，根据选择渲染不同视图

**Props**: 无

**关键功能**:
- 动态组件加载
- 视图切换动画
- 布局管理

**子组件**:
- `<component :is="currentView">` 动态加载视图

---

## Email相关组件

### EmailList.vue

**位置**: `src/components/email/EmailList.vue`

**描述**: 邮件列表容器，显示选中会话的所有邮件

**Props**:
```javascript
{
  user_agent_name: {
    type: String,
    default: 'User'
  }
}
```

**关键功能**:
- `loadEmails(sessionId)`: 加载会话邮件
- `scrollToBottom()`: 滚动到最新邮件
- `handleInlineReply(email)`: 显示内联回复
- `handleAgentQuestionSubmit()`: 提交Agent问答

**使用的Store**:
- `useSessionStore`: 当前会话、待处理问题
- `useAgentStore`: Agent状态

**特殊逻辑**:
1. **Agent问答处理**:
   - 检测 `pendingQuestion` computed属性
   - 显示问答表单（替换底部回复控件）
   - 临时显示问答记录在邮件列表中

2. **三种回复模式**:
   - 底部悬浮回复（默认）
   - Inline回复（点击邮件卡片）
   - Agent问答回答（替换底部回复）

**样式规范**:
- 工具栏高度: `48px`
- 邮件间距: `var(--spacing-md)`
- 底部控件: 固定在底部，`padding: var(--spacing-md)`

---

### EmailItem.vue

**位置**: `src/components/email/EmailItem.vue`

**描述**: 单封邮件展示组件

**Props**:
```javascript
{
  email: {
    type: Object,
    required: true
  },
  user_agent_name: {
    type: String,
    default: 'User'
  }
}
```

**Emits**:
```javascript
{
  'reply': (email) => void  // 用户点击回复按钮
}
```

**关键功能**:
- Markdown渲染（使用 `marked` 库）
- 附件显示和打开
- 邮件操作（回复、复制、删除）

**数据映射**:
| Email字段 | 显示位置 | 说明 |
|-----------|---------|------|
| `email.sender` | displayName | 发件人名称 |
| `email.is_from_user` | TO/FROM标签 | true=TO, false=FROM |
| `email.body` | Markdown渲染 | 邮件正文 |
| `email.attachments` | 附件列表 | 文件名和大小 |
| `email.timestamp` | 时间显示 | 相对时间格式 |

**样式特点**:
- 用户邮件: 绿色渐变背景 `linear-gradient(to bottom right, #f0fdf4, white)`
- Agent邮件: 白色背景
- Hover效果: 左边框变为主色 `border-left: 3px solid var(--primary-500)`

---

### EmailReply.vue

**位置**: `src/components/email/EmailReply.vue`

**描述**: 邮件回复控件

**Props**:
```javascript
{
  currentSession: Object,   // 当前会话
  emails: Array,            // 邮件列表
  inlineEmail: Object,      // 内联回复的邮件（可选）
  showInline: Boolean       // 是否显示内联回复
}
```

**Emits**:
```javascript
{
  'sent': () => void,           // 邮件发送成功
  'cancel-inline': () => void   // 取消内联回复
}
```

**关键功能**:
- 文本输入（支持Ctrl+Enter发送）
- 附件上传
- 自动调整高度（auto-resize textarea）
- 发件人选择（如果没有inline模式）

**特性**:
- 固定在EmailList底部
- 支持多行文本输入
- 文件拖拽上传

---

## Session相关组件

### SessionList.vue

**位置**: `src/components/session/SessionList.vue`

**描述**: 会话列表容器

**Props**: 无

**关键功能**:
- `loadSessions()`: 加载会话列表
- `createSession()`: 创建新会话
- `searchSessions(query)`: 搜索会话

**使用的Store**:
- `useSessionStore`: 所有会话操作

**UI元素**:
- 新邮件按钮（顶部，全宽）
- 搜索框（新邮件按钮下方）
- 会话列表（可滚动）

---

### SessionItem.vue

**位置**: `src/components/session/SessionItem.vue`

**描述**: 单个会话项显示

**Props**:
```javascript
{
  session: {
    type: Object,
    required: true
  },
  isActive: {
    type: Boolean,
    default: false
  },
  index: {
    type: Number,
    required: true
  }
}
```

**Emits**:
```javascript
{
  'click': () => void  // 点击会话项
}
```

**关键功能**:
- **智能配色系统**: 基于Agent名称生成一致但多样的颜色
- **待处理问题指示器**: 红色圆点显示有未回答问题
- **时间格式化**: 相对时间显示

**配色算法**:
```javascript
// 第一步：基于agent名称生成基础色相
const baseHue = hash(agentName) % 360

// 第二步：基于sessionId生成变化因子
const hueOffset = (sessionHash % 31) - 15  // -15到+15度
const hue = baseHue + hueOffset

// 饱和度和亮度变化
const saturation = 60 + (sessionHash % 16)      // 60-75%
const lightness = 52 + (sessionHash % 8)        // 52-62%
```

**样式规范**:
- 高度: `56px`
- 内边距: `12px 16px`
- 头像: `32px`圆形
- 激活状态: 背景色 `--primary-50`

---

## Agent相关组件

### AgentStatusIndicator.vue

**位置**: `src/components/agent/AgentStatusIndicator.vue`

**描述**: Agent状态指示器

**Props**:
```javascript
{
  agentName: {
    type: String,
    required: true
  },
  currentSessionId: {
    type: String,
    required: true
  }
}
```

**Agent状态**:
| 状态 | 说明 | 颜色 |
|------|------|------|
| IDLE | 空闲 | 灰色 |
| THINKING | 思考中 | 蓝色 |
| WORKING | 工作中 | 绿色 |
| WAITING_FOR_USER | 等待用户 | 橙色 |

**关键功能**:
- 显示当前状态
- 显示最近3条状态历史
- 状态变化动画

**使用的Store**:
- `useAgentStore`: Agent状态数据

---

## Settings组件

### SettingsPanel.vue

**位置**: `src/components/settings/SettingsPanel.vue`

**描述**: 设置面板容器

**Props**: 无

**子面板**:
- LLM配置
- 语言和外观
- 后端设置

---

### LLMConfigForm.vue

**位置**: `src/components/settings/LLMConfigForm.vue`

**描述**: LLM配置表单

**Props**:
```javascript
{
  configName: String,    // 配置名称
  config: Object         // 配置数据
}
```

**表单字段**:
- API Base URL
- API Key
- Model Name
- Temperature
- Max Tokens

**使用的Store**:
- `useSettingsStore`: LLM配置CRUD

---

## Dialog组件

### AskUserDialog.vue

**位置**: `src/components/dialog/AskUserDialog.vue`

**描述**: Agent问答对话框

**Props**:
```javascript
{
  show: {
    type: Boolean,
    default: false
  }
}
```

**Emits**:
```javascript
{
  'close': () => void,      // 关闭对话框
  'submitted': () => void   // 提交回答
}
```

**关键功能**:
- 显示Agent问题
- 用户输入回答
- 提交到后端
- 防止重复弹窗

**使用的Store**:
- `useSessionStore`: 获取和提交待处理问题

**样式特点**:
- 模态框: `max-width: 540px`
- 背景: `var(--warning-50)`
- 图标: `var(--warning-600)`

---

### NewEmailModal.vue

**位置**: `src/components/dialog/NewEmailModal.vue`

**描述**: 新邮件模态框

**Props**:
```javascript
{
  show: Boolean,
  recipients: Array    // 可用的Agent列表
}
```

**Emits**:
```javascript
{
  'close': () => void,
  'send': (emailData) => void
}
```

**表单字段**:
- 收件人（Agent选择）
- 主题
- 正文
- 附件（拖拽上传）

---

## Stores状态管理

### useSessionStore

**位置**: `src/stores/session.js`

**状态**:
```javascript
{
  sessions: [],              // 会话列表
  currentSession: null,      // 当前选中会话
  currentPage: 1,            // 当前页码
  perPage: 20,              // 每页数量
  totalSessions: 0,          // 总会话数
  isLoading: false,          // 加载状态
  error: null,               // 错误信息
  pendingQuestions: {},      // { session_id: { agent_name, question, task_id, timestamp } }
  askUserDialogShownFor: null // 记录已弹出对话框的session_id
}
```

**Getters**:
```javascript
{
  hasMoreSessions: Boolean,        // 是否有更多会话
  currentParticipants: Array,      // 当前会话参与者
  hasSelectedSession: Boolean,     // 是否已选择会话
  hasPendingQuestion: (sessionId) => Boolean,    // 是否有待处理问题
  getPendingQuestion: (sessionId) => Object,     // 获取待处理问题
  shouldShowAskUserDialog: (sessionId) => Boolean  // 是否应该显示对话框
}
```

**Actions**:
```javascript
{
  loadSessions(loadMore = false),        // 加载会话列表
  selectSession(session, force = false), // 选择会话
  createSession(data),                   // 创建新会话
  searchSessions(query),                 // 搜索会话
  clearCurrentSession(),                 // 清除当前会话
  setPendingQuestion(sessionId, questionData),    // 设置待处理问题
  clearPendingQuestion(sessionId),               // 清除待处理问题
  submitAskUserAnswer(sessionId, answer),        // 提交ask_user回答
  markDialogShown(sessionId),                    // 标记对话框已显示
  resetDialogShown(),                            // 重置对话框标记
  closeAskUserDialog(sessionId)                  // 关闭对话框
}
```

**特殊逻辑**:
- **防止重复弹窗**: 使用 `askUserDialogShownFor` 跟踪已显示对话框的会话
- **强制刷新**: `selectSession(session, force=true)` 强制重新加载邮件

---

### useAgentStore

**位置**: `src/stores/agent.js`

**状态**:
```javascript
{
  agents: {}  // { agentName: { status, status_history, current_user_session_id, ... } }
}
```

**Getters**:
```javascript
{
  getAgent: (agentName) => Object,        // 获取Agent信息
  getAgentStatus: (agentName) => String   // 获取Agent状态
}
```

**Actions**:
```javascript
{
  updateAgentStatus(agentName, data),   // 更新Agent状态
  clearAgentStatus(agentName)            // 清除Agent状态
}
```

**Agent状态类型**:
- `IDLE`: 空闲
- `THINKING`: 思考中
- `WORKING`: 工作中
- `WAITING_FOR_USER`: 等待用户输入

---

### useWebSocketStore

**位置**: `src/stores/websocket.js`

**状态**:
```javascript
{
  isConnected: false,           // WebSocket连接状态
  lastEvent: null,              // 最后收到的事件
  newEmailCallbacks: []         // 新邮件回调函数列表
}
```

**Getters**:
```javascript
{
  hasNewEmailCallbacks: Boolean  // 是否有新邮件回调
}
```

**Actions**:
```javascript
{
  setConnected(connected),              // 设置连接状态
  handle_message(data),                 // 处理WebSocket消息
  handleNewEmail(emailData),            // 处理新邮件事件
  handleRuntimeEvent(eventData),        // 处理运行时事件
  handleAskUserEvent(eventData),        // 处理ASK_USER事件
  handleSystemStatus(statusData),       // 处理系统状态事件
  handleAgentStatusUpdate(message),     // 处理Agent状态增量更新
  onNewEmail(callback),                 // 注册新邮件回调
  offNewEmail(callback)                 // 移除新邮件回调
}
```

**WebSocket消息类型**:
| 类型 | 处理函数 | 说明 |
|------|---------|------|
| `new_email` | `handleNewEmail()` | 新邮件通知 |
| `runtime_event` | `handleRuntimeEvent()` | 运行时事件（包含ASK_USER） |
| `SYSTEM_STATUS` | `handleSystemStatus()` | 系统状态推送 |
| `AGENT_STATUS_UPDATE` | `handleAgentStatusUpdate()` | Agent状态增量更新 |

---

### useUIStore

**位置**: `src/stores/ui.js`

**状态**:
```javascript
{
  sidebarWidth: 320,          // 侧边栏宽度
  minSidebarWidth: 250,       // 最小宽度
  maxSidebarWidth: 500,       // 最大宽度
  panelSizes: [30, 70],       // 面板尺寸百分比
  modals: {                   // 对话框状态
    newEmail: false,
    settings: false,
    agentConfig: false,
    confirmDialog: false
  },
  notifications: [],          // 通知列表
  isLoading: false,          // 加载状态
  error: null,               // 错误信息
  theme: 'light',            // 主题
  debugMode: false           // 调试模式
}
```

**Getters**:
```javascript
{
  hasNotifications: Boolean,           // 是否有通知
  unreadNotificationCount: Number,     // 未读通知数量
  isDarkMode: Boolean                  // 是否为暗色模式
}
```

**Actions**:
```javascript
{
  resizeSidebar(width),               // 调整侧边栏宽度
  resetSidebarWidth(),                // 重置侧边栏宽度
  resizePanels(sizes),                // 调整面板尺寸
  openModal(modalName, data),         // 打开对话框
  closeModal(modalName),              // 关闭对话框
  closeAllModals(),                   // 关闭所有对话框
  showNotification(message, type, duration),  // 显示通知
  removeNotification(notificationId),         // 移除通知
  markNotificationAsRead(notificationId),     // 标记通知已读
  clearNotifications(),                       // 清空通知
  setLoading(loading),                        // 设置加载状态
  setError(error),                            // 设置错误信息
  toggleTheme(),                              // 切换主题
  setTheme(theme),                            // 设置主题
  toggleDebugMode(),                          // 切换调试模式
  initializeUI()                              // 初始化UI状态
}
```

---

### useSettingsStore

**位置**: `src/stores/settings.js`

**状态**:
```javascript
{
  llmConfig: null,          // LLM配置（向后兼容）
  llmConfigs: [],           // 所有LLM配置
  configStatus: null,       // 配置状态
  agents: [],               // Agent列表
  isLoading: false,         // 加载状态
  error: null               // 错误信息
}
```

**Getters**:
```javascript
{
  isLLMConfigured: Boolean,    // 是否已配置LLM
  needsColdStart: Boolean      // 是否需要冷启动
}
```

**Actions**:
```javascript
{
  loadConfigStatus(),              // 加载配置状态
  loadLLMConfig(),                 // 加载所有LLM配置
  saveLLMConfig(configName, config), // 保存LLM配置
  createLLMConfig(config),         // 创建LLM配置
  deleteLLMConfig(configName),     // 删除LLM配置
  resetLLMConfig(configName)       // 重置LLM配置为默认值
}
```

---

### useBackendStore

**位置**: `src/stores/backend.js`

**状态**:
```javascript
{
  isRunning: false,              // 后端是否运行
  isStarting: false,             // 后端是否正在启动
  isStopping: false,             // 后端是否正在停止
  error: null,                   // 错误信息
  lastCheckTime: null,           // 最后检查时间
  healthCheckInterval: null,     // 健康检查定时器
  startupAttempts: 0,            // 启动尝试次数
  maxStartupAttempts: 3,         // 最大启动尝试次数
  autoStartEnabled: true,        // 是否自动启动
  continuousMonitoring: true     // 是否持续监控
}
```

**Getters**:
```javascript
{
  status: String,           // 'starting' | 'stopping' | 'running' | 'stopped'
  canStart: Boolean,        // 是否可以启动
  canStop: Boolean,         // 是否可以停止
  healthStatus: String,     // 'error' | 'healthy' | 'unhealthy'
  canRetry: Boolean         // 是否可以重试
}
```

**Actions**:
```javascript
{
  startBackend(autoRetry = true),     // 启动后端
  stopBackend(),                      // 停止后端
  checkBackend(),                     // 检查后端状态
  startHealthMonitoring(),            // 开始健康监控
  stopHealthMonitoring(),             // 停止健康监控
  initializeBackend(),                // 初始化后端
  showNotification(title, body),      // 显示通知
  clearError(),                       // 清除错误
  setAutoStart(enabled),              // 设置自动启动
  setContinuousMonitoring(enabled)    // 设置持续监控
}
```

---

## 概念映射表

### Email ↔ EmailList/EmailItem/EmailReply

| Email字段 | 组件/显示 | 说明 |
|-----------|---------|------|
| `email.sender` | displayName | 发件人名称 |
| `email.recipient` | displayName | 收件人名称 |
| `email.is_from_user` | TO/FROM标签 | true显示"TO"，false显示"FROM" |
| `email.subject` | 邮件主题 | EmailItem顶部显示 |
| `email.body` | Markdown渲染 | 使用marked库渲染 |
| `email.attachments` | 附件列表 | 显示文件名和大小 |
| `email.timestamp` | 相对时间 | "Just now", "5m ago", "Yesterday" |
| `email.task_id` | 文件路径 | 用于附件打开 |
| `email.id` | 邮件标识 | 用于回复和删除操作 |

### Session ↔ SessionList/SessionItem

| Session字段 | 组件/显示 | 说明 |
|------------|---------|------|
| `session.session_id` | 路由参数 | 唯一标识符 |
| `session.participants` | 显示名称 | 逗号分隔的Agent名称 |
| `session.subject` | 会话标题 | 显示为粗体文本 |
| `session.last_email_time` | 时间显示 | 相对时间格式 |
| `session.name` | 头像颜色 | 用于生成智能配色 |

### Agent ↔ AgentStatusIndicator

| Agent状态 | 显示 | 颜色 |
|----------|------|------|
| IDLE | "Idle" | 灰色 |
| THINKING | "Thinking..." | 蓝色 |
| WORKING | "Working" | 绿色 |
| WAITING_FOR_USER | "Waiting for you" | 橙色 |

### User ↔ user_agent_name

| 概念 | 前端变量 | 显示效果 |
|------|---------|---------|
| User邮件 | `email.is_from_user === true` | 绿色渐变背景 |
| TO标签 | `email.is_from_user === true` | 绿色边框标签 |
| User回复 | EmailReply组件 | 默认收件人为User |

### Task ↔ task_id

| Task用途 | 组件 | 说明 |
|---------|------|------|
| 文件隔离 | EmailItem附件 | 路径: `/workspace/agent_files/{recipient}/work_files/{task_id}/attachments/` |
| 任务追踪 | 所有邮件 | 关联同一个任务的所有邮件 |
| 会话上下文 | Session | 跨Agent的任务边界 |

---

## API层

### sessionAPI

**位置**: `src/api/session.js`

**方法**:
```javascript
{
  getSessions(page, perPage),           // 获取会话列表
  createSession(data),                  // 创建新会话
  getEmails(sessionId),                 // 获取会话邮件
  deleteSession(sessionId)              // 删除会话
}
```

### emailAPI

**位置**: `src/api/email.js`

**方法**:
```javascript
{
  sendEmail(emailData),                 // 发送邮件
  deleteEmail(emailId, sessionId)       // 删除邮件
}
```

### agentAPI

**位置**: `src/api/agent.js`

**方法**:
```javascript
{
  getAgents(),                          // 获取所有Agent
  submitUserInput(agentName, question, answer)  // 提交用户回答
}
```

### configAPI

**位置**: `src/api/config.js`

**方法**:
```javascript
{
  getConfigStatus(),                    // 获取配置状态
  getLLMConfigs(),                      // 获取所有LLM配置
  updateLLMConfig(configName, config),  // 更新LLM配置
  createLLMConfig(config),              // 创建LLM配置
  deleteLLMConfig(configName),          // 删除LLM配置
  resetLLMConfig(configName)            // 重置LLM配置
}
```

---

## 路由与导航

### 视图切换机制

**ViewSelector.vue** → **ViewContainer.vue**

1. 用户点击ViewSelector图标
2. ViewSelector更新 `currentView` 状态
3. ViewContainer动态加载对应组件:
   ```javascript
   const views = {
     email: 'EmailView',
     matrix: 'MatrixView',
     magic: 'MagicView',
     settings: 'SettingsView'
   }
   ```

### 会话切换流程

1. 用户点击SessionItem
2. SessionItem emit `@click` 事件
3. SessionList调用 `sessionStore.selectSession(session)`
4. selectSession触发watcher
5. EmailList的 `watch(currentSession)` 触发
6. EmailList调用 `loadEmails(sessionId)`
7. 等待 `nextTick()` + `requestAnimationFrame()`
8. EmailList调用 `scrollToBottom()`

---

## 样式资源

### tokens.css

**位置**: `src/styles/tokens.css`

**内容**: 所有设计系统变量

**使用方式**:
```vue
<style scoped>
.my-component {
  color: var(--primary-500);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
}
</style>
```

**重要变量**:
- 颜色: `--primary-*`, `--neutral-*`, `--success-*`, etc.
- 间距: `--spacing-*`
- 字体: `--font-*`
- 圆角: `--radius-*`
- 阴影: `--shadow-*`
- 动画: `--duration-*`, `--ease-*`

---

### global.css

**位置**: `src/styles/global.css`

**内容**:
- 全局样式重置
- 工具类
- 响应式断点
- 暗色模式样式

**工具类示例**:
```css
.flex { display: flex; }
.items-center { align-items: center; }
.gap-2 { gap: var(--spacing-sm); }
.text-sm { font-size: var(--font-sm); }
```

---

## 术语一致性检查表

| 概念 | 组件命名 | Store命名 | API路径 | 变量命名 | ✅ |
|------|---------|-----------|---------|---------|---|
| 邮件 | Email* | email | /api/emails | email | ✅ |
| 会话 | Session* | session | /api/sessions | session | ✅ |
| 智能体 | Agent* | agent | /api/agents | agent | ✅ |
| 用户 | User | - | - | user_agent_name | ✅ |
| 附件 | attachments | attachments | - | attachments | ✅ |
| 任务 | taskId | taskId | - | taskId | ✅ |

---

## 相关文档

- **[UI设计系统](./ui-design-system.md)** - 设计规范和样式指南
- **[交互设计](./ui-interaction-flows.md)** - 特殊流程和状态管理
- **[核心概念](../concepts/CONCEPTS.md)** - Email, Session, Agent定义

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
