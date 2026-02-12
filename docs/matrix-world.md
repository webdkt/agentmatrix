NEED REVIEW

# Matrix World Architecture

## Overview

AgentMatrix is a multi-agent orchestration framework that manages the lifecycle, communication, and coordination of AI agents. This document describes the overall architecture, directory structure, initialization process, and runtime execution flow.

## Project Directory Structure

```
agentmatrix/
├── src/agentmatrix/
│   ├── agents/                    # Agent implementations
│   │   ├── base.py               # BaseAgent class
│   │   ├── micro_agent.py        # MicroAgent class
│   │   └── post_office.py        # Message routing
│   ├── backends/                  # LLM client implementations
│   │   └── llm_client.py         # LLM API wrapper
│   ├── core/                      # Core infrastructure
│   │   ├── runtime.py            # AgentMatrix main class
│   │   ├── loader.py             # Agent loader
│   │   ├── cerebellum.py         # Parameter negotiator
│   │   ├── action.py             # Action decorator
│   │   ├── session.py            # Session management
│   │   └── message.py            # Email messaging
│   ├── skills/                    # Skill modules
│   │   ├── filesystem.py         # File operations
│   │   ├── web_searcher.py       # Web search
│   │   ├── deep_researcher.py    # Deep research
│   │   ├── crawler_helpers.py    # Web crawling
│   │   ├── notebook.py           # Notebook management
│   │   └── project_management.py # Project planning
│   ├── profiles/                  # Agent configurations
│   │   ├── prompts/              # Prompt templates
│   │   └── *.yml                 # Agent profile YAML files
│   └── db/                        # Database layer
│       └── vector_db.py          # Vector database (ChromaDB)
├── docs/                          # Documentation
│   ├── v0.1/                     # Archived documentation
│   ├── matrix-world.md           # This file
│   ├── agent-and-micro-agent-design.md
│   └── think-with-retry-pattern.md
└── MyWorld/                       # Example world setup
    ├── matrix_state.json         # Persisted world state
    └── agent_profiles/           # Custom agent profiles
```

## Core Components

### AgentMatrix Runtime

**Location**: `src/agentmatrix/core/runtime.py`

The `AgentMatrix` class is the main entry point that manages the entire agent world.

```python
class AgentMatrix:
    def __init__(self, agent_profile_path, matrix_path, ...):
        self.matrix_path = matrix_path
        self.agent_profile_path = agent_profile_path

        # World resources
        self.post_office = None      # Message routing
        self.vector_db = None        # Email/notebook search
        self.user_sessions = {}      # User session tracking

        # Agents
        self.agents = {}             # name -> agent instance

        # Initialization
        self._prepare_world_resource()
        self._prepare_agents()
        self.load_matrix()
```

**Key Responsibilities**:
- **World Resource Preparation**: Initialize PostOffice and VectorDB
- **Agent Loading**: Load all agents from YAML profiles
- **State Persistence**: Save and restore world state

### World Resource Preparation

**`_prepare_world_resource()`** (lines 79-89)

```python
def _prepare_world_resource(self):
    # Initialize PostOffice for message routing
    self.post_office = PostOffice()

    # Initialize VectorDB for semantic search
    self.vector_db = ChromaDB(
        persist_directory=os.path.join(self.matrix_path, "chroma_db")
    )

    # Register with agents
    for agent in self.agents.values():
        agent.post_office = self.post_office
        agent.vector_db = self.vector_db
```

**Resources Initialized**:
1. **PostOffice**: Async message queue for inter-agent communication
2. **VectorDB (ChromaDB)**: Semantic search for emails and notebooks
3. **User Sessions**: Track user conversations across agents

### Agent Loading

**Location**: `src/agentmatrix/core/loader.py`

The `AgentLoader` class discovers and instantiates agents from YAML profiles.

```python
class AgentLoader:
    def __init__(self, profile_path, default_backend, default_cerebellum):
        self.profile_path = profile_path
        self.default_backend = default_backend
        self.default_cerebellum = default_cerebellum

    def load_from_file(self, file_path) -> BaseAgent:
        # Parse YAML profile
        with open(file_path, 'r') as f:
            profile = yaml.safe_load(f)

        # Import base class
        module = importlib.import_module(profile["module"])
        base_class = getattr(module, profile["class_name"])

        # Load mixins
        mixin_classes = []
        for mixin_path in profile.get("mixins", []):
            mixin_class = self._import_mixin(mixin_path)
            mixin_classes.append(mixin_class)

        # Create dynamic class with mixins
        agent_class = type(
            f"Dynamic{profile['class_name']}",
            (base_class, *mixin_classes),
            {}
        )

        # Instantiate agent
        agent = agent_class(profile)

        return agent
```

**`load_all()`** (lines 179-187):

