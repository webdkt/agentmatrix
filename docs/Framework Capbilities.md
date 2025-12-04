# **机制（Mechanism）与策略（Policy）的分离**。

*   **机制（Framework/Library）**：提供“怎么做”的能力（例如：发信、查人、存状态）。
*   **策略（Application）**：决定“做什么”（例如：先让Planner做计划，再让Coder写代码）。

虽然业务逻辑千变万化，但为了让 Agent 组织能“转”起来，框架层必须提供比“发邮件”更高一层的**基本原子能力**。

应该沉淀在 **Framework** 层的 5 个核心基础能力（除了 Communication 之外）：

---

### 1. **Service Discovery & Capability Manifest (服务发现与能力清单)**

在现实公司里，你入职第一天，HR 会给你一张表：“这是 IT 部门的小王，修电脑找他；这是财务的小李，报销找他。”

**框架层应实现：**
*   **动态通讯录 (Directory)**: 不仅仅是 `Name -> Agent实例` 的映射。
*   **能力描述协议 (Manifest)**: 每个 Agent 注册时，必须通过框架提供的标准格式声明自己的能力。
    *   例如：`{ "role": "Coder", "skills": ["python", "pandas"], "description": "处理数据清洗" }`
*   **语义查询接口**: 允许 Agent 向框架（邮局）提问：“谁最擅长画图？”（框架负责做简单的语义匹配返回名字）。

**应用层决定：**
*   到底有哪些 Agent，他们的人设和具体技能是什么。

---

### 2. **Structured Task Lifecycle (结构化任务生命周期)**

现在的“邮件”只是纯文本。但在正规组织里，任务是有“元数据”的。

**框架层应实现：**
*   **标准化的工单状态 (Ticket Status)**: 所有的任务交互，除了 Body 之外，框架强制附加一个 `status` 字段：`OPEN` -> `IN_PROGRESS` -> `BLOCKED` -> `RESOLVED` -> `CLOSED`。
*   **父子任务追踪 (Traceability)**: 框架自动维护 `parent_task_id`。如果 Planner 发起的任务 ID 是 `T-100`，Coder 为了完成它发出的求助信 ID 应该是 `T-100-1`。框架要提供 API 方便地查询 `T-100` 衍生出的所有子任务是否都 `RESOLVED` 了。

**应用层决定：**
*   什么情况下把状态改为 Blocked，什么算是 Resolved。

---

### 3. **Escalation Mechanism (异常升级/求助机制)**

如果 Coder 卡住了，或者 LLM 崩溃了，或者 Secretary 报错了，Agent 该怎么办？不能只是 Log 一下就死掉了。

**框架层应实现：**
*   **默认的 `escalate()` 接口**: 每个 Agent 基类都有这个方法。
*   **Chain of Command (指挥链)**: 框架允许在注册 Agent 时配置 `supervisor`（上级）。
*   **兜底逻辑**: 当 Agent 调用 `self.escalate("不知道怎么做")` 时，框架自动把这封信转发给它的 `supervisor`（通常是 Planner 或 Human Admin），并附带报错堆栈。

**应用层决定：**
*   谁是谁的上级？Planner 收到下属的报错后，是重试、换人还是问用户？

---

### 4. **Shared Blackboard / Workspace (公共白板)**

你提到的“Basic Memory”（大家都知道谁是谁，项目进行到哪了）。邮件是一对一的，有时候需要一个“全员可见”的地方。

**框架层应实现：**
*   **Blackboard 对象**: 一个线程安全的、支持订阅变更的 KV 存储。
*   **广播机制 (Broadcasting)**: 允许 Planner 发送 `@all` 的通告（例如：“项目需求变更了，大家注意”）。这不同于点对点邮件，它会塞入所有人的 Context 或作为一个高优先级 System Message。
*   **只读/读写权限控制**: 普通 Agent 可能对白板只有读权限，只有 Planner 有写权限。

**应用层决定：**
*   白板上写什么？是“项目进度表”，还是“当前分析结论”，还是“全局变量”。

---

### 5. **Standard Output Protocol (标准化输出协议)**

虽然输入输出是自然语言，但为了让流程可控，Agent 的输出**动作**必须被框架标准化，而不是让 LLM 随意发挥。

**框架层应实现：**
*   **Action Primitive (原子动作定义)**: 框架定义好几种基本的“意图类型”：
    *   `SEND_MAIL` (发信)
    *   `CALL_TOOL` (调工具)
    *   `THINK` (仅记录想法，不发信)
    *   `FINISH` (当前工单完结)
    *   `ASK_USER` (请求人类介入)
*   **Output Parser (强制解析器)**: 框架提供针对不同 LLM 的解析层，强制把 LLM 的输出映射到上述原子动作上。如果解析失败，框架自动驳回给 LLM 重试，不让 Application 层操心格式错误。

---

### 总结：框架 vs 应用

| 功能点 | **框架 (AgentMailOS) 负责** | **应用 (Your Business App) 负责** |
| :--- | :--- | :--- |
| **通信** | 邮件传输、路由、死信处理 | 谁给谁发、发什么内容 |
| **组织** | 维护通讯录、提供群发/公告能力 | 定义组织架构（扁平还是层级） |
| **记忆** | 提供白板存储、提供数据库归档 | 决定白板上存什么、怎么利用历史 |
| **流程** | 维护 `Open/Closed` 状态机、父子任务关联 | 决定先分析还是先写代码 (SOP) |
| **容错** | 提供 `escalate()` 接口、自动重试机制 | 决定遇到困难时是问人还是忽略 |
| **动作** | 定义标准动作 (Send, Tool, Finish) | Prompt Engineering (人设) |

### “Planner 模式”在这个框架里怎么跑？

在这种设计下，你的 Planner 模式会非常顺畅：

1.  **App 初始化**：在框架的 `Blackboard` 上写上：“项目目标：分析 A 股票”。
2.  **Planner (App层逻辑)**：读取白板，决定第一步是“收集数据”。
3.  **框架层**：Planner 发出一封 `OPEN` 状态的邮件给 Researcher。框架记录 `Parent: Project_1, Child: Task_1_1`。
4.  **Researcher**：干活。
5.  **框架层**：Researcher 调用 `FINISH` 动作。框架把 `Task_1_1` 标记为 `RESOLVED`，并自动通知 Planner。
6.  **Planner**：收到通知，读取 Researcher 的成果（更新到白板），然后决定下一步。

这样，**“流程把控”**（Planner 的核心职责）变成了应用层的逻辑，而**“状态跟踪、通知回调、错误兜底”**变成了框架层的免费能力。这就是最理想的封装。