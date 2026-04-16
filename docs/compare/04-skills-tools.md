# 04 — 技能/工具系统

## 注册模式

### AgentMatrix: @register_action + Mixin 类

AgentMatrix 的技能是 **Python Mixin 类**，通过 `@register_action` 装饰器注册方法为 Agent 动作（`src/agentmatrix/core/action.py`）：

```python
class FileSkillMixin:
    @register_action(
        short_desc="读取文件内容",
        description="读取指定路径的文件内容，返回文件文本",
        param_infos={"file_path": "文件的绝对路径"}
    )
    async def read_file(self, file_path: str) -> str:
        ...
```

`SkillRegistry`（`src/agentmatrix/skills/registry.py`）实现懒加载：
1. 按名称在多个搜索路径中查找 `{name}_skill.py`
2. 找到 `{Name}SkillMixin` 类
3. 解析依赖（`_skill_dependencies` 声明）
4. 缓存到 `_python_mixins`

### Hermes Agent: 自注册 ToolRegistry

Hermes 使用 **自注册模式**（`tools/registry.py`）。每个工具文件在模块级别调用 `registry.register()`：

```python
# tools/web_tools.py 模块级别
registry.register(
    name="web_search",
    toolset="web",
    schema={...},
    handler=web_search_handler,
    description="Search the web",
    emoji="🔍",
)
```

`discover_builtin_tools()` 通过 **AST 检查**自动发现包含 `registry.register()` 调用的模块，无需手动维护工具列表。

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **注册方式** | 装饰器 + Mixin 类 | 模块级函数调用 |
| **发现机制** | 按名称搜索文件 → 导入 Mixin | AST 扫描 → 自动导入 |
| **线程安全** | 无（单线程 asyncio） | RLock 保护（多线程安全） |
| **代码组织** | 一个技能 = 一个 Mixin 类（方法集合） | 一个工具 = 一个独立函数 |

## 组合模型

### AgentMatrix: 动态 Mixin 合成

这是 AgentMatrix 最独特的设计之一。MicroAgent 在创建时，通过 `_create_dynamic_class()` 将选定的 Mixin 类动态合成到实例上：

```python
# MicroAgent.__init__ 中
if available_skills:
    self.__class__ = self._create_dynamic_class(available_skills)
```

这意味着：
- 技能方法可以直接访问 Agent 状态（`self.brain`、`self.cerebellum`、`self.current_session`）
- 技能之间可以互相调用（通过 `self`）
- 每个 MicroAgent 实例拥有不同的技能组合
- 子 Agent 可以继承或覆盖父 Agent 的技能

### Hermes Agent: 独立可调用工具

Hermes 的工具是独立的函数，不与 Agent 实例绑定。工具通过 `handle_function_call()` 调度：

```python
result = handle_function_call(tool_name, tool_args, task_id)
```

工具无法直接访问 Agent 状态，需要通过参数传递上下文。优点是工具之间完全解耦，易于测试。

## 数量与广度

### AgentMatrix: ~11 个内置技能

| 技能 | 用途 |
|------|------|
| `file` | 文件读写、搜索、bash 命令 |
| `email` | 向其他 Agent 发送邮件（含附件） |
| `new_web_search` | 网页搜索与内容提取 |
| `deep_researcher` | 多阶段深度研究（规划→调研→写作） |
| `memory` | 跨会话知识/记忆搜索 |
| `agent_admin` | Agent 生命周期管理（创建/删除/重载/克隆） |
| `system_admin` | 系统配置管理 |
| `scheduler` | 定时/周期任务 |
| `markdown` | Markdown 解析与渲染 |
| `glm_image` | 图像生成 |
| `base` | 基础工具（获取当前时间等） |

此外，Agent 支持 **Markdown 技能**：在 `~/SKILLS/` 目录放置 `skill.md` 文件，提供无需代码的程序性知识。

### Hermes Agent: 50+ 工具

涵盖更广泛的领域：

| 类别 | 示例工具 |
|------|----------|
| Web | web_search, web_extract, browser_automation |
| 文件 | file_read, file_write, file_search, file_patch |
| 终端 | terminal（6 种后端：local/Docker/SSH/Modal/Daytona/Singularity） |
| 代码 | code_execution（沙箱 Python 执行） |
| 通信 | send_message（跨平台）、email |
| 多模态 | vision, tts, image_generation |
| 调度 | cronjob 管理 |
| 委派 | delegate（子任务委派） |
| MCP | mcp_tool（连接外部 MCP 服务器，~1050 行） |
| 会话 | session_search（FTS5 全文搜索） |
| 技能 | skill_manager（技能 CRUD） |
| 规划 | todo（任务规划） |
| 交互 | clarify（追问澄清） |
| 记忆 | memory（持久化记忆） |

## 标准化

### AgentMatrix: 自有 API

AgentMatrix 的 `@register_action` 装饰器和 Mixin 模式是项目自定义的 API，不遵循外部标准。

### Hermes Agent: agentskills.io 开放标准

Hermes 的技能遵循 [agentskills.io](https://agentskills.io) 开放标准。每个技能是一个目录，包含 `SKILL.md` 和可选参考文档。这意味着：
- 技能可以在不同兼容框架间移植
- 社区可以贡献标准化的技能包
- `hermes_cli/skills_hub.py` 提供技能浏览、搜索、安装功能

## 参数发现机制

### AgentMatrix: Cerebellum 自然语言解析

Brain 在 `[ACTION]` 标签中用自然语言表达意图，Cerebellum 负责从中解析出结构化参数。参数 Schema 定义在 `@register_action` 的 `param_infos` 中。

优势：Brain 完全不需要关心 JSON 格式，只需自然语言描述意图。
劣势：需要额外的 LLM 调用（Cerebellum），增加延迟和成本。

### Hermes Agent: JSON Schema Function Calling

Hermes 使用标准的 OpenAI function calling 格式。工具注册时提供 JSON Schema，模型直接输出结构化参数。

优势：标准协议，模型广泛支持，无需额外 LLM 调用。
劣势：模型需要"学会"输出正确的 JSON，对于复杂参数可能出错。

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **注册模式** | @register_action + Mixin 类 | 自注册 ToolRegistry |
| **组合方式** | 运行时动态 Mixin 合成 | 独立函数解耦调用 |
| **技能数量** | ~11 个 | 50+ 个 |
| **覆盖领域** | 偏重多 Agent 协作和研究 | 全面覆盖（Web/终端/多模态/调度） |
| **标准化** | 自有 API | agentskills.io 开放标准 |
| **参数解析** | Cerebellum 自然语言解析 | JSON Schema function calling |
| **优势** | 技能可访问 Agent 状态，组合灵活 | 生态丰富，标准可移植 |
| **劣势** | 生态小，标准封闭 | 工具无法直接访问 Agent 内部状态 |
