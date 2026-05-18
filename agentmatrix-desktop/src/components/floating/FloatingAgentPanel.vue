<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { emit } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import { sessionAPI } from '@/api/session'
import ChatMessage from '@/components/collab/ChatMessage.vue'
import MIcon from '@/components/icons/MIcon.vue'

// ---- Parse session info from URL hash ----
function parseParams() {
  const hash = window.location.hash.slice(1) // remove #
  const params = {}
  hash.split('&').forEach(pair => {
    const [key, val] = pair.split('=')
    if (key && val) params[decodeURIComponent(key)] = decodeURIComponent(val)
  })
  return params
}

const params = parseParams()
const sessionId = ref(params.sessionId || null)
const agentName = ref(params.agentName || null)
const agentSessionId = ref(params.agentSessionId || null)
const agentStatus = ref('IDLE')
const isCollapsed = ref(false)
const isSending = ref(false)
const isLoading = ref(false)
const inputText = ref('')
const messagesContainer = ref(null)

console.log('[Floating] params:', params)

// ---- Messages ----
const messages = ref([])

// ---- Parse event (same logic as useChatTimeline) ----
function parseEvent(raw) {
  let detail = {}
  if (raw.event_detail) {
    try {
      detail = typeof raw.event_detail === 'string' ? JSON.parse(raw.event_detail) : raw.event_detail
    } catch { detail = {} }
  }
  return {
    id: raw.id,
    timestamp: raw.timestamp,
    eventType: raw.event_type,
    eventName: raw.event_name,
    detail,
    renderType: classifyEvent(raw.event_type, raw.event_name, detail),
  }
}

function classifyEvent(type, name, detail) {
  if (type === 'email') {
    const isReceived = name === 'received'
    if (isReceived && detail.sender === 'User') return 'bubble-user'
    if (name === 'sent' && detail.recipient === 'User') return 'bubble-agent'
    return 'agent-comm'
  }
  if (type === 'think') return 'thought'
  if (type === 'action') {
    if (name === 'detected') return 'skip'
    if (detail.action_name === 'send_internal_mail') return 'skip'
    return 'pill'
  }
  if (type === 'session') {
    if (name === 'activated' || name === 'deactivated') return 'session-time'
    return 'skip'
  }
  return 'system'
}

// Wrap events into the format ChatMessage expects: { type, id, timestamp, data }
const chatTimeline = computed(() => {
  return messages.value
    .filter(e => e.renderType !== 'skip')
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
    .map(event => ({
      type: event.renderType,
      id: event.id,
      timestamp: event.timestamp,
      data: event,
    }))
})

// ---- Scroll to bottom ----
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// ---- Load history from backend (same as AgentSessionPanel) ----
async function loadHistory() {
  if (!agentName.value || !agentSessionId.value) {
    console.warn('[Floating] Missing agentName or agentSessionId, skipping history load')
    return
  }

  isLoading.value = true
  try {
    console.log('[Floating] Loading history for', agentName.value, agentSessionId.value)
    const result = await sessionAPI.getSessionEvents(agentName.value, agentSessionId.value, 200)
    const events = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
    console.log('[Floating] Loaded', events.length, 'events')
    messages.value = events
    await nextTick()
    scrollToBottom()
  } catch (err) {
    console.error('[Floating] Failed to load history:', err)
  } finally {
    isLoading.value = false
  }
}

// ---- Send message ----
async function sendMessage() {
  const body = inputText.value.trim()
  if (!body || !sessionId.value || !agentName.value || isSending.value) return

  isSending.value = true
  inputText.value = ''

  // Optimistic placeholder
  const placeholder = {
    id: `floating-placeholder-${Date.now()}`,
    timestamp: new Date().toISOString(),
    eventType: 'email',
    eventName: 'received',
    detail: { body_preview: body, sender: 'User', recipient: agentName.value, _isPlaceholder: true },
    renderType: 'bubble-user',
  }
  messages.value.push(placeholder)
  await nextTick()
  scrollToBottom()

  try {
    await sessionAPI.sendEmail(sessionId.value, {
      recipient: agentName.value,
      subject: '',
      body: body,
    })
  } catch (err) {
    console.error('Floating send failed:', err)
    // Remove placeholder on failure
    const idx = messages.value.findIndex(e => e.id === placeholder.id)
    if (idx !== -1) messages.value.splice(idx, 1)
  } finally {
    isSending.value = false
  }
}

