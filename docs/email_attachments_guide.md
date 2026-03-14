# Email 附件系统使用指南

## 概述

Email 附件系统允许 User 通过 web 应用发送带附件的邮件给 Agent。附件会被安全地保存在 `.matrix/email_attachments/` 目录中。

## 架构

### 核心组件

1. **Email 类** (`src/agentmatrix/core/message.py`)
   - 添加了 `metadata` 字段用于存储附件信息
   - 添加了 `attachments` 属性用于访问附件列表

2. **AttachmentManager** (`src/agentmatrix/core/attachment_manager.py`)
   - 管理附件的临时上传和永久存储
   - 临时目录：`.matrix/temp_uploads/{task_id}/`
   - 共享存储：`.matrix/email_attachments/{task_id}/{email_id}/`

3. **API 端点** (`server.py`)
   - 扩展了 `POST /api/sessions/{session_id}/emails` 端点
   - 支持 `multipart/form-data` 文件上传

4. **前端 API** (`web/js/api.js`)
   - 扩展了 `sendEmail()` 方法支持文件上传
   - 自动检测是否有文件，选择使用 FormData 或 JSON

## 使用方法

### 后端 API

#### 发送带附件的邮件

```bash
curl -X POST http://localhost:8000/api/sessions/new/emails \
  -F "recipient=Mark" \
  -F "subject=报告" \
  -F "body=请查收附件" \
  -F "attachments=@/path/to/document.pdf"
```

#### 响应示例

```json
{
  "success": true,
  "task_id": "abc-123-def",
  "message": "Email sent successfully",
  "attachments_count": 1
}
```

### 前端 JavaScript

#### 基本用法

```javascript
// 获取文件
const fileInput = document.getElementById('fileInput');
const files = Array.from(fileInput.files);

// 准备邮件数据
const emailData = {
  recipient: 'Mark',
  subject: '报告',
  body: '请查收附件'
};

// 发送带附件的邮件
API.sendEmail('new', emailData, files)
  .then(response => {
    console.log('Email sent:', response);
    console.log('Attachments:', response.attachments_count);
  })
  .catch(error => {
    console.error('Failed to send email:', error);
  });
```

#### HTML 示例

```html
<input type="file" id="fileInput" multiple>
<button onclick="sendEmailWithAttachments()">发送邮件</button>

<script>
function sendEmailWithAttachments() {
  const files = Array.from(document.getElementById('fileInput').files);

  const emailData = {
    recipient: 'Mark',
    subject: '报告',
    body: '请查收附件'
  };

  API.sendEmail('new', emailData, files)
    .then(response => {
      alert(`邮件发送成功！包含 ${response.attachments_count} 个附件`);
    })
    .catch(error => {
      alert('发送失败：' + error.message);
    });
}
</script>
```

### 后端 Python

#### 创建带附件的邮件

```python
from agentmatrix.core.message import Email
from agentmatrix.core.attachment_manager import AttachmentManager

# 创建 AttachmentManager
attachment_manager = AttachmentManager()

# 准备附件信息
attachments = [
    {
        'file_id': 'file_123',
        'filename': 'document.pdf',
        'size': 1024,
        'path': '/path/to/document.pdf'
    }
]

# 创建带附件的邮件
email = Email(
    sender='User',
    recipient='Agent',
    subject='Report',
    body='Please check the attachment',
    metadata={'attachments': attachments}
)

# 访问附件
print(f"Attachments: {len(email.attachments)}")
for attachment in email.attachments:
    print(f"  - {attachment['filename']} ({attachment['size']} bytes)")
```

#### 附件文件操作

```python
# 保存临时上传文件
temp_info = attachment_manager.save_temp_upload(
    task_id='session_123',
    filename='document.pdf',
    content=file_content
)

# 保存到共享存储
attachment_info = attachment_manager.save_attachment(
    task_id='session_123',
    email_id='email_456',
    file_id=temp_info['file_id'],
    filename='document.pdf',
    temp_path=temp_info['temp_path']
)

# 获取附件路径
path = attachment_manager.get_attachment_path(
    task_id='session_123',
    email_id='email_456',
    filename='document.pdf'
)

# 检查附件是否存在
exists = attachment_manager.attachment_exists(
    task_id='session_123',
    email_id='email_456',
    filename='document.pdf'
)
```

## 数据库集成

### 保存带附件的邮件

```python
# 创建带附件的邮件
email = Email(
    sender='User',
    recipient='Agent',
    subject='Test',
    body='Test body',
    metadata={'attachments': [{'filename': 'doc.pdf', 'size': 1024}]}
)

# 保存到数据库（metadata 会自动序列化为 JSON）
db.log_email(email)

# 从数据库恢复（metadata 会自动反序列化）
records = db.get_user_session_emails('session_id')
for record in records:
    import json
    metadata = json.loads(record['metadata'])
    print(f"Attachments: {metadata.get('attachments', [])}")
```

## 文件存储结构

```
.matrix/
├── temp_uploads/           # 临时上传目录
│   └── {task_id}/  # 用户会话目录
│       └── {file_id}_{filename}  # 临时文件
└── email_attachments/      # 永久附件存储
    └── {task_id}/  # 用户会话目录
        └── {email_id}/     # 邮件目录
            └── {filename}  # 附件文件
```

## 安全特性

1. **文件名清理**：自动移除危险字符（如 `..`, `/`, `\`）
2. **路径验证**：确保文件保存在指定目录内
3. **临时文件清理**：保存到共享存储后自动清理临时文件
4. **文件大小限制**：可通过 FastAPI 配置限制上传文件大小

## 测试

运行测试：

```bash
python tests/test_email_attachments.py
```

测试覆盖：
- Email 类的附件功能
- AttachmentManager 的所有方法
- 数据库集成

## 限制和注意事项

1. **当前版本不支持**：
   - ❌ Agent 发送附件
   - ❌ Agent 下载附件
   - ❌ 附件验证（文件类型、大小等）
   - ❌ 附件预览

2. **性能考虑**：
   - 大文件上传可能影响性能
   - 建议在生产环境中添加文件大小限制
   - 考虑使用异步文件处理

3. **存储管理**：
   - 附件会永久保存，需要定期清理
   - 建议实现附件删除功能
   - 考虑实现存储配额

## 下一步

1. 添加文件类型验证
2. 实现附件大小限制
3. 支持 Agent 发送附件
4. 实现附件删除功能
5. 添加附件预览功能
6. 实现存储配额管理
