# Agent Developer Guide

This guide contains the **essential information** every agent and skill developer must know. Read this before writing your first agent.

## 1. Core Concepts

AgentMatrix uses a **dual-layer architecture**:

```
BaseAgent (Session Layer)
  └─ Manages conversations and user sessions
  └─ Owns skills and capabilities
  └─ Delegates tasks to MicroAgent

MicroAgent (Execution Layer)
  └─ Executes single tasks
  └─ Inherits BaseAgent's capabilities
  └─ Has isolated execution context
  └─ Terminates when done
```

**Execution Flow**:
```
User sends email
  → BaseAgent receives it
  → Delegates to MicroAgent
  → MicroAgent executes actions
  → Returns result to BaseAgent
  → BaseAgent replies to user
```

**Key Insight**: `MicroAgent.execute()` is like calling a **function**—it takes a task and returns a result. You can nest these calls recursively.

## 2. Creating an Agent

### 2.1 Create YAML Profile

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

### 2.2 Run Your Agent

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
    """Skill module with actions"""
    
    @register_action(
        description="Search the web for information",
        param_infos={
            "query": "Search query string",
            "num_results": "Number of results (default 10)"
        }
    )
    async def web_search(self, query: str, num_results: int = 10) -> str:
        """Search web and return results"""
        # Implementation
        results = await self._search_api(query, num_results)
        return f"Found {len(results)} results"
```

**Key points**:
- Skills are **mixin classes** (can be combined)
- Actions are **async methods** decorated with `@register_action`
- Return type is usually `str` (natural language) or `dict` (structured data)

### 3.2 The @register_action Decorator

```python
@register_action(
    description="Clear natural language description of what this action does",
    param_infos={
        "param1": "Description of parameter 1",
        "param2": "Description of parameter 2 (default value shown in description)"
    }
)
async def my_action(self, param1: str, param2: int = 10) -> str:
    pass
