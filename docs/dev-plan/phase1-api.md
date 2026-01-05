# AgentMatrix Phase 1 API 开发计划

> **版本**: 1.0
> **更新日期**: 2026-01-05
> **基于文档**: `docs/ui-functions.md`

## 1. 概述

本文档定义了 AgentMatrix Phase 1 的所有必需API端点，基于实际UI功能需求设计。

### 1.1 核心概念

#### User Session（用户会话）
- **定义**: 用户的一次对话任务，对应一个唯一的 session_id
- **存储位置**: `workspace/.matrix/user_sessions.json`
- **数据格式**:
```json
{
  "e4362eb8-9394-4284-8546-566a20bc935d": {
    "name": "能力询问 2026-01-04",
    "last_email_time": "2026-01-04 19:03:50.301214"
  }
}
```

#### Email（邮件/消息）
- **定义**: Agent之间通信的基本单位
- **关键规则**: 只显示发件人或收件人是 `User` 的邮件
- **显示方式**: 聊天对话样式（User发送的靠左，接收的靠右）

#### Session共享目录
- **路径**: `workspace/{session_id}/shared/`
- **用途**: Session相关的文件存储和共享
- **操作**: 浏览文件树、上传文件、下载文件

### 1.2 UI布局与API对应关系

| UI组件 | 对应API | 数据来源 |
|--------|---------|----------|
| **左侧: Conversation Topic List** | `GET /api/sessions` | `user_sessions.json` |
| **中间: Conversation History View** | `GET /api/sessions/{id}/emails` | PostOffice/Database |
| **右侧: Session File View** | `GET /api/sessions/{id}/files` | 文件系统 |
| **Wizard: LLM配置** | `POST /api/config/llm` | `agents/llm_config.json` |

---

## 2. Priority 1: MUST-HAVE APIs

### 2.1 LLM配置API（已实现 ✅）

#### GET /api/config/status
检查系统配置状态

**状态**: ✅ 已实现

**响应**:
```json
{
  "configured": false,
  "matrix_world_dir": "/path/to/MatrixWorld",
  "agents_dir": "/path/to/MatrixWorld/agents",
  "workspace_dir": "/path/to/MatrixWorld/workspace"
}
```

---

#### POST /api/config/llm
保存LLM配置

**状态**: ✅ 已实现

**请求Body**:
```json
{
  "default_llm": {
    "url": "https://api.deepseek.com/chat/completions",
    "api_key": "DEEPSEEK_API_KEY",
    "model_name": "deepseek-reasoner"
  },
  "default_slm": {
    "url": "https://api.deepseek.com/chat/completions",
    "api_key": "DEEPSEEK_API_KEY",
    "model_name": "deepseek-reasoner"
  }
}
```

**响应**:
```json
{
  "success": true,
  "message": "LLM configuration saved successfully"
}
```

---

### 2.2 User Session管理API

#### GET /api/sessions
获取所有User Session列表（用于Conversation Topic List）

**状态**: 🔲 待实现

**优先级**: **HIGH** - 核心功能

**业务逻辑**:
1. 读取 `workspace/.matrix/user_sessions.json`
2. 按照最后邮件时间降序排列
3. 返回所有session信息

**请求参数**: 无

**响应**:
```json
{
  "success": true,
  "sessions": [
    {
      "session_id": "bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1",
      "name": "查询14117法案背景 2026-01-04",
      "last_email_time": "2026-01-04T19:07:11.320544",
      "last_email_time_relative": "2小时前"
    },
    {
      "session_id": "e4362eb8-9394-4284-8546-566a20bc935d",
      "name": "能力询问 2026-01-04",
      "last_email_time": "2026-01-04T19:03:50.301214",
      "last_email_time_relative": "3小时前"
    }
  ],
  "total_count": 2
}
```

**错误响应**:
```json
{
  "success": false,
  "error": {
    "code": "SESSION_FILE_NOT_FOUND",
    "message": "user_sessions.json file not found"
  }
}
```

---

#### GET /api/sessions/{session_id}
获取单个Session的详细信息

**状态**: 🔲 待实现

**优先级**: MEDIUM

**路径参数**:
- `session_id` (string): Session UUID

**响应**:
```json
{
  "success": true,
  "session": {
    "session_id": "bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1",
    "name": "查询14117法案背景 2026-01-04",
    "last_email_time": "2026-01-04T19:07:11.320544",
    "shared_dir_path": "workspace/bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1/shared",
    "email_count": 15
  }
}
```

