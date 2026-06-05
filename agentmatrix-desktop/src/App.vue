<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import { useBackendStore } from '@/stores/backend'
import { useConfigStore } from '@/stores/config'
import { useSessionStore } from '@/stores/session'
import { useUIStore } from '@/stores/ui'
import { useWebSocketStore } from '@/stores/websocket'
import { listen } from '@tauri-apps/api/event'
import ViewSelector from '@/components/view-selector/ViewSelector.vue'
import ViewContainer from '@/components/view-container/ViewContainer.vue'
import ColdStartWizard from '@/components/wizard/ColdStartWizard.vue'
import EmailToast from '@/components/toast/EmailToast.vue'
import ToastContainer from '@/components/settings/toast/ToastContainer.vue'
import { configAPI } from '@/api/config'

const windowLabel = getCurrentWebviewWindow().label
const currentView = ref('collab')
const backendStore = useBackendStore()
const configStore = useConfigStore()
const sessionStore = useSessionStore()
const uiStore = useUIStore()
const websocketStore = useWebSocketStore()
const isConnected = ref(false)
let unlistenFns = []

const appState = ref('loading')

const backendStatus = computed(() => backendStore.status)

const handleViewChange = (viewId) => {
  currentView.value = viewId
}

async function handleEmailToastClick(emailData) {
  const sessionId = emailData.recipient_session_id || emailData.receiver_session_id
  let targetSession = null
  if (sessionId) {
    targetSession = sessionStore.sessions.find(
      s => s.session_id === sessionId
    )
    if (targetSession) {
      await sessionStore.selectSession(targetSession, true)
    }
  }

  // 统一路由到 Collab View（逐步淘汰 Email View）
  currentView.value = 'collab'
  uiStore.emailToast.show = false
}

async function initializeEventListeners() {
  // Connection status (emitted by Rust update_ws_status)
  unlistenFns.push(await listen('ws:connection-status', (event) => {
    const status = event.payload
    isConnected.value = status === 'Connected' || (status && status.state === 'Connected')
  }))

  // Forward all WS events to websocketStore.handle_message()
  // Payload is the raw JSON from backend (no field loss)
  for (const eventName of [
    'ws:session-event', 'ws:agent-status-update', 'ws:system-status',
    'ws:new-user-session', 'ws:ui-action-result', 'ws:collab-bash-output',
  ]) {
    unlistenFns.push(await listen(eventName, (event) => {
      websocketStore.handle_message(event.payload)
    }))
  }

  // Request initial system status
  await invoke('request_system_status')
}

async function handleWizardComplete() {
  // submitWizard 已完成（配置文件 + mark_configured）
  // 通知 Rust 关闭向导 → 显示 splash → 启动环境 → 显示主窗口
  await invoke('wizard_complete')
  // 后端已启动，触发首次运行初始化（向 SystemAdmin 发送欢迎邮件）
  try {
    await configAPI.firstRunInit({
      user_name: configStore.wizardData.user_name,
    })
  } catch (error) {
    console.error('First-run init failed (non-critical):', error)
  }
}

onMounted(async () => {
  if (windowLabel === 'wizard') {
    appState.value = 'wizard'
    return
  }
  // Main window: backend is already running (started by Rust setup)
  await backendStore.initializeBackend()
  await initializeEventListeners()
  appState.value = 'ready'
})

onUnmounted(() => {
  backendStore.stopHealthMonitoring()
  unlistenFns.forEach(fn => fn())
  unlistenFns = []
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
  <ToastContainer />
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
  background: var(--bg-primary);
}

.app-loading__spinner {
  width: 32px;
  height: 32px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}

.status-indicator {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.status-indicator:hover {
  background: var(--surface-hover);
}

.status-indicator__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  transition: all var(--duration-base) var(--ease-out);
}

.status-indicator__dot--running,
.status-indicator__dot--connected {
  background: var(--success);
}

.status-indicator__dot--stopped,
.status-indicator__dot--disconnected {
  background: var(--error);
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
  background: var(--text-primary);
  color: white;
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  white-space: nowrap;
  z-index: var(--z-tooltip);
}
</style>