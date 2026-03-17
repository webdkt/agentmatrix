<script setup>
import { ref, computed, watch } from 'vue'
import { sessionAPI } from '@/api/session'

const props = defineProps({
  currentSession: {
    type: Object,
    default: null
  },
  emails: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['sent'])

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
  if (props.emails.length === 0) {
    return '发送消息...'
  }
  const sender = lastEmail.value?.is_from_user
    ? (lastEmail.value.recipient || props.currentSession?.name)
    : lastEmail.value?.sender
  return `回复给 ${sender}...`
})

// 发送回复
const sendReply = async () => {
  if (!canSend.value) return

  isSending.value = true
  try {
    // 如果没有邮件，发送给会话的 agent
    if (props.emails.length === 0) {
      const emailData = {
        recipient: props.currentSession.name,
        subject: '',
        body: replyBody.value
      }

      const response = await sessionAPI.sendEmail(
        props.currentSession.session_id,
        emailData
      )

      console.log('Message sent:', response)

      // 清空输入
      replyBody.value = ''
      emit('sent', response)
    } else {
      // 回复最后一封邮件
      const last = lastEmail.value

      // 确定回复对象
      let recipient
      if (last.is_from_user) {
        // 最后一封是用户发的，回复给收件人
        recipient = last.recipient || props.currentSession.name
      } else {
        // 最后一封是 AI 发的，回复给发送者
        recipient = last.sender
      }

      // 使用邮件 ID 作为 in_reply_to
      const inReplyTo = last.id

      const emailData = {
        recipient: recipient,
        subject: '',
        body: replyBody.value,
        in_reply_to: inReplyTo
      }

      const response = await sessionAPI.sendEmail(
        props.currentSession.session_id,
        emailData
      )

      console.log('Reply sent:', response)

      // 清空输入
      replyBody.value = ''
      emit('sent', response)
    }
  } catch (error) {
    console.error('Failed to send reply:', error)
    alert(`发送失败: ${error.message}`)
  } finally {
    isSending.value = false
  }
}

// 处理 Enter 键发送
const handleKeyDown = (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendReply()
  }
}

// 自动调整文本框高度
const adjustHeight = (event) => {
  const textarea = event.target
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 128) + 'px'
}
</script>

<template>
  <div v-if="currentSession" class="px-6 pb-6 pt-2 flex-shrink-0">
    <!-- Reply Info -->
    <div v-if="emails.length > 0" class="flex items-center gap-2 mb-2 px-1">
      <span class="text-xs text-surface-500">
        <i class="ti ti-arrow-back-up"></i>
        回复给
        <span class="font-medium text-surface-700">
          {{ lastEmail?.is_from_user
            ? (lastEmail?.recipient || currentSession.name)
            : lastEmail?.sender }}
        </span>
      </span>
    </div>

    <!-- Reply Input -->
    <div class="glass rounded-2xl border border-surface-200/60 shadow-elevated p-2">
      <div class="flex items-end gap-2">
        <textarea
          v-model="replyBody"
          @keydown="handleKeyDown"
          @input="adjustHeight"
          :placeholder="placeholder"
          rows="1"
          class="flex-1 py-2.5 px-2 bg-transparent border-0 text-surface-700 placeholder-surface-400 resize-none focus:outline-none focus:ring-0 text-[15px] max-h-32"
          style="min-height: 44px;"
        ></textarea>
        <button
          @click="sendReply"
          :disabled="!canSend"
          class="w-10 h-10 rounded-xl bg-primary-600 text-white hover:bg-primary-700 flex items-center justify-center transition-all duration-200 btn-press shadow-glow-sm flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <i v-if="!isSending" class="ti ti-send text-lg"></i>
          <i v-else class="ti ti-loader animate-spin text-lg"></i>
        </button>
      </div>
      <div class="flex items-center justify-end px-3 pb-1 pt-1">
        <span class="text-xs text-surface-400">按 Enter 发送</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.glass {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
}

.shadow-elevated {
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}

.shadow-glow-sm {
  box-shadow: 0 0 20px rgba(14, 165, 233, 0.3);
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
