<script setup>
import { ref, computed, watch, onUnmounted, nextTick } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useConfigStore } from '@/stores/config'
import { useChatTimeline } from '@/composables/useChatTimeline'
import { useWhiteboard } from '@/composables/useWhiteboard'
import { useTodo } from '@/composables/useTodo'
import { useTaskFiles } from '@/composables/useTaskFiles'
import { sessionAPI } from '@/api/session'
import MIcon from '@/components/icons/MIcon.vue'
import ChatMessage from '@/components/collab/ChatMessage.vue'
import WhiteboardView from '@/components/collab/WhiteboardView.vue'
import TodoView from '@/components/collab/TodoView.vue'
import TaskFilesPanel from '@/components/collab/TaskFilesPanel.vue'
import QuestionForm from '@/components/design/QuestionForm.vue'
import AgentStatusIndicator from '@/components/agent/AgentStatusIndicator.vue'
import DesignSessionList from './DesignSessionList.vue'

const DESIGNER_AGENT = 'Designer'

const sessionStore = useSessionStore()
const configStore = useConfigStore()

const userAgentName = computed(() => configStore.config?.user_agent_name || 'User')

const {
  chatTimeline,
  messagesContainer,
  currentSession,
  primaryAgentName,
  onScroll,
  scrollToBottom,
  handleEmailSendStarted,
  handleEmailSendFailed,
} = useChatTimeline({ userAgentName: () => userAgentName.value })

const currentAgentName = computed(() => primaryAgentName.value || DESIGNER_AGENT)

// ---- agent_name / session_id（驱动 whiteboard/todo/files）----
const agentName = computed(() => currentSession.value?.agent_name || currentSession.value?.name || '')
const sessionId = computed(() => currentSession.value?.agent_session_id || '')

const whiteboard = useWhiteboard({
  agentName: () => agentName.value,
  sessionId: () => sessionId.value,
})

const todo = useTodo({
  agentName: () => agentName.value,
  sessionId: () => sessionId.value,
})

const taskFiles = useTaskFiles({
  agentName: () => agentName.value,
  sessionId: () => sessionId.value,
})

// ---- Tabs ----
const TABS = [
  { id: 'chat', label: 'Chat', icon: 'message-circle' },
  { id: 'whiteboard', label: 'Whiteboard', icon: 'clipboard' },
  { id: 'todo', label: 'Todo', icon: 'list-checks' },
  { id: 'files', label: 'Files', icon: 'folder' },
  { id: 'history', label: 'History', icon: 'history' },
]
const activeTab = ref('chat')

function switchTab(id) {
  activeTab.value = id
  if (id === 'chat') nextTick(() => scrollToBottom())
}

// ---- Badge counts ----
const whiteboardCount = computed(() => {
  let n = 0
  for (const entries of Object.values(whiteboard.sections.value)) {
    n += Object.keys(entries).length
  }
  return n || null
})
const todoCount = computed(() => Object.keys(todo.todos.value).length || null)

function badgeFor(tabId) {
  if (tabId === 'whiteboard') return whiteboardCount.value
  if (tabId === 'todo') return todoCount.value
  return null
}

// ---- Auto-switch on content change（参考 TaskInfoPanel line 60-65）----
watch(() => whiteboard.version.value, (v) => {
  if (v > 0 && activeTab.value !== 'whiteboard') activeTab.value = 'whiteboard'
})
watch(() => todo.version.value, (v) => {
  if (v > 0 && todoCount.value > 0 && activeTab.value !== 'todo') activeTab.value = 'todo'
})

// ---- Files polling when active（参考 TaskInfoPanel line 140-148）----
let filesTimer = null
watch(activeTab, (tab) => {
  if (filesTimer) { clearInterval(filesTimer); filesTimer = null }
  if (tab === 'files') {
    taskFiles.loadFiles()
    filesTimer = setInterval(() => taskFiles.loadFiles(), 1000)
  }
}, { immediate: true })

onUnmounted(() => {
  if (filesTimer) clearInterval(filesTimer)
})

