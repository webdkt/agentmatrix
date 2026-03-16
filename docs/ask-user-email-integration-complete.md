# Ask User 邮件集成实现完成

## 实现概览

本次实现为 AgentMatrix 的 `ask_user` 机制添加了邮件回复支持，用户现在可以通过邮件或 Web UI 两种方式回答 Agent 的提问。

## 实现时间

2026-03-16

## 修改的文件

### 1. src/agentmatrix/agents/base.py

**新增方法**：
- `_send_ask_user_email(question: str, task_id: str)`: 发送 ask_user 邮件通知

**修改方法**：
- `ask_user(question: str)`: 添加了邮件发送调用

**关键实现细节**：
- Subject 格式：`{agent_name}问：{question} #ASK_USER#{agent_name}#{agent_session_id}#`
- 使用 `#ASK_USER#` 标记使邮件回复可被识别
- 邮件正文包含问题内容和回复说明
- 直接访问 `self.runtime.email_proxy`（无需 get_service 方法）

### 2. src/agentmatrix/services/email_proxy_service.py

**新增方法**：
- `_parse_ask_user_metadata(subject: str) -> Optional[dict]`: 解析 subject 中的 ask_user 标记
- `_handle_ask_user_reply(internal_email: Email)`: 处理 ask_user 回复邮件
- `_send_ask_user_feedback(original_email: Email, success: bool, message: str)`: 发送反馈邮件

**修改方法**：
- `convert_to_internal(raw_email)`: 添加 ask_user 标记检测和 body/attachments 提取（修复原有 bug）
- `fetch_external_emails()`: 添加 ask_user 回复特殊处理分支

**关键实现细节**：
- 使用正则表达式 `r'#ASK_USER#([^#]+)#([^#]+)#'` 提取 agent_name 和 agent_session_id
- 直接调用 Agent 的 `submit_user_input()` 方法（不通过 PostOffice）
- 捕获 `RuntimeError` 异常处理重复回答和超时情况
- 所有邮件回复都发送反馈（成功或失败）

## 数据流设计

### 正常流程

```
1. Agent 调用 ask_user("预算多少？")
   ├─> 前端：显示对话框
   └─> 邮件：发送 "Researcher问：预算多少？ #ASK_USER#Researcher#abc123#"

2. 用户选择渠道回答
   ├─> 选项 A：Web UI
   │   └─> submit_user_input("5000元")
   │       └─> Future.set_result("5000元")
   │
   └─> 选项 B：邮件回复
       └─> Email Proxy 识别 #ASK_USER#
           └─> 解析 agent_name=Researcher
               └─> 调用 agent.submit_user_input("5000元")
                   └─> 检查 Future 状态
                       └─> Future.set_result("5000元")
                           └─> Email Proxy 发送反馈："回答已收到"

3. ask_user() 返回 "5000元"
   └─> Agent 继续执行
```

### 边界情况处理

| 情况 | 检测条件 | 处理方式 |
|------|----------|----------|
| 双渠道回答 | submit_user_input() 抛出 RuntimeError | Email Proxy 捕获异常，发送反馈："已回答" |
| Agent 不存在 | agent_name not in directory | Email Proxy 直接发送反馈："未找到 Agent" |
| 不在等待状态 | submit_user_input() 抛出 RuntimeError | Email Proxy 捕获异常，发送反馈："不在等待状态" |
| 回复内容为空 | body.strip() == "" | Email Proxy 发送反馈："回复内容为空" |

## 安全考虑

### 1. 发件人验证
- Email Proxy 已有发件人过滤（只处理 user_mailbox）
- 无需额外验证

### 2. 状态检查
- `submit_user_input()` 已包含 Future 状态检查
- Email Proxy 捕获 RuntimeError 异常

### 3. 错误反馈
- 所有失败情况都发送反馈邮件
- 用户明确知道发生了什么

## 测试建议

### 1. 基本流程测试
- 触发 ask_user → 验证邮件发送 → 邮件回复 → 验证 Agent 收到

### 2. 双渠道冲突测试
- 触发 ask_user → Web UI 回答 → 邮件回复 → 验证第二个被拒绝

### 3. Agent 不存在测试
- 邮件中的 agent_name 不存在 → 验证发送反馈"未找到 Agent"

### 4. 边界情况测试
- 超时回复（Agent 已经完成）
- 重复回复
- 空回复

## 注意事项

### 1. Session ID 含义
- `agent_session_id`：BaseAgent 的 session ID（用于日志和调试）
- `email_session_id`：邮件链路的 session ID（用于邮件 threading）
- 两者不同，不需要在邮件处理时验证

### 2. Subject 可见性
- `#ASK_USER#` 标记在用户邮箱中可见
- 类似现有的 `[Session: xxx]` 标记
- 用户回复时自动保留，不会丢失

### 3. 无超时机制
- ask_user 不设置超时
- Agent 会一直等待
- 符合用户需求

### 4. 向后兼容
- 前端机制完全不变
- 邮件是额外通道
- 不影响现有功能

### 5. 反馈邮件
- 所有邮件回复都给反馈
- 成功和失败都有明确提示
- 用户体验良好

### 6. 统一入口
- 前端和邮件都调用 `submit_user_input()`
- Agent 不需要区分回答来源
- 验证逻辑统一，易于维护

## 修复的 Bug

在 `email_proxy_service.py` 的 `convert_to_internal()` 方法中，`body` 和 `attachments` 变量被引用但从未定义。此问题已修复，现在正确调用 `_extract_body_and_attachments()` 方法来获取这些值。

## 后续改进建议

1. **邮件模板美化**：可以改进邮件正文的格式，使其更加友好
2. **国际化支持**：添加多语言支持
3. **邮件附件**：支持通过邮件附件回答问题（如上传文件）
4. **批量问答**：支持在一个邮件中回答多个问题

## 相关文档

- [Ask User 邮件集成实现计划](./ask-user-email-integration-plan.md)
- [AgentMatrix 架构文档](../architecture/)

## 状态

✅ 实现完成，待测试验证
