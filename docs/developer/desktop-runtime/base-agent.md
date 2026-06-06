# BaseAgent — Agent 生命周期与状态机

BaseAgent 是 Desktop 运行时的核心 Agent 实现。它继承自 Core 层的 BasicAgent，增加了状态管理、PostOffice 集成、容器管理和前端事件推送等 Desktop 场景特有的功能。

---

## 状态机

BaseAgent 维护一个明确的状态机，反映当前的任务执行情况：

```
         ┌─────────────┐
         │    IDLE     │ ← 初始状态，等待新邮件
         └──────┬──────┘
                │ 收到新邮件
                ▼
         ┌─────────────┐
         │  THINKING   │ ← 正在分析任务、规划步骤
         └──────┬──────┘
                │ 规划完成，开始执行
                ▼
         ┌─────────────┐
         │  WORKING    │ ← 正在执行 Action
         └──────┬──────┘
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
┌───────┐  ┌─────────┐  ┌────────┐
│ PAUSED │  │RECOVERING│  │  IDLE  │
└───┬───┘  └────┬─────┘  └────────┘
    │           │
    ▼           ▼
┌─────────┐  ┌────────┐
│ WORKING │  │ WORKING│
│(resumed)│  │(after  │
│         │  │recover)│
└─────────┘  └────────┘
```

### 状态说明

| 状态 | 含义 |
|------|------|
| IDLE | 空闲，等待新邮件 |
| THINKING | 正在思考如何完成任务 |
| WORKING | 正在执行具体的 Action |
| RECOVERING | LLM 服务中断后正在恢复 |
| PAUSED | 被用户暂停，可以在任意时刻恢复 |
| STOPPED | 当前任务被停止 |
| ERROR | 执行过程中发生不可恢复的错误 |

### 状态历史

BaseAgent 维护最近 10 条状态变更记录，包括状态值和时间戳。前端可以通过 API 查询这些历史，绘制状态变化时间线。

---

## 信号路由

BaseAgent 的主循环从 inbox（input_queue）中消费 Signal，根据当前状态决定如何处理：

### 无活跃 MicroAgent

如果当前没有正在执行的 MicroAgent，收到新 Signal 后：
1. 解析 Signal 中的会话信息
2. 创建新的 MicroAgent
3. 将 Signal 投递给 MicroAgent
4. 状态从 IDLE 变为 THINKING

### 同 Session

如果 Signal 属于当前正在处理的 Session：
1. 直接将 Signal 投递给活跃的 MicroAgent
2. MicroAgent 继续执行循环

### 不同 Session（Lazy Deactivate）

如果 Signal 属于另一个 Session：
1. 先暂停当前 MicroAgent（不是立即停止，而是等当前动作完成）
2. 保存当前 MicroAgent 的状态
3. 激活目标 Session 的 MicroAgent（如果之前创建过则复用，否则新建）
4. 将 Signal 投递给新的 MicroAgent

这种「Lazy Deactivate」机制避免了在 Action 执行中途强制切换上下文导致的状态不一致。

---

## 暂停、恢复与停止

### 暂停

用户请求暂停时：
1. 在 BaseAgent 上设置暂停标志
2. MicroAgent 在执行到下一个 Checkpoint 时检测到标志
3. Checkpoint 阻塞等待恢复信号
4. 状态变为 PAUSED

暂停是协作式的，MicroAgent 会完成当前 Action 后才真正停下来。

### 恢复

用户请求恢复时：
1. 向 BaseAgent 发送恢复 Signal
2. Checkpoint 解除阻塞
3. MicroAgent 继续执行循环
4. 状态从 PAUSED 变为 WORKING

### 停止

用户请求停止时：
1. 在 BaseAgent 上设置停止标志
2. MicroAgent 在 Checkpoint 检测到标志后抛出停止异常
3. 执行循环终止，MicroAgent 被回收
4. 状态变为 STOPPED，然后回到 IDLE

停止当前任务不会影响 Agent 接收和处理其他邮件的能力。

---

## 事件推送

BaseAgent 的状态变化和执行事件通过以下方式推送到前端：

1. Agent 产生事件（状态变化、思考内容、Action 执行等）
2. 事件被放入 event_queue
3. Runtime 的事件总线消费这些事件
4. 通过 WebSocket 推送到前端
5. 前端更新界面

这种设计使得前端可以实时看到 Agent 在做什么，而不需要轮询。

---

## 与容器的关系

BaseAgent 本身不直接管理容器。当需要执行 Action 时：

1. BaseAgent 调用 Action 方法
2. Action 方法内部根据配置决定是在本地执行还是在容器中执行
3. 如果是容器模式，Action 通过容器适配器在容器内执行
4. 执行结果返回给 Action 方法，再返回给 MicroAgent

这种设计使得容器管理对 BaseAgent 和 MicroAgent 透明。Action 开发者不需要关心容器细节，除非特别需要。
