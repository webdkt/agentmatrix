# 开发 Python Skill

Python Skill 是 AgentMatrix 中最强大的扩展方式。通过编写 Python 代码，你可以让 Agent 获得任何可编程的能力。

---

## Skill 的本质

一个 Python Skill 本质上是一个 Python Mixin 类，其中包含若干个 Action 方法。当 MicroAgent 创建时，系统会把选中的 Skill 的 Mixin 类动态组合到 MicroAgent 的类继承链中，使得 MicroAgent 可以调用这些 Action 方法。

---

## 开发步骤

### 1. 创建 Skill 目录

在 `SKILLS/` 目录（或任何已注册的 Skill 搜索路径）下创建一个新的目录，目录名就是 Skill 名。

目录结构：

```
my_skill/
├── __init__.py       # Skill 入口，导出 Mixin 类
└── skill.py          # Skill 实现
```

### 2. 编写 Mixin 类

Mixin 类是一个普通的 Python 类，包含 Action 方法。每个 Action 方法需要用装饰器注册。

Action 装饰器需要声明：
- 动作名称
- 简短描述（一句话）
- 详细描述（多行，说明使用场景和注意事项）
- 参数信息（每个参数的名称、类型、是否必填、描述）

### 3. 注册 Action

Action 方法需要用系统提供的装饰器注册。注册后，Action 会自动被收集到 Action Registry 中，MicroAgent 可以通过动作名调用它。

### 4. 声明依赖

如果 Skill 依赖其他 Skill，在 Skill 类上声明依赖列表。系统在加载时会自动解析并先加载被依赖的 Skill。

### 5. 测试

给 Agent 配置新 Skill，然后向 Agent 发送任务，验证 Skill 的 Action 是否能被正确调用和执行。

---

## Action 设计原则

### 单一职责

每个 Action 只做一件事。不要把多个不相关的功能塞进一个 Action。如果 Agent 需要完成一个复杂任务，它可以通过调用多个 Action 来组合实现。

### 幂等性

Action 尽可能设计为幂等的：同样的输入应该产生同样的输出，多次执行不应该产生副作用。这使得 Agent 在重试时不会导致重复操作。

### 清晰的错误信息

Action 失败时返回清晰的错误描述，帮助 Brain 理解问题并决定如何修正。例如，文件不存在时返回"文件 xxx 不存在"，而不是简单的"Error"。

### 合理的参数设计

- 参数名要自描述
- 必填参数尽量少，让更多参数有合理默认值
- 对于复杂输入，考虑用字符串而不是结构化数据（因为 LLM 生成字符串比生成精确的结构化数据更可靠）

---

## Skill 描述的重要性

Skill 类和每个 Action 的描述文本不是给人类读的文档，而是给 LLM 读的指令。LLM 通过描述来决定：

- 这个 Skill 是做什么的
- 这个 Action 在什么场景下使用
- 每个参数的含义和格式

因此，描述要：
- 清晰明确，避免歧义
- 包含具体的使用场景示例
- 说明参数的格式要求（如路径格式、日期格式）
- 注明限制和注意事项

---

## 状态管理

Skill Mixin 可以维护运行时状态（如数据库连接、缓存、配置等）。这些状态存储在 Mixin 实例的属性中，在 MicroAgent 的生命周期内持续存在。

注意：MicroAgent 是临时对象，任务完成后即被回收。如果需要在任务之间保持状态，应该：
- 把状态写入文件或数据库
- 使用专门的持久化 Skill（如 memory）
- 或者把状态维护在 BaseAgent 级别（而不是 MicroAgent 级别）

---

## 调试技巧

开发 Skill 时常见的调试方法：

1. **直接调用**：在 Python 交互环境中直接实例化 Skill Mixin 并调用 Action 方法，验证逻辑正确性
2. **日志输出**：在 Action 中添加日志，观察执行流程和参数值
3. **简化测试**：先用最简单的输入测试，确认基本路径通后再测试复杂场景
4. **查看 Agent 思考**：在 Desktop App 中观察 Agent 的 Think 输出，看它是如何理解 Skill 描述的
