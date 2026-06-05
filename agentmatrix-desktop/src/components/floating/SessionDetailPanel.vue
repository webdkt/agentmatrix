<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { emit as tauriEmit, listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import { sessionAPI } from '@/api/session'
import { configAPI } from '@/api/config'
import ChatMessage from '@/components/collab/ChatMessage.vue'
import MIcon from '@/components/icons/MIcon.vue'

// ---- Session state: read from Rust global state ----
const agentName = ref(null)
const agentSessionId = ref(null)
const userSessionId = ref(null)
const taskId = ref(null)
const lastEmailId = ref(null)
const userAgentName = ref(null)
const agentStatus = ref('IDLE')
const agentStatusData = ref({})
const isLoading = ref(false)

async function loadSessionFromGlobal() {
  try {
    const config = await configAPI.getFullConfig()
    userAgentName.value = config?.user_agent_name || null
  } catch (e) {
    console.error('[Detail] Failed to load backend config:', e)
  }
  try {
    const rustConfig = await invoke('get_config')
    worldPath.value = rustConfig.matrix_world_path || ''
  } catch (e) {
    console.error('[Detail] Failed to load config:', e)
  }
  try {
    const ctx = await invoke('get_current_session')
    agentName.value = ctx.agent_name || null
    agentSessionId.value = ctx.agent_session_id || null
    userSessionId.value = ctx.user_session_id || null
    taskId.value = ctx.task_id || null
    lastEmailId.value = ctx.last_email_id || null
  } catch (e) {
    console.error('[Detail] Failed to load session:', e)
  }
}

const isValidSession = computed(() => !!(agentName.value && agentSessionId.value))

// ---- Events ----
const events = ref([])
const currentAction = ref(null)
const messagesContainer = ref(null)
const worldPath = ref('')
const isAutoScrolling = ref(true)

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
      return (detail.body_preview && isPureXml(detail.body_preview)) ? 'skip' : 'bubble-agent'
    }
    if (name === 'received' && detail.sender === userAgentName.value) return 'bubble-user'
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

// ---- Chat timeline (same as useChatTimeline) ----

const chatTimeline = computed(() => {
  return events.value
    .map(event => ({
      type: event.renderType,
      id: event.id,
      timestamp: event.timestamp,
      data: event,
    }))
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
})

// ---- Load history ----

