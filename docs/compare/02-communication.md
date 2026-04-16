# 02 — Agent 间通信模型

## 通信隐喻

### AgentMatrix: 邮件系统

所有 Agent 间通信通过 `Email` 数据类（`src/agentmatrix/core/message.py`）实现，由 `PostOffice`（`src/agentmatrix/agents/post_office.py`）统一路由。

```python
@dataclass
class Email:
    sender: str
    recipient: str
    subject: str
    body: str
    in_reply_to: Optional[str] = None
    id: Optional[str] = None
    timestamp: Optional[datetime] = None
    task_id: Optional[str] = None
    sender_session_id: Optional[str] = None
    recipient_session_id: Optional[str] = None
    metadata: Optional[dict] = None  # 附件等
```

核心特征：
- **异步传递**：邮件投递到队列，Agent 在事件循环中接收
- **线程追踪**：`in_reply_to` 字段形成邮件线程链
- **双视角 Session**：`sender_session_id` 和 `recipient_session_id` 维护各自会话上下文
- **附件支持**：通过 `metadata` 字段携带文件
- **可读性强**：邮件格式天然对人类友好，便于审计和调试

PostOffice 提供 **黄页服务**（`yellow_page()`），生成所有注册 Agent 的人类可读目录，供 Agent 动态发现协作对象。

### Hermes Agent: 进程内 Tool-Calling

Hermes 没有 Agent 间通信协议。Agent 通过 tool call 直接操作外部系统（发送消息、执行命令等）。子任务通过 `delegate_tool` 委派，结果通过函数返回值传递，不经过持久化消息层。

消息传递的"通信"仅发生在 Agent 与外部世界之间（用户、消息平台），而非 Agent 与 Agent 之间。

## 消息持久化

### AgentMatrix: 邮件归档 + 交付队列

数据库（`src/agentmatrix/db/agent_matrix_db.py`）维护多张表：

| 表 | 用途 |
|---|---|
| `emails` | 所有邮件的归档存储 |
| `email_to_deliver` | 待投递队列（崩溃恢复） |
| `email_to_process` | 待处理队列（崩溃恢复） |
| `sessions` | 会话元数据 |
| `scheduled_tasks` | 定时任务 |

完整线程链可通过 `in_reply_to` 反向追溯。每封邮件都有唯一的 `id` 和时间戳。

### Hermes Agent: SQLite + FTS5 全文搜索

`hermes_state.py` 实现了结构更丰富的数据库：

- **sessions 表**：包含 message_count、tool_call_count、input/output tokens、cache tokens、cost tracking 等丰富元数据
- **messages 表**：存储完整对话历史，含 role、content、tool_calls、token_count
- **FTS5 虚拟表**：支持跨所有会话消息的全文搜索
- **parent_session_id 链**：压缩触发的会话拆分追踪

Hermes 的存储更侧重于**单 Agent 对话历史的搜索和分析**，而非多 Agent 间的邮件追溯。

## 外部通信桥接

### AgentMatrix: EmailProxyService

`src/agentmatrix/services/email_proxy_service.py`（~42KB）桥接外部真实邮箱：

- **双邮箱模式**：`user_mailbox`（用户个人邮箱）+ `matrix_mailbox`（系统邮箱）
- **主题标记规则**：`@Agent` 表示入站，`#Agent` 表示出站
- **IMAP IDLE** 实时推送 + 轮询降级
- **支持**：Gmail、Outlook、QQ 邮箱
- **会话追溯**：通过映射表 + AMX footer 标记回溯原始邮件

这让 Agent 看起来像一个**邮件联系人**——用户可以像给同事发邮件一样与 Agent 交互。

### Hermes Agent: 22 个消息平台适配器

`gateway/platforms/` 目录下有 22 个平台适配器：

telegram, discord, slack, whatsapp, signal, matrix, feishu, qqbot, weixin, wecom, wecom-callback, bluebubbles, mattermost, email, sms, webhook, homeassistant, dingtalk, api_server

所有适配器继承 `BasePlatformAdapter`，实现统一接口：`connect()`、`disconnect()`、`send()`、`send_typing()`、`send_image()` 等。

这让 Agent 看起来像一个**全渠道 Bot**——用户在任何消息平台都能与 Agent 对话。

## "Agent as Contact" vs "Agent as Bot"

| 维度 | AgentMatrix (Contact) | Hermes (Bot) |
|------|----------------------|--------------|
| **交互方式** | 异步邮件，可以有较长延迟 | 即时消息，实时响应 |
| **通信内容** | 支持长文、附件、线程 | 短消息、图片为主 |
| **用户心智模型** | "给 Agent 发封邮件" | "在群里 @Bot" |
| **适用场景** | 复杂任务委托、研究型工作 | 日常问答、快速操作 |
| **审计性** | 天然邮件存档 | 依赖平台消息历史 |
| **多 Agent 可见性** | 邮件线程天然展示协作 | 不可见（进程内委派） |

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **Agent 间通信** | 邮件（Email dataclass + PostOffice） | 无独立通信层（函数返回值） |
| **消息格式** | 结构化邮件（线程、附件、双 Session） | OpenAI messages 格式 |
| **持久化深度** | 邮件归档 + 交付/处理队列 | 对话历史 + FTS5 搜索 |
| **外部通道** | 邮件（Gmail/Outlook IMAP） | 22 个消息平台 |
| **优势** | 人类可读的多 Agent 审计追踪 | 全渠道用户触达 |
| **劣势** | 外部通道仅限邮件 | Agent 间协作不可见、不可审计 |
