# LLM-Managed Configuration: A New Design Pattern

## The Core Idea

Traditional software uses configuration files that humans edit directly, or GUI forms that write to those files. AgentMatrix introduces a third approach:

**An LLM Agent manages configuration on behalf of the user, through natural language conversation.**

The user says "set up email for Gmail" — the Agent figures out the right config, validates it, tests the connection, and writes it. The user never sees a YAML file.

This is not just "an AI assistant that helps you edit config." It's a clean separation of concerns:

```
User ←→ SystemAdmin Agent (LLM) ←→ ConfigService ←→ Config Files
     natural language         structured API         YAML/JSON
```

Each layer has a specific job. The Agent handles ambiguity and intent. ConfigService handles validation and file operations. Neither can do the other's job.

---

## Why This Works

### 1. LLMs are good at YAML/JSON

Large language models were trained on massive amounts of structured data. They can read, understand, modify, and generate YAML and JSON fluently. This means we can give the Agent raw config content and trust it to make correct modifications.

### 2. Deterministic validation is still needed

LLMs are not reliable validators. They might accept invalid configs, hallucinate field names, or miss subtle errors. So ConfigService provides **deterministic, schema-based validation** using Pydantic. The Agent proposes changes; ConfigService approves or rejects them with specific, structured error messages.

### 3. Verification goes beyond syntax

A config can be syntactically valid but functionally broken — wrong password, unreachable server, incompatible model. ConfigService runs **connection tests** (SMTP, IMAP, LLM API) before writing. If the test fails, the config is never written, and the Agent gets a clear error message to act on.

### 4. Content-first API simplifies the Agent's job

Instead of giving the Agent 15 typed parameters for email configuration (and watching it struggle with the exact parameter names), we give it a simpler mental model:

```
1. read_config("email_proxy")  → get current YAML
2. Think about what to change
3. write_config("email_proxy", modified_yaml)  → validate + test + write
```

The Agent works with **content**, not parameters. This is more natural for an LLM and reduces the surface area for errors.

---

## Architecture

### The Three Layers

```
┌─────────────────────────────────────────────┐
│  SystemAdmin Agent                          │
│  - Understands user intent in natural lang  │
│  - Reads/writes config via skill actions    │
│  - Handles errors, retries, asks questions  │
│  - Never touches files directly             │
└──────────────────┬──────────────────────────┘
                   │ skill actions (10 methods)
┌──────────────────▼──────────────────────────┐
│  ConfigService                              │
│  - Content-first API (read/write/validate)  │
│  - Pydantic schema validation               │
│  - Connection verification tests            │
│  - Auto backup + cleanup                    │
│  - Structured error messages                │
└──────────────────┬──────────────────────────┘
                   │ file I/O
┌──────────────────▼──────────────────────────┐
│  Config Files (split, independent)          │
│  - system_config.yml                        │
│  - email_proxy_config.yml                   │
│  - llm_config.json                          │
│  - agents/{name}.yml                        │
└─────────────────────────────────────────────┘
```

### Config File Structure

Each concern has its own file. This means reading or writing one config never risks corrupting another:

```
.matrix/configs/
├── agents/                    # Agent profiles
│   ├── User.yml
│   └── SystemAdmin.yml
├── llm_config.json            # LLM API endpoints
├── system_config.yml          # System-level settings
├── email_proxy_config.yml     # Email configuration
└── backups/
    ├── agents/                # Agent backups (separate dir)
    │   └── SystemAdmin_20260324_120000.yml
    ├── system_config_20260324_120000.yml
    ├── email_proxy_config_20260324_120000.yml
    └── llm_config_20260324_120000.json
```

---

## How It Works: A Walkthrough

### Scenario: User wants to configure email

**User:** "Set up my email. I use Gmail. My address is alice@gmail.com and I have an app password abc123."

**SystemAdmin Agent:**

```
[THOUGHTS]
The user wants to configure email proxy. I need to:
1. Get the current email config to understand the structure
2. Build a complete config with Gmail SMTP/IMAP settings
3. Write it - ConfigService will test the connection before saving

[ACTION]
read_config(config_type="email_proxy")
```

