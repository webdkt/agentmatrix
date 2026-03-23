# Cold Start Wizard

First-run experience when the app has no configuration. The wizard collects user input, creates the directory structure, writes config files, then starts the backend.

## Flow

```
User opens app
  ↓
is_first_run? (settings.json check)
  ↓ yes
Wizard launches (full screen, no sidebar)
  ↓
1. Welcome (typewriter animation)
2. Name
3. Workspace directory
4. Brain (LLM model + API key)
5. Cerebellum (pre-filled from Brain, editable)
6. Initialize Matrix
  ↓
Tauri creates files (no backend needed yet)
  ↓
Backend starts → reads existing files → runtime ready
  ↓
Main app launches
```

## Key Design Decisions

- **Wizard before backend**: All file creation happens via Tauri commands. The backend only starts after files are ready.
- **Single config file**: `matrix_config.yml` holds everything (user name, container settings, email proxy). No `system_config.yml`.
- **Template with placeholders**: `{{USER_NAME}}` in template files gets replaced at copy time.
- **Cerebellum pre-filled**: Step 5 copies Brain's values. User can modify. No "same as brain" checkbox.

## Files

| Layer | File | Purpose |
|-------|------|---------|
| UI | `ColdStartWizard.vue` | Step orchestration, rain, typewriter |
| UI | `ModelSelector.vue` | Search/type model combobox |
| UI | `StepLLM.vue` | Brain/Cerebellum form |
| UI | `StepUserName.vue` | Name input |
| UI | `StepDirectory.vue` | Directory picker |
| Store | `stores/config.js` | `submitWizard()` — calls Tauri + backend |
| API | `api/config.js` | `initRuntime()` — backend init endpoint |
| Tauri | `src-tauri/src/main.rs` | `init_matrix_world`, `save_llm_config`, `save_email_proxy_config_cmd` |
| Template | `src-tauri/resources/matrix-template/` | Directory structure + config templates |
| Backend | `server.py` | `/api/config/init` — reads files, starts runtime |
| Runtime | `core/config.py` | `_load_matrix_config()`, `_load_email_proxy_config()` |
| Runtime | `core/paths.py` | Path definitions (`MatrixPaths`) |

## Config File Structure

```
.matrix/configs/
  matrix_config.yml          ← user_agent_name + container + email_proxy
  agents/
    User.yml                 ← agent config (name from template placeholder)
    SystemAdmin.yml          ← system admin agent
    llm_config.json          ← LLM/SLM API keys and URLs
```

## Where to Make Changes

- **Add a wizard step**: Edit `ColdStartWizard.vue` (template + STEPS array + validation)
- **Add a model provider**: Edit `src/assets/llm-presets.json`
- **Change template files**: Edit `src-tauri/resources/matrix-template/`
- **Change what files are created**: Edit Tauri commands in `main.rs`
- **Change how runtime loads config**: Edit `core/config.py`
