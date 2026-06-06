# agentmatrix-core

**Let LLMs think. Don't make them write JSON.**

A Python execution engine for building AI agent applications. Separates reasoning from formatting: the large model thinks in natural language, a dedicated module handles the structured output.

---

## What It Is

`agentmatrix-core` provides the execution engine behind AgentMatrix. It includes:

- **MicroAgent** — A task execution engine with think-negotiate-act loop
- **AgentShell Protocol** — Clean boundary between execution and I/O
- **Cerebellum** — Intent parsing and parameter negotiation
- **Action System** — Pluggable skill registry and execution
- **SessionStore** — Conversation persistence
- **Auto-Compression** — Working Notes for arbitrarily long tasks
- **Signal System** — Event-driven communication

The core knows nothing about desktop apps, file systems, or networks. All external interaction goes through the `AgentShell` protocol, which you implement for your target environment.

---

## Install

```bash
pip install agentmatrix-core
```

Requires Python 3.12+.

---

## Quick Example

```python
from agentmatrix import AgentMatrix, Email

# Create the runtime
matrix = AgentMatrix("./MatrixWorld")

# Send an email to an agent
email = Email(
    sender="User",
    recipient="Researcher",
    subject="Search for Python 3.13 features",
    body="Find and summarize the major new features in Python 3.13"
)

# Dispatch via PostOffice
await matrix.post_office.dispatch(email)
```

For a complete minimal example implementing `AgentShell`, see the CLI tutorial in the repository.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Your App (Desktop / CLI / Server)          │
├─────────────────────────────────────────────┤
│  AgentShell Protocol (you implement this)   │
├─────────────────────────────────────────────┤
│  MicroAgent Engine (this package)           │
│  - Brain (reasoning in natural language)    │
│  - Cerebellum (intent → action params)      │
│  - Action Registry                          │
│  - SessionStore                             │
└─────────────────────────────────────────────┘
```

---

## Key Design

- **No JSON output required** — Brain reasons in plain text
- **Dynamic skill composition** — Mixins assembled at runtime per task
- **Checkpoint-based pause/resume** — Cooperative, not forced interruption
- **Auto context compression** — LLM-generated Working Notes prevent overflow
- **Nested MicroAgents** — Tasks can spawn sub-tasks with different skill sets

---

## Documentation

- Full docs: https://github.com/webdkt/agentmatrix/docs
- CLI tutorial: https://github.com/webdkt/agentmatrix/tree/main/tutorial/cli-agent

---

## License

Apache License 2.0
