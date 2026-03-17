<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useSessionStore } from '@/stores/session'
import { sessionAPI } from '@/api/session'
import MessageItem from './MessageItem.vue'
import MessageReply from './MessageReply.vue'

const props = defineProps({
  user_agent_name: {
    type: String,
    default: 'User'
  }
})

const sessionStore = useSessionStore()

// 状态
const emails = ref([])
const isLoading = ref(false)
const error = ref(null)
const messagesContainer = ref(null)

// Ask User 相关状态
const answer = ref('')
const hideInlineForm = ref(false)

// 计算属性
const currentSession = computed(() => sessionStore.currentSession)
const hasEmails = computed(() => emails.value.length > 0)

// 待处理问题
const pendingQuestion = computed(() => {
  if (!currentSession.value) {
    console.log('🔍 [MessageList] No current session')
    return null
  }
  const sessionId = currentSession.value.session_id
  const question = sessionStore.getPendingQuestion(sessionId)
  console.log('🔍 [MessageList] Checking pending question for session:', sessionId)
  console.log('🔍 [MessageList] Pending question:', question)
  console.log('🔍 [MessageList] Store pendingQuestions:', sessionStore.pendingQuestions)
  return question
})

// 监听 pendingQuestion 变化
watch(pendingQuestion, (newQuestion) => {
  console.log('🔍 [MessageList] pendingQuestion changed:', newQuestion)
}, { immediate: true })

// 监听当前会话变化，加载邮件
watch(currentSession, async (newSession) => {
  console.log('🔍 [MessageList] currentSession changed:', newSession?.session_id)
  if (newSession) {
    await loadEmails(newSession.session_id)
  } else {
    emails.value = []
  }
  // 重置内联表单状态
  answer.value = ''
  hideInlineForm.value = false
}, { immediate: true })

