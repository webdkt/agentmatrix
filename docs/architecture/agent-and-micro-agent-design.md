# Agent and MicroAgent Design

**Document Version**: v0.2.0 | **Last Updated**: 2026-02-27 | **Status**: ✅ Implemented

## Overview

### Core Concepts

AgentMatrix adopts a dual-layer architecture to separate session management from task execution:

- **Agent (Session Layer)**: Long-running, manages multiple sessions, provides capabilities
- **MicroAgent (Execution Layer)**: Temporary execution of individual tasks, independent context

### Why Separate

A single conversation can contain multiple tasks, and each task may be executed in multiple steps. If mixed together:
- **State confusion**: Conversation history, task state, and execution steps are all piled together
- **Hard to maintain**: Modifying one part might break another
- **Cannot nest**: Unable to support recursive task decomposition

### Architecture Value

| Value | Description |
|-------|-------------|
| **Clear Responsibilities** | Agent manages sessions, MicroAgent manages execution |
| **State Isolation** | Conversation history is not polluted by execution steps |
| **Recursive Nesting** | MicroAgent can create child MicroAgents, supporting task decomposition layer by layer |
| **Failure Isolation** | Task failures do not affect the session |

## Core Entities

### Agent (Session Manager)

**Code Location**: `src/agentmatrix/agents/base.py`

**Core Responsibilities**:
- Manage multiple independent sessions
- Own skill packages and action registry
- Create MicroAgents to execute specific tasks
- Maintain persistent conversation memory

**Initialization Code**:

```python
class BaseAgent(AutoLoggerMixin):
    def __init__(self, profile):
        # Basic information
        self.name = profile["name"]
        self.description = profile["description"]

        # Persona system (supports multiple personas)
        self.persona_config = profile.get("persona", {"base": ""})

        # Other prompts (such as task_prompt)
        self.other_prompts = profile.get("prompts", {})

        # Dual-brain architecture
        self.brain = None           # LLM - Advanced reasoning
        self.cerebellum = None      # SLM - Parameter negotiation
        self.vision_brain = None    # Visual model ✨

        # Capability registry
        self.action_registry = {}   # name -> bound_method
        self.actions_meta = {}      # name -> metadata

        # Session management
        self.session_manager = None

        # Event callbacks ✨
        self.async_event_callback = None

        # Scan all actions
        self._scan_all_actions()
```

**Persona System** ✨:

Supports multiple switchable personas, each is an independent prompt template:

```python
# Configuration file
persona:
  base: "You are a helpful assistant"
  planner: "You are a project planning expert, good at task decomposition"
  researcher: "You are an information collection expert"

# Use in code
persona = self.get_persona(
    persona_name="researcher",
    task_type="web_search"
)
```

**Skill Prompt System** ✨:

Each skill can have independent prompt templates, stored in `prompts/skills/{skill_name}/{prompt_name}.txt`:

```python
# Get skill prompt
prompt = self.get_skill_prompt(
    skill_name="browser_use",
    prompt_name="task_optimization",
    task_description="Search papers"
)
```

### MicroAgent (Executor)

**Code Location**: `src/agentmatrix/agents/micro_agent.py`

**Core Responsibilities**:
- Execute a single task (think-act loop)
- Use Agent's capabilities
- Have independent working context
- Destroyed when task is complete

**Creation Methods**:

```python
from agentmatrix.agents.micro_agent import MicroAgent

# Method 1: Share all capabilities from parent
micro_agent = MicroAgent(
    parent=self,  # Agent or another MicroAgent
    working_context=None,  # None means using parent's
    default_max_steps=50
)

# Method 2: Dynamically select available skills ✨
micro_agent = MicroAgent(
    parent=self,
    working_context=None,
    available_skills=["file", "browser"],  # Only use these two skills
    default_max_steps=50
)
```

**Dynamic Skill Composition** ✨:

Through the `available_skills` parameter, MicroAgent can load only the skills it needs:

```python
# Only load file and browser skills
micro = MicroAgent(
    parent=self,
    available_skills=["file", "browser"]
)

# This dynamically composes FileSkillMixin and BrowserSkillMixin
# Other skills will not be loaded
```

**Execute Task**:

```python
result = await micro_agent.execute(
    persona="You are a web search expert",  # Persona: identity for this execution
    task="Search for latest AI safety papers",  # Task: what to do
    available_actions=["search", "open_page"],  # Available actions: which actions to allow
    max_steps=20,  # Maximum steps
    result_params={
        "expected_schema": {  # Expected structured output
            "papers": ["string"],
            "summary": "string"
        }
    }
)
```

### State Management

#### Conversation Memory (Session Context)

**Core Mechanism**:

1. **Shared Memory** (default): Share the same memory through the hierarchical chain
2. **Automatic Save**: Automatically persist to disk on every update
3. **Independent Mode** (optional): Create independent temporary memory

**Code Example**:

```python
# Default: Share parent's memory (persistent)
micro1 = MicroAgent(parent=self)  # Shared
micro2 = MicroAgent(parent=self)  # Shared
# micro1 and micro2 share the same memory

# Independent mode: Create independent memory (not persistent)
micro3 = MicroAgent(
    parent=self,
    independent_session_context=True  # Independent memory
)
# micro3 has independent memory, won't persist
```

**Use Cases**:
- **Shared Mode** (default): Most scenarios, need memory persistence
- **Independent Mode**: Temporary calculations, intermediate steps, memory not needed to be saved

#### Working Space (Working Context)

**Hierarchical Directory Structure**:

```
workspace_root/
├── {task_id}/
│   └── agents/
│       └── {agent_name}/  # Agent's private working directory
│           ├── 20250226_143022/  # MicroAgent subtask directory (with timestamp)
│           │   └── files/
│           └── 20250226_143545/  # Another subtask directory
│               └── files/
```

**Create Subdirectory**:

```python
# With timestamp (default): Create new directory for each execution
micro = MicroAgent(parent=self)
# Working directory: workspace/.../agent_name/20250226_143022/

# Without timestamp: Share same directory across multiple executions
micro = MicroAgent(
    parent=self,
    working_context=WorkingContext(
        base_dir=str(self.private_workspace),
        current_dir=str(subtask_dir)  # Directory without timestamp
    )
)
```

## Skills and Actions

### Action (Capability)

Action is a specific operation that an Agent can perform, marked with `@register_action` decorator:

```python
from agentmatrix.core.action import register_action

@register_action(
    description="Search web information",
    param_infos={
        "query": "Search query string",
        "num_results": "Number of results to return (default 10)"
    }
)
async def web_search(self, query: str, num_results: int = 10) -> str:
    """Search web and return results"""
    results = await self._search_api(query, num_results)
    return self._format_results(results)
```

### Skill (Skill Package)

Skill is a collection of related Actions, implemented as Mixin classes:

```python
# src/agentmatrix/skills/web_searcher.py
class WebSearcherMixin:
    """Web search skill package"""

    @register_action(description="Search web")
    async def web_search(self, query: str) -> str:
        # Implementation
        pass

    @register_action(description="Open webpage")
    async def open_page(self, url: str) -> str:
        # Implementation
        pass

    @register_action(description="Extract content")
    async def extract_content(self, html: str) -> str:
        # Implementation
        pass
```

### Configuration Method

Specify required skills in Agent's YAML configuration:

```yaml
# profiles/researcher.yml
name: Researcher
description: Information collection expert

# Persona configuration ✨
persona:
  base: "You are a research assistant"
  planner: "You are a planning expert"
  researcher: "You are an information collection expert"

# Loaded skills
skills:
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.crawler_helpers.CrawlerHelpersMixin

# Backend configuration
backend_model: gpt-4
cerebellum_model: gpt-3.5-turbo
```

### Dynamic Loading

Dynamically compose Agent class through multiple inheritance at runtime:

```python
# Load mixin classes
mixin_classes = []
for mixin_path in profile["skills"]:
    mixin_class = import_module(mixin_path)
    mixin_classes.append(mixin_class)

# Create dynamic class
agent_class = type(
    f"Dynamic{class_name}",
    (BaseAgent, *mixin_classes),  # Multiple inheritance
    {}
)

# Instantiate
agent = agent_class(profile)
```

## Execution Mechanism

### "Soul Injection" Three Elements

Each time MicroAgent is executed, three elements are dynamically injected:

```python
result = await micro_agent.execute(
    persona="...",      # 1. Persona: identity for this execution
    task="...",         # 2. Task: what specifically to do
    available_actions=[...]  # 3. Available capabilities: which actions to allow this time
)
```

**Persona**:
- Determines the executor's thinking style and behavior
- Can select different personas from `persona_config`
- Supports template variables

**Task**:
- Initial User Message
- Specific goal to achieve
- Can include structured requirements

**Available Actions**:
- Can be all actions, or a subset
- Limiting capabilities makes the executor more focused

### Execution Flow

```
1. Create MicroAgent (parent = Agent)
   └─ Obtain: all actions, brain, cerebellum, memory

2. Inject "soul" (execute() parameters):
   ├─ persona: "You are a web search expert"
   ├─ task: "Search AI safety papers"
   └─ available_actions: ["search", "open_page"]

3. Think-act loop:
   Loop (up to max_steps times):
   ├─ Think: Call brain to think about next step
   ├─ Detect: Recognize action from thought output
   ├─ Negotiate: Negotiate parameters through cerebellum
   ├─ Execute: Execute action
   ├─ Feedback: Get execution result
   └─ Repeat: until all_finished or timeout

4. Return result and destroy
```

