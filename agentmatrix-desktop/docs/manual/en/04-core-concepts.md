# Core Concepts

Understanding these concepts will help you use AgentMatrix Desktop effectively.

## Matrix World

The **Matrix World** is your workspace — a directory on your computer that contains all agent configurations, conversation history, generated files, and system settings.

When you set up AgentMatrix (via the wizard or manually), you choose a directory to serve as the Matrix World. Inside it, a hidden `.matrix/` directory holds all system data:

```
MatrixWorld/
├── .matrix/
│   ├── configs/          # All configuration files
│   │   ├── agents/       # Agent definitions
│   │   ├── prompts/      # System prompt templates
│   │   ├── system_config.yml
│   │   ├── matrix_config.yml
│   │   ├── email_proxy_config.yml
│   │   └── llm_config.json
│   ├── sessions/         # Conversation history
│   ├── files/            # Agent-generated files
│   └── logs/             # Runtime logs
└── (other workspace files)
```

## Agents

An **Agent** is an autonomous AI entity. Each agent has:

- **Name** — A unique identifier (e.g., "mark", "SystemAdmin")
- **Persona** — A role definition that shapes how the agent thinks and responds
- **Skills** — Capabilities the agent can use (web search, file management, email, etc.)
- **Class** — The agent type that determines its behavior pattern
- **Backend Model** — Which LLM/SLM configuration the agent uses for reasoning

AgentMatrix comes with pre-configured agents:

| Agent | Role | Skills |
|-------|------|--------|
| **User** | Represents you in the system | base, email |
| **SystemAdmin** | Manages system configuration and agent profiles | base, email, agent_admin, system_admin, file |
| **mark** | Web research and OSINT specialist | file, web_search |

You can create additional agents by adding YAML configuration files in the agents directory.

## Sessions

A **Session** is a conversation thread — an ongoing exchange of messages (emails) between you and one or more agents. Sessions organize your work into logical groups.

Each session has:

- A list of participants (you and the agents involved)
- A sequence of emails (the conversation history)
- An unread indicator showing new messages

Sessions are created when you send your first email to an agent, or when an agent initiates contact.

## Emails

An **Email** is a message within a session. Despite the name, emails in AgentMatrix are not sent over the internet (unless you configure the Email Proxy). They are internal messages between you and agents.

Each email contains:

- **From** — The sender (you or an agent)
- **To** — The recipient(s)
- **Subject** — A topic line
- **Body** — The message content (supports Markdown formatting)
- **Attachments** — Optional file attachments

Emails are the primary way you interact with agents — you send a task as an email, the agent processes it, and replies with results.

## LLM and SLM

AgentMatrix uses two AI models:

- **LLM (Large Language Model)** — The "Brain." A powerful model used for complex reasoning, planning, and decision-making. Examples: GPT-4o, Claude Sonnet 4, Gemini 1.5 Pro.
- **SLM (Small Language Model)** — The "Cerebellum." A faster, cheaper model for lightweight tasks like email parsing, classification, and quick responses. Examples: GPT-4o Mini, Claude Haiku 4, Gemini 2.0 Flash.

The separation ensures complex tasks get the best AI quality while simple tasks remain fast and cost-effective.

## Skills

A **Skill** is a capability that an agent can use. Skills are defined in the agent's configuration and determine what tools the agent has access to.

Common skills include:

| Skill | Description |
|-------|-------------|
| **base** | Core reasoning and text generation |
| **email** | Send and receive emails |
| **file** | Read, write, and manage files |
| **web_search** | Search the internet for information |
| **agent_admin** | Manage other agents' configurations |
| **system_admin** | Manage system-level configurations |

## Persona

A **Persona** is the personality and role definition of an agent. It's a text description that tells the agent:

- Who it is
- What its responsibilities are
- How it should behave
- What constraints it should follow

Personas are written in the agent's YAML configuration file and loaded at runtime. They significantly influence how the agent responds to tasks.

## Email Proxy

The **Email Proxy** is an optional bridge between AgentMatrix and a real email account (via IMAP/SMTP). When enabled:

- Emails sent from AgentMatrix can be delivered to real email addresses
- Incoming emails from your real inbox can be forwarded to AgentMatrix agents

This allows agents to interact with external contacts through your email account.

## Container Runtime

AgentMatrix uses **Podman** (preferred) or **Docker** to run agents in isolated containers. This provides:

- Security isolation between agents
- Consistent runtime environments
- Resource management

The application auto-detects which runtime is available on your system. On macOS, AgentMatrix can bundle Podman installers for convenience.
