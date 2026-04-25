<script setup>
import { ref, computed, inject, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { sessionAPI } from '@/api/session'
import { addPendingEmail, removePendingEmail } from '@/composables/usePendingEmails'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  currentSession: {
    type: Object,
    default: null
  },
  emails: {
    type: Array,
    default: () => []
  },
  isLocked: {
    type: Boolean,
    default: false
  }
})

const { t } = useI18n()
const emit = defineEmits(['sent', 'send-started', 'send-failed'])

// 状态
const replyBody = ref('')
const isSending = ref(false)
const textareaRef = ref(null)

// Collab draft message — set by CollabPanel on file drop
const collabDraftMessage = inject('collabDraftMessage', null)
watch(collabDraftMessage, (val) => {
  if (val) {
    replyBody.value = val
    collabDraftMessage.value = ''
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.style.height = 'auto'
        textareaRef.value.style.height = Math.min(textareaRef.value.scrollHeight, 200) + 'px'
      }
    })
  }
})

// 计算属性
const canSend = computed(() => {
  return replyBody.value.trim() && props.currentSession && !isSending.value && !props.isLocked
})

const lastEmail = computed(() => {
  if (props.emails.length === 0) return null
  return props.emails[props.emails.length - 1]
})

const placeholder = computed(() => {
  if (props.emails.length === 0) {
    return t('emails.sendMessage')
  }
  // For reply to specific email, use the same message
  return t('emails.sendMessage')
})

// Helper function to get recipient name from email
const getRecipient = (email) => {
  if (!email) return ''
  if (email.is_from_user) {
    return email.recipient || props.currentSession?.agent_name || 'Agent'
  } else {
    return email.sender || 'Agent'
  }
}

// 发送回复
const sendReply = async () => {
  if (!canSend.value) return

  isSending.value = true
  let emailData
  let placeholder = null

  try {
    emailData = {
      recipient: props.currentSession.agent_name,
      subject: '',
      body: replyBody.value,
      task_id: props.currentSession.task_id || props.currentSession.session_id,
      in_reply_to: props.currentSession.last_email_id || undefined,
      recipient_session_id: props.currentSession.agent_session_id || undefined,
    }

    // 创建 placeholder，立即通知父组件
    placeholder = addPendingEmail(props.currentSession.session_id, emailData)
    emit('send-started', { placeholder, emailData })

    // 清空输入
    replyBody.value = ''

    // 调用 API 发送
    const response = await sessionAPI.sendEmail(
      props.currentSession.session_id,
      emailData
    )

    console.log('✅ Reply sent:', response)

    // 清理 placeholder
    removePendingEmail(placeholder.id)
    emit('sent', { response, placeholderId: placeholder.id })
  } catch (error) {
    console.error('❌ Failed to send reply:', error)
    if (placeholder) {
      removePendingEmail(placeholder.id)
      emit('send-failed', { placeholderId: placeholder.id, error: error.message })
    }
    alert(`${t('emails.sendError')}: ${error.message}`)
  } finally {
    isSending.value = false
  }
}

// 处理键盘事件：Enter 换行，Ctrl+Enter 发送
const handleKeyDown = (event) => {
  if (event.key === 'Enter' && event.ctrlKey) {
    event.preventDefault()
    sendReply()
  }
  // Enter 键不阻止默认行为，允许换行
}

// 自动调整文本框高度
const adjustHeight = (event) => {
  const textarea = event.target
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px' // 增加最大高度到200px
}
</script>

<template>
  <!-- Floating Reply (bottom only) -->
  <div class="email-reply">
    <!-- Reply Info (only for bottom reply) -->
    <div v-if="emails.length > 0" class="email-reply__info">
      <span class="email-reply__info-text">
        <MIcon name="arrow-back-up" />
        {{ t('emails.replyTo') }}
        <span class="email-reply__info-name">
          {{ getRecipient(lastEmail) }}
        </span>
      </span>
    </div>

    <!-- Reply Container -->
    <div class="email-reply__container">
      <!-- Textarea -->
      <textarea
        ref="textareaRef"
        v-model="replyBody"
        @keydown="handleKeyDown"
        @input="adjustHeight"
        :placeholder="placeholder"
        :disabled="isLocked"
        rows="1"
        class="email-reply__textarea"
      ></textarea>

      <!-- Send button -->
      <button
        @click="sendReply"
        :disabled="!canSend"
        class="email-reply__send"
        :title="t('emails.send')"
      >
        <MIcon v-if="!isSending" name="send" />
        <span v-else class="animate-spin"><MIcon name="loader" /></span>
      </button>
    </div>

    <!-- Hint -->
    <div class="email-reply__hint">
      <span v-if="isLocked" class="email-reply__hint-text">Sending...</span>
      <span v-else class="email-reply__hint-text">Ctrl+Enter {{ t('emails.send') }}</span>
    </div>
  </div>
</template>
<style scoped>
.email-reply {
  padding: 0;
  background: transparent;
}

/* Info (bottom reply only) */
.email-reply__info {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  margin-bottom: var(--spacing-xs);
  padding-left: var(--spacing-xs);
}

.email-reply__info-text {
  font-size: var(--font-xs);
  color: var(--ink-500);
  display: flex;
  align-items: center;
  gap: 4px;
}

.email-reply__info-name {
  font-weight: var(--font-medium);
  color: var(--ink-700);
  font-variant: normal;
  letter-spacing: normal;
  text-transform: none;
}

/* Container */
.email-reply__container {
  background: var(--parchment-50);
  border: 1px solid var(--parchment-300);
  border-radius: var(--radius-sm);
  padding: var(--spacing-xs);
  display: flex;
  align-items: flex-end;
  gap: var(--spacing-xs);
  transition: border-color var(--duration-base) var(--ease-out);
}

.email-reply__container:focus-within {
  border-color: var(--accent);
  border-left-width: 3px;
  padding-left: calc(var(--spacing-xs) - 2px);
}

/* Cancel button (inline only) */
.email-reply__cancel {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--ink-400);
  font-size: var(--icon-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.email-reply__cancel:hover {
  color: var(--ink-700);
  background: var(--parchment-200);
  border-radius: var(--radius-sm);
}

/* Textarea */
.email-reply__textarea {
  flex: 1;
  min-height: 32px;
  max-height: 128px;
  padding: var(--spacing-sm);
  background: transparent;
  border: none;
  color: var(--ink-700);
  font-size: var(--font-sm);
  line-height: var(--leading-normal);
  resize: none;
  font-family: var(--font-serif);
}

.email-reply__textarea::placeholder {
  color: var(--ink-400);
  font-style: italic;
}

.email-reply__textarea:focus {
  outline: none;
}

/* Send button */
.email-reply__send {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--ink-900);
  color: var(--parchment-50);
  font-size: var(--icon-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.email-reply__send:hover:not(:disabled) {
  background: var(--accent);
}

.email-reply__send:active:not(:disabled) {
  transform: scale(0.95);
}

.email-reply__send:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Hint */
.email-reply__hint {
  display: flex;
  justify-content: flex-end;
  padding-right: var(--spacing-xs);
  margin-top: 2px;
}

.email-reply__hint-text {
  font-size: var(--font-xs);
  color: var(--ink-300);
  line-height: 1;
}
</style>