**ConfigService returns:**
```yaml
enabled: false
matrix_mailbox: ""
user_mailbox: ""
smtp:
  host: "smtp.gmail.com"
  port: 587
  user: ""
  password: ""
imap:
  host: "imap.gmail.com"
  port: 993
  user: ""
  password: ""
```

**Agent continues:**
```
[THOUGHTS]
Good, I can see the structure. Now I'll fill in the user's info.
Gmail SMTP: smtp.gmail.com:587, IMAP: imap.gmail.com:993
The matrix_mailbox should be a system mailbox, not the user's.
I'll set user_mailbox to alice@gmail.com.

[ACTION]
write_config(
  config_type="email_proxy",
  content="enabled: true\nmatrix_mailbox: matrix@gmail.com\nuser_mailbox: alice@gmail.com\n...",
  skip_verification=false
)
```

**ConfigService runs:**
1. Parse YAML ✓
2. Pydantic validation ✓
3. SMTP connection test: `smtp.gmail.com:587` with `alice@gmail.com:abc123` → ✅ Connected
4. IMAP connection test: `imap.gmail.com:993` with `alice@gmail.com:abc123` → ✅ Connected
5. Backup old file → `backups/email_proxy_config_20260324_143000.yml`
6. Write new file

**Returns to Agent:**
```
✅ Config 'email_proxy' written successfully
📦 Backup: .matrix/configs/backups/email_proxy_config_20260324_143000.yml
📄 File: .matrix/configs/email_proxy_config.yml

Verification results:
  ✅ smtp_connection: Connected to smtp.gmail.com:587 as alice@gmail.com
  ✅ imap_connection: Connected to imap.gmail.com:993 as alice@gmail.com
```

**Agent reports to user:** "Done! Email is configured and both sending and receiving connections tested successfully."

### What if the password was wrong?

**ConfigService would return:**
```
❌ Verification tests failed
  ✅ smtp_connection: Connected
  ❌ imap_connection: Authentication failed for alice@gmail.com. Check user/password.

💡 Hint: Gmail app passwords are 16 characters without spaces. Generate one at
   https://myaccount.google.com/apppasswords
```

The Agent can then ask the user to recheck the password, or try with just SMTP enabled.

---

## The Skill Actions

The SystemAdmin Agent has exactly 10 actions. This is intentional — fewer actions mean the Agent is less likely to pick the wrong one.

### Discovery

| Action | Purpose |
|--------|---------|
| `list_config_types` | "What can I configure?" → returns `["agent", "llm", "system", "email_proxy"]` |
| `get_config_schema` | "What does a valid X look like?" → returns JSON Schema |

### Read & Write

| Action | Purpose |
|--------|---------|
| `read_config` | "Show me the current X config" → returns raw YAML/JSON |
| `write_config` | "Here's the new X config" → validate → test → backup → write |
| `validate_config` | "Is this config valid?" → check without writing |

### Backup

| Action | Purpose |
|--------|---------|
| `list_backups` | "What backups exist for X?" → returns timestamped list |
| `read_backup` | "Show me backup Y" → returns backup content |

### Agent Lifecycle

| Action | Purpose |
|--------|---------|
| `list_agents` | "What agents are running?" → returns agent list with status |
| `reload_agent` | "Reload agent X from its config file" |
| `delete_agent` | "Remove agent X" |

---

## Design Decisions

### Why content-first, not parameter-based?

The old matrix_admin skill had actions like `config_email_proxy(enabled, matrix_mailbox, user_mailbox, smtp_host, smtp_port, smtp_user, smtp_password, imap_host, imap_port, imap_user, imap_password)` — 11 parameters. The Agent had to remember the exact parameter names and provide all of them correctly.

With content-first:
- The Agent reads the current config → sees the exact structure
- Modifies what needs changing → using its natural language understanding
- Provides the full content → ConfigService validates everything at once

This is more robust because:
1. The Agent doesn't need to memorize parameter names
2. Validation happens holistically, not field-by-field
3. The Agent can see the full context of what it's changing
4. Error messages point to specific fields in the content the Agent just provided

### Why split config files?

