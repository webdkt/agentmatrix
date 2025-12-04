# 对于最顶端的Planner，它需要维护的对话可能非常长，应该如何设计？

这是Agent 系统的**核心瓶颈**：**Context Window Management（上下文窗口管理）** 与 **Information Abstraction（信息抽象）** 的矛盾。

1.  **底层员工（Coder/Secretary）**：任务明确、生命周期短。处理完一个具体函数或查询，Context 就可以丢弃。
2.  **顶层管理者（Planner）**：生命周期极长（贯穿整个项目），信息密度极大。

如果简单地把所有下属的汇报邮件（包含大量代码、报错日志、数据片段）都堆进 Planner 的 Context 里，无论多大的 Context Window 都会很快爆掉，而且噪音太大，LLM 会变笨。

为了解决这个问题，我们需要引入一种**通用机制**，我称之为 **“动态文档（Living Artifact）”模式**，或者叫 **“状态驱动（State-Driven）”模式**，而不是传统的“对话驱动（History-Driven）”。

---

### 1. 核心理念：Planner 不是 Chatbot，是“状态维护者”

对于 Planner，我们不能让它依赖线性的 `List<Message>` 来记忆。我们必须**强制**它维护一份 **“项目状态文档（Project State Document）”**。

*   **传统模式 (Chat)**:
    *   Input: `[User: 做A, Planner: 让Coder做A, Coder: 报错xxx, Planner: 试一下y, Coder: 好了, output is Z]`
    *   *问题：Coder 的报错细节和调试过程，对 Planner 的长期记忆是垃圾信息。*

*   **动态文档模式 (State-Driven)**:
    *   Planner 不记忆“对话流”，只记忆一个 **JSON/Markdown 对象**（我们称之为 **The Plan**）。
    *   每次收到新邮件，Planner 的工作不是“回复”，而是 **“更新文档”**，然后基于文档决定下一步。

---

### 2. 机制设计：双循环结构 (The Update-Act Loop)

为了在框架层面支持这种能力，我们需要给 Planner 这种特殊的 Agent 设计一种**双步骤**的思考流。

当 Planner 收到一封邮件（比如 Coder 的汇报）时：

#### 第一步：Reflect & Update (消化与更新)
*   **输入**：当前的项目文档（The Plan） + 新收到的邮件（The Email）。
*   **System Prompt**：“你是一个项目经理。这是当前的项目计划状态。这是刚收到的下属汇报。请根据汇报内容，**更新**项目计划（标记完成、添加新步骤、记录关键结果）。不要回复邮件，只输出更新后的计划。”
*   **输出**：新的项目文档（The New Plan）。
*   **动作**：框架用“New Plan”替换掉内存里的“Old Plan”。

#### 第二步：Act & Dispatch (决策与分发)
*   **输入**：更新后的项目文档（The New Plan）。
*   **System Prompt**：“这是当前最新的项目计划。请检查还有哪些未完成的任务。决定下一步该给谁发邮件，发什么指令。”
*   **输出**：一封或多封发给下属的邮件。
*   **动作**：投递邮件。

#### 第三步：Garbage Collection (关键！丢弃上下文)
*   **动作**：**直接丢弃** 刚才那封 Coder 发来的原始邮件和第一步的思考过程。
*   **保留**：只保留 **最新的 Project Plan** 作为下一轮的 Context。

---

### 3. 这个机制解决了什么问题？

1.  **无限的生命周期**：
    *   因为 Planner 每次只需要看“最新的 Plan”，而不需要看“过去 100 轮的邮件”。Plan 的大小通常是可控的（几 KB），而邮件历史是无限增长的。
    *   Planner 永远处于 **Context 几乎为空** 的清爽状态，只关注当下状态。

2.  **自动的信息压缩（Compression）**：
    *   Coder 发来：“我试了库 A 报错，试了库 B 报错，最后用库 C 成功了，结果是 X。”
    *   Planner 在“第一步”更新文档时，只会把 Plan 更新为：`Task 1: Completed. Result: X. (Note: Library C used)`。
    *   中间的报错过程被自动过滤掉了。这就是**抽象**。

---

### 4. 框架内如何实现？(Framework Implementation)

这不应该是 Application 层的瞎写，而应该是 Framework 提供的标准能力。

我们给 `BaseAgent` 扩展一个子类 `StatefulAgent`（专门给 Planner 用）。

```python
# agents/stateful.py 

class StatefulAgent(BaseAgent):
    def __init__(self, name, backend):
        super().__init__(name, backend)
        # 这就是那个“动态文档”，可以是 JSON，也可以是 Markdown
        self.project_state = {
            "objective": "",
            "tasks": [],
            "key_findings": []
        }

    async def step(self, session: TaskSession):
        # 获取最新的一封信（导致这次激活的那封）
        incoming_mail = session.history[-1]['content']
        
        # === Phase 1: State Update (只更新记忆，不发信) ===
        update_prompt = f"""
        当前状态: {json.dumps(self.project_state)}
        收到消息: {incoming_mail}
        
        任务:
        1. 根据消息更新任务状态 (TODO -> DONE)。
        2. 将关键结果摘要写入 key_findings。
        3. 如果有新问题，添加到 tasks。
        
        输出: 仅输出更新后的 JSON 状态。
        """
        new_state_json = await self.backend.chat(self.name, [{"role": "user", "content": update_prompt}])
        
        # 更新内存
        try:
            self.project_state = json.loads(new_state_json)
            # 存入数据库快照，方便回溯
            self.save_state_snapshot() 
        except:
            print("State update failed")

        # === Phase 2: Action Decision (只看状态，不看历史邮件) ===
        action_prompt = f"""
        当前项目状态: {json.dumps(self.project_state)}
        
        任务:
        基于当前状态，判断下一步该做什么？
        - 如果所有任务完成，回复用户。
        - 如果有 OPEN 的任务，给相应的 Worker 发邮件。
        
        输出: [Action: EMAIL] ...
        """
        response = await self.backend.chat(self.name, [{"role": "user", "content": action_prompt}])
        
        # ... 解析 response 并发信 (同 WorkerAgent) ...
        
        # === Phase 3: Context Clearing ===
        # 极其激进的策略：清空 Session History，只保留最新的状态
        # 因为所有必要信息都已经“沉淀”到 project_state 里了
        session.history = [] 
```

### 5. 对比总结：Planner vs Secretary

这下角色的差异就非常明显了：

| 特性 | **Secretary (工具人)** | **Worker (Coder/Analyst)** | **Planner (管理者)** |
| :--- | :--- | :--- | :--- |
| **核心机制** | Function Calling | ReAct / Standard Chat | **State Update Loop** |
| **记忆类型** | 无记忆 (Stateless) | 短期会话 (Session History) | **长期结构化状态 (Artifact)** |
| **Context策略**| 用完即弃 | 任务结束即弃 | **不断重写与覆盖** |
| **主要能力** | 翻译 (NL $\to$ Code) | 执行 (NL $\to$ Output) | **归纳与调度 (Info $\to$ State)** |



*   **Planner** 必须继承自 `StatefulAgent`。
*   它的 System Prompt 不再是“你是一个助手”，而是定义 **State Schema（状态的结构）**。
    *   例如：“你的内存由 `Plan List` 和 `Data Summary` 组成。你永远不要相信你的聊天记录，只相信你的内存。”

这种设计让 Planner 即使运行了一个月，处理了 1000 封邮件，它每次发令时发给 LLM 的 Token 数可能依然只有 2k (Current State)，而不是 200k (Full History)。这才是能够长期稳定运行的关键。