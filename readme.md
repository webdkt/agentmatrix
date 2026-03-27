# AgentMatrix

[English](readme.md) | [中文](readme_zh.md)

**Let LLMs think. Don't make them write JSON.**

Here's a question we kept asking: why does getting a powerful language model to do anything require first teaching it JSON syntax?

You ask GPT to research a topic. It has to understand your intent, then carefully output perfectly formatted JSON. Two completely different skills—reasoning and formatting—forced into a single output channel. Like solving calculus while writing calligraphy. Both tasks suffer.

AgentMatrix separates these two concerns. The large model thinks. The small model handles the format. That's it.

---

## What It Is

AgentMatrix is a multi-agent framework with a native desktop app.

It's not just another "AI Agent SDK." It redefines how agents collaborate with each other and with humans.

---

## What Agents Can Do

### Think Freely

The agent's "Brain" (large model) reasons entirely in natural language. No JSON output required, no format constraints. Say what you mean. A separate "Cerebellum" (smaller model) translates intent into executable parameters. If the intent is ambiguous, the Cerebellum asks the Brain for clarification. Two models, each doing what they're best at.

### Collaborate Like Email

Agents don't call each other's APIs. They send emails. Natural language emails.

You can read what agents are saying to each other. You can trace conversation threads. You can understand *why* an agent did something. It doesn't just return a status code—it explains its reasoning. This makes debugging and understanding multi-agent systems feel natural for the first time.

### Pause, Resume, Stop — Anytime

Any running agent can be paused, resumed, or stopped. When paused, it halts at a safe checkpoint, saves its state, and can be resumed later. Stopping the current task doesn't affect the agent's ability to receive new emails.

### Run Extremely Long Jobs Without Blowing Up Context

Agents can execute tasks spanning thousands of steps or unlimited duration. When conversation history grows too large, the system automatically compresses it into a "Whiteboard"—a dynamic state snapshot. This isn't a fixed template. The LLM analyzes the conversation type (research, knowledge, creative writing) and generates the optimal structure for that specific context. Tasks can run for hours or days; the context window never overflows.

### Ask You Questions Mid-Execution

Agents can pause mid-task and ask you a question, then wait for your answer before continuing. The desktop app shows a dialog. You can also reply by email. Dual notification channels—desktop popup plus email—so you never miss it.

### Isolated Workspaces Per Task

Every task gets its own private working directory. Files created in Task A don't interfere with Task B. Workspaces switch automatically when the agent moves between tasks.

### Run in Isolated Containers

Each agent runs in its own Docker container. File operations execute inside the container. Agents can't interfere with each other. Containers wake and hibernate on demand—dormant when idle to save resources, automatically activated when new mail arrives.

### Survive Restarts

Conversation history is automatically persisted to disk. After a shutdown and restart, agents resume from where they left off. Tasks in progress are not lost.

### Recover from LLM Outages

If the LLM service goes down during execution, the agent enters a wait mode, periodically checking for recovery. When the service comes back, execution continues automatically. No progress is lost.

---

## System Management: In Natural Language

AgentMatrix has a unique design principle: because LLMs naturally read YAML/JSON, system configuration can be managed entirely through natural language.

### SystemAdmin Agent

No need to edit config files manually. Just tell SystemAdmin what you want:

- "Add a new LLM model using GPT-4o"
- "Turn off the email proxy"
- "Show me the current system configuration"
- "Restart the system"

SystemAdmin reads the config, validates the format, tests connections, backs up the old version, and writes the new one. Natural language feedback at every step.

### AgentAdmin Agent

Manage other agents' lifecycles, also in natural language:

- "Create an agent called Researcher with web_search and memory skills"
- "Clone Writer as Editor"
- "Stop Researcher's current task"
- "Reload Writer with the new config"
- "Delete Editor"

Creation validates that skills exist and models are reachable. Edits are auto-backed up before writing. Rollback is supported—you can view and restore any historical config version at any time.

### Configuration Safety

Every config write goes through a full validation pipeline: parse → schema validation → content validation (do skills exist? are models reachable?) → connection test → backup old file → write new file. Automatically keeps the last 5 backup versions per config type, available for rollback anytime.

---

## Skill System

### Built-in Skills

The framework ships with a set of Python skills covering file operations, browser, search, email, memory management, system management, and more. They work out of the box.

| Skill | Capability |
|-------|------------|
| file | File read/write, search, command execution (inside container) |
| browser | Browser automation |
| web_search | Web search |
| email | Send emails to other agents (with attachments) |
| memory | Knowledge and memory management |
| system_admin | System configuration management |
| agent_admin | Agent lifecycle management |
| scheduler | Scheduled tasks (with recurring support) |

### Extend with Code

Developers can write custom Python skills for domain-specific capabilities. Skills can declare dependencies on each other—resolved automatically. Requires code development.

### Extend with Markdown (Recommended)

No code required. Place a `skill.md` file in the workspace's `/home/SKILLS/` directory, describing procedures and workflows in Markdown. The agent reads it as procedural knowledge. Define SOPs, workflows, domain expertise—plain text is enough. The easiest way to extend.

---

## Desktop App

Native desktop application built on Tauri (Rust) + Vue 3.

### Matrix-Themed Initialization

First launch takes you through a full-screen Matrix-themed setup: character rain animation, typewriter reveal, step-by-step configuration—user name, workspace, Brain model, Cerebellum model. Not cold CLI prompts. A ritual.

### Real-Time Status

Agent status (thinking, working, waiting for input, paused...) is pushed to the desktop via WebSocket in real-time. You see what agents are doing, step by step. No refresh, no polling.

### Email-Style Interaction

Send emails to agents, just like writing to a colleague. Drag-and-drop file attachments. Conversations organized as threaded replies.

### Prompt Preview

View any agent's complete System Prompt without executing a task. Useful for debugging configuration.

### Settings

Manage LLM configuration (models, API keys, endpoints) and email proxy settings through the GUI. No config file editing.

### Bilingual

Full Chinese and English interface support.

---

## Email Proxy: Talk to Agents via Real Email

Configure the email proxy and you can interact with agents using Gmail, Outlook, QQ Mail, or any email client:

- Send an email with `@AgentName` in the subject, and the agent receives and processes it
- Agent replies are forwarded to your inbox, maintaining the email thread
- When an agent asks you a question, just reply to the email
- Attachments transfer automatically in both directions

The internal agent email system and the external email world, connected.

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

---

## Project Structure

```
agentmatrix/
├── src/agentmatrix/          # Core framework
│   ├── agents/               # BaseAgent + MicroAgent
│   ├── core/                 # Runtime, Cerebellum, Action system
│   ├── skills/               # Built-in skills
│   └── services/             # ConfigService, etc.
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

**Version**: v0.3.0 | **Status**: Alpha  
**Repository**: https://github.com/webdkt/agentmatrix
