<script setup>
import { ref, computed, provide, inject, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { useAgentStore } from '@/stores/agent'
import { useWebSocketStore } from '@/stores/websocket'
import { useChatTimeline } from '@/composables/useChatTimeline'
import { useCollabFile } from '@/composables/useCollabFile'
import { useTaskFiles } from '@/composables/useTaskFiles'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { agentAPI } from '@/api/agent'
import ChatMessage from './ChatMessage.vue'
import CollabInput from './CollabInput.vue'
import CollabStartPanel from './CollabStartPanel.vue'
import NewTaskPanel from './NewTaskPanel.vue'
import TaskSendingOverlay from './TaskSendingOverlay.vue'
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
const sessionStore = useSessionStore()
const agentStore = useAgentStore()
const websocketStore = useWebSocketStore()

// ---- Collab Wizard ----
const wizard = inject('collabWizard')

// ---- Chat timeline (from composable) ----
const {
  events,
  isLoading,
  isLoadingMore,
  error,
  messagesContainer,
  answer,
  currentSession,
  chatTimeline,
  hasContent,
  hasMoreEvents,
  pendingQuestion,
  primaryAgentName,
  loadEvents,
  onScroll,
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

// ---- Primary agent status (直接从全局 store 读) ----
const primaryAgentStatus = computed(() => {
  if (!primaryAgentName.value) return null
  const agent = agentStore.agents[primaryAgentName.value]
  if (!agent) return { status: 'IDLE', isOnCurrentSession: true, otherSessionId: null }
  const status = agent.status || 'IDLE'
  // 只有非 IDLE 状态才判断是否在处理其他工作
  const isActive = status !== 'IDLE'
  const isOnCurrentSession = !isActive || !currentSession.value || agent.current_session_id === currentSession.value.session_id
  return {
    status,
    isOnCurrentSession,
    otherSessionId: !isOnCurrentSession ? agent.current_user_session_id : null,
  }
})

const currentSessionId = computed(() => {
  return currentSession.value?.session_id || null
})

// ---- Navigate to the session an agent is working on ----
const navigateToAgentSession = (otherSessionId) => {
  if (!otherSessionId) return
  const session = sessionStore.sessions.find(s => s.session_id === otherSessionId)
  if (session) {
    sessionStore.selectSession(session)
  }
}

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

// ---- Task files (single instance shared with TaskFilesPanel) ----
const taskFiles = useTaskFiles({
  agentName: () => currentAgentName.value,
  sessionId: () => currentSessionId.value,
})

// ---- Drag-drop file upload (single global listener) ----
const isDragging = ref(false)
const dropZone = ref(null) // 'task-files' | null
let unlistenDragDrop = null

function getDropZone(position) {
  if (!position) return null
  const clientX = position.x / window.devicePixelRatio
  const clientY = position.y / window.devicePixelRatio
  const el = document.elementFromPoint(clientX, clientY)
  if (!el) return null
  const zone = el.closest('[data-drop-zone]')
  return zone?.getAttribute('data-drop-zone') || null
}

onMounted(async () => {
  updateMiddleSize()
  window.addEventListener('resize', updateMiddleSize)

  setupDragDrop()
})

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

onUnmounted(() => {
  window.removeEventListener('resize', updateMiddleSize)
  if (unlistenDragDrop) unlistenDragDrop()
})

// ---- Drag-drop setup (conditional on session mode) ----
async function setupDragDrop() {
  if (unlistenDragDrop) return // already listening
  const webview = await getCurrentWebview()
  unlistenDragDrop = await webview.onDragDropEvent(async (event) => {
    // Skip if wizard is active
    if (wizard.isActive.value) return

    if (event.payload.type === 'over') {
      isDragging.value = true
      dropZone.value = getDropZone(event.payload.position)
    } else if (event.payload.type === 'drop') {
      isDragging.value = false
      dropZone.value = null
      const paths = event.payload.paths
      if (!paths?.length || !currentAgentName.value || !currentSessionId.value) return

      const zone = getDropZone(event.payload.position)
      const fileNames = []

      if (zone === 'task-files') {
        const { fileNames: copied } = await taskFiles.copyFiles(paths, taskFiles.currentDir.value)
        fileNames.push(...copied)
        if (fileNames.length > 0) {
          const rel = taskFiles.relativePath.value
          const containerDir = rel ? `~/current_task${rel}` : '~/current_task'
          const fileList = fileNames.map(n => `- ${n}`).join('\n')
          const draftLine = `已复制以下文件到 \`${containerDir}\` 目录，你看一下：\n${fileList}\n`
          collabDraftMessage.value = collabDraftMessage.value
            ? collabDraftMessage.value + '\n' + draftLine
            : draftLine
        }
      } else {
        const { fileNames: copied } = await taskFiles.copyFiles(paths)
        fileNames.push(...copied)
        if (fileNames.length > 0) {
          showTaskFiles.value = true
          const fileList = fileNames.map(n => `- ${n}`).join('\n')
          const draftLine = `已复制以下文件到 \`~/current_task\` 目录，你看一下：\n${fileList}\n`
          collabDraftMessage.value = collabDraftMessage.value
            ? collabDraftMessage.value + '\n' + draftLine
            : draftLine
        }
      }
    } else {
      isDragging.value = false
      dropZone.value = null
    }
  })
}

function teardownDragDrop() {
  if (unlistenDragDrop) {
    unlistenDragDrop()
    unlistenDragDrop = null
  }
}

// Manage drag-drop lifecycle based on wizard state
watch(() => wizard.isActive, (active) => {
  if (active) {
    teardownDragDrop()
  } else {
    setupDragDrop()
  }
})

// ---- Wizard event handlers ----
const handleAgentSelected = (agent) => {
  wizard.selectAgent(agent)
}

const handleTaskSendStarted = (emailData) => {
  wizard.startSending(emailData.recipient)
}

const handleTaskSent = (_response) => {
  // Session will arrive via NEW_USER_SESSION — nothing to do here
}

const handleTaskSendFailed = ({ error }) => {
  console.error('Task send failed:', error)
  // Go back to task input so user can retry
  wizard.wizardStep = 'new-task'
}

// ---- NEW_USER_SESSION detection during wizard sending phase ----
let lastSessionCount = sessionStore.sessions.length

watch(() => sessionStore.sessions.length, (newLen, oldLen) => {
  if (wizard.wizardStep.value !== 'sending') {
    lastSessionCount = newLen
    return
  }
  if (newLen <= oldLen) return

  // A new session appeared — find one matching our target agent
  const targetAgent = wizard.sendTargetAgentName.value
  if (!targetAgent) return

  // Look for the newest session matching the agent
  const newSession = sessionStore.sessions.find(s =>
    s.agent_name === targetAgent && !s._isPlaceholder
  )
  if (newSession) {
    sessionStore.selectSession(newSession)
    wizard.finishWizard()
  }
  lastSessionCount = newLen
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
    <!-- Wizard mode / No session selected -->
    <template v-if="wizard.isActive.value || !currentSession">
      <CollabStartPanel
        v-if="wizard.wizardStep.value === 'pick-agent' || (!wizard.isActive.value && !currentSession)"
        @select-agent="handleAgentSelected"
      />
      <NewTaskPanel
        v-else-if="wizard.wizardStep.value === 'new-task'"
        :agent="wizard.selectedAgent.value"
        @back="wizard.goBack()"
        @send-started="handleTaskSendStarted"
        @sent="handleTaskSent"
        @send-failed="handleTaskSendFailed"
      />
      <TaskSendingOverlay
        v-else-if="wizard.wizardStep.value === 'sending'"
        :agent-name="wizard.sendTargetAgentName.value"
      />
    </template>

    <!-- Session mode -->
    <template v-else>
    <!-- Top Bar -->
    <header v-if="currentSession" class="agent-session-panel__topbar">
      <div class="agent-session-panel__agent-info">
        <div class="agent-session-panel__avatar">
          {{ primaryAgentName ? primaryAgentName.charAt(0).toUpperCase() : '?' }}
        </div>
        <span v-if="primaryAgentName" class="agent-session-panel__agent-name">{{ primaryAgentName }}</span>
        <!-- Live status indicator in top bar -->
        <span
          v-if="primaryAgentStatus"
          class="agent-session-panel__status"
          :class="{
            'agent-session-panel__status--idle': primaryAgentStatus.status === 'IDLE',
            'agent-session-panel__status--clickable': primaryAgentStatus.otherSessionId,
          }"
          @click="navigateToAgentSession(primaryAgentStatus.otherSessionId)"
        >
          <span :class="['agent-session-panel__status-icon', { 'agent-session-panel__status-icon--spinning': primaryAgentStatus.status === 'THINKING' || primaryAgentStatus.status === 'WORKING' }]">
            <MIcon :name="primaryAgentStatus.status === 'THINKING' ? 'brain' : primaryAgentStatus.status === 'WORKING' ? 'loader' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'message-circle' : primaryAgentStatus.status === 'PAUSED' ? 'player-pause' : primaryAgentStatus.status === 'ERROR' ? 'alert-circle' : 'circle-check'" />
          </span>
          <span class="agent-session-panel__status-label">
            <template v-if="primaryAgentStatus.isOnCurrentSession">
              {{ primaryAgentStatus.status === 'THINKING' ? 'thinking' : primaryAgentStatus.status === 'WORKING' ? 'working' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'waiting' : primaryAgentStatus.status === 'PAUSED' ? 'paused' : primaryAgentStatus.status === 'ERROR' ? 'error' : 'idle' }}
            </template>
            <template v-else>
              正在处理其他工作
              <MIcon v-if="primaryAgentStatus.otherSessionId" name="arrow-right" class="agent-session-panel__status-jump" />
            </template>
          </span>
        </span>
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
      <div ref="messagesContainer" data-drop-zone="chat" class="agent-session-panel__messages" @scroll="onScroll">
        <!-- Loading older events indicator -->
        <div v-if="isLoadingMore" class="agent-session-panel__loading-more">
          <MIcon name="loader" class="spin" /> 加载更早的消息...
        </div>
        <!-- Loading -->
        <div v-if="isLoading" class="agent-session-panel__empty">
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
          <div v-if="!hasContent" class="agent-session-panel__empty">
            <div class="agent-session-panel__empty-icon">
              <MIcon name="mail-off" />
            </div>
            <p class="agent-session-panel__empty-text">{{ t('emails.noEmails') }}</p>
            <p class="agent-session-panel__empty-hint">{{ t('emails.startConversation') }}</p>
          </div>
        </template>

        <!-- Inline status indicator (below messages, above bottom) -->
        <div
          v-if="primaryAgentStatus"
          class="agent-session-panel__status-indicator"
          :class="{
            'agent-session-panel__status-indicator--idle': primaryAgentStatus.status === 'IDLE',
            'agent-session-panel__status-indicator--clickable': primaryAgentStatus.otherSessionId,
          }"
          @click="navigateToAgentSession(primaryAgentStatus.otherSessionId)"
        >
          <span :class="['agent-session-panel__status-indicator-icon', { 'agent-session-panel__status-indicator-icon--spinning': primaryAgentStatus.status === 'THINKING' || primaryAgentStatus.status === 'WORKING' }]">
            <MIcon :name="primaryAgentStatus.status === 'THINKING' ? 'brain' : primaryAgentStatus.status === 'WORKING' ? 'loader' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'message-circle' : primaryAgentStatus.status === 'PAUSED' ? 'player-pause' : primaryAgentStatus.status === 'ERROR' ? 'alert-circle' : 'circle-check'" />
          </span>
          <span class="agent-session-panel__status-indicator-agent">{{ primaryAgentName }}</span>
          <span v-if="primaryAgentStatus.isOnCurrentSession" class="agent-session-panel__status-indicator-label">
            {{ primaryAgentStatus.status === 'THINKING' ? 'thinking' : primaryAgentStatus.status === 'WORKING' ? 'working' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'waiting for you' : primaryAgentStatus.status === 'PAUSED' ? 'paused' : primaryAgentStatus.status === 'ERROR' ? 'error' : 'idle' }}
          </span>
          <span v-else class="agent-session-panel__status-indicator-label">
            正在处理其他工作
            <MIcon v-if="primaryAgentStatus.otherSessionId" name="arrow-right" class="agent-session-panel__status-jump" />
          </span>
        </div>
      </div>

      <!-- Task Files Slide-Out (from right edge) -->
      <Transition name="slide-right">
        <TaskFilesPanel
          v-if="showTaskFiles && currentAgentName && currentSessionId"
          :width="taskFilesWidth"
          :files="taskFiles.files.value"
          :files-loading="taskFiles.filesLoading.value"
          :current-dir="taskFiles.currentDir.value"
          :root-dir="taskFiles.rootDir.value"
          :is-at-root="taskFiles.isAtRoot.value"
          :relative-path="taskFiles.relativePath.value"
          @load-files="taskFiles.loadFiles()"
          @open-entry="(entry) => taskFiles.openEntry(entry)"
          @go-up="taskFiles.goUp()"
          @go-root="taskFiles.goRoot()"
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

      <!-- Drag-drop overlay -->
      <div v-if="isDragging" class="agent-session-panel__drop-overlay">
        <MIcon name="upload" />
        <span>{{ dropZone === 'task-files' ? 'Drop to copy into current folder' : 'Drop files to upload' }}</span>
      </div>
    </div>

    <!-- Bottom Input Area -->
    <div data-drop-zone="input" class="agent-session-panel__bottom">
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
    </template> <!-- end session mode -->
  </div>
</template>

<style scoped>
.agent-session-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--surface-base);
}

/* ---- Top Bar ---- */
.agent-session-panel__topbar {
  height: 56px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: var(--surface-base);
  border-bottom: 1px solid var(--border-light);
}

.agent-session-panel__agent-info {
  display: flex;
  align-items: center;
  gap: 14px;
}

.agent-session-panel__avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--morandi-mauve);
  color: rgba(255,255,255,0.9);
  font-size: 13px;
  font-weight: var(--font-semibold);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
}

.agent-session-panel__avatar::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
}

.agent-session-panel__agent-name {
  font-size: 15px;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.agent-session-panel__status {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: var(--surface-secondary);
  border: 1px solid var(--surface-hover);
  border-radius: var(--radius-md);
  font-size: 10px;
  color: var(--text-tertiary);
  animation: fadeIn 200ms var(--ease-out);
}

.agent-session-panel__status-icon {
  display: flex;
  align-items: center;
  font-size: var(--font-xs);
  color: var(--text-tertiary);
}

.agent-session-panel__status-icon--spinning {
  animation: spin 1.2s linear infinite;
}

.agent-session-panel__status-label {
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 3px;
}

.agent-session-panel__status--idle {
  opacity: 0.5;
}

.agent-session-panel__status--clickable {
  cursor: pointer;
}

.agent-session-panel__status--clickable:hover {
  background: var(--surface-hover);
  border-color: var(--border);
}

.agent-session-panel__status-jump {
  font-size: 10px;
}

.agent-session-panel__toolbar {
  display: flex;
  align-items: center;
  gap: 3px;
}

.agent-session-panel__toolbar-btn {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--icon-md);
  cursor: pointer;
  transition: all 0.12s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agent-session-panel__toolbar-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.agent-session-panel__toolbar-btn--active {
  background: var(--surface-secondary);
  color: var(--accent);
}

.agent-session-panel__toolbar-btn--active:hover {
  background: var(--surface-hover);
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
  background: var(--success);
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
  padding: 32px 36px 44px 36px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}

.agent-session-panel__loading-more {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-1);
  padding: var(--spacing-2);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}

