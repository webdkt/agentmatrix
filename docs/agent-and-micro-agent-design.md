# Agent and Micro Agent Design

## Overview

AgentMatrix implements a dual-layer agent system with **BaseAgent** and **MicroAgent**. The MicroAgent is designed as a "temporary personality" of a BaseAgent - reusing the same capabilities but operating with an independent task context and focused execution loop.

## Design Philosophy

- **Dual-Brain Architecture**: Separate reasoning (LLM) from parameter negotiation (SLM)
- **Micro Agent as Temporary Personality**: Same capabilities, different context, independent lifecycle
- **Email-Based Communication**: All inter-agent coordination uses natural language messages
- **Dynamic Skill Composition**: Skills are mixins dynamically loaded at runtime

## BaseAgent

**Location**: `src/agentmatrix/agents/base.py`

### Core Components

```python
class BaseAgent(FileSkillMixin, AutoLoggerMixin):
    def __init__(self, profile):
        # Identity
        self.name = profile["name"]
        self.description = profile["description"]
        self.system_prompt = profile["system_prompt"]

        # Dual-Brain Architecture
        self.brain = None      # LLM client for high-level reasoning
        self.cerebellum = None # SLM for parameter negotiation

        # Action Registry
        self.actions_map = {}   # name -> method reference
        self.actions_meta = {}  # name -> metadata (description, params)

        # Session Management
        self.sessions = {}      # TaskSession per conversation
        self.reply_mapping = {} # Email threading (in_reply_to -> session)

        # Micro Agent Core (lazy initialized)
        self._micro_core = None
```

### Action Registration

Actions are methods decorated with `@register_action`:

```python
@register_action(
    description="Search web for information",
    param_infos={
        "query": "Search query string",
        "num_results": "Number of results to return"
    }
)
async def web_search(self, query: str, num_results: int = 10):
    # Implementation
    pass
```

The decorator marks the method as an action and stores metadata. During initialization, `_scan_methods()` (lines 89-105) discovers all decorated methods and builds the action registry.

### Email Processing Workflow

**Main Entry Point**: `process_email()` (lines 244-286)

1. **Receive Email**: Incoming email from PostOffice
2. **Threading**: Check `in_reply_to` to restore conversation context
3. **Micro Agent Execution**: Delegate task to MicroAgent
4. **Response**: Send reply email with results

```python
async def process_email(self, email: Email):
    # Restore or create session
    session = self._get_or_create_session(email)

    # Execute with Micro Agent
    result = await self._run_micro_agent(
        persona=self.system_prompt,
        task=email.body,
        available_actions=self.actions_map.keys(),
        session_history=session.history
    )

    # Update session and send reply
    session.add_message(email.body, result)
    await self._send_reply(email, result)
```

### Convenience Method

**`_run_micro_agent()`** (lines 597-683): Lazy-initializes MicroAgent and executes task.

```python
async def _run_micro_agent(self, persona, task, available_actions,
                           initial_history=None, result_params=None):
    if self._micro_core is None:
        self._micro_core = MicroAgent(
            brain=self.brain,
            cerebellum=self.cerebellum,
            action_registry=self.actions_map,
            name=self.name,
            default_max_steps=10
        )

    return await self._micro_core.execute(
        persona=persona,
        task=task,
        available_actions=available_actions,
        initial_history=initial_history,
        result_params=result_params
    )
```

## MicroAgent

**Location**: `src/agentmatrix/agents/micro_agent.py`

### Design Concept

MicroAgent is NOT a separate agent class - it's a temporary execution mode:

- Reuses BaseAgent's brain, cerebellum, and action registry
- Has independent execution context (task, history, step count)
- Terminates upon task completion or reaching max_steps
- No persistent state - results flow back to BaseAgent

### Execute Mechanism

**Main Method**: `execute()` (lines 68-152)

```python
async def execute(self, persona, task, available_actions,
                 max_steps=None, initial_history=None, result_params=None):
    # Initialize context
    self.persona = persona
    self.task = task
    self.available_actions = available_actions
    self.max_steps = max_steps or self.default_max_steps
    self.history = initial_history or []
    self.result_params = result_params

    # Run think-negotiate-act loop
    await self._run_loop()

    return self.result
```

### Think-Negotiate-Act Loop

**`_run_loop()`** (lines 208-256)

```python
async def _run_loop(self):
    for self.step_count in range(1, self.max_steps + 1):
        # 1. Think - Call brain for reasoning
        thought = await self._think()

        # 2. Detect action from thought output
        action_name = self._detect_action(thought)

        # 3. Execute or finish
        if action_name == "finish_task":
            result = await self._execute_action(action_name, thought)
            self.result = result
            break  # Return to BaseAgent
        elif action_name:
            result = await self._execute_action(action_name, thought)
            # Add feedback and continue loop
        else:
            # No action detected - retry or ask for clarification
            pass
```

### Action Detection

**`_detect_action()`** (lines 262-285)

Simple substring matching in LLM output:

```python
def _detect_action(self, thought: str) -> Optional[str]:
    """Find action name in thought output using substring matching"""
    for action in sorted(self.available_actions, key=len, reverse=True):
        if action in thought:
            return action
    return None
```

- Actions sorted by length (longest first) to avoid partial matches
- Returns `None` if no action detected
- Returns `"finish_task"` to terminate execution

### Action Execution with Parameter Negotiation

**`_execute_action()`** (lines 288-378)

1. **Parse Action Intent**: Extract which action to take
2. **Parameter Negotiation** (via Cerebellum):
   - Get action parameter schema
   - Loop until parameters are clear or max turns reached
   - Use SLM (Cerebellum) for JSON generation
   - Ask brain (LLM) for clarification if needed
