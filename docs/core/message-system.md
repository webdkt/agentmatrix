# 消息系统详解

**版本**: v1.0
**最后更新**: 2026-03-19

---

## 📋 目录

- [Email模型](#email模型)
- [PostOffice](#postoffice)
- [消息传递流程](#消息传递流程)
- [消息持久化](#消息持久化)
- [附件系统](#附件系统)

---

## Email模型

### Email结构

```python
@dataclass
class Email:
    sender: str                         # 发件人
    recipient: str                      # 收件人
    subject: str                        # 主题
    body: str                           # 正文
    in_reply_to: Optional[str]          # 回复的邮件ID
    id: str                             # 唯一ID
    timestamp: datetime                 # 时间戳
    task_id: Optional[str]              # 任务ID
    sender_session_id: Optional[str]    # 发件人会话ID
    recipient_session_id: Optional[str] # 收件人会话ID
    metadata: Dict[str, Any]            # 元数据
```

### 字段说明

| 字段 | 类型 | 说明 | 用途 |
|------|------|------|------|
| `sender` | str | 发件人名称 | 标识发送方 |
| `recipient` | str | 收件人名称 | 标识接收方 |
| `subject` | str | 邮件主题 | 简短描述 |
| `body` | str | 邮件正文 | 主要内容 |
| `in_reply_to` | str | 回复的邮件ID | 构建回复链 |
| `id` | str | 唯一标识 | 邮件追踪 |
| `timestamp` | datetime | 发送时间 | 排序和查询 |
| `task_id` | str | 任务ID | 跨Agent任务追踪 |
| `sender_session_id` | str | 发件人会话ID | 发件方视角 |
| `recipient_session_id` | str | 收件人会话ID | 收件方视角 |
| `metadata` | dict | 元数据 | 附件等信息 |

### 创建Email

```python
from agentmatrix import Email

# 基本邮件
email = Email(
    sender="AgentA",
    recipient="AgentB",
    subject="Hello",
    body="How are you?"
)

# 带附件的邮件
email = Email(
    sender="AgentA",
    recipient="AgentB",
    subject="Report",
    body="Please find the report attached.",
    metadata={
        "attachments": [
            {
                "filename": "report.pdf",
                "path": "/path/to/report.pdf",
                "size": 1024000
            }
        ]
    }
)

# 回复邮件
reply = Email(
    sender="AgentB",
    recipient="AgentA",
    subject="Re: Hello",
    body="I'm fine, thanks!",
    in_reply_to=email.id
)
```

---

## PostOffice

### PostOffice职责

PostOffice是消息传递的中心，负责：

1. **Agent目录管理**
   - 维护所有注册的Agent
   - 提供Agent查找服务

2. **邮件队列处理**
   - 异步邮件分发
   - 队列管理

3. **邮件持久化**
   - 保存邮件到数据库
   - 邮件历史查询

### PostOffice API

```python
class PostOffice:
    def register_agent(self, agent: BaseAgent) -> None:
        """注册Agent"""

    def unregister_agent(self, agent_name: str) -> None:
        """注销Agent"""

    def send_email(self, email: Email) -> None:
        """发送邮件"""

    def get_agent_directory(self) -> Dict[str, BaseAgent]:
        """获取Agent目录"""

    def get_agent(self, agent_name: str) -> BaseAgent:
        """获取指定Agent"""
```

### 使用PostOffice

```python
from agentmatrix import AgentMatrix

# 创建Runtime
matrix = AgentMatrix()
matrix.start()

# 访问PostOffice
post_office = matrix.post_office

# 发送邮件
email = Email(
    sender="AgentA",
    recipient="AgentB",
    subject="Hello",
    body="How are you?"
)
post_office.send_email(email)

# 查询Agent
agent_b = post_office.get_agent("AgentB")
```

---

## 消息传递流程

### 发送流程

```
1. 创建Email
   AgentA创建Email对象

2. 发送到PostOffice
   AgentA → PostOffice.send_email(email)

3. 验证收件人
   PostOffice查找recipient

4. 加入队列
   PostOffice → AgentB.inbox

5. 持久化
   PostOffice → Database

6. 通知Agent
   PostOffice通知AgentB有新邮件
```

### 接收流程

```
1. Agent监听inbox
   AgentB检查inbox

2. 获取邮件
   AgentB.inbox.get()

3. 处理邮件
   AgentB.handle_email(email)

4. 发送回复（可选）
   AgentB → PostOffice → AgentA
```

### 异步处理

```python
import asyncio

class PostOffice:
    async def _process_email_queue(self):
        """异步处理邮件队列"""
        while self.running:
            email = await self.email_queue.get()
            await self._deliver_email(email)

    async def _deliver_email(self, email: Email):
        """投递邮件到收件人"""
        recipient = self.get_agent(email.recipient)
        if recipient:
            await recipient.inbox.put(email)
```

---

## 消息持久化

### 数据库存储

```python
class AgentMatrixDB:
    def save_email(self, email: Email) -> None:
        """保存邮件到数据库"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO emails
            (id, sender, recipient, subject, body, in_reply_to,
             timestamp, task_id, sender_session_id, recipient_session_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email.id, email.sender, email.recipient,
            email.subject, email.body, email.in_reply_to,
            email.timestamp, email.task_id,
            email.sender_session_id, email.recipient_session_id,
            json.dumps(email.metadata)
        ))
        self.conn.commit()

    def get_emails(self, agent_name: str) -> List[Email]:
        """获取Agent的所有邮件"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM emails
            WHERE sender = ? OR recipient = ?
            ORDER BY timestamp
        """, (agent_name, agent_name))
        rows = cursor.fetchall()
        return [self._row_to_email(row) for row in rows]
```

### 查询邮件

```python
# 获取会话邮件
emails = db.get_session_emails(session_id)

# 获取Agent邮件
emails = db.get_emails("AgentA")

# 获取任务相关邮件
emails = db.get_task_emails(task_id)

# 获取邮件回复链
thread = db.get_email_thread(email_id)
```

---

## 附件系统

### 附件结构

```python
{
    "filename": "document.pdf",
    "path": "/path/to/document.pdf",
    "size": 1024000,
    "mime_type": "application/pdf",
    "container_path": "/workspace/agent_files/{recipient}/work_files/{task_id}/attachments/{filename}"
}
```

### 附件路径

```
/workspace/agent_files/
├── {recipient}/
│   └── work_files/
│       └── {task_id}/
│           └── attachments/
│               ├── file1.pdf
│               ├── file2.txt
│               └── ...
```

### 添加附件

```python
email = Email(
    sender="AgentA",
    recipient="AgentB",
    subject="Document",
    body="Please find the document attached.",
    metadata={
        "attachments": [
            {
                "filename": "document.pdf",
                "path": "/path/to/document.pdf",
                "size": 1024000
            }
        ]
    }
)
```

### 访问附件

```python
# 获取附件列表
attachments = email.attachments

# 访问附件
for attachment in attachments:
    filename = attachment['filename']
    path = attachment['container_path']
    # 读取文件
    with open(path, 'rb') as f:
        content = f.read()
```

---

## 消息路由

### 点对点路由

```python
# AgentA → AgentB
email = Email(
    sender="AgentA",
    recipient="AgentB",
    subject="Direct Message",
    body="Hello"
)
```

### 广播路由

```python
# 发送给多个Agent
recipients = ["AgentB", "AgentC", "AgentD"]
for recipient in recipients:
    email = Email(
        sender="AgentA",
        recipient=recipient,
        subject="Broadcast",
        body="Hello everyone"
    )
    post_office.send_email(email)
```

### 任务路由

```python
# 使用task_id关联消息
task_id = str(uuid.uuid4())

# 初始消息
email1 = Email(
    sender="User",
    recipient="AgentA",
    subject="Start Task",
    body="Please process this task",
    task_id=task_id
)

# 后续消息（同一任务）
email2 = Email(
    sender="AgentA",
    recipient="AgentB",
    subject="Continue Task",
    body="Please continue the task",
    task_id=task_id
)
```

---

## 消息监控

### 监听消息

```python
class MessageMonitor:
    def __init__(self, post_office):
        self.post_office = post_office
        post_office.add_observer(self)

    def on_email_sent(self, email: Email):
        print(f"Sent: {email.sender} → {email.recipient}")

    def on_email_received(self, email: Email):
        print(f"Received: {email.sender} → {email.recipient}")
```

### 消息统计

```python
class MessageStats:
    def __init__(self):
        self.sent_count = 0
        self.received_count = 0
        self.error_count = 0

    def record_sent(self):
        self.sent_count += 1

    def record_received(self):
        self.received_count += 1

    def record_error(self):
        self.error_count += 1

    def get_stats(self):
        return {
            "sent": self.sent_count,
            "received": self.received_count,
            "errors": self.error_count
        }
```

---

## 最佳实践

### 1. 邮件主题规范

```python
# 好的主题
subject = "Task: Analyze data"  # 清晰描述内容

# 不好的主题
subject = "Hello"  # 不够具体
```

### 2. 邮件正文格式

```python
# 结构化正文
body = """
Task: Analyze data
Input: /path/to/data.csv
Output Format: JSON
Deadline: 2026-03-20

Please analyze the data and provide insights.
"""
```

### 3. 错误处理

```python
try:
    post_office.send_email(email)
except Exception as e:
    logger.error(f"Failed to send email: {e}")
    # 重试或记录错误
```

### 4. 性能优化

```python
# 批量发送
emails = [create_email(i) for i in range(100)]
for email in emails:
    post_office.send_email(email)  # 异步处理

# 或者使用批量API
post_office.send_emails(emails)
```

---

## 相关文档

- **[架构概览](./architecture.md)** - 系统架构
- **[组件参考](./component-reference.md)** - PostOffice API
- **[Agent系统](./agent-system.md)** - Agent通信
- **[核心概念](../concepts/CONCEPTS.md)** - Email概念定义

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
