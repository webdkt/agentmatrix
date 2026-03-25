<script setup>
import { ref, computed, watch, nextTick, onMounted, onUpdated } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { useAgentStore } from '@/stores/agent'
import { sessionAPI } from '@/api/session'
import EmailItem from './EmailItem.vue'
import EmailReply from './EmailReply.vue'
import AgentStatusIndicator from '../agent/AgentStatusIndicator.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  user_agent_name: {
    type: String,
    default: 'User'
  }
})

const { t } = useI18n()
const sessionStore = useSessionStore()
const agentStore = useAgentStore()

const emails = ref([])
const isLoading = ref(false)
const error = ref(null)
const messagesContainer = ref(null)
const inlineReplyEmail = ref(null)
const showInlineReply = ref(false)
const showMenu = ref(false)

const answer = ref('')
const hideInlineForm = ref(false)
const submittedAnswer = ref(null)
const currentSession = computed(() => sessionStore.currentSession)
const hasEmails = computed(() => emails.value.length > 0)

// 判断是否需要底部对齐：内容是否超出容器
const shouldAlignBottom = ref(false)

const checkAlignment = () => {
  if (!messagesContainer.value || !hasEmails.value) {
    shouldAlignBottom.value = false
    return
  }
  
  const container = messagesContainer.value
  
  // 更可靠的方式：检查是否可以滚动
  // 如果scrollHeight > clientHeight，说明内容溢出
  const hasScrollbar = container.scrollHeight > container.clientHeight
  
  // 或者：检查scrollWidth是否大于clientWidth（横向滚动条也会影响）
  const actuallyOverflows = container.scrollHeight > container.clientHeight
  
  console.log('📏 Overflow check:', {
    containerHeight: container.clientHeight,
    scrollHeight: container.scrollHeight,
    hasScrollbar,
    actuallyOverflows,
    emailCount: emails.value.length,
    // 额外信息
    scrollBottom: container.scrollHeight - container.clientHeight
  })
  
  shouldAlignBottom.value = actuallyOverflows
}

// 监听邮件数量变化
// emails变化时，更新显示对齐方式
watch(emails, async () => {
  // 等待DOM完全渲染
  await nextTick()
  // 等待一帧，确保子组件（EmailItem）完全渲染
  requestAnimationFrame(() => {
    checkAlignment()
  })
}, { flush: 'post' })

const sessionAgents = computed(() => {
  if (!emails.value || emails.value.length === 0) {
    return []
  }

  const agentSet = new Set()

  emails.value.forEach(email => {
    if (email.sender && email.sender !== props.user_agent_name) {
      agentSet.add(email.sender)
    }
    if (email.recipient && email.recipient !== props.user_agent_name) {
      agentSet.add(email.recipient)
    }
  })

  const agents = Array.from(agentSet)
  return agents
})

const loadEmails = async (sessionId) => {
  if (!sessionId) return

  isLoading.value = true
  error.value = null

  try {
    const result = await sessionAPI.getEmails(sessionId)
    emails.value = result.emails || result.sessions || []

    await nextTick()
  } catch (err) {
    error.value = err.message
    console.error('Failed to load emails:', err)
  } finally {
    isLoading.value = false
  }
}

const pendingQuestion = computed(() => {
  if (!currentSession.value) {
    return null
  }
  const sessionId = currentSession.value.session_id
  const question = sessionStore.getPendingQuestion(sessionId)
  return question
})

watch(pendingQuestion, (newQuestion) => {
}, { immediate: true })

watch(currentSession, async (newSession) => {
  if (newSession) {
    await loadEmails(newSession.session_id)
  } else {
    emails.value = []
  }
  answer.value = ''
  hideInlineForm.value = false
}, { immediate: true })

const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const refreshEmails = async () => {
  if (currentSession.value) {
    await loadEmails(currentSession.value.session_id)
  }
}

