# Email Proxy Service - 设计文档

## 概述

Email Proxy Service 是 AgentMatrix 系统中的邮件代理服务，连接外部标准邮件系统（IMAP/SMTP）和内部消息传递系统。

**实现文件**：`src/agentmatrix/services/email_proxy_service.py`

---

## 设计目的

### 1. 用户可访问性

- 用户可以使用任何邮件客户端（Gmail, Outlook, Apple Mail 等）与 Agent 交互
- 无需打开专门的 AgentMatrix Web UI
- 支持从任何设备（手机、平板、电脑）发送任务

### 2. 异步通信

- 邮件天然支持异步通信
- 用户发送邮件后可以离线
- Agent 处理完成后通过邮件通知用户
- 适合长时间运行的任务

### 3. 远程访问

- 仅需要邮件客户端即可访问
- 适合低带宽环境
- 不依赖网络浏览器

### 4. 通知推送

- Agent 可以发送邮件到用户邮箱
- 用户收到邮件后会被邮件客户端通知
- 支持附件（报告、文件等）

### 5. 工作流集成

- 用户可以在邮件中抄送 Agent
- 可以将邮件链转换为 Agent 任务
- 保持现有邮件工作习惯

---

## 架构设计

### 数据流

```
┌─────────────────────────────────────────────────────────┐
│                    External World                        │
│                 (User's Email Client)                    │
└─────────────────────────────────────────────────────────┘
                           │
                           │ IMAP (Pull) / SMTP (Push)
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Email Proxy Service                     │
│  ┌────────────────────┐         ┌────────────────────┐ │
│  │  IMAP Fetch Loop   │         │   SMTP Sender      │ │
│  │  - 每 30 秒检查    │         │  - 发送到外部邮箱  │ │
│  │  - 过滤发件人      │         │  - 添加 session tag│ │
│  │  - 解析 @mention   │         │  - 处理附件       │ │
│  └────────────────────┘         └────────────────────┘ │
│           │                                │             │
│           │ External → Internal            │ Internal → External
│           ▼                                ▼             │
│  ┌────────────────────────────────────────────────────┐ │
│  │              Email Converter                       │ │
│  │  - 格式转换              │ │
│  │  - Session ID 管理                               │ │
│  │  - 收件人识别 (@mention)                         │ │
│  │  - 附件处理                                      │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           │ dispatch() / receive()
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    PostOffice                            │
│  - 邮件路由和分发                                         │
│  - 维护 Agent 注册表                                     │
└─────────────────────────────────────────────────────────┘
                           │
                           │ Email delivery
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      Agents                               │
│  - User Agent (接收来自用户的邮件)                       │
│  - Other Agents (接收任务并处理)                         │
└─────────────────────────────────────────────────────────┘
```

### 核心组件

#### 1. IMAP Fetch Loop

**职责**：定期从用户邮箱拉取新邮件

**流程**：
1. 连接 IMAP 服务器
2. 获取未读邮件
3. 过滤发件人（只处理来自配置的用户邮箱的邮件）
4. 转换为内部 Email 格式
5. 发送到 PostOffice

**轮询间隔**：30 秒

#### 2. SMTP Sender

**职责**：将内部 Email 发送到用户邮箱

**流程**：
1. 检查是否需要发送到外部（metadata.is_external）
2. 获取原始发送者邮箱
3. 添加 session 标记到 subject
4. 生成外部 Message-ID
5. 构造 MIME 邮件
6. 处理附件
7. 通过 SMTP 发送

#### 3. Email Converter

**职责**：双向转换邮件格式

**External → Internal**：
- 解析 headers（From, To, Subject, Message-ID）
- 从 subject 提取 session_id
- 清理 subject（移除 session tag）
- 解析收件人（@mention 或默认 User）
- 确定 sender（user_mailbox → User）
- 解析 body 和 attachments
- 构造内部 Email 对象

**Internal → External**：
- 添加 session tag 到 subject
- 映射 sender → matrix_mailbox
- 映射 recipient → original_sender
- 转换内部格式为 MIME 邮件
- 添加附件

---

## 功能特性

### 1. @mention 路由

支持通过 @mention 指定收件 Agent：

**优先级**：
1. Subject 中的 @mention（最高优先级）
2. Body 第一行的 @mention
3. 默认发给 User Agent

**示例**：
```
Subject: @Researcher 查找最新 AI 论文
→ 收件人：Researcher Agent

Subject: 你好
Body: @Coder 写个函数
→ 收件人：Coder Agent

Subject: 普通邮件
→ 收件人：User Agent
```

### 2. Session 管理

**Session Tag 格式**：`[Session: {session_id}]`

**生命周期**：
```
用户发送第一封邮件
    → Email Proxy 生成新的 session_id
    → 添加到 subject: "[Session: abc123] @Researcher 任务"
    → 发送给 Agent

Agent 回复
    → 使用相同的 session_id
    → Subject 保持: "[Session: abc123] Re: 任务"
    → 发送回用户

用户再次回复
    → Email Proxy 识别已有的 session_id
    → 保持 session 连续性
    → 路由到同一个 Agent
```

**作用**：
- 维护对话上下文
- 确保 Agent 可以识别之前的对话
- 防止不同会话混淆

### 3. 附件处理

**接收附件（IMAP → Internal）**：
- 从 MIME 邮件中提取附件
- 下载到 User 的 attachments 目录
- 保存文件元数据（filename, size, container_path）

**发送附件（Internal → SMTP）**：
- 从 Agent 的 attachments 目录读取文件
- 添加到 MIME 邮件
- 通过 SMTP 发送

