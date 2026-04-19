<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  message: {
    type: Object,
    required: true
  },
  user_agent_name: {
    type: String,
    default: 'User'
  },
  primaryChatPartner: {
    type: String,
    default: null
  }
})

// ---- Email message ----

const renderedBody = computed(() => {
  if (props.message.type !== 'email') return ''
  const body = props.message.data?.body
  if (!body) return ''
  try {
    return marked(body)
  } catch {
    return body
  }
})

const isFromUser = computed(() => {
  return props.message.type === 'email' && props.message.data?.is_from_user
})

// For user messages sent to someone other than the primary partner
const recipientBadge = computed(() => {
  if (props.message.type !== 'email' || !props.message.data?.is_from_user) return null
  const recipient = props.message.data.recipient
  if (!recipient) return null
  if (props.primaryChatPartner && recipient !== props.primaryChatPartner) {
    return recipient
  }
  return null
})

// For agent messages from someone other than the primary partner
const senderBadge = computed(() => {
  if (props.message.type !== 'email' || props.message.data?.is_from_user) return null
  const sender = props.message.data.sender
  if (!sender) return null
  if (props.primaryChatPartner && sender !== props.primaryChatPartner) {
    return sender
  }
  return null
})

// ---- Status message ----

const statusConfig = {
  THINKING: { icon: 'brain', label: 'thinking', spinning: true },
  WORKING: { icon: 'loader', label: 'working', spinning: true },
  WAITING_FOR_USER: { icon: 'message-circle', label: 'waiting for you', spinning: false },
  PAUSED: { icon: 'player-pause', label: 'paused', spinning: false },
  ERROR: { icon: 'alert-circle', label: 'error', spinning: false },
  IDLE: { icon: 'circle', label: 'idle', spinning: false }
}

const currentStatusConfig = computed(() => {
  if (props.message.type !== 'status') return null
  return statusConfig[props.message.data?.status] || statusConfig.IDLE
})

// ---- Time formatting ----

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))

  if (diffMins < 1) return 'now'
  if (diffMins < 60) return `${diffMins}m`
  if (diffHours < 24) return `${diffHours}h`
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

// ---- Attachment helpers ----

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
</script>

