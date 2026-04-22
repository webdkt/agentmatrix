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
  padding: 0;
  background: transparent;
}

.collab-input__container {
  background: var(--parchment-50);
  border: 1px solid var(--parchment-300);
  border-radius: var(--radius-sm);
  padding: var(--spacing-xs);
  display: flex;
  align-items: flex-end;
  gap: var(--spacing-xs);
  transition: border-color var(--duration-base) var(--ease-out);
}

.collab-input__container:focus-within {
  border-color: var(--accent);
  border-left-width: 3px;
  padding-left: calc(var(--spacing-xs) - 2px);
}

.collab-input__textarea {
  flex: 1;
  min-height: 72px;
  max-height: 200px;
  padding: var(--spacing-sm);
  background: transparent;
  border: none;
  color: var(--ink-700);
  font-size: var(--font-sm);
  line-height: var(--leading-normal);
  resize: none;
  font-family: var(--font-serif);
}

.collab-input__textarea::placeholder {
  color: var(--ink-400);
  font-style: italic;
}

.collab-input__textarea:focus {
  outline: none;
}

.collab-input__send {
  width: 36px;
  height: 36px;
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

.collab-input__send:hover:not(:disabled) {
  background: var(--accent);
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
  padding-right: var(--spacing-xs);
  margin-top: 2px;
}

.collab-input__hint-text {
  font-size: 10px;
  font-variant: small-caps;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-300);
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
