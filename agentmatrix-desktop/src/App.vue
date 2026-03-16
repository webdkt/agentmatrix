<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { useWebSocket } from '@/composables/useWebSocket'
import { useBackendStore } from '@/stores/backend'
import { useNotifications } from '@/composables/useNotifications'
import ConversationList from '@/components/conversation/ConversationList.vue'
import MessageList from '@/components/message/MessageList.vue'
import SettingsPanel from '@/components/settings/SettingsPanel.vue'
import AskUserDialog from '@/components/dialog/AskUserDialog.vue'

const currentView = ref('conversations') // 'conversations' or 'settings'
const sessionStore = useSessionStore()
const websocketStore = useWebSocketStore()
const backendStore = useBackendStore()
const { isConnected, connect, onMessage } = useWebSocket()
const { requestPermission } = useNotifications()

// Backend management
const showBackendPrompt = ref(false)
const backendCheckDone = ref(false)

// 计算属性
const currentSession = computed(() => sessionStore.currentSession)
const user_agent_name = computed(() => 'DKT') // 可以从配置中读取
const backendStatus = computed(() => backendStore.status)

// Backend startup check
const checkBackend = async () => {
  if (backendCheckDone.value) return

  const isRunning = await backendStore.checkBackend()
  console.log('Backend status check:', isRunning ? 'running' : 'not running')

  if (!isRunning) {
    // Show prompt to start backend
    showBackendPrompt.value = true
  }

  backendCheckDone.value = true
}

// Handle backend startup
const startBackend = async () => {
  try {
    await backendStore.startBackend()
    showBackendPrompt.value = false

    // After backend starts, initialize WebSocket
    connect()
  } catch (error) {
    console.error('Failed to start backend:', error)
  }
}

// 对话框显示状态
const showAskUserDialog = ref(false)

// 监听 session 变化，自动弹出对话框
watch(currentSession, (newSession) => {
  if (newSession && sessionStore.shouldShowAskUserDialog(newSession.session_id)) {
    // 延迟 300ms 弹出（让用户先看到 session 切换）
    setTimeout(() => {
      showAskUserDialog.value = true
    }, 300)
  } else {
    showAskUserDialog.value = false
  }
})

// 处理对话框提交
const handleDialogSubmitted = () => {
  // 提交成功后的处理（如果需要）
  console.log('✅ Ask user dialog submitted')
}

