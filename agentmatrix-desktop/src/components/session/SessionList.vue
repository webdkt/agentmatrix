<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import SessionItem from './SessionItem.vue'
import NewEmailModal from '@/components/dialog/NewEmailModal.vue'

const { t } = useI18n()
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
  <aside class="session-list">
    <!-- New Email Button (Large, Prominent, Full-Width) -->
    <div class="session-list__header">
      <button
        @click="openNewEmailModal"
        class="session-list__new-email-btn"
      >
        <i class="ti ti-plus session-list__new-email-icon"></i>
        <span>{{ t('sessions.newEmail') }}</span>
      </button>
    </div>

    <!-- Search Box (Full-Width) -->
    <div class="session-list__search">
      <i class="ti ti-search session-list__search-icon"></i>
      <input
        type="text"
        :placeholder="t('sessions.search')"
        :value="searchQuery"
        @input="handleSearch"
        class="session-list__search-input"
      />
    </div>

    <!-- Session List -->
    <div class="session-list__items">
      <!-- Session Items -->
      <SessionItem
        v-for="(session, index) in sessions"
        :key="session.session_id"
        :session="session"
        :index="index"
        :is-active="currentSession?.session_id === session.session_id"
        @click="handleSessionClick(session)"
      />

      <!-- Load More Button -->
      <div v-if="hasMore" class="session-list__load-more">
        <button
          @click="handleLoadMore"
          :disabled="isLoading"
          class="session-list__load-more-btn"
        >
          <i class="ti" :class="isLoading ? 'ti-loader animate-spin' : 'ti-loader'"></i>
          <span>{{ isLoading ? t('sessions.loading') : t('sessions.loadMore') }}</span>
        </button>
      </div>

      <!-- Empty State -->
      <div v-if="sessions.length === 0" class="session-list__empty">
        <div class="session-list__empty-icon">
          <i class="ti ti-messages"></i>
        </div>
        <p class="session-list__empty-text">{{ t('sessions.noSessions') }}</p>
        <p class="session-list__empty-hint">{{ t('sessions.startNew') }}</p>
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
.session-list {
  width: var(--session-list-width);
  height: 100%;
  background: white;
  border-right: 1px solid var(--neutral-200);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

/* Header with New Email Button */
.session-list__header {
  padding: var(--spacing-md);
  padding-bottom: var(--spacing-sm);
}

.session-list__new-email-btn {
  width: 100%;
  height: var(--button-height-md);
  padding: 0 var(--spacing-md);
  background: var(--primary-500);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  box-shadow: var(--shadow-sm);
}

.session-list__new-email-btn:hover {
  background: var(--primary-600);
  box-shadow: var(--shadow-md);
}

.session-list__new-email-btn:active {
  transform: scale(0.98);
}

.session-list__new-email-icon {
  font-size: var(--icon-lg);
}

/* Search Box */
.session-list__search {
  position: relative;
  padding: 0 var(--spacing-md);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--neutral-100);
}

.session-list__search-icon {
  position: absolute;
  left: calc(var(--spacing-md) + 12px);
  top: 50%;
  transform: translateY(-50%);
  font-size: var(--icon-md);
  color: var(--neutral-400);
  pointer-events: none;
}

.session-list__search-input {
  width: 100%;
  height: 36px;
  padding: 0 var(--spacing-sm) 0 36px;
  background: var(--neutral-50);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  color: var(--neutral-700);
  transition: all var(--duration-base) var(--ease-out);
}

.session-list__search-input::placeholder {
  color: var(--neutral-400);
}

.session-list__search-input:focus {
  outline: none;
  border-color: var(--primary-300);
  background: white;
}

/* Session Items Container */
.session-list__items {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm); /* 8px compact spacing */
}

/* Load More Button */
.session-list__load-more {
  padding: var(--spacing-sm);
}

.session-list__load-more-btn {
  width: 100%;
  height: var(--button-height-sm);
  padding: 0 var(--spacing-md);
  background: var(--neutral-100);
  color: var(--neutral-700);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.session-list__load-more-btn:hover:not(:disabled) {
  background: var(--neutral-200);
}

.session-list__load-more-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Empty State */
.session-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-xl) var(--spacing-md);
  text-align: center;
}

.session-list__empty-icon {
  width: 64px;
  height: 64px;
  background: var(--neutral-100);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: var(--neutral-300);
  margin-bottom: var(--spacing-md);
}

.session-list__empty-text {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
  margin: 0;
  margin-bottom: var(--spacing-xs);
}

.session-list__empty-hint {
  font-size: var(--font-xs);
  color: var(--neutral-400);
  margin: 0;
}

/* Animations */
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
