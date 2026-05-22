<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { emit as tauriEmit, listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { useAgentStore } from '@/stores/agent'
import { sessionAPI } from '@/api/session'
import { useKaraokeScroll } from '@/composables/useKaraokeScroll'
import KaraokeStream from './KaraokeStream.vue'

// ---- Session state: read from Rust global state ----
const agentName = ref(null)
const agentSessionId = ref(null)
const userAgentName = ref(null)
const agentStatus = ref('IDLE')

async function loadSessionFromGlobal() {
  try {
    const ctx = await invoke('get_current_session')
    agentSessionId.value = ctx.agent_session_id || null
    agentName.value = ctx.agent_name || null
    userAgentName.value = ctx.user_agent_name || null
  } catch (e) {
    console.error('[Stream] Failed to load session:', e)
  }
}

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

// ---- Event display helpers ----
function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

function eventSummary(event) {
  const { renderType, detail, eventName } = event
  switch (renderType) {
    case 'thought':
      return truncate(detail.thought || detail.body_preview || '', 120)
    case 'agent-comm': {
      if (eventName === 'received') return `收到来自 ${detail.sender || '未知'} 的邮件`
      return ''
    }
    case 'system':
      return eventName
    default:
      return ''
  }
}

// ---- Karaoke scroll logic ----
const {
  karaokeTriple,
  isTyping,
  enqueueTypewriter,
  reset,
  onDetailOpen,
  onDetailClose,
} = useKaraokeScroll(messages, eventSummary)

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

function isPureXml(text) {
  if (!text) return false
  const s = text.trim()
  return s.startsWith('<') && s.endsWith('>') && /<\/\w/.test(s)
}

function classifyEvent(type, name, detail) {
  if (type === 'email') {
    if (name === 'sent') {
      return (detail.body_preview && isPureXml(detail.body_preview)) ? 'skip' : 'thought'
    }
    if (name === 'received' && detail.sender === userAgentName.value) return 'skip'
    return 'agent-comm'
  }
  if (type === 'think') {
    return isPureXml(detail.thought) ? 'skip' : 'thought'
  }
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

// ---- History (loaded on init, cancelled if typewriter starts) ----
let historyAborted = false

async function loadHistory() {
  if (!agentName.value || !agentSessionId.value) return
  try {
    const result = await sessionAPI.getSessionEvents(agentName.value, agentSessionId.value, 200)
    if (historyAborted) return
    const events = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
    messages.value = events.filter(e => e.renderType !== 'pill')
  } catch (err) {
    console.error('[Stream] Failed to load history:', err)
  }
}

// ---- Broadcast agent status to capsule window ----
async function broadcastStatus(data) {
  try {
    await tauriEmit('floating:status-update', data)
  } catch (e) {
    console.error('[Stream] Failed to broadcast status:', e)
  }
}

// ---- Direct WebSocket connection ----
let ws = null
let wsReconnectTimer = null

function connectWebSocket() {
  // Clean up existing connection before creating a new one
  if (wsReconnectTimer) {
    clearTimeout(wsReconnectTimer)
    wsReconnectTimer = null
  }
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }

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
    if (!historyAborted) {
      historyAborted = true
      reset()
    }
    enqueueTypewriter(parsed)
  } else if (data.type === 'AGENT_STATUS_UPDATE') {
    const { agent_name, data: statusData } = data
    agentStore.updateAgentStatus(agent_name, statusData)
    if (agent_name === agentName.value) {
      agentStatus.value = statusData.status || 'IDLE'
      broadcastStatus(statusData)
    }
  }
}

// ---- Lifecycle ----
let unlistenDetail = null
let unlistenReloadSession = null

onMounted(async () => {
  invoke('clip_window_rounded', { label: 'floating-stream', radius: 16 })
  await loadSessionFromGlobal()
  connectWebSocket()

  unlistenReloadSession = await listen('session-changed', async () => {
    await loadSessionFromGlobal()
    historyAborted = false
    reset()
    currentAction.value = null
    loadHistory()
    // Reconnect WebSocket to ensure connection (onMounted may have run before backend was ready)
    connectWebSocket()
  })

  unlistenDetail = await listen('detail:closed', () => {
    onDetailClose()
  })
})

onUnmounted(() => {
  if (unlistenDetail) unlistenDetail()
  if (unlistenReloadSession) unlistenReloadSession()
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
</script>

<template>
  <div class="stream-panel">
    <!-- Stream -->
    <KaraokeStream
      :karaoke-triple="karaokeTriple"
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
  background: rgba(255, 255, 255, 0.68);
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border-radius: 16px;
  border: 0.5px solid rgba(0, 0, 0, 0.1);
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.06),
    0 8px 24px rgba(0, 0, 0, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
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
  padding: 0 14px 4px;
  box-sizing: border-box;
  overflow: hidden;
  position: relative;
  margin-top: auto;
  flex-shrink: 0;
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

</style>