3. **Execute Action**: Call actual method with negotiated parameters
4. **Return Result**: Feedback for next iteration

## Skills System

### Definition

Skills are natural language interface functions with built-in intelligence, dynamically mountable to agents.

**Key Characteristics**:
- Decorated with `@register_action`
- Contain natural language descriptions
- Auto-discovered during agent initialization
- Reusable across agents via mixins

### Skill Example

**Location**: `src/agentmatrix/skills/web_searcher.py`

```python
class WebSearcherMixin:
    @register_action(
        description="Search the web for information using search engine",
        param_infos={
            "query": "Search query",
            "num_results": "Number of results to return (default 10)"
        }
    )
    async def web_search(self, query: str, num_results: int = 10) -> str:
        # Implementation using search API
        results = await self._search_api(query, num_results)
        return self._format_results(results)
```

### Dynamic Loading via Mixins

**Location**: `src/agentmatrix/core/loader.py` (lines 66-188)

Agent profile (YAML) specifies mixins:

```yaml
# profiles/planner.yml
name: Planner
description: A planning agent
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.project_management.ProjectManagementMixin
```

**Dynamic Class Creation**:

```python
# Load mixin classes
mixin_classes = []
for mixin_path in profile["mixins"]:
    mixin_class = import_module(mixin_path)
    mixin_classes.append(mixin_class)

# Create agent class with multiple inheritance
agent_class = type(
    f"Dynamic{class_name}",
    (base_agent_class, *mixin_classes),  # Multiple inheritance
    {}  # Class attributes
)

# Instantiate agent
agent = agent_class(profile)
```

This allows flexible composition of capabilities without modifying base classes.

### Skill Composition

Benefits:
- **Modularity**: Each skill is self-contained
- **Reusability**: Same skill used by multiple agents
- **Extensibility**: New skills added without changing core
- **Separation of Concerns**: Skills independent of agent logic

## Communication Mechanisms

### Email-Based Messaging

**Location**: `src/agentmatrix/core/message.py`

All inter-agent communication uses `Email` dataclass:

```python
@dataclass
class Email:
    id: str                  # Unique email ID
    sender: str              # Sender agent name
    recipient: str           # Recipient agent name
    subject: str             # Email subject
    body: str                # Email body (natural language)
    in_reply_to: str         # Thread ID for conversation context
    user_session_id: str     # User session tracking
```

**Key Features**:
- **Threading**: `in_reply_to` links related messages
- **Natural Language**: Body contains free-form text
- **User Sessions**: Tracks user conversations across agents

### PostOffice

**Location**: `src/agentmatrix/agents/post_office.py`

PostOffice provides async message routing and service discovery:

```python
class PostOffice:
    def __init__(self):
        self.yellow_page = {}      # Service registry (name -> agent)
        self.inboxes = {}           # Agent inboxes (name -> queue)
        self.vector_db = None       # For email search
        self.user_sessions = {}     # User session tracking

    async def send_email(self, email: Email):
        """Route email to recipient's inbox"""
        recipient_inbox = self.inboxes.get(email.recipient)
        if recipient_inbox:
            await recipient_inbox.put(email)

    async def get_email(self, agent_name: str, timeout: float = None):
        """Retrieve next email from agent's inbox"""
        inbox = self.inboxes.get(agent_name)
        return await inbox.get()

    def register_agent(self, agent: BaseAgent):
        """Register agent for communication"""
        self.yellow_page[agent.name] = agent
        self.inboxes[agent.name] = asyncio.Queue()
```

**Key Features**:
- **Service Discovery**: Yellow page maps agent names to instances
- **Async Routing**: Non-blocking message delivery
- **Vector Search**: Find relevant emails by content
- **Session Management**: Track user conversations

### Inter-Agent Collaboration Pattern

Example: Planner agent delegating to Researcher agent

```python
# Planner's action
@register_action(description="Delegate research task to Researcher agent")
async def delegate_research(self, task_description: str) -> str:
    # Compose email
    email = Email(
        id=str(uuid.uuid4()),
        sender=self.name,
        recipient="Researcher",
        subject=f"Research task: {task_description}",
        body=task_description,
        user_session_id=self.current_session_id
    )

    # Send via PostOffice
    await self.post_office.send_email(email)

    # Wait for reply
    reply_email = await self.post_office.get_email(
        self.name,
        timeout=300  # 5 minutes
    )

    return reply_email.body
```

This natural language coordination enables flexible, explainable collaboration.

## Summary

| Component | Location | Responsibility |
|-----------|----------|----------------|
| BaseAgent | agents/base.py | Main agent with email processing and action registry |
| MicroAgent | agents/micro_agent.py | Temporary task executor with think-act loop |
| @register_action | core/action.py | Decorator marking methods as actions |
| AgentLoader | core/loader.py | Dynamic class composition with mixins |
| PostOffice | agents/post_office.py | Message routing and service discovery |
| Email | core/message.py | Inter-agent communication data structure |

### Key Design Decisions

1. **Dual-Brain Architecture**: Separate reasoning (LLM) from parameter parsing (SLM)
2. **Micro Agent as Temporary Personality**: Reuse components with independent context
3. **Email-Based Communication**: Natural language coordination between agents
4. **Mixin-Based Skills**: Flexible composition of capabilities
5. **Action Detection via Substring Matching**: Simple but effective for LLM output

### Development Guidelines

When adding new features:

1. **Define Actions**: Use `@register_action` with clear descriptions
2. **Create Skills**: Implement as mixin classes with `*SkillMixin` naming
3. **Register in Profile**: Add to YAML `mixins` list
4. **Test with MicroAgent**: Use `_run_micro_agent()` for single-task execution
5. **Communicate via Email**: Use PostOffice for inter-agent coordination
