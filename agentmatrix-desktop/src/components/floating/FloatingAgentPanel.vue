<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import { emit } from '@tauri-apps/api/event'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { useAgentStore } from '@/stores/agent'
import { agentAPI } from '@/api/agent'
import { sessionAPI } from '@/api/session'
import { useKaraokeScroll } from '@/composables/useKaraokeScroll'
import GlassCard from './GlassCard.vue'
import KaraokeStream from './KaraokeStream.vue'
import FloatingMenu from './FloatingMenu.vue'
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

// ---- UI state ----
const showMenu = ref(false)
const panelRef = ref(null)

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

const {
  karaokeTriple,
  isTyping,
  enqueueTypewriter,
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
    // Replay in order: action sets bar, non-action washes it away
    let lastAction = null
    for (const e of events) {
      if (e.renderType === 'pill') {
        lastAction = formatAction(e)
      } else {
        lastAction = null
      }
    }
    currentAction.value = lastAction
    // Stream shows everything except actions
    messages.value = events.filter(e => e.renderType !== 'pill')
  } catch (err) {
    console.error('[Floating] Failed to load history:', err)
  } finally {
    isLoading.value = false
  }
}

// ---- Restore to desktop ----
async function restoreToDesktop() {
  await emit('floating:restore')
}

// ---- Open/close input window ----
let isInputWindowOpen = false

/** Find the last email event ID for in_reply_to */
function getLastEmailId() {
  const emailEvents = messages.value.filter(
    e => ['bubble-user', 'bubble-agent', 'agent-comm'].includes(e.renderType)
  )
  if (emailEvents.length === 0) return undefined
  return emailEvents[emailEvents.length - 1].id
}

// ---- Open/close input window (toggle) ----
async function openInputWindow() {
  if (!sessionId.value || !agentName.value) return
  try {
    if (isInputWindowOpen) {
      await invoke('destroy_input_window')
      isInputWindowOpen = false
    } else {
      await invoke('create_input_window', {
        sessionId: sessionId.value,
        agentName: agentName.value,
        agentSessionId: agentSessionId.value,
        lastEmailId: getLastEmailId() || '',
      })
      isInputWindowOpen = true
    }
  } catch (e) {
    console.error('[Floating] Failed to toggle input window:', e)
    isInputWindowOpen = false
  }
}

// ---- UI Actions ----
const agentUISchema = ref([])

async function loadAgentUISchema() {
  if (!agentName.value) return
  const cached = agentStore.getAgentUISchema(agentName.value)
  if (cached.length > 0) {
    agentUISchema.value = cached
    return
  }
  try {
    const result = await agentAPI.getAgentUIActions(agentName.value)
    agentUISchema.value = result.schema || []
    agentStore.setAgentUISchema(agentName.value, result.schema || [])
  } catch (e) {
    console.error('[Floating] Failed to load UI schema:', e)
  }
}

async function invokeUIAction(actionNode) {
  if (!agentName.value) return
  try {
    const payload = { session_id: sessionId.value }
    await agentAPI.invokeAgentUIAction(agentName.value, actionNode.action, payload)
  } catch (e) {
    console.error('[Floating] UI action failed:', e)
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
        console.error('[Floating] WS parse error:', e)
      }
    }

    ws.onclose = () => {
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
    if (agent_name !== agentName.value) return
    if (wsAgentSessionId && wsAgentSessionId !== agentSessionId.value) return

    const parsed = parseEvent(eventData)
    if (parsed.renderType === 'skip') return
    if (parsed.renderType === 'bubble-user') return // skip echo
    if (parsed.renderType === 'pill') {
      currentAction.value = formatAction(parsed)
      return
    }

    // Any non-action message washes away the action bar
    currentAction.value = null
    enqueueTypewriter(parsed)
  } else if (data.type === 'AGENT_STATUS_UPDATE') {
    const { agent_name, data: statusData } = data
    agentStore.updateAgentStatus(agent_name, statusData)
    if (agent_name === agentName.value) {
      agentStatus.value = statusData.status || 'IDLE'
    }
  }
}

// ---- Dynamic window sizing ----
const menuRef = ref(null)

function updateWindowSize() {
  if (!panelRef.value) return
  const el = panelRef.value
  const width = Math.ceil(el.scrollWidth)
  const height = Math.ceil(el.scrollHeight)
  invoke('resize_floating_window', { width, height }).catch(() => {})
}

// ---- Lifecycle: react to session becoming valid ----
let sessionInitialized = false
let unlistenDetail = null

watch(isValidSession, async (valid) => {
  if (!valid || sessionInitialized) return
  sessionInitialized = true
  await loadHistory()
  await loadAgentUISchema()
  connectWebSocket()

  // Listen for detail window close
  unlistenDetail = await listen('detail:closed', () => {
    onDetailClose()
  })
}, { immediate: true })

// Resize window when content changes (including menu toggle)
watch([karaokeTriple, isValidSession, showMenu, currentAction], () => {
  nextTick(updateWindowSize)
}, { deep: true })

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
</script>

<template>
  <div ref="panelRef" class="floating-panel">
    <template v-if="isValidSession">
    <!-- Capsule: card + menu only -->
    <div class="glass-capsule">
      <GlassCard
        :agent-name="agentName"
        :agent-status="agentStatus"
        @toggle-menu="showMenu = !showMenu"
        @open-input="openInputWindow"
      />

      <FloatingMenu
        ref="menuRef"
        :visible="showMenu"
        :schema="agentUISchema"
        :agent-name="agentName"
        :agent-status="agentStatus"
        @close="showMenu = false"
        @invoke-action="invokeUIAction"
        @restore="restoreToDesktop"
      />

      <!-- Loading state -->
      <div v-if="isLoading" class="floating-loading">
        <span class="floating-loading__spinner"><MIcon name="loader" /></span>
      </div>
    </div>

    <!-- Stream: wider than capsule (1.618x), right-aligned with it -->
    <KaraokeStream
      v-if="!isLoading"
      :karaoke-triple="karaokeTriple"
    />

    <!-- Action status bar: bottom of stream, washed away by any new message -->
    <div v-if="currentAction" class="action-bar">
      <Transition name="action-flip">
        <div class="action-bar__line" :key="currentAction.key">
          <span class="action-bar__dot" :class="`action-bar__dot--${currentAction.status}`"></span>
          <span class="action-bar__text">{{ currentAction.text }}</span>
        </div>
      </Transition>
    </div>
    </template>
  </div>
</template>

<style scoped>
.floating-panel {
  background: transparent;
  padding: 0;
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.08));
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
}

.glass-capsule {
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.97);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(0, 0, 0, 0.06);
  width: fit-content;
}

/* ---- Action status bar (below stream) ---- */
.action-bar {
  width: 453px;
  padding: 0 14px 6px;
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

.floating-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.floating-loading__spinner {
  font-size: 16px;
  color: var(--text-quaternary, #d4d4d8);
  animation: spin 1s linear infinite;
  display: flex;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>