---

### 2.3 邮件/对话管理API

#### GET /api/sessions/{session_id}/emails
获取指定Session的所有邮件（用于Conversation History View）

**状态**: 🔲 待实现

**优先级**: **HIGH** - 核心功能

**业务逻辑**:
1. 查询所有发件人或收件人是 `User` 的邮件
2. 关联到指定的session_id
3. 按时间戳升序排列（最早的在前面）
4. 标记每封邮件是"发送"还是"接收"

**路径参数**:
- `session_id` (string): Session UUID

**查询参数**:
- `limit` (int, 可选): 每页数量，默认50
- `offset` (int, 可选): 偏移量，默认0
- `sort_order` (string, 可选): 排序方式，`asc`或`desc`，默认`asc`

**响应**:
```json
{
  "success": true,
  "emails": [
    {
      "id": "email-uuid-1",
      "user_session_id": "bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1",
      "sender": "User",
      "recipient": "Planner",
      "subject": "New Project",
      "body": "请帮我查询14117法案的背景信息",
      "in_reply_to": "some-id-1",
      "timestamp": "2026-01-04T19:03:50.301214",
      "is_from_user": true,
      "attachments": []
    },
    {
      "id": "email-uuid-2",
      "user_session_id": "bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1",
      "sender": "Planner",
      "recipient": "User",
      "subject": "Re: New Project",
      "body": "好的，我将为你查询14117法案的背景信息...",
      "timestamp": "2026-01-04T19:05:23.456789",
      "is_from_user": false,
      "attachments": ["research_notes.txt"]
    }
  ],
  "pagination": {
    "total_count": 15,
    "limit": 50,
    "offset": 0,
    "has_more": false
  }
}
```

**实现说明**:
- 需要集成 AgentMatrix 的 PostOffice 或 Email 数据库
- 需要判断邮件的发件人或收件人是否是 `User`
- `is_from_user` 字段用于前端判断消息显示在左侧还是右侧

---

#### POST /api/sessions/{session_id}/emails/
发邮件（用于Conversation History View中的“新邮件”或者"Reply"功能）

**状态**: 🔲 待实现

**优先级**: **HIGH** - 核心交互功能

**业务逻辑**:
1. 用户点击某封邮件的"Reply"按钮/或者发送新邮件
2. 弹出输入框，用户输入回复内容
3. 构造新邮件，发件人是User，收件人是原邮件的发件人（Reply)或者选择输入名字
4. 通过 PostOffice 发送邮件
5. 通过 WebSocket 推送新邮件通知

**路径参数**:
- `session_id` (string): Session UUID

**请求Body**:
```json
{
  "user_session_id": "bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1",
  "sender": "User",
  "recipient": "Planner",
  "subject": "Re: New Project",
  "body": "好的，我将为你查询14117法案的背景信息...",
  "in_reply_to": "id nor None"
}
```

**响应**:
```json
{
  "success": true,
  "id": "email-uuid-3",
  "message": "Reply sent successfully",
  "timestamp": "2026-01-04T19:10:00.123456"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": {
    "code": "RECIPIENT_NOT_FOUND",
    "message": "Original email recipient not found"
  }
}
```

---

### 2.4 文件浏览与管理API

#### GET /api/sessions/{session_id}/files
获取Session共享目录的文件树（用于Session File View）

**状态**: 🔲 待实现

**优先级**: **HIGH** - 核心功能

**业务逻辑**:
1. 读取 `workspace/{session_id}/shared/` 目录
2. 递归构建文件树结构
3. 返回树形JSON结构

**路径参数**:
- `session_id` (string): Session UUID

**查询参数**:
- `path` (string, 可选): 相对路径，用于获取子目录，默认根目录

**响应**:
```json
{
  "success": true,
  "session_id": "bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1",
  "base_path": "workspace/bfb4d2fb-fe59-4cb0-a87a-63a57626fcb1/shared",
  "current_path": "",
  "files": [
    {
      "name": "research_notes.txt",
      "path": "research_notes.txt",
      "type": "file",
      "size": 2048,
      "modified_at": "2026-01-04T19:07:11.320544",
      "is_directory": false
    },
    {
      "name": "documents",
      "path": "documents",
      "type": "directory",
      "is_directory": true,
      "children": [
        {
          "name": "report.pdf",
          "path": "documents/report.pdf",
          "type": "file",
          "size": 1048576,
          "modified_at": "2026-01-04T19:08:00.000000",
          "is_directory": false
        }
      ]
    }
  ]
}
```

