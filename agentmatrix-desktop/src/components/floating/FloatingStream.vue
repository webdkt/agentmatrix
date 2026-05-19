<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { emit as tauriEmit } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { useAgentStore } from '@/stores/agent'
import { sessionAPI } from '@/api/session'
import { useKaraokeScroll } from '@/composables/useKaraokeScroll'
import KaraokeStream from './KaraokeStream.vue'
import MIcon from '@/components/icons/MIcon.vue'

// ---- Parse session info from URL hash ----
function parseParams() {
  const hash = window.location.hash.slice(1)
  const params = {}
  hash.split('&').forEach(pair => {
    const [key, val] = pair.split('=')
    if (key && val) params[decodeURIComponent(key)] = decodeURIComponent(val)
  })
  return params
}

const sessionId = ref(null)
const agentName = ref(null)
const agentSessionId = ref(null)
const agentStatus = ref('IDLE')
const isLoading = ref(false)

function readParamsFromHash() {
  const params = parseParams()
  sessionId.value = params.sessionId || null
  agentName.value = params.agentName || null
  agentSessionId.value = params.agentSessionId || null
}
readParamsFromHash()
window.addEventListener('hashchange', readParamsFromHash)

const isValidSession = computed(() => !!(agentName.value && agentSessionId.value))

// ---- Stores ----
const agentStore = useAgentStore()

// ---- Messages ----
const messages = ref([])

// ---- Action ticker ----
const currentAction = ref(null)

function formatAction(event) {
  const { detail, eventName } = event
  const label = detail.action_label || detail.action_name || ''
  let text = label
  let status = 'started'
  if (eventName === 'completed') {
    status = detail.status === 'error' ? 'error' : detail.status === 'canceled' ? 'canceled' : 'completed'
    if (detail.status === 'error') text = label + ' 出错'
    else if (detail.status === 'canceled') text = label + ' 已取消'
    else text = label
  }
  return { text, status, key: event.id }
}

// ---- Karaoke scroll logic ----
const {
  karaokeTriple,
  isAutoScrolling,
  unreadCount,
  onDetailOpen,
  onDetailClose,
  pauseAutoScroll,
  resumeAutoScroll,
} = useKaraokeScroll(messages)

// ---- Parse event ----
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
    if (name === 'received' && detail.sender === 'User') return 'bubble-user'
    if (name === 'sent') return 'bubble-agent'
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

// ---- Load history from backend ----
async function loadHistory() {
  if (!agentName.value || !agentSessionId.value) return
  isLoading.value = true
  try {
    const result = await sessionAPI.getSessionEvents(agentName.value, agentSessionId.value, 200)
    const events = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
    let lastAction = null
    for (const e of events) {
      if (e.renderType === 'pill') {
        lastAction = formatAction(e)
      } else {
        lastAction = null
      }
    }
    currentAction.value = lastAction
    messages.value = events.filter(e => e.renderType !== 'pill')
  } catch (err) {
    console.error('[Stream] Failed to load history:', err)
  } finally {
    isLoading.value = false
  }
}

// ---- Broadcast agent status to capsule window ----
async function broadcastStatus(status) {
  try {
    await tauriEmit('floating:status-update', { status })
  } catch (e) {
    console.error('[Stream] Failed to broadcast status:', e)
  }
}

// ---- Direct WebSocket connection ----
let ws = null
let wsReconnectTimer = null

function connectWebSocket() {
  invoke('get_backend_port').then(port => {
    if (!port) return
    const wsUrl = `ws://localhost:${port}/ws`
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'REQUEST_SYSTEM_STATUS' }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        handleWsMessage(data)
      } catch (e) {
        console.error('[Stream] WS parse error:', e)
      }
    }

    ws.onclose = () => {
      wsReconnectTimer = setTimeout(connectWebSocket, 3000)
    }

    ws.onerror = (e) => {
      console.error('[Stream] WebSocket error:', e)
    }
  }).catch(e => {
    console.error('[Stream] Failed to get backend port:', e)
  })
}

