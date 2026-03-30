# Configuration Files

AgentMatrix Desktop uses several configuration files to store settings. Understanding their locations and formats helps you troubleshoot issues and make advanced customizations.

## Application-Level Configuration

### `~/.agentmatrix/settings.json`

This file stores the desktop application's core settings. It is created automatically when you complete the first-run wizard.

**Location**: `~/.agentmatrix/settings.json` (in your home directory)

**Format**: JSON

**Fields**:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `matrix_world_path` | string | `"~/MatrixWorld"` | Path to your Matrix World workspace directory |
| `auto_start_backend` | boolean | `true` | Whether to start the Python backend automatically on app launch |
| `enable_notifications` | boolean | `true` | Whether to show desktop notifications |
| `log_level` | string | `"INFO"` | Logging verbosity level (DEBUG, INFO, WARNING, ERROR) |

**Example**:

```json
{
  "matrix_world_path": "~/MatrixWorld",
  "auto_start_backend": true,
  "enable_notifications": true,
  "log_level": "INFO"
}
```

## Matrix World Configuration

All files below are located inside your Matrix World directory, under `.matrix/configs/`.

### `system_config.yml`

Basic system identity settings.

**Location**: `.matrix/configs/system_config.yml`

**Format**: YAML

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `user_agent_name` | string | Your display name in the system |
| `matrix_version` | string | Matrix World format version |
| `description` | string | Description of this Matrix World instance |
| `timezone` | string | Timezone for timestamps (e.g., "UTC", "Asia/Shanghai") |
| `proxy` | object | Optional. HTTP proxy settings (see below) |

**Example**:

```yaml
user_agent_name: "Alice"
matrix_version: "1.0.0"
description: "AgentMatrix World"
timezone: "Asia/Shanghai"

proxy:
  enabled: false
  host: "127.0.0.1"
  port: 7890
```

**Proxy fields**:

| Field | Type | Description |
|-------|------|-------------|
| `proxy.enabled` | boolean | Whether to route HTTP traffic through the proxy |
| `proxy.host` | string | Proxy server hostname or IP address |
| `proxy.port` | number | Proxy server port number |

When enabled, the proxy settings affect:
- LLM API calls (via `HTTP_PROXY` / `HTTPS_PROXY` environment variables)
- LLM connection verification tests
- Agent containers (with container-specific hostname mapping: `host.containers.internal` for Podman, `host.docker.internal` for Docker)

### `matrix_config.yml`

System-wide operational settings including container runtime and email proxy.

**Location**: `.matrix/configs/matrix_config.yml`

**Format**: YAML

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `user_agent_name` | string | Your display name |
| `matrix_version` | string | Matrix version identifier |
| `container.runtime` | string | Container runtime: "auto", "podman", or "docker" |
| `container.auto_start` | boolean | Auto-start containers on launch |
| `container.fallback_strategy` | string | What to do if preferred runtime unavailable ("fallback") |
| `email_proxy.enabled` | boolean | Enable email proxy bridge |
| `email_proxy.matrix_mailbox` | string | Matrix system email address |
| `email_proxy.user_mailbox` | string | Your email address |

**Example**:

```yaml
user_agent_name: "Alice"
matrix_version: "1.0.0"
description: "AgentMatrix World"
timezone: "UTC"

container:
  runtime: "auto"
  auto_start: true
  fallback_strategy: "fallback"

email_proxy:
  enabled: false
  matrix_mailbox: ""
  user_mailbox: ""
```

### `email_proxy_config.yml`

Dedicated email proxy IMAP/SMTP settings.

**Location**: `.matrix/configs/email_proxy_config.yml`

**Format**: YAML

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean | Enable the email proxy |
| `matrix_mailbox` | string | Matrix system email address |
| `user_mailbox` | string | Your email address |
| `imap.host` | string | IMAP server hostname |
| `imap.port` | number | IMAP server port (typically 993) |
| `imap.user` | string | IMAP login username |
| `imap.password` | string | IMAP login password |
| `smtp.host` | string | SMTP server hostname |
| `smtp.port` | number | SMTP server port (typically 587) |
| `smtp.user` | string | SMTP login username |
| `smtp.password` | string | SMTP login password |

**Example**:

```yaml
enabled: false
matrix_mailbox: "matrix@example.com"
user_mailbox: "alice@example.com"
imap:
  host: "imap.gmail.com"
  port: 993
  user: "alice@gmail.com"
  password: "your-app-password"
smtp:
  host: "smtp.gmail.com"
  port: 587
  user: "alice@gmail.com"
  password: "your-app-password"
```

### `llm_config.json`

AI model endpoint configurations.

**Location**: `.matrix/configs/llm_config.json`

**Format**: JSON

Contains entries for each configured LLM/SLM. Each entry has:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Configuration name (e.g., "default_llm") |
| `model_name` | string | Model identifier |
| `api_key` | string | Provider API key |
| `base_url` | string | API endpoint URL |
| `description` | string | Human-readable description |

### Agent Configuration Files

Individual agent definitions are stored as YAML files in `.matrix/configs/agents/`.

**Location**: `.matrix/configs/agents/<agent_name>.yml`

**Format**: YAML

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Agent display name |
| `description` | string | What the agent does |
| `class_name` | string | Agent class (determines behavior pattern) |
| `backend_model` | string | Which LLM config to use (e.g., "default_llm") |
| `skills` | list | List of skill names the agent can use |
| `persona` | string | The agent's personality and role definition |

**Example** (`mark.yml`):

```yaml
name: "mark"
description: "Web research and OSINT specialist"
class_name: agentmatrix.agents.base.BaseAgent
backend_model: default_llm
skills:
  - file
  - web_search
persona: |
  You are an expert OSINT researcher. Your job is to find
  accurate, well-sourced information from the web.
```

### System Prompt Template

**Location**: `.matrix/configs/prompts/system_prompt.md`

A template file that defines the runtime prompt for all agents. It uses template variables like `$persona`, `$agent_name`, `$user_name`, and `$actions_list` that are filled in at runtime.

You typically do not need to modify this file unless you want to change the fundamental behavior of how all agents process information.

## File Summary

| File | Location | Purpose |
|------|----------|---------|
| Application settings | `~/.agentmatrix/settings.json` | Desktop app configuration |
| System config | `.matrix/configs/system_config.yml` | System identity & proxy settings |
| Matrix config | `.matrix/configs/matrix_config.yml` | Operational settings |
| Email proxy config | `.matrix/configs/email_proxy_config.yml` | IMAP/SMTP settings |
| LLM config | `.matrix/configs/llm_config.json` | AI model endpoints |
| Agent configs | `.matrix/configs/agents/*.yml` | Agent definitions |
| System prompt | `.matrix/configs/prompts/system_prompt.md` | Runtime prompt template |
