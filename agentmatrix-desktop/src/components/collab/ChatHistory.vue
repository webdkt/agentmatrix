<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { useAgentStore } from '@/stores/agent'
import { sessionAPI } from '@/api/session'
import ChatMessage from './ChatMessage.vue'
import EmailReply from '@/components/email/EmailReply.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  user_agent_name: {
    type: String,
    default: 'User'
  }
})

const { t } = useI18n()
const sessionStore = useSessionStore()
const agentStore = useAgentStore()

// ---- State ----
const events = ref([])           // parsed session events
const isLoading = ref(false)
const error = ref(null)
const messagesContainer = ref(null)
const answer = ref('')

// Current agent status for the live status indicator at bottom
const currentAgentStatuses = ref({})

// ---- Computed ----
const currentSession = computed(() => sessionStore.currentSession)

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

const hasContent = computed(() => chatTimeline.value.length > 0)

const pendingQuestion = computed(() => {
  if (!currentSession.value) return null
  return sessionStore.getPendingQuestion(currentSession.value.session_id)
})

// Agent name for display (toolbar + thought labels)
const primaryAgentName = computed(() => {
  if (!currentSession.value) return null
  return currentSession.value.agent_name || currentSession.value.name || null
})

// ---- Event parsing ----

function parseEvent(raw) {
  let detail = {}
  if (raw.event_detail) {
    try {
      detail = typeof raw.event_detail === 'string' ? JSON.parse(raw.event_detail) : raw.event_detail
    } catch {
      detail = {}
    }
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
    const isSent = name === 'sent'
    if (isReceived && detail.sender === props.user_agent_name) {
      return 'bubble-user'
    }
    if (isSent && detail.recipient === props.user_agent_name) {
      return 'bubble-agent'
    }
    return 'agent-comm'
  }
  if (type === 'think') {
    return 'thought'
  }
  if (type === 'action') {
    if (name === 'detected') {
      return 'skip'
    }
    return 'pill'
  }
  if (type === 'session') {
    if (name === 'activated' || name === 'deactivated') {
      return 'session-time'
    }
    return 'skip'
  }
  return 'system'
}

// ---- Event loading ----

const loadEvents = async (session) => {
  const agentName = session.agent_name || session.name
  const agentSessionId = session.agent_session_id
  if (!agentName || !agentSessionId) {
    console.warn('ChatHistory: missing agent_name or agent_session_id', session)
    return
  }

  isLoading.value = true
  error.value = null

  try {
    const result = await sessionAPI.getSessionEvents(agentName, agentSessionId)
    events.value = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
    sessionStore.markSessionRead(session.session_id)
  } catch (err) {
    error.value = err.message
    console.error('Failed to load session events:', err)
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

// ---- Session watcher ----

watch(currentSession, async (newSession, oldSession) => {
  // 如果是从 placeholder session 切换到真实 session（同一封邮件），不清空 events
  const isPlaceholderToReal = oldSession?._isPlaceholder && newSession && !newSession._isPlaceholder

  if (!isPlaceholderToReal) {
    events.value = []
    currentAgentStatuses.value = {}
  }

  if (newSession) {
    if (newSession._isPlaceholder) {
      isLoading.value = false
      return
    }
    // placeholder → real: 不重新加载，保留 optimistic 的 placeholder bubble
    // 后端 SESSION_EVENT 到达时会替换 placeholder 为真实数据
    if (isPlaceholderToReal) {
      isLoading.value = false
      return
    }
    await loadEvents(newSession)
  }
  answer.value = ''
}, { immediate: true })

// ---- Incremental append via lastSessionEvent ----

watch(() => sessionStore.lastSessionEvent, (evt) => {
  if (!evt || !currentSession.value) return
  const agentName = currentSession.value.agent_name || currentSession.value.name
  const agentSessionId = currentSession.value.agent_session_id

  // 匹配当前 session 的事件（agent_session_id 可能尚未赋值的新 session）
  const isMatch = agentSessionId
    ? (evt.agent_name === agentName && evt.session_id === agentSessionId)
    : (evt.agent_name === agentName)  // 新 session 尚无 agent_session_id，按 agent_name 匹配
  if (!isMatch) return

  const parsed = parseEvent(evt.data)

  // 跳过不需要渲染的事件（session、action detected）
  if (parsed.renderType === 'skip') return

  // 用户发的邮件（email.received, sender == user）已在本地 optimistic 插入，跳过后端推送
  if (parsed.eventType === 'email' && parsed.eventName === 'received' && parsed.detail.sender === props.user_agent_name) {
    // 替换匹配的 placeholder（用 body_preview 匹配，替换为后端生成的真实数据）
    const phIdx = events.value.findIndex(e => e.detail?._isPlaceholder && e.detail.body_preview === parsed.detail.body_preview)
    if (phIdx !== -1) {
      events.value.splice(phIdx, 1, parsed)
    }
    return
  }

  events.value.push(parsed)
  nextTick(() => scrollToBottom())
})

// ---- Agent status watcher (bottom indicator only) ----

const previousHistoryLengths = ref({})

watch(() => agentStore.agents, (agents) => {
  if (!currentSession.value) return

  const sessionId = currentSession.value.session_id

  Object.entries(agents).forEach(([agentName, agentData]) => {
    if (agentData.current_user_session_id !== sessionId) return

    // Update current status indicator
    currentAgentStatuses.value[agentName] = {
      status: agentData.status || 'IDLE',
      agentName
    }

    // Track history length to avoid replay
    const history = agentData.status_history || []
    previousHistoryLengths.value[agentName] = history.length
  })
}, { deep: true })

// ---- Scroll ----

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// ---- Email send handlers (for EmailReply optimistic UI) ----

const handleEmailSendStarted = ({ placeholder }) => {
  // 本地 optimistic 插入用户消息（不等后端 roundtrip）
  events.value.push({
    id: placeholder.id || `placeholder-${Date.now()}`,
    timestamp: new Date().toISOString(),
    eventType: 'email',
    eventName: 'received',
    detail: {
      body_preview: placeholder.body || '',
      recipient: placeholder.recipient || '',
      sender: props.user_agent_name,
      subject: placeholder.subject || '',
      _isPlaceholder: true,
    },
    renderType: 'bubble-user',
  })
  nextTick(() => scrollToBottom())
}

const handleEmailSendFailed = ({ placeholderId }) => {
  const idx = events.value.findIndex(e => e.id === placeholderId)
  if (idx !== -1) {
    events.value.splice(idx, 1)
  }
}

const handleEmailSent = (payload) => {
  // 保留 placeholder 在 timeline 中，后端 email.received event 到达时会替换为真实数据
  // 如果发送失败，由 handleEmailSendFailed 处理
}

// ---- Ask user ----

const handleAgentQuestionSubmit = async () => {
  if (!answer.value.trim() || !currentSession.value) return
  const sessionId = currentSession.value.session_id

  try {
    await sessionStore.submitAskUserAnswer(sessionId, answer.value)
    answer.value = ''
  } catch (err) {
    console.error('Failed to submit answer:', err)
    alert('Failed to submit answer: ' + err.message)
  }
}
</script>

<template>
  <main class="chat-history">
    <!-- Toolbar -->
    <header v-if="currentSession" class="chat-history__toolbar">
      <div v-if="primaryAgentName" class="chat-history__partner">
        <div class="chat-history__partner-avatar">
          {{ primaryAgentName.charAt(0).toUpperCase() }}
        </div>
        <span class="chat-history__partner-name">{{ primaryAgentName }}</span>
      </div>
      <div class="chat-history__toolbar-actions">
        <button @click="currentSession && loadEvents(currentSession)" class="chat-history__toolbar-btn" title="Refresh">
          <MIcon name="refresh" />
        </button>
      </div>
    </header>

    <!-- Messages area -->
    <div ref="messagesContainer" class="chat-history__messages">
      <!-- No session selected -->
      <div v-if="!currentSession" class="chat-history__empty">
        <div class="chat-history__empty-icon">
          <MIcon name="message-circle" />
        </div>
        <p class="chat-history__empty-text">{{ t('emails.selectSession') }}</p>
      </div>

      <!-- Loading -->
      <div v-else-if="isLoading" class="chat-history__empty">
        <div class="chat-history__empty-icon chat-history__empty-icon--loading">
          <span class="animate-spin"><MIcon name="loader" /></span>
        </div>
        <p class="chat-history__empty-text">{{ t('sessions.loading') }}</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="chat-history__empty">
        <div class="chat-history__empty-icon chat-history__empty-icon--error">
          <MIcon name="alert-circle" />
        </div>
        <p class="chat-history__empty-text">{{ t('common.error') }}</p>
        <p class="chat-history__empty-hint">{{ error }}</p>
        <button @click="currentSession && loadEvents(currentSession)" class="chat-history__retry-btn">Retry</button>
      </div>

      <!-- Chat timeline -->
      <template v-else>
        <ChatMessage
          v-for="item in chatTimeline"
          :key="item.id"
          :message="item"
          :user_agent_name="user_agent_name"
          :agent-name="primaryAgentName"
        />

        <!-- Empty state -->
        <div v-if="!hasContent && Object.keys(currentAgentStatuses).length === 0" class="chat-history__empty">
          <div class="chat-history__empty-icon">
            <MIcon name="mail-off" />
          </div>
          <p class="chat-history__empty-text">{{ t('emails.noEmails') }}</p>
          <p class="chat-history__empty-hint">{{ t('emails.startConversation') }}</p>
        </div>
      </template>

      <!-- Live status indicator (refreshes in place, not accumulated) -->
      <div
        v-for="(statusInfo, agentName) in currentAgentStatuses"
        :key="agentName"
        v-show="statusInfo.status !== 'IDLE'"
        class="chat-status-indicator"
      >
        <span :class="['chat-status-indicator__icon', { 'chat-status-indicator__icon--spinning': statusInfo.status === 'THINKING' || statusInfo.status === 'WORKING' }]">
          <MIcon :name="statusInfo.status === 'THINKING' ? 'brain' : statusInfo.status === 'WORKING' ? 'loader' : statusInfo.status === 'WAITING_FOR_USER' ? 'message-circle' : statusInfo.status === 'PAUSED' ? 'player-pause' : statusInfo.status === 'ERROR' ? 'alert-circle' : 'circle'" />
        </span>
        <span class="chat-status-indicator__agent">{{ agentName }}</span>
        <span class="chat-status-indicator__label">
          {{ statusInfo.status === 'THINKING' ? 'thinking' : statusInfo.status === 'WORKING' ? 'working' : statusInfo.status === 'WAITING_FOR_USER' ? 'waiting for you' : statusInfo.status === 'PAUSED' ? 'paused' : statusInfo.status === 'ERROR' ? 'error' : '' }}
        </span>
      </div>
    </div>

    <!-- Ask user question form -->
    <div v-if="pendingQuestion" class="chat-history__bottom">
      <div class="chat-history__question-form">
        <div class="chat-history__question-header">
          <MIcon name="message-circle" />
          <span class="chat-history__question-title">{{ pendingQuestion.agent_name }} {{ t('emails.hasQuestion') }}</span>
        </div>
        <p class="chat-history__question-text">{{ pendingQuestion.question }}</p>
        <textarea
          v-model="answer"
          rows="2"
          :placeholder="t('emails.questionPlaceholder')"
          class="chat-history__question-input"
        />
        <div class="chat-history__question-actions">
          <button
            @click="handleAgentQuestionSubmit"
            :disabled="!answer.trim()"
            class="chat-history__question-btn"
          >
            {{ t('common.submit') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Reply input -->
    <div v-else class="chat-history__bottom">
      <EmailReply
        :current-session="currentSession"
        :emails="events"
        @send-started="handleEmailSendStarted"
        @sent="handleEmailSent"
        @send-failed="handleEmailSendFailed"
      />
    </div>
  </main>
</template>

<style scoped>
.chat-history {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--neutral-50);
  overflow: hidden;
}

/* Toolbar */
.chat-history__toolbar {
  height: 48px;
  background: white;
  border-bottom: 1px solid var(--neutral-200);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-md);
  flex-shrink: 0;
}

.chat-history__partner {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.chat-history__partner-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--accent);
  color: white;
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-history__partner-name {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--neutral-800);
}

.chat-history__toolbar-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.chat-history__toolbar-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--neutral-500);
  font-size: var(--icon-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-history__toolbar-btn:hover {
  background: var(--neutral-100);
  color: var(--neutral-700);
}

/* Messages */
.chat-history__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md) var(--spacing-lg);
  display: flex;
  flex-direction: column;
}