.agent-session-panel__loading-more .spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
  background: var(--surface-hover);
  border-radius: var(--radius-xl);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: var(--text-quaternary);
  margin-bottom: var(--spacing-4);
}

.agent-session-panel__empty-icon--loading {
  background: var(--surface-base);
  color: var(--accent);
}

.agent-session-panel__empty-icon--error {
  background: var(--error-muted);
  color: var(--error);
}

.agent-session-panel__empty-text {
  font-size: var(--font-base);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-1) 0;
}

.agent-session-panel__empty-hint {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: 0 0 var(--spacing-4) 0;
}

.agent-session-panel__retry-btn {
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
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
  margin-top: var(--spacing-2);
  background: var(--surface-secondary);
  border: 1px solid var(--surface-hover);
  border-radius: var(--radius-md);
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  animation: fadeIn 200ms var(--ease-out);
  flex-shrink: 0;
  align-self: flex-start;
}

.agent-session-panel__status-indicator-icon {
  display: flex;
  align-items: center;
  font-size: var(--font-sm);
  color: var(--text-tertiary);
}

.agent-session-panel__status-indicator-icon--spinning {
  animation: spin 1.2s linear infinite;
}

.agent-session-panel__status-indicator-agent {
  font-weight: var(--font-semibold);
  color: var(--text-tertiary);
}

