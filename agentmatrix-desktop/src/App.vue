<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useBackendStore } from '@/stores/backend'
import { useConfigStore } from '@/stores/config'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { useWebSocket } from '@/composables/useWebSocket'
import ViewSelector from '@/components/view-selector/ViewSelector.vue'
import ViewContainer from '@/components/view-container/ViewContainer.vue'
import ColdStartWizard from '@/components/wizard/ColdStartWizard.vue'

const currentView = ref('email')
const backendStore = useBackendStore()
const configStore = useConfigStore()
const sessionStore = useSessionStore()
const websocketStore = useWebSocketStore()
const { isConnected, connect, onMessage } = useWebSocket()

// App state: 'loading' | 'wizard' | 'ready'
const appState = ref('loading')

const backendStatus = computed(() => backendStore.status)
const currentSession = computed(() => sessionStore.currentSession)

const handleViewChange = (viewId) => {
  currentView.value = viewId
}

// 初始化WebSocket连接
async function initializeWebSocket() {
  console.log('🔌 Initializing WebSocket connection...')

  // If backend is running, connect WebSocket
  if (backendStore.isRunning) {
    console.log('✅ Backend is running, connecting WebSocket...')
    connect()
  } else {
    console.log('⏳ Backend not running yet, will connect when ready')
  }

  // 监听 WebSocket 消息
  onMessage((data) => {
    websocketStore.handle_message(data)
  })

  // 注册新邮件回调
  websocketStore.onNewEmail(async (emailData) => {
    console.log('📧 Handling new email from WebSocket:', emailData)
    console.log('📊 Current session:', currentSession.value?.session_id)
    console.log('📊 Email recipient_session_id:', emailData.recipient_session_id || emailData.receiver_session_id)

    // 1. 刷新会话列表（处理新会话）
    await sessionStore.loadSessions()

    // 2. 使用 recipient_session_id 匹配会话
    const sessionId = emailData.recipient_session_id || emailData.receiver_session_id
    if (sessionId) {
      const targetSession = sessionStore.sessions.find(
        s => s.session_id === sessionId
      )

      if (targetSession) {
        if (targetSession.session_id === currentSession.value?.session_id) {
          // 是当前会话 → 强制刷新
          console.log('✅ Email belongs to current session, forcing refresh...')
          await sessionStore.selectSession(targetSession, true)
        } else {
          // 是其他会话 → 切换过去
          console.log('🔄 Email belongs to different session, switching...')
          await sessionStore.selectSession(targetSession, true)
        }
      } else {
        console.log('⚠️ Session not found in list, might be a new session')
      }
    } else {
      console.log('⚠️ Email has no session_id')
    }
  })
}

async function handleWizardComplete() {
  appState.value = 'ready'
  // Backend is now running and configured (submitted by wizard)
  await backendStore.initializeBackend()

  // 初始化WebSocket连接
  await initializeWebSocket()
}

onMounted(async () => {
  try {
    const isFirstRun = await configStore.checkFirstRun()
    if (isFirstRun) {
      appState.value = 'wizard'
      return
    }
    // Warm start
    await backendStore.initializeBackend()

    // 初始化WebSocket连接
    await initializeWebSocket()

    appState.value = 'ready'
  } catch (error) {
    console.error('Failed to initialize:', error)
    appState.value = 'ready' // fallback to normal app
  }
})

onUnmounted(() => {
  backendStore.stopHealthMonitoring()
})
</script>

<template>
  <!-- Wizard: completely separate full-screen experience -->
  <ColdStartWizard v-if="appState === 'wizard'" @complete="handleWizardComplete" />

  <!-- Loading -->
  <div v-else-if="appState === 'loading'" class="app-loading">
    <div class="app-loading__spinner"></div>
  </div>

  <!-- Normal app -->
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

/* Status indicators */
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