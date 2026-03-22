<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { sessionAPI } from '@/api/session'
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
  inlineEmail: {
    type: Object,
    default: null
  },
  showInline: {
    type: Boolean,
    default: false
  }
})

const { t } = useI18n()
const emit = defineEmits(['sent', 'cancelInline'])

// 状态
const replyBody = ref('')
const isSending = ref(false)

// 计算属性
const canSend = computed(() => {
  return replyBody.value.trim() && props.currentSession && !isSending.value
})

const lastEmail = computed(() => {
  if (props.emails.length === 0) return null
  return props.emails[props.emails.length - 1]
})

const placeholder = computed(() => {
  if (props.showInline && props.inlineEmail) {
    const sender = props.inlineEmail.is_from_user
      ? (props.inlineEmail.recipient || props.currentSession.name)
      : props.inlineEmail.sender
    return t('emails.replyTo', { name: sender })
  }

  if (props.emails.length === 0) {
    return t('emails.sendMessage')
  }
  const sender = lastEmail.value?.is_from_user
    ? (lastEmail.value.recipient || props.currentSession.name)
    : lastEmail.value?.sender
  return t('emails.replyTo', { name: sender })
})

// 发送回复
const sendReply = async () => {
  if (!canSend.value) return

  isSending.value = true
  try {
    let emailData
    let targetEmail = props.showInline ? props.inlineEmail : lastEmail.value

    if (!targetEmail) {
      // 没有邮件，发送给会话的 agent
      emailData = {
        recipient: props.currentSession.name,
        subject: '',
        body: replyBody.value
      }
    } else {
      // 回复邮件
      let recipient
      if (targetEmail.is_from_user) {
        recipient = targetEmail.recipient || props.currentSession.name
      } else {
        recipient = targetEmail.sender
      }

      emailData = {
        recipient: recipient,
        subject: '',
        body: replyBody.value,
        in_reply_to: targetEmail.id
      }
    }

    const response = await sessionAPI.sendEmail(
      props.currentSession.session_id,
      emailData
    )

    console.log('Reply sent:', response)

    // 清空输入
    replyBody.value = ''
    emit('sent', response)
  } catch (error) {
    console.error('Failed to send reply:', error)
    alert(`${t('emails.sendError')}: ${error.message}`)
  } finally {
    isSending.value = false
  }
}

// 取消内联回复
const cancelInline = () => {
  replyBody.value = ''
  emit('cancelInline')
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
  <!-- Floating Reply (bottom or inline) -->
  <div :class="['email-reply', { 'email-reply--inline': showInline }]">
    <!-- Reply Info (only for bottom reply) -->
    <div v-if="!showInline && emails.length > 0" class="email-reply__info">
      <span class="email-reply__info-text">
        <MIcon name="arrow-back-up" />
        {{ t('emails.replyTo') }}
        <span class="email-reply__info-name">
          {{ lastEmail?.is_from_user
            ? (lastEmail?.recipient || currentSession.name)
            : lastEmail?.sender }}
        </span>
      </span>
    </div>

    <!-- Reply Container -->
    <div class="email-reply__container">
      <!-- Cancel button (inline only) -->
      <button
        v-if="showInline"
        @click="cancelInline"
        class="email-reply__cancel"
        :title="t('common.cancel')"
      >
        <MIcon name="x" />
      </button>

      <!-- Textarea -->
      <textarea
        v-model="replyBody"
        @keydown="handleKeyDown"
        @input="adjustHeight"
        :placeholder="placeholder"
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
    <div v-if="!showInline" class="email-reply__hint">
      <span class="email-reply__hint-text">Ctrl+Enter {{ t('emails.send') }}</span>
    </div>
  </div>
</template>

<style scoped>
.email-reply {
  padding: 0;
  background: transparent;
}

.email-reply--inline {
  margin: var(--spacing-md) 0;
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
  color: var(--neutral-500);
  display: flex;
  align-items: center;
  gap: 4px;
}

.email-reply__info-name {
  font-weight: var(--font-medium);
  color: var(--neutral-700);
}

/* Container */
.email-reply__container {
  background: white;
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  padding: var(--spacing-xs);
  display: flex;
  align-items: flex-end;
  gap: var(--spacing-xs);
}

/* Cancel button (inline only) */
.email-reply__cancel {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--neutral-400);
  font-size: var(--icon-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.email-reply__cancel:hover {
  color: var(--neutral-600);
  background: var(--neutral-100);
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
  color: var(--neutral-700);
  font-size: var(--font-sm);
  line-height: var(--leading-normal);
  resize: none;
  font-family: inherit;
}

.email-reply__textarea::placeholder {
  color: var(--neutral-400);
}

.email-reply__textarea:focus {
  outline: none;
}

/* Send button */
.email-reply__send {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--accent);
  color: white;
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
  opacity: 0.9;
}

.email-reply__send:active:not(:disabled) {
  transform: scale(0.95);
}

.email-reply__send:disabled {
  opacity: 0.5;
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
  font-size: 10px;
  color: var(--neutral-300);
  line-height: 1;
}

/* Animations */

</style>