// ---- Restore to desktop ----
async function restoreToDesktop() {
  await emit('floating:restore')
}

// ---- Toggle collapse ----
function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

// ---- Ensure input can receive focus ----
async function focusInput() {
  try {
    const webviewWindow = getCurrentWebviewWindow()
    await webviewWindow.setFocus()
  } catch (e) {
    // ignore
  }
}

// ---- Direct WebSocket connection for real-time events ----
let ws = null
let wsReconnectTimer = null

function connectWebSocket() {
  invoke('get_backend_port').then(port => {
    if (!port) {
      console.warn('[Floating] No backend port available')
      return
    }
    const wsUrl = `ws://localhost:${port}/ws`
    console.log('[Floating] Connecting WebSocket:', wsUrl)
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      console.log('[Floating] WebSocket connected')
      ws.send(JSON.stringify({ type: 'REQUEST_SYSTEM_STATUS' }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleWsMessage(data)
      } catch (e) {
        console.error('[Floating] WS parse error:', e)
      }
    }

    ws.onclose = () => {
      console.log('[Floating] WebSocket disconnected')
      wsReconnectTimer = setTimeout(connectWebSocket, 3000)
    }

    ws.onerror = (e) => {
      console.error('[Floating] WebSocket error:', e)
    }
  }).catch(e => {
    console.error('[Floating] Failed to get backend port:', e)
  })
}

function handleWsMessage(data) {
  if (data.type === 'SESSION_EVENT') {
    const { agent_name, session_id: wsAgentSessionId, data: eventData } = data
    // Only process events for our agent + session
    if (agent_name !== agentName.value) return
    if (wsAgentSessionId && wsAgentSessionId !== agentSessionId.value) return

    const parsed = parseEvent(eventData)
    if (parsed.renderType === 'skip') return
    // Skip user messages (we add optimistic placeholder on send)
    if (parsed.renderType === 'bubble-user') return

    messages.value.push(parsed)
    nextTick(scrollToBottom)
  } else if (data.type === 'AGENT_STATUS_UPDATE') {
    const { agent_name, data: statusData } = data
    if (agent_name === agentName.value) {
      agentStatus.value = statusData.status || 'IDLE'
    }
  }
}

// ---- Lifecycle ----
onMounted(async () => {
  // 1. Load history from backend
  await loadHistory()

  // 2. Connect WebSocket for real-time events
  connectWebSocket()
})

onUnmounted(() => {
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }
  if (ws) {
    ws.onclose = null // prevent reconnect
    ws.close()
    ws = null
  }
})
</script>

<template>
  <div class="floating-panel" :class="{ 'floating-panel--collapsed': isCollapsed }">
    <!-- Header (draggable) -->
    <header class="floating-header" data-tauri-drag-region>
      <div class="floating-header__left" data-tauri-drag-region>
        <div class="floating-header__avatar">
          {{ agentName ? agentName.charAt(0).toUpperCase() : '?' }}
        </div>
        <span class="floating-header__name">{{ agentName || 'Agent' }}</span>
        <span class="floating-header__status" :class="'floating-header__status--' + agentStatus.toLowerCase()">
          <span class="floating-header__status-dot"></span>
          {{ agentStatus }}
        </span>
      </div>
      <div class="floating-header__actions">
        <button class="floating-header__btn" @click.stop="toggleCollapse" :title="isCollapsed ? 'Expand' : 'Collapse'">
          <MIcon :name="isCollapsed ? 'chevron-down' : 'chevron-up'" />
        </button>
        <button class="floating-header__btn" @click.stop="restoreToDesktop" title="Back to Desktop">
          <MIcon name="arrows-maximize" />
        </button>
      </div>
    </header>

    <!-- Messages (hidden when collapsed) -->
    <div v-if="!isCollapsed" ref="messagesContainer" class="floating-messages">
      <!-- Loading -->
      <div v-if="isLoading" class="floating-messages__loading">
        <MIcon name="loader" class="spin" />
        <span>Loading messages...</span>
      </div>

      <template v-else>
        <ChatMessage
          v-for="item in chatTimeline"
          :key="item.id"
          :message="item"
          :user_agent_name="'User'"
          :agent-name="agentName"
        />
        <div v-if="chatTimeline.length === 0" class="floating-messages__empty">
          No messages yet
        </div>
      </template>
    </div>

    <!-- Input (hidden when collapsed) -->
    <div v-if="!isCollapsed" class="floating-input-area" @mousedown="focusInput">
      <textarea
        v-model="inputText"
        class="floating-input"
        placeholder="Type a message..."
        rows="2"
        @keydown.enter.exact.prevent="sendMessage"
        @focus="focusInput"
        :disabled="isSending || !sessionId"
      />
      <button
        class="floating-send-btn"
        @click="sendMessage"
        :disabled="!inputText.trim() || isSending || !sessionId"
      >
        <MIcon name="send" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.floating-panel {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--surface-base, #ffffff);
  overflow: hidden;
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
}

