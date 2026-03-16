# AgentMatrix Desktop - Quick Start Guide

**Vue 3 + Vite + Pinia + Tailwind CSS**

---

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Python 3.10+
- AgentMatrix backend running on port 8000

### Installation

```bash
# 1. Navigate to the desktop app directory
cd agentmatrix-desktop

# 2. Install dependencies
npm install

# 3. Start development server
npm run dev
```

**Access**: http://localhost:5173

---

## 📦 Project Structure

```
agentmatrix-desktop/
├── src/
│   ├── components/          # Vue components
│   │   ├── conversation/    # Conversation list
│   │   ├── message/         # Message display
│   │   ├── dialog/          # Modal dialogs
│   │   └── settings/        # Settings panel
│   ├── composables/         # Reusable logic
│   ├── stores/              # Pinia stores
│   ├── api/                 # API clients
│   ├── utils/               # Utility functions
│   ├── App.vue              # Root component
│   └── main.js              # Entry point
├── index.html               # HTML template
├── vite.config.js           # Vite configuration
├── tailwind.config.js       # Tailwind configuration
└── package.json             # Dependencies
```

---

## 🎯 Key Features

### ✅ Implemented
- **Conversation Management**: View, search, and switch between conversations
- **Email Operations**: Send, reply, copy, and delete emails
- **Real-time Updates**: WebSocket integration for instant notifications
- **Settings Panel**: Manage LLM configurations with full CRUD
- **Attachment Support**: Send and receive file attachments
- **Markdown Rendering**: Beautiful formatted messages
- **Responsive Design**: Works on desktop and tablet

---

## 🔧 Configuration

### Vite Proxy
The development server proxies API requests to the backend:

```javascript
// vite.config.js
server: {
  proxy: {
    '/api': 'http://localhost:8000',
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true,
    },
  },
}
```

### Tailwind CSS
Customize styles in `tailwind.config.js`:

```javascript
theme: {
  extend: {
    colors: {
      primary: { /* ... */ },
      surface: { /* ... */ },
    },
  },
}
```

---

## 📚 Component API

### ConversationList
```vue
<ConversationList />
```
**Features**: Session list, search, pagination, new conversation

### MessageList
```vue
<MessageList :user_agent_name="'DKT'" />
```
**Props**:
- `user_agent_name`: Display name for user messages

**Features**: Message display, reply input, real-time updates

### SettingsPanel
```vue
<SettingsPanel />
```
**Features**: LLM config CRUD, beautiful card UI

### NewEmailModal
```vue
<NewEmailModal
  :show="showModal"
  @close="showModal = false"
  @sent="handleEmailSent"
/>
```
**Props**:
- `show`: Boolean to control visibility

**Events**:
- `@close`: Fired when modal is closed
- `@sent`: Fired when email is sent successfully

---

## 🗂️ Pinia Stores

### sessionStore
```javascript
import { useSessionStore } from '@/stores/session'

const sessionStore = useSessionStore()
await sessionStore.loadSessions()
await sessionStore.selectSession(session)
```

### emailStore
```javascript
import { useEmailStore } from '@/stores/email'

const emailStore = useEmailStore()
await emailStore.loadEmails(sessionId)
await emailStore.sendEmail(sessionId, emailData, files)
```

### uiStore
```javascript
import { useUIStore } from '@/stores/ui'

const uiStore = useUIStore()
uiStore.showNotification('Message sent', 'success')
uiStore.openModal('newEmail')
```

---

## 🔌 WebSocket Integration

The app automatically connects to WebSocket on mount:

```javascript
// In App.vue
onMounted(() => {
  connect()  // Connect to WebSocket
  onMessage((data) => {
    websocketStore.handle_message(data)
  })
})
```

### WebSocket Events
- `new_email`: New email received
- `runtime_event`: Runtime status update

---

## 🎨 Styling

### Tailwind CSS Classes
```vue
<!-- Button -->
<button class="px-4 py-2 bg-primary-600 text-white rounded-xl hover:bg-primary-700">
  Click me
</button>

<!-- Card -->
<div class="bg-white rounded-xl shadow-card p-4">
  Content
</div>
```

### Custom CSS
Use scoped styles in `.vue` files:

```vue
<style scoped>
.my-component {
  /* Custom styles */
}
</style>
```

---

## 🧪 Development

### Hot Module Replacement
Vite provides instant HMR. Save a file and see changes immediately!

### Build for Production
```bash
npm run build
```

Output in `dist/` directory.

### Preview Production Build
```bash
npm run preview
```

---

## 🐛 Debugging

### Console Logs
The app includes helpful console logs:
- `📧` - Email operations
- `🔄` - Session operations
- `🔌` - WebSocket connection
- `✅` - Success operations
- `❌` - Error operations

### Vue DevTools
Install [Vue DevTools](https://devtools.vuejs.org/) for debugging:
- Inspect component hierarchy
- View Pinia store state
- Track events and performance

---

## 📝 Common Tasks

### Add a New Component
```bash
# Create component file
touch src/components/my-component/MyComponent.vue
```

```vue
<script setup>
import { ref } from 'vue'

const message = ref('Hello World')
</script>

<template>
  <div>{{ message }}</div>
</template>

<style scoped>
/* Component styles */
</style>
```

### Add a New Store
```bash
# Create store file
touch src/stores/myStore.js
```

```javascript
import { defineStore } from 'pinia'

export const useMyStore = defineStore('myStore', {
  state: () => ({
    data: null,
  }),

  actions: {
    async loadData() {
      // Load data
    },
  },
})
```

### Add API Endpoint
```bash
# Create API file
touch src/api/myApi.js
```

```javascript
import { API } from './client'

export const myAPI = {
  async getData() {
    return API.get('/api/my-endpoint')
  },
}
```

---

## 🚨 Troubleshooting

### Issue: API calls failing
**Solution**: Ensure backend is running on port 8000

```bash
# Start backend
cd /Users/dkt/myprojects/agentmatrix
python server.py
```

### Issue: WebSocket not connecting
**Solution**: Check WebSocket proxy configuration in `vite.config.js`

### Issue: Styles not applying
**Solution**: Ensure Tailwind CSS is properly configured

```bash
# Rebuild Tailwind
npm run build
```

### Issue: Components not rendering
**Solution**: Check Vue DevTools for errors in console

---

## 📖 Resources

- [Vue 3 Documentation](https://vuejs.org/)
- [Vite Documentation](https://vitejs.dev/)
- [Pinia Documentation](https://pinia.vuejs.org/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [Tabler Icons](https://icones.js.org/collection/tabler)

---

## 🎉 Next Steps

1. **Explore the app**: Click around and try the features
2. **Customize**: Modify components and styles to your liking
3. **Add features**: Implement new functionality using the established patterns
4. **Deploy**: Build for production and deploy to your server

---

**Happy Coding! 🚀**

For detailed implementation docs, see: [docs/vue3-migration-implementation-complete.md](../docs/vue3-migration-implementation-complete.md)