const handleReplySent = async () => {
  // Deprecated: 这个方法保留用于向后兼容，但新的实现使用 handleReplySentWithEmail
  await refreshEmails()
}

const handleReplySentWithEmail = (email) => {
  // 新的实现：直接将邮件添加到列表，无需刷新
  if (email) {
    emails.value.push(email)
    // 滚动到底部
    nextTick(() => {
      scrollToBottom()
    })
  }
}

const handleMenuAction = async (action) => {
  showMenu.value = false

  if (action === 'refresh') {
    await refreshEmails()
  } else if (action === 'delete') {
    console.log('Delete session - to be implemented')
  }
}

const handleInlineReply = (email) => {
  inlineReplyEmail.value = email
  showInlineReply.value = true
}

const cancelInlineReply = () => {
  inlineReplyEmail.value = null
  showInlineReply.value = false
}

const handleInlineReplySent = async (response) => {
  // 如果响应中包含 email 对象，直接添加到列表
  if (response && response.email) {
    handleReplySentWithEmail(response.email)
  } else {
    // 降级到刷新整个列表（向后兼容）
    await handleReplySent()
  }
  inlineReplyEmail.value = null
  showInlineReply.value = false
}

const handleAgentQuestionSubmit = async () => {
  if (!answer.value.trim() || !currentSession.value) return

  const sessionId = currentSession.value.session_id
  const question = sessionStore.getPendingQuestion(sessionId)

  try {
    await sessionStore.submitAskUserAnswer(sessionId, answer.value)

    submittedAnswer.value = {
      question: question?.question || '',
      answer: answer.value,
      agentName: question?.agent_name || 'Agent',
      timestamp: new Date()
    }

    answer.value = ''
    hideInlineForm.value = false

    console.log('✅ Agent question answered, temporary display added')
  } catch (error) {
    console.error('❌ Failed to submit answer:', error)
    alert('Failed to submit answer: ' + error.message)
  }
}
</script>