.floating-panel--collapsed .floating-header {
  border-bottom: none;
}

/* ---- Header ---- */
.floating-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--surface-secondary, #f4f4f5);
  border-bottom: 1px solid var(--border-light, #e4e4e7);
  user-select: none;
}

.floating-header__left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.floating-header__avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--morandi-mauve, #8B7AAF);
  color: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.floating-header__name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #18181b);
}

.floating-header__status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--text-tertiary, #71717a);
  padding: 2px 6px;
  background: var(--surface-base, #ffffff);
  border-radius: 10px;
  border: 1px solid var(--border-light, #e4e4e7);
}

.floating-header__status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--text-quaternary, #a1a1aa);
}

.floating-header__status--idle .floating-header__status-dot {
  background: var(--success, #10b981);
}

.floating-header__status--thinking .floating-header__status-dot {
  background: var(--warning, #f59e0b);
  animation: pulse 1.5s ease-in-out infinite;
}

.floating-header__status--working .floating-header__status-dot {
  background: var(--accent, #6366f1);
  animation: pulse 1s ease-in-out infinite;
}

.floating-header__status--error .floating-header__status-dot {
  background: var(--error, #ef4444);
}

.floating-header__actions {
  display: flex;
  gap: 2px;
  pointer-events: auto;
}

.floating-header__btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #71717a);
  font-size: 14px;
  transition: all 0.12s ease;
}

.floating-header__btn:hover {
  background: var(--surface-hover, #e4e4e7);
  color: var(--text-primary, #18181b);
}

/* ---- Messages ---- */
.floating-messages {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.floating-messages__empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-quaternary, #a1a1aa);
  font-size: 13px;
}

.floating-messages__loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--text-quaternary, #a1a1aa);
  font-size: 13px;
}

.floating-messages__loading .spin {
  animation: spin 1s linear infinite;
}

/* ---- Input ---- */
.floating-input-area {
  flex-shrink: 0;
  display: flex;
  align-items: flex-end;
  gap: 6px;
  padding: 8px 10px;
  border-top: 1px solid var(--border-light, #e4e4e7);
  background: var(--surface-base, #ffffff);
}

.floating-input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid var(--border, #d4d4d8);
  border-radius: 8px;
  font-size: 13px;
  line-height: 1.4;
  resize: none;
  outline: none;
  background: var(--surface-base, #ffffff);
  color: var(--text-primary, #18181b);
  font-family: inherit;
  transition: border-color 0.15s ease;
  pointer-events: auto;
}

.floating-input:focus {
  border-color: var(--accent, #6366f1);
}

.floating-input:disabled {
  opacity: 0.5;
}

.floating-send-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: var(--accent, #6366f1);
  color: white;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  transition: all 0.12s ease;
  flex-shrink: 0;
  pointer-events: auto;
}

.floating-send-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.floating-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

@keyframes pulse {
  0%, 100% { opacity: 1 }
  50% { opacity: 0.4 }
}

@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>
