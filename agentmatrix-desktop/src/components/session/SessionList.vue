<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import SessionItem from './SessionItem.vue'
import NewEmailModal from '@/components/dialog/NewEmailModal.vue'

const sessionStore = useSessionStore()

// 状态
const searchQuery = ref('')
const showNewEmailModal = ref(false)

// 计算属性
const sessions = computed(() => sessionStore.sessions)
const currentSession = computed(() => sessionStore.currentSession)
const hasMore = computed(() => sessionStore.hasMoreSessions)
const isLoading = computed(() => sessionStore.isLoading)

// 生命周期
onMounted(async () => {
  try {
    await sessionStore.loadSessions()
  } catch (error) {
    console.error('Failed to load sessions:', error)
  }
})

// 方法
const handleSessionClick = async (session) => {
  await sessionStore.selectSession(session)
}

const handleLoadMore = async () => {
  try {
    await sessionStore.loadSessions(true)
  } catch (error) {
    console.error('Failed to load more sessions:', error)
  }
}

const handleSearch = (event) => {
  const query = event.target.value
  searchQuery.value = query
  sessionStore.searchSessions(query)
}

// 打开新建会话对话框
const openNewEmailModal = () => {
  showNewEmailModal.value = true
}

// 邮件发送成功后重新加载会话列表
const handleEmailSent = async (result) => {
  console.log('Email sent result:', result)

  // 重新加载会话列表
  await sessionStore.loadSessions()

  // 尝试自动选择新会话
  // 策略1: 如果返回了 session_id，直接选择
  if (result && result.session_id) {
    const newSession = sessions.value.find(s => s.session_id === result.session_id)
    if (newSession) {
      console.log('Auto-selecting session by ID:', newSession)
      await sessionStore.selectSession(newSession)
      return
    }
  }

  // 策略2: 如果返回了 agent name，选择第一个匹配的会话
  if (result && result.recipient) {
    const matchedSession = sessions.value.find(s => {
      const participants = s.participants || []
      return participants.includes(result.recipient)
    })
    if (matchedSession) {
      console.log('Auto-selecting session by recipient:', matchedSession)
      await sessionStore.selectSession(matchedSession)
      return
    }
  }

  // 策略3: 选择最新创建的会话（列表第一个）
  if (sessions.value.length > 0) {
    const latestSession = sessions.value[0]
    console.log('Auto-selecting latest session:', latestSession)
    await sessionStore.selectSession(latestSession)
  }
}
</script>

<template>
  <aside class="w-[320px] bg-white border-r border-surface-200/60 flex flex-col flex-shrink-0">
    <!-- Panel Header -->
    <div class="px-5 py-4 border-b border-surface-100">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold text-surface-900 tracking-tight">Sessions</h2>
        <button
          @click="openNewEmailModal"
          class="w-9 h-9 rounded-xl bg-primary-50 text-primary-600 hover:bg-primary-100 flex items-center justify-center transition-all duration-200 btn-press shadow-soft"
          title="New conversation"
        >
          <i class="ti ti-plus text-lg"></i>
        </button>
      </div>

      <!-- Search -->
      <div class="relative">
        <i class="ti ti-search absolute left-3 top-1/2 -translate-y-1/2 text-surface-400"></i>
        <input
          type="text"
          placeholder="Search sessions..."
          :value="searchQuery"
          @input="handleSearch"
          class="w-full pl-10 pr-4 py-3 bg-surface-50 border border-surface-200 rounded-xl text-sm text-surface-700 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-300 transition-all duration-200"
        />
      </div>
    </div>

    <!-- Session List -->
    <div class="flex-1 overflow-y-auto p-3 space-y-1">
      <!-- Conversation Items -->
      <SessionItem
        v-for="(session, index) in sessions"
        :key="session.session_id"
        :session="session"
        :index="index"
        :is-active="currentSession?.session_id === session.session_id"
        @click="handleSessionClick(session)"
      />

      <!-- Load More Button -->
      <div v-if="hasMore" class="p-3">
        <button
          @click="handleLoadMore"
          :disabled="isLoading"
          class="w-full py-2.5 px-4 bg-surface-100 hover:bg-surface-200 text-surface-700 rounded-xl text-sm font-medium transition-colors duration-200 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <i class="ti" :class="isLoading ? 'ti-loader animate-spin' : 'ti-loader'"></i>
          {{ isLoading ? 'Loading...' : 'Load More Sessions' }}
        </button>
      </div>

      <!-- Empty State -->
      <div v-if="sessions.length === 0" class="p-8 text-center">
        <div class="w-16 h-16 mx-auto mb-4 rounded-2xl bg-surface-100 flex items-center justify-center">
          <i class="ti ti-messages text-3xl text-surface-300"></i>
        </div>
        <p class="text-surface-500 text-sm">No sessions yet</p>
        <p class="text-surface-400 text-xs mt-1">Start a new conversation to begin</p>
      </div>
    </div>

    <!-- New Email Modal -->
    <NewEmailModal
      :show="showNewEmailModal"
      @close="showNewEmailModal = false"
      @sent="handleEmailSent"
    />
  </aside>
</template>

<style scoped>
.shadow-soft {
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
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