<template>
  <!-- Content-type status message: timeline item with message content -->
  <div v-if="message.type === 'status' && message.data.isContent" class="chat-content-msg">
    <div class="chat-content-msg__bubble">
      <div class="chat-content-msg__body">{{ message.data.message }}</div>
      <div class="chat-content-msg__footer">
        <span class="chat-content-msg__time">{{ formatTime(message.data.timestamp) }}</span>
      </div>
    </div>
  </div>

  <!-- Pure status pill (only for non-content status messages, should be rare in timeline) -->
  <div v-else-if="message.type === 'status'" class="chat-status">
    <div class="chat-status__pill">
      <span :class="['chat-status__icon', { 'chat-status__icon--spinning': currentStatusConfig.spinning }]">
        <MIcon :name="currentStatusConfig.icon" />
      </span>
      <span class="chat-status__agent">{{ message.data.agentName }}</span>
      <span class="chat-status__label">{{ currentStatusConfig.label }}</span>
    </div>
  </div>

  <!-- Email message: chat bubble -->
  <div v-else-if="message.type === 'email'" :class="['chat-msg', { 'chat-msg--user': isFromUser }]">
    <div :class="['chat-msg__bubble', { 'chat-msg__bubble--other-agent': senderBadge }]">
      <!-- Badge for non-primary recipient (user sending to someone else) -->
      <div v-if="recipientBadge" class="chat-msg__badge">
        → @{{ recipientBadge }}
      </div>

      <!-- Sender label for non-primary agent messages -->
      <div v-if="senderBadge" class="chat-msg__other-sender">
        <MIcon name="agent-dispatch" />
        <span>{{ senderBadge }}</span>
      </div>

      <div class="chat-msg__header">
        <span class="chat-msg__time">{{ formatTime(message.data.timestamp) }}</span>
      </div>

      <div v-if="message.data.subject && !isFromUser" class="chat-msg__subject">
        {{ message.data.subject }}
      </div>

      <div class="chat-msg__body markdown-content" v-html="renderedBody"></div>

      <!-- Attachments -->
      <div v-if="message.data.attachments?.length" class="chat-msg__attachments">
        <div
          v-for="(att, i) in message.data.attachments"
          :key="i"
          class="chat-msg__attachment"
        >
          <MIcon name="paperclip" />
          <span class="chat-msg__attachment-name">{{ att.filename }}</span>
          <span class="chat-msg__attachment-size">{{ formatFileSize(att.size) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ===== Content-type status message (timeline item) ===== */
.chat-content-msg {
  display: flex;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 200ms var(--ease-out);
}

.chat-content-msg__bubble {
  max-width: 75%;
  background: var(--neutral-50);
  border: 1px solid var(--neutral-100);
  border-radius: var(--radius-md);
  border-bottom-left-radius: var(--radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
}

.chat-content-msg__body {
  font-size: var(--font-sm);
  color: var(--neutral-600);
  line-height: var(--leading-relaxed);
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-content-msg__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.chat-content-msg__time {
  font-size: 10px;
  color: var(--neutral-400);
}

/* ===== Status pill (pure status indicator) ===== */
.chat-status {
  display: flex;
  justify-content: center;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 200ms var(--ease-out);
}

.chat-status__pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  background: var(--neutral-50);
  border: 1px solid var(--neutral-100);
  border-radius: 999px;
  font-size: var(--font-xs);
  color: var(--neutral-400);
  max-width: 80%;
}

.chat-status__icon {
  display: flex;
  align-items: center;
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

.chat-status__icon--spinning {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}

.chat-status__agent {
  font-weight: var(--font-semibold);
  color: var(--neutral-500);
}

.chat-status__label {
  color: var(--neutral-400);
}

.chat-status__detail {
  color: var(--neutral-400);
  font-style: italic;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ===== Email message ===== */
.chat-msg {
  display: flex;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 200ms var(--ease-out);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px) }
  to { opacity: 1; transform: translateY(0) }
}

/* Agent messages: left-aligned */
.chat-msg__bubble {
  max-width: 75%;
  background: var(--parchment-100);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-md);
  border-bottom-left-radius: var(--radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
}

/* User messages: right-aligned */
.chat-msg--user {
  justify-content: flex-end;
}

.chat-msg--user .chat-msg__bubble {
  background: var(--success-50);
  border-color: var(--success-200);
  border-radius: var(--radius-md);
  border-bottom-right-radius: var(--radius-sm);
}

/* Header */
.chat-msg__header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-bottom: 2px;
}

.chat-msg__time {
  font-size: 10px;
  color: var(--neutral-400);
  flex-shrink: 0;
}

/* Badge for → @Agent (user sending to non-primary) */
.chat-msg__badge {
  font-size: 11px;
  font-weight: var(--font-medium);
  color: var(--accent);
  margin-bottom: 4px;
  padding: 1px 0;
}

/* Sender label for non-primary agent messages */
.chat-msg__other-sender {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--neutral-500);
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--neutral-100);
}

.chat-msg__other-sender .m-icon {
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

/* Non-primary agent bubble: subtle tint to differentiate */
.chat-msg__bubble--other-agent {
  background: var(--neutral-50);
  border-color: var(--neutral-200);
}

/* Subject */
.chat-msg__subject {
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--neutral-700);
  padding-bottom: 4px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--neutral-100);
}

/* Body */
.chat-msg__body {
  font-size: var(--font-sm);
  color: var(--neutral-700);
  line-height: var(--leading-relaxed);
}

/* Attachments */
.chat-msg__attachments {
  margin-top: var(--spacing-xs);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-msg__attachment {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-xs);
  color: var(--neutral-500);
  padding: 3px 8px;
  background: rgba(0,0,0,0.03);
  border-radius: var(--radius-sm);
}

.chat-msg__attachment-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--neutral-600);
  font-weight: var(--font-medium);
}

.chat-msg__attachment-size {
  flex-shrink: 0;
  color: var(--neutral-400);
}

/* ===== Markdown styles (inherited from EmailItem pattern) ===== */
.markdown-content :deep(p) {
  margin-bottom: var(--spacing-xs);
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-left: var(--spacing-md);
  margin-bottom: var(--spacing-xs);
}

.markdown-content :deep(li) {
  margin-bottom: 2px;
}

.markdown-content :deep(code) {
  background: var(--neutral-100);
  color: var(--accent);
  padding: 1px 4px;
  border-radius: var(--radius-sm);
  font-size: var(--font-xs);
}

.markdown-content :deep(pre) {
  background: var(--neutral-800);
  color: var(--neutral-50);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin-bottom: var(--spacing-xs);
}

.markdown-content :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 3px solid var(--neutral-300);
  padding-left: var(--spacing-sm);
  font-style: italic;
  color: var(--neutral-500);
  margin-bottom: var(--spacing-xs);
}

.markdown-content :deep(a) {
  color: var(--info-500);
  text-decoration: underline;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin-bottom: var(--spacing-xs);
  margin-top: var(--spacing-xs);
}
</style>
