<script setup>
import { computed, ref } from 'vue'
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

const expanded = ref(false)

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
      return detail.action_name || ''
    }
    if (eventName === 'completed') {
      const label = detail.action_label || detail.action_name || ''
      if (detail.status === 'error') {
        return `${label} 出错`
      }
      if (detail.status === 'canceled') {
        return `${label} 已取消`
      }
      // 正常完成：只显示 label，勾勾用 CSS 显示
      return label
    }
    if (eventName === 'error') {
      const label = detail.action_label || detail.action_name || ''
      return `${label} 出错: ${detail.error_message || ''}`
    }
  }
  return `${eventType}.${eventName}`
})

// ---- Agent comm (agent-to-agent email) ----

const agentCommLabel = computed(() => {
  if (props.message.type !== 'agent-comm') return ''
  const { eventType, eventName } = props.message.data
  const name = props.agentName || 'Agent'
  if (eventType === 'email' && eventName === 'received') return `${name}收到邮件`
  if (eventType === 'email' && eventName === 'sent') return `${name}发出邮件`
  return ''
})

const agentCommMeta = computed(() => {
  if (props.message.type !== 'agent-comm') return ''
  const { eventType, eventName, detail } = props.message.data
  if (eventType === 'email' && eventName === 'received') return `来自: ${detail.sender || '未知'}`
  if (eventType === 'email' && eventName === 'sent') return `致: ${detail.recipient || '未知'}`
  return ''
})

const agentCommSubject = computed(() => {
  if (props.message.type !== 'agent-comm') return ''
  return props.message.data?.detail?.subject || ''
})