// 生命周期
onMounted(async () => {
  // Request notification permission
  await requestPermission()

  // Check backend status
  await checkBackend()

  // If backend is already running, connect WebSocket
  if (backendStore.isRunning) {
    connect()
  }

  // 监听 WebSocket 消息
  onMessage((data) => {
    websocketStore.handle_message(data)
  })

  // 注册新邮件回调
  websocketStore.onNewEmail(async (emailData) => {
    console.log('📧 Handling new email from WebSocket:', emailData)
    console.log('📊 Current session:', currentSession.value?.session_id)
    console.log('📊 Email receiver_session_id:', emailData.receiver_session_id)

    // 1. 刷新会话列表（处理新会话）
    await sessionStore.loadSessions()

    // 2. 使用 receiver_session_id 匹配会话
    if (emailData.receiver_session_id) {
      const targetSession = sessionStore.sessions.find(
        s => s.session_id === emailData.receiver_session_id
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
      console.log('⚠️ Email has no receiver_session_id')
    }
  })
})
</script>

<template>
  <div class="h-screen bg-surface-50 flex flex-col overflow-hidden">
    <!-- Backend Startup Prompt -->
    <div
      v-if="showBackendPrompt"
      class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
    >
      <div class="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
        <div class="text-center">
          <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-primary-100 flex items-center justify-center">
            <i class="ti ti-server text-3xl text-primary-600"></i>
          </div>
          <h2 class="text-2xl font-bold text-surface-900 mb-2">Backend Not Running</h2>
          <p class="text-surface-600 mb-6">
            The AgentMatrix backend server is not running. Would you like to start it?
          </p>
          <div class="flex gap-3">
            <button
              @click="startBackend"
              :disabled="backendStore.isStarting"
              class="flex-1 px-4 py-3 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <span v-if="backendStore.isStarting">Starting...</span>
              <span v-else>Start Backend</span>
            </button>
            <button
              @click="showBackendPrompt = false"
              class="flex-1 px-4 py-3 bg-surface-200 text-surface-700 rounded-xl font-medium hover:bg-surface-300 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Top Navigation Bar -->
    <header class="bg-white border-b border-surface-200 px-4 py-3 flex-shrink-0">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center">
            <i class="ti ti-robot text-xl text-white"></i>
          </div>
          <div>
            <h1 class="text-lg font-bold text-surface-900">AgentMatrix</h1>
            <p class="text-xs text-surface-500">Desktop Application</p>
          </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="flex items-center gap-2">
          <button
            @click="currentView = 'conversations'"
            :class="currentView === 'conversations' ? 'bg-primary-50 text-primary-600' : 'text-surface-500 hover:bg-surface-100'"
            class="px-4 py-2 rounded-xl font-medium transition-all duration-200 flex items-center gap-2"
          >
            <i class="ti ti-messages"></i>
            <span>Conversations</span>
          </button>
          <button
            @click="currentView = 'settings'"
            :class="currentView === 'settings' ? 'bg-primary-50 text-primary-600' : 'text-surface-500 hover:bg-surface-100'"
            class="px-4 py-2 rounded-xl font-medium transition-all duration-200 flex items-center gap-2"
          >
            <i class="ti ti-settings"></i>
            <span>Settings</span>
          </button>
        </div>

        <!-- Connection Status -->
        <div class="flex items-center gap-2">
          <!-- Backend Status -->
          <span
            :class="{
              'bg-green-50 text-green-600': backendStatus === 'running',
              'bg-rose-50 text-rose-600': backendStatus === 'stopped',
              'bg-yellow-50 text-yellow-600': backendStatus === 'starting' || backendStatus === 'stopping'
            }"
            class="px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1"
          >
            <span
              :class="{
                'bg-green-500': backendStatus === 'running',
                'bg-rose-500': backendStatus === 'stopped',
                'bg-yellow-500': backendStatus === 'starting' || backendStatus === 'stopping'
              }"
              class="w-1.5 h-1.5 rounded-full"
            ></span>
            <span>{{ backendStatus.charAt(0).toUpperCase() + backendStatus.slice(1) }}</span>
          </span>

          <!-- WebSocket Status -->
          <span
            :class="isConnected ? 'bg-green-50 text-green-600' : 'bg-rose-50 text-rose-600'"
            class="px-2 py-1 rounded-full text-xs font-medium flex items-center gap-1"
          >
            <span
              :class="isConnected ? 'bg-green-500' : 'bg-rose-500'"
              class="w-1.5 h-1.5 rounded-full"
            ></span>
            <span>{{ isConnected ? 'Connected' : 'Connecting...' }}</span>
          </span>
        </div>
      </div>
    </header>

    <!-- Main Content Area -->
    <div class="flex-1 flex overflow-hidden">
      <!-- Conversations View -->
      <div v-show="currentView === 'conversations'" class="flex-1 flex">
        <!-- Conversation List -->
        <ConversationList />

        <!-- Message List -->
        <MessageList :user_agent_name="user_agent_name" />
      </div>

      <!-- Settings View -->
      <div v-show="currentView === 'settings'" class="flex-1">
        <SettingsPanel />
      </div>
    </div>

    <!-- Ask User 对话框 -->
    <AskUserDialog
      :show="showAskUserDialog"
      @close="showAskUserDialog = false"
      @submitted="handleDialogSubmitted"
    />
  </div>
</template>

<style scoped>
/* 添加动画效果 */
@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}
</style>
