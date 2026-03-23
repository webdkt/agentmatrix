# MicroAgent 执行循环

**版本**: v1.0
**最后更新**: 2026-03-23

---

## 概述

MicroAgent 是 AgentMatrix 的执行引擎。它运行一个 **Think → Act** 循环，每一步向 LLM 提供完整的对话上下文，LLM 输出思考过程和行动指令，系统执行行动并将结果反馈给 LLM，如此反复直到任务完成。

---

## 执行流程

### 入口

每次执行从 `MicroAgent.execute()` 开始。调用方提供：
- **task**: 本轮的任务描述（通常是邮件内容或子任务描述）
- **persona**: Agent 的身份/角色描述
- **available_skills**: 本次执行可用的技能列表
- **session**（可选）: 持久化会话，用于跨邮件恢复上下文

### 主循环

循环从 `_run_loop()` 开始，每一步包含三个阶段：

**1. Think（思考）**

将完整的对话消息列表发送给 LLM。LLM 返回包含思考过程和行动指令的回复。

**2. Detect Actions（行动识别）**

从 LLM 的回复中提取行动声明。先通过正则匹配，再用 LLM 做验证，确保提取的行动名称有效。

**3. Execute Actions（行动执行）**

逐个执行识别到的行动。每个行动的参数通过 Cerebellum（小脑）从 LLM 的思考文本中解析。执行结果作为 user message 追加到对话历史，供下一步 Think 使用。

### 循环终止

循环在以下情况下结束：
- LLM 调用 `all_finished`，返回最终结果
- 达到最大步数限制
- 达到最大时间限制
- 触发 `exit_actions` 中指定的退出行动

---

## 上下文结构

### 消息列表的演变

初始状态：
- system: 完整的系统提示词（包含 persona、可用工具列表、响应协议）
- user: 任务描述

每一步循环后，追加：
- assistant: LLM 的回复（思考 + 行动声明）
- user: 行动执行结果（或错误信息）

随着循环推进，消息列表不断增长，形成完整的对话历史。

### 系统提示词

系统提示词在执行期间保持不变，包含：
- Agent 的 persona（身份描述）
- 运行环境说明（循环机制、无状态工具的特性）
- 可用工具列表（按 Skill 分组，含简短描述）
- 响应协议（THOUGHTS / ACTION 的输出格式要求）
- 协作网络（黄页，其他 Agent 的联系方式）

### Cerebellum（小脑）— 参数解析

行动参数的解析由 Cerebellum 独立完成，使用独立的对话历史（negotiation_history），不影响主对话上下文。

流程：
- Cerebellum 收到行动名称、参数定义、LLM 的思考文本
- 用独立的 system prompt 和思考文本构造对话
- 如果参数不明确，Cerebellum 可以向 Brain（大脑）提问获取澄清
- 最终返回解析好的参数字典

---

## 上下文压缩

### 触发条件

- **自动触发**: 每步循环开始时检查消息总 token 数，超过阈值时触发
- **主动触发**: LLM 通过 `update_memory` 行动主动调用

### 压缩过程

1. 将当前全部对话历史（排除 system message）发送给 LLM
2. LLM 生成 Whiteboard（状态白板），是对对话历史的结构化摘要
3. 用 Whiteboard 替换所有 user/assistant 消息，保留 system message

压缩后的消息列表变为：
- system: 原始系统提示词（不变）
- user: 原始任务内容 + [WHITEBOARD] + Whiteboard 内容

### Whiteboard 生成

Whiteboard 不是简单的总结，而是让 LLM 扮演"上下文架构师"，根据对话场景动态构建最合适的结构：

- 识别对话类型（任务导向、知识探索等），生成适配的标题结构
- 如果已有旧 Whiteboard，继承其结构并更新内容
- 去噪、消歧、保留客观事实和关键结论

Whiteboard 必须包含一个"关键上下文"区域，用于兜底非结构化信息。

---

## 两种 MicroAgent

### Top-level MicroAgent

由 BaseAgent 的 `process_email` 创建，是邮件处理的顶层执行单元。

特点：
- 拥有持久化 Session，对话历史保存到磁盘
- 压缩时使用邮件历史作为锚点（从 PostOffice 获取该 Session 的全部邮件）
- 压缩前将待总结的消息推送给 history_worker（后台异步生成长期记忆）
- update_memory 执行时会持久化 Whiteboard 到文件、Timeline 事件到数据库

### Nested MicroAgent

由行动在循环中递归创建，用于执行子任务。

特点：
- 无持久化 Session，所有数据在内存中
- execute 结束后上下文即销毁
- 压缩时使用原始任务描述作为锚点
- 不涉及持久化操作

两种 MicroAgent 共享相同的执行循环逻辑和工具体系，区别仅在于上下文的生命周期管理。

---

## 关键设计决策

### 为什么每次 Think 都发送完整上下文？

LLM 是无状态的，每次调用都需要完整信息。系统不依赖 LLM 自身的记忆能力，而是通过管理消息列表来控制上下文。

### 为什么行动结果直接追加为 user message？

保持对话的自然轮次结构。LLM 在下一步 Think 时可以看到自己之前的思考和对应的执行结果，形成完整的因果链。

### 为什么用 Whiteboard 而不是简单总结？

简单总结会丢失结构化信息。Whiteboard 让 LLM 根据对话场景动态选择最合适的组织方式，保留对后续决策真正重要的信息。

### 为什么 Top-level 和 Nested 共用同一套循环？

统一的执行模型降低了框架复杂度。持久化是外层（BaseAgent）的职责，MicroAgent 本身不关心数据是否持久化。
