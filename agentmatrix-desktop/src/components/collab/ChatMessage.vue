<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import MIcon from '@/components/icons/MIcon.vue'
import { openAttachment, getAttachmentIcon } from '@/utils/attachmentHelper'

const props = defineProps({
  message: {
    type: Object,
    required: true
  },
  user_agent_name: {
    type: String,
    default: 'User'
  },
  agentName: {
    type: String,
    default: null
  }
})

// ---- Bubble (user / agent) ----

const renderedBody = computed(() => {
  if (!['bubble-user', 'bubble-agent', 'thought'].includes(props.message.type)) return ''
  if (props.message.type === 'thought') {
    const body = props.message.data?.detail?.thought
    if (!body) return ''
    return body
  }
  const body = props.message.data?.detail?.body_preview
  if (!body) return ''
  try {
    return marked(body).trim()
  } catch {
    return body
  }
})

// ---- Pill (action events) ----

const pillText = computed(() => {
  if (props.message.type !== 'pill') return ''
  const { eventType, eventName, detail } = props.message.data
  if (eventType === 'action') {
    if (eventName === 'started') {
      return `执行 ${detail.action_name || ''}`
    }
    if (eventName === 'completed') {
      const label = detail.action_label || detail.action_name || ''
      if (detail.status === 'error') {
        return `${label} 出错`
      }
      if (detail.status === 'canceled') {
        return `${label} 已取消`
      }
      return `${label} 完成`
    }
    if (eventName === 'error') {
      const label = detail.action_label || detail.action_name || ''
      return `${label} 出错: ${detail.error_message || ''}`
    }
  }
  return `${eventType}.${eventName}`
})

// ---- Agent comm (agent-to-agent email) ----

const agentCommText = computed(() => {
  if (props.message.type !== 'agent-comm') return ''
  const { eventType, eventName, detail } = props.message.data
  if (eventType === 'email' && eventName === 'received') {
    return `收到来自 ${detail.sender || '未知'} 的邮件${detail.subject ? ': ' + detail.subject : ''}`
  }
  if (eventType === 'email' && eventName === 'sent') {
    return `给 ${detail.recipient || '未知'} 发了邮件${detail.subject ? ': ' + detail.subject : ''}`
  }
  return ''
})

// ---- System event ----

const systemText = computed(() => {
  if (props.message.type !== 'system') return ''
  const { eventName, detail } = props.message.data
  const labels = {
    activated: '会话开始',
    deactivated: '会话结束',
    user_interrupt: '用户中断',
    message_auto_compress: '上下文压缩',
  }
  return labels[eventName] || eventName
})

