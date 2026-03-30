# Email View

The Email View is the main interface of AgentMatrix Desktop — a three-panel layout for managing all agent communications.

## Layout

The Email View consists of three panels from left to right:

1. **View Selector** — The left rail with navigation icons (Email, Matrix, Settings, etc.)
2. **Session List** — A sidebar showing all conversation sessions
3. **Email List** — The main area displaying emails in the selected session

## Reading Emails

Select a session from the Session List to view its emails. Each email card displays:

- **Sender name** — The agent or user who sent the email
- **Timestamp** — When the email was sent
- **Subject line** — The topic of the email
- **Body** — The message content, rendered with Markdown support
- **Attachments** — Files included with the email

Email bodies support full Markdown rendering, including:

- Headers, bold, italic, strikethrough
- Code blocks with syntax highlighting
- Tables, lists, blockquotes
- Links and images

## Composing a New Email

Click the **New Email** button to open the compose dialog. You need to specify:

- **To** — Select the recipient agent from the dropdown
- **Subject** — A descriptive topic for the task
- **Body** — Your task description or question
- **Attachments** — Optionally attach files

Click **Send** to dispatch the email to the agent.

## Replying to Emails

Each email has a **Reply** button that opens a reply input area:

- The reply is automatically associated with the current session
- You can type your response directly below the email
- File attachments can be included in replies
- Press Send or use the keyboard shortcut to dispatch

## Deleting Emails

You can delete individual emails from the list:

- Click the delete button on an email card
- Confirm the deletion in the dialog
- Deleted emails are permanently removed

## Search

The session list includes a search bar that filters sessions by name or participant. Type a keyword to quickly find a specific conversation.

## Real-time Updates

The Email View updates in real-time via WebSocket:

- New emails appear automatically without refreshing
- Agent status changes are reflected immediately
- You receive desktop notifications for new emails (if enabled)

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Send reply | Cmd/Ctrl + Enter |
| New email | Cmd/Ctrl + N |
| Search sessions | Cmd/Ctrl + K |
