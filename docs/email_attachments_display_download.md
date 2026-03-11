# 邮件附件显示和下载功能

## 实现时间
2026-03-11

## 实现概述
在 Web 应用界面中显示邮件的附件列表，并允许用户下载任意附件。

## 修改内容

### 1. 后端修改 (server.py)

#### 1.1 添加 FileResponse 导入
```python
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
```

#### 1.2 修改 get_session_emails API
在返回的邮件数据中添加 `attachments` 字段：

```python
emails_data.append({
    "id": email.id,
    "timestamp": email.timestamp.isoformat(),
    "sender": email.sender,
    "recipient": email.recipient,
    "subject": email.subject,
    "body": email.body,
    "in_reply_to": email.in_reply_to,
    "user_session_id": email.user_session_id,
    "is_from_user": getattr(email, 'is_from_user', False),
    "attachments": email.attachments  # 新增：附件列表
})
```

#### 1.3 新增下载附件 API
添加新的 API 端点用于下载附件：

```python
@app.get("/api/sessions/{session_id}/emails/{email_id}/attachments/{filename}")
async def download_email_attachment(session_id: str, email_id: str, filename: str):
    """下载邮件附件"""
```

**API 路径规则**：
- 路径: `/api/sessions/{session_id}/emails/{email_id}/attachments/{filename}`
- 根据邮件的 `recipient` 字段确定附件所在目录
- 附件物理路径: `{workspace_root}/agent_files/{recipient}/work_files/{user_session_id}/attachments/{filename}`

### 2. 前端修改 (web/index.html)

#### 2.1 在邮件卡片中显示附件列表
在邮件的 `message-body` 之后添加附件显示区域：

```html
<!-- Attachments -->
<div x-show="email.attachments && email.attachments.length > 0" class="mt-3 space-y-2">
    <div class="text-xs font-medium text-surface-500 uppercase tracking-wide">Attachments</div>
    <template x-for="(attachment, index) in email.attachments" :key="index">
        <div class="flex items-center justify-between p-2 rounded-lg bg-surface-50 hover:bg-surface-100 transition-colors group">
            <!-- 附件信息：文件名、大小 -->
            <!-- 下载按钮：悬停时显示 -->
        </div>
    </template>
</div>
```

**UI 特性**：
- 仅在邮件有附件时显示
- 显示每个附件的文件名和大小
- 悬停时显示下载按钮
- 点击下载按钮直接下载附件

## 附件路径规则

### 发送附件时
当 Agent A 发送带附件的邮件给 Agent B 时：
1. 附件从 A 的附件目录复制
2. 复制到 B 的附件目录

### 路径格式
```
{workspace_root}/agent_files/{agent_name}/work_files/{user_session_id}/attachments/{filename}
```

### 示例
- User 发送给 Mark 的附件 → `/agent_files/Mark/work_files/session123/attachments/report.pdf`
- Mark 发送给 User 的附件 → `/agent_files/User/work_files/session123/attachments/data.xlsx`

## 下载逻辑

无论谁发送的邮件，附件都保存在**收件人**的附件目录中：
- 用户发出的邮件 → 附件在目标 Agent 的目录
- 用户收到的邮件 → 附件在用户自己的目录

下载 API 会根据邮件的 `recipient` 字段自动定位到正确的目录。

## 测试

运行测试脚本：

```bash
python test_attachment_display.py
```

测试内容：
1. ✅ 验证邮件 API 返回 attachments 字段
2. ✅ 验证下载附件 API 工作正常

## 使用方法

### 1. 发送带附件的邮件
用户在 Web 界面创建新对话时，可以上传附件并发送。

### 2. 查看附件
在邮件列表中，带附件的邮件会显示附件列表，包括：
- 文件名
- 文件大小

### 3. 下载附件
- 悬停在附件上
- 点击下载按钮（悬停时出现）
- 浏览器会下载附件到本地

## 技术亮点

1. **零前端代码修改**：仅修改 HTML 模板，无需修改 JavaScript
2. **利用现有功能**：使用已有的 `formatFileSize` 函数
3. **优雅的 UI**：悬停显示下载按钮，不占用常驻空间
4. **正确的路径逻辑**：根据收件人自动定位附件目录

## 文件清单

### 修改的文件
1. `server.py` - 后端 API 修改
2. `web/index.html` - 前端附件显示

### 新增的文件
1. `test_attachment_display.py` - 测试脚本
2. `docs/email_attachments_display_download.md` - 本文档

## 总结

成功实现了邮件附件的显示和下载功能，用户现在可以：
- 在 Web 界面看到邮件的附件列表
- 下载任意附件
- 附件路径自动正确处理

功能完整，代码简洁，易于维护。