<template>
  <main class="email-list">
    <header v-if="currentSession" class="email-list__toolbar">
      <div class="email-list__toolbar-right">
        <button
          @click="refreshEmails"
          class="email-list__toolbar-btn"
          :title="t('emails.refresh')"
        >
          <MIcon name="refresh" />
        </button>
        <div class="email-list__toolbar-divider"></div>
        <button
          @click="showMenu = !showMenu"
          class="email-list__toolbar-btn"
          title="More options"
        >
          <MIcon name="dots-vertical" />
        </button>

        <div v-if="showMenu" class="email-list__menu">
          <button
            @click="handleMenuAction('delete')"
            class="email-list__menu-item"
          >
            <MIcon name="trash" />
            <span>Delete Session</span>
          </button>
          <button
            @click="handleMenuAction('refresh')"
            class="email-list__menu-item"
          >
            <MIcon name="refresh" />
            <span>Refresh</span>
          </button>
        </div>
      </div>
    </header>

    <div
      ref="messagesContainer"
      class="email-list__messages"
      :class="{
        'email-list__messages--align-bottom': shouldAlignBottom,
        'email-list__messages--align-top': !shouldAlignBottom
      }"
    >
      <div v-if="!currentSession" class="email-list__empty">
        <div class="email-list__empty-icon">
          <MIcon name="message-circle" />
        </div>
        <p class="email-list__empty-text">{{ t('emails.selectSession') }}</p>
      </div>

      <div v-else-if="isLoading" class="email-list__empty">
        <div class="email-list__empty-icon email-list__empty-icon--loading">
          <span class="animate-spin"><MIcon name="loader" /></span>
        </div>
        <p class="email-list__empty-text">{{ t('sessions.loading') }}</p>
      </div>

      <div v-else-if="error" class="email-list__empty">
        <div class="email-list__empty-icon email-list__empty-icon--error">
          <MIcon name="alert-circle" />
        </div>
        <p class="email-list__empty-text">{{ t('common.error') }}</p>
        <p class="email-list__empty-hint">{{ error }}</p>
        <button
          @click="refreshEmails"
          class="email-list__retry-btn"
        >
          {{ t('common.save') }} Retry
        </button>
      </div>

      <template v-else>
        <EmailItem
          @reply="handleInlineReply"
          v-for="email in emails"
          :key="email.id"
          :email="email"
          :user_agent_name="user_agent_name"
        />

        <!-- Agent Status - 在滚动容器内 -->
        <div class="email-list__agent-status">
          <AgentStatusIndicator
            v-for="agentName in sessionAgents"
            :key="agentName"
            :agent-name="agentName"
            :current-session-id="currentSession.session_id"
          />
        </div>

        <div v-if="pendingQuestion" class="qa-temp-display">
          <div class="email-item">
            <div class="email-card email-card--question">
              <div class="email-card__header">
                <span class="email-card__label">Question</span>
                <span class="email-card__name">
                  <MIcon name="help" />
                  {{ pendingQuestion.agent_name }}
                </span>
                <span class="email-card__time">Just now</span>
              </div>
              <div class="email-card__content">
                <div class="email-card__body">
                  {{ pendingQuestion.question }}
                </div>
              </div>
            </div>
          </div>

          <div v-if="submittedAnswer" class="email-item">
            <div class="email-card email-card--answer">
              <div class="email-card__header">
                <span class="email-card__label">Answer</span>
                <span class="email-card__name">
                  <MIcon name="user" />
                  {{ user_agent_name }}
                </span>
                <span class="email-card__time">Just now</span>
              </div>
              <div class="email-card__content">
                <div class="email-card__body">
                  {{ submittedAnswer.answer }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="!hasEmails" class="email-list__empty">
          <div class="email-list__empty-icon">
            <MIcon name="mail-off" />
          </div>
          <p class="email-list__empty-text">{{ t('emails.noEmails') }}</p>
          <p class="email-list__empty-hint">{{ t('emails.startConversation') }}</p>
        </div>

      </template>
    </div>

    <!-- Agent 问题回答表单 - 固定在底部 -->
    <div
      v-if="pendingQuestion && !hideInlineForm"
      class="email-list__bottom-area email-list__question-form-wrapper"
    >
      <div class="email-list__question-header">
        <MIcon name="message-circle" />
        <span class="email-list__question-title">{{ pendingQuestion.agent_name }} {{ t('emails.hasQuestion') }}</span>
      </div>
      <p class="email-list__question-text">
        {{ pendingQuestion.question }}
      </p>
      <textarea
        v-model="answer"
        rows="3"
        :placeholder="t('emails.questionPlaceholder')"
        class="email-list__question-input"
      />
      <div class="email-list__question-actions">
        <button
          @click="handleAgentQuestionSubmit"
          :disabled="!answer.trim()"
          class="email-list__question-btn email-list__question-btn--primary"
        >
          {{ t('common.submit') }}
        </button>
      </div>
    </div>

    <!-- EmailReply - 固定在底部 -->
    <div v-if="!pendingQuestion || hideInlineForm" class="email-list__bottom-area">
      <EmailReply
        :current-session="currentSession"
        :emails="emails"
        :inline-email="inlineReplyEmail"
        :show-inline="showInlineReply"
        @sent="handleInlineReplySent"
        @cancel-inline="cancelInlineReply"
      />
    </div>
  </main>
</template>

<style scoped>
.email-list {
  flex: 1;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--neutral-50);
  position: relative;
  overflow: hidden;
}

.email-list__toolbar {
  height: 48px;
  background: white;
  border-bottom: 1px solid var(--neutral-200);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 var(--spacing-md);
  flex-shrink: 0;
}

.email-list__toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  position: relative;
}