### Parameter Negotiation

MicroAgent performs parameter negotiation through Cerebellum (cerebellar model):

```python
# 1. Recognize action from brain's thought output
action_name = "search"

# 2. Get action's parameter definition
param_schema = self.actions_meta[action_name]["params"]

# 3. Negotiate parameters through cerebellum
params = await self.cerebellum.negotiate_params(
    thought=brain_output,  # Brain's original thought
    action_schema=param_schema,  # Action's parameter definition
    context=...  # Context information
)

# 4. Execute action
result = await self.actions_map[action_name](**params)
```

## Recursive Nesting

### "Natural Language Function" Concept

Treat `micro_agent.execute()` as a natural language function:
- **Input**: Natural language task description
- **Processing**: AI reasoning + multi-step think-act loop
- **Output**: Natural language result or structured data

### Nesting Example

```
User: "Research AI safety"

Agent
  └─ MicroAgent Layer 1 (Planner)
      task: "Create research plan"
      available actions: all

      ├─ Create child MicroAgent Layer 2 (Search Expert)
      │   task: "Search related papers"
      │   available actions: ["search", "open_page"]
      │
      │   └─ Create child MicroAgent Layer 3 (Analyst)
      │       task: "Analyze search results"
      │       available actions: ["summarize", "extract_info"]
      │       expected_schema: {...}
      │
      │       └─ Return structured data
      │
      └─ Integrate results, generate report
```

**Code Example**:

```python
async def research_ai_safety(topic: str) -> Dict:
    """Recursive research function"""

    # Layer 1: Create plan
    plan = await micro_agent.execute(
        persona="You are a research planner",
        task=f"Create research plan for '{topic}'",
        available_actions=["plan"]
    )

    # Layer 2: Search information
    papers = await micro_agent.execute(
        persona="You are a search expert",
        task=plan["search_task"],
        available_actions=["search", "open_page"]
    )

    # Layer 3: Analyze content
    analysis = await micro_agent.execute(
        persona="You are a content analyst",
        task=f"Analyze the following papers: {papers}",
        available_actions=["summarize", "extract_info"],
        result_params={
            "expected_schema": {
                "key_findings": ["string"],
                "summary": "string"
            }
        }
    )

    return analysis
```

### State Isolation

Each layer of MicroAgent has independent execution context:
- Layer 3's thought process doesn't pollute Layer 2
- Layer 2's intermediate steps don't affect Layer 1
- Each layer only sees the final result of the layer below

## Communication and Collaboration

### Email-Based Communication

**Code Location**: `src/agentmatrix/core/message.py`

All Agent-to-Agent communication uses Email data structure:

```python
@dataclass
class Email:
    id: str                  # Unique ID
    sender: str              # Sender Agent name
    recipient: str           # Recipient Agent name
    subject: str             # Email subject
    body: str                # Body (natural language)
    in_reply_to: str         # Reply relationship (maintains conversation thread)
    task_id: str             # Task ID (global task identifier)
```

**Features**:
- **Threading**: `in_reply_to` maintains conversation threads
- **Natural Language**: body contains free text
- **Task Tracking**: `task_id` tracks global tasks


### Two Types of Session IDs

**task_id (Task ID)**
- Global task identifier for file space division
- Can be initiated by any Agent (User, Daemon, regular Agent)
- One task = one "collaborative thing"
- File path: `{workspace_root}/{task_id}/`

**session_id (Session ID)**
- Conversation history ID from each Agent's perspective
- A task can have multiple sessions (one per Agent)
- File path: `.matrix/{agent_name}/{task_id}/history/{session_id}/`
### PostOffice System

**Code Location**: `src/agentmatrix/agents/post_office.py`

```python
class PostOffice:
    def __init__(self):
        self.yellow_page = {}      # Service registry (name -> agent)
        self.inboxes = {}           # Agent inboxes (name -> queue)
        self.vector_db = None       # Email search
        self.user_sessions = {}     # User session tracking

    async def send_email(self, email: Email):
        """Route email to recipient's inbox"""
        inbox = self.inboxes.get(email.recipient)
        if inbox:
            await inbox.put(email)

    def register_agent(self, agent: BaseAgent):
        """Register Agent to service registry"""
        self.yellow_page[agent.name] = agent
        self.inboxes[agent.name] = asyncio.Queue()
```

### Natural Language Coordination Example

