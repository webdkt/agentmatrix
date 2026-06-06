# Skill 体系概览

Skill 是扩展 Agent 能力的主要机制。AgentMatrix 提供两条路径来扩展 Skill：编写 Python 代码（功能强大），或编写 Markdown 文档（无需代码）。

---

## 两条路径

### Python Skill

用 Python 编写，通过 Mixin 模式动态组合到 MicroAgent。适合需要复杂逻辑、外部库调用、状态管理的场景。

### Markdown Skill

用 Markdown 编写，描述过程性知识和操作步骤。适合定义 SOP、工作流、领域专业知识。Agent 会读取这些文档并当作指南来遵循。

---

## 内置 Skill 清单

以下是 AgentMatrix 当前内置的 Skill：

| Skill | 类型 | 能力说明 |
|-------|------|---------|
| base | Python | 获取当前日期时间 |
| file | Python | 文件读写、目录列表、文件搜索 |
| shell | Python | 执行 Shell 命令 |
| browser | Python | 浏览器自动化（导航、点击、表单、截图） |
| browser_control | Python | 浏览器高阶控制 |
| web_search | Python | 网页搜索与内容提取 |
| deep_researcher | Python | 多轮深度研究与综合 |
| email | Python | 向其他 Agent 发送邮件（含附件） |
| memory | Python | 长期记忆的读写与检索 |
| vision | Python | 图像分析与理解 |
| markdown | Python | Markdown 解析与渲染 |
| scheduler | Python | 定时任务与周期性任务 |
| system_admin | Python | 系统配置管理 |
| agent_admin | Python | Agent 生命周期管理 |
| sub_agent | Python | 创建和调用子 Agent |
| basic_planning | Python | 基础任务规划 |
| glm_image | Python | 图像生成 |
| git-workflow | Markdown | Git 工作流程指南 |

---

## Skill 依赖解析

Skill 可以声明依赖其他 Skill。例如，一个「数据分析」Skill 可能依赖 `file`（读取数据文件）和 `shell`（调用分析工具）。

依赖声明后，系统在加载 Skill 时会：
1. 解析依赖图
2. 按拓扑排序加载依赖
3. 检测循环依赖并报错
4. 确保被依赖的 Skill 的 Action 在依赖它的 Skill 之前注册

这避免了 Action 注册顺序导致的问题。

---

## Skill 与 MicroAgent 的动态组合

MicroAgent 在创建时根据可用技能列表动态组合 Mixin。过程如下：

1. Runtime 从 Agent 配置中读取技能列表
2. 从 Skill Registry 中查找对应的 Skill 类
3. 收集所有 Skill 的 Mixin 类
4. 动态创建一个新的类，继承所有 Mixin 和 MicroAgent 基类
5. 实例化这个动态类

这意味着：
- 同一个 Agent 在不同任务中可以使用不同的技能组合
- 新增 Skill 不需要修改 MicroAgent 的代码
- Skill 之间可以通过 Mixin 机制共享方法和状态

---

## Skill 注册路径

Skill 可以通过以下方式注册到系统：

1. **内置路径**：`agentmatrix.desktop.skills` 包下的所有 Skill 自动注册
2. **工作区路径**：MatrixWorld 的 `SKILLS/` 目录下的 Markdown Skill
3. **自定义路径**：在代码中调用 `SKILL_REGISTRY.add_search_path()` 添加新的搜索路径

系统启动时会扫描所有注册路径，加载发现的 Skill。

---

## 选择 Python Skill 还是 Markdown Skill

| | Python Skill | Markdown Skill |
|--|-------------|----------------|
| 开发成本 | 需要写代码 | 只需要写文档 |
| 能力范围 | 任何可编程逻辑 | 过程性知识和指南 |
| 状态管理 | 可以维护运行时状态 | 无状态 |
| 外部调用 | 可以调用 API、执行命令 | 不能 |
| 适用场景 | 工具型能力 | 知识型能力 |
| 示例 | 文件操作、浏览器控制 | Git 工作流、代码审查清单 |

一般建议：能用 Markdown 解决的就不要用 Python。Markdown Skill 更容易编写、更容易维护、不需要担心代码错误。
