# Micro Agent 使用指南

## 概述

Micro Agent 是一个轻量级的临时 Agent，用于处理需要多步思考的子任务。

### 核心特点

1. **无 Session 概念**：每次执行都是独立的，类似函数调用
2. **简单的动作识别**：直接从 think 输出中检测 action 名字
3. **自动参数协商**：通过 cerebellum 协商参数
4. **自主返回**：LLM 决定何时调用 `finish_task` 完成任务
5. **可重复使用**：一次初始化，多次执行不同任务
6. **临时人格**：默认继承 BaseAgent 的所有 actions（除等待类），是 BaseAgent 的临时"人格"

## 架构设计

### MicroAgent 类

```python
# 初始化（一次性设置核心组件）
micro_agent = MicroAgent(
    brain=agent.brain,
    cerebellum=agent.cerebellum,
    action_registry=agent.actions_map,
    name="MyMicroAgent",
    default_max_steps=50
)

# 执行任务（可重复调用）
result = await micro_agent.execute(
    persona="You are a code expert...",
    task="Analyze this codebase",
    available_actions=["read_file", "search_code", "finish_task"],
    task_context={"path": "/project"}
)
```

### BaseAgent 集成

BaseAgent 提供了 `_run_micro_agent()` 方法，更简洁地使用 Micro Agent：

```python
# 在 BaseAgent 的 action 中

# 方式1：使用所有 BaseAgent 的 actions（推荐）
result = await self._run_micro_agent(
    persona="You are a code analysis expert...",
    task="Analyze the project structure",
    task_context={"path": "/project"},
    max_steps=30
)
# available_actions 自动继承 BaseAgent 的所有 actions（除 rest_n_wait, take_a_break）

# 方式2：限制部分 actions
result = await self._run_micro_agent(
    persona="You are a researcher...",
    task="Research this topic",
    available_actions=["web_search", "read_file", "finish_task"],
    max_steps=20
)

# 方式3：排除特定 actions
result = await self._run_micro_agent(
    persona="You are a file processor...",
    task="Process files",
    exclude_actions=["send_email", "web_search"],  # 额外排除这些
    max_steps=30
)
```

## 基本用法

### 步骤1：注册 finish_task action

在 BaseAgent 的 `__init__` 中：

```python
from ..agents.micro_agent import FINISH_TASK_INFO

class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)

        # 注册 finish_task action
        self.actions_map["finish_task"] = FINISH_TASK_INFO["method"]
        self.actions_meta["finish_task"] = {
            "action": "finish_task",
            "description": FINISH_TASK_INFO["description"],
            "params": FINISH_TASK_INFO["param_infos"]
        }
```

### 步骤2：定义使用 Micro Agent 的 action

#### 示例1：代码分析

```python
@register_action(
    "分析代码库结构，理解项目架构",
    param_infos={
        "path": "项目路径",
        "focus": "关注重点: architecture/dependencies/tests/all"
    }
)
async def analyze_codebase(self, path: str, focus: str = "architecture"):
    """使用 Micro Agent 分析代码库"""
    persona = """You are a code analysis expert.
You carefully examine project structure, dependencies, and key files.
You provide clear, structured summaries of your findings."""

    task = f"""Analyze the codebase at {path} with focus on {focus}.

Your goal:
1. List the main directory structure
2. Identify key files and their purposes
3. Analyze dependencies and imports
4. Summarize the architecture

When you have completed the analysis, use finish_task with your summary."""

    task_context = {
        "target_path": path,
        "focus_area": focus
    }

    # 使用所有 BaseAgent 的 actions（默认）
    result = await self._run_micro_agent(
        persona=persona,
        task=task,
        task_context=task_context,
        max_steps=30
    )

    return f"""Codebase Analysis completed:
Focus: {focus}
Path: {path}

Summary:
{result}
"""
```

#### 示例2：深度研究

```python
@register_action(
    "深入研究一个主题，搜索并整合信息",
    param_infos={
        "topic": "研究主题",
        "max_sources": "最大信息源数量（默认5）",
        "depth": "研究深度: quick/standard/deep"
    }
)
async def deep_research(self, topic: str, max_sources: int = 5, depth: str = "standard"):
    """使用 Micro Agent 进行深度研究"""
    persona = """You are an expert researcher.
You know how to find, evaluate, and synthesize information from multiple sources.
You provide well-structured, accurate summaries."""

    task = f"""Research the topic: {topic}

Requirements:
- Gather information from at least {max_sources} sources
- Depth level: {depth}
- Evaluate the credibility of sources
- Synthesize findings into a coherent summary

Use search, read sources, and when done, call finish_task with your research summary."""

    task_context = {
        "topic": topic,
        "max_sources": max_sources,
        "depth_level": depth
    }

    # 限制为研究相关的 actions
    result = await self._run_micro_agent(
        persona=persona,
        task=task,
        available_actions=[
            "web_search",
            "read_webpage",
            "summarize_text",
            "take_notes",
            "finish_task"
        ],
        task_context=task_context,
        max_steps=40
    )

    return f"""Research completed on: {topic}
Sources gathered: {max_sources}
Depth: {depth}

Findings:
{result}
"""
```

