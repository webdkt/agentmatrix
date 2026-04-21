<script setup>
import { ref, computed, provide, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useChatTimeline } from '@/composables/useChatTimeline'
import { useCollabFile } from '@/composables/useCollabFile'
import { agentAPI } from '@/api/agent'
import ChatMessage from './ChatMessage.vue'
import CollabInput from './CollabInput.vue'
import AgentTerminal from './AgentTerminal.vue'
import TaskFilesPanel from './TaskFilesPanel.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  userAgentName: {
    type: String,
    default: 'User'
  }
})

const { t } = useI18n()

// ---- Chat timeline (from composable) ----
const {
  events,
  isLoading,
  error,
  messagesContainer,
  answer,
  currentAgentStatuses,
  currentSession,
  chatTimeline,
  hasContent,
  pendingQuestion,
  primaryAgentName,
  loadEvents,
  handleEmailSendStarted,
  handleEmailSendFailed,
  handleEmailSent,
  handleAgentQuestionSubmit,
} = useChatTimeline({ userAgentName: () => props.userAgentName })

// ---- Agent name derived from session ----
const currentAgentName = computed(() => {
  if (!currentSession.value) return null
  return currentSession.value.agent_name || currentSession.value.name || null
})

const currentSessionId = computed(() => {
  return currentSession.value?.session_id || null
})

// ---- Collab file ----
const { collabFile, collabFileName, openCollabFile } = useCollabFile({ agentName: currentAgentName })

// ---- Collab draft message (provide/inject for cross-component communication) ----
const collabDraftMessage = ref('')
provide('collabDraftMessage', collabDraftMessage)

// ---- UI State ----
const showTaskFiles = ref(false)
const showTerminal = ref(false)
const terminalMinimized = ref(true)
const isCollabMode = ref(false)

// Middle area ref for sizing calculations
const middleArea = ref(null)
const middleSize = ref({ width: 800, height: 600 })

const updateMiddleSize = () => {
  if (middleArea.value) {
    middleSize.value = {
      width: middleArea.value.clientWidth,
      height: middleArea.value.clientHeight,
    }
  }
}

onMounted(() => {
  updateMiddleSize()
  window.addEventListener('resize', updateMiddleSize)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateMiddleSize)
})

// ---- Terminal toggle: hidden → minimized → expanded → hidden ----
const toggleTerminal = () => {
  if (!showTerminal.value) {
    // Hidden → show minimized
    showTerminal.value = true
    terminalMinimized.value = true
  } else if (terminalMinimized.value) {
    // Minimized → expand
    terminalMinimized.value = false
  } else {
    // Expanded → hide
    showTerminal.value = false
  }
}

const handleTerminalClose = () => {
  // Close button: go to minimized (not hidden)
  terminalMinimized.value = true
}

// ---- Collab mode toggle ----
const toggleCollabMode = async () => {
  if (!currentAgentName.value) return
  isCollabMode.value = !isCollabMode.value
  try {
    await agentAPI.toggleCollabMode(currentAgentName.value, isCollabMode.value)
  } catch (err) {
    console.error('Failed to toggle collab mode:', err)
    isCollabMode.value = !isCollabMode.value
  }
}

// ---- Task files panel width ----
const taskFilesWidth = computed(() => {
  return Math.round(middleSize.value.width * 0.5)
})
</script>

