# Internationalization

AgentMatrix Desktop supports multiple languages for its user interface.

## Supported Languages

| Language | Code | Status |
|----------|------|--------|
| **Chinese (Simplified)** | zh | Default |
| **English** | en | Fully supported |

## Switching Languages

The application defaults to Chinese. To switch to English:

1. Open the application
2. Navigate to the Settings panel (gear icon in the View Selector)
3. Look for the language setting in the appearance or general settings
4. Select your preferred language
5. The interface updates immediately

## What Gets Translated

The language setting affects:

- All UI labels, buttons, and menus
- Status messages and notifications
- Error messages
- Wizard steps and descriptions
- Settings panel labels

## What Stays the Same

The following are not affected by the language setting:

- Agent persona text (as defined in configuration files)
- Email content (user-written and agent-generated)
- Configuration file contents
- Log messages from the backend

## Adding a New Language

If you want to contribute a translation, the locale files are located at:

- `src/i18n/locales/en.json` — English
- `src/i18n/locales/zh.json` — Chinese

Each file contains key-value pairs organized by UI section (views, emails, settings, etc.).