async function loadHistory() {
  if (!agentName.value || !agentSessionId.value) return
  isLoading.value = true
  try {
    const result = await sessionAPI.getSessionEvents(agentName.value, agentSessionId.value, 200)
    const parsed = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
    let lastAction = null
    for (const e of parsed) {
      if (e.renderType === 'pill') {
        lastAction = formatAction(e)
      } else {
        lastAction = null
      }
    }
    currentAction.value = lastAction
    events.value = parsed
  } catch (err) {
    console.error('[Detail] Failed to load history:', err)
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

// ---- Auto-scroll ----

function scrollToBottom() {
  if (!messagesContainer.value || !isAutoScrolling.value) return
  messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
}

function onScroll() {
  const el = messagesContainer.value
  if (!el) return
  const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 50
  isAutoScrolling.value = atBottom
}

// ---- Tauri event listeners (replaces direct WebSocket) ----
let unlistenWsSession = null
let unlistenWsStatus = null

async function setupEventListeners() {
  unlistenWsSession = await listen('ws:session-event', (event) => {
    handleWsMessage(event.payload)
  })
  unlistenWsStatus = await listen('ws:agent-status-update', (event) => {
    handleWsMessage(event.payload)
  })
}

function handleWsMessage(data) {
  if (data.type === 'SESSION_EVENT') {
    const { agent_name, session_id: wsAgentSessionId, data: eventData } = data
    if (agent_name !== agentName.value) return
    if (wsAgentSessionId && wsAgentSessionId !== agentSessionId.value) return

    const parsed = parseEvent(eventData)
    if (parsed.renderType === 'skip') return

    if (parsed.renderType === 'pill') {
      currentAction.value = formatAction(parsed)
      return
    }

    currentAction.value = null
    events.value.push(parsed)
    nextTick(() => scrollToBottom())
  } else if (data.type === 'AGENT_STATUS_UPDATE') {
    const { agent_name, data: statusData } = data
    if (agent_name === agentName.value) {
      agentStatus.value = statusData.status || 'IDLE'
    }
  }
}

// ---- Send message ----
const inputText = ref('')
const isSending = ref(false)
const textareaRef = ref(null)

// ---- Status display (same logic as GlassCard) ----
const agentInitial = computed(() => {
  return agentName.value ? agentName.value.charAt(0).toUpperCase() : '?'
})

const isOnCurrentSession = computed(() => {
  const status = agentStatus.value
  if (status === 'IDLE') return true
  const activeSessionId = agentStatusData.value?.current_session_id
  if (!activeSessionId) return true
  return activeSessionId === agentSessionId.value
})

const statusLabel = computed(() => {
  switch (agentStatus.value) {
    case 'THINKING': return 'thinking'
    case 'WORKING': return 'working'
    case 'RECOVERING': return 'recovering'
    case 'WAITING_FOR_USER': return 'waiting'
    case 'PAUSED': return 'paused'
    case 'ERROR': return 'error'
    default: return 'idle'
  }
})

const isActive = computed(() => {
  if (!isOnCurrentSession.value && agentStatus.value !== 'IDLE') return true
  return ['THINKING', 'WORKING', 'RECOVERING'].includes(agentStatus.value)
})

const statusType = computed(() => {
  if (!isOnCurrentSession.value && agentStatus.value !== 'IDLE') return 'working'
  switch (agentStatus.value) {
    case 'THINKING': return 'thinking'
    case 'WORKING': return 'working'
    case 'RECOVERING': return 'recovering'
    default: return null
  }
})

const activeIcon = computed(() => {
  if (!isOnCurrentSession.value && agentStatus.value !== 'IDLE') return 'loader'
  switch (agentStatus.value) {
    case 'THINKING': return 'logo'
    case 'WORKING': return 'settings'
    case 'RECOVERING': return 'loader'
    default: return null
  }
})

const canSend = computed(() => {
  return inputText.value.trim() && userSessionId.value && agentName.value && !isSending.value
})

async function sendMessage() {
  const body = inputText.value.trim()
  if (!body || !userSessionId.value || !agentName.value || isSending.value) return

  isSending.value = true
  try {
    // Optimistic placeholder
    const placeholder = {
      id: `placeholder-${Date.now()}`,
      timestamp: new Date().toISOString(),
      eventType: 'email',
      eventName: 'received',
      detail: {
        body_preview: body,
        sender: userAgentName.value || 'User',
        recipient: agentName.value,
        _isPlaceholder: true,
      },
      renderType: 'thought',
    }
    events.value.push(placeholder)
    nextTick(() => { isAutoScrolling.value = true; scrollToBottom() })

    await sessionAPI.sendEmail(userSessionId.value, {
      recipient: agentName.value,
      subject: '',
      body,
      task_id: taskId.value || userSessionId.value,
      in_reply_to: lastEmailId.value || undefined,
      recipient_session_id: agentSessionId.value || undefined,
    })

    inputText.value = ''
    nextTick(adjustTextareaHeight)
  } catch (err) {
    console.error('[Detail] Send failed:', err)
  } finally {
    isSending.value = false
  }
}

function handleKeyDown(event) {
  if (event.key === 'Enter' && event.ctrlKey) {
    event.preventDefault()
    sendMessage()
  }
}

function adjustTextareaHeight() {
  if (!textareaRef.value) return
  textareaRef.value.style.height = 'auto'
  textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 120) + 'px'
}

// ---- Drag-drop ----
const isDragging = ref(false)
let unlistenDragDrop = null

async function setupDragDrop() {
  const webview = getCurrentWebview()
  unlistenDragDrop = await webview.onDragDropEvent(async (event) => {
    if (event.payload.type === 'over') {
      isDragging.value = true
    } else if (event.payload.type === 'drop') {
      isDragging.value = false
      const paths = event.payload.paths
      if (!paths?.length || !agentName.value || !agentSessionId.value || !worldPath.value) return

      const taskDir = `${worldPath.value}/workspace/agent_files/${agentName.value}/work_files/${agentSessionId.value}`
      const fileNames = []
      for (const srcPath of paths) {
        const fileName = srcPath.split('/').pop()
        const destPath = `${taskDir}/${fileName}`
        try {
          await invoke('copy_file', { src: srcPath, dest: destPath })
          fileNames.push(fileName)
        } catch (err) {
          console.error(`Failed to copy ${fileName}:`, err)
        }
      }

      if (fileNames.length > 0) {
        const fileList = fileNames.map(n => `- ${n}`).join('\n')
        const draft = `已复制以下文件到 \`~/current_task\` 目录，你看一下：\n${fileList}\n`
        inputText.value = inputText.value ? inputText.value + '\n' + draft : draft
        nextTick(adjustTextareaHeight)
      }
    } else {
      isDragging.value = false
    }
  })
}

// ---- Close window ----

async function closeWindow() {
  await tauriEmit('detail:closed')
  const win = getCurrentWebviewWindow()
  await win.hide()
}

// ---- Lifecycle ----
let sessionInitialized = false
let unlistenReloadSession = null
let unlistenStatus = null

onMounted(async () => {
  await loadSessionFromGlobal()
  await setupDragDrop()
  await setupEventListeners()

  unlistenReloadSession = await listen('session-changed', async () => {
    const oldAgentName = agentName.value
    const oldAgentSessionId = agentSessionId.value
    await loadSessionFromGlobal()
    if (agentName.value !== oldAgentName || agentSessionId.value !== oldAgentSessionId) {
      events.value = []
      currentAction.value = null
      sessionInitialized = false
      // Re-init if valid
      if (isValidSession.value && !sessionInitialized) {
        sessionInitialized = true
        await loadHistory()
      }
    }
  })

  unlistenStatus = await listen('floating:status-update', (event) => {
    agentStatusData.value = event.payload || {}
    agentStatus.value = event.payload?.status || 'IDLE'
  })
})

watch(isValidSession, async (valid) => {
  if (!valid || sessionInitialized) return
  sessionInitialized = true
  await loadHistory()
}, { immediate: true })

onUnmounted(() => {
  if (unlistenReloadSession) unlistenReloadSession()
  if (unlistenStatus) unlistenStatus()
  if (unlistenDragDrop) unlistenDragDrop()
  if (unlistenWsSession) unlistenWsSession()
  if (unlistenWsStatus) unlistenWsStatus()
})
</script>

<template>
  <div class="session-detail-panel">
    <!-- Header -->
    <div class="session-detail-panel__header" @mousedown="getCurrentWebviewWindow().startDragging()">
      <div class="session-detail-panel__avatar" :class="{ 'session-detail-panel__avatar--active': isActive }">
        <span v-if="isActive && activeIcon" class="session-detail-panel__avatar-icon">
          <MIcon :name="activeIcon" />
        </span>
        <span v-else class="session-detail-panel__avatar-letter">{{ agentInitial }}</span>
      </div>
<div class="session-detail-panel__info">
         <span class="session-detail-panel__name">{{ agentName }}</span>
         <template v-if="isOnCurrentSession">
           <span class="session-detail-panel__status" :class="{
             'session-detail-panel__status--idle': agentStatus === 'IDLE',
             'session-detail-panel__status--active': isActive,
             [`session-detail-panel__status--${statusType}`]: statusType,
           }">
             {{ statusLabel }}
           </span>
         </template>
         <template v-else>
           <span class="session-detail-panel__other-task">ON OTHER TASK</span>
         </template>
       </div>
      <button class="session-detail-panel__close" @mousedown.stop @click="closeWindow" title="Close">
        <MIcon name="x" />
      </button>
    </div>

    <!-- Messages (scrollable) -->
    <div ref="messagesContainer" class="session-detail-panel__messages" @scroll="onScroll">
      <!-- Loading -->
      <div v-if="isLoading" class="session-detail-panel__loading">
        <span class="session-detail-panel__loading-spinner"><MIcon name="loader" /></span>
      </div>

      <!-- Chat timeline -->
      <template v-else>
        <ChatMessage
          v-for="item in chatTimeline"
          :key="item.id"
          :message="item"
          :user_agent_name="userAgentName || 'User'"
          :agent-name="agentName"
        />
      </template>

      <!-- Drag-drop overlay -->
      <div v-if="isDragging" class="session-detail-panel__drop-overlay">
        <MIcon name="upload" />
        <span>Drop files to copy into task directory</span>
      </div>
    </div>

    <!-- Action ticker -->
    <div v-if="currentAction" class="session-detail-panel__action-bar">
      <Transition name="action-flip">
        <div class="action-bar__line" :key="currentAction.key">
          <span class="action-bar__dot" :class="`action-bar__dot--${currentAction.status}`"></span>
          <span class="action-bar__text">{{ currentAction.text }}</span>
        </div>
      </Transition>
    </div>

    <!-- Input area -->
    <div class="session-detail-panel__input">
      <textarea
        ref="textareaRef"
        v-model="inputText"
        class="session-detail-panel__textarea"
        placeholder="输入消息... (Ctrl+Enter 发送)"
        rows="2"
        @keydown="handleKeyDown"
        @input="adjustTextareaHeight"
        :disabled="isSending"
      />
      <button
        class="session-detail-panel__send"
        @click="sendMessage"
        :disabled="!canSend"
        title="Send"
      >
        <MIcon v-if="!isSending" name="send" />
        <span v-else class="session-detail-panel__spin"><MIcon name="loader" /></span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.session-detail-panel {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-radius: 16px;
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  overflow: hidden;
}

