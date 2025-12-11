这份总结旨在记录 **AgentMatrix** 的核心架构设计、概念定义与运行机制

---

### 1. 核心设计哲学 (Design Philosophy)

*   **拟人化组织 (Anthropomorphic Organization)**: 系统模拟人类公司的运作方式。Agent 之间通过自然语言（邮件）沟通，而非生硬的 API 调用。
*   **双脑架构 (Dual-Brain Architecture)**: 彻底分离“高层思考”与“底层执行”。
    *   **大脑 (Brain/LLM)**: 负责模糊推理、决策、意图生成 (High-level Intent)。
    *   **小脑 (Cerebellum/Local SLM)**: 负责将意图转化为精确的结构化指令 (Text-to-JSON)、格式化、参数填充。
*   **配置驱动 (Configuration-Driven)**: Agent 的代码逻辑（Python Class）与 行为设定（Profile YAML）分离。
*   **异步通信 (Async Communication)**: 邮件协议是系统的血液，支持长周期的异步协作。

---

### 2. 关键概念定义 (Key Concepts)

#### A. 基础设施 (Infrastructure)
*   **AgentMatrix (The World)**: 运行时容器。它是一个“平行宇宙”，包含了所有活着的 Agent、邮局状态、文件系统工作区（Workspace）和数据库。Matrix 可以被“冻结（Save）”到磁盘，也可以从磁盘“复活（Load）”。
*   **PostOffice (The Router)**: 消息总线。负责邮件的路由分发，维护通讯录（Yellow Pages），并提供服务发现能力。
*   **Loader (The Factory)**: 负责读取静态的 `Profile` 文件，组装出动态的 Agent 实例（注入大脑、小脑、动作能力）。

#### B. 智能体结构 (Agent Anatomy)
每个 Agent 由三部分组成：
1.  **Profile (DNA)**: 定义了我是谁（System Prompt）、我不做什么（Constraints）、怎么跟我说话（Instruction to Caller）。
2.  **Runtime Components (Organs)**:
    *   **Brain**: 远程 LLM 客户端（如 GPT-4）。
    *   **Cerebellum**: 本地 SLM 接口（如 Llama-3-8B），负责翻译 Action。
    *   **Inbox**: 异步消息队列。
    *   **Session Memory**: 当前正在处理的任务上下文。
3.  **Action Registry (Limbs)**: Agent 能做的具体事情（Python 函数）。通过装饰器注册，包含 SYNC/ASYNC/TERMINAL 三种类型。

#### C. 通信协议 (The Protocol)
*   **Email Object**: 包含 `From`, `To`, `Subject`, `Body`, `In-Reply-To` (用于追踪会话链)。
*   **Agent Manifest**: 一种“软契约”。每个 Agent 都要对外宣称“如何跟我沟通（Instruction for Caller）”，这会被注入到上游 Agent 的 Prompt 中，指导其生成邮件。

---

### 3. 运行机制 (Runtime Flow)

#### A. The "Process Loop" (主循环)
Agent 处理邮件的标准流程，是一个 **Think-Act Loop**：
1.  **Receive**: 从 Inbox 取出一封信。
2.  **Routing**:
    *   是回复（In-Reply-To）? $\rightarrow$ 唤醒旧 Session。
    *   是新信? $\rightarrow$ 创建新 Session。
3.  **Loop (Brain <-> Cerebellum <-> Body)**:
    *   **Brain**: 阅读 Context，输出自然语言 **意图 (Intent)**。
    *   **Cerebellum**: 结合意图和可用工具列表，翻译成 **动作 (Action JSON)**。
    *   **Body**: 映射到 Python 函数并执行。
4.  **Feedback**:
    *   **SYNC Action** (如读文件、思考): 结果存入历史，**继续** Loop。
    *   **ASYNC Action** (如发邮件): 挂起 Session (WAITING)，**退出** Loop，释放资源。
    *   **TERMINAL Action** (如结束任务): 归档/销毁 Session，**退出** Loop。

#### B. 状态管理 (State Management)
*   **Worker (Stateless/Session-based)**: 依赖线性的对话历史 (History)。任务结束，记忆即焚。
*   **Planner (Stateful)**: 依赖结构化的状态文档 (Project State YAML)。
    *   **Reflect & Update**: 收到信先更新状态文档。
    *   **Decide & Act**: 基于最新状态文档决定下一步。

#### C. 人机交互 (HCI)
*   **UserProxyAgent**: 系统中代表“用户”的特殊 Agent。
    *   **Inversion of Control**: 它不依赖特定的前端。它通过 Hook/Callback 将内部邮件推送到外部（CLI/Web），并通过 API 接收外部输入转化为内部邮件。

---


