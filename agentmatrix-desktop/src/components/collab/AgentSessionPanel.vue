<script setup>
import { ref, computed, provide, inject, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { useAgentStore } from '@/stores/agent'
import { useWebSocketStore } from '@/stores/websocket'
import { showUIActionResult } from '@/composables/useUIActionResult'
import { useChatTimeline } from '@/composables/useChatTimeline'
import { useTaskFiles } from '@/composables/useTaskFiles'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { agentAPI } from '@/api/agent'
import { sessionAPI } from '@/api/session'
import ChatMessage from './ChatMessage.vue'
import CollabInput from './CollabInput.vue'
import CollabStartPanel from './CollabStartPanel.vue'
import EmptySessionPanel from './EmptySessionPanel.vue'
import NewTaskPanel from './NewTaskPanel.vue'
import TaskSendingOverlay from './TaskSendingOverlay.vue'
import AgentTerminal from './AgentTerminal.vue'
import TaskInfoPanel from './TaskInfoPanel.vue'
import MIcon from '@/components/icons/MIcon.vue'
import { useFloatingWindow } from '@/composables/useFloatingWindow'

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
  primaryAgentName,
  loadEvents,
  onScroll,
  handleEmailSendStarted,
  handleEmailSendFailed,
  handleEmailSent,
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
  // 只有真正在工作的状态才判断是否在处理其他工作
  // STOPPED 也是非活跃状态，不应显示"正在处理其他工作"
  const isActive = status !== 'IDLE' && status !== 'STOPPED'
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

// ---- Collab draft message (provide/inject for cross-component communication) ----
// Re-use parent's ref if already provided (e.g. AutomationView), otherwise create local one
const collabDraftMessage = inject('collabDraftMessage', ref(''))
provide('collabDraftMessage', collabDraftMessage)

// ---- UI State ----
const taskInfoRef = ref(null)
const showTerminal = ref(false)
const terminalFullscreen = ref(false)
const isCollabMode = ref(false)
const subjectInput = ref(null)

// ---- Close panels when switching sessions ----
watch(currentSessionId, (newId, oldId) => {
  if (newId && oldId && newId !== oldId) {
    // Close terminal when switching to a different session
    showTerminal.value = false
    terminalFullscreen.value = false
  }
})

// ---- Update session subject ----
async function updateSubject(event) {
  const newSubject = event.target.value.trim()
  if (!currentSession.value) return

  const sessionId = currentSession.value.session_id
  const oldSubject = currentSession.value.subject || ''

  if (newSubject === oldSubject) return

  try {
    // 调用 API 更新 subject
    await sessionAPI.updateSessionSubject(sessionId, newSubject)

    // 更新前端 session store 中的 subject
    const index = sessionStore.sessions.findIndex(s => s.session_id === sessionId)
    if (index !== -1) {
      sessionStore.sessions[index] = {
        ...sessionStore.sessions[index],
        subject: newSubject
      }
    }

    // 更新 currentSession
    sessionStore.currentSession = {
      ...sessionStore.currentSession,
      subject: newSubject
    }

    console.log('✅ Session subject updated:', sessionId, newSubject)
  } catch (error) {
    console.error('❌ Failed to update session subject:', error)
    // 恢复原值
    event.target.value = oldSubject
    alert('Failed to update subject: ' + error.message)
  }
}

// ---- Task files ----
const taskFiles = useTaskFiles({
  agentName: () => currentAgentName.value,
  sessionId: () => currentSessionId.value,
})

// ---- UI Schema (动态工具条) ----
const agentUISchema = ref([])
const openGroup = ref(null)

const loadAgentUISchema = async () => {
  if (!currentAgentName.value) {
    agentUISchema.value = []
    return
  }
  const cached = agentStore.getAgentUISchema(currentAgentName.value)
  if (cached.length > 0) {
    agentUISchema.value = cached
    return
  }
  try {
    const result = await agentAPI.getAgentUIActions(currentAgentName.value)
    agentUISchema.value = result.schema || []
    agentStore.setAgentUISchema(currentAgentName.value, result.schema || [])
  } catch (e) {
    console.error('Failed to load UI schema:', e)
    agentUISchema.value = []
  }
}

const agentSkills = ref([])

const loadAgentSkills = async () => {
  if (!currentAgentName.value) {
    agentSkills.value = []
    return
  }
  const cached = agentStore.getAgentSkills(currentAgentName.value)
  if (cached.length > 0) {
    agentSkills.value = cached
    return
  }
  try {
    const result = await agentAPI.getAgent(currentAgentName.value)
    agentSkills.value = result.skills || []
    agentStore.setAgentSkills(currentAgentName.value, result.skills || [])
  } catch (e) {
    console.error('Failed to load agent skills:', e)
    agentSkills.value = []
  }
}

watch(currentAgentName, () => {
  loadAgentUISchema()
  loadAgentSkills()
}, { immediate: true })

// 目录节点（有 children）
const floatingGroups = computed(() =>
  agentUISchema.value.filter(n => n.children)
)

// 顶层 action 节点（无 children）
const floatingTopActions = computed(() =>
  agentUISchema.value.filter(n => n.action)
)

const isActionDisabled = (actionNode) => {
  if (!actionNode.requires_idle) return false
  return agentStore.getAgentStatus(currentAgentName.value) !== 'IDLE'
}

const toggleGroup = (name) => {
  openGroup.value = openGroup.value === name ? null : name
}

// ---- UI Action 弹窗 ----
const wsStore = useWebSocketStore()

// ---- Floating Window ----
const floating = useFloatingWindow()

// 监听 WebSocket 推送的 UI_ACTION_RESULT
watch(() => wsStore.lastUIActionResult, async (result) => {
  if (result && result.agent_name === currentAgentName.value) {
    await showUIActionResult({
      agent_name: result.agent_name,
      action_name: result.action_name,
      result: result.result,
      display_mode: result.display_mode,
    })
  }
})

const invokeUIAction = async (actionNode) => {
  if (!currentAgentName.value) return
  try {
    const payload = { session_id: currentSessionId.value }
    console.log('[UI Action]', actionNode.action, payload)
    const resp = await agentAPI.invokeAgentUIAction(currentAgentName.value, actionNode.action, payload)
    console.log('[UI Action] API response:', resp)
    if (resp.success && resp.result != null) {
      await showUIActionResult({
        agent_name: currentAgentName.value,
        action_name: actionNode.action,
        result: resp.result,
        display_mode: resp.display_mode,
      })
    }
  } catch (e) {
    console.error('UI action failed:', e)
  }
}

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

const _closeGroup = () => { openGroup.value = null }

onMounted(async () => {
  updateMiddleSize()
  window.addEventListener('resize', updateMiddleSize)

  // Click outside to close group dropdown
  document.addEventListener('click', _closeGroup)

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
  document.removeEventListener('click', _closeGroup)
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
          taskInfoRef.value?.switchTab('files')
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
  showTerminal.value = !showTerminal.value
  if (!showTerminal.value) {
    // 隐藏时退出全屏模式
    terminalFullscreen.value = false
  }
}

const handleTerminalClose = () => {
  // 关闭按钮 = 隐藏 terminal
  showTerminal.value = false
  terminalFullscreen.value = false
}

const handleTerminalToggleMinimize = () => {
  // 最小化/最大化按钮 = 在默认大小和全屏之间切换
  if (!showTerminal.value) return
  terminalFullscreen.value = !terminalFullscreen.value
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

// ---- TaskInfo Panel resizable ----
const taskInfoWidth = ref(null) // null = 50% default, number = fixed px
const isDraggingDivider = ref(false)

const taskInfoStyle = computed(() => {
  if (taskInfoWidth.value != null) {
    return { flex: '0 0 auto', width: `${taskInfoWidth.value}px` }
  }
  return { flex: '3 1 0%' } // default: 5:3 ratio
})

const messagesStyle = computed(() => {
  if (taskInfoWidth.value != null) {
    return { flex: '1 1 0%', minWidth: '0' }
  }
  return { flex: '5 1 0%', minWidth: '0' } // default: 5:3 ratio
})

function onDividerMouseDown(e) {
  e.preventDefault()
  isDraggingDivider.value = true
  // If still in default 50/50 mode, initialize from actual widths
  if (taskInfoWidth.value == null && middleArea.value) {
    const total = middleArea.value.clientWidth
    taskInfoWidth.value = Math.round(total / 2)
  }
  document.addEventListener('mousemove', onDividerMouseMove)
  document.addEventListener('mouseup', onDividerMouseUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onDividerMouseMove(e) {
  if (!isDraggingDivider.value || !middleArea.value) return
  const total = middleArea.value.clientWidth
  const newWidth = total - e.clientX + middleArea.value.getBoundingClientRect().left
  const clamped = Math.max(200, Math.min(total - 300, newWidth))
  taskInfoWidth.value = Math.round(clamped)
}

function onDividerMouseUp() {
  isDraggingDivider.value = false
  document.removeEventListener('mousemove', onDividerMouseMove)
  document.removeEventListener('mouseup', onDividerMouseUp)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}
</script>

<template>
  <div class="agent-session-panel">
    <!-- Wizard mode / No session selected -->
    <template v-if="wizard.isActive.value || !currentSession">
      <EmptySessionPanel
        v-if="!wizard.isActive.value && !currentSession"
        @start-new-task="wizard.enterWizard()"
      />
      <CollabStartPanel
        v-else-if="wizard.wizardStep.value === 'pick-agent'"
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
          <span :class="['agent-session-panel__status-icon', { 'agent-session-panel__status-icon--spinning': primaryAgentStatus.status === 'THINKING' || primaryAgentStatus.status === 'WORKING' || primaryAgentStatus.status === 'RECOVERING' }]">
            <MIcon :name="primaryAgentStatus.status === 'THINKING' ? 'logo' : primaryAgentStatus.status === 'WORKING' || primaryAgentStatus.status === 'RECOVERING' ? 'loader' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'message-circle' : primaryAgentStatus.status === 'PAUSED' ? 'player-pause' : primaryAgentStatus.status === 'ERROR' ? 'alert-circle' : 'circle-check'" />
          </span>
          <span class="agent-session-panel__status-label">
            <template v-if="primaryAgentStatus.isOnCurrentSession">
              {{ primaryAgentStatus.status === 'THINKING' ? 'thinking' : primaryAgentStatus.status === 'WORKING' ? 'working' : primaryAgentStatus.status === 'RECOVERING' ? 'recovering' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'waiting' : primaryAgentStatus.status === 'PAUSED' ? 'paused' : primaryAgentStatus.status === 'ERROR' ? 'error' : 'idle' }}
            </template>
            <template v-else>
              正在处理其他工作
              <MIcon v-if="primaryAgentStatus.otherSessionId" name="arrow-right" class="agent-session-panel__status-jump" />
            </template>
          </span>
        </span>

        <!-- Editable subject title -->
        <div class="agent-session-panel__subject-wrapper">
          <input
            v-if="currentSession"
            ref="subjectInput"
            class="agent-session-panel__subject-input"
            :value="currentSession.subject || ''"
            placeholder="输入标题..."
            @blur="updateSubject"
            @keyup.enter="subjectInput?.blur()"
          />
        </div>
      </div>

      <div class="agent-session-panel__toolbar">
        <!-- Floating Mode -->
        <button
          class="agent-session-panel__toolbar-btn agent-session-panel__toolbar-btn--float"
          @click="floating.openFloating()"
          title="Floating Mode"
        >
          <MIcon name="arrows-maximize" />
          <span class="agent-session-panel__toolbar-btn-text">Float</span>
        </button>

        <!-- Refresh -->
        <button
          class="agent-session-panel__toolbar-btn"
          @click="currentSession && loadEvents(currentSession)"
          title="Refresh"
        >
          <MIcon name="refresh" />
          <span class="agent-session-panel__toolbar-btn-text">Refresh</span>
        </button>
      </div>
    </header>

    <!-- Middle Area -->
    <div ref="middleArea" class="agent-session-panel__middle">
      <!-- Chat messages -->
      <div ref="messagesContainer" data-drop-zone="chat" class="agent-session-panel__messages" :style="messagesStyle" @scroll="onScroll">
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
          <span :class="['agent-session-panel__status-indicator-icon', { 'agent-session-panel__status-indicator-icon--spinning': primaryAgentStatus.status === 'THINKING' || primaryAgentStatus.status === 'WORKING' || primaryAgentStatus.status === 'RECOVERING' }]">
            <MIcon :name="primaryAgentStatus.status === 'THINKING' ? 'logo' : primaryAgentStatus.status === 'WORKING' || primaryAgentStatus.status === 'RECOVERING' ? 'loader' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'message-circle' : primaryAgentStatus.status === 'PAUSED' ? 'player-pause' : primaryAgentStatus.status === 'ERROR' ? 'alert-circle' : 'circle-check'" />
          </span>
          <span class="agent-session-panel__status-indicator-agent">{{ primaryAgentName }}</span>
          <span v-if="primaryAgentStatus.isOnCurrentSession" class="agent-session-panel__status-indicator-label">
            {{ primaryAgentStatus.status === 'THINKING' ? 'thinking' : primaryAgentStatus.status === 'WORKING' ? 'working' : primaryAgentStatus.status === 'RECOVERING' ? 'recovering' : primaryAgentStatus.status === 'WAITING_FOR_USER' ? 'waiting for you' : primaryAgentStatus.status === 'PAUSED' ? 'paused' : primaryAgentStatus.status === 'ERROR' ? 'error' : 'idle' }}
          </span>
          <span v-else class="agent-session-panel__status-indicator-label">
            正在处理其他工作
            <MIcon v-if="primaryAgentStatus.otherSessionId" name="arrow-right" class="agent-session-panel__status-jump" />
          </span>
        </div>
      </div>

      <!-- Resize Handle -->
      <div
        v-if="currentAgentName && currentSessionId"
        class="agent-session-panel__resize-handle"
        :class="{ 'agent-session-panel__resize-handle--active': isDraggingDivider }"
        @mousedown="onDividerMouseDown"
      />

      <!-- TaskInfo Panel (resizable right panel, default 50%) -->
      <TaskInfoPanel
        v-if="currentAgentName && currentSessionId"
        ref="taskInfoRef"
        :agent-name="currentAgentName"
        :session-id="currentSessionId"
        :agent-skills="agentSkills"
        :files="taskFiles.files.value"
        :files-loading="taskFiles.filesLoading.value"
        :current-dir="taskFiles.currentDir.value"
        :root-dir="taskFiles.rootDir.value"
        :is-at-root="taskFiles.isAtRoot.value"
        :relative-path="taskFiles.relativePath.value"
        :selected-files="taskFiles.selectedFiles.value"
        :context-menu="taskFiles.contextMenu.value"
        class="agent-session-panel__task-info"
        :style="taskInfoStyle"
        @load-files="taskFiles.loadFiles()"
        @open-entry="(entry) => taskFiles.openEntry(entry)"
        @go-up="taskFiles.goUp()"
        @go-root="taskFiles.goRoot()"
        @select-file="(entry, event) => taskFiles.toggleFileSelection(entry, event)"
        @contextmenu="(entry, event) => taskFiles.showContextMenu(entry, event)"
        @hide-context-menu="taskFiles.hideContextMenu()"
        @menu-action="(action) => taskFiles.handleMenuAction(action)"
      />

      <!-- Floating Terminal -->
      <AgentTerminal
        v-if="showTerminal && currentAgentName"
        :agent-name="currentAgentName"
        :minimized="false"
        :fullscreen="terminalFullscreen"
        :parent-width="middleSize.width"
        :parent-height="middleSize.height"
        @toggle-minimize="handleTerminalToggleMinimize"
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
      <!-- Floating toolbar (sits on right shoulder) -->
      <div class="agent-session-panel__floating-toolbar">

        <!-- Terminal toggle -->
        <button
          class="floating-toolbar-btn"
          :class="{ 'floating-toolbar-btn--active': showTerminal }"
          @click="toggleTerminal"
        >
          <MIcon name="monitor-play" />
          <span class="floating-toolbar-btn__tooltip">Terminal</span>
        </button>

        <!-- Dynamic UI Schema: group dropdowns -->
        <div v-for="group in floatingGroups" :key="group.name" class="floating-toolbar-group">
          <button
            class="floating-toolbar-btn floating-toolbar-btn--ui-action"
            :class="{ 'floating-toolbar-btn--active': openGroup === group.name }"
            @click.stop="toggleGroup(group.name)"
          >
            <MIcon :name="group.icon || 'menu'" />
            <span class="floating-toolbar-btn__tooltip">{{ $t(`ui_actions.groups.${group.name}`, group.name) }}</span>
          </button>
          <div v-if="openGroup === group.name" class="floating-toolbar-dropdown">
            <button
              v-for="child in group.children"
              :key="child.action"
              class="floating-toolbar-dropdown__item"
              :class="{ 'floating-toolbar-dropdown__item--disabled': isActionDisabled(child) }"
              :disabled="isActionDisabled(child)"
              @click="invokeUIAction(child); openGroup = null"
            >
              <MIcon :name="child.icon || 'zap'" />
              <span>{{ $t(`ui_actions.actions.${child.action}`, child.action) }}</span>
            </button>
          </div>
        </div>

        <!-- Dynamic UI Schema: top-level action buttons -->
        <button
          v-for="action in floatingTopActions"
          :key="action.action"
          class="floating-toolbar-btn floating-toolbar-btn--ui-action"
          :class="{ 'floating-toolbar-btn--disabled': isActionDisabled(action) }"
          :disabled="isActionDisabled(action)"
          @click="invokeUIAction(action)"
        >
          <MIcon :name="action.icon || 'zap'" />
          <span class="floating-toolbar-btn__tooltip">{{ $t(`ui_actions.actions.${action.action}`, action.action) }}</span>
        </button>
      </div>

      <!-- Input -->
      <CollabInput
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
  border-bottom: 1px solid var(--border);
}

.agent-session-panel__agent-info {
  display: flex;
  align-items: center;
  gap: 14px;
  flex: 1;
  min-width: 0;
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

.agent-session-panel__subject-wrapper {
  margin-left: 32px;
  flex: 1;
}

.agent-session-panel__subject-input {
  width: 100%;
  font-size: 15px;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  outline: none;
  transition: all 0.12s ease;
}

.agent-session-panel__subject-input:hover {
  background: var(--surface-hover);
}

.agent-session-panel__subject-input:focus {
  background: var(--surface-base);
  border-color: var(--accent);
}

.agent-session-panel__subject-input::placeholder {
  color: var(--text-quaternary);
  font-weight: var(--font-normal);
}

.agent-session-panel__status {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 11px;
  color: var(--text-secondary);
  animation: fadeIn 200ms var(--ease-out);
  transition: all 0.3s ease;
}

.agent-session-panel__status-icon {
  display: flex;
  align-items: center;
  font-size: var(--font-xs);
  color: var(--text-secondary);
}

.agent-session-panel__status-icon--spinning {
  animation: spin 1.2s linear infinite;
}

.agent-session-panel__status-label {
  color: var(--text-secondary);
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
  gap: 4px;
}

.agent-session-panel__toolbar-btn {
  position: relative;
  height: 36px;
  padding: 0 10px;
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
  gap: 6px;
}

.agent-session-panel__toolbar-btn-text {
  font-size: 12px;
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.agent-session-panel__toolbar-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.agent-session-panel__toolbar-btn:hover .agent-session-panel__toolbar-btn-text {
  color: var(--text-primary);
}

.agent-session-panel__toolbar-btn--active {
  background: var(--surface-secondary);
  color: var(--accent);
}

.agent-session-panel__toolbar-btn--active .agent-session-panel__toolbar-btn-text {
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

.agent-session-panel__toolbar-btn--float {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #fff;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.35);
  border-radius: 8px;
  padding: 0 14px;
}

.agent-session-panel__toolbar-btn--float .agent-session-panel__toolbar-btn-text {
  color: #fff;
  font-weight: 600;
}

.agent-session-panel__toolbar-btn--float:hover {
  background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.45);
  transform: translateY(-1px);
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
  flex: 5 1 0%;
  overflow-y: auto;
  padding: 32px 36px 16px 36px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}

/* ---- Resize Handle ---- */
.agent-session-panel__resize-handle {
  width: 5px;
  flex-shrink: 0;
  cursor: col-resize;
  position: relative;
  z-index: 3;
  transition: background 0.15s ease;
}
.agent-session-panel__resize-handle::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 3px;
  height: 24px;
  border-radius: 2px;
  background: var(--border);
  opacity: 0;
  transition: opacity 0.15s ease;
}
.agent-session-panel__resize-handle:hover::after,
.agent-session-panel__resize-handle--active::after {
  opacity: 1;
  background: var(--accent);
}

/* ---- TaskInfo Panel (default 5:3, resizable) ---- */
.agent-session-panel__task-info {
  flex: 3 1 0%;
  overflow: visible;
  z-index: 2;
  min-width: 200px;
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
  color: var(--text-secondary);
  animation: fadeIn 200ms var(--ease-out);
  flex-shrink: 0;
  align-self: flex-start;
  transition: all 0.3s ease;
}

.agent-session-panel__status-indicator:not(.agent-session-panel__status-indicator--idle) {
  background: rgba(184, 169, 201, 0.08);
  border-color: rgba(184, 169, 201, 0.15);
}

.agent-session-panel__status-indicator-icon {
  display: flex;
  align-items: center;
  font-size: var(--font-sm);
  color: var(--text-secondary);
}

.agent-session-panel__status-indicator-icon--spinning {
  animation: spin 1.2s linear infinite;
}

.agent-session-panel__status-indicator-agent {
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
}

.agent-session-panel__status-indicator-label {
  color: var(--text-secondary);
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
  position: relative;
  flex-shrink: 0;
  background: var(--surface-base);
}

/* ---- Floating Toolbar ---- */
.agent-session-panel__floating-toolbar {
  position: absolute;
  top: -16px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(200, 200, 200, 0.3);
  border-radius: 12px;
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.06),
    0 8px 24px rgba(0, 0, 0, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  z-index: 10;
  animation: floatUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes floatUp {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.floating-toolbar-btn {
  position: relative;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  border: 1.5px solid var(--border-color, #C5CDD8);
  background: transparent;
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

/* Terminal: sage green */
.floating-toolbar-btn:nth-child(1) {
  border-color: #5A8A52;
  color: #5A8A52;
}

/* UI Action buttons: mauve */
.floating-toolbar-btn--ui-action {
  border-color: #8B7AAF;
  color: #8B7AAF;
}

/* Group dropdown container */
.floating-toolbar-group {
  position: relative;
}

.floating-toolbar-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  min-width: 140px;
  z-index: 100;
  padding: 4px 0;
}

.floating-toolbar-dropdown__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: #333;
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
}

.floating-toolbar-dropdown__item:hover:not(:disabled) {
  background: rgba(139, 122, 175, 0.08);
}

.floating-toolbar-dropdown__item--disabled,
.floating-toolbar-dropdown__item:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.floating-toolbar-btn:hover {
  transform: translateY(-2px);
  background: rgba(0, 0, 0, 0.04);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.floating-toolbar-btn:active {
  transform: translateY(0);
}

/* ---- Active state: solid fill ---- */
.floating-toolbar-btn:nth-child(1).floating-toolbar-btn--active {
  border-color: #3A6A32;
  color: #3A6A32;
  background: rgba(90, 138, 82, 0.12);
}

.floating-toolbar-btn--ui-action.floating-toolbar-btn--active {
  border-color: #5A4A8A;
  color: #5A4A8A;
  background: rgba(139, 122, 175, 0.12);
}

/* ---- Hover tooltip ---- */
.floating-toolbar-btn__tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 10px;
  background: var(--text-primary, #18181B);
  color: var(--surface-base, #fff);
  font-size: 11px;
  font-weight: 500;
  border-radius: 6px;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
  z-index: 20;
}

.floating-toolbar-btn:hover .floating-toolbar-btn__tooltip {
  opacity: 1;
}

/* ---- Disabled ---- */
.floating-toolbar-btn--disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.floating-toolbar-btn--disabled:hover {
  transform: none;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.floating-toolbar-btn--disabled:hover .floating-toolbar-btn__tooltip {
  opacity: 0;
}

/* ---- Green dot indicator ---- */
.floating-toolbar-btn__dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  border: 1.5px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
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

