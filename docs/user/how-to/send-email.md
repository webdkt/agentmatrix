# How-To: Send Email with Attachments

发送带附件的邮件。

## 发送邮件

在对话中要求 Agent 发送邮件：

```
请发送邮件给 user@example.com，
主题是 "周报"，
内容是 "本周工作总结..."
```

Agent 会调用 `send_email` action。

## 添加附件

### 方式一：Web UI 上传

1. 在 "New Conversation" 对话框
2. 点击附件按钮选择文件
3. 或拖放文件到上传区域

附件会自动发送给 Agent。

### 方式二：Agent 转发

Agent 可以转发收到的附件：

```
请转发附件 report.pdf 给 manager@example.com
```

## 附件存储

附件保存在：

```
workspace/agent_files/{agent}/work_files/{task}/attachments/
```

每个会话有独立的附件目录。

## 附件限制

- 大小限制：配置在 `server.py`
- 类型限制：默认允许常见文档类型

## 下载附件

收到带附件的邮件时：
1. Web UI 显示附件列表
2. 点击下载按钮

附件从 Agent 的 attachments 目录读取。