<template>
  <div class="agent-session-panel">
    <!-- Top Bar -->
    <header v-if="currentSession" class="agent-session-panel__topbar">
      <div class="agent-session-panel__agent-info">
        <div class="agent-session-panel__avatar">
          {{ primaryAgentName ? primaryAgentName.charAt(0).toUpperCase() : '?' }}
        </div>
        <span v-if="primaryAgentName" class="agent-session-panel__agent-name">{{ primaryAgentName }}</span>
        <!-- Live status indicator in top bar -->
        <template v-for="(statusInfo, agentName) in currentAgentStatuses" :key="agentName">
          <span
            v-show="statusInfo.status !== 'IDLE'"
            class="agent-session-panel__status"
          >
            <span :class="['agent-session-panel__status-icon', { 'agent-session-panel__status-icon--spinning': statusInfo.status === 'THINKING' || statusInfo.status === 'WORKING' }]">
              <MIcon :name="statusInfo.status === 'THINKING' ? 'brain' : statusInfo.status === 'WORKING' ? 'loader' : statusInfo.status === 'WAITING_FOR_USER' ? 'message-circle' : statusInfo.status === 'PAUSED' ? 'player-pause' : statusInfo.status === 'ERROR' ? 'alert-circle' : 'circle'" />
            </span>
            <span class="agent-session-panel__status-label">
              {{ statusInfo.status === 'THINKING' ? 'thinking' : statusInfo.status === 'WORKING' ? 'working' : statusInfo.status === 'WAITING_FOR_USER' ? 'waiting' : statusInfo.status === 'PAUSED' ? 'paused' : statusInfo.status === 'ERROR' ? 'error' : '' }}
            </span>
          </span>
        </template>
      </div>

      <div class="agent-session-panel__toolbar">
        <!-- Collab Mode toggle -->
        <button
          class="agent-session-panel__toolbar-btn"
          :class="{ 'agent-session-panel__toolbar-btn--active': isCollabMode }"
          @click="toggleCollabMode"
          title="Toggle Collab Mode"
        >
          <MIcon name="users" />
        </button>

        <!-- Collabring File indicator -->
        <button
          class="agent-session-panel__toolbar-btn"
          :class="{
            'agent-session-panel__toolbar-btn--active': collabFile,
            'agent-session-panel__toolbar-btn--disabled': !collabFile,
          }"
          @click="openCollabFile"
          :disabled="!collabFileName"
          :title="collabFileName || 'No collab file'"
        >
          <MIcon name="file" />
          <span v-if="collabFile" class="agent-session-panel__indicator-dot" />
        </button>

        <!-- Task Files toggle -->
        <button
          class="agent-session-panel__toolbar-btn"
          :class="{ 'agent-session-panel__toolbar-btn--active': showTaskFiles }"
          @click="showTaskFiles = !showTaskFiles"
          title="Task Files"
        >
          <MIcon name="folder" />
        </button>

        <!-- Terminal toggle -->
        <button
          class="agent-session-panel__toolbar-btn"
          :class="{ 'agent-session-panel__toolbar-btn--active': showTerminal }"
          @click="toggleTerminal"
          title="Terminal"
        >
          <MIcon name="terminal" />
        </button>

        <!-- Refresh -->
        <button
          class="agent-session-panel__toolbar-btn"
          @click="currentSession && loadEvents(currentSession)"
          title="Refresh"
        >
          <MIcon name="refresh" />
        </button>
      </div>
    </header>

    <!-- Middle Area -->
    <div ref="middleArea" class="agent-session-panel__middle">
      <!-- Chat messages -->
      <div ref="messagesContainer" class="agent-session-panel__messages">
        <!-- No session selected -->
        <div v-if="!currentSession" class="agent-session-panel__empty">
          <div class="agent-session-panel__empty-icon">
            <MIcon name="message-circle" />
          </div>
          <p class="agent-session-panel__empty-text">{{ t('emails.selectSession') }}</p>
        </div>

        <!-- Loading -->
        <div v-else-if="isLoading" class="agent-session-panel__empty">
          <div class="agent-session-panel__empty-icon agent-session-panel__empty-icon--loading">
            <span class="animate-spin"><MIcon name="loader" /></span>
          </div>
          <p class="agent-session-panel__empty-text">{{ t('sessions.loading') }}</p>
        </div>

        <!-- Error -->
        <div v-else-if="error" class="agent-session-panel__empty">
          <div class="agent-session-panel__empty-icon agent-session-panel__empty-icon--error">
            <MIcon name="alert-circle" />
          </div>
          <p class="agent-session-panel__empty-text">{{ t('common.error') }}</p>
          <p class="agent-session-panel__empty-hint">{{ error }}</p>
          <button @click="currentSession && loadEvents(currentSession)" class="agent-session-panel__retry-btn">Retry</button>
        </div>

        <!-- Chat timeline -->
        <template v-else>
          <ChatMessage
            v-for="item in chatTimeline"
            :key="item.id"
            :message="item"
            :user_agent_name="userAgentName"
            :agent-name="primaryAgentName"
          />

          <!-- Empty state -->
          <div v-if="!hasContent && Object.keys(currentAgentStatuses).length === 0" class="agent-session-panel__empty">
            <div class="agent-session-panel__empty-icon">
              <MIcon name="mail-off" />
            </div>
            <p class="agent-session-panel__empty-text">{{ t('emails.noEmails') }}</p>
            <p class="agent-session-panel__empty-hint">{{ t('emails.startConversation') }}</p>
          </div>
        </template>

        <!-- Inline status indicator (below messages, above bottom) -->
        <div
          v-for="(statusInfo, agentName) in currentAgentStatuses"
          :key="agentName"
          v-show="statusInfo.status !== 'IDLE'"
          class="agent-session-panel__status-indicator"
        >
          <span :class="['agent-session-panel__status-indicator-icon', { 'agent-session-panel__status-indicator-icon--spinning': statusInfo.status === 'THINKING' || statusInfo.status === 'WORKING' }]">
            <MIcon :name="statusInfo.status === 'THINKING' ? 'brain' : statusInfo.status === 'WORKING' ? 'loader' : statusInfo.status === 'WAITING_FOR_USER' ? 'message-circle' : statusInfo.status === 'PAUSED' ? 'player-pause' : statusInfo.status === 'ERROR' ? 'alert-circle' : 'circle'" />
          </span>
          <span class="agent-session-panel__status-indicator-agent">{{ agentName }}</span>
          <span class="agent-session-panel__status-indicator-label">
            {{ statusInfo.status === 'THINKING' ? 'thinking' : statusInfo.status === 'WORKING' ? 'working' : statusInfo.status === 'WAITING_FOR_USER' ? 'waiting for you' : statusInfo.status === 'PAUSED' ? 'paused' : statusInfo.status === 'ERROR' ? 'error' : '' }}
          </span>
        </div>
      </div>

      <!-- Task Files Slide-Out (from right edge) -->
      <Transition name="slide-right">
        <TaskFilesPanel
          v-if="showTaskFiles && currentAgentName && currentSessionId"
          :agent-name="currentAgentName"
          :session-id="currentSessionId"
          :width="taskFilesWidth"
          @close="showTaskFiles = false"
        />
      </Transition>

      <!-- Floating Terminal -->
      <AgentTerminal
        v-if="showTerminal && currentAgentName"
        :agent-name="currentAgentName"
        :minimized="terminalMinimized"
        :parent-width="middleSize.width"
        :parent-height="middleSize.height"
        @toggle-minimize="terminalMinimized = !terminalMinimized"
        @close="handleTerminalClose"
      />
    </div>

    <!-- Bottom Input Area -->
    <div class="agent-session-panel__bottom">
      <!-- Ask User Question form -->
      <div v-if="pendingQuestion" class="agent-session-panel__ask-user">
        <div class="agent-session-panel__ask-user-form">
          <div class="agent-session-panel__ask-user-header">
            <MIcon name="message-circle" />
            <span class="agent-session-panel__ask-user-title">{{ pendingQuestion.agent_name }} {{ t('emails.hasQuestion') }}</span>
          </div>
          <p class="agent-session-panel__ask-user-text">{{ pendingQuestion.question }}</p>
          <textarea
            v-model="answer"
            rows="2"
            :placeholder="t('emails.questionPlaceholder')"
            class="agent-session-panel__ask-user-input"
          />
          <div class="agent-session-panel__ask-user-actions">
            <button
              @click="handleAgentQuestionSubmit"
              :disabled="!answer.trim()"
              class="agent-session-panel__ask-user-btn"
            >
              {{ t('common.submit') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Normal Input -->
      <CollabInput
        v-else
        :current-session="currentSession"
        :emails="events"
        @send-started="handleEmailSendStarted"
        @sent="handleEmailSent"
        @send-failed="handleEmailSendFailed"
      />
    </div>
  </div>
</template>

<style scoped>
.agent-session-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--neutral-50);
}

