# Settings

The Settings panel allows you to configure AgentMatrix without editing files directly. Access it by clicking the **Settings** icon in the View Selector.

## Settings Layout

The Settings panel has a two-column layout:

- **Left sidebar** — Category navigation (LLM Configuration, Email Proxy)
- **Right content area** — Configuration interface for the selected category

## LLM Configuration

The LLM Configuration section manages the AI models used by your agents.

### Required Configurations

Three LLM configurations are required and cannot be deleted:

| Config Name | Purpose |
|-------------|---------|
| **default_llm** | Primary language model for main agent reasoning (the "Brain") |
| **default_slm** | Small language model for simple tasks (the "Cerebellum") |
| **browser-use-llm** | Language model specifically for browser automation tasks |

### Custom Configurations

You can add custom LLM configurations for specialized use cases:

- Click **Add New** to create a custom configuration
- Custom configs can be edited and deleted freely

### Configuration Fields

Each LLM configuration requires:

| Field | Description |
|-------|-------------|
| **Config Name** | Unique identifier (e.g., "default_llm") |
| **Description** | Human-readable purpose description |
| **Model Name** | The model identifier (e.g., "gpt-4o", "claude-sonnet-4-20250514") |
| **API Key** | Your provider API key (stored locally) |
| **API Base URL** | The API endpoint URL |

### Quick-Select Common Models

The configuration form includes a quick-select panel with common models:

- GPT-4, GPT-3.5 Turbo
- Claude 3 Opus, Claude 3 Sonnet
- Gemini Pro

Selecting a model auto-fills the model name and API URL.

### Editing and Deleting

- Click the **Edit** button on any configuration card to modify it
- Click the **Delete** button on custom configurations to remove them
- Required configurations show a **Required** badge and cannot be deleted
- A confirmation dialog appears before deletion

## Email Proxy Configuration

The Email Proxy section manages the connection between AgentMatrix and a real email account.

### Enable / Disable

Toggle the Email Proxy on or off:

- When **enabled**, AgentMatrix can send and receive emails through your real email account
- When **disabled**, all email communication stays internal to AgentMatrix

### Configuration Fields

| Field | Description |
|-------|-------------|
| **Email Address** | Your email address |
| **IMAP Host** | Incoming mail server hostname (e.g., imap.gmail.com) |
| **IMAP Port** | Incoming mail server port (typically 993) |
| **IMAP Username** | Login username for IMAP |
| **IMAP Password** | Login password or app password for IMAP |
| **SMTP Host** | Outgoing mail server hostname (e.g., smtp.gmail.com) |
| **SMTP Port** | Outgoing mail server port (typically 587) |
| **SMTP Username** | Login username for SMTP |
| **SMTP Password** | Login password or app password for SMTP |

### Common Email Provider Settings

| Provider | IMAP Host | IMAP Port | SMTP Host | SMTP Port |
|----------|-----------|-----------|-----------|-----------|
| **Gmail** | imap.gmail.com | 993 | smtp.gmail.com | 587 |
| **Outlook** | outlook.office365.com | 993 | smtp.office365.com | 587 |
| **QQ Mail** | imap.qq.com | 993 | smtp.qq.com | 465 |
| **163 Mail** | imap.163.com | 993 | smtp.163.com | 465 |

**Note**: For Gmail, you need to use an [App Password](https://support.google.com/accounts/answer/185833) instead of your regular password.

### Test Connection

After configuring the Email Proxy, click **Test Connection** to verify that AgentMatrix can connect to both IMAP and SMTP servers.

### Copy to SMTP

The configuration form includes a **Copy to SMTP** button that duplicates your IMAP settings to the SMTP fields — useful when your provider uses the same credentials for both.

## Saving Changes

Changes to LLM configurations and Email Proxy settings are saved to the Matrix World configuration files. The application may prompt you to restart the backend after significant changes.