/* Empty states */
.chat-history__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.chat-history__empty-icon {
  width: 64px;
  height: 64px;
  background: var(--neutral-100);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: var(--neutral-300);
  margin-bottom: var(--spacing-md);
}

.chat-history__empty-icon--loading {
  background: var(--parchment-50);
  color: var(--accent);
}

.chat-history__empty-icon--error {
  background: var(--error-50);
  color: var(--error-500);
}

.chat-history__empty-text {
  font-size: var(--font-base);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
  margin: 0 0 var(--spacing-xs) 0;
}

.chat-history__empty-hint {
  font-size: var(--font-sm);
  color: var(--neutral-400);
  margin: 0 0 var(--spacing-md) 0;
}

.chat-history__retry-btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
}

/* Bottom area */
.chat-history__bottom {
  flex-shrink: 0;
  background: var(--parchment-50);
  padding: var(--spacing-md);
}

/* Question form */
.chat-history__question-form {
  padding: var(--spacing-lg);
  background: var(--parchment-50);
  border: 2px solid var(--accent);
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 12px rgba(194, 59, 34, 0.15);
}

.chat-history__question-form:focus-within {
  border-color: var(--parchment-300);
  box-shadow: none;
}

.chat-history__question-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.chat-history__question-header .m-icon {
  font-size: var(--icon-md);
  color: var(--accent);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1 }
  50% { opacity: 0.5 }
}