/* ---- Top Bar ---- */
.agent-session-panel__topbar {
  height: 48px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-md);
  background: white;
  border-bottom: 1px solid var(--neutral-200);
}

.agent-session-panel__agent-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.agent-session-panel__avatar {
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

.agent-session-panel__agent-name {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--neutral-800);
}

.agent-session-panel__status {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--neutral-50);
  border: 1px solid var(--neutral-100);
  border-radius: var(--radius-sm);
  font-size: 10px;
  color: var(--neutral-400);
  animation: fadeIn 200ms var(--ease-out);
}

.agent-session-panel__status-icon {
  display: flex;
  align-items: center;
  font-size: var(--font-xs);
  color: var(--neutral-400);
}

.agent-session-panel__status-icon--spinning {
  animation: spin 1.2s linear infinite;
}

.agent-session-panel__status-label {
  color: var(--neutral-400);
}

.agent-session-panel__toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
}

.agent-session-panel__toolbar-btn {
  position: relative;
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--neutral-400);
  font-size: var(--icon-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.agent-session-panel__toolbar-btn:hover {
  background: var(--neutral-100);
  color: var(--neutral-700);
}

.agent-session-panel__toolbar-btn--active {
  background: var(--parchment-100);
  color: var(--accent);
}

.agent-session-panel__toolbar-btn--active:hover {
  background: var(--parchment-200);
}

.agent-session-panel__toolbar-btn--disabled {
  opacity: 0.35;
}

.agent-session-panel__toolbar-btn:disabled {
  cursor: default;
  opacity: 0.3;
}

.agent-session-panel__toolbar-btn:disabled:hover {
  background: transparent;
}

.agent-session-panel__indicator-dot {
  position: absolute;
  top: 5px;
  right: 5px;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success-500, #22c55e);
  border: 1.5px solid white;
}

/* ---- Middle Area ---- */
.agent-session-panel__middle {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  min-height: 0;
}

.agent-session-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md) var(--spacing-lg);
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* ---- Empty States ---- */
.agent-session-panel__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.agent-session-panel__empty-icon {
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

.agent-session-panel__empty-icon--loading {
  background: var(--parchment-50);
  color: var(--accent);
}

.agent-session-panel__empty-icon--error {
  background: var(--error-50);
  color: var(--error-500);
}

.agent-session-panel__empty-text {
  font-size: var(--font-base);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
  margin: 0 0 var(--spacing-xs) 0;
}

.agent-session-panel__empty-hint {
  font-size: var(--font-sm);
  color: var(--neutral-400);
  margin: 0 0 var(--spacing-md) 0;
}

.agent-session-panel__retry-btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
}

