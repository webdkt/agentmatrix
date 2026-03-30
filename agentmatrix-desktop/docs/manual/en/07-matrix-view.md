# Matrix View

The Matrix View is the agent monitoring dashboard — a real-time view of all agents running in your Matrix World.

## Accessing the Matrix View

Click the **Matrix** icon in the View Selector (left rail) to switch to the Matrix View.

## Agent List

The left panel shows a list of all configured agents with their current status:

| Status | Description |
|--------|-------------|
| **Running** | Agent is actively processing tasks |
| **Idle** | Agent is online but not processing |
| **Stopped** | Agent is not running |
| **Starting** | Agent is initializing |
| **Stopping** | Agent is shutting down |

Each agent entry shows:

- **Agent name** — The configured name
- **Status indicator** — A color-coded dot showing current state
- **Last activity** — When the agent last processed a task

Use the search bar to filter agents by name.

## Agent Dashboard

Select an agent from the list to view its dashboard. The dashboard has multiple tabs:

### Profile Tab

Shows the agent's configuration:

- **Name** — Agent identifier
- **Description** — What the agent does
- **Class** — The agent type
- **Skills** — List of capabilities
- **Backend Model** — Which LLM/SLM the agent uses
- **Persona** — The agent's role definition (preview)

### Resources Tab

Shows what the agent has access to:

- **Browser** — Web browsing capability
- **Computer** — System command access
- **Home Folder** — The agent's working directory
- **Session Folder** — Session-specific data directory
- **Skills Folder** — Available skill modules

### Log Tab

A real-time log viewer showing:

- Agent thought processes
- Action executions
- Tool invocations
- Error messages
- System events

Logs update in real-time as the agent works.

### Memory Tab

Shows the agent's memory state — information it has accumulated and retained across tasks.

## Agent Operations

From the Agent Dashboard, you can perform the following operations on an agent:

| Action | Description |
|--------|-------------|
| **View Prompt** | View the agent's full system prompt |
| **Stop** | Stop the agent (terminates current task) |
| **Pause** | Pause the agent (suspends processing) |
| **Resume** | Resume a paused agent |
| **Reload** | Reload the agent's configuration |
| **Clone** | Create a copy of the agent with a new name |
| **Mail To** | Compose a new email to this agent |

## Session History

The dashboard also shows the agent's session history — a list of all sessions the agent has participated in, with timestamps and status.
