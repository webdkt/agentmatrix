# Architecture

## Responsibility Split

The cold start wizard separates concerns across three layers:

### Tauri (Rust) — File System Operations

Handles all file creation. No backend needed.

- `init_matrix_world` — copies template directory, replaces `{{USER_NAME}}` in `User.yml` and `matrix_config.yml`
- `save_llm_config` — writes `llm_config.json` with API keys
- `save_email_proxy_config_cmd` — updates `email_proxy` section in `matrix_config.yml`

### Frontend (Vue) — User Interaction

Collects input, orchestrates the flow.

- `ColdStartWizard.vue` — step management, validation, Enter/click navigation
- `ModelSelector.vue` — model search with pattern matching (GPT→OpenAI, etc.)
- `submitWizard()` in store — calls Tauri commands, then starts backend

### Backend (Python) — Runtime Only

Does NOT create files. Only reads existing files and starts the runtime.

- `/api/config/init` — receives `matrix_world_path`, calls `init_runtime()`
- `MatrixConfig._load_matrix_config()` — reads `matrix_config.yml`
- `MatrixConfig._load_email_proxy_config()` — reads `email_proxy` from `matrix_config.yml`

## The Flow in Detail

```
1. submitWizard() calls:
   a. init_matrix_world(path, name)     → creates dirs + templates + replaces placeholders
   b. save_llm_config(path, llmConfig)  → writes llm_config.json
   c. save_email_proxy_config_cmd()     → updates matrix_config.yml (if email enabled)

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
