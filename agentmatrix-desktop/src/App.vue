<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { useWebSocket } from '@/composables/useWebSocket'
import ConversationList from '@/components/conversation/ConversationList.vue'
import MessageList from '@/components/message/MessageList.vue'
import SettingsPanel from '@/components/settings/SettingsPanel.vue'
import AskUserDialog from '@/components/dialog/AskUserDialog.vue'

const currentView = ref('conversations') // 'conversations' or 'settings'
const sessionStore = useSessionStore()
const websocketStore = useWebSocketStore()
const { isConnected, connect, onMessage } = useWebSocket()

// 计算属性
const currentSession = computed(() => sessionStore.currentSession)
const user_agent_name = computed(() => 'DKT') // 可以从配置中读取

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
  // 初始化 WebSocket 连接
  connect()

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
    <!-- Top Navigation Bar -->
    <header class="bg-white border-b border-surface-200 px-4 py-3 flex-shrink-0">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center">
            <i class="ti ti-robot text-xl text-white"></i>
          </div>
          <div>
            <h1 class="text-lg font-bold text-surface-900">AgentMatrix</h1>
            <p class="text-xs text-surface-500">Vue 3 + Vite Migration</p>
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
