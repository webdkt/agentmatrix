# 自然语言管理 Agent

AgentMatrix 中有一个特殊的内置 Agent 叫 **AgentAdmin**，专门用来管理其他 Agent 的生命周期。你可以用自然语言创建、修改、克隆、删除 Agent，而不需要手动编辑配置文件。

---

## AgentAdmin 能做什么

- **创建 Agent**：指定名字、描述、人设、技能、使用的模型
- **克隆 Agent**：基于现有 Agent 创建副本，然后修改
- **编辑 Agent**：修改已有 Agent 的描述、人设、技能或模型
- **删除 Agent**：从系统中移除一个 Agent
- **启停任务**：停止某个 Agent 当前正在执行的任务
- **查看配置**：列出所有 Agent 或查看某个 Agent 的详细配置
- **版本回滚**：恢复到某个历史版本的 Agent 配置

---

## 如何使用

给 AgentAdmin 发一封邮件，用自然语言描述你的需求。例如：

> "创建一个名字叫 Researcher 的 Agent，擅长网页搜索和资料整理，给它 web_search、memory 和 file 技能"

AgentAdmin 收到后会：

1. 检查名字是否已存在
2. 验证你提到的技能是否已在系统中注册
3. 验证指定的模型是否可用
4. 自动生成合理的描述和人设（如果你没指定）
5. 创建 Agent 配置文件
6. 通知 Runtime 加载新 Agent
7. 向你汇报结果

---

## 示例

**创建 Agent**

> "创建一个叫 Coder 的 Agent，专门写 Python 代码，给它 file、shell 和 memory 技能，用 gpt4o 模型"

**克隆 Agent**

> "把 Writer 克隆成 Editor，Editor 要额外带一个 markdown 技能"

**修改 Agent**

> "给 Researcher 添加 browser 技能" / "把 Coder 的模型换成 claude-sonnet"

**删除 Agent**

> "删除 Editor"

**查看信息**

> "列出所有 Agent" / "显示 Writer 的详细配置"

**停止任务**

> "停止 Researcher 的当前任务"

---

## 配置版本管理

AgentAdmin 在每次修改 Agent 配置前都会自动备份旧版本。备份文件按时间戳存放在 MatrixWorld 的备份目录中。

如果你发现修改后的 Agent 行为不对，可以告诉 AgentAdmin：

- "恢复 Researcher 到昨天的配置"
- "显示 Researcher 的历史版本"
- "回滚到上一个版本"

---

## 创建时的自动补全

如果你创建 Agent 时没指定某些字段，AgentAdmin 会自动补全：

- **描述**：基于名字和技能自动生成一段简短的职责说明
- **人设**：基于描述和技能自动生成一段 Persona
- **模型**：如果没指定，使用系统默认模型

你当然可以在创建后随时修改这些自动生成的内容。

---

## 注意事项

AgentAdmin 不能删除它自己和 SystemAdmin。这是系统的保护机制，防止误操作导致无法恢复。

删除 Agent 时，该 Agent 的历史邮件和会话数据不会被删除，只是 Agent 本身不再加载。如果你之后用相同名字重新创建，之前的历史数据仍然可见。