/* ---- Status Indicator (below messages) ---- */
.agent-session-panel__status-indicator {
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
  align-self: flex-start;
}

.agent-session-panel__status-indicator-icon {
  display: flex;
  align-items: center;
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

.agent-session-panel__status-indicator-icon--spinning {
  animation: spin 1.2s linear infinite;
}

.agent-session-panel__status-indicator-agent {
  font-weight: var(--font-semibold);
  color: var(--neutral-500);
}

.agent-session-panel__status-indicator-label {
  color: var(--neutral-400);
}

/* ---- Bottom Input Area ---- */
.agent-session-panel__bottom {
  flex-shrink: 0;
  background: var(--parchment-50);
  padding: var(--spacing-md);
}

/* ---- Ask User Question ---- */
.agent-session-panel__ask-user-form {
  padding: var(--spacing-lg);
  background: var(--parchment-50);
  border: 2px solid var(--accent);
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 12px rgba(194, 59, 34, 0.15);
}

.agent-session-panel__ask-user-form:focus-within {
  border-color: var(--parchment-300);
  box-shadow: none;
}

.agent-session-panel__ask-user-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.agent-session-panel__ask-user-header .m-icon {
  font-size: var(--icon-md);
  color: var(--accent);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.agent-session-panel__ask-user-title {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--ink-900);
}

.agent-session-panel__ask-user-text {
  font-size: var(--font-sm);
  color: var(--ink-700);
  margin: 0 0 var(--spacing-sm) 0;
  line-height: var(--leading-relaxed);
}

.agent-session-panel__ask-user-input {
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

.agent-session-panel__ask-user-input:focus {
  outline: none;
  border-color: var(--accent);
}

.agent-session-panel__ask-user-actions {
  display: flex;
  justify-content: flex-end;
}

.agent-session-panel__ask-user-btn {
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

.agent-session-panel__ask-user-btn:hover:not(:disabled) {
  background: var(--accent);
}

.agent-session-panel__ask-user-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ---- Slide-out transition for TaskFilesPanel ---- */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: transform 0.25s var(--ease-out);
  will-change: transform;
}

.slide-right-enter-from,
.slide-right-leave-to {
  transform: translateX(100%);
}

/* ---- Animations ---- */
.animate-spin {
  animation: spin 1s linear infinite;
  display: flex;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}

@keyframes pulse {
  0%, 100% { opacity: 1 }
  50% { opacity: 0.5 }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px) }
  to { opacity: 1; transform: translateY(0) }
}
</style>
