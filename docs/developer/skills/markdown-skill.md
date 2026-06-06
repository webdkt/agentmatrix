# 编写 Markdown Skill

Markdown Skill 是 AgentMatrix 中最轻量的扩展方式。不需要写任何代码，只需要写一个 Markdown 文件，描述过程性知识或操作步骤，Agent 就会把它当作指南来遵循。

---

## 本质

Markdown Skill 不是程序，而是文档。Agent 在处理任务时，会把 Markdown Skill 的内容插入到 System Prompt 中。当 Agent 遇到相关场景时，它会参考这些文档中的步骤和规则来指导自己的行为。

你可以把它理解为给 Agent 发了一份「操作手册」或「工作规范」。

---

## 存放位置

Markdown Skill 文件放在 MatrixWorld 工作区的 `SKILLS/` 目录下。文件名就是 Skill 名（例如 `git-workflow.md`）。

系统启动时会扫描这个目录，自动加载所有 Markdown Skill。

---

## 内容格式

Markdown Skill 没有强制的格式要求，但建议包含以下内容：

### 标题和简介

开头用标题说明这份文档的主题，用一段简介说明适用场景。

### 步骤列表

用编号列表或任务列表描述具体的操作步骤。Agent 会按顺序参考这些步骤。

### 规则和约束

用引用块或加粗文本强调重要的规则和约束条件。

### 示例

提供具体的输入/输出示例，帮助 Agent 理解期望的行为。

### 常见错误

列出常见的错误和对应的处理方式。

---

## 适用场景

Markdown Skill 特别适合以下场景：

### 标准操作流程（SOP）

例如「代码审查流程」：
- 检查代码风格
- 检查潜在的安全问题
- 检查测试覆盖率
- 给出具体的修改建议

### 工作流定义

例如「Git 工作流」：
- 创建功能分支的命名规范
- 提交信息的格式要求
- 合并前的检查清单
- 版本号升级规则

### 领域专业知识

例如「医疗数据脱敏规范」：
- 哪些字段属于敏感信息
- 脱敏的具体方法
- 脱敏后的验证步骤
- 合规要求

### 项目特定规范

例如「本项目的 API 设计规范」：
- 命名约定
- 参数格式
- 错误码定义
- 文档要求

---

## 与 Python Skill 的配合

Markdown Skill 和 Python Skill 可以配合使用：

- Markdown Skill 定义「做什么」和「怎么做」
- Python Skill 提供「做这件事的工具」

例如，一个「数据分析流程」Markdown Skill 描述了分析数据的标准步骤，而 Python Skill 提供了读取数据、清洗数据、生成图表的具体 Action。Agent 先参考 Markdown Skill 了解流程，然后调用 Python Skill 的 Action 来执行每一步。

---

## 注意事项

### 长度控制

Markdown Skill 的内容会被插入到 System Prompt 中，过长的文档会占用大量上下文空间。建议：
- 保持简洁，聚焦核心流程
- 把详细的参考资料放在外部，用链接引用
- 如果文档很长，考虑拆分成多个小的 Markdown Skill

### 清晰优先

Markdown Skill 的读者是 LLM，不是人类。虽然 LLM 能理解复杂的自然语言，但清晰的结构和明确的指令会得到更好的遵循效果。

### 版本管理

Markdown Skill 作为项目知识的一部分，应该纳入版本控制。当规范发生变化时，更新 Markdown Skill 文件即可，所有使用该 Skill 的 Agent 会自动使用最新版本。

### 没有执行保证

Markdown Skill 只是给 Agent 的参考指南，Agent 可以选择遵循也可以不遵循。如果需要强制执行某些规则，应该通过 Python Skill 在代码层面实现校验。
