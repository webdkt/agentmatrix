# How-To: Create Conversation

创建新对话。

## Web UI 方式

1. 点击 "New Conversation" 按钮
2. 选择 Agent
3. （可选）上传附件
4. 输入消息内容
5. 点击发送

## API 方式

```bash
curl -X POST http://localhost:8000/api/conversations \
  -H "Content-Type: application/json" \
  -d '{
    "agent_name": "MyAgent",
    "content": "你好"
  }'
```

返回 `task_id`，用于后续消息。

## 继续对话

使用相同的 `task_id`：

```bash
curl -X POST http://localhost:8000/api/conversations/continue \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "...",
    "content": "继续"
  }'
```

## 会话状态

Agent 会自动保存会话历史到：

```
.matrix/sessions/{agent}/{session}/history.json
```

下次可以继续之前的对话。
