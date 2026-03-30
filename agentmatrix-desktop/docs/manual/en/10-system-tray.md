# System Tray & Notifications

AgentMatrix Desktop runs with a system tray icon that provides quick access and background operation.

## System Tray Icon

When AgentMatrix Desktop is running, a tray icon appears in your system's menu bar (macOS) or taskbar notification area (Windows/Linux).

### Tray Menu

Right-click (or click on macOS) the tray icon to access:

| Action | Description |
|--------|-------------|
| **Open AgentMatrix** | Show and focus the application window |
| **Quit** | Close the application completely |

Clicking the tray icon directly will show/hide the application window.

## Window Behavior

- **Close button** — Minimizes to tray (does not quit the app)
- **Tray click** — Toggles window visibility
- **Quit from tray** — Fully exits the application

## Desktop Notifications

AgentMatrix Desktop can show native desktop notifications for important events:

- **New email received** — When an agent sends you a response
- **Agent status changes** — When an agent starts, stops, or encounters an error
- **Backend status** — When the Python backend starts or stops

### Enabling / Disabling Notifications

Notifications can be controlled via the application settings:

- Set `enable_notifications` to `true` or `false` in `~/.agentmatrix/settings.json`
- The default is `true` (notifications enabled)

On first launch, your system may prompt you to grant notification permissions to AgentMatrix.

### Notification Fallback

If native notifications are not available (e.g., permission denied), AgentMatrix falls back to browser-style in-app notifications.
