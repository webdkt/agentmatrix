# AgentMatrix 架构设计文档 (v2.0)

### 1. 核心设计哲学 (Design Philosophy)

*   **拟人化与社会化 (Anthropomorphic & Social)**:
    *   Agent 是独立的“数字员工”，而非简单的函数接口。
    *   Agent 之间通过自然语言（邮件）进行社交协作，而非 API 调用。
    *   系统容忍模糊性，Agent 像人类一样通过沟通来消除歧义。

*   **双脑架构与谈判机制 (Dual-Brain & Negotiation)**:
    *   **大脑 (Brain/LLM)**: 负责高层认知、推理、人设扮演（Persona）和模糊意图生成。
    *   **小脑 (Cerebellum/SLM)**: 负责接口适配、参数检查和结构化翻译。
    *   **谈判 (Negotiation)**: 当大脑意图不清时，小脑不会强行执行，而是发起“内部质询（Internal Query）”，与大脑进行多轮对话以补全信息。

*   **框架嵌入 (Frame Embedding)**:
    *   **驾驶舱隐喻 (Pilot in the Cockpit)**: 将 Agent 分为“意识（Pilot）”与“躯体（System）”。
    *   Prompt 不再是指令集，而是“物理法则”。Agent 在一个回合制的世界中，通过操作仪表盘（Output Format）来驱动躯体。

*   **显式意志驱动 (Volition-Driven Flow)**:
    *   **Action is Sync**: 对大脑而言，所有动作（发邮件、读文件）都是瞬间完成的反馈。
    *   **Wait is Explicit**: 系统不再自动挂起。挂起（Wait）是一个主动的认知决策。Agent 必须显式决定“我现在没事做了，我要等待外部信号”。

---

### 2. 关键概念定义 (Key Concepts)

#### A. 基础设施 (The World)
*   **The Matrix**: 运行时容器，提供时间、空间（文件系统沙箱）和通讯设施。
*   **PostOffice**: 异步消息总线。负责邮件投递、服务发现（Yellow Page）。
*   **Signals**: 系统内唯一的信息载体。无论是新邮件、文件内容、执行报错还是小脑的提问，统统被封装为统一的 **Signal** 格式投喂给大脑。

#### B. 智能体结构 (Agent Anatomy)
1.  **Pilot (The Mind)**:
    *   **System Prompt**: 定义人设（我是谁）。
    *   **Protocol Constraint**: 定义物理法则（我要怎么动）。
    *   **Capability Menu**: 只有名字和描述的能力菜单（大脑只看菜单，不看配方）。
2.  **Cerebellum (The Interface)**:
    *   持有完整的 **Tools Manifest**（JSON Schema）。
    *   作为“看门人”，拦截无效意图，发起参数协商。
3.  **Body (The Execution Unit)**:
    *   无状态的执行器。负责将小脑输出的 JSON 映射为具体的 Python 函数调用。

#### C. 信号系统 (The Signal System)
Agent 与世界的交互被抽象为纯粹的 **I/O 流**：
*   **Input**: `[INCOMING MAIL]`, `[BODY FEEDBACK]`, `[INTERNAL QUERY]`
*   **Output**: `THOUGHT` (思维链) + `ACTION SIGNAL` (具体指令)

---

### 3. 运行机制 (Runtime Flow)

#### A. The "Turn-Based" Loop (主循环)
Agent 的生命周期由一系列离散的 **回合 (Turn)** 组成：

1.  **Awake (Signal Received)**:
    *   Agent 处于冻结状态，直到收到一个 Signal。
2.  **Reasoning (Thought)**:
    *   大脑阅读历史上下文和最新信号。
    *   生成 **THOUGHT**: 进行隐式的思维链推导（例如：分析局势、制定计划、检查遗漏）。
3.  **Decision (Action Signal)**:
    *   大脑输出 **ACTION SIGNAL**: 明确下一步要做的一个动作。
    *   *Rule*: "Pass the Baton" —— 输出动作后，大脑立即停止生成，交出控制权。
4.  **Negotiation (The Filter)**:
    *   小脑拦截 Signal。
    *   **Check**: 参数齐了吗？意图在能力范围内吗？
    *   **If No**: 小脑生成 `[INTERNAL QUERY]`，回滚到第 1 步（Agent 收到质询信号，被唤醒进行解释）。
    *   **If Yes**: 生成结构化 JSON。
5.  **Execution (The Body)**:
    *   执行具体的 Python 函数。
6.  **Feedback Loop**:
    *   **Action Result**: 动作产生结果（如“邮件已发送”或“文件内容”），封装为 `[BODY FEEDBACK]`，**立即** 触发下一回合（回到第 1 步）。
    *   **Explicit Wait**: 如果动作是 `rest_n_wait`，则系统**挂起** Session，直到有外部新邮件进入。

#### B. 状态机流转
*   **Active**: 正在处理 Signal，或刚刚执行完动作收到反馈。
*   **Negotiating**: 正在与小脑进行内部参数对齐。
*   **Waiting**: 执行了 `rest_n_wait`，处于休眠状态，等待 PostOffice 的唤醒。

---

### 4. 交互契约 (The Protocol)

#### A. 思维链与动作分离
为了提升智能并保证稳定性，输出被严格分为两块：
*   **THOUGHT**: 允许 Agent 自言自语。这是“暗知识”，用于推理和决策，小脑不看这一部分。
*   **ACTION SIGNAL**: 必须是纯净的指令。这是“工单”，小脑只执行这一部分。

#### B. 显式等待 (Explicit Wait)
*   **Fire-and-Forget**: 发送邮件 (`send_email`) 不会自动结束任务。Agent 会收到“发送成功”的反馈，然后它必须决定是继续工作（如写代码）还是休息。
*   **Yield**: 只有调用 `rest_n_wait`，Agent 才会交出 CPU 时间片。这使得“连续多步操作”成为可能（如：发信 -> 查文件 -> 再发信 -> 休息）。

#### C. 原子化工具 (Atomic Capabilities)
*   工具不再包含复杂的业务逻辑（如“回复上一个人”）。
*   工具回归原子化（如“发给某人”）。
*   **路由逻辑**（发给谁？）完全由大脑基于上下文在 `THOUGHT` 阶段决定，小脑只负责填空。

---

### 5. 总结

AgentMatrix v2.0 的核心在于**“解放大脑，约束接口”**。

*   我们不再用复杂的代码逻辑去猜测 Agent 发完邮件后想干什么。
*   我们将“决定权”完全交还给 Agent 的**自由意志**（通过 THOUGHT 和 Explicit Wait）。
*   同时，利用 **Negotiation** 机制作为安全网，确保这种自由意志不会转化为错误的系统调用。

这是一个**以认知为中心 (Cognition-Centric)** 而非以流程为中心 (Process-Centric) 的系统架构。


