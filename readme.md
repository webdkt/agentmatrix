# AgentMatrix

An intelligent multi-agent framework that lets LLMs focus on **reasoning**, not format compliance. Making agent development more natural.

**What we enable**:
- **Natural Language Functions**: It is no longer just a simple LLM API call, but a natural language function. You input a natural language intent and get the execution result without worrying about specific formats. There is no more need to expend effort defining JSON structures; you only need to focus on the intent itself.

- Natural **Sub-Agent Context Management**: Agents can recursively and nestably call skills (essentially sub-agents, referred to as "micro-agents" in this project), enabling them to handle more complex tasks. The execution contexts of these micro-agents are naturally and automatically isolated, eliminating concerns about context pollution. This supports long-cycle tasks without the need for complex manual context management.

[**English**](readme.md) | [**中文文档**](readme_zh.md)

## 🎯 What is AgentMatrix?

AgentMatrix is a multi-agent framework where:

- **Agents** act as digital employees with specific skills
- Agents collaborate through **natural language** (like email), not rigid APIs
- LLMs can reason naturally without wasting "mental energy" on JSON syntax

## 📦 Project Organization

AgentMatrix repository consists of three main parts:

### 1. Core Framework (`src/agentmatrix/`)
The heart of AgentMatrix - a Python library for building intelligent agents.
- **Install**: `pip install matrix-for-agents`
- **Use as**: Library in your own projects
- **Contains**: Agent runtime, skill system, LLM integration, message routing

### 2. Web Application (`web/` + `server.py`)
Official web-based management interface for AgentMatrix.
- **Start**: `python server.py`
- **Provides**: Visual UI for agent interaction, email-style messaging, session management
- **Tech**: FastAPI backend + modern frontend (Alpine.js + Tailwind CSS)
- **Documentation**: See [web/README.md](web/README.md)

### 3. Examples (`examples/`)
Sample configurations and tutorials to help you get started.
- **MyWorld**: Complete example world with multiple agents
- **Documentation**: See [examples/README.md](examples/README.md)

**Quick Start Paths**:
- 🖥️ **Want a visual interface?** → Start Web app: `python server.py`
- 🐍 **Want to build programmatically?** → Use as library: `pip install matrix-for-agents`
- 📚 **Want to learn by example?** → Explore `examples/MyWorld`

## 🧠 Why This Matters?

### The Problem

Most agent frameworks force powerful LLMs to think inside rigid formats like JSON. This:

- ❌ Wastes LLM attention on syntax instead of reasoning
- ❌ Causes frequent parsing errors and brittle workflows
- ❌ Reduces the LLM's ability to handle complex tasks

**Our theory**: Asking an LLM to perfectly format JSON while doing complex reasoning is like asking a human to solve calculus problems while juggling. You're adding unnecessary cognitive load.

### Our Solution

AgentMatrix uses a **Brain + Cerebellum + Body** architecture:

```
┌─────────────────────────────────────────────────┐
│  🧠 Brain (LLM)                                 │
│  - Reasons in natural language                 │
│  - Decides "what to do"                        │
│  - No format constraints → better reasoning    │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  🧠 Cerebellum (SLM)                            │
│  - Translates intent to structured data        │
│  - Handles parameter negotiation               │
│  - Clarifies unclear requests                 │
└─────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────┐
│  💪 Body (Python Code)                          │
│  - Executes functions                          │
│  - Provides feedback                           │
│  - Manages resources                           │
└─────────────────────────────────────────────────┘
```

**Key Insight**: Let the LLM think in natural language, then use a smaller model to translate that intent into machine-executable commands.

## ✨ Key Features

### 1. Dual-Layer Agent Architecture (v0.1.5+)

**BaseAgent = Session Layer**
- Manages conversation state across multiple user interactions
- Can maintain multiple independent sessions simultaneously
- Owns skills, actions, and capabilities