```python
def load_all(self) -> Dict[str, BaseAgent]:
    """Load all agents from profile directory"""
    agents = {}
    for filename in os.listdir(self.profile_path):
        if filename.endswith(".yml"):
            file_path = os.path.join(self.profile_path, filename)
            agent = self.load_from_file(file_path)
            agents[agent.name] = agent
    return agents
```

### Agent Profile Format

**Example**: `profiles/planner.yml`

```yaml
name: Planner
description: A planning agent that breaks down complex tasks
module: agentmatrix.agents.base
class_name: BaseAgent

# Skill mixins to load
mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.project_management.ProjectManagementMixin

# System prompt (persona)
system_prompt: |
  You are a senior project manager. You excel at breaking down complex tasks
  and generating clear, actionable plans.

# Backend configuration
backend_model: default_llm
cerebellum_model: default_slm

# Agent-specific settings
max_steps: 15
temperature: 0.7
```

**Profile Fields**:
- `name`: Unique agent identifier
- `description`: Agent purpose
- `module`: Python module path to base class
- `class_name`: Base class name
- `mixins`: List of skill mixin classes to compose
- `system_prompt`: Agent's persona and behavior
- `backend_model`: LLM model for reasoning
- `cerebellum_model`: SLM model for parameter negotiation

### PostOffice

**Location**: `src/agentmatrix/agents/post_office.py`

The `PostOffice` class provides asynchronous message routing and service discovery.

```python
class PostOffice:
    def __init__(self):
        # Service registry (agent directory)
        self.yellow_page = {}      # name -> agent instance

        # Message queues
        self.inboxes = {}           # name -> asyncio.Queue

        # Search and sessions
        self.vector_db = None       # For email search
        self.user_sessions = {}     # User session tracking

    def register_agent(self, agent: BaseAgent):
        """Register agent for communication"""
        self.yellow_page[agent.name] = agent
        self.inboxes[agent.name] = asyncio.Queue()

    async def send_email(self, email: Email):
        """Route email to recipient's inbox"""
        recipient_inbox = self.inboxes.get(email.recipient)
        if recipient_inbox:
            await recipient_inbox.put(email)

    async def get_email(self, agent_name: str, timeout: float = None):
        """Retrieve next email from agent's inbox"""
        inbox = self.inboxes.get(agent_name)
        return await asyncio.wait_for(inbox.get(), timeout)

    def find_agent(self, name: str) -> Optional[BaseAgent]:
        """Service discovery via yellow page"""
        return self.yellow_page.get(name)
```

**Key Features**:
- **Service Discovery**: Yellow page maps agent names to instances
- **Async Message Routing**: Non-blocking email delivery
- **Vector Search**: Find relevant emails by semantic similarity
- **User Session Management**: Track user conversations across agents

### State Persistence

**`save_matrix()`** (runtime.py lines 144-156):

```python
def save_matrix(self):
    """Persist world state to disk"""
    state = {
        "user_sessions": self.user_sessions,
        "agent_states": {}
    }

    # Save each agent's session state
    for name, agent in self.agents.items():
        state["agent_states"][name] = {
            "sessions": agent.sessions,
            "reply_mapping": agent.reply_mapping
        }

    # Write to file
    state_file = os.path.join(self.matrix_path, "matrix_state.json")
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
```

**`load_matrix()`** (runtime.py lines 158-171):

```python
def load_matrix(self):
    """Restore world state from disk"""
    state_file = os.path.join(self.matrix_path, "matrix_state.json")
    if not os.path.exists(state_file):
        return

    with open(state_file, 'r') as f:
        state = json.load(f)

    # Restore user sessions
    self.user_sessions = state.get("user_sessions", {})

    # Restore agent sessions
    for name, agent_state in state.get("agent_states", {}).items():
        if name in self.agents:
            agent = self.agents[name]
            agent.sessions = agent_state.get("sessions", {})
            agent.reply_mapping = agent_state.get("reply_mapping", {})
```

## Initialization Flow

### Startup Sequence

```
1. Create AgentMatrix instance
   │
2. Prepare World Resources
   ├─ Initialize PostOffice
   ├─ Initialize VectorDB (ChromaDB)
   └─ Create user session tracker
   │
3. Load Agents
   ├─ Scan profiles/ directory for *.yml files
   ├─ For each profile:
   │  ├─ Parse YAML
   │  ├─ Import base class (BaseAgent)
   │  ├─ Load skill mixins
   │  ├─ Create dynamic class (multiple inheritance)
   │  └─ Instantiate agent
   └─ Register agents with PostOffice
   │
4. Load World State
   ├─ Read matrix_state.json
   ├─ Restore user sessions
   └─ Restore agent sessions and reply mappings
   │
5. Start Agent Loops
   └─ Each agent starts listening for emails
```

### Code Example

