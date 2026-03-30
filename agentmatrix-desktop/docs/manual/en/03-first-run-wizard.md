# First-Run Wizard

When you launch AgentMatrix Desktop for the first time, a guided setup wizard walks you through the essential configuration. The wizard features a Matrix-rain animated background and consists of six steps.

## Step 1: Welcome

The welcome screen introduces AgentMatrix Desktop. Click **Begin** to start the setup process.

## Step 2: Your Name

Enter your display name. This name is used throughout the system to identify you as the user — in sessions, emails, and agent interactions.

- Use a meaningful name (e.g., your real name or a consistent alias)
- This can be changed later by editing the system configuration file

## Step 3: Workspace Directory

Select a directory on your computer to serve as the **Matrix World** — the workspace where all agent data, configurations, and files will be stored.

- Click the directory selector to browse and choose a folder
- The default suggestion is `~/MatrixWorld`
- The directory will be created automatically if it doesn't exist
- A `.matrix/configs/` subdirectory will be created inside with all configuration templates

**Important**: Choose a directory with sufficient disk space. Agent files, logs, and browser data will accumulate over time.

## Step 4: Brain (Large Language Model)

Configure the primary AI model that powers your agents' reasoning. This is the "brain" — a powerful model used for complex thinking and decision-making.

Select from the available providers:

| Provider | Recommended Models |
|----------|--------------------|
| **Anthropic** | Claude Sonnet 4, Claude Haiku 4 |
| **OpenAI** | GPT-4o, GPT-4o Mini, o1, o3 |
| **DeepSeek** | DeepSeek Chat, DeepSeek Coder |
| **Google** | Gemini 2.0 Flash, Gemini 1.5 Pro |
| **Xiaomi** | MiMo v2 Pro, MiMo v2 Flash |
| **Custom** | Any OpenAI-compatible API endpoint |

For each provider, you need to supply:

- **API Key** — Your provider API key (kept locally, never shared)
- **Model Name** — The specific model to use
- **API URL** — Auto-filled for known providers, manually entered for custom endpoints

## Step 5: Cerebellum (Small Language Model)

Configure a smaller, faster model for lightweight tasks such as email parsing, simple classifications, and quick responses. This frees up the main model for complex reasoning.

- The same provider selection applies
- Choose a smaller/faster model (e.g., GPT-4o Mini, Claude Haiku, Gemini Flash)
- Can use the same provider as the Brain or a different one

## Step 6: Review & Launch

Review all your settings before launching:

- **User Name** — Your chosen display name
- **Data Directory** — Your Matrix World workspace path
- **Large Model** — Provider and model for the Brain
- **Small Model** — Provider and model for the Cerebellum

You can also optionally configure **Email Proxy** settings:

- **Enable Email Proxy** — Toggle to connect AgentMatrix to a real email account
- **Matrix Mailbox** — The email address for the Matrix system
- **User Mailbox** — Your personal email address
- **IMAP Settings** — Incoming mail server (host, port)
- **SMTP Settings** — Outgoing mail server (host, port)

Click **Launch** to initialize your Matrix World. The wizard will:

1. Create the workspace directory
2. Copy configuration templates
3. Save your LLM configuration
4. Start the Python backend
5. Transition to the main application

## Re-running the Wizard

The wizard appears automatically when:

- The settings file (`~/.agentmatrix/settings.json`) does not exist
- The configured workspace directory does not exist
- The LLM configuration file is missing

To force the wizard during development:

```bash
./start-dev.sh --force-wizard
```