/* ---- Header ---- */
.session-detail-panel__header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
  user-select: none;
}

.session-detail-panel__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--morandi-mauve, #B8A9C9);
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  pointer-events: none;
}

.session-detail-panel__avatar::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  z-index: 0;
}

.session-detail-panel__avatar--active {
  animation: avatar-breathe 2s ease-in-out infinite;
  box-shadow: 0 0 0 0 rgba(184, 169, 201, 0.4);
}

.session-detail-panel__avatar-letter {
  position: relative;
  z-index: 1;
}

.session-detail-panel__avatar-icon {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  animation: icon-spin 1.5s linear infinite;
}

@keyframes avatar-breathe {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(184, 169, 201, 0.4);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(184, 169, 201, 0);
  }
}

@keyframes icon-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.session-detail-panel__info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.session-detail-panel__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #18181b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-detail-panel__status {
  padding: 3px 10px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary, #52525b);
  white-space: nowrap;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.session-detail-panel__status--idle {
  color: var(--text-quaternary, #d4d4d8);
  font-weight: 400;
}

.session-detail-panel__status--active {
  background: rgba(184, 169, 201, 0.12);
  color: var(--morandi-mauve, #8B7BA5);
}

/* Thinking state */
.session-detail-panel__status--thinking {
  background: linear-gradient(90deg,
    rgba(124, 58, 237, 0.08) 0%,
    rgba(124, 58, 237, 0.18) 50%,
    rgba(124, 58, 237, 0.08) 100%
  );
  background-size: 200% 100%;
  color: #7C3AED;
  font-weight: 600;
  border: 1px solid rgba(124, 58, 237, 0.2);
  animation: thinking-shimmer 2s ease-in-out infinite;
  text-shadow: 0 0 8px rgba(124, 58, 237, 0.3);
}

.session-detail-panel__status--thinking::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.4) 50%,
    transparent 100%
  );
  animation: thinking-light 2s ease-in-out infinite;
}

