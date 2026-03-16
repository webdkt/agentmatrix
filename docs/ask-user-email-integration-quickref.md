# Ask User 邮件集成 - 快速参考

## 概述

允许用户通过邮件回复 Agent 的 `ask_user` 请求，实现前端和邮件双渠道支持。

## 核心机制

### Subject 标记格式

```
{agent_name}问：{question} #ASK_USER#{agent_name}#{agent_session_id}#
```

**示例**：
```
Researcher问：你的预算是多少？ #ASK_USER#Researcher#abc123#
```

### 数据流

```
ask_user() 调用
    ↓
┌───────────┬───────────┐
│           │           │
前端事件   邮件通知    Future创建
           ↓           │
       用户收到邮件     │
           ↓           │
      ┌────┴────┐      │
      │         │      │
   Web UI  邮件回复    │
      │         │      │
      └────┬────┘      │
           │           │
           ↓    submit_user_input()
           ↓           ↓
      Future.set_result()
           ↓
      ask_user() 返回
```

## 文件修改

### 1. BaseAgent (`src/agentmatrix/agents/base.py`)

**新增**：
- `_send_ask_user_email(question, task_id)` - 发送 ask_user 邮件

**修改**：
- `ask_user(question)` - 添加邮件发送调用

### 2. EmailProxyService (`src/agentmatrix/services/email_proxy_service.py`)

**新增**：
- `_parse_ask_user_metadata(subject)` - 解析 ask_user 标记
- `_handle_ask_user_reply(email)` - 处理 ask_user 回复
- `_send_ask_user_feedback(email, success, message)` - 发送反馈邮件

**修改**：
- `convert_to_internal()` - 检测 ask_user 标记
- `fetch_external_emails()` - 特殊处理 ask_user 回复

## 使用方式

### Agent 调用 ask_user

```python
# 在 MicroAgent 中
answer = await self.root_agent.ask_user("请确认预算范围")
```

**自动触发**：
1. 前端显示对话框
2. 发送邮件给用户

### 用户回复

#### 方式 1：Web UI
1. 在对话框中输入回答
2. 点击提交

#### 方式 2：邮件回复
1. 回复 ask_user 邮件
2. 输入回答内容
3. 发送邮件（保留 Subject 中的标记）

**用户会收到反馈邮件**：
- ✅ 成功：回答已提交
- ❌ 失败：具体原因（Agent 不存在、不在等待状态等）

## 错误处理

| 场景 | 检测方式 | 反馈 |
|------|----------|------|
| Agent 不存在 | `agent_name not in directory` | "未找到 Agent" |
| 不在等待状态 | `RuntimeError` from `submit_user_input()` | "不在等待状态" |
| 双渠道回答 | `Future.done()` | "已经回答" |
| 空回复 | `body.strip() == ""` | "回复内容为空" |

## 测试验证

### 基本流程
```bash
# 运行测试脚本
python scripts/test_ask_user_email.py
```

### 手动测试
1. 启动 AgentMatrix
2. 让 Agent 调用 ask_user
3. 检查是否收到邮件
4. 回复邮件
5. 验证 Agent 收到回答
6. 检查反馈邮件

## 注意事项

1. **Subject 可见性**：`#ASK_USER#` 标记在用户邮箱中可见
2. **无超时**：ask_user 不设置超时，Agent 会一直等待
3. **向后兼容**：前端机制完全不变，邮件是额外通道
4. **统一入口**：前端和邮件都调用 `submit_user_input()`

## 相关文档

- [实现完成文档](./ask-user-email-integration-complete.md)
- [实现计划](./ask-user-email-integration-plan.md)