const agentCommBody = computed(() => {
  if (props.message.type !== 'agent-comm') return ''
  const body = props.message.data?.detail?.body_preview
  if (!body) return ''
  try { return marked(body).trim() } catch { return body }
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

// ---- UI Action result ----

const uiActionLabel = computed(() => {
  if (!props.message.type?.startsWith('ui-action')) return ''
  return props.message.data?.detail?.label || props.message.data?.eventName || ''
})

const uiActionDisplayMode = computed(() => {
  if (!props.message.type?.startsWith('ui-action')) return 'text'
  return props.message.data?.detail?.display_mode || 'text'
})

const renderedUIActionBody = computed(() => {
  if (!props.message.type?.startsWith('ui-action')) return ''
  const result = props.message.data?.detail?.result
  if (result == null) return ''
  if (uiActionDisplayMode.value === 'json') {
    try {
      const obj = typeof result === 'string' ? JSON.parse(result) : result
      return JSON.stringify(obj, null, 2)
    } catch { return String(result) }
  }
  if (uiActionDisplayMode.value === 'markdown') {
    try { return marked(String(result)).trim() } catch { return String(result) }
  }
  return String(result)
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

  <!-- Thought (agent's inner monologue, natural display) -->
  <div v-else-if="message.type === 'thought'" class="chat-msg chat-msg--thought-row">
    <div class="chat-msg__body chat-msg__body--thought markdown-content" v-html="renderedBody"></div>
  </div>

  <!-- Agent-to-agent email (left-aligned bubble, expandable) -->
  <div v-else-if="message.type === 'agent-comm'" class="chat-agent-comm" @click="expanded = !expanded">
    <div class="chat-agent-comm__header">
      <MIcon name="mail" class="chat-agent-comm__icon" />
      <span class="chat-agent-comm__label">{{ agentCommLabel }}</span>
      <span class="chat-agent-comm__time">{{ formatTime(message.timestamp) }}</span>
      <MIcon :name="expanded ? 'chevron-down' : 'chevron-right'" class="chat-agent-comm__chevron" />
    </div>
    <div class="chat-agent-comm__meta">
      <span class="chat-agent-comm__sender">{{ agentCommMeta }}</span>
      <span v-if="agentCommSubject" class="chat-agent-comm__subject">主题: {{ agentCommSubject }}</span>
    </div>
    <Transition name="comm-expand">
      <div v-if="expanded" class="chat-agent-comm__body" @click.stop>
        <div v-if="agentCommBody" class="chat-agent-comm__body-content markdown-content" v-html="agentCommBody"></div>
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
    </Transition>
  </div>

  <!-- Status pill (action events) -->
  <div v-else-if="message.type === 'pill'" class="chat-pill">
    <div class="chat-pill__capsule" :class="`chat-pill__capsule--${message.data.eventName}`">
      <span class="chat-pill__text">{{ pillText }}</span>
    </div>
  </div>

  <!-- Session start/end (centered, time only) -->
  <div v-else-if="message.type === 'session-time'" class="chat-session-time">
    {{ formatTime(message.timestamp) }}
  </div>

  <!-- UI Action result (card style) -->
  <div v-else-if="message.type === 'ui-action-text'" class="chat-ui-action">
    <div class="chat-ui-action__header">
      <MIcon name="zap" class="chat-ui-action__icon" />
      <span class="chat-ui-action__label">{{ uiActionLabel }}</span>
      <span class="chat-ui-action__time">{{ formatTime(message.timestamp) }}</span>
    </div>
    <div class="chat-ui-action__body">
      <pre v-if="uiActionDisplayMode === 'json'" class="chat-ui-action__pre">{{ renderedUIActionBody }}</pre>
      <div v-else-if="uiActionDisplayMode === 'markdown'" class="chat-ui-action__markdown" v-html="renderedUIActionBody"></div>
      <div v-else class="chat-ui-action__text">{{ renderedUIActionBody }}</div>
    </div>
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
  padding: 12px 16px;
  font-size: 14px;
  line-height: 1.65;
}

/* Agent bubble: white with border */
.chat-msg:not(.chat-msg--user) .chat-msg__bubble {
  background: var(--surface-base);
  color: var(--text-primary);
  border: 2px solid var(--text-tertiary);
  border-radius: 8px 8px 8px 4px;
  position: relative;
  margin-bottom: 12px;
  overflow: visible;
}

.chat-msg:not(.chat-msg--user) .chat-msg__bubble::after {
  content: '';
  position: absolute;
  bottom: -10px;
  left: 10px;
  width: 0;
  height: 0;
  border-left: 10px solid transparent;
  border-right: 10px solid transparent;
  border-top: 10px solid var(--surface-base);
  z-index: 1;
}

.chat-msg:not(.chat-msg--user) .chat-msg__bubble::before {
  content: '';
  position: absolute;
  bottom: -13px;
  left: 7px;
  width: 0;
  height: 0;
  border-left: 13px solid transparent;
  border-right: 13px solid transparent;
  border-top: 13px solid var(--text-tertiary);
  z-index: 0;
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

/* ===== Agent-to-agent email bubble ===== */
.chat-agent-comm {
  display: flex;
  flex-direction: column;
  align-self: flex-start;
  max-width: 68%;
  background: var(--surface-secondary);
  border-left: 3px solid var(--accent);
  border-radius: 6px;
  padding: 10px 14px;
  cursor: pointer;
  animation: fadeIn 250ms var(--ease-out);
  transition: background var(--duration-base) var(--ease-out);
}

.chat-agent-comm:hover {
  background: var(--surface-hover);
}

.chat-agent-comm__header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-agent-comm__icon {
  font-size: 14px;
  color: var(--accent);
  flex-shrink: 0;
}

.chat-agent-comm__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.chat-agent-comm__time {
  font-size: 11px;
  color: var(--text-quaternary);
  margin-left: auto;
}

.chat-agent-comm__chevron {
  font-size: 14px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  transition: transform var(--duration-base) var(--ease-out);
}

.chat-agent-comm__meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}

.chat-agent-comm__sender {
  font-size: 12px;
  color: var(--text-tertiary);
}

.chat-agent-comm__subject {
  font-size: 12px;
  color: var(--text-tertiary);
}

.chat-agent-comm__body {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}

.chat-agent-comm__body-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.comm-expand-enter-active {
  animation: expandIn 200ms var(--ease-out);
}

.comm-expand-leave-active {
  animation: expandIn 150ms var(--ease-out) reverse;
}

@keyframes expandIn {
  from { opacity: 0; max-height: 0; overflow: hidden; }
  to { opacity: 1; max-height: 500px; overflow: hidden; }
}

/* ===== Action pill (colored dot, no background) ===== */
.chat-pill {
  display: inline-flex;
  justify-content: flex-start;
  padding: 0;
  animation: fadeIn 250ms var(--ease-out);
  margin: -12px 12px -12px 0;
  vertical-align: top;
  padding-left: 20px;
}

.chat-pill__capsule {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  font-size: 12px;
  color: var(--text-secondary);
  max-width: 100%;
}

.chat-pill__capsule::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal);
  flex-shrink: 0;
}

.chat-pill__capsule--started::before {
  background: var(--info);
}

.chat-pill__capsule--completed::before {
  background: var(--success);
}

.chat-pill__capsule--completed::after {
  content: '✓';
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
  margin-left: 4px;
  vertical-align: baseline;
}

.chat-pill__capsule--error::before {
  background: var(--error);
}

.chat-pill__text {
  color: var(--text-secondary);
}

/* ===== Thought (inner monologue, natural display) ===== */
.chat-msg--thought-row {
  align-self: flex-start;
  max-width: 68%;
}

.chat-msg__body--thought {
  color: rgba(60, 60, 60, 0.75);
  font-size: 14px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', 'Courier New', 'PingFang SC', 'Microsoft YaHei', monospace;
  line-height: 1.4;
  letter-spacing: -0.01em;
  white-space: pre-wrap;
  word-break: break-word;
  font-style: normal;
  font-feature-settings: 'tnum' 1;
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 12px;
  font-size: 11px;
  color: var(--text-tertiary);
  background: var(--surface-elevated);
  border-radius: 12px;
  margin: 0 auto;
  animation: fadeIn 200ms var(--ease-out);
  /* 减少上下间距（抵消父容器的 gap: 24px） */
  margin-top: -16px;
  margin-bottom: -16px;
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

/* ===== UI Action result card ===== */
.chat-ui-action {
  display: flex;
  flex-direction: column;
  align-self: flex-start;
  max-width: 72%;
  background: var(--surface-secondary, #FAFAFA);
  border-left: 3px solid #8B7AAF;
  border-radius: 6px;
  padding: 10px 14px;
  animation: fadeIn 250ms var(--ease-out);
}

.chat-ui-action__header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.chat-ui-action__icon {
  font-size: 14px;
  color: #8B7AAF;
  flex-shrink: 0;
}

.chat-ui-action__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.chat-ui-action__time {
  font-size: 11px;
  color: var(--text-quaternary);
  margin-left: auto;
}

.chat-ui-action__body {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-primary);
}

.chat-ui-action__pre {
  background: var(--text-primary, #18181B);
  color: var(--surface-base, #fff);
  padding: 8px 12px;
  border-radius: var(--radius-md, 4px);
  overflow-x: auto;
  font-size: 12px;
  font-family: var(--font-mono, monospace);
  margin: 0;
}

.chat-ui-action__text {
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-ui-action__markdown :deep(p) {
  margin-bottom: var(--spacing-1);
}

.chat-ui-action__markdown :deep(code) {
  background: var(--surface-hover);
  color: var(--accent);
  padding: 1px 4px;
  border-radius: var(--radius-md);
  font-size: var(--font-xs);
}

.chat-ui-action__markdown :deep(pre) {
  background: var(--text-primary);
  color: var(--surface-base);
  padding: 8px 12px;
  border-radius: var(--radius-md);
  overflow-x: auto;
  font-size: 12px;
  font-family: var(--font-mono);
}
</style>