```python
# Planner Agent's action
@register_action(description="Delegate research task")
async def delegate_research(self, task_description: str) -> str:
    # Send email
    email = Email(
        id=str(uuid.uuid4()),
        sender=self.name,
        recipient="Researcher",
        subject=f"Research task: {task_description}",
        body=task_description,
        task_id=self.current_task_id
    )

    # Send through PostOffice
    await self.post_office.send_email(email)

    # Wait for reply
    reply = await self.post_office.get_email(
        self.name,
        timeout=300
    )

    return reply.body
```

### Event Callback Mechanism ✨

**Code Location**: `base.py:59`

```python
self.async_event_callback: Optional[Callable] = None
```

Agents can notify external systems through event callbacks:

```python
# Inject callback in server.py
agent.async_event_callback = self._on_agent_event

async def _on_agent_event(self, event: AgentEvent):
    """Handle Agent event"""
    # Send to frontend
    await websocket.send_json(event.to_dict())
```

**Supported Event Types**:
- Task start/completion
- Action execution
- Error occurrence
- State updates

## Best Practices

### Configuration Recommendations

**1. Persona Design**

```yaml
# Good persona design
persona:
  base: |
    You are a helpful assistant.
    Your goal is: {{ goal }}

  planner: |
    You are a project planning expert.
    Please break down tasks into 3-5 subtasks.
    Each subtask should: {{ criteria }}

  researcher: |
    You are an information collection expert.
    When searching, focus on: {{ focus_areas }}
```

**2. Skill Selection**

```yaml
# Select appropriate skills based on tasks
skills:
  # File processing tasks
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.notebook.NotebookMixin

  # Web research tasks
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.crawler_helpers.CrawlerHelpersMixin

  # Browser automation
  - agentmatrix.skills.browser_use.BrowserUseMixin
```

### Code Patterns

**1. Creating MicroAgent**

```python
# Recommended: Use parent parameter
micro = MicroAgent(
    parent=self,
    default_max_steps=50
)

# Optional: Limit available skills
micro = MicroAgent(
    parent=self,
    available_skills=["file", "browser"]
)
```

**2. Executing Tasks**

```python
# Simple task
result = await micro.execute(
    persona="You are a search expert",
    task="Search AI papers",
    available_actions=["search"]
)

# Complex task (expect structured output)
result = await micro.execute(
    persona="You are an analyst",
    task="Analyze the following content",
    available_actions=["analyze", "summarize"],
    result_params={
        "expected_schema": {
            "summary": "string",
            "key_points": ["string"]
        }
    }
)
```

**3. Recursive Task Decomposition**

```python
async def process_complex_task(task: str, depth: int = 0):
    """Recursively process complex tasks"""
    if depth > 3:
        return await execute_simple(task)

    # Break down task
    subtasks = await micro.execute(
        persona="You are a task planner",
        task=f"Break down '{task}' into subtasks",
        result_params={"expected_schema": {"subtasks": ["string"]}}
    )

    # Recursively process
    results = []
    for subtask in subtasks["subtasks"]:
        result = await process_complex_task(subtask, depth + 1)
        results.append(result)

    return results
```

### Debugging Tips

**1. View Execution Logs**

```python
# MicroAgent logs every thought step
# Set log level to DEBUG to see detailed information
import logging
logging.getLogger("agentmatrix").setLevel(logging.DEBUG)
```

**2. Check Action Registration**

```python
# View registered actions
print(agent.actions_meta.keys())

# View specific action's metadata
print(agent.actions_meta["web_search"])
```

**3. Test Individual Action**

```python
# Directly call action to test
result = await agent.web_search(
    query="AI safety",
    num_results=5
)
```

## Summary

### Core Components

| Component | Location | Responsibility |
|-----------|----------|---------------|
| BaseAgent | agents/base.py | Session management, capability registry |
| MicroAgent | agents/micro_agent.py | Task execution, think-act loop |
| @register_action | core/action.py | Mark action |
| PostOffice | agents/post_office.py | Message routing |
| Email | core/message.py | Communication data structure |

### Design Principles

1. **Session and Execution Separation**: Long-term sessions vs short-term tasks
2. **Capability Inheritance, State Independence**: Reuse capabilities, isolate state
3. **Natural Language Coordination**: Email-style communication, easy to understand
4. **Dual-Brain Architecture**: LLM reasoning + SLM negotiation
5. **Dynamic Composition**: Flexibly configure capabilities through mixins

### API Quick Reference

```python
# Create MicroAgent
micro = MicroAgent(parent=self)

# Execute task
result = await micro.execute(
    persona="Persona",
    task="Task",
    available_actions=["action1", "action2"],
    max_steps=50,
    result_params={"expected_schema": {...}}
)

# Send email
await self.post_office.send_email(
    Email(sender="A", recipient="B", body="...")
)

# Get persona
persona = self.get_persona("planner", task_type="X")

# Get skill prompt
prompt = self.get_skill_prompt("browser_use", "task_optimization")
```
