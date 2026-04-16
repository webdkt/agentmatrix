# 01 — 核心 Agent 范式

## 核心哲学

| | AgentMatrix | Hermes Agent |
|---|---|---|
| **口号** | "Let LLMs think. Don't make them write JSON." | "The self-improving AI agent" |
| **设计焦点** | 多 Agent 协作，自然语言通信 | 单 Agent 全能，工具调用 + 自进化 |
| **Agent 定义** | 数字办公室中的"员工"，通过邮件协作 | 一个能学会新技能的自主实体 |

## Agent 模型单元

### AgentMatrix: 双层架构

AgentMatrix 将 Agent 分为两层：

- **BaseAgent**（`src/agentmatrix/agents/base.py`, ~42KB）：持久化的 Agent 实例，拥有独立的 Session 管理。每个 BaseAgent 代表一个长期存在的"员工"，持续接收邮件并为每个会话创建 MicroAgent。
- **MicroAgent**（`src/agentmatrix/agents/micro_agent.py`, ~96KB）：临时、轻量级的任务执行单元。每个子任务创建一个 MicroAgent，执行完毕后销毁。类似函数调用：输入任务 → 执行 → 返回结果。

```python
# MicroAgent 创建时自动继承父 Agent 的组件
class MicroAgent(AutoLoggerMixin):
    def __init__(self, parent, name=None, available_skills=None):
        self.parent = parent
        self.persona = parent.persona
        # 动态组合 Skill Mixins
        if available_skills:
            self.__class__ = self._create_dynamic_class(available_skills)
```

关键设计：MicroAgent 通过 `parent` 参数自动继承 brain、cerebellum、action_registry 等组件，通过 `__class__` 重赋值实现运行时 Mixin 动态合成。

### Hermes Agent: 单一 AIAgent 循环

Hermes 使用单一的 `AIAgent` 类（`run_agent.py`, ~585KB），实现同步 tool-calling 对话循环：

```python
# 简化的 AIAgent 核心循环
while iterations < max_iterations:
    response = client.chat.completions.create(
        model=model, messages=messages, tools=tool_schemas
    )
    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(tool_call.name, tool_call.args)
            messages.append(tool_result_message(result))
    else:
        return response.content
```

所有能力（文件操作、浏览器、终端、委派等）都通过 tool schema 注入同一个循环，不存在 Agent 间的层级关系。

## Agent 生命周期

### AgentMatrix: 显式状态机

Agent 有明确的状态流转（IDLE → THINKING → WORKING → WAITING_FOR_USER → PAUSED/STOPPED/ERROR），带有状态历史追踪。MicroAgent 基于 **Signal 事件驱动**执行：

```python
@dataclass
class Signal:
    type: str  # "email", "action_completed", "action_failed", "actions_completed"
    payload: Any
```

Think-Negotiate-Act 循环：收到信号 → 思考 → 协商参数 → 执行动作 → 收到完成信号 → 继续思考。Agent 在没有信号时休眠，不消耗资源。

### Hermes Agent: 简单活跃/空闲循环

Hermes 的 Agent 没有显式状态机。Agent 在 `run_conversation()` 期间处于活跃状态，循环调用 LLM 直到模型返回文本（而非 tool call）为止。没有暂停、恢复等中间状态。

## 任务分解策略

### AgentMatrix: 无限嵌套 MicroAgent

MicroAgent 可以递归创建子 MicroAgent（`docs/core/11-*.md`），形成父子→孙级的嵌套树：

- 父 Agent 等待子 Agent 完成（同步嵌套）
- 父 Agent 可创建多个子 Agent 并 `await all`（并行）
- 所有层级共享同一个 Brain/Cerebellum（通过 `root_agent` 引用）
- 子 Agent 可以拥有不同的 skills 组合

典型场景：并行搜索（多个子 Agent 同时搜索不同方向）、多阶段研究（规划 → 调研 → 写作）。

### Hermes Agent: 进程内委派

Hermes 通过 `delegate_tool.py` 在同一个 agent loop 内委派子任务。子 Agent 运行在独立的 `AIAgent` 实例中，但没有递归嵌套的概念，也不存在组件共享机制。委派是工具调用的一种，与其他工具（文件操作、浏览器）地位相同。

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **Agent 本质** | 有生命周期的"员工" | 全能的工具调用循环 |
| **层级关系** | BaseAgent → MicroAgent → 子MicroAgent | 扁平，单一 AIAgent |
| **执行模式** | 事件驱动，休眠时零开销 | 同步循环，持续占用直到完成 |
| **任务分解** | 无限递归嵌套，组件共享 | 进程内委派，独立实例 |
| **优势** | 天然支持复杂多步协作 | 简单直接，易于理解和调试 |
| **劣势** | 架构复杂度高 | 难以表达多 Agent 协作场景 |