// 加载邮件列表
const loadEmails = async (sessionId) => {
  if (!sessionId) return

  isLoading.value = true
  error.value = null

  try {
    const result = await sessionAPI.getEmails(sessionId)
    emails.value = result.emails || result.conversations || []

    // 滚动到底部
    await nextTick()
    scrollToBottom()
  } catch (err) {
    error.value = err.message
    console.error('Failed to load emails:', err)
  } finally {
    isLoading.value = false
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 刷新邮件列表
const refreshEmails = async () => {
  if (currentSession.value) {
    await loadEmails(currentSession.value.session_id)
  }
}

// 处理回复发送成功
const handleReplySent = async () => {
  // 刷新邮件列表
  await refreshEmails()
}

// 提交 ask_user 回答
const submitAnswer = async () => {
  if (!currentSession.value || !answer.value.trim()) return

  try {
    await sessionStore.submitAskUserAnswer(currentSession.value.session_id, answer.value)
    answer.value = ''
    hideInlineForm.value = false
  } catch (error) {
    alert('提交失败: ' + error.message)
  }
}

// 暂不回答（隐藏表单）
const hideInlineFormHandler = () => {
  hideInlineForm.value = true
}

// 暴露方法给父组件
defineExpose({
  refreshEmails,
  scrollToBottom
})
</script>

<template>
  <main class="flex-1 flex flex-col bg-gradient-to-br from-surface-50/50 to-white relative min-w-0">
    <!-- Chat Header -->
    <header v-if="currentSession" class="glass border-b border-surface-200/60 px-6 py-3.5 flex items-center justify-between z-10 flex-shrink-0">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-400 to-blue-600 flex items-center justify-center text-white shadow-card">
          <i class="ti ti-brain text-base"></i>
        </div>
        <div>
          <h1 class="font-semibold text-surface-900">{{ currentSession.subject || 'New Conversation' }}</h1>
          <div class="flex items-center gap-1.5 text-xs text-surface-500">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            <span>Agent • Online</span>
          </div>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button class="w-9 h-9 rounded-xl text-surface-500 hover:bg-surface-100 hover:text-surface-700 flex items-center justify-center transition-all duration-200 btn-press">
          <i class="ti ti-phone text-lg"></i>
        </button>
        <button class="w-9 h-9 rounded-xl text-surface-500 hover:bg-surface-100 hover:text-surface-700 flex items-center justify-center transition-all duration-200 btn-press">
          <i class="ti ti-dots-vertical text-lg"></i>
        </button>
      </div>
    </header>

    <!-- Messages Container -->
    <div
      ref="messagesContainer"
      class="flex-1 overflow-y-auto px-6 py-6 space-y-6"
    >
      <!-- No Session Selected -->
      <div v-if="!currentSession" class="flex items-center justify-center h-full">
        <div class="text-center">
          <div class="w-20 h-20 mx-auto mb-4 rounded-2xl bg-surface-100 flex items-center justify-center">
            <i class="ti ti-message-circle text-4xl text-surface-300"></i>
          </div>
          <p class="text-surface-600 font-medium">Select a conversation to view messages</p>
        </div>
      </div>

      <!-- Loading State -->
      <div v-else-if="isLoading" class="flex items-center justify-center h-full">
        <div class="text-center">
          <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-primary-100 flex items-center justify-center">
            <i class="ti ti-loader animate-spin text-3xl text-primary-600"></i>
          </div>
          <p class="text-surface-600 font-medium">Loading messages...</p>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="flex items-center justify-center h-full">
        <div class="text-center">
          <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-rose-100 flex items-center justify-center">
            <i class="ti ti-alert-circle text-3xl text-rose-600"></i>
          </div>
          <p class="text-surface-600 font-medium mb-2">Failed to load messages</p>
          <p class="text-surface-500 text-sm mb-4">{{ error }}</p>
          <button
            @click="refreshEmails"
            class="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>

      <!-- Messages -->
      <template v-else>
        <MessageItem
          v-for="email in emails"
          :key="email.id"
          :email="email"
          :user_agent_name="user_agent_name"
        />

        <!-- Empty State (No Messages) -->
        <div v-if="!hasEmails" class="flex items-center justify-center h-full">
          <div class="text-center">
            <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-100 flex items-center justify-center">
              <i class="ti ti-mail-off text-3xl text-surface-300"></i>
            </div>
            <p class="text-surface-600 font-medium">No messages yet</p>
            <p class="text-surface-500 text-sm">Start the conversation</p>
          </div>
        </div>
      </template>
    </div>

    <!-- Ask User 内联表单 -->
    <div
      v-if="pendingQuestion && !hideInlineForm"
      class="px-6 py-4 bg-amber-50 border-t border-amber-200"
    >
      <div class="mb-3">
        <div class="flex items-center gap-2 mb-2">
          <i class="ti ti-message-circle text-amber-600"></i>
          <span class="font-semibold text-amber-900">{{ pendingQuestion.agent_name }} 有一个问题需要你回答</span>
        </div>
        <p class="text-amber-800 text-sm bg-amber-100/50 rounded-lg px-3 py-2">
          {{ pendingQuestion.question }}
        </p>
      </div>

      <textarea
        v-model="answer"
        rows="3"
        placeholder="输入你的回答..."
        class="w-full px-3 py-2 border border-amber-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-400 resize-none"
      />

      <div class="mt-3 flex justify-end gap-2">
        <button
          @click="hideInlineFormHandler"
          class="px-4 py-2 text-sm text-amber-700 hover:bg-amber-100 rounded-lg transition-colors"
        >
          暂不回答
        </button>
        <button
          @click="submitAnswer"
          :disabled="!answer.trim()"
          class="px-4 py-2 text-sm bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          提交回答
        </button>
      </div>
    </div>

    <!-- Message Reply -->
    <MessageReply
      :current-session="currentSession"
      :emails="emails"
      @sent="handleReplySent"
    />
  </main>
</template>

<style scoped>
.glass {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
}

.shadow-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.btn-press {
  transition: all 0.2s;
}

.btn-press:active {
  transform: scale(0.95);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}
</style>