// ---- Time formatting ----

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const time = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  const isToday = date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate()
  if (isToday) return time
  return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()} ${time}`
}

// ---- Attachments ----

const attachments = computed(() => {
  return props.message.data?.detail?.attachments || []
})

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

const handleAttachmentClick = async (attachment) => {
  try {
    if (!attachment || !attachment.filename) {
      console.warn('Invalid attachment:', attachment)
      return
    }
    await openAttachment(
      props.user_agent_name,
      props.message.data?.detail?.task_id,
      attachment.filename
    )
  } catch (error) {
    console.error('Failed to open attachment:', error)
  }
}
</script>

<template>
  <!-- User chat bubble (right-aligned, green) -->
  <div v-if="message.type === 'bubble-user'" class="chat-msg chat-msg--user">
    <div class="chat-msg__bubble">
      <div class="chat-msg__body markdown-content" v-html="renderedBody"></div>
      <div v-if="attachments.length > 0" class="chat-msg__attachments">
        <div
          v-for="(attachment, index) in attachments"
          :key="index"
          v-show="attachment.filename"
          class="chat-msg__attachment"
          @click="handleAttachmentClick(attachment)"
        >
          <div class="chat-msg__attachment-dot"></div>
          <MIcon :name="getAttachmentIcon(attachment.filename)" class="chat-msg__attachment-icon" />
          <span class="chat-msg__attachment-name">{{ attachment.filename || 'Unknown file' }}</span>
          <span class="chat-msg__attachment-size">{{ formatFileSize(attachment.size) }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Agent chat bubble (left-aligned, parchment) -->
  <div v-else-if="message.type === 'bubble-agent'" class="chat-msg">
    <div class="chat-msg__bubble">
      <div class="chat-msg__body markdown-content" v-html="renderedBody"></div>
      <div v-if="attachments.length > 0" class="chat-msg__attachments">
        <div
          v-for="(attachment, index) in attachments"
          :key="index"
          v-show="attachment.filename"
          class="chat-msg__attachment"
          @click="handleAttachmentClick(attachment)"
        >
          <div class="chat-msg__attachment-dot"></div>
          <MIcon :name="getAttachmentIcon(attachment.filename)" class="chat-msg__attachment-icon" />
          <span class="chat-msg__attachment-name">{{ attachment.filename || 'Unknown file' }}</span>
          <span class="chat-msg__attachment-size">{{ formatFileSize(attachment.size) }}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- Thought (agent's inner monologue, bubble style) -->
  <div v-else-if="message.type === 'thought'" class="chat-msg chat-msg--thought-row">
    <div class="chat-msg__bubble chat-msg__bubble--thought">
      <div class="chat-msg__body chat-msg__body--thought">{{ renderedBody }}</div>
    </div>
  </div>

  <!-- Agent-to-agent communication (subtle, centered) -->
  <div v-else-if="message.type === 'agent-comm'" class="chat-agent-comm">
    <span class="chat-agent-comm__icon">
      <MIcon name="mail" />
    </span>
    <span class="chat-agent-comm__text">{{ agentCommText }}</span>
  </div>

  <!-- Status pill (action events) -->
  <div v-else-if="message.type === 'pill'" class="chat-pill">
    <div class="chat-pill__capsule">
      <span class="chat-pill__text">{{ pillText }}</span>
    </div>
  </div>

  <!-- Session start/end (centered, time only) -->
  <div v-else-if="message.type === 'session-time'" class="chat-session-time">
    {{ formatTime(message.timestamp) }}
  </div>

  <!-- System event (minimal, centered) -->
  <div v-else-if="message.type === 'system'" class="chat-system">
    <span class="chat-system__text">{{ systemText }}</span>
  </div>
</template>

<style scoped>
/* ===== Message base ===== */
.chat-msg {
  display: flex;
  flex-direction: column;
  max-width: 68%;
  animation: fadeIn 250ms var(--ease-out);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px) }
  to { opacity: 1; transform: translateY(0) }
}

.chat-msg--user {
  align-self: flex-end;
  align-items: flex-end;
}

.chat-msg:not(.chat-msg--user):not(.chat-msg--thought-row) {
  align-self: flex-start;
  align-items: flex-start;
}

/* ===== Bubble base ===== */
.chat-msg__bubble {
  padding: 14px 18px;
  font-size: 14px;
  line-height: 1.65;
}

/* Agent bubble: white with border */
.chat-msg:not(.chat-msg--user) .chat-msg__bubble {
  background: var(--surface-base);
  color: var(--text-primary);
  border: 1px solid var(--border);
  border-radius: 8px 8px 8px 4px;
}

/* User bubble: light gray */
.chat-msg--user .chat-msg__bubble {
  background: var(--surface-hover);
  color: var(--text-primary);
  border-radius: 8px 8px 4px 8px;
}

.chat-msg__body {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.65;
}

/* ===== Agent-to-agent communication ===== */
.chat-agent-comm {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 0;
  width: 100%;
  border-top: 1px dashed var(--border);
  border-bottom: 1px dashed var(--border);
  animation: fadeIn 250ms var(--ease-out);
}

.chat-agent-comm__icon {
  font-size: var(--font-xs);
  color: var(--text-quaternary);
  display: flex;
  align-items: center;
}

.chat-agent-comm__text {
  font-size: 12px;
  color: var(--text-quaternary);
  font-style: italic;
}

/* ===== Action pill (colored dot, no background) ===== */
.chat-pill {
  display: flex;
  justify-content: flex-start;
  padding: 3px 0;
  animation: fadeIn 250ms var(--ease-out);
}

.chat-pill__capsule {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 80%;
}

.chat-pill__capsule::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal);
  flex-shrink: 0;
}

.chat-pill__text {
  color: var(--text-secondary);
}

/* ===== Thought (inner monologue, rose-tinted card) ===== */
.chat-msg__bubble--thought {
  background: var(--accent-soft);
  border: none;
  border-left: 2px solid var(--accent);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-top: 10px;
  opacity: 1;
}

.chat-msg__body--thought {
  font-style: italic;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ===== System event ===== */
.chat-system {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 0;
  animation: fadeIn 200ms var(--ease-out);
}

.chat-system__text {
  font-size: 11px;
  color: var(--text-quaternary);
}

/* ===== Session start/end time ===== */
.chat-session-time {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 0;
  font-size: 11px;
  color: var(--text-quaternary);
  animation: fadeIn 200ms var(--ease-out);
}

/* ===== Markdown styles ===== */
.markdown-content :deep(p) {
  margin-bottom: var(--spacing-1);
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-left: var(--spacing-4);
  margin-bottom: var(--spacing-1);
}

.markdown-content :deep(li) {
  margin-bottom: 2px;
}

.markdown-content :deep(code) {
  background: var(--surface-hover);
  color: var(--accent);
  padding: 1px 4px;
  border-radius: var(--radius-md);
  font-size: var(--font-xs);
}

.markdown-content :deep(pre) {
  background: var(--text-primary);
  color: var(--surface-base);
  padding: var(--spacing-2);
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin-bottom: var(--spacing-1);
}

.markdown-content :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 3px solid var(--text-quaternary);
  padding-left: var(--spacing-2);
  font-style: italic;
  color: var(--text-tertiary);
  margin-bottom: var(--spacing-1);
}

.markdown-content :deep(a) {
  color: var(--info);
  text-decoration: underline;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin-bottom: var(--spacing-1);
  margin-top: var(--spacing-1);
}

/* ===== Attachments (zen-v2-dot style) ===== */
.chat-msg__attachments {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-msg__attachment {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-base) var(--ease-out);
}

.chat-msg__attachment:hover {
  background: var(--surface-hover);
}

.chat-msg__attachment-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--teal);
  flex-shrink: 0;
}

.chat-msg__attachment-icon {
  font-size: 14px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.chat-msg__attachment-name {
  font-size: 12px;
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.chat-msg__attachment-size {
  font-size: 12px;
  color: var(--text-quaternary);
  flex-shrink: 0;
  margin-left: auto;
}
</style>