**MicroAgent = Execution Layer**
- Temporary executor for single tasks
- Inherits BaseAgent's capabilities
- Has isolated execution context
- Terminates when task completes

**🔥 Key Feature: Recursive Nesting & "LLM Functions"**

MicroAgent calls can be **recursively nested** - this is a game-changer:

```
MicroAgent Layer 1
  ├─ Calls: web_search() action
  │   └─ This action internally runs:
  │       └─ MicroAgent Layer 2 (processes search results)
  │           ├─ Calls: analyze_content() action
  │           │   └─ This action internally runs:
  │           │       └─ MicroAgent Layer 3 (extracts key info)
  │           │           └─ Returns structured data to Layer 2
  │           └─ Returns analysis to Layer 1
  └─ Returns final result to user
```

**Why This Matters**:

- ✅ **Perfect State Isolation**: Each layer's execution history stays isolated. Layer 3's complex reasoning doesn't pollute Layer 2's context. Layer 2's intermediate steps don't clutter Layer 1's session.

- ✅ **MicroAgent as "LLM Function"**: Think of `micro_agent.execute()` as a **natural language function**:
  - **Input**: Natural language task description
  - **Processing**: LLM reasoning + multi-step execution
  - **Output**: Natural language result OR structured data (via `expected_schema`)

  ```python
  # Define an "LLM function"
  async def research_topic(topic: str) -> Dict:
      """LLM function - not a regular Python function"""
      result = await micro_agent.execute(
          persona="You are a researcher",
          task=f"Research about {topic}",
          result_params={
              "expected_schema": {
                  "summary": "string",
                  "key_findings": ["string"],
                  "sources": ["string"]
              }
          }
      )
      return result  # Returns structured data

  # Call it from another MicroAgent
  @register_action(description="Research multiple topics")
  async def research_multiple_topics(topics: List[str]) -> Dict:
      results = {}
      for topic in topics:
          # Recursive MicroAgent call
          results[topic] = await research_topic(topic)
      return results
  ```

- ✅ **Build Complex Tasks Simply**: Break down complex workflows into composable LLM function calls, each with isolated context.

- ✅ **Natural Recursion**: Implement recursive task decomposition where each level is an independent MicroAgent.

**Comparison**:
- **Python Functions**: Deterministic logic, fixed flow
- **LLM Functions (MicroAgent)**: Probabilistic reasoning, flexible thinking, natural language interface

### 2. Think-With-Retry Pattern

**The Challenge**: Extract structured data from LLM outputs without hurting reasoning quality

**Our Solution**:
- Use **loose format requirements** (e.g., `[Section Name]` instead of strict JSON)
- **Intelligent retry** with specific, actionable feedback
- **Conversational flow** - retries feel like natural clarification

**Example**:
```python
result = await llm_client.think_with_retry(
    initial_messages="Create a project plan with sections: [Plan], [Timeline], [Budget]",
    parser=multi_section_parser,
    section_headers=['[Plan]', '[Timeline]', '[Budget]'],
    max_retries=3
)
```

If the LLM forgets the `[Timeline]` section:
1. Parser detects missing section
2. System automatically requests: *"Your response was helpful, but missing the [Timeline] section. Please add it."*
3. LLM corrects output naturally
4. No rigid constraints, just conversational feedback

### 3. Natural Language Coordination

Agents communicate through **Email** (natural language messages), not API calls:

```python
email = Email(
    sender="Researcher",
    recipient="Writer",
    subject="Research Report Request",
    body="Please compile a summary based on the research...",
    user_session_id="session_123"
)
await post_office.send_email(email)
```

**Benefits**:
- 📝 More interpretable and debuggable
- 🔄 Threaded conversations via `in_reply_to`
- 🤝 Agents explain what they're doing, not just return codes

### 4. Dynamic Skill Composition

Skills are **mixins** loaded at runtime via YAML configuration:

```yaml
# profiles/researcher.yml
name: Researcher
description: Research and information gathering specialist

mixins:
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.crawler_helpers.CrawlerHelpersMixin
  - agentmatrix.skills.notebook.NotebookMixin
```

**Benefits**:
- 🔧 Composable capabilities
- 📦 No code changes to add skills
- 🎯 Skills can be shared across agents

## 🚀 Quick Start

### Installation

```bash
pip install matrix-for-agents
```

### Basic Usage

```python
from agentmatrix import AgentMatrix

# Initialize the framework
matrix = AgentMatrix(
    agent_profile_path="path/to/profiles",
    matrix_path="path/to/matrix"
)

# Start the runtime
await matrix.run()
```

### Sending Tasks to Agents

```python
# Send an email to an agent
email = Email(
    sender="user@example.com",
    recipient="Researcher",
    subject="Research Task",
    body="Help me research AI safety best practices",
    user_session_id="my-session"
)

await matrix.post_office.send_email(email)
```

## 📚 Architecture Overview

### Core Components

```
AgentMatrix Runtime
├── PostOffice        # Message routing and service discovery
├── VectorDB          # Semantic search for emails/notebooks
├── AgentLoader       # Dynamically loads agents from YAML
└── Agents
    ├── BaseAgent     # Session layer - manages conversations
    └── MicroAgent    # Execution layer - runs tasks
```

### Execution Flow

```
User sends email
    ↓
BaseAgent receives email
    ↓
Restore/creates session
    ↓
Delegates to MicroAgent
    ↓
MicroAgent executes:
  1. Think: What should I do next?
  2. Detect action from LLM output
  3. Negotiate parameters (via Cerebellum)
  4. Execute action
  5. Repeat until all_finished or max_steps
    ↓
MicroAgent returns result
    ↓
BaseAgent updates session
    ↓
BaseAgent sends reply email
```

## 📖 Documentation

Comprehensive bilingual documentation (English & Chinese):

### Core Architecture
- **[Agent and Micro Agent Design](docs/architecture/agent-and-micro-agent-design.md)**
  - Dual-layer architecture philosophy
  - Session vs. execution separation
  - Skill system and communication

- **[Matrix World Architecture](docs/matrix-world.md)**
  - Project structure and components
  - Initialization and runtime flow
  - Configuration format

### Key Patterns
- **[Think-With-Retry Pattern](docs/architecture/think-with-retry-pattern.md)**
  - Natural language → structured data
  - Parser design and implementation
  - Custom parser creation guide

## 🛠️ Built-in Skills

- **Filesystem** - File operations and directory management
- **WebSearcher** - Web search with multiple search engines
- **CrawlerHelpers** - Web scraping and content extraction
- **Notebook** - Notebook creation and management
- **ProjectManagement** - Project planning and task breakdown

## 🧪 Example: Creating a Custom Agent

```yaml
# profiles/my-agent.yml
name: MyAgent
description: A custom agent for my use case
module: agentmatrix.agents.base
class_name: BaseAgent

# Load required skills
mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.web_searcher.WebSearcherMixin

# Define the agent's persona
system_prompt: |
  You are a helpful assistant specializing in
  research and analysis.

# Configure backends
backend_model: gpt-4
cerebellum_model: gpt-3.5-turbo
```

## 🤝 Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📝 License

Apache License 2.0 - see [LICENSE](LICENSE) file for details

## 🙏 Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [DrissionPage](https://drissionpage.cn/) - Browser automation
- [ChromaDB](https://www.trychroma.com/) - Vector database

## 📅 Roadmap

- [ ] Enhanced multi-agent collaboration patterns
- [ ] More built-in skills
- [ ] Performance optimizations
- [ ] Additional backend integrations
- [ ] Enhanced monitoring and debugging tools

---

**Current Version**: v0.1.5
**Status**: Alpha (APIs may evolve)
**Documentation**: [docs/](docs/) | [中文文档](readme_zh.md)

For detailed information, visit: https://github.com/webdkt/agentmatrix