```python
# Initialize AgentMatrix
matrix = AgentMatrix(
    agent_profile_path="src/agentmatrix/profiles",
    matrix_path="MyWorld",
    default_backend=llm_client,
    default_cerebellum=cerebellum_client
)

# All agents loaded and ready
print(f"Loaded {len(matrix.agents)} agents:")
for name, agent in matrix.agents.items():
    print(f"  - {name}: {agent.description}")

# Agents are now listening for emails
# Send task to Planner agent
email = Email(
    id=str(uuid.uuid4()),
    sender="user@example.com",
    recipient="Planner",
    subject="Plan a website",
    body="Create a plan for building a portfolio website",
    user_session_id="session_123"
)

await matrix.post_office.send_email(email)
```

## Runtime Execution

### Task Processing Lifecycle

```
1. User sends email to agent
   │
2. PostOffice routes email to agent's inbox
   │
3. Agent's process_email() method:
   ├─ Check in_reply_to for thread context
   ├─ Restore or create session via SessionManager
   ├─ Delegate to MicroAgent
   │  └─ Think-Negotiate-Act loop:
   │     ├─ Think: LLM generates reasoning
   │     ├─ Detect action from output
   │     ├─ Negotiate parameters (via Cerebellum)
   │     ├─ Execute action
   │     └─ Repeat until all_finished or max_steps
   ├─ MicroAgent returns result
   └─ Send reply email
   │
4. PostOffice delivers reply to user
   │
5. AgentMatrix saves state
```

### Concurrent Agent Execution

Each agent runs its own async loop, processing emails independently:

```python
# Each agent's message loop
async def message_loop(agent: BaseAgent):
    while True:
        # Get next email (blocking)
        email = await agent.post_office.get_email(agent.name)

        # Process email
        await agent.process_email(email)

# Start all agents concurrently
async def run_matrix(matrix: AgentMatrix):
    tasks = []
    for agent in matrix.agents.values():
        task = asyncio.create_task(message_loop(agent))
        tasks.append(task)

    # Run all agents
    await asyncio.gather(*tasks)
```

### Inter-Agent Collaboration

Agents can delegate tasks to each other via email:

```python
# Researcher agent's action
@register_action(description="Delegate planning to Planner agent")
async def delegate_planning(self, research_results: str) -> str:
    # Compose delegation email
    email = Email(
        id=str(uuid.uuid4()),
        sender=self.name,
        recipient="Planner",
        subject="Create plan from research",
        body=f"Based on research: {research_results}\nCreate a project plan.",
        user_session_id=self.current_session_id
    )

    # Send to Planner
    await self.post_office.send_email(email)

    # Wait for Planner's response
    reply = await self.post_office.get_email(self.name, timeout=600)
    return reply.body
```

## Component Summary

| Component | File | Responsibility |
|-----------|------|----------------|
| AgentMatrix | core/runtime.py | World management and orchestration |
| AgentLoader | core/loader.py | Agent initialization from YAML profiles |
| PostOffice | agents/post_office.py | Message routing and service discovery |
| VectorDB | db/vector_db.py | Semantic search for emails/notebooks |
| Session | core/session.py | Conversation state management |
| Email | core/message.py | Inter-agent communication data structure |

### Key Design Decisions

1. **YAML-Based Configuration**: Agent profiles declarative and easy to modify
2. **Dynamic Class Composition**: Mixins enable flexible skill composition
3. **Async-First Architecture**: Non-blocking message passing and execution
4. **State Persistence**: Conversations survive restarts
5. **Service Discovery**: Yellow page enables loose coupling between agents

## Development Guidelines

### Adding a New Agent

1. **Create Profile YAML**: Add to `profiles/` directory
2. **Define System Prompt**: Specify agent's persona and behavior
3. **Select Skills**: Add required mixins
4. **Configure Backend**: Choose LLM/SLM models
5. **Restart Matrix**: Agent auto-loaded on next startup

### Adding a New Skill

1. **Create Mixin Class**: In `src/agentmatrix/skills/`
2. **Register Actions**: Use `@register_action` decorator
3. **Implement Methods**: Add action logic
4. **Update Profiles**: Add to agent's `mixins` list
5. **Test**: Use MicroAgent for single-task execution

### Monitoring and Debugging

- **Check Agent Status**: `matrix.agents.keys()`
- **View User Sessions**: `matrix.user_sessions`
- **Inspect Agent Sessions**: `agent.sessions`
- **Search Email History**: `matrix.vector_db.search()`
- **Save State**: `matrix.save_matrix()`

## Example World Setup

```
MyWorld/
├── matrix_state.json        # Persisted state
├── chroma_db/               # Vector database
└── agent_profiles/          # Custom agent profiles
    ├── planner.yml
    ├── researcher.yml
    └── writer.yml
```

Initialize with:

```python
matrix = AgentMatrix(
    agent_profile_path="MyWorld/agent_profiles",
    matrix_path="MyWorld",
    default_backend=your_llm_client,
    default_cerebellum=your_slm_client
)

# Run matrix
await matrix.run()
```
