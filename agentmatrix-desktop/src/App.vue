<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import { useBackendStore } from '@/stores/backend'
import { useConfigStore } from '@/stores/config'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'
import { useWebSocketStore } from '@/stores/websocket'
import { useWebSocket } from '@/composables/useWebSocket'
import { useNotifications } from '@/composables/useNotifications'
import ViewSelector from '@/components/view-selector/ViewSelector.vue'
import ViewContainer from '@/components/view-container/ViewContainer.vue'
import ColdStartWizard from '@/components/wizard/ColdStartWizard.vue'
import EmailToast from '@/components/toast/EmailToast.vue'
import { sessionAPI } from '@/api/session'

const windowLabel = getCurrentWebviewWindow().label
const currentView = ref('email')
const backendStore = useBackendStore()
const configStore = useConfigStore()
const sessionStore = useSessionStore()
const uiStore = useUIStore()
const websocketStore = useWebSocketStore()
const { isConnected, connect, onMessage } = useWebSocket()
const { showNotification } = useNotifications()

const appState = ref('loading')

const backendStatus = computed(() => backendStore.status)
const currentSession = computed(() => sessionStore.currentSession)

const handleViewChange = (viewId) => {
  currentView.value = viewId
}

async function handleEmailToastClick(emailData) {
  const sessionId = emailData.recipient_session_id || emailData.receiver_session_id
  if (sessionId) {
    const targetSession = sessionStore.sessions.find(
      s => s.session_id === sessionId
    )
    if (targetSession) {
      await sessionStore.selectSession(targetSession, true)
    }
  }
  // Switch to email view
  currentView.value = 'email'
  uiStore.emailToast.show = false
}

async function initializeWebSocket() {
  if (backendStore.isRunning) {
    connect()
  }

  onMessage((data) => {
    websocketStore.handle_message(data)
  })

  websocketStore.onSessionUpdate(async (data) => {
    const { session_id, direction, is_read, sender, subject } = data
    const isCurrentSession = session_id === currentSession.value?.session_id

    sessionStore.updateSessionFromEvent(data)

    if (direction === 'inbound' && is_read === 0) {
      if (currentView.value === 'email') {
        if (isCurrentSession) {
          sessionStore.selectSession(currentSession.value, true)
          setTimeout(() => {
            sessionStore.markSessionRead(session_id)
            sessionAPI.markAsRead(session_id)
          }, 3000)
        }
      } else {
        uiStore.emailToast = { show: true, emailData: data }
        showNotification('新邮件', `来自 ${sender}: ${subject}`)
      }
    }
  })
}

async function handleWizardComplete() {
  // submitWizard 已完成（配置文件 + mark_configured）
  // 通知 Rust 关闭向导 → 显示 splash → 启动环境 → 显示主窗口
  await invoke('wizard_complete')
}

onMounted(async () => {
  if (windowLabel === 'wizard') {
    appState.value = 'wizard'
    return
  }
  // Main window: backend is already running (started by Rust setup)
  await backendStore.initializeBackend()
  await initializeWebSocket()
  appState.value = 'ready'
})

onUnmounted(() => {
  backendStore.stopHealthMonitoring()
})
</script>

<template>
  <ColdStartWizard v-if="appState === 'wizard'" @complete="handleWizardComplete" />

  <div v-else-if="appState === 'loading'" class="app-loading">
    <div class="app-loading__spinner"></div>
  </div>

  <div v-else class="app">
    <ViewSelector :current-view="currentView" @view-change="handleViewChange">
      <template #status>
        <div
          :class="['status-indicator', `status-indicator--${backendStatus}`]"
          :title="backendStatus.charAt(0).toUpperCase() + backendStatus.slice(1)"
        >
          <span
            :class="['status-indicator__dot', `status-indicator__dot--${backendStatus}`]"
          ></span>
        </div>
        <div
          :class="['status-indicator', `status-indicator--${isConnected ? 'connected' : 'disconnected'}`]"
          :title="isConnected ? 'Connected' : 'Connecting...'"
        >
          <span
            :class="['status-indicator__dot', `status-indicator__dot--${isConnected ? 'connected' : 'disconnected'}`]"
          ></span>
        </div>
      </template>
    </ViewSelector>
    <ViewContainer
      :current-view="currentView"
      @view-change="handleViewChange"
    />
  </div>

  <EmailToast
    :show="uiStore.emailToast.show"
    :email-data="uiStore.emailToast.emailData"
    @click="handleEmailToastClick"
    @close="uiStore.emailToast.show = false"
  />
</template>

<style scoped>
.app {
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
}

.app-loading {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
}

.app-loading__spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--parchment-300);
  border-top-color: var(--vermillion);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}

.status-indicator {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.status-indicator:hover {
  background: var(--parchment-300);
}

.status-indicator__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  transition: all var(--duration-base) var(--ease-out);
}

.status-indicator__dot--running,
.status-indicator__dot--connected {
  background: var(--verdant);
}

.status-indicator__dot--stopped,
.status-indicator__dot--disconnected {
  background: var(--fault);
}

.status-indicator__dot--starting,
.status-indicator__dot--stopping {
  background: var(--amber);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1 }
  50% { opacity: 0.5 }
}

.status-indicator[title]:hover::after {
  content: attr(title);
  position: absolute;
  left: calc(100% + 12px);
  top: 50%;
  transform: translateY(-50%);
  background: var(--neutral-800);
  color: white;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  white-space: nowrap;
  z-index: var(--z-tooltip);
}
</style>