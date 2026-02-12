NEED REVIEW


# Agent Developer Guide

This guide contains the **essential information** every agent and skill developer must know.

## 1. Core Architecture

AgentMatrix uses a **dual-layer architecture**:

```
BaseAgent (Session Layer)
  └─ Manages user sessions and conversation history
  └─ Delegates tasks to MicroAgent
  └─ Persists state to session

MicroAgent (Execution Layer)
  └─ Executes single tasks
  └─ Temporary execution context (disappears after execution)
  └─ Works via think-negotiate-act loop
```

**Key Insight**: `_run_micro_agent()` is like calling a **function**—it takes a task and returns a result. You can nest these calls recursively.

## 2. Creating an Agent

### 2.1 YAML Configuration File

Minimal example (`profiles/my_agent.yml`):

```yaml
name: MyAgent
description: A helpful assistant
module: agentmatrix.agents.base
class_name: BaseAgent

# Load skills
mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin

# Agent's persona
system_prompt: |
  You are a helpful assistant.

# Backend models
backend_model: gpt-4
cerebellum_model: gpt-3.5-turbo
```

**Required fields**:
- `name`: Unique agent identifier
- `description`: What this agent does
- `module`: Python module path to base class
- `class_name`: Base class name
- `system_prompt`: Agent's persona
- `backend_model`: LLM for reasoning
- `cerebellum_model`: SLM for parameter negotiation

**Optional fields**:
- `mixins`: List of skill mixin classes
- `max_steps`: Maximum execution steps (default: 10)
- `temperature`: LLM temperature (default: 0.7)

### 2.2 Running an Agent

```python
from agentmatrix import AgentMatrix

# Initialize
matrix = AgentMatrix(
    agent_profile_path="profiles",
    matrix_path="MyWorld"
)

# Send task
email = Email(
    sender="user@example.com",
    recipient="MyAgent",
    subject="Hello",
    body="Can you help me?",
    user_session_id="session_123"
)

await matrix.post_office.send_email(email)
```

## 3. Writing Skills

Skills are Python mixin classes with `@register_action` decorated methods.

### 3.1 Basic Skill Structure

```python
# my_skills.py
class MySkillMixin:
    """A skill module containing actions"""

    @register_action(
        description="Search the web for information",
        param_infos={
            "query": "Search query string",
            "num_results": "Number of results (default 10)"
        }
    )
    async def web_search(self, query: str, num_results: int = 10) -> str:
        """Search the web and return results"""
        results = await self._search_api(query, num_results)
        return f"Found {len(results)} results"
```

### 3.2 **Key: Design Principles for description and param_info**

This is the most important part of skill development.

#### description (For Micro Agent's LLM)

- **Purpose**: Tell the LLM what this action can do, what options are available
- **Don't write parameter names**: LLM doesn't know or need to know parameter names
- **Fully describe functionality**: Let the LLM decide when to call it and how to describe intent

**Example Comparison**:

❌ **Bad description**:
```python
description="Write to file"
# Problem: Too simple, LLM doesn't know there are two modes (overwrite/append)
```

❌ **Bad description**:
```python
description="Control whether to search by filename or in file content via the target parameter"
# Problem: Shouldn't mention "target parameter", LLM doesn't know what a parameter name is
```

✅ **Good description**:
```python
description="Write content to file. Supports overwrite or append mode. If overwriting an existing file, must explicitly state that overwriting is allowed"
# Strengths:
# 1. Tells LLM there are two modes (overwrite/append)
# 2. Clearly states behavior constraints (need explicit permission to overwrite existing files)
```

✅ **Good description**:
```python
description="Read file content. Can specify line range to read (default reads first 200 lines). Will display file statistics (size, total lines)"
# Strengths:
# 1. Tells LLM it can specify line range
# 2. Explains default behavior
# 3. Mentions additional features (statistics)
```

✅ **Good description**:
```python
description="Search for files or content. Can choose to search by filename (supports Glob patterns like *.txt) or search for keywords in file content (supports regex). Defaults to searching in file content. Can choose recursive or non-recursive search"
# Strengths:
# 1. Doesn't mention parameter names, just describes functionality
# 2. Gives concrete examples (*.txt)
# 3. Explains default behavior and options
```

#### param_info (For Cerebellum)

- **Purpose**: Help the Cerebellum understand each parameter's meaning, map LLM intent to parameters ("fill in the blanks")
- **Clearly explain**: Parameter meaning, possible values, default values

**Good param_info**:
```python
param_infos={
    "file_path": "File path",
    "content": "File content",
    "mode": "Write mode (optional, default 'overwrite'). Options: 'overwrite' to overwrite, 'append' to append",
    "allow_overwrite": "Whether to allow overwriting existing files (optional, default False). If file exists and mode is overwrite, must set to True to overwrite"
}
```

**Checklist**:
- [ ] Does description fully explain functionality without mentioning parameter names?
- [ ] Does description tell LLM what options are available?
- [ ] Does description explain default behavior and constraints?
- [ ] Does param_info clearly explain each parameter's meaning and possible values?

### 3.3 Calling MicroAgent

Skills can call `self._run_micro_agent()` to execute subtasks.

**Example: Recursive Task Decomposition**

```python
class ResearchSkillMixin:
    @register_action(
        description="Deep research on a topic. Can specify research depth, defaults to 2 levels",
        param_infos={
            "topic": "Research topic",
            "depth": "Research depth (default 2 levels)"
        }
    )
    async def deep_research(self, topic: str, depth: int = 2) -> dict:
        """Research through recursive MicroAgent calls"""

        if depth <= 0:
            # Base case: simple search
            return await self._run_micro_agent(
                persona="You are a researcher",
                task=f"Search for information about {topic}",
                available_actions=["web_search"]
            )

        # Recursive case: decompose into subtopics
        subtopics_result = await self._run_micro_agent(
            persona="You are a research planner",
            task=f"Break down '{topic}' into 3-5 subtopics",
            available_actions=["think_only"]
        )

        # Recursively research each subtopic
        results = {}
        for subtopic in subtopics_result["subtopics"]:
            results[subtopic] = await self.deep_research(subtopic, depth - 1)

        return {
            "topic": topic,
            "sub_research": results
        }
```

**`_run_micro_agent()` parameters**:

```python
await self._run_micro_agent(
    persona="You are...",                   # Required: Who is this MicroAgent?
    task="Do this task",                    # Required: What should it do?
    available_actions=["action1", ...],    # Optional: What actions can it use?
    max_steps=10,                          # Optional: Maximum execution steps
    max_time=5.0,                          # Optional: Maximum execution time (minutes)
    exclude_actions=["action2", ...]       # Optional: Exclude certain actions
)
```

**Key points**:
- Each call creates a **new isolated execution context**
- Nested calls don't pollute each other's history
- Recursive nesting is encouraged for complex tasks

## 4. Session Management

BaseAgent manages session state through sessions:

```python
# Get session context
context = self.get_session_context()

# Update session context (auto-persisted)
await self.update_session_context(
    key1="value1",
    key2="value2"
)

# Get transient context (not persisted)
value = self.get_transient("notebook")

# Set transient context
self.set_transient("notebook", notebook_obj)
```

**MicroAgent session support**:

MicroAgent's `execute()` method supports session parameters for persisting conversation history:

```python
# At the MicroAgent.execute() level
result = await micro_core.execute(
    persona="...",
    task="...",
    available_actions=[...],
    session=session_obj,           # Optional: session object
    session_manager=session_mgr    # Optional: session manager
)
```

This allows MicroAgent to restore conversation history across multiple executions.

## 5. Important Constraints

### 5.1 State Isolation

**✅ Should**: Store session-level state in BaseAgent
```python
class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        self.user_preferences = {}  # OK: session-level state
```

**❌ Should not**: Store execution state in BaseAgent
```python
# Avoid this
class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        self.current_step = 0  # Bad: execution state
```

**Why**: BaseAgent manages multiple sessions. Execution state belongs to MicroAgent (which is temporary).

### 5.2 MicroAgent Lifecycle

**MicroAgent disappears after execution**:
```python
# MicroAgent executes
result = await self._run_micro_agent(task="Do something")

# After this line, MicroAgent is gone
# Don't try to access its internal state
```

**✅ Should**: Capture results
```python
result = await self._run_micro_agent(task="...")
self.last_result = result  # OK: storing result, not MicroAgent
```

## 6. Quick Reference

### 6.1 YAML Configuration Fields

| Field | Required | Description |
|------|----------|-------------|
| `name` | Yes | Unique agent identifier |
| `description` | Yes | What this agent does |
| `module` | Yes | Python module path (e.g., `agentmatrix.agents.base`) |
| `class_name` | Yes | Base class name (e.g., `BaseAgent`) |
| `system_prompt` | Yes | Agent's persona and behavior |
| `backend_model` | Yes | LLM for reasoning (e.g., `gpt-4`) |
| `cerebellum_model` | Yes | SLM for parameter negotiation (e.g., `gpt-3.5-turbo`) |
| `mixins` | No | List of skill mixin classes |
| `max_steps` | No | Maximum MicroAgent steps (default: 10) |
| `temperature` | No | LLM temperature (default: 0.7) |

### 6.2 @register_action Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `description` | Yes | **For LLM**: Functional description, don't mention parameter names |
| `param_infos` | No | **For Cerebellum**: Dictionary mapping parameter names to descriptions |

### 6.3 _run_micro_agent() Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `persona` | Yes | MicroAgent's persona (natural language) |
| `task` | Yes | Task description (natural language) |
| `available_actions` | No | List of action names it can use (default: all actions) |
| `max_steps` | No | Maximum steps (default: from BaseAgent) |
| `max_time` | No | Maximum time (minutes) |
| `exclude_actions` | No | Actions to exclude (default excludes waiting actions) |

## 7. Common Patterns

### Pattern 1: Simple Action
```python
@register_action(description="Do a simple task")
async def simple_task(self, input: str) -> str:
    return f"Processed: {input}"
```

### Pattern 2: Action with MicroAgent Subtask
```python
@register_action(description="Do a complex task")
async def complex_task(self, input: str) -> dict:
    sub_result = await self._run_micro_agent(
        persona="You are an expert",
        task=f"Analyze: {input}"
    )
    return sub_result
```

### Pattern 3: Recursive Decomposition
```python
@register_action(description="Decompose and execute")
async def recursive_task(self, task: str, depth: int = 0) -> dict:
    if depth > 3:
        return await self._run_micro_agent(task=f"Execute: {task}")

    # Decompose
    subtasks = await self._run_micro_agent(
        task=f"Decompose: {task}"
    )

    # Recursively execute
    results = {}
    for subtask in subtasks["subtasks"]:
        results[subtask] = await self.recursive_task(subtask, depth + 1)

    return results
```

## 8. Troubleshooting

**Problem**: MicroAgent returns unexpected output
- **Solution**: Improve description to make it clearer

**Problem**: MicroAgent chooses wrong action
- **Solution**: Improve description to explain when to use which action

**Problem**: Cerebellum extracts parameters incorrectly
- **Solution**: Improve param_info to explain parameter meanings more clearly

**Problem**: Tasks take too long
- **Solution**: Reduce `max_steps` or break into smaller subtasks

---

For more details, see:
- [Agent and Micro Agent Design](agent-and-micro-agent-design.md)
- [Think-With-Retry Pattern](think-with-retry-pattern.md)
- [Matrix World Architecture](matrix-world.md)