```

**Parameters**:
- `description`: What this action does (natural language). MicroAgent's LLM reads this to decide when to call it.
- `param_infos`: Optional dictionary describing each parameter. Helps Cerebellum negotiate values.

### 3.3 Calling MicroAgent from Skills (Critical!)

This is the **most important pattern**: Skills can call `self._run_micro_agent()` to execute subtasks.

**Example: Recursive Task Decomposition**

```python
class ResearchSkillMixin:
    @register_action(
        description="Research a topic in depth",
        param_infos={
            "topic": "Research topic",
            "depth": "How many levels deep to research (default 2)"
        }
    )
    async def deep_research(self, topic: str, depth: int = 2) -> dict:
        """Research by recursively calling MicroAgent"""
        
        if depth <= 0:
            # Base case: simple search
            return await self._run_micro_agent(
                persona="You are a researcher",
                task=f"Search for information about {topic}",
                available_actions=["web_search"],
                result_params={
                    "expected_schema": {
                        "summary": "Brief summary",
                        "key_points": ["Main points"]
                    }
                }
            )
        
        # Recursive case: decompose into subtopics
        subtopics_result = await self._run_micro_agent(
            persona="You are a research planner",
            task=f"Break down '{topic}' into 3-5 subtopics",
            available_actions=["think_only"],
            result_params={
                "expected_schema": {
                    "subtopics": ["List of subtopics"]
                }
            }
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

**`_run_micro_agent()` Parameters**:

```python
await self._run_micro_agent(
    persona="You are a ...",           # Required: Who is this MicroAgent?
    task="Do this task",                # Required: What should it do?
    available_actions=["action1", ...], # Optional: Which actions can it use?
    max_steps=10,                       # Optional: Max execution steps
    initial_history=[],                  # Optional: Previous conversation
    result_params={                      # Optional: Expected output format
        "expected_schema": {
            "field1": "description",
            "field2": ["list of items"]
        }
    }
)
```

**Key points**:
- Each `_run_micro_agent()` call creates a **new isolated execution context**
- Nested calls don't pollute each other's history
- Use `result_params["expected_schema"]` to request structured output
- Recursive nesting is encouraged for complex tasks

### 3.4 Return Formats

**Natural language (simplest)**:
```python
async def simple_action(self, query: str) -> str:
    return f"Processed: {query}"
```

**Structured data (recommended for composition)**:
```python
async def structured_action(self, query: str) -> dict:
    result = await self._run_micro_agent(
        task=f"Process {query}",
        result_params={
            "expected_schema": {
                "status": "success/failed",
                "data": "Result data",
                "metadata": {"key": "value"}
            }
        }
    )
    return result  # Returns dict matching schema
```

## 4. Important Constraints

### 4.1 State Isolation

**✅ DO**: Store session-level state in BaseAgent
```python
class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        self.user_preferences = {}  # OK: session-level state
```

**❌ DON'T**: Store execution state in BaseAgent
```python
# Avoid this
class MyAgent(BaseAgent):
    def __init__(self, profile):
        super().__init__(profile)
        self.current_step = 0  # BAD: execution state
```

**Why**: BaseAgent manages multiple sessions. Execution state belongs in MicroAgent (which is temporary).

### 4.2 MicroAgent Lifecycle

**MicroAgent disappears after execution**:
```python
# MicroAgent executes
result = await self._run_micro_agent(task="Do something")

# After this line, MicroAgent is gone
# Don't try to access its internal state
```

**✅ DO**: Capture the result
```python
result = await self._run_micro_agent(task="...")
self.last_result = result  # OK: store result, not MicroAgent
```

**❌ DON'T**: Try to reuse MicroAgent
```python
micro_agent = self._run_micro_agent(...)  # Returns result, not agent
# You can't call micro_agent again
```

### 4.3 Don't Mix Layers

**✅ DO**: Use BaseAgent for session, MicroAgent for execution
```python
# In BaseAgent method
async def process_email(self, email):
    session = self._get_session(email)  # Session: BaseAgent
    result = await self._run_micro_agent(...)  # Execution: MicroAgent
    session.add_result(result)  # Update session
```

**❌ DON'T**: Handle execution state in BaseAgent
```python
# Avoid this
async def process_email(self, email):
    self.step_count = 0  # BAD: execution in BaseAgent
    while self.step_count < 10:
        # ...
```

## 5. Quick Reference

### 5.1 YAML Profile Fields

| Field | Required | Description |
|-------|----------|-------------|
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

### 5.2 @register_action Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `description` | Yes | Natural language description of what the action does |
| `param_infos` | No | Dictionary mapping parameter names to descriptions |

### 5.3 _run_micro_agent() Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `persona` | Yes | MicroAgent's persona (natural language) |
| `task` | Yes | Task description (natural language) |
| `available_actions` | No | List of action names it can use (default: all actions) |
| `max_steps` | No | Maximum steps (default: from BaseAgent) |
| `initial_history` | No | Previous conversation to continue (default: empty) |
| `result_params` | No | Output format specification, including `expected_schema` |

## 6. Common Patterns

### Pattern 1: Simple Action
```python
@register_action(description="Do simple task")
async def simple_task(self, input: str) -> str:
    return f"Processed: {input}"
```

### Pattern 2: Action with MicroAgent Subtask
```python
@register_action(description="Do complex task")
async def complex_task(self, input: str) -> dict:
    # Use MicroAgent for subtask
    sub_result = await self._run_micro_agent(
        persona="You are a specialist",
        task=f"Analyze: {input}",
        result_params={"expected_schema": {"analysis": "string"}}
    )
    return sub_result
```

### Pattern 3: Recursive Decomposition
```python
@register_action(description="Break down and execute")
async def recursive_task(self, task: str, depth: int = 0) -> dict:
    if depth > 3:
        return await self._run_micro_agent(task=f"Do: {task}")
    
    # Decompose
    subtasks = await self._run_micro_agent(
        task=f"Break down: {task}",
        result_params={"expected_schema": {"subtasks": ["string"]}}
    )
    
    # Recursively execute
    results = {}
    for subtask in subtasks["subtasks"]:
        results[subtask] = await self.recursive_task(subtask, depth + 1)
    
    return results
```

## 7. Troubleshooting

**Problem**: MicroAgent returns unexpected output
- **Solution**: Use `result_params["expected_schema"]` to specify expected format

**Problem**: Task takes too long
- **Solution**: Reduce `max_steps` or decompose into smaller subtasks

**Problem**: Context is getting cluttered
- **Solution**: Use recursive MicroAgent calls—each has isolated context

**Problem**: Can't access MicroAgent state after execution
- **Solution**: Capture the result instead—MicroAgent is gone after execution

---

For more details, see:
- [Agent and Micro Agent Design](agent-and-micro-agent-design.md)
- [Think-With-Retry Pattern](think-with-retry-pattern.md)
- [Matrix World Architecture](matrix-world.md)
