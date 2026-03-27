# AgentMatrix

[English](readme.md) | [中文](readme_zh.md)

**Let LLMs think. Don't make them write JSON.**

Here's a question we kept asking ourselves: why does getting a powerful language model to do anything require first teaching it JSON syntax?

You ask GPT to research a topic. It has to understand your intent, then carefully format `{"action": "search", "parameters": {"query": "..."}}`. Two completely different skills—reasoning and formatting—forced into a single output channel. It's like asking someone to solve calculus while simultaneously writing calligraphy. Both tasks suffer.

AgentMatrix separates these two concerns. Let the large model think. Let the small model handle the format. That's it.

---

## What It Is

AgentMatrix is a multi-agent framework with a native desktop app.

It's not just another "AI Agent SDK." It redefines how agents collaborate with each other and with humans.

### Three Core Innovations

**1. Brain + Cerebellum: Separate Thinking from Execution**

```
Brain (LLM)         →  Thinks in natural language, decides "what to do"
Cerebellum (SLM)    →  Translates intent into structured parameters  
Body (Python Code)  →  Actually executes
```

The Brain doesn't need to know what JSON is. It just thinks. The Cerebellum takes "I think we should search for this topic" and turns it into `web_search(query="...")`. If the intent is ambiguous, the Cerebellum asks the Brain for clarification. Two models, each doing what they're best at.

**2. Email System: How Agents Talk to Each Other**

Agents don't call each other's APIs. They send emails.

```python
email = Email(
    sender="Researcher",
    recipient="Writer",
    subject="Research Report Request",
    body="Please compile a summary based on the key points I've gathered...",
)
await post_office.send_email(email)
```

Why email? Because natural language is easier to debug than APIs. You can read what agents are saying to each other. You can trace conversation threads. You can understand *why* an agent did something. It doesn't just return a status code—it explains its reasoning.

**3. MicroAgent: Natural Language Functions**

In traditional frameworks, you write Python functions that call other Python functions. In AgentMatrix, you write "natural language functions" that call other "natural language functions":

```python
async def research_topic(topic: str) -> dict:
    """This is an LLM function, not a regular Python function"""
    return await micro_agent.execute(
        persona="You are a researcher",
        task=f"Do deep research on {topic}",
        result_params={
            "expected_schema": {
                "summary": "One-line summary",
                "findings": ["Key findings"],
            }
        }
    )

# Called from another Agent
@register_action(description="Compare research across topics")
async def compare_topics(topics: list) -> dict:
    results = {}
    for topic in topics:
        results[topic] = await research_topic(topic)  # Recursive, isolated
    return results
```

Each MicroAgent has its own isolated execution context. You can nest MicroAgent calls recursively—each layer stays clean. Complex tasks naturally decompose into composable "language functions."

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 Desktop App (Tauri + Vue 3)                  │
│         MERIDIAN Design · Matrix-themed Init Wizard          │
└──────────────────────────┬──────────────────────────────────┘
                           │ WebSocket + REST API
┌──────────────────────────┴──────────────────────────────────┐
│                    FastAPI Server                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│                  AgentMatrix Runtime                         │
│                                                             │
│  ┌──────────────┐  ┌────────────────┐  ┌─────────────────┐  │
│  │  PostOffice  │  │  ConfigService │  │  TaskScheduler  │  │
│  │  (Messaging) │  │  (Config Mgmt) │  │  (Scheduling)   │  │
│  └──────┬───────┘  └────────────────┘  └─────────────────┘  │
│         │                                                   │
│  ┌──────┴───────────────────────────────────────────────┐   │
│  │                     Agents                            │   │
│  │  ┌──────────────┐  ┌─────────────────────────────┐   │   │
│  │  │  BaseAgent   │  │  MicroAgent (recursively     │   │   │
│  │  │  Persistent  │  │  nestable)                    │   │   │
│  │  │  Session     │  │  Ephemeral Execution          │   │   │
│  │  └──────────────┘  └─────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│         │                                                   │
│  ┌──────┴──────────────────────────────────────────────┐    │
│  │           Docker Containers (per-agent isolation)    │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Features

### Think-With-Retry: Natural Language Structured Extraction

Don't require strict JSON from LLMs. Use loose format markers (like `[Section Name]`), and if the output is incomplete, the system provides conversational feedback for self-correction:

```python
result = await llm.think_with_retry(
    initial_messages="Create a plan with sections: [Approach], [Timeline], [Budget]",
    parser=section_parser,
    max_retries=3
)
# LLM forgot [Timeline]? The system says: "Great response, but missing the 
# [Timeline] section. Please add it."
# Not an error. A conversation.
```

