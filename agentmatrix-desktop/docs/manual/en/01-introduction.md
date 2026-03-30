# Introduction

## What is AgentMatrix Desktop?

AgentMatrix Desktop is a **distributed cognition dispatch system** — a desktop application that lets you manage, monitor, and interact with autonomous AI agents through an intuitive email-like interface.

Think of it as a **dispatch center** for AI workers. Each AI agent is like a team member with their own inbox. You send tasks via email, agents execute them autonomously, and report results back to you through email.

## How It Works

1. **You compose an email** describing a task
2. **The backend dispatches** it to the appropriate AI agent
3. **The agent thinks and acts** — using tools, browsing the web, writing files
4. **The agent replies** with results via email
5. **You review the results** in the Email View

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Agent** | An autonomous AI entity with a defined personality, skills, and access to tools |
| **Session** | A conversation thread between you and one or more agents |
| **Email** | A message (task or reply) sent within a session |
| **Matrix World** | The workspace directory where all agent data, configs, and files are stored |
| **LLM / SLM** | Large and Small Language Models that power agent reasoning |
| **Skill** | A capability an agent can use (web search, file management, email, etc.) |
| **Persona** | The personality and role definition of an agent |

## Key Features

- **Cold-Start Wizard** — Guided first-time setup (user name, workspace, AI models)
- **Email Interface** — Send, receive, reply, and manage agent communications
- **Session Management** — Organize conversations with search and pagination
- **Matrix View** — Real-time monitoring dashboard for all agents
- **Settings Panel** — Configure AI models and email proxy without editing files
- **Real-time Notifications** — WebSocket-powered instant updates
- **Multi-language** — Chinese and English interface support

## Platforms

AgentMatrix Desktop is built with Tauri 2.0 and supports:

- **macOS** (Apple Silicon & Intel)
- **Windows** (x64)
- **Linux** (x86_64)