.chat-history__question-title {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--ink-900);
}

.chat-history__question-text {
  font-size: var(--font-sm);
  color: var(--ink-700);
  margin: 0 0 var(--spacing-sm) 0;
  line-height: var(--leading-relaxed);
}

.chat-history__question-input {
  width: 100%;
  padding: var(--spacing-sm);
  background: var(--parchment-50);
  border: 1px solid var(--parchment-300);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  color: var(--ink-700);
  resize: none;
  margin-bottom: var(--spacing-sm);
  transition: all var(--duration-base) var(--ease-out);
}

.chat-history__question-input:focus {
  outline: none;
  border-color: var(--accent);
}

.chat-history__question-actions {
  display: flex;
  justify-content: flex-end;
}

.chat-history__question-btn {
  padding: var(--spacing-xs) var(--spacing-lg);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: var(--font-medium);
  cursor: pointer;
  background: var(--ink-900);
  color: var(--parchment-50);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  transition: all var(--duration-base) var(--ease-out);
}

.chat-history__question-btn:hover:not(:disabled) {
  background: var(--accent);
}

.chat-history__question-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Spin animation */
.animate-spin {
  animation: spin 1s linear infinite;
  display: flex;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}

/* Live status indicator */
.chat-status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  margin-top: var(--spacing-sm);
  background: var(--neutral-50);
  border: 1px solid var(--neutral-100);
  border-radius: var(--radius-sm);
  font-size: var(--font-xs);
  color: var(--neutral-400);
  animation: fadeIn 200ms var(--ease-out);
  flex-shrink: 0;
}

.chat-status-indicator__icon {
  display: flex;
  align-items: center;
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

.chat-status-indicator__icon--spinning {
  animation: spin 1.2s linear infinite;
}

.chat-status-indicator__agent {
  font-weight: var(--font-semibold);
  color: var(--neutral-500);
}

.chat-status-indicator__label {
  color: var(--neutral-400);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px) }
  to { opacity: 1; transform: translateY(0) }
}
</style>