### Dynamic Skill Composition

Skills are Python Mixins, dynamically composed onto Agent classes at runtime:

```yaml
# Agent configuration (YAML)
name: Researcher
description: Deep research specialist
skills:
  - web_search
  - crawler
  - memory
  - deep_researcher
```

Write a new `skill.py`, drop it in the skills directory, and the Agent automatically gains new capabilities. No existing code changes required.

### Container-Level Isolation

Each Agent runs in its own Docker container. File operations execute inside containers. Agents can't interfere with each other. Containers wake and hibernate on demand.

### Content-First Configuration

Configuration passes between agents as raw text. Because LLMs naturally read YAML/JSON, config errors are fed back to the agent in natural language for self-correction. ConfigService handles validation, backup, and safe writes.

---

## Desktop App

Native desktop application built on Tauri (Rust) + Vue 3.

### MERIDIAN Design Language

We call our design style **MERIDIAN**—an "intelligence archive room" aesthetic.

- Edit-first, zero decoration. Hierarchy through borders and whitespace, not shadows and gradients.
- Serif carries thought. Sans-serif drives action.
- Vermillion (#C23B22) appears only where it matters: selected borders, focus states, the thinking progress bar.
- Chinese and English treated equally, each with dedicated font stacks.

### Matrix-Themed Init Wizard

First launch takes you through a full-screen Matrix-themed setup: typewriter effects, character rain animation, step-by-step configuration—user name, workspace, Brain model, Cerebellum model. Not cold CLI prompts. A ritual.

### Real-Time Status Sync

Agent status pushes to the desktop app via WebSocket in real-time. Every `update_status()` triggers a push—no polling. You see agents thinking, working, waiting for your input, as it happens.

---

## Quick Start

### Desktop App (Recommended)

```bash
cd agentmatrix-desktop
npm install
npm run tauri:dev
```

The init wizard launches on first run. Follow the prompts.

### As a Python Library

```bash
pip install matrix-for-agents
```

```python
from agentmatrix import AgentMatrix

matrix = AgentMatrix(
    agent_profile_path="path/to/profiles",
    matrix_path="path/to/matrix"
)

await matrix.run()
```

---

## Built-in Skills

| Skill | Description |
|-------|-------------|
| `base` | Core: get time, ask user, list additional skills |
| `file` | File operations: read, write, search, bash (executes in container) |
| `browser` | Browser automation |
| `web_search` | Web search |
| `email` | Email send/receive (with attachments) |
| `memory` | Knowledge / memory management |
| `deep_researcher` | Deep research (multi-agent collaboration) |
| `system_admin` | System management |
| `agent_admin` | Agent lifecycle management |
| `scheduler` | Task scheduling |

You can also write your own skills. One `skill.py` file is all it takes.

---

## Project Structure

```
agentmatrix/
├── src/agentmatrix/          # Core framework
│   ├── agents/               # BaseAgent + MicroAgent
│   ├── core/                 # Runtime, Cerebellum, Action system
│   ├── skills/               # Built-in skills
│   ├── services/             # ConfigService, etc.
│   └── backends/             # LLM backend adapters
├── agentmatrix-desktop/      # Native desktop app
│   ├── src/                  # Vue 3 frontend
│   └── src-tauri/            # Tauri (Rust) backend
├── server.py                 # FastAPI server
├── examples/                 # Examples
└── docs/                     # Documentation
```

---

## What This Is Not

- Not a wrapper. We don't wrap LLM APIs. We rethink how agents think.
- Not a no-code tool. You write Python, YAML, and natural language.
- Not a toy project. Docker isolation, session management, persistence, real-time sync—all seriously implemented.

---

## Documentation

- [Agent and MicroAgent Design](docs/architecture/agent-and-micro-agent-design.md)
- [Matrix World Architecture](docs/matrix-world.md)
- [Think-With-Retry Pattern](docs/architecture/think-with-retry-pattern.md)
- [Config Service and Admin Skills](docs/core/config-service-and-admin-skill.md)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE)

---

## Roadmap

- [ ] Enhanced multi-agent collaboration patterns
- [ ] More built-in skills
- [ ] Additional LLM backend support
- [ ] Enhanced monitoring and debugging tools
- [ ] Plugin marketplace

---

**Version**: v0.3.0 | **Status**: Alpha  
**Repository**: https://github.com/webdkt/agentmatrix