**实现说明**:
- 使用 `os.walk()` 或 `pathlib.Path.rglob()` 递归遍历目录
- 限制递归深度，避免性能问题（建议最多3层）
- 返回相对路径，便于前端渲染

---

#### POST /api/sessions/{session_id}/files/upload
上传文件到Session共享目录

**状态**: 🔲 待实现

**优先级**: **HIGH** - 核心交互功能

**业务逻辑**:
1. 接收multipart/form-data文件上传
2. 保存到 `workspace/{session_id}/shared/` 目录
3. 通过WebSocket推送文件上传通知

**路径参数**:
- `session_id` (string): Session UUID

**请求**: multipart/form-data
- `file`: 文件对象
- `subpath` (string, 可选): 子目录路径

**响应**:
```json
{
  "success": true,
  "file": {
    "name": "uploaded_file.pdf",
    "path": "uploaded_file.pdf",
    "size": 524288,
    "uploaded_at": "2026-01-04T19:15:00.000000"
  },
  "message": "File uploaded successfully"
}
```

**错误响应**:
```json
{
  "success": false,
  "error": {
    "code": "UPLOAD_FAILED",
    "message": "Failed to save file"
  }
}
```

---

#### GET /api/sessions/{session_id}/files/download
下载文件

**状态**: 🔲 待实现

**优先级**: MEDIUM

**路径参数**:
- `session_id` (string): Session UUID

**查询参数**:
- `path` (string, 必需): 文件相对路径

**响应**: 文件流（application/octet-stream）

---

### 2.5 系统状态API

#### GET /api/system/status
获取系统运行状态

**状态**: 🔲 待完善

**优先级**: LOW

**响应**:
```json
{
  "status": "running",
  "version": "0.1.4",
  "uptime": "2 hours 15 minutes",
  "active_websockets": 3,
  "matrix_world_dir": "/path/to/MatrixWorld",
  "agents_count": 5,
  "sessions_count": 10
}
```

---

## 3. 数据模型规范

### 3.1 User Session Model

```typescript
interface UserSession {
  session_id: string;        // UUID
  name: string;              // Session名称
  last_email_time: string;   // ISO 8601时间戳
}
```

### 3.2 Email Model

```typescript
interface Email {
  id: string;          // UUID
  user_session_id: string;        // 关联的Session ID
  in_reply_to: string;          // 回复的邮件UUID
  sender: string;              // 发件人Agent名称
  recipient: string;                // 收件人Agent名称
  subject: string;           // 邮件主题
  body: string;              // 邮件正文
  timestamp: string;         // ISO 8601时间戳
  is_from_user: boolean;     // 是否是User发送的

}
```

### 3.3 File Model

```typescript
interface FileItem {
  name: string;              // 文件/目录名
  path: string;              // 相对路径
  type: 'file' | 'directory'; // 类型
  size?: number;             // 文件大小（字节）
  modified_at: string;       // 修改时间
  is_directory: boolean;     // 是否是目录
  children?: FileItem[];     // 子文件/目录（如果是目录）
}
```

---

## 4. WebSocket事件规范

TBD

---

## 5. 实施计划

### 阶段1: 核心数据访问（最小可用版本）

**目标**: 实现基本的数据读取，让UI能显示内容

1. ✅ `GET /api/config/status` - 已实现
2. ✅ `POST /api/config/llm` - 已实现
3. 🔲 `GET /api/sessions` - 读取user_sessions.json
4. 🔲 `GET /api/sessions/{session_id}/emails` - 查询Email数据库
5. 🔲 `GET /api/sessions/{session_id}/files` - 文件系统遍历

### 阶段2: 用户交互功能

**目标**: 实现基本的用户交互

6. 🔲 `POST /api/sessions/{session_id}/email` - 回复邮件
7. 🔲 `POST /api/sessions/{session_id}/files/upload` - 文件上传
8. 🔲 WebSocket集成 - 实时事件推送

### 阶段3: 完善和优化

**目标**: 错误处理、性能优化、用户体验

