# 核心概念

本文档解释 AgentMatrix 中几个最基本的数据模型及其关系。理解这些概念有助于正确使用系统和阅读代码。

---

## Email — 通信的基本单位

Agent 之间不通过 API 调用通信，而是发送邮件。一封邮件包含：

- **发件人与收件人**：Agent 的名称
- **主题与正文**：自然语言内容
- **任务 ID**：标识这封邮件所属的工作任务
- **发件人会话 ID**：发件人视角下的会话标识
- **收件人会话 ID**：收件人视角下的会话标识
- **附件**：随邮件传输的文件

邮件是系统中唯一的信息传递方式。用户给 Agent 发任务、Agent 之间协作、Agent 向用户提问，全部通过邮件完成。

---

## Session — 单 Agent 的主观视角

Session 是一个 Agent 看到的邮件往来视图。

关键设计：**Session 是主观的**。A 给 B 发了一封邮件，这在 A 的视角里是一个 Session，在 B 的视角里是另一个 Session。两个 Session 有各自的 ID，指向同一组邮件的不同侧面。

每个 Session 由该 Agent 参与的所有邮件组成，按时间排序。Session 的 ID 在邮件发送时由发件方生成，收件方在收到时记录为自己的会话 ID。

**Session 的用途**：
- 在桌面应用中显示对话列表
- 查询某个主题的历史邮件
- 组织邮件的展示顺序

---

## Task — 跨 Agent 的客观工作单元

Task 是一个完整的工作任务，是客观存在的。一个 Task 可能涉及多个 Agent 和多组 Session。

**Task 与 Session 的关系**：

| | Task | Session |
|--|------|---------|
| 视角 | 客观工作单元 | 单 Agent 主观视图 |
| 范围 | 跨 Agent | 单 Agent |
| 用途 | 任务追踪、文件隔离 | 对话列表、历史查询 |
| 关系 | 一个 Task 包含多个 Session | 一个 Session 属于某个 Task |

所有属于同一个 Task 的邮件都携带相同的任务 ID。这使得系统可以追踪一个任务在多个 Agent 之间的流转过程，也是文件隔离的基础。

**示例**：

用户给 Agent A 发了一个"研究量子计算"的任务。Agent A 决定让 Agent B 帮忙搜索资料。

- 这是一个 Task（任务 ID 相同）
- 用户 ↔ Agent A 的邮件：在用户和 Agent A 各有一个 Session
- Agent A ↔ Agent B 的邮件：在 Agent A 和 Agent B 各有一个 Session
- Agent B 完成搜索后回复 Agent A，Agent A 综合后回复用户
- 从 Task 视角，这是同一个任务的完整流程
- 从 Session 视角，用户只看到自己和 Agent A 的对话

---

## Agent — 自主参与者

Agent 是系统中的自主参与者，每个 Agent 有：

- **名称**：系统中的唯一标识
- **描述**：一句话说明这个 Agent 是做什么的
- **人设 (Persona)**：详细定义角色、性格、工作方式和约束
- **技能列表**：这个 Agent 可以使用哪些 Skill
- **后端模型**：连接哪个 LLM

Agent 分为两类：

- **AI Agent**：由大模型驱动，接收邮件后创建 MicroAgent 执行任务
- **UserProxy**：代表人类用户，负责把用户的输入转发给目标 Agent，再把回复带回给用户

还有两个特殊的内置 Agent：

- **SystemAdmin**：管理系统配置
- **AgentAdmin**：管理其他 Agent 的生命周期

---

## 文件隔离

每个任务有独立的工作目录。附件和 Agent 创建的文件按以下规则存放：

```
MatrixWorld/
└── workspace/
    └── agent_files/
        └── {agent_name}/
            └── work_files/
                └── {task_id}/
                    └── attachments/
```

任务 ID 是文件隔离的边界。不同任务的文件不会互相覆盖或泄漏。Agent 在容器模式下运行时，这个目录会被挂载到容器内部。

---

## 数据模型关系

```
┌─────────────────────────────────────────────┐
│                 AgentMatrix 系统               │
└─────────────────────────────────────────────┘

        用户 (UserProxy)
            │
            │ 发送 Email
            ↓
        PostOffice ─────────┬──────────┐
            │               │          │
            ↓               ↓          ↓
        Agent A         Agent B    Agent C
            │               │          │
            └───────────────┴──────────┘
                    互相发送 Email

┌─────────────────────────────────────────────┐
│                 一个 Task 的视角                │
│                                               │
│   用户 → A (Email 1, task_id="t1")            │
│        A → B (Email 2, task_id="t1")          │
│             B → A (Email 3, task_id="t1")     │
│        A → 用户 (Email 4, task_id="t1")       │
│                                               │
│   所有邮件共享同一个 task_id                   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│                Session 的视角                  │
│                                               │
│   用户的 Session：Email 1 + Email 4           │
│   Agent A 的 Session：Email 1 + 2 + 3 + 4     │
│   Agent B 的 Session：Email 2 + 3             │
│                                               │
│   每个 Agent 只看到自己的 Session             │
└─────────────────────────────────────────────┘
```

---

## 命名规范

### 后端（Python）

- 使用 `snake_case`
- 邮件收件人字段用 `recipient`（不用 `receiver`）
- 任务 ID 用 `task_id`，会话 ID 用 `session_id`（发件人视角 `sender_session_id`，收件人视角 `recipient_session_id`）

### 前端（JavaScript）

- 使用 `camelCase`
- 对应字段：`taskId`、`senderSessionId`、`recipientSessionId`

### API 路径

- 使用 `kebab-case`，如 `/api/sessions`、`/api/agents`
- 返回字段保持 `snake_case`