.agent-session-panel__status-indicator-label {
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  gap: 3px;
}

.agent-session-panel__status-indicator--idle {
  opacity: 0.45;
}

.agent-session-panel__status-indicator--clickable {
  cursor: pointer;
}

.agent-session-panel__status-indicator--clickable:hover {
  background: var(--surface-hover);
  border-color: var(--border);
}

/* ---- Bottom Input Area ---- */
.agent-session-panel__bottom {
  flex-shrink: 0;
  background: var(--surface-base);
}

/* ---- Ask User Question ---- */
.agent-session-panel__ask-user-form {
  padding: 18px;
  background: var(--warning-soft);
  border: 1px solid rgba(196,162,101,0.15);
  border-radius: var(--radius-lg);
}

.agent-session-panel__ask-user-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.agent-session-panel__ask-user-header .m-icon {
  font-size: 13px;
  color: var(--warning);
}

.agent-session-panel__ask-user-title {
  font-size: 11px;
  font-weight: 700;
  color: var(--warning);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.agent-session-panel__ask-user-text {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  margin: 0 0 14px 0;
  line-height: var(--leading-relaxed);
}

.agent-session-panel__ask-user-input {
  width: 100%;
  padding: var(--spacing-2);
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-primary);
  resize: none;
  margin-bottom: 10px;
  transition: all 0.15s ease;
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
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  background: white;
  color: var(--text-primary);
  transition: all 0.12s ease;
}

.agent-session-panel__ask-user-btn:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

.agent-session-panel__ask-user-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ---- Drag-drop overlay ---- */
.agent-session-panel__drop-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--accent);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  border: 2px dashed var(--accent);
  border-radius: var(--radius-md);
  z-index: 20;
  pointer-events: none;
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
