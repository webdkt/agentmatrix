# current_user_session_id 功能实现 ✅

## 概述

在 BaseAgent 中新增 `current_user_session_id` 变量，用于追踪当前是否在处理来自 User 的邮件。

**日期**: 2026-03-15
**状态**: ✅ 完成
**测试**: ✅ 全部通过

---

## 功能说明

### 问题背景

当 Agent 处理邮件时，需要知道：
1. 邮件是否来自 User（而不是其他 Agent）
2. 如果来自 User，需要知道 User 的 session_id
3. 这样前端可以跳转到正确的用户会话显示对话框

### 解决方案

在 `BaseAgent` 中添加 `current_user_session_id` 变量：
- **如果邮件来自 User**: `current_user_session_id = mail.sender_session_id`
- **如果邮件来自其他 Agent**: `current_user_session_id = None`

---

## 实现细节

### 1. BaseAgent 变量初始化

**文件**: `src/agentmatrix/agents/base.py`

```python
# 在 __init__ 方法中添加
self.current_user_session_id = None  # 🆕 当前用户会话ID（如果邮件来自User）
```

**位置**: 第 86 行（与 `current_task_id` 相邻）

---

### 2. 邮件处理逻辑

**文件**: `src/agentmatrix/agents/base.py`

**位置**: `process_email()` 方法，第 559-568 行

```python
# 1. Session Management (Routing)
self.logger.debug(f"New Email")
self.logger.debug(str(email))
session = await self.session_manager.get_session(email)
self.current_session = session
self.current_task_id = session["task_id"]

# 🆕 设置 current_user_session_id（如果邮件来自User）
# 检查邮件发送者是否是用户
if self.runtime and email.sender == self.runtime.get_user_agent_name():
    # 邮件来自User，设置 current_user_session_id
    self.current_user_session_id = email.sender_session_id
    self.logger.debug(f"📧 邮件来自用户 User，设置 current_user_session_id = {email.sender_session_id[:8] if email.sender_session_id else None}...")
else:
    # 邮件来自其他Agent，清空 current_user_session_id
    self.current_user_session_id = None
    self.logger.debug(f"📧 邮件来自 {email.sender}，清空 current_user_session_id")
```

**逻辑流程**:
1. 获取 User 的名字：`self.runtime.get_user_agent_name()`
2. 比较邮件发送者：`email.sender == user_name`
3. 如果是 User：设置 `current_user_session_id = email.sender_session_id`
4. 如果不是 User：设置 `current_user_session_id = None`

---

### 3. 状态收集器更新

**文件**: `src/agentmatrix/core/system_status_collector.py`

```python
agent_info = {
    "status": agent.status,
    "pending_question": None,
    "current_session_id": None,
    "current_task_id": None,
    "current_user_session_id": None  # 🆕 新增字段
}

# 添加 user_session_id（🆕 如果邮件来自User）
if hasattr(agent, 'current_user_session_id'):
    agent_info["current_user_session_id"] = agent.current_user_session_id
```

**广播数据结构**:
```python
{
    "timestamp": "...",
    "agents": {
        "AgentName": {
            "status": "WAITING_FOR_USER",
            "pending_question": "...",
            "current_session_id": "xxx",        # Agent 的当前会话
            "current_task_id": "xxx",           # Agent 的当前任务
            "current_user_session_id": "xxx"    # 🆕 User 的会话（如果邮件来自User）
        }
    }
}
```

---

## 使用场景

### 场景 1: Agent 间通信

```
Planner → Worker: "开始任务 A"
```

**结果**:
- `Worker.current_session_id` = Worker 的会话
- `Worker.current_user_session_id` = **None**（因为邮件来自 Planner）

---

### 场景 2: 用户发起任务

```
User → Worker: "帮我写代码"
```

**结果**:
- `Worker.current_session_id` = Worker 的会话
- `Worker.current_user_session_id` = **User 的 session_id**（因为邮件来自 User）

---

## 前端使用

### 检测用户会话

```javascript
// 在 checkForWaitingUser() 中
for (const [agentName, agentInfo] of Object.entries(this.systemStatus.agents)) {
    if (agentInfo.pending_question) {
        // 检查是否有用户会话
        if (agentInfo.current_user_session_id) {
            // 邮件来自 User，跳转到用户的会话
            const userSession = this.sessions.find(
                s => s.session_id === agentInfo.current_user_session_id
            );
            if (userSession) {
                await this.selectSession(userSession);
            }
        }

        // 显示对话框
        const payload = {
            agent_name: agentName,
            task_id: agentInfo.current_task_id,
            session_id: agentInfo.current_session_id
        };
        this.handleAskUser(agentName, agentInfo.pending_question, payload);
    }
}
```

---

## 字段对比

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `current_session_id` | str | Agent 的当前会话 | `"worker_session_123"` |
| `current_task_id` | str | Agent 的当前任务 | `"task_456"` |
| `current_user_session_id` | str \| None | User 的会话（如果邮件来自User） | `"user_session_789"` 或 `None` |

---

## 测试验证

### 测试用例

**文件**: `tests/test_status_collector.py`

1. **test_agent_info_fields()**
   - 验证 `current_user_session_id` 字段存在
   - 验证值正确传递

2. **test_user_session_id_logic()**
   - 场景 1: 邮件来自其他 Agent（值为 None）
   - 场景 2: 邮件来自 User（值为 sender_session_id）

### 测试结果

```bash
$ python tests/test_status_collector.py

测试 3: Agent 信息包含所有 session ID 字段
✅ Agent 信息字段完整
   - current_user_session_id: user_session_789 ✨ 新增

测试 4: current_user_session_id 逻辑
场景 1: 邮件来自其他 Agent
   ✅ current_user_session_id = None

场景 2: 邮件来自 User
   ✅ current_user_session_id = user_session_abc

🎉 所有测试通过！current_user_session_id 功能正常！
```

---

## 修改文件清单

### 核心文件 (2 个)

1. ✅ `src/agentmatrix/agents/base.py`
   - 添加 `current_user_session_id` 变量
   - 在 `process_email()` 中设置逻辑

2. ✅ `src/agentmatrix/core/system_status_collector.py`
   - 添加 `current_user_session_id` 到 agent_info
   - 通过 WebSocket 广播到前端

### 测试文件 (1 个)

3. ✅ `tests/test_status_collector.py`
   - 添加 `test_user_session_id_logic()` 测试

---

## 后续优化建议

### 可选的未来增强

1. **前端会话跳转**
   - 当检测到 `current_user_session_id` 时，自动跳转到用户会话
   - 提供更好的用户体验

2. **历史记录**
   - 记录最近的 `current_user_session_id` 变化
   - 帮助调试 Agent 交互流程

3. **多用户支持**
   - 如果未来支持多个 User，可以扩展为数组
   - `current_user_session_ids = [...]`

---

## 总结

### 核心价值

- ✅ **追踪用户交互**: 清晰知道 Agent 是否在处理用户请求
- ✅ **会话跳转**: 前端可以准确跳转到用户会话显示对话框
- ✅ **逻辑清晰**: 邮件来自 User 就设置，否则清空
- ✅ **完整测试**: 所有场景都有测试覆盖

### 设计原则

- **简单直接**: 一个变量，两种状态（有值 / None）
- **自动化**: 无需手动设置，根据邮件发送者自动判断
- **可扩展**: 未来可以轻松扩展支持多用户

---

**current_user_session_id 功能实现完成！** 🎉
