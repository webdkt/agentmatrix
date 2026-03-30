# Glossary

Definitions of terms used throughout AgentMatrix Desktop.

| Term | Definition |
|------|------------|
| **Agent** | An autonomous AI entity configured with a name, persona, skills, and a language model. Agents execute tasks and communicate via email. |
| **Backend** | The Python runtime server that manages agent execution, handles API requests, and coordinates the WebSocket connection. |
| **Brain (LLM)** | The Large Language Model used for complex reasoning tasks. Configured as `default_llm`. |
| **Cerebellum (SLM)** | The Small Language Model used for lightweight, fast tasks. Configured as `default_slm`. |
| **Cold-Start** | The first-time setup process that runs when AgentMatrix detects no existing configuration. |
| **Container Runtime** | Software (Podman or Docker) that runs agents in isolated environments. |
| **Email** | A message within a session — the primary communication method between you and agents. |
| **Email Proxy** | An optional bridge connecting AgentMatrix to a real email account via IMAP/SMTP. |
| **IMAP** | Internet Message Access Protocol — used for receiving emails from a mail server. |
| **LLM** | Large Language Model — a powerful AI model (e.g., GPT-4o, Claude Sonnet) used for complex reasoning. |
| **Matrix View** | The monitoring dashboard showing all agents, their status, logs, and session history. |
| **Matrix World** | The workspace directory containing all agent data, configurations, and generated files. |
| **MERIDIAN** | The custom design system used by AgentMatrix Desktop (Parchment + Ink + Vermillion palette). |
| **Persona** | A text description defining an agent's personality, role, responsibilities, and behavioral constraints. |
| **Podman** | A rootless container engine — the preferred container runtime for AgentMatrix. |
| **Session** | A conversation thread — a sequence of emails between you and one or more agents. |
| **Skill** | A capability that an agent can use, such as web search, file management, or email handling. |
| **SLM** | Small Language Model — a faster, cheaper AI model used for simple tasks. |
| **SMTP** | Simple Mail Transfer Protocol — used for sending emails through a mail server. |
| **System Prompt** | The base instruction template loaded for every agent at runtime, defining the communication protocol and cognitive model. |
| **Tauri** | The desktop application framework used to build AgentMatrix (Rust backend + WebView frontend). |
| **WebSocket** | A real-time communication protocol used for instant updates between the frontend and backend. |
| **Wizard** | The guided first-run setup process (Cold-Start Wizard) that configures essential settings. |