/* Working state */
.session-detail-panel__status--working {
  background: linear-gradient(90deg,
    rgba(13, 148, 136, 0.08) 0%,
    rgba(13, 148, 136, 0.2) 50%,
    rgba(13, 148, 136, 0.08) 100%
  );
  background-size: 200% 100%;
  color: #0D9488;
  font-weight: 600;
  border: 1px solid rgba(13, 148, 136, 0.25);
  animation: working-pulse 1.5s ease-in-out infinite;
  text-shadow: 0 0 8px rgba(13, 148, 136, 0.3);
}

.session-detail-panel__status--working::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120%;
  height: 120%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(13, 148, 136, 0.15) 0%, transparent 70%);
  animation: working-glow 1.5s ease-in-out infinite;
}

/* Recovering state */
.session-detail-panel__status--recovering {
  background: linear-gradient(90deg,
    rgba(217, 119, 6, 0.08) 0%,
    rgba(217, 119, 6, 0.2) 50%,
    rgba(217, 119, 6, 0.08) 100%
  );
  background-size: 200% 100%;
  color: #D97706;
  font-weight: 600;
  border: 1px solid rgba(217, 119, 6, 0.25);
  animation: recovering-flash 1.2s ease-in-out infinite;
  text-shadow: 0 0 8px rgba(217, 119, 6, 0.3);
}

