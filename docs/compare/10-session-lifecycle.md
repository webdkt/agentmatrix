# 10 — 会话生命周期管理

## 核心问题

Hermes 只有一个 AIAgent 类，不存在 Agent 间邮件通信，那么"一次会话"从哪里开始、到哪里结束？

## 会话开始

### AgentMatrix: 任务驱动

会话绑定在**任务**上。BaseAgent 收到一封邮件，为该邮件创建一个 MicroAgent 会话。会话的开始 = 新任务到达。

- 邮件到达 → BaseAgent 接收 → 创建 MicroAgent → MicroAgent 拥有独立 Session
- 会话通过 `sender_session_id` / `recipient_session_id` 维护双视角
- `in_reply_to` 链将相关邮件的会话串联

### Hermes: 连接驱动

会话绑定在**对话通道**上。会话的开始 = 一个新的对话通道被打开。

**CLI 模式**：每次启动 `hermes` 命令 = 一个新会话。会话 ID 在 CLI 初始化时生成：

```python
# cli.py, line 1796
timestamp_str = self.session_start.strftime("%Y%m%d_%H%M%S")
short_uuid = uuid.uuid4().hex[:6]
self.session_id = f"{timestamp_str}_{short_uuid}"
# 例: "20260416_143052_a3f2c1"
```

DB 行在第一次调用 `run_conversation()` 时才创建（懒创建）。

**Gateway 模式**（Telegram/Discord/Slack 等）：Gateway 用**确定性的 session key** 来判定"这是不是同一个会话"：

```
DM:    agent:main:telegram:dm:<chat_id>
Group: agent:main:telegram:group:<chat_id>:<user_id>
```

每条消息进来时调用 `SessionStore.get_or_create_session(source)`：
1. 从 SessionSource 计算 session key
2. 该 key 已有活跃 SessionEntry 且未过期 → 复用
3. 过期或被挂起 → 结束旧的，创建新的

**会话开始 = 第一条消息到达一个没有活跃会话的 session key。**

## 会话结束

### AgentMatrix: 自然结束

MicroAgent 完成任务（调用 `provide_final_answer` 等退出 action）后，会话自然结束。生命周期绑定在任务语义上。

### Hermes: 外部策略触发

Hermes 没有"Agent 判断对话已结束"的机制。会话结束由外部事件触发：

| 触发方式 | end_reason | 说明 |
|----------|------------|------|
| 空闲超时 | `"session_reset"` | Gateway 后台每 5 分钟检查 `_session_expiry_watcher` |
| 每日重置 | `"session_reset"` | 按配置的时间表重置 |
| `/new` 命令 | `"new_session"` | 用户手动开始新会话 |
| `/branch` 命令 | `"branched"` | 从当前会话分叉 |
| `/resume` 命令 | `"resumed_other"` | 切换到历史会话 |
| 上下文压缩 | `"compression"` | 对话太长时自动拆分链 |
| Gateway 关闭 | suspend（挂起） | 不设 ended_at，标记 suspended，下次启动恢复 |

**关键点：会话不会因为"Agent 认为对话结束了"而结束。** 结束只能由用户命令或系统策略触发。

## 会话压缩与拆分

当对话上下文过大（超过 context window 的 85% 或 400+ 条消息），Hermes 通过 `_compress_context()` 拆分会话：

1. 用 `ContextCompressor` 压缩对话历史
2. 结束当前会话（`end_session(old_id, "compression")`）
3. 创建新会话（`parent_session_id=old_id`）
4. 将压缩后的消息写入新会话
5. 标题自动编号（"my task" → "my task #2"）

这形成了一条 `parent_session_id` 链：`session_1 → session_2 → session_3 → ...`。旧会话保留在 DB 中可搜索。

AgentMatrix 的 SessionManager 也有类似的自动压缩（基于 token 阈值 32000 和 scratchpad 累积 8 条），但压缩在同一会话内进行，不拆分会话 ID。

## Gateway Agent 实例管理

一个关键细节：**Gateway 为每条消息创建（或复用缓存的）AIAgent 实例，但会话 ID 跨实例保持不变。**

```
消息1到达 → AIAgent(session_id="abc") → run_conversation() → 返回
消息2到达 → AIAgent(session_id="abc") → run_conversation() → 返回
消息3到达 → AIAgent(session_id="abc") → run_conversation() → 返回
```

AIAgent 是短暂的（处理完一条消息就销毁），但会话是持久的（在 SessionStore 和 SQLite 中持续存在）。这与 AgentMatrix 的模式形成对比——AM 中 BaseAgent 是持久的，MicroAgent 是短暂的但绑定在单个任务上。

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **会话开始触发** | 新邮件/新任务到达 | 新消息到达一个无活跃会话的通道 |
| **会话结束触发** | MicroAgent 完成任务（语义驱动） | 用户命令 / 超时 / 压缩（策略驱动） |
| **会话绑定对象** | 任务（一封邮件的处理过程） | 对话通道（一个聊天/一个 CLI 进程） |
| **Agent 实例 vs 会话** | BaseAgent 持久，MicroAgent 临时绑定任务 | AIAgent 临时（每消息），会话持久 |
| **压缩方式** | 同会话内压缩 | 拆分会话 + parent_session_id 链 |
| **会话恢复** | 通过 in_reply_to 邮件线链 | `/resume` 命令 + reopen_session() |
| **哲学差异** | 会话 = 一个任务的上下文 | 会话 = 一段持续的对话 |