function handleWsMessage(data) {
  if (data.type === 'SESSION_EVENT') {
    const { agent_name, session_id: wsAgentSessionId, data: eventData } = data
    if (agent_name !== agentName.value) return
    if (wsAgentSessionId && wsAgentSessionId !== agentSessionId.value) return

    const parsed = parseEvent(eventData)
    if (parsed.renderType === 'skip') return
    if (parsed.renderType === 'bubble-user') return
    if (parsed.renderType === 'pill') {
      currentAction.value = formatAction(parsed)
      return
    }

    currentAction.value = null
    messages.value.push(parsed)
  } else if (data.type === 'AGENT_STATUS_UPDATE') {
    const { agent_name, data: statusData } = data
    agentStore.updateAgentStatus(agent_name, statusData)
    if (agent_name === agentName.value) {
      agentStatus.value = statusData.status || 'IDLE'
      broadcastStatus(statusData.status || 'IDLE')
    }
  }
}

// ---- Lifecycle ----
let sessionInitialized = false
let unlistenDetail = null

onMounted(() => {
  invoke('clip_window_rounded', { label: 'floating-stream', radius: 16 })
})

watch(isValidSession, async (valid) => {
  if (!valid || sessionInitialized) return
  sessionInitialized = true
  await loadHistory()
  connectWebSocket()

  unlistenDetail = await listen('detail:closed', () => {
    onDetailClose()
  })
}, { immediate: true })

onUnmounted(() => {
  window.removeEventListener('hashchange', readParamsFromHash)
  if (unlistenDetail) unlistenDetail()
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
})

// Need to import listen for detail:closed
import { listen } from '@tauri-apps/api/event'
</script>

<template>
  <div class="stream-panel">
    <!-- Loading state -->
    <div v-if="isLoading" class="stream-loading">
      <span class="stream-loading__spinner"><MIcon name="loader" /></span>
    </div>

    <!-- Stream -->
    <KaraokeStream
      v-if="!isLoading"
      :karaoke-triple="karaokeTriple"
      :is-auto-scrolling="isAutoScrolling"
      :unread-count="unreadCount"
      @scroll-pause="pauseAutoScroll"
      @scroll-resume="resumeAutoScroll"
    />

    <!-- Action status bar -->
    <div v-if="currentAction" class="action-bar">
      <Transition name="action-flip">
        <div class="action-bar__line" :key="currentAction.key">
          <span class="action-bar__dot" :class="`action-bar__dot--${currentAction.status}`"></span>
          <span class="action-bar__text">{{ currentAction.text }}</span>
        </div>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.stream-panel {
  background: rgba(255, 255, 255, 0.72);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  padding: 0;
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}

/* ---- Action status bar ---- */
.action-bar {
  width: 100%;
  padding: 0 14px 6px;
  box-sizing: border-box;
  overflow: hidden;
  position: relative;
}

.action-bar__line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-bar__dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--info, #7B8FA1);
  flex-shrink: 0;
}

.action-bar__dot--completed { background: var(--success, #7D9B76); }
.action-bar__dot--error { background: var(--error, #B57171); }
.action-bar__dot--canceled { background: var(--text-quaternary, #d4d4d8); }

.action-bar__text {
  font-size: 11px;
  color: var(--text-tertiary, #a1a1aa);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.action-flip-enter-active {
  transition: all 0.3s cubic-bezier(0.22, 1, 0.36, 1);
}
.action-flip-leave-active {
  transition: all 0.25s ease-in;
  position: absolute;
}
.action-flip-enter-from {
  opacity: 0;
  transform: translateY(100%);
}
.action-flip-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}

.stream-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.stream-loading__spinner {
  font-size: 16px;
  color: var(--text-quaternary, #d4d4d8);
  animation: spin 1s linear infinite;
  display: flex;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>