.session-detail-panel__status--recovering::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(217, 119, 6, 0.1) 25%,
    rgba(255, 255, 255, 0.3) 50%,
    rgba(217, 119, 6, 0.1) 75%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: recovering-light 1.2s linear infinite;
}

.session-detail-panel__other-task {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  background: rgba(180, 140, 80, 0.08);
  border: 1px solid rgba(180, 140, 80, 0.15);
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  color: rgba(160, 120, 60, 0.85);
  white-space: nowrap;
}

.session-detail-panel__close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #a1a1aa);
  font-size: 16px;
  transition: all 0.12s ease;
  margin-left: auto;
}

.session-detail-panel__close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary, #18181b);
}

/* ---- Messages ---- */
.session-detail-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 16px 44px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  position: relative;
  min-height: 0;
}

.session-detail-panel__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.session-detail-panel__loading-spinner {
  font-size: 20px;
  color: var(--text-quaternary, #d4d4d8);
  animation: spin 1s linear infinite;
  display: flex;
}

/* ---- Action ticker ---- */
.session-detail-panel__action-bar {
  width: 100%;
  padding: 0 16px 4px;
  box-sizing: border-box;
  overflow: hidden;
  position: relative;
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

/* ---- Input area ---- */
.session-detail-panel__input {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 12px 16px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.session-detail-panel__textarea {
  flex: 1;
  min-height: 36px;
  max-height: 120px;
  padding: 8px 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  font-size: 13px;
  line-height: 1.5;
  resize: none;
  outline: none;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-primary, #18181b);
  font-family: inherit;
  transition: border-color 0.15s ease;
}

.session-detail-panel__textarea:focus {
  border-color: var(--accent, #A67B7B);
}

.session-detail-panel__textarea::placeholder {
  color: var(--text-quaternary, #d4d4d8);
}

.session-detail-panel__textarea:disabled {
  opacity: 0.5;
}

.session-detail-panel__send {
  width: 36px;
  height: 36px;
  border: none;
  background: var(--accent, #A67B7B);
  color: white;
  border-radius: 50%;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.12s ease;
}

.session-detail-panel__send:hover:not(:disabled) {
  opacity: 0.85;
}

.session-detail-panel__send:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.session-detail-panel__spin {
  animation: spin 1s linear infinite;
  display: flex;
}

/* ---- Drag-drop overlay ---- */
.session-detail-panel__drop-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary, #52525b);
  border-radius: 16px;
  z-index: 10;
  pointer-events: none;
}

.session-detail-panel__drop-overlay .iconify {
  font-size: 32px;
  color: var(--accent, #A67B7B);
}

@keyframes spin {
  to { transform: rotate(360deg) }
}

@keyframes thinking-shimmer {
  0%, 100% {
    background-position: 0% 50%;
    box-shadow: 0 0 8px rgba(124, 58, 237, 0.15);
  }
  50% {
    background-position: 100% 50%;
    box-shadow: 0 0 16px rgba(124, 58, 237, 0.3);
  }
}

@keyframes thinking-light {
  0% { left: -100%; }
  50% { left: 100%; }
  100% { left: 100%; }
}

@keyframes working-pulse {
  0%, 100% {
    background-position: 0% 50%;
    transform: scale(1);
  }
  50% {
    background-position: 100% 50%;
    transform: scale(1.02);
  }
}

@keyframes working-glow {
  0%, 100% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
  50% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}

@keyframes recovering-flash {
  0%, 100% {
    background-position: 0% 50%;
    box-shadow: 0 0 8px rgba(217, 119, 6, 0.2);
  }
  25% {
    box-shadow: 0 0 16px rgba(217, 119, 6, 0.4);
  }
  50% {
    background-position: 100% 50%;
    box-shadow: 0 0 8px rgba(217, 119, 6, 0.2);
  }
  75% {
    box-shadow: 0 0 20px rgba(217, 119, 6, 0.5);
  }
}

@keyframes recovering-light {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
