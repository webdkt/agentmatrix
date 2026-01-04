# Agent-Matrix

A cognition-centric autonomous agent framework with pluggable skills and multi-backend LLM integrations.

## Overview

Agent-Matrix is a multi-agent framework where agents act as independent "digital employees" that collaborate through asynchronous messaging (similar to email) rather than rigid API calls.

Designed for building robust, intelligent systems that can reason, negotiate, and handle ambiguity like humans do.

## Core Philosophy

The core philosophy is simple: Many agent frameworks force powerful LLMs to "think" in rigid formats like JSON, which is error-prone and limits their reasoning capabilities.

**Agent-Matrix's approach**: Let LLMs communicate, think, and output in natural language. The brain should focus on reasoning, not JSON conversion.

Agent-Matrix solves this with a **Brain + Cerebellum + Body** architecture:

- 🧠 **Brain (The LLM):** Strategic thinker. Uses natural language for high-level reasoning and intent formation. Like a pilot in a cockpit deciding "where to go" without worrying about switch details.
- 🧠 **Cerebellum (The SLM):** Precise interface manager. Translates natural language intent into machine-executable commands (JSON). Understands intent and fills in JSON.
- 💪 **Body**: The Python program that executes functions based on JSON and provides feedback.

When the brain's intent is unclear (e.g., "send email" without specifying recipient), the cerebellum doesn't error or blindly execute. Instead, it **initiates "negotiation"** by sending an internal query back to the brain for clarification. This internal dialogue makes agents exceptionally robust and intelligent.

## Core Concepts

- **Agent**: A digital employee with a specific persona and capability list
- **PostOffice**: Central communication hub for all inter-agent messages
- **Runtime (the Matrix)**: Execution environment including memory structures and directory layout
- **Signal**: Information unit in the system - new emails, tool results, or cerebellum queries
- **Email**: How agents communicate. Email reply chains automatically maintain conversation context

## How It Works: Turn-Based Loop

An agent's lifecycle is like a turn-based game:

1. **Awake**: A `Signal` arrives, waking the agent from sleep
2. **Reasoning**: Brain analyzes signal and history, reasoning in the `THOUGHT` section (internal monologue)
3. **Decision**: Brain makes a decision and outputs a clear `ACTION SIGNAL`, e.g., "Send Coder an email with code review request"
4. **Negotiation**: Cerebellum intercepts the instruction
   - **If clear**: Translate to JSON and let it through
   - **If unclear**: Pause execution, generate an `[INTERNAL QUERY]` signal back to brain, starting a "sub-turn" for clarification
5. **Execution**: Agent's "body" executes the cerebellum-validated instruction
6. **Feedback & Rest**: Action results immediately return as `[BODY FEEDBACK]` signal, triggering next turn. This continues until brain explicitly decides `rest_n_wait` action

See `docs/Design.md` for detailed architecture.

## Key Features & Advantages

- ✅ **Exceptional Robustness**: "Negotiation mechanism" fundamentally eliminates execution failures from format errors or unclear intent
- 🧠 **Stronger Intelligence**: Decouples "thinking" from "actioning", letting the brain (LLM) do complex reasoning unencumbered by formats
- 🌐 **True Asynchronous Collaboration**: Message passing through "post office" naturally supports complex, parallel social agent workflows
- 🧘 **Explicit Will-Driven**: Agents have "free will". Must actively decide when to rest (`rest_n_wait`), making multi-step tasks simple and natural

**The biggest advantage**: Makes workflow design remarkably simple

## Trade-offs

Everything has trade-offs. This architecture has two potential drawbacks:

1. When brain and cerebellum negotiate clarification, multiple rounds of dialogue may consume more tokens
2. Fully asynchronous mechanism with email communication means each agent processes emails serially. While beneficial, tasks may sit in queue longer before processing

However, these aren't major issues. What matters most for agents is intelligence and robustness - autonomously completing work correctly. Taking one hour vs two hours doesn't matter much. And token costs will only decrease long-term. Spending tokens to do things right is worth it.

## Installation

```bash
pip install matrix-for-agents
```

## Quick Start

### Basic Usage

```python
from agent_matrix import AgentMatrix

# Initialize the framework
matrix = AgentMatrix(
    agent_profile_path="agent_profile_path",
    matrix_path="matrix_path"
)

# Start the runtime (this will load all agents from profiles)
await matrix.run()
```

### Using the CLI Runner (Recommended for First-Time Users)

The package includes `cli_runner.py` as a practical example for interacting with agents:

```python
# Run the CLI runner
python cli_runner.py
```

The CLI runner provides:
- 📥 Interactive command-line interface
- 💬 Real-time agent communication
- 🔄 Multi-session support
- 📝 Message reply tracking

**Usage Example:**
```bash
# Start the CLI
$ python cli_runner.py
>>> 系统启动。可以在下面输入指令。
>>> 例如: Planner: 帮我分析数据

# Send a message to an agent
>> Planner: 请帮我爬取网页数据

# Start a new session
>> new session
✅ 新会话开始 ID: a1b2c3d4-...

# Reply to a specific message
>> reply: msg-123: 谢谢你的分析

# Exit and save
>> exit
```

The CLI runner demonstrates:
- How to initialize the AgentMatrix framework
- How to set up event callbacks
- How to communicate with agents through the User proxy
- How to handle multi-session conversations

For full source code, see `cli_runner.py` in the package installation directory.

## Project Structure

```
agent-matrix/
├── agents/          # Agent implementations
│   ├── base.py      # Base agent class
│   └── post_office.py  # Message routing system
├── core/            # Core framework
│   ├── runtime.py   # Main runtime
│   ├── message.py   # Email/Signal definitions
│   └── browser/     # Browser automation
├── skills/          # Built-in skills
│   ├── data_crawler.py    # Web scraping
│   ├── web_searcher.py    # Web search
│   └── filesystem.py      # File operations
├── backends/        # LLM integrations
├── db/              # Database layer
├── profiles/        # Agent configurations (YAML)
└── docs/            # Documentation
```

## Usage Examples

### Agent Communication

```python
from agent_matrix import Email

email = Email(
    sender="researcher",
    recipient="analyst",
    subject="Data Analysis Request",
    body="Please analyze the crawled data...",
    user_session_id="session_123"
)

# Send through post office
await matrix.post_office.dispatch(email)
```

### Built-in Skills

Agents automatically load skills based on their profiles:

```yaml
# profiles/analyst.yaml
name: "analyst"
description: "Data analysis specialist"
skills:
  - filesystem
  - web_searcher
```

## Requirements

- Python 3.8 or higher
- See `requirements.txt` for full dependency list

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## Roadmap

- [ ] Enhanced multi-agent collaboration patterns
- [ ] More built-in skills
- [ ] Improved documentation and tutorials
- [ ] Performance optimizations
- [ ] Additional backend integrations

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/) (Not really used, will use later)
- Browser automation powered by [DrissionPage](https://drissionpage.cn/)
- Vector search with [ChromaDB](https://www.trychroma.com/)

---

**Note**: Agent-Matrix is currently in alpha release (v0.1.2). APIs and features may evolve as we develop the framework.

For Chinese documentation, see [readme_zh.md](readme_zh.md)
