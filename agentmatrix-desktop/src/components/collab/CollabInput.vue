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

const replyBody = ref('')
const isSending = ref(false)
const textareaRef = ref(null)

// Collab draft message — set by file drop in TaskFilesPanel
const collabDraftMessage = inject('collabDraftMessage', null)
watch(collabDraftMessage, (val) => {
  if (val) {
    replyBody.value = val
    collabDraftMessage.value = ''
    nextTick(adjustHeight)
  }
})

const canSend = computed(() => {
  return replyBody.value.trim() && props.currentSession && !isSending.value && !props.isLocked
})

const placeholder = computed(() => {
  return t('emails.sendMessage')
})

const sendReply = async () => {
  if (!canSend.value) return

  isSending.value = true
  let emailData
  let placeholderObj = null

  try {
    emailData = {
      recipient: props.currentSession.agent_name,
      subject: '',
      body: replyBody.value,
      task_id: props.currentSession.task_id || props.currentSession.session_id,
      in_reply_to: props.currentSession.last_email_id || undefined,
      recipient_session_id: props.currentSession.agent_session_id || undefined,
    }

    placeholderObj = addPendingEmail(props.currentSession.session_id, emailData)
    emit('send-started', { placeholder: placeholderObj, emailData })

    replyBody.value = ''

    const response = await sessionAPI.sendEmail(
      props.currentSession.session_id,
      emailData
    )

    removePendingEmail(placeholderObj.id)
    emit('sent', { response, placeholderId: placeholderObj.id })
  } catch (error) {
    console.error('Failed to send reply:', error)
    if (placeholderObj) {
      removePendingEmail(placeholderObj.id)
      emit('send-failed', { placeholderId: placeholderObj.id, error: error.message })
    }
    alert(`${t('emails.sendError')}: ${error.message}`)
  } finally {
    isSending.value = false
  }
}

const handleKeyDown = (event) => {
  if (event.key === 'Enter' && event.ctrlKey) {
    event.preventDefault()
    sendReply()
  }
}

const adjustHeight = () => {
  if (!textareaRef.value) return
  const textarea = textareaRef.value
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
}
</script>

<template>
  <div class="collab-input">
    <div class="collab-input__container">
      <textarea
        ref="textareaRef"
        v-model="replyBody"
        @keydown="handleKeyDown"
        @input="adjustHeight"
        :placeholder="placeholder"
        :disabled="isLocked"
        rows="3"
        class="collab-input__textarea"
      ></textarea>

      <button
        @click="sendReply"
        :disabled="!canSend"
        class="collab-input__send"
        :title="t('emails.send')"
      >
        <MIcon v-if="!isSending" name="send" />
        <span v-else class="animate-spin"><MIcon name="loader" /></span>
      </button>
    </div>

    <div class="collab-input__hint">
      <span v-if="isLocked" class="collab-input__hint-text">Sending...</span>
      <span v-else class="collab-input__hint-text">Ctrl+Enter {{ t('emails.send') }}</span>
    </div>
  </div>
</template>

<style scoped>
.collab-input {
  padding: 18px 36px 28px;
  background: transparent;
  border-top: 1px solid var(--border-light);
}

.collab-input__container {
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 12px 12px 12px 18px;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  transition: border-color var(--duration-base) var(--ease-out);
}

.collab-input__container:focus-within {
  border-color: var(--text-primary);
}

.collab-input__textarea {
  flex: 1;
  min-height: 24px;
  max-height: 120px;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  font-family: var(--font-sans);
}

.collab-input__textarea::placeholder {
  color: var(--text-tertiary);
  font-style: italic;
}

.collab-input__textarea:focus {
  outline: none;
}

.collab-input__send {
  width: 40px;
  height: 40px;
  border: none;
  background: var(--accent);
  color: white;
  font-size: 18px;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  flex-shrink: 0;
}

.collab-input__send:hover:not(:disabled) {
  background: var(--accent-hover);
  transform: scale(1.05);
}

.collab-input__send:active:not(:disabled) {
  transform: scale(0.95);
}

.collab-input__send:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.collab-input__hint {
  display: flex;
  justify-content: flex-end;
  padding-right: var(--spacing-1);
  margin-top: 2px;
}

.collab-input__hint-text {
  font-size: 10px;
  color: var(--text-quaternary);
  line-height: 1;
}

.animate-spin {
  animation: spin 1s linear infinite;
  display: flex;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>
