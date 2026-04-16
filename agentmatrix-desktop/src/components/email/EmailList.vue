<script setup>
import { ref, computed, watch, nextTick, onMounted, onUpdated } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import { useAgentStore } from '@/stores/agent'
import { sessionAPI } from '@/api/session'
import { getPlaceholdersForSession, consumeResolvedEmail } from '@/composables/usePendingEmails'
import EmailItem from './EmailItem.vue'
import EmailReply from './EmailReply.vue'
import AgentStatusCard from '../agent/AgentStatusCard.vue'
import NewEmailModal from '@/components/dialog/NewEmailModal.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  user_agent_name: {
    type: String,
    default: 'User'
  },
  selectedAgent: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['agent-selected'])

const { t } = useI18n()
const sessionStore = useSessionStore()
const agentStore = useAgentStore()

const emails = ref([])
const isLoading = ref(false)
const error = ref(null)
const messagesContainer = ref(null)
const showMenu = ref(false)

// 回复对话框状态
const showReplyDialog = ref(false)
const replyEmail = ref(null)

const answer = ref('')
const hideInlineForm = ref(false)
const submittedAnswer = ref(null)
const currentSession = computed(() => sessionStore.currentSession)
const hasEmails = computed(() => emails.value.length > 0)

const hasPlaceholderLast = computed(() => {
  if (emails.value.length === 0) return false
  return !!emails.value[emails.value.length - 1]._isPlaceholder
})

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

  // 仅在初次加载（列表为空）时显示 loading spinner
  // 后台刷新时不显示，避免 EmailReply 被 v-if 销毁导致用户输入丢失
  const isInitialLoad = emails.value.length === 0
  if (isInitialLoad) {
    isLoading.value = true
  }
  error.value = null

  try {
    const result = await sessionAPI.getEmails(sessionId)
    const serverEmails = result.emails || result.sessions || []

    // When loading real emails from server, drop all placeholders
    // (placeholder emails are shown via watch(currentSession) for placeholder sessions only)
    emails.value = serverEmails

    // 标记会话为已读（后端已处理，前端同步更新本地状态）
    sessionStore.markSessionRead(sessionId)

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
    if (newSession._isPlaceholder) {
      // Placeholder session: load from pending map, don't call API
      const placeholders = getPlaceholdersForSession(newSession.session_id)
      emails.value = placeholders.length > 0 ? [...placeholders] : []
      isLoading.value = false
      return
    }

    // Check if there's a resolved email from a new email send (avoids API call)
    const resolved = consumeResolvedEmail(newSession.session_id)
    if (resolved) {
      emails.value = [resolved]
      isLoading.value = false
      sessionStore.markSessionRead(newSession.session_id)
      await nextTick()
      return
    }

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

const handleEmailSendStarted = ({ placeholder }) => {
  emails.value.push(placeholder)
  nextTick(() => scrollToBottom())
}

const handleEmailSendFailed = ({ placeholderId }) => {
  const idx = emails.value.findIndex(e => e.id === placeholderId)
  if (idx !== -1) {
    emails.value.splice(idx, 1)
  }
}

const handleEmailSent = (payload) => {
  // Support new { response, placeholderId } and old response format
  const response = payload?.response || payload
  const placeholderId = payload?.placeholderId
  const email = response?.email

  if (email) {
    if (placeholderId) {
      // 找到 placeholder 并替换为真实邮件
      const idx = emails.value.findIndex(e => e.id === placeholderId)
      if (idx !== -1) {
        emails.value.splice(idx, 1, email)
        return
      }
    }
    // Fallback: append (no placeholder found, or old code path)
    // 必须校验邮件属于当前会话，防止用户快速切换会话后邮件出现在错误的列表中
    const emailSessionId = email.task_id || email.recipient_session_id
    const currentSessionId = currentSession.value?.session_id
    if (emailSessionId && currentSessionId && emailSessionId !== currentSessionId) {
      console.warn('⚠️ Email belongs to different session, skipping append:', emailSessionId, '!=', currentSessionId)
      return
    }
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

// 处理显示回复对话框
const handleShowReplyDialog = (email) => {
  replyEmail.value = email
  showReplyDialog.value = true
}

// 关闭回复对话框
const handleCloseReplyDialog = () => {
  showReplyDialog.value = false
  replyEmail.value = null
}

// 处理回复发送成功
const handleReplySent = (payload) => {
  // Support new { response, placeholderId } and old response format
  const response = payload?.response || payload
  const placeholderId = payload?.placeholderId
  const email = response?.email

  if (email) {
    if (placeholderId) {
      // 找到 placeholder 并替换为真实邮件
      const idx = emails.value.findIndex(e => e.id === placeholderId)
      if (idx !== -1) {
        emails.value.splice(idx, 1, email)
        return
      }
    }
    // Fallback: append (no placeholder found, or old code path)
    handleReplySentWithEmail(email)
  }
}

// 处理回复发送失败
const handleReplySendFailed = ({ placeholderId }) => {
  const idx = emails.value.findIndex(e => e.id === placeholderId)
  if (idx !== -1) {
    emails.value.splice(idx, 1)
  }
}

// 处理回复发送开始（添加 placeholder）
const handleReplySendStarted = ({ placeholder }) => {
  emails.value.push(placeholder)
  nextTick(() => scrollToBottom())
}

const handleAgentSelected = (agentName) => {
  const agentData = agentStore.getAgent(agentName)
  const agentStatus = agentStore.getAgentStatus(agentName)
  const isBusy = agentStatus && agentStatus !== 'IDLE'
  const isWorkingOnOther = isBusy && agentData?.current_user_session_id && agentData.current_user_session_id !== currentSession.value?.session_id

  if (isWorkingOnOther) {
    // Switch to the session the agent is working on
    sessionStore.selectSession({ session_id: agentData.current_user_session_id })
    return
  }

  // Toggle panel
  emit('agent-selected', agentName)
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
          @show-reply-dialog="handleShowReplyDialog"
          v-for="email in emails"
          :key="email.id"
          :email="email"
          :user_agent_name="user_agent_name"
        />

        <!-- Agent Status - 在滚动容器内 -->
        <div class="email-list__agent-status">
          <AgentStatusCard
            v-for="agentName in sessionAgents"
            :key="agentName"
            :agent-name="agentName"
            :current-session-id="currentSession.session_id"
            :is-selected="selectedAgent === agentName"
            @select="handleAgentSelected"
          />
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
      <div class="email-list__question-form">
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
    </div>

    <!-- EmailReply - 固定在底部 -->
    <div v-if="!pendingQuestion || hideInlineForm" class="email-list__bottom-area">
      <EmailReply
        :current-session="currentSession"
        :emails="emails"
        :is-locked="hasPlaceholderLast"
        @send-started="handleEmailSendStarted"
        @sent="handleEmailSent"
        @send-failed="handleEmailSendFailed"
      />
    </div>

    <!-- Reply Email Dialog -->
    <NewEmailModal
      :show="showReplyDialog"
      mode="reply"
      :replyToEmail="replyEmail"
      :session="currentSession"
      @close="handleCloseReplyDialog"
      @send-started="handleEmailSendStarted"
      @sent="handleEmailSent"
      @send-failed="handleEmailSendFailed"
    />
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
  padding: var(--spacing-lg);
  background: var(--parchment-50);
  border: 2px solid var(--accent);
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 12px rgba(194, 59, 34, 0.15);
  position: relative;
  transition: all 0.3s var(--ease-out);
}

/* 输入框聚焦时，表单边框变淡 */
.email-list__question-form:focus-within {
  border-color: var(--parchment-300);
  box-shadow: none;
}

.email-list__question-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.email-list__question-header .m-icon {
  font-size: var(--icon-lg);
  color: var(--accent);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.email-list__question-title {
  font-family: var(--font-serif);
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--ink-900);
  line-height: var(--leading-snug);
}

.email-list__question-text {
  font-size: var(--font-base);
  color: var(--ink-700);
  padding: 0;
  margin: 0 0 var(--spacing-lg) 0;
  line-height: 1.8;
  font-family: var(--font-serif);
}

.email-list__question-input {
  width: 100%;
  padding: var(--spacing-md);
  background: var(--parchment-50);
  border: 1px solid var(--parchment-300);
  border-radius: var(--radius-sm);
  font-size: var(--font-base);
  color: var(--ink-700);
  resize: none;
  margin-bottom: var(--spacing-lg);
  font-family: var(--font-serif);
  line-height: 1.8;
  transition: all var(--duration-base) var(--ease-out);
}

.email-list__question-input:focus {
  outline: none;
  border-color: var(--accent);
  border-width: 2px;
  padding: calc(var(--spacing-md) - 1px);
  box-shadow: 0 0 0 3px rgba(194, 59, 34, 0.1);
  background: var(--parchment-50);
}

.email-list__question-input::placeholder {
  color: var(--ink-400);
  font-style: italic;
}

.email-list__question-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
}

.email-list__question-btn {
  padding: var(--spacing-sm) var(--spacing-lg);
  border: none;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.email-list__question-btn--primary {
  background: var(--ink-900);
  color: var(--parchment-50);
}

.email-list__question-btn--primary:hover:not(:disabled) {
  background: var(--accent);
}

.email-list__question-btn--primary:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}


.email-list__messages {
}

/* 底部控件区域的通用样式 */


.email-list__bottom-area {
  flex-shrink: 0;
  background: var(--parchment-50);
  padding: var(--spacing-md);
}

/* 问题表单特殊样式 */
.email-list__question-form-wrapper {
  /* wrapper本身不设置样式，所有样式在question-form上 */
}

.email-list__question-form {
  padding: var(--spacing-lg);
  background: var(--parchment-50);
  border: 2px solid var(--accent);
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 12px rgba(194, 59, 34, 0.15);
  position: relative;
}
</style>
