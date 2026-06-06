# Action 系统

Action 是 Agent 可调用的能力单元。AgentMatrix 的所有功能——读文件、写文件、搜索网页、发邮件——都是通过 Action 暴露给 MicroAgent 的。

---

## Action 的本质

一个 Action 包含：

- **名称**：在系统中的唯一标识，通常以 `skill_name.action_name` 的格式命名
- **简短描述**：一句话说明这个 Action 是做什么的
- **详细描述**：更完整的说明，包括使用场景和注意事项
- **参数信息**：每个参数的名称、类型、是否必填、默认值和描述
- **实现方法**：实际的执行逻辑

Action 不是独立存在的，它们被组织在 Skill 中。一个 Skill 是一组相关 Action 的集合。

---

## 注册与发现

Action 通过装饰器注册到 Action Registry。注册时，系统会：

1. 解析方法的参数签名
2. 提取文档字符串中的描述信息
3. 将 Action 按 Skill 分组存储
4. 建立动作名到方法的映射（支持短名和全名）

MicroAgent 在执行阶段需要调用 Action 时，通过动作名在 Registry 中查找对应的方法。查找支持以下方式：

- 全名：`file.read`
- 短名：`read`（如果在当前 Skill 范围内唯一）
- 别名：系统为常用 Action 提供别名以方便调用

---

## 执行流程

当 Cerebellum 解析出一个动作意图后：

1. MicroAgent 用动作名在 Registry 中查找对应方法
2. 如果找不到，向 Brain 报告错误，让 Brain 重新思考
3. 如果找到，用 Cerebellum 提取的参数调用方法
4. 方法执行完成后，返回结果（字符串或结构化数据）
5. 结果被追加到对话历史中，作为下一步 Think 的上下文

---

## 错误处理

Action 执行可能失败，常见原因包括：

- **参数错误**：必填参数缺失、类型不匹配、值超出有效范围
- **运行时错误**：文件不存在、网络超时、权限不足
- **逻辑错误**：前置条件不满足（例如尝试读取未创建的变量）

错误信息会被捕获并返回给 MicroAgent，MicroAgent 把错误描述追加到对话历史中。Brain 看到错误后会重新思考，通常会选择修正参数后重试，或换一个 Action 来达成目标。

系统内置了重试机制。对于可恢复的错误（如网络超时），MicroAgent 会自动重试一定次数。

---

## Action 与 Skill 的关系

Skill 是 Action 的容器，但 Skill 本身不只是 Action 的集合。Skill 还可以：

- 声明依赖其他 Skill（自动解析）
- 提供初始化逻辑（如建立数据库连接）
- 定义共享的状态或配置
- 提供辅助方法供内部 Action 使用

当一个 MicroAgent 被创建时，系统根据可用技能列表收集所有相关的 Action，注册到同一个 Registry 中。这意味着一个 MicroAgent 可以同时使用来自多个 Skill 的 Action，即使这些 Skill 之间没有显式的依赖声明。

---

## 内置 Action 示例

以下是一些常见的内置 Action（只列举，不展示实现）：

- `file.read` — 读取文件内容
- `file.write` — 写入文件
- `file.list_dir` — 列出目录内容
- `shell.bash` — 执行 shell 命令
- `web_search.search` — 网页搜索
- `browser.navigate` — 浏览器导航
- `browser.click` — 点击页面元素
- `email.send` — 向其他 Agent 发送邮件
- `memory.write` — 写入长期记忆
- `memory.read` — 读取长期记忆
- `scheduler.schedule` — 创建定时任务