When everything was in one `matrix_config.yml`, modifying email proxy meant reading the entire file, modifying one section, and writing it back. This risked corrupting other sections (e.g., if the Agent's YAML generation had a formatting issue).

With split files:
- Each config is self-contained
- Reading/writing one config doesn't touch others
- Backup files have short, clear names
- The Agent can reason about one concern at a time

### Why verification before write?

A config that passes schema validation can still fail in practice (wrong password, unreachable server, unsupported model). By testing connections before writing, we:
1. Prevent the user from having a "valid but broken" config
2. Give the Agent immediate feedback to act on
3. Keep the config files always in a working state

The `skip_verification` parameter exists for cases where you know the config is correct but can't test right now (e.g., network is down, or setting up for later).

### Why automatic backup?

The SystemAdmin Agent's persona instructs it to always backup before changes. But humans make mistakes, and LLMs can too. Automatic backup at the ConfigService level means:
1. Every write is backed up, even if the Agent forgets
2. The backup happens atomically before the write
3. Old backups are automatically cleaned up (keep last 5)
4. The Agent (or user) can always recover from a bad change

---

## Contrast with Traditional Approaches

### vs. GUI Config Forms

| Aspect | GUI Form | LLM-Managed Config |
|--------|----------|-------------------|
| User experience | Click through fields | Natural conversation |
| Validation | Client-side only | Schema + connection tests |
| Flexibility | Fixed fields | Can handle any config |
| Discoverability | Tooltips | Agent explains in context |
| Error handling | Generic messages | Structured, actionable errors |

### vs. CLI/Terraform

| Aspect | CLI/Terraform | LLM-Managed Config |
|--------|--------------|-------------------|
| User needs | Know exact syntax | Natural language |
| Learning curve | Read docs | Ask the Agent |
| Idempotency | Manual planning | Agent plans step-by-step |
| Dry run | Separate command | Built-in validate_config |

### vs. Direct File Editing

| Aspect | Direct Edit | LLM-Managed Config |
|--------|------------|-------------------|
| Error risk | High (typos, format) | Validated before write |
| Backup | Manual | Automatic |
| Connection test | Manual | Automatic |
| History | git (if set up) | Built-in backup list |

---

## Implementation Notes

### Pydantic Schemas

Each config type has a Pydantic model that defines:
- Required vs optional fields
- Field types and constraints
- Cross-field validation (e.g., "if enabled, then smtp and imap are required")
- Human-readable descriptions for each field

The same model is used for:
1. Runtime validation when writing
2. JSON Schema generation for Agent discovery
3. Type-safe access in Python code

### Structured Error Messages

ConfigService returns errors as structured objects, not strings:
```python
ConfigError(
    field="skills[2]",
    value="nonexistent_skill",
    issue="Skill not found in registry",
    suggestion="Available skills: base, email, file, browser, ..."
)
```

The Agent formats these into readable text for the user, but the structure allows programmatic handling too.

### Backup Convention

Backups use the pattern `{config_file_stem}_{YYYYMMDD_HHMMSS}{suffix}`:
- `system_config_20260324_120000.yml`
- `email_proxy_config_20260324_120000.yml`
- `llm_config_20260324_120000.json`
- `SystemAdmin_20260324_120000.yml` (in backups/agents/)

This makes backups:
- Sortable by name (chronological order)
- Easy to identify which config and when
- Simple to glob/filter
- Short paths (no nested directories except agents/)

---

## Cold Start (First-Run Wizard)

The desktop app uses a wizard for initial setup. The wizard's file operations mirror the ConfigService approach:

1. `init_matrix_world` — copies template directory with placeholder files
2. `save_llm_config` — writes `llm_config.json` to `.matrix/configs/`
3. `save_email_proxy_config_cmd` — writes `email_proxy_config.yml` to `.matrix/configs/`

The template provides the initial structure. After cold start, all config management goes through ConfigService (via the SystemAdmin Agent or direct API).

---

## Summary

LLM-Managed Configuration is a pattern where:

1. **The Agent handles intent** — translating natural language into config changes
2. **ConfigService handles correctness** — schema validation, connection tests, backups
3. **Config files are split** — one concern per file, no cross-contamination
4. **The API is content-first** — Agent works with YAML/JSON strings, not typed parameters
5. **Errors are structured** — Agent can understand and act on them programmatically

This pattern could be applied to any system where configuration is complex enough to benefit from an LLM assistant, but correctness is important enough to require deterministic validation.
