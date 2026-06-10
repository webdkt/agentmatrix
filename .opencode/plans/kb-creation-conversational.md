# CreateKBWizard 对话式改造方案

## 用户流程

```
1. 用户点击"创建知识库"
2. 显示表单：name + description
3. 用户填写后点击"开始创建"
4. 前端生成 task_id，发送第一封消息给 KnowledgeBaseAgent
5. 进入分屏界面：
   - 左侧：schema-draft.md 预览（轮询刷新）
   - 右侧：简化版聊天（Agent 消息 + 用户输入框）
6. Agent 生成 schema，写入 /tmp/{task_id}-schema-draft.md
7. 用户通过对话确认/修改 schema
8. Agent 调用 create_namespace → 前端检测到 → 进入 wiki 界面
```

## 第一封消息模板

```
你正在帮助用户创建一个新的知识库。

【任务信息】
- 任务ID: {task_id}
- 知识库名称: {name}
- 用户描述: {description}

【工作流程】
1. 根据描述生成初始 Schema
2. 将 Schema 写入 /tmp/{task_id}-schema-draft.md
3. 向用户展示 Schema，询问是否需要修改
4. 根据反馈修改（同步更新文件）
5. 用户确认后，调用 create_namespace(name="{name}", description="{description}", schema=<内容>)

【Schema 格式】
包含三个部分：
1. 关注的信息类型（名称、描述、关注维度）
2. 类型之间的关系（包含、引用）
3. 目录结构及用途

【要求】
- 每次修改后更新 /tmp/{task_id}-schema-draft.md
- 等待用户确认后再创建
- 描述不清时主动询问
```

## 后端改动

### knowledge.py

1. 新增 `GET /api/knowledge/schema-draft/{task_id}` 端点
   - 读取 `/tmp/{task_id}-schema-draft.md` 文件内容
   - 返回 `{ "content": "...", "exists": true/false }`

2. 移除 `POST /api/knowledge/generate-schema` 端点（不再需要）

### 新增文件：无

### 修改文件：
- `server_handlers/routes/knowledge.py` — 新增 schema-draft 端点，移除 generate-schema

## 前端改动

### api/knowledge.js

新增：
```js
async getSchemaDraft(taskId) {
  return API.get(`/api/knowledge/schema-draft/${taskId}`)
}
```

移除：
```js
async generateSchema(name, description) { ... }
```

### stores/knowledge.js

新增状态：
```js
const schemaDraft = ref('')
const schemaDraftLoading = ref(false)
```

新增 actions：
```js
async function fetchSchemaDraft(taskId) { ... }
function clearSchemaDraft() { ... }
```

### CreateKBWizard.vue（重写）

状态机：`form` → `creating` → `done`

**form 状态**：
- name 输入框
- description 文本框
- "开始创建"按钮

**creating 状态**：
- 左侧：schema 预览面板（每 3 秒轮询 getSchemaDraft）
- 右侧上方：Agent 消息列表（从 session events 获取）
- 右侧下方：用户输入框

**done 状态**：
- 显示创建成功
- 自动进入 wiki 界面

### 组件结构

```
CreateKBWizard.vue
├── [form] 表单
└── [creating] 分屏
    ├── SchemaPreview.vue（左侧，轮询刷新）
    └── 右侧聊天区（内联，不用单独组件）
        ├── 消息列表
        └── 输入框
```

## 实现细节

### task_id 生成

复用 AutomationView 的格式：
```js
function generateTaskId(name) {
  const now = new Date()
  const pad = (n, l = 2) => String(n).padStart(l, '0')
  const timeStr = [
    String(now.getFullYear()).slice(-2),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
  ].join('')
  const subject = `kb-${name}`
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .slice(0, 10)
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  const rand = Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
  return `${timeStr}-${subject}-${rand}`
}
```

### 发送第一封消息

```js
const taskId = generateTaskId(name.value)
const schemaPath = `/tmp/${taskId}-schema-draft.md`

const emailData = {
  recipient: '知识管家',
  subject: `kb-create-${name.value}`,
  body: buildFirstMessage(name.value, description.value, taskId, schemaPath),
  task_id: taskId,
}

const response = await sessionAPI.sendEmail('new', emailData)
```

### 轮询 session 等待创建

```js
async function waitForSession(response, prevCount) {
  const taskId = response?.email?.task_id
  const maxWait = 15000
  const startTime = Date.now()

  while (Date.now() - startTime < maxWait) {
    await sessionStore.fetchSessions()
    const found = sessionStore.sessions.find(
      s => s.session_id === taskId || s.readable_id === taskId
    ) || (sessionStore.sessions.length > prevCount ? sessionStore.sessions[0] : null)

    if (found) {
      currentSession.value = found
      return true
    }
    await new Promise(r => setTimeout(r, 500))
  }
  return false
}
```

### 轮询 schema 预览

```js
let pollTimer = null

function startPolling(taskId) {
  pollTimer = setInterval(async () => {
    try {
      const data = await knowledgeAPI.getSchemaDraft(taskId)
      if (data.exists) {
        schemaDraft.value = data.content
      }
    } catch (e) { /* ignore */ }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}
```

### 检测 namespace 创建完成

```js
let detectTimer = null

function startDetecting(name) {
  detectTimer = setInterval(async () => {
    await knowledgeStore.fetchNamespaces()
    const found = knowledgeStore.namespaces.find(n => n.name === name)
    if (found && found.has_schema) {
      stopDetecting()
      state.value = 'done'
      await knowledgeStore.selectNamespace(name)
      emit('complete')
    }
  }, 3000)
}
```

## 实现步骤

| 步骤 | 内容 | 文件 |
|------|------|------|
| 1 | 后端：新增 schema-draft 端点，移除 generate-schema | `knowledge.py` |
| 2 | 前端：更新 api/knowledge.js | `api/knowledge.js` |
| 3 | 前端：更新 stores/knowledge.js | `stores/knowledge.js` |
| 4 | 前端：重写 CreateKBWizard.vue | `CreateKBWizard.vue` |
| 5 | 前端：清理 ViewContainer.vue（移除旧的 wizard 引用） | `ViewContainer.vue`（如需要） |