.email-list__toolbar-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--neutral-500);
  font-size: var(--icon-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.email-list__toolbar-btn:hover {
  background: var(--neutral-100);
  color: var(--neutral-700);
}

.email-list__toolbar-divider {
  width: 1px;
  height: 20px;
  background: var(--neutral-200);
  margin: 0 var(--spacing-xs);
}

.email-list__menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: white;
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  min-width: 160px;
  z-index: var(--z-dropdown);
  overflow: hidden;
}

.email-list__menu-item {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  background: transparent;
  color: var(--neutral-700);
  font-size: var(--font-sm);
  text-align: left;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.email-list__menu-item:hover {
  background: var(--neutral-50);
}

.email-list__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

/* 邮件多时：底部对齐 */
.email-list__messages--align-bottom {
  justify-content: flex-end;
}

/* 邮件少时：顶部对齐（默认） */
.email-list__messages--align-top {
  justify-content: flex-start;
}

.email-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.email-list__empty-icon {
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

.email-list__empty-icon--loading {
  background: var(--parchment-50);
  color: var(--accent);
}

.email-list__empty-icon--error {
  background: var(--error-50);
  color: var(--error-500);
}

.email-list__empty-text {
  font-size: var(--font-base);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
  margin: 0 0 var(--spacing-xs) 0;
}

.email-list__empty-hint {
  font-size: var(--font-sm);
  color: var(--neutral-400);
  margin: 0 0 var(--spacing-md) 0;
}

.email-list__retry-btn {
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.email-list__retry-btn:hover {
  opacity: 0.9;
}

.email-list__question-form {
  flex-shrink: 0;
  padding: var(--spacing-md);
  background: var(--warning-50);
  border-top: 2px solid var(--warning-300);
}

.email-list__question-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.email-list__question-header i {
  font-size: var(--icon-md);
  color: var(--warning-600);
}

.email-list__question-title {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--warning-900);
}

.email-list__question-text {
  font-size: var(--font-sm);
  color: var(--warning-800);
  background: var(--warning-100);
  border-radius: var(--radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  margin: 0 0 var(--spacing-md) 0;
}

.email-list__question-input {
  width: 100%;
  padding: var(--spacing-sm);
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--warning-300);
  border-radius: 0;
  font-size: var(--font-sm);
  color: var(--neutral-700);
  resize: none;
  margin-bottom: var(--spacing-md);
  font-family: inherit;
}

.email-list__question-input:focus {
  outline: none;
  border-bottom-color: var(--accent);
}

.email-list__question-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
}

.email-list__question-btn {
  padding: var(--spacing-xs) var(--spacing-md);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.email-list__question-btn--primary {
  background: var(--accent);
  color: white;
}

.email-list__question-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}

.email-list__question-btn--primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}



.qa-temp-display {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  animation: qaFadeIn 300ms var(--ease-out);
}

@keyframes qaFadeIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.email-card--question {
  background: var(--warning-50);
  border-color: var(--warning-200);
}

.email-card--answer {
  background: var(--success-50);
  border-color: var(--success-200);
}

.email-card--question .email-card__label {
  background: var(--warning-100);
  color: var(--warning-700);
}

.email-card--answer .email-card__label {
  background: var(--success-100);
  color: var(--success-700);
}

.email-card--question .email-card__name i,
.email-card--answer .email-card__name i {
  color: var(--neutral-400);
  margin-right: 4px;
}

/* Agent Status 容器 - 在滚动容器内 */
.email-list__agent-status {
  padding: var(--spacing-sm) var(--spacing-md);
  margin-bottom: var(--spacing-md);
  min-height: 60px;
}

/* 确保底部有足够空间给悬浮控件 */
.email-list__messages {
}

/* 底部控件区域的通用样式 */


.email-list__bottom-area {
  flex-shrink: 0;
  background: white;
  border-top: 1px solid var(--neutral-100);
  padding: var(--spacing-md);
}

/* 问题表单特殊样式 */
.email-list__question-form-wrapper {
  background: var(--warning-50);
  border-top: 1px solid var(--warning-200);
}
</style>
