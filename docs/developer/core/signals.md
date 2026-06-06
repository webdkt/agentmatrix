# Signal 系统

AgentMatrix Core 层使用事件驱动模型进行内部通信。所有输入、输出和状态变化都通过 Signal 传递。

---

## 设计动机

传统的函数调用模型（请求-响应）不适合 Agent 的执行特点：

- Agent 的执行是异步的：收到任务后不会立即返回结果，而是经过多轮思考-执行循环
- Agent 可能产生多个输出：执行过程中会不断产生中间结果、状态更新和日志
- Agent 需要被外部控制：暂停、恢复、停止等操作需要在执行过程中介入

Signal 模型把这些需求统一为事件流：所有通信都是异步的、可监听的、可拦截的。

---

## 核心 Signal 类型

### 输入 Signal

从外部进入 Agent 的 Signal，通常由用户输入或系统事件触发：

- **TextSignal**：文本输入，通常是一封邮件的正文内容
- **ActionCompletedSignal**：一个 Action 执行完成的结果
- **ResumeSignal**：恢复被暂停的执行

### 输出 Signal

从 Agent 向外发出的 Signal，通知外部世界发生了什么：

- **ThinkSignal**：Brain 的思考输出，用于展示 Agent 的推理过程
- **ActionSignal**：Agent 决定执行某个 Action
- **ResultSignal**：Action 的执行结果
- **QuestionSignal**：Agent 向用户提问
- **CompleteSignal**：任务完成
- **ErrorSignal**：执行过程中发生错误

### 控制 Signal

用于控制 Agent 执行流程的 Signal：

- **PauseSignal**：请求暂停执行
- **StopSignal**：请求停止执行
- **CheckpointSignal**：到达安全检查点

---

## 队列机制

每个 Agent 有两个核心队列：

### input_queue

接收外部输入的异步队列。所有发给 Agent 的邮件、恢复信号、Action 结果都进入这个队列。Agent 的主循环从这个队列中消费 Signal。

### event_queue

向外部输出事件的异步队列。Agent 的思考、Action 调用、状态变化都转化为 Signal 放入这个队列。Shell 实现可以监听这个队列，把事件展示给用户或记录到日志。

---

## 信号路由

BasicAgent 实现了三段式信号路由：

1. **无活跃 Session**：如果 Agent 当前没有正在处理的 MicroAgent，收到新 Signal 后创建新的 MicroAgent 来处理
2. **同 Session**：如果 Signal 属于当前正在处理的 Session，直接投递给活跃的 MicroAgent
3. **不同 Session**：如果 Signal 属于另一个 Session，先暂停当前 MicroAgent（Lazy Deactivate），然后激活目标 Session 的 MicroAgent

这种路由机制使得一个 Agent 可以同时维护多个会话，在不同任务之间切换。

---

## 与前端的事件推送

在 Desktop 场景中，event_queue 中的 Signal 被转化为 WebSocket 消息，推送到前端。前端根据 Signal 类型更新界面：

- ThinkSignal → 显示 Agent 正在思考的内容
- ActionSignal → 显示正在执行的动作名称
- ResultSignal → 显示动作执行结果
- QuestionSignal → 弹出对话框等待用户输入
- StatusChange → 更新 Agent 状态指示器

这种设计使得前端不需要轮询，所有状态更新都是实时推送的。

---

## 扩展 Signal

如果你正在开发自定义 Skill 或扩展 Core 层，可以定义新的 Signal 类型。只要继承核心 Signal 基类并在适当位置发送和监听即可。

新的 Signal 类型会自动被事件系统识别和路由，不需要修改现有的队列逻辑。
