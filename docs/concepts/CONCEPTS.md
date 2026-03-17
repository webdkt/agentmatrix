# AgentMatrix 核心概念文档

> 本文档介绍 AgentMatrix 系统中的核心概念和数据模型设计，帮助开发人员理解系统架构。

## 📋 目录

- [核心概念定义](#核心概念定义)
- [前端 vs 后端术语对照](#前端-vs-后端术语对照)
- [数据模型关系图](#数据模型关系图)
- [命名规范](#命名规范)

---

## 🎯 核心概念定义

### 1. Email (邮件)

**本质**：Agent 之间通信的基本单位

**后端定义** (`src/agentmatrix/core/message.py`):
```python
@dataclass
class Email:
    sender: str                         # 发件人 Agent 名称
    recipient: str                      # 收件人 Agent 名称
    subject: str                        # 邮件主题
    body: str                           # 邮件正文
    in_reply_to: Optional[str]          # 回复的邮件 ID
    id: str                             # 邮件唯一 ID
    timestamp: datetime                 # 发送时间
    task_id: Optional[str]              # 任务 ID（跨 Agent 的任务边界）
    sender_session_id: Optional[str]    # 发件人的 session_id
    recipient_session_id: Optional[str] # 收件人的 session_id
    metadata: Dict[str, Any]            # 元数据（附件等）
```

**前端实现**：
- 组件：`EmailList.vue`, `EmailItem.vue`, `EmailReply.vue`
- 路径：`agentmatrix-desktop/src/components/email/`
- 数据变量：`emails`
- API：`sessionAPI.sendEmail()`

**关键设计**：
- 所有邮件都携带 `task_id`，用于跨 Agent 的任务追踪和文件隔离
- `sender_session_id` 和 `recipient_session_id` 分别记录发送方和接收方的会话视角

---

### 2. Session (会话)

**本质**：单个 Agent/User 的邮件往来视图（主观视角）

**后端实现**：
- 数据库表：`emails` 表中的 `sender_session_id` 和 `recipient_session_id`
- API 端点：`/api/sessions`
- API 返回：`{ sessions: [...], total: N, page: 1 }`

**前端实现**：
- Store：`useSessionStore` (`stores/session.js`)
- API：`sessionAPI` (`api/session.js`)
- 组件：`SessionList.vue`, `SessionItem.vue`
- 路径：`agentmatrix-desktop/src/components/session/`

**数据结构**：
```javascript
{
  session_id: string,      // 会话唯一 ID
  subject: string,         // 第一封邮件的主题
  last_email_time: string, // 最后邮件时间
  participants: string[]   // 参与的 Agent 名称列表
}
```

**Session Data View 的构建**：
```sql
-- 任何一个 Agent 的 sessions 是两个 view 的 JOIN：
SELECT sender_session_id as session_id FROM emails WHERE sender = 'Me'
UNION
SELECT recipient_session_id as session_id FROM emails WHERE recipient = 'Me'
```

**特点**：
- A 和 B 对话 → 有 2 个 session（A 的 + B 的）
- B 收到 A 的信后，去联系 C → 对于 B，还在同一个 session；对于 A，看不到
- 每个 Agent 有自己的 session 视角

---

### 3. Task (任务)

**本质**：一个完整的工作任务/上下文范围（客观工作单元）

**后端实现**：
- Email 类中的 `task_id` 字段
- 用于关联同一个任务中的所有邮件（可能涉及多个 Agent）
- 附件存储路径：`/workspace/agent_files/{recipient}/work_files/{task_id}/attachments/`

**前端使用**：
- 邮件发送时的 `emailData.task_id`
- 附件打开时使用 `email.task_id`

**与 Session 的关系**：
- **Task（任务）**：客观的工作单元，可能涉及多个 Agent 和多个 Session
- **Session（会话）**：单个 Agent 的主观视角，每个 Agent 有自己的 Session Data View
- 一个 Task 可能包含多个 Session（A 的、B 的、C 的）
- 所有相关邮件都携带同一个 `task_id`，用于跨 Agent 的任务追踪和文件隔离

**示例**：
- User → Agent A → Agent B → Agent C
  - 这是一个 Task（`task_id="task_001"`）
  - User 的 Session：看到与 A 的对话
  - Agent A 的 Session：看到与 User 和 B 的对话
  - Agent B 的 Session：看到与 A 和 C 的对话
  - Agent C 的 Session：看到与 B 的对话

**Email 的双视角设计**：
```python
class Email:
    sender_session_id: str      # 发件人视角的 session
    recipient_session_id: str   # 收件人视角的 session
    task_id: str                # 所属任务（连接多个 session）
```

---

### 4. Agent (智能体)

**本质**：系统中的自主参与者，可以是 AI Agent 或人类用户

**后端实现**：
- 基类：`BaseAgent` (`src/agentmatrix/agents/base.py`)
- 子类：`UserProxy`, `DeepResearcher`, `MicroAgent` 等
- API 端点：`/api/agents`

**前端实现**：
- Store：`useAgentStore` (`stores/agent.js`)
- API：`agentAPI` (`api/agent.js`)
- 组件：`AgentStatusIndicator.vue`

**特殊 Agent**：
- **User (用户)**：人类用户，通过 Desktop 应用交互
- 其他 AI Agent：如 Planner, Coder, Researcher 等

**命名规范**：
- 后端：所有参与者都是 Agent，包括用户
- 前端：使用 `user_agent_name` 标识用户
- 数据库：使用 `agent_name` 字段
- API：路径参数使用 camelCase (`/api/agents/{agentName}`)

---

### 5. Attachment (附件)

**本质**：随邮件传输的文件

**后端实现**：
- 存储在 Email 的 `metadata['attachments']` 中
- 实际文件路径：`{matrix_world}/workspace/agent_files/{recipient}/work_files/{task_id}/attachments/{filename}`

**前端实现**：
- 工具函数：`getAttachmentIcon()`, `openAttachment()`
- UI 组件：`EmailItem.vue` 中的附件列表

**文件组织**：
- 使用 `task_id` 作为文件隔离边界
- 每个 recipient 有自己的工作目录
- 附件按任务分组存储

---

## 📊 前端 vs 后端术语对照

| 概念 | 后端术语 | 前端组件 | 前端变量 | API 路径 | 说明 |
|------|---------|---------|---------|---------|------|
| 邮件 | Email | Email* | email | /api/emails | 统一使用 Email |
| 会话 | Session | Session* | session | /api/sessions | 统一使用 Session |
| 智能体 | Agent | Agent | agent | /api/agents | 统一使用 Agent |
| 用户 | User/UserProxy | User | user | - | 统一使用 User |
| 附件 | attachments | attachments | attachments | - | 统一使用复数 |
| 任务 | task_id | taskId | taskId | - | 跨 Agent 任务边界 |
| 会话视图 | session_id | sessionId | sessionId | /api/sessions | 单 Agent 视角 |
| 收件人 | recipient | recipient | recipient | - | 统一使用 recipient |

**组件目录结构**：
```
agentmatrix-desktop/src/components/
├── email/              # 邮件相关组件
│   ├── EmailList.vue
│   ├── EmailItem.vue
│   └── EmailReply.vue
├── session/            # 会话相关组件
│   ├── SessionList.vue
│   └── SessionItem.vue
├── agent/              # Agent 相关组件
│   └── AgentStatusIndicator.vue
└── dialog/             # 对话框组件
    ├── AskUserDialog.vue
    └── NewEmailModal.vue
```

---

## 🔗 数据模型关系图

```
┌─────────────────────────────────────────────────────────────┐
│                        AgentMatrix 系统架构                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────┐
│   Desktop App   │  ← 用户交互界面
│  (Vue.js App)   │
└────────┬────────┘
         │ HTTP/WebSocket
         ↓
┌─────────────────┐
│  FastAPI Server │  ← 后端服务
└────────┬────────┘
         │
         ↓
┌─────────────────────────────────────┐
│         AgentMatrix Core            │
│  ┌───────────────────────────────┐  │
│  │  BaseAgent (基类)              │  │
│  │  ├── UserProxy (用户)          │  │
│  │  ├── DeepResearcher (研究员)   │  │
│  │  └── MicroAgent (通用 Agent)   │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  Email (通信单位)              │  │
│  │  ├── sender: Agent             │  │
│  │  ├── recipient: Agent          │  │
│  │  ├── sender_session_id: str    │  │ ← 发件人视角的 session
│  │  ├── recipient_session_id: str │  │ ← 收件人视角的 session
│  │  ├── task_id: str              │  │ ← 所属任务（连接多个 session）
│  │  └── metadata[attachments]     │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────┐
│      SQLite Database                │
│  ┌───────────────────────────────┐  │
│  │  emails 表                     │  │
│  │  ├── id, sender, recipient     │  │
│  │  ├── sender_session_id         │  │
│  │  ├── recipient_session_id      │  │
│  │  ├── task_id                   │  │
│  │  └── metadata (JSON)           │  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  scheduled_tasks 表            │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      Task vs Session 关系             │
│                                     │
│  Task (任务):                        │
│  ┌─────────────────────────────┐    │
│  │    task_001                  │    │
│  │  ┌─────────────────────┐    │    │
│  │  │ A → B (Email 1)      │    │    │
│  │  │   sender_session: A   │    │    │
│  │  │   recip_session: B    │    │    │
│  │  └─────────────────────┘    │    │
│  │  ┌─────────────────────┐    │    │
│  │  │ B → C (Email 2)      │    │    │
│  │  │   sender_session: B   │    │    │
│  │  │   recip_session: C    │    │    │
│  │  └─────────────────────┘    │    │
│  │  ┌─────────────────────┐    │    │
│  │  │ C → A (Email 3)      │    │    │
│  │  │   sender_session: C   │    │    │
│  │  │   recip_session: A    │    │    │
│  │  └─────────────────────┘    │    │
│  └─────────────────────────────┘    │
│                                     │
│  Session Data Views (主观视角):           │
│  - Agent A 看到: A↔B + A↔C          │
│  - Agent B 看到: A↔B + B↔C          │
│  - Agent C 看到: B↔C + A↔C          │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      MatrixWorld 文件系统            │
│  workspace/agent_files/             │
│    ├── {recipient}/work_files/      │
│    │   └── {task_id}/               │  ← Task 用作文件隔离边界
│    │       └── attachments/         │
│    │           └── {filename}       │
└─────────────────────────────────────┘
```

---

## 📝 命名规范

### 1. 核心实体命名

| 实体 | 命名 | 说明 |
|------|------|------|
| 邮件 | **Email** | 后端已定义，标准术语 |
| 会话 | **Session** | 后端 API/数据库已使用 |
| 智能体 | **Agent** | 后端已定义，清晰准确 |
| 用户 | **User** | 简洁明了 |
| 附件 | **Attachment** | 标准术语 |

### 2. 字段命名规范

#### 后端 (Python/snake_case)
```python
class Email:
    sender: str
    recipient: str                    # ✅ 使用 recipient（不是 receiver）
    subject: str
    body: str
    task_id: str                      # ✅ 任务 ID（跨 session 的任务边界）
    sender_session_id: str            # ✅ 发件人视角的 session
    recipient_session_id: str         # ✅ 收件人视角的 session
    attachments: List[Attachment]     # ✅ 复数形式
```

**使用场景**：
- `task_id`：用于文件隔离、跨 Agent 的任务追踪
- `sender_session_id`：发送方维护的会话上下文
- `recipient_session_id`：接收方维护的会话上下文

#### 前端 (JavaScript/camelCase)
```javascript
const email = {
  sender: string,
  recipient: string,              // ✅ 使用 recipient
  subject: string,
  body: string,
  taskId: string,                 // ✅ 任务 ID（跨 session 的任务边界）
  senderSessionId: string,        // ✅ 发件人视角的 session
  recipientSessionId: string,     // ✅ 收件人视角的 session
  attachments: array              // ✅ 复数形式
}
```

**使用场景**：
- `taskId`：用于附件路径、任务关联查询
- `senderSessionId`：发送方的会话视图
- `recipientSessionId`：接收方的会话视图

### 3. 组件命名规范

| 组件类型 | 命名模式 | 示例 |
|---------|---------|------|
| 邮件组件 | Email*.vue | EmailList.vue, EmailItem.vue, EmailReply.vue |
| 会话组件 | Session*.vue | SessionList.vue, SessionItem.vue |
| Agent 组件 | Agent*.vue | AgentStatusIndicator.vue |
| 对话框组件 | *Dialog.vue | AskUserDialog.vue, NewEmailModal.vue |

### 4. API 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 路径 | kebab-case | /api/sessions, /api/emails |
| 返回字段 | snake_case | `{ sessions: [...], total: 10 }` |
| 查询参数 | snake_case | ?page=1&per_page=20 |

### 5. 语言特定规范

| 语言 | 命名风格 | 示例 |
|------|---------|------|
| Python (后端) | snake_case | `agent_name`, `task_id`, `sender_session_id` |
| JavaScript (前端) | camelCase | `agentName`, `taskId`, `senderSessionId` |
| Vue 组件 | PascalCase | `EmailList.vue`, `SessionItem.vue` |
| API 路径 | kebab-case | `/api/sessions`, /api/emails` |

---

## 🎯 设计原则

### 核心原则

1. **一致性优先**：前后端使用相同的核心术语
2. **后端为准**：核心概念以后端定义为标准
3. **语言惯例**：遵循各语言命名规范（Python snake_case, JS camelCase）
4. **清晰区分**：`task_id` 和 `session_id` 各司其职，不冗余

### 关键设计决策

✅ **使用 `Email` 而非 `Message`**
✅ **使用 `Session` 而非 `Conversation`**
✅ **使用 `recipient` 而非 `receiver`**
✅ **保持 `task_id` 和 `session_id` 的分工关系**
   - `task_id`：跨 Agent 的任务边界，用于文件隔离
   - `session_id`：单个 Agent 的会话视图，主观视角

### Task vs Session 的分工

| 维度 | Task（任务） | Session（会话） |
|------|-------------|----------------|
| 视角 | 客观工作单元 | 主观视图 |
| 范围 | 跨 Agent | 单 Agent |
| 用途 | 任务追踪、文件隔离 | 会话列表、对话视图 |
| 关系 | 一个 Task 可包含多个 Session | 一个 Session 属于某个 Agent |

---

**文档版本**: v2.0
**创建时间**: 2025-03-17
**最后更新**: 2025-03-17
**维护者**: AgentMatrix Team