// ---- Chat input + send ----
const inputText = ref('')

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || !currentSession.value) return
  inputText.value = ''

  const session = currentSession.value
  const placeholderId = `placeholder-${Date.now()}`

  handleEmailSendStarted({
    placeholder: {
      id: placeholderId,
      body: text,
      recipient: session.agent_name,
      subject: '',
    },
  })

  try {
    await sessionAPI.sendReply(session, text)
  } catch (e) {
    console.error('Failed to send message:', e)
    handleEmailSendFailed({ placeholderId })
  }
}

// ---- History: pick a session → switch currentSession ----
function handlePickSession(session) {
  sessionStore.selectSession(session)
  activeTab.value = 'chat'
}

// ---- pending question（agent 调 ask_user_question 触发，非阻塞）----
// watch lastSessionEvent 只处理 question 分支；refresh/screenshot 仍由 DesignView 处理
const pendingQuestions = ref(null)

watch(() => sessionStore.lastSessionEvent, (evt) => {
  if (!evt || !currentSession.value) return
  if (evt.agent_name !== DESIGNER_AGENT) return
  const agentSessionId = currentSession.value.agent_session_id
  if (agentSessionId && evt.session_id !== agentSessionId) return

  const data = evt.data || {}
  if (data.event_type !== 'design' || data.event_name !== 'question') return

  let detail = data.event_detail || {}
  if (typeof detail === 'string') {
    try { detail = JSON.parse(detail) } catch { detail = {} }
  }
  const qs = detail.questions || []
  if (qs.length) pendingQuestions.value = qs
})

async function handleQuestionSubmit(answersText) {
  const session = currentSession.value
  pendingQuestions.value = null
  if (!session || !answersText) return

  const placeholderId = `placeholder-q-${Date.now()}`
  handleEmailSendStarted({
    placeholder: {
      id: placeholderId,
      body: answersText,
      recipient: session.agent_name,
      subject: '',
    },
  })
  try {
    await sessionAPI.sendReply(session, answersText)
  } catch (e) {
    console.error('Failed to submit question answer:', e)
    handleEmailSendFailed({ placeholderId })
  }
}

function handleQuestionCancel() {
  pendingQuestions.value = null
}
</script>

<template>
  <div class="design-tabs-panel">
    <!-- Tab bar -->
    <div class="dtp-tabs">
      <button
        v-for="tab in TABS"
        :key="tab.id"
        class="dtp-tab"
        :class="{ 'dtp-tab--active': activeTab === tab.id }"
        @click="switchTab(tab.id)"
      >
        <MIcon :name="tab.icon" class="dtp-tab__icon" />
        <span class="dtp-tab__label">{{ tab.label }}</span>
        <span v-if="badgeFor(tab.id)" class="dtp-tab__badge">{{ badgeFor(tab.id) }}</span>
      </button>
    </div>

    <!-- Content -->
    <div class="dtp-content">
      <!-- Chat tab -->
      <div v-if="activeTab === 'chat'" class="dtp-chat">
        <div class="dtp-chat__status">
          <AgentStatusIndicator
            :agent-name="currentAgentName"
            :current-session-id="sessionId"
          />
        </div>
        <div ref="messagesContainer" class="dtp-chat__messages" @scroll="onScroll">
          <ChatMessage
            v-for="item in chatTimeline"
            :key="item.id"
            :message="item"
            :user_agent_name="userAgentName"
            :agent-name="currentAgentName"
          />
        </div>
        <div class="dtp-chat__input">
          <textarea
            v-model="inputText"
            placeholder="输入消息..."
            rows="3"
            @keydown.enter.exact.prevent="handleSend"
          ></textarea>
          <button class="dtp-chat__send" :disabled="!inputText.trim()" @click="handleSend">
            <MIcon name="send" />
          </button>
        </div>
      </div>

      <!-- Whiteboard tab -->
      <WhiteboardView
        v-else-if="activeTab === 'whiteboard'"
        :agent-name="agentName"
        :session-id="sessionId"
        :sections="whiteboard.sections.value"
        :is-loaded="whiteboard.isLoaded.value"
        @save="whiteboard.replaceAll"
      />

      <!-- Todo tab -->
      <TodoView
        v-else-if="activeTab === 'todo'"
        :agent-name="agentName"
        :session-id="sessionId"
        :todos="todo.todos.value"
        :is-loaded="todo.isLoaded.value"
      />

      <!-- Files tab -->
      <TaskFilesPanel
        v-else-if="activeTab === 'files'"
        :files="taskFiles.files.value"
        :files-loading="taskFiles.filesLoading.value"
        :current-dir="taskFiles.currentDir.value"
        :root-dir="taskFiles.rootDir.value"
        :is-at-root="taskFiles.isAtRoot.value"
        :relative-path="taskFiles.relativePath.value"
        :selected-files="taskFiles.selectedFiles.value"
        :context-menu="taskFiles.contextMenu.value"
        @open-entry="taskFiles.openEntry"
        @go-up="taskFiles.goUp"
        @go-root="taskFiles.goRoot"
        @select-file="taskFiles.toggleFileSelection"
        @contextmenu="taskFiles.showContextMenu"
        @hide-context-menu="taskFiles.hideContextMenu"
        @menu-action="taskFiles.handleMenuAction"
      />

      <!-- History tab -->
      <DesignSessionList
        v-else-if="activeTab === 'history'"
        @select="handlePickSession"
      />
    </div>

    <!-- Question overlay（agent 调 ask_user_question 触发，非阻塞）-->
    <QuestionForm
      v-if="pendingQuestions"
      :questions="pendingQuestions"
      @submit="handleQuestionSubmit"
      @cancel="handleQuestionCancel"
    />
  </div>