9. 🔲 `GET /api/sessions/{session_id}/files/download` - 文件下载
10. 🔲 `GET /api/system/status` - 系统状态监控
11. 🔲 错误处理和验证
12. 🔲 性能优化（分页、缓存）

---

## 6. 技术实现要点

### 6.1 读取user_sessions.json

```python
import json
from pathlib import Path

def load_user_sessions(workspace_dir: Path) -> dict:
    sessions_file = workspace_dir / ".matrix" / "user_sessions.json"
    if not sessions_file.exists():
        return {}

    with open(sessions_file, 'r', encoding='utf-8') as f:
        return json.load(f)
```

### 6.2 查询Email（集成PostOffice）

```python
# 需要集成 AgentMatrix 的 PostOffice
async def get_session_emails(session_id: str, limit: int = 50, offset: int = 0):
    # 从PostOffice或数据库查询
    # 过滤条件: from='User' OR to='User'
    # 排序: timestamp ASC
    pass
```

### 6.3 文件系统遍历

```python
from pathlib import Path

def build_file_tree(session_id: str, base_dir: Path, relative_path: str = ""):
    shared_dir = base_dir / session_id / "shared"
    target_path = shared_dir / relative_path if relative_path else shared_dir

    if not target_path.exists():
        return []

    files = []
    for item in target_path.iterdir():
        # 构建文件树结构
        pass

    return files
```

### 6.4 文件上传

```python
from fastapi import UploadFile

async def upload_file(session_id: str, file: UploadFile, subpath: str = ""):
    shared_dir = base_dir / session_id / "shared"
    target_path = shared_dir / subpath / file.filename

    # 保存文件
    with open(target_path, 'wb') as f:
        content = await file.read()
        f.write(content)

    # 通过WebSocket推送通知
    await broadcast_file_upload_event(session_id, file.filename)
```

---

## 7. API响应格式规范

### 7.1 成功响应

```json
{
  "success": true,
  "data": { ... }
}
```

### 7.2 错误响应

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": { ... }
  }
}
```

### 7.3 常见错误码

| 错误码 | 说明 |
|--------|------|
| `SESSION_NOT_FOUND` | Session不存在 |
| `SESSION_FILE_NOT_FOUND` | user_sessions.json不存在 |
| `EMAIL_NOT_FOUND` | 邮件不存在 |
| `FILE_NOT_FOUND` | 文件不存在 |
| `INVALID_PATH` | 无效的文件路径 |
| `UPLOAD_FAILED` | 文件上传失败 |
| `RECIPIENT_NOT_FOUND` | 邮件收件人不存在 |

---

## 8. 前端集成示例

### 8.1 获取Session列表

```javascript
// web/js/api.js
async getSessions() {
    return this.request('/api/sessions');
}

// 使用
const response = await API.getSessions();
const sessions = response.sessions; // Array of UserSession
```

### 8.2 获取邮件列表

```javascript
async getSessionEmails(sessionId, limit = 50, offset = 0) {
    return this.request(`/api/sessions/${sessionId}/emails?limit=${limit}&offset=${offset}`);
}

// 使用
const response = await API.getSessionEmails(sessionId);
const emails = response.emails; // Array of Email
```

### 8.3 回复邮件

```javascript
async replyEmail(sessionId, toEmailId, content) {
    return this.request(`/api/sessions/${sessionId}/email`, {
        method: 'POST',
        body: JSON.stringify({
            TODO: Need Update
        })
    });
}
```

---

## 9. 版本历史

| 版本 | 日期 | 变更说明 |
|------|------|----------|
| 1.0  | 2026-01-05 | 初始版本，基于ui-functions.md设计Phase 1 API |

---

## 附录A: 与现有代码的集成

### A.1 AgentMatrix Runtime集成

- 需要在 `server.py` 的 lifespan 中初始化 AgentMatrix Runtime
- 访问 `agentMatrix.post_office` 来查询和发送邮件
- 使用 `agentMatrix` 的其他组件来获取Agent状态

### A.2 数据库集成

- PostOffice 可能使用SQLite存储邮件
- 需要查询 `emails` 表，按 `from` 和 `to` 字段过滤
- Session ID可能存储在邮件的metadata中

---

## 附录B: 未来扩展（Phase 2+）

- B.1 创建新Session API
- B.2 Session标题编辑API
- B.3 邮件搜索API
- B.4 Agent状态监控API
- B.5 World View相关API
- B.6 Matrix Setting相关API
