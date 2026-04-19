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
const emails = ref([])
const contentMessages = ref([])  // Content-type status messages that stay in timeline
const previousStatuses = ref({})
const previousHistoryLengths = ref({})  // Track status_history length per agent
const isLoading = ref(false)
const error = ref(null)
const messagesContainer = ref(null)
const answer = ref('')

// Current agent status for the status indicator (always reflects latest)
const currentAgentStatuses = ref({})

// ---- Computed ----
const currentSession = computed(() => sessionStore.currentSession)

// Primary chat partner: derived from the first email in the session
// If first email is from user → the recipient is the primary partner
// If first email is from agent → the sender is the primary partner
const primaryChatPartner = computed(() => {
  if (emails.value.length === 0) return null
  const first = emails.value[0]
  if (first.is_from_user) {
    return first.recipient || null
  }
  return first.sender || null
})

const chatTimeline = computed(() => {
  const items = []

  emails.value.forEach(email => {
    items.push({
      type: 'email',
      id: `email-${email.id}`,
      timestamp: email.timestamp,
      data: email
    })
  })

  contentMessages.value.forEach(msg => {
    items.push({
      type: 'status',
      id: msg.id,
      timestamp: msg.timestamp,
      data: msg
    })
  })

  items.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
  return items
})

const hasContent = computed(() => chatTimeline.value.length > 0)

const pendingQuestion = computed(() => {
  if (!currentSession.value) return null
  return sessionStore.getPendingQuestion(currentSession.value.session_id)
})

const hasPlaceholderLast = computed(() => {
  if (emails.value.length === 0) return false
  return !!emails.value[emails.value.length - 1]._isPlaceholder
})

// ---- Email loading ----

const loadEmails = async (sessionId) => {
  if (!sessionId) return

  const isInitialLoad = emails.value.length === 0
  if (isInitialLoad) {
    isLoading.value = true
  }
  error.value = null

  try {
    const result = await sessionAPI.getEmails(sessionId)
    emails.value = result.emails || result.sessions || []
    sessionStore.markSessionRead(sessionId)
  } catch (err) {
    error.value = err.message
    console.error('Failed to load emails:', err)
  } finally {
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}

const refreshEmails = async () => {
  if (currentSession.value) {
    await loadEmails(currentSession.value.session_id)
  }
}

// ---- Session watcher ----

watch(currentSession, async (newSession) => {
  // Clear transient state on session change
  contentMessages.value = []
  previousStatuses.value = {}
  previousHistoryLengths.value = {}
  currentAgentStatuses.value = {}

  if (newSession) {
    if (newSession._isPlaceholder) {
      emails.value = []
      isLoading.value = false
      return
    }
    await loadEmails(newSession.session_id)
  } else {
    emails.value = []
  }
  answer.value = ''
}, { immediate: true })

// Status label patterns — these are state indicators, not content
const STATUS_LABEL_PATTERNS = [
  /^Thinking\.\.\.$/i,
  /^开始执行:/,
  /^开始执行 /,
  /^已完成/,
  /^已完成执行/,
  /^已完成所有操作/,
  /^Agent已暂停/,
  /^Agent已从暂停状态恢复/,
  /^Agent已停止/,
  /^⏸️/,
  /^▶️/,
  /^🛑/,
]

function isStatusLabel(message) {
  if (!message) return true
  const trimmed = message.trim()
  return STATUS_LABEL_PATTERNS.some(re => re.test(trimmed))
}

// ---- Agent status watcher ----

watch(() => agentStore.agents, (agents) => {
  if (!currentSession.value) return

  const sessionId = currentSession.value.session_id

  Object.entries(agents).forEach(([agentName, agentData]) => {
    // Only track agents working on the current session
    if (agentData.current_user_session_id !== sessionId) return

    // --- 1. Update current status indicator ---
    currentAgentStatuses.value[agentName] = {
      status: agentData.status || 'IDLE',
      agentName
    }

    // --- 2. Detect new status_history entries (content messages) ---
    const history = agentData.status_history || []
    const prevLength = previousHistoryLengths.value[agentName] || 0
    previousHistoryLengths.value[agentName] = history.length

    // On first load (prevLength === 0), don't replay old history
    if (prevLength === 0) return

    // New entries appended since last update
    if (history.length > prevLength) {
      const newEntries = history.slice(prevLength)
      newEntries.forEach(entry => {
        if (!isStatusLabel(entry.message)) {
          contentMessages.value.push({
            type: 'status',
            id: `content-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
            timestamp: entry.timestamp || new Date().toISOString(),
            agentName,
            status: agentData.status,
            message: entry.message,
            isContent: true
          })
        }
      })
      nextTick(() => scrollToBottom())
    }

    // --- 3. Track status transitions ---
    previousStatuses.value[agentName] = agentData.status
  })
}, { deep: true })

// ---- Scroll ----

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// ---- Email send handlers ----

const handleEmailSendStarted = ({ placeholder }) => {
  emails.value.push(placeholder)
  nextTick(() => scrollToBottom())
}

const handleEmailSendFailed = ({ placeholderId }) => {
  const idx = emails.value.findIndex(e => e.id === placeholderId)
  if (idx !== -1) {
    emails.value.splice(idx, 1)
  }
}

const handleEmailSent = (payload) => {
  const response = payload?.response || payload
  const placeholderId = payload?.placeholderId
  const email = response?.email

  if (email) {
    if (placeholderId) {
      const idx = emails.value.findIndex(e => e.id === placeholderId)
      if (idx !== -1) {
        emails.value.splice(idx, 1, email)
        return
      }
    }
    // Session guard
    const emailSessionId = email.task_id || email.recipient_session_id
    const currentSessionId = currentSession.value?.session_id
    if (emailSessionId && currentSessionId && emailSessionId !== currentSessionId) {
      return
    }
    emails.value.push(email)
    nextTick(() => scrollToBottom())
  }
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
      <div v-if="primaryChatPartner" class="chat-history__partner">
        <div class="chat-history__partner-avatar">
          {{ primaryChatPartner.charAt(0).toUpperCase() }}
        </div>
        <span class="chat-history__partner-name">{{ primaryChatPartner }}</span>
      </div>
      <div class="chat-history__toolbar-actions">
        <button @click="refreshEmails" class="chat-history__toolbar-btn" title="Refresh">
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
        <button @click="refreshEmails" class="chat-history__retry-btn">Retry</button>
      </div>

      <!-- Chat timeline -->
      <template v-else>
        <ChatMessage
          v-for="item in chatTimeline"
          :key="item.id"
          :message="item"
          :user_agent_name="user_agent_name"
          :primary-chat-partner="primaryChatPartner"
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
        :emails="emails"
        :is-locked="hasPlaceholderLast"
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
