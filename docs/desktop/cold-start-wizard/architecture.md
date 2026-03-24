# Architecture

## Responsibility Split

The cold start wizard separates concerns across three layers:

### Tauri (Rust) — File System Operations

Handles all file creation. No backend needed.

- `init_matrix_world` — copies template directory, replaces `{{USER_NAME}}` in `User.yml` and `system_config.yml`
- `save_llm_config` — writes `llm_config.json` to `.matrix/configs/`
- `save_email_proxy_config_cmd` — writes `email_proxy_config.yml` to `.matrix/configs/`

### Frontend (Vue) — User Interaction

Collects input, orchestrates the flow.

- `ColdStartWizard.vue` — step management, validation, Enter/click navigation
- `ModelSelector.vue` — model search with pattern matching (GPT→OpenAI, etc.)
- `submitWizard()` in store — calls Tauri commands, then starts backend

### Backend (Python) — Runtime Only

Does NOT create files. Only reads existing files and starts the runtime.

- `/api/config/init` — receives `matrix_world_path`, calls `init_runtime()`
- `MatrixConfig._load_matrix_config()` — reads `system_config.yml`
- `MatrixConfig._load_email_proxy_config()` — reads `email_proxy_config.yml`
- `MatrixConfig._load_llm_config()` — reads `llm_config.json`

## Config File Layout

After cold start, the `.matrix/configs/` directory contains:

```
.matrix/configs/
├── agents/
│   ├── User.yml                    # User agent profile
│   └── SystemAdmin.yml             # System admin agent profile
├── llm_config.json                 # LLM API configurations
├── system_config.yml               # System settings (user_agent_name, etc.)
├── email_proxy_config.yml          # Email proxy settings
└── backups/                        # (created on first config change)
```

Each config file is independent. Modifying one never affects others.

## The Flow in Detail

```
1. submitWizard() calls:
   a. init_matrix_world(path, name)     → creates dirs + templates + replaces {{USER_NAME}}
   b. save_llm_config(path, llmConfig)  → writes llm_config.json to .matrix/configs/
   c. save_email_proxy_config_cmd()     → writes email_proxy_config.yml (if email enabled)

2. submitWizard() then calls:
   a. start_backend()                   → spawns python server.py
   b. health check (poll localhost:8000)
   c. POST /api/config/init {path}      → backend reads files, starts runtime
   d. mark_configured(path)             → persists to ~/.agentmatrix/settings.json

3. App switches to main view
```

## Why This Order?

- Files must exist before backend starts. The backend's `init_runtime()` reads files immediately.
- Tauri commands are synchronous file ops — fast, no network.
- Backend is only needed for the AgentMatrix runtime (LLM calls, agent orchestration).

## After Cold Start

Once the system is running, all configuration management goes through **ConfigService** (accessed by the **SystemAdmin Agent** via skill actions). See [LLM-Managed Config](../../core/llm-managed-config.md) for the full design.