**路径映射**：
```
Internal Email
    metadata.attachments = [{
        'filename': 'report.pdf',
        'size': 12345,
        'container_path': '/work_files/attachments/report.pdf'
    }]

Host Filesystem
    {workspace_root}/agent_files/{agent_name}/work_files/{task_id}/attachments/report.pdf

External Email (MIME attachment)
    Content-Disposition: attachment; filename="report.pdf"
```

### 4. 安全过滤

**发件人过滤**：
- 只处理来自 `user_mailbox` 的邮件
- 其他发件人的邮件会被忽略
- 防止垃圾邮件和滥用

**Session 隔离**：
- 每个邮件链路有独立的 session_id
- 用户 A 的 session 不会混入用户 B 的 session

**@mention 白名单**：
- 只有注册的 Agent 才能接收邮件
- 不存在的 Agent 不会收到邮件

---

## 邮件转换示例

### External → Internal

**输入**（来自用户的邮件）：
```
From: user@gmail.com
To: matrix@gmail.com
Subject: [Session: abc123] @Researcher 查找最新 AI 论文

请帮我找最近一周的 AI 论文。
```

**输出**（内部 Email）：
```
Email(
    sender="User",
    recipient="Researcher",
    subject="查找最新 AI 论文",
    body="请帮我找最近一周的 AI 论文。",
    session_id="abc123",
    sender_session_id="abc123",
    receiver_session_id=None,
    metadata={
        'original_sender': 'user@gmail.com',
        'original_subject': '[Session: abc123] @Researcher 查找最新 AI 论文',
        'is_external': True
    }
)
```

### Internal → External

**输入**（Agent 的回复）：
```
Email(
    sender="Researcher",
    recipient="User",
    subject="Re: 查找最新 AI 论文",
    body="我找到了以下论文...",
    session_id="abc123",
    sender_session_id="abc123",
    receiver_session_id="xyz789",
    metadata={'is_external': True}
)
```

**输出**（发送到用户邮箱）：
```
From: matrix@gmail.com
To: user@gmail.com
Subject: [Session: abc123] Re: 查找最新 AI 论文
Message-ID: <new-message-id@matrix.gmail.com>

我找到了以下论文...
```

---

## 配置方式

### 通过 matrix_admin skill 配置

在 AgentMatrix 对话中使用：

```
config_email_proxy(
    enabled=True,
    matrix_mailbox="matrix@gmail.com",
    user_mailbox="your-email@gmail.com",
    smtp_host="smtp.gmail.com",
    smtp_port=587,
    smtp_user="matrix@gmail.com",
    smtp_password="abcd efgh ijkl mnop",  # Gmail 应用专用密码
    imap_host="imap.gmail.com",
    imap_port=993,
    imap_user="your-email@gmail.com",
    imap_password="wxyz abcd efgh ijkl"
)
```

### 配置存储

配置保存在 `system_config/email_proxy.yml`

---

## 生命周期管理

### 启动

```python
# 在 AgentMatrix.__init__() 中
if system_config.is_email_proxy_enabled():
    email_proxy = EmailProxyService(...)
    email_proxy_task = asyncio.create_task(email_proxy.start())
```

### 运行

- IMAP Fetch Loop 每 30 秒拉取一次新邮件
- SMTP Sender 在需要时发送邮件

### 停止

```python
# 在 save_matrix() 中
await email_proxy.stop()
if email_proxy_task:
    email_proxy_task.cancel()
```

---

## 安全考虑

### 1. 发件人过滤

只处理来自 `user_mailbox` 的邮件，防止：
- 垃圾邮件被转发到 Agent
- 未知发件人滥用系统

### 2. Session 隔离

每个邮件链路有独立的 session_id，防止：
- 用户 A 的 session 混入用户 B 的 session
- Agent 回复错乱

### 3. @mention 白名单

只有已注册的 Agent 能接收邮件，防止：
- 未授权的 Agent 被调用
- 路由到不存在的目标

---

## 常用邮箱配置

| 邮箱服务商 | SMTP 服务器 | SMTP 端口 | IMAP 服务器 | IMAP 端口 |
|-----------|------------|----------|------------|----------|
| Gmail | smtp.gmail.com | 587 | imap.gmail.com | 993 |
| Outlook | smtp-mail.outlook.com | 587 | outlook.office365.com | 993 |
| QQ邮箱 | smtp.qq.com | 587 | imap.qq.com | 993 |
| 163邮箱 | smtp.163.com | 465 | imap.163.com | 993 |

**重要提示**：
- Gmail/Outlook 必须使用"应用专用密码"，不能用账户密码
- QQ/163邮箱需要开启 SMTP/IMAP 服务并使用"授权码"

---

## 未来 TODO

### 1. IMAP IDLE 支持

**当前**：每 30 秒轮询一次 IMAP 服务器

**改进**：使用 IMAP IDLE 模式（服务器推送）

**优点**：
- 新邮件到达立即收到通知（实时性）
- 无需轮询（节省资源）

**限制**：
- 需要邮件服务器支持 IDLE（Gmail, Outlook 支持）

### 2. 附件大小限制

**当前**：没有附件大小限制

**改进**：添加附件大小检查

**建议**：限制为 25 MB

```python
MAX_ATTACHMENT_SIZE = 25 * 1024 * 1024  # 25 MB

if file_size > MAX_ATTACHMENT_SIZE:
    # 拒绝处理
```

**优点**：
- 防止内存占用过高
- 防止磁盘空间不足
- 防止 SMTP 发送超时

---

## 相关文档

- **使用指南**：`src/agentmatrix/skills/matrix_admin/README.md`
- **配置 API**：`config_email_proxy` skill function
- **实现源码**：`src/agentmatrix/services/email_proxy_service.py`

---

**最后更新**：2026-03-16
**维护人**：AgentMatrix Team
