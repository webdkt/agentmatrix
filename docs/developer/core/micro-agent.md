# MicroAgent — 任务执行引擎

MicroAgent 是 AgentMatrix Core 层的核心执行单元。它的职责很简单：接收一个任务，执行它，返回结果。

---

## 定位

MicroAgent 不是长期运行的 Agent。它是为单个任务临时创建的轻量级执行器，任务完成后即被回收。

你可以把它理解为一个"智能函数"：输入是自然语言描述的任务，输出是执行结果。函数内部使用 LLM 来推理、规划和执行。

---

## 执行循环

MicroAgent 的核心是一个循环，每一步包含三个阶段：

### Think（思考）

MicroAgent 把当前任务和历史上下文发给 Brain（大模型），要求它用自然语言思考下一步该做什么。Brain 的输出是完全自由的文本，不需要遵循任何格式。

### Negotiate（协商）

Brain 的思考输出被交给 Cerebellum。Cerebellum 分析这段自然语言，判断 Agent 想要执行什么动作，并提取参数。如果意图明确，Cerebellum 返回动作名和参数。如果意图模糊，Cerebellum 会生成一个澄清请求，MicroAgent 把这个问题反馈给 Brain，让 Brain 重新思考。

### Act（执行）

Cerebellum 解析出的动作名和参数被用来在 Action Registry 中查找对应的 Action 方法，然后执行。执行结果（成功或失败）被追加到对话历史中，作为下一步 Think 的上下文。

### 循环终止

循环在以下情况下终止：

- Brain 明确表示任务已完成
- 执行出错且重试失败
- 达到最大迭代次数
- 被外部暂停或停止

---

## 组件继承

MicroAgent 自己不持有 Brain、Cerebellum 或 Action Registry。这些组件从它的父级（创建它的 Agent）继承。这意味着：

- 同一个 BaseAgent 创建的所有 MicroAgent 共享同一套 Brain 和 Cerebellum
- 配置变更（如切换模型）在 BaseAgent 上生效后，后续创建的 MicroAgent 自动使用新配置
- MicroAgent 可以通过 parent 链追溯到根 Agent

这种设计避免了为每个任务重复创建昂贵的 LLM 客户端连接。

---

## 动态技能组合

MicroAgent 在创建时会根据可用技能列表动态组合 Mixin 类。系统会：

1. 从 Skill Registry 中查找指定的技能
2. 收集每个技能的 Mixin 类
3. 动态创建一个新的类，继承所有 Mixin
4. 实例化这个类作为 MicroAgent

这意味着 MicroAgent 的能力不是硬编码的，而是在运行时根据任务需求组装的。同一个 BaseAgent 可以在不同任务中使用不同的技能组合。

---

## 嵌套调用

MicroAgent 可以创建子 MicroAgent 来执行子任务。这在以下场景中很有用：

- 一个复杂任务需要拆分为多个独立子任务
- 子任务需要不同的技能组合
- 需要限制子任务的上下文范围

子 MicroAgent 从父 MicroAgent 继承组件，但可以有自己的技能列表和系统提示。父 MicroAgent 等待子任务完成后，把结果合并到自己的上下文中继续执行。

---

## 与 BasicAgent 的关系

BasicAgent 是 Core 层提供的通用 Agent 参考实现，负责信号路由和 Session 管理。它本身不执行任务，而是在收到信号后创建 MicroAgent 来执行。

BaseAgent（Desktop 运行时）继承 BasicAgent，添加了 Desktop 场景特有的功能（状态机、PostOffice 集成、容器管理等）。

关系链：用户邮件 → BaseAgent → 创建/复用 MicroAgent → 执行循环 → 返回结果 → BaseAgent 发送回复邮件。