#### 示例3：文件处理管道

```python
@register_action(
    "处理多个文件，执行转换和分析",
    param_infos={
        "file_pattern": "文件匹配模式（如 *.py）",
        "operation": "操作类型: count/analyze/convert"
    }
)
async def process_files(self, file_pattern: str, operation: str = "analyze"):
    """使用 Micro Agent 处理多个文件"""
    persona = """You are a file processing specialist.
You efficiently handle multiple files and perform various operations."""

    task = f"""Process all files matching pattern: {file_pattern}
Operation: {operation}

Steps:
1. Find all matching files
2. Process each file according to the operation
3. Aggregate results
4. Call finish_task with the final report"""

    task_context = {
        "pattern": file_pattern,
        "operation": operation
    }

    # 排除不需要的 actions（如发邮件）
    result = await self._run_micro_agent(
        persona=persona,
        task=task,
        task_context=task_context,
        exclude_actions=["send_email", "web_search"],
        max_steps=50
    )

    return f"File processing completed:\n{result}"
```

## 高级用法

### 动态 Actions 列表

根据上下文动态决定可用 actions：

```python
@register_action("智能文件处理")
async def smart_file_processing(self, path: str):
    """根据文件类型动态选择 actions"""
    # 检测文件类型
    if path.endswith(".py"):
        available_actions = ["analyze_python", "check_imports", "find_classes", "finish_task"]
        persona = "You are a Python code analyst."
    elif path.endswith(".md"):
        available_actions = ["parse_markdown", "extract_links", "summarize", "finish_task"]
        persona = "You are a document processor."
    else:
        # 使用所有默认 actions
        available_actions = None
        persona = "You are a general file processor."

    task = f"Process the file at {path} according to its type."

    result = await self._run_micro_agent(
        persona=persona,
        task=task,
        available_actions=available_actions,
        task_context={"file_path": path},
        max_steps=20
    )

    return result
```

### Micro Agent 作为"临时人格"

Micro Agent 是 BaseAgent 的临时人格，继承所有能力但有不同的个性：

```python
@register_action("以不同角色分析问题")
async def analyze_from_different_perspectives(self, problem: str):
    """从不同角度分析同一个问题"""

    perspectives = []

    # 人格1：安全专家
    security_view = await self._run_micro_agent(
        persona="You are a security expert. Focus on vulnerabilities and threats.",
        task=f"Analyze this problem from a security perspective: {problem}",
        max_steps=20
    )
    perspectives.append(f"Security Expert View:\n{security_view}")

    # 人格2：性能专家
    performance_view = await self._run_micro_agent(
        persona="You are a performance optimization expert. Focus on efficiency.",
        task=f"Analyze this problem from a performance perspective: {problem}",
        max_steps=20
    )
    perspectives.append(f"Performance Expert View:\n{performance_view}")

    # 人格3：用户体验专家
    ux_view = await self._run_micro_agent(
        persona="You are a UX expert. Focus on user experience and accessibility.",
        task=f"Analyze this problem from a UX perspective: {problem}",
        max_steps=20
    )
    perspectives.append(f"UX Expert View:\n{ux_view}")

    return "\n\n".join(perspectives)
```

### 传递工作区上下文

```python
@register_action("分析用户工作区")
async def analyze_user_workspace(self, focus: str = "structure"):
    """分析当前用户的工作区"""
    workspace = self.current_workspace

    result = await self._run_micro_agent(
        persona="You are a workspace organization expert.",
        task=f"Analyze the workspace at {workspace}",
        available_actions=[
            "list_files",
            "read_file",
            "get_file_stats",
            "finish_task"
        ],
        task_context={
            "workspace_path": str(workspace),
            "focus": focus
        }
    )

    return result
```

### 多阶段任务（嵌套调用）

```python
@register_action("分析并重构代码")
async def analyze_and_refactor(self, path: str):
    """多阶段任务：先分析，再重构"""

    # 阶段1：分析
    analysis = await self._run_micro_agent(
        persona="You are a code analyst. Identify issues and improvement opportunities.",
        task=f"Analyze code at {path} and list problems",
        available_actions=["read_file", "search_code", "finish_task"],
        task_context={"path": path},
        max_steps=20
    )

    # 阶段2：重构（基于分析结果）
    refactoring = await self._run_micro_agent(
        persona="You are a code refactoring expert. Apply best practices.",
        task=f"""Refactor the code at {path} based on this analysis:
{analysis}

Make the improvements necessary.""",
        available_actions=["read_file", "edit_file", "finish_task"],
        task_context={"path": path, "analysis": analysis},
        max_steps=40
    )

    return f"""Analysis and Refactoring completed:

Analysis:
{analysis}

Refactoring:
{refactoring}
"""
```

## 最佳实践

### 1. 明确定义 Persona

```python
# 好的 persona
persona = """You are a security expert with 10 years of experience.
You carefully identify vulnerabilities and provide actionable recommendations.
You think step by step and document your reasoning."""

# 不好的 persona
persona = "You are helpful"  # 太模糊
```

### 2. 清晰的任务描述

```python
# 好的任务描述
task = """
Analyze the security of this web application:

Steps:
1. Check for SQL injection vulnerabilities
2. Verify authentication mechanisms
3. Review authorization checks
4. Test for XSS vulnerabilities

When complete, use finish_task with a security report.
"""

# 不好的任务描述
task = "Check security"  # 太简单
```

### 3. 合理的步数限制

```python
# 简单任务
max_steps=10

# 中等任务
max_steps=30

# 复杂任务
max_steps=50

# 非常复杂的任务
max_steps=100  # 谨慎使用
```

### 4. 限制可用 Actions

```python
# 好的做法：只给必要的 actions
available_actions = [
    "read_file",
    "search_code",
    "finish_task"
]

# 避免：给太多 actions（会降低准确率）
available_actions = list(self.actions_map.keys())  # 所有 actions
```

## 工作流程对比

### BaseAgent 主循环
```
收到邮件
  ↓
Think-Act 循环（最多100步）
  ├─ Brain think → 生成意图
  ├─ Cerebellum negotiate → 翻译为 action
  ├─ 执行 action
  └─ 结果反馈给 Brain
  ↓
调用 rest_n_wait → 等待下一封邮件
```

### Micro Agent 循环
```
创建 Micro Agent（或复用已有实例）
  ↓
设置 persona, task, available_actions
  ↓
Think-Act 循环（最多N步）
  ├─ Brain think → 生成意图
  ├─ 检测 action 名字（如 "read_file"）
  ├─ Cerebellum negotiate → 协商参数
  ├─ 执行 action
  └─ 结果反馈给 Brain
  ↓
检测到 "finish_task" → 返回结果给 BaseAgent
```

## 设计优势

### 1. 简洁性

```python
# 只需要提供两个核心参数
result = await self._run_micro_agent(
    persona="You are an expert...",
    task="Do this task...",
    available_actions=["action1", "action2", "finish_task"]
)
```

### 2. 可重用性

```python
# Micro Agent 实例会被 BaseAgent 缓存
# 可以多次执行不同的任务
result1 = await self._run_micro_agent(persona="...", task="Task 1", ...)
result2 = await self._run_micro_agent(persona="...", task="Task 2", ...)
```

### 3. 组件复用

```python
# 自动使用 BaseAgent 的核心组件
# - brain（相同的 LLM）
# - cerebellum（相同的参数协商）
# - actions_map（相同的 action 注册表）
```

### 4. 上下文隔离

```python
# Micro Agent 有独立的对话历史
# 不会污染 BaseAgent 的 session
# 每个 Micro Agent 执行都是独立的
```

## 调试技巧

### 1. 查看日志

```python
# Micro Agent 使用 DEBUG 级别日志
# 会记录每一步的思考过程
# 可以在日志中看到详细执行过程
```

### 2. 调整步数限制

```python
# 如果任务经常超时
max_steps=100  # 增加步数

# 如果任务很快完成但仍在循环
max_steps=10  # 减少步数
```

### 3. 检查 Action 检测

```python
# 如果 Micro Agent 一直不执行 action
# 检查：
# 1. action 名字是否在 available_actions 中
# 2. LLM 的 think 输出是否包含 action 名字
# 3. action 名字是否会被其他词误匹配

# 解决：使用更明确的名字
available_actions = [
    "read_file_content",  # 而不是 "read"
    "search_in_codebase",  # 而不是 "search"
]
```

### 4. 优化 Persona

```python
# 如果 Micro Agent 不听指令
# 在 persona 中强调指令遵循

persona = """
You are a code expert.

IMPORTANT:
- Always use the available actions
- When you need to read a file, mention "read_file" in your response
- When done, always use "finish_task"
- Follow the format exactly
"""
```

## 何时使用 Micro Agent vs 直接 Code

### ✅ 使用 Micro Agent

- 需要多步决策
- 步骤不确定，需要 LLM 动态规划
- 需要整合多个工具
- 任务复杂度高

示例：
```python
@register_action("分析代码架构")
async def analyze_architecture(self, path: str):
    return await self._run_micro_agent(...)  # 合适
```

### ✅ 使用直接 Code

- 步骤固定、确定
- 逻辑简单
- 性能要求高
- 不需要 LLM 决策

示例：
```python
@register_action("读取文件前100行")
async def read_first_lines(self, path: str, n: int = 100):
    # 直接用 code 更合适
    content = await self.read_file(path)
    lines = content.split('\n')[:n]
    return '\n'.join(lines)
```

## 完整示例

```python
from ..agents.base import BaseAgent
from ..agents.micro_agent import FINISH_TASK_INFO
from ..core.action import register_action

class MyWorkerAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)

        # 注册 finish_task
        self.actions_map["finish_task"] = FINISH_TASK_INFO["method"]
        self.actions_meta["finish_task"] = {
            "action": "finish_task",
            "description": FINISH_TASK_INFO["description"],
            "params": FINISH_TASK_INFO["param_infos"]
        }

    @register_action(
        "智能代码审查",
        param_infos={
            "path": "代码路径",
            "depth": "审查深度: quick/standard/deep"
        }
    )
    async def smart_code_review(self, path: str, depth: str = "standard"):
        """使用 Micro Agent 进行智能代码审查"""

        # 定义 persona
        persona = """You are a senior code reviewer with 15 years of experience.
You identify potential bugs, security issues, performance problems, and code smell.
You provide constructive, actionable feedback.
You think systematically and document your findings."""

        # 定义任务
        task = f"""Perform a {depth} code review of the code at {path}.

Review checklist:
1. Code correctness and potential bugs
2. Security vulnerabilities
3. Performance issues
4. Code readability and maintainability
5. Adherence to best practices
6. Testing coverage

For each issue found:
- Describe the problem clearly
- Explain why it's a problem
- Suggest how to fix it
- Rate severity (Critical/High/Medium/Low)

When complete, use finish_task with a comprehensive review report."""

        # 可用 actions
        available_actions = [
            "list_files",
            "read_file",
            "search_in_files",
            "analyze_complexity",
            "check_dependencies",
            "finish_task"
        ]

        # 执行
        result = await self._run_micro_agent(
            persona=persona,
            task=task,
            available_actions=available_actions,
            task_context={
                "target_path": path,
                "review_depth": depth
            },
            max_steps=50 if depth == "deep" else 30
        )

        return f"""Code Review Completed:
Path: {path}
Depth: {depth}

Report:
{result}
"""
```

## 总结

Micro Agent 提供了一种优雅的方式来处理需要多步思考的子任务：

- **统一架构**：和 BaseAgent 一样的 think-act 模式
- **简洁设计**：无 session，类似函数调用
- **易于使用**：在 BaseAgent 中只需调用 `self._run_micro_agent()`
- **可重用**：一次初始化，多次执行
- **组件复用**：自动使用 BaseAgent 的 brain、cerebellum、actions
- **临时人格**：默认继承所有 BaseAgent 的 actions（除等待类），是 BaseAgent 的临时"人格"

### 核心设计理念

**Micro Agent = BaseAgent 的临时人格**

- **相同的能力**：使用相同的 brain、cerebellum、actions
- **不同的个性**：通过 `persona` 参数定制角色和思维模式
- **独立的任务**：通过 `task` 参数指定具体任务
- **独立的上下文**：每次执行有独立的对话历史，不污染 BaseAgent session

### 三种使用模式

```python
# 1. 使用所有 actions（默认）- Micro Agent 拥有和 BaseAgent 相同的能力
await self._run_micro_agent(persona="...", task="...")

# 2. 限制部分 actions - 提高准确率，专注于特定任务
await self._run_micro_agent(
    persona="...",
    task="...",
    available_actions=["action1", "action2", "finish_task"]
)

# 3. 排除特定 actions - 减少干扰
await self._run_micro_agent(
    persona="...",
    task="...",
    exclude_actions=["send_email", "web_search"]
)
```

关键是要权衡：**什么时候用 Micro Agent，什么时候直接写 code**。