</template>

<style scoped>
.design-tabs-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: visible;
  font-size: 14px;
  padding-top: 6px;
}

/* ---- Tab bar（参考 TaskInfoPanel）---- */
.dtp-tabs {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
  position: relative;
  z-index: 2;
  overflow-x: auto;
  scrollbar-width: none;
}
.dtp-tabs::-webkit-scrollbar { display: none; }

.dtp-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1.5px solid var(--border);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: var(--surface-secondary);
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.dtp-tab:hover {
  color: var(--text-primary);
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.dtp-tab--active {
  border: 2px solid var(--text-primary);
  border-bottom: 2px solid var(--surface-base);
  border-radius: 10px 10px 0 0;
  background: var(--surface-base);
  color: var(--text-primary);
  font-weight: 600;
  z-index: 3;
  margin-bottom: -2px;
  padding-bottom: 7px;
  background-clip: padding-box;
}

.dtp-tab--active:hover {
  color: var(--text-primary);
  background: var(--surface-base);
}

.dtp-tab__icon {
  font-size: 15px;
  flex-shrink: 0;
}

.dtp-tab__label {
  max-width: 0;
  overflow: hidden;
  opacity: 0;
  transition: max-width 0.2s ease, opacity 0.15s ease;
}

.dtp-tab:hover .dtp-tab__label,
.dtp-tab--active .dtp-tab__label {
  max-width: 120px;
  opacity: 1;
}

.dtp-tab__badge {
  font-size: 10px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.dtp-tab--active .dtp-tab__badge {
  background: var(--text-primary);
  color: var(--surface-base);
}

/* ---- Content ---- */
.dtp-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: var(--surface-base);
  border: 2px solid var(--text-primary);
  border-radius: 10px 0 0 10px;
  display: flex;
  flex-direction: column;
}

/* ---- Chat ---- */
.dtp-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.dtp-chat__status {
  flex-shrink: 0;
  padding: 6px var(--spacing-3);
  border-bottom: 1px solid var(--border);
  background: var(--surface-secondary);
}

.dtp-chat__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-3);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.dtp-chat__input {
  display: flex;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  align-items: flex-end;
}

.dtp-chat__input textarea {
  flex: 1;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-sm);
  font-family: inherit;
  resize: none;
  line-height: 1.5;
}

.dtp-chat__input textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.dtp-chat__send {
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
  height: fit-content;
}

.dtp-chat__send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
