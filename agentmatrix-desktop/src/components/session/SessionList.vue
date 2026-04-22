<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { addPendingEmail, removePendingEmail } from '@/composables/usePendingEmails'
import SessionItem from './SessionItem.vue'
import NewEmailModal from '@/components/dialog/NewEmailModal.vue'
import MIcon from '@/components/icons/MIcon.vue'

const { t } = useI18n()
const sessionStore = useSessionStore()

const props = defineProps({
  mode: {
    type: String,
    default: 'email',
    validator: (v) => ['email', 'collab'].includes(v)
  }
})

// Collab wizard (only injected, may be undefined in email mode)
const wizard = inject('collabWizard', null)

// 状态
const searchQuery = ref('')
const showNewEmailModal = ref(false)

// 计算属性
const sessions = computed(() => sessionStore.sessions)
const newButtonLabel = computed(() => props.mode === 'collab' ? t('sessions.newCollab') : t('sessions.newEmail'))
const dialogTitle = computed(() => props.mode === 'collab' ? t('sessions.newCollab') : t('sessions.newEmail'))
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
  // Cancel wizard if active (collab mode)
  if (wizard && wizard.isActive.value) {
    wizard.cancelWizard()
  }
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

// New button click — branches by mode
const handleNewClick = () => {
  if (props.mode === 'collab' && wizard) {
    wizard.enterWizard()
  } else {
    showNewEmailModal.value = true
  }
}

// ---- Email mode only: NewEmailModal placeholder logic ----
const handleNewEmailStarted = (emailData) => {
  const placeholderId = `placeholder-session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

  const placeholderSession = {
    session_id: placeholderId,
    agent_name: emailData.recipient,
    participants: [emailData.recipient],
    subject: emailData.body.substring(0, 50),
    timestamp: new Date().toISOString(),
    last_email_time: new Date().toISOString(),
    is_unread: false,
    _isPlaceholder: true,
  }

  const placeholderEmail = addPendingEmail(placeholderId, emailData)
  placeholderSession._placeholderEmailId = placeholderEmail.id

  sessionStore.sessions.unshift(placeholderSession)
  sessionStore.selectSession(placeholderSession)
  showNewEmailModal.value = false
}

const handleEmailSent = (result) => {
  console.log('Email sent result:', result)

  const placeholderIndex = sessionStore.sessions.findIndex(s => s._isPlaceholder)
  if (placeholderIndex !== -1) {
    sessionStore.sessions.splice(placeholderIndex, 1)
  }

  const email = result.response.email
  const sessionId = email.sender_session_id || result.response.task_id
  const taskId = result.response.task_id

  const realSession = {
    session_id: sessionId,
    agent_name: email.recipient,
    agent_session_id: sessionId,
    task_id: taskId,
    participants: [email.recipient],
    subject: email.subject || email.body.substring(0, 50),
    timestamp: email.timestamp,
    last_email_time: email.timestamp,
    is_unread: false,
    last_email_id: email.id,
  }

  sessionStore.sessions.unshift(realSession)
  sessionStore.buildAgentSessionMap()

  if (sessionStore.currentSession?._isPlaceholder) {
    sessionStore.currentSession = realSession
  } else {
    sessionStore.selectSession(realSession)
  }
}

const handleNewEmailFailed = ({ emailData, error }) => {
  console.error('New email failed:', error)
  const idx = sessionStore.sessions.findIndex(s => s._isPlaceholder)
  if (idx !== -1) {
    const session = sessionStore.sessions[idx]
    if (session._placeholderEmailId) {
      removePendingEmail(session._placeholderEmailId)
    }
    sessionStore.sessions.splice(idx, 1)
  }
}
</script>

<template>
  <aside class="session-list">
    <!-- New Email Button (Large, Prominent, Full-Width) -->
    <div class="session-list__header">
      <button
        @click="handleNewClick"
        class="session-list__new-email-btn"
      >
        <MIcon name="plus" />
        <span>{{ newButtonLabel }}</span>
      </button>
    </div>

    <!-- Search Box (Full-Width) -->
    <div class="session-list__search">
      <MIcon name="search" />
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
          <span :class="{ 'animate-spin': isLoading }"><MIcon name="loader" /></span>
          <span>{{ isLoading ? t('sessions.loading') : t('sessions.loadMore') }}</span>
        </button>
      </div>

      <!-- Empty State -->
      <div v-if="sessions.length === 0" class="session-list__empty">
        <div class="session-list__empty-icon">
          <MIcon name="messages" />
        </div>
        <p class="session-list__empty-text">{{ t('sessions.noSessions') }}</p>
        <p class="session-list__empty-hint">{{ t('sessions.startNew') }}</p>
      </div>
    </div>

    <!-- New Email Modal (email mode only) -->
    <NewEmailModal
      v-if="mode === 'email'"
      :show="showNewEmailModal"
      :title="dialogTitle"
      @close="showNewEmailModal = false"
      @send-started="handleNewEmailStarted"
      @sent="handleEmailSent"
      @send-failed="handleNewEmailFailed"
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
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.session-list__new-email-btn:hover {
  opacity: 0.9;
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
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--neutral-200);
  border-radius: 0;
  font-size: var(--font-sm);
  color: var(--neutral-700);
  transition: all var(--duration-base) var(--ease-out);
}

.session-list__search-input::placeholder {
  color: var(--neutral-400);
}

.session-list__search-input:focus {
  outline: none;
  border-bottom-color: var(--accent);
  background: transparent;
}

/* Session Items Container */
.session-list__items {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm) 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm); /* 8px compact spacing */
}

/* Load More Button */
.session-list__load-more {
  padding: var(--spacing-sm) 0;
}

.session-list__load-more-btn {
  width: 100%;
  height: var(--button-height-sm);
  padding: 0 var(--spacing-md);
  background: var(--neutral-100);
  color: var(--neutral-700);
  border: none;
  border-radius: var(--radius-sm);
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
  border-radius: var(--radius-sm);
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

</style>
