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
  agentName: {
    type: String,
    default: null
  }
})

// ---- Bubble (user / agent) ----

const renderedBody = computed(() => {
  if (!['bubble-user', 'bubble-agent'].includes(props.message.type)) return ''
  const body = props.message.data?.detail?.body_preview
  if (!body) return ''
  try {
    return marked(body)
  } catch {
    return body
  }
})

// ---- Pill (action events) ----

const pillText = computed(() => {
  if (props.message.type !== 'pill') return ''
  const { eventType, eventName, detail } = props.message.data
  if (eventType === 'action') {
    if (eventName === 'detected') {
      const actions = detail.actions || []
      return `检测到动作: ${actions.join(', ')}`
    }
    if (eventName === 'started') {
      return `执行 ${detail.action_name || ''}`
    }
    if (eventName === 'completed') {
      if (detail.status === 'error') {
        return `${detail.action_name || ''} 出错`
      }
      if (detail.status === 'canceled') {
        return `${detail.action_name || ''} 已取消`
      }
      return `完成 ${detail.action_name || detail.action_label || ''}`
    }
    if (eventName === 'error') {
      return `${detail.action_name || ''} 出错: ${detail.error_message || ''}`
    }
  }
  return `${eventType}.${eventName}`
})

// ---- Thought (think.brain) ----

const thoughtText = computed(() => {
  if (props.message.type !== 'thought') return ''
  return props.message.data?.detail?.raw_reply || ''
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
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))

  if (diffMins < 1) return 'now'
  if (diffMins < 60) return `${diffMins}m`
  if (diffHours < 24) return `${diffHours}h`
  return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}
</script>

<template>
  <!-- User chat bubble (right-aligned, green) -->
  <div v-if="message.type === 'bubble-user'" class="chat-msg chat-msg--user">
    <div class="chat-msg__bubble">
      <div class="chat-msg__header">
        <span class="chat-msg__time">{{ formatTime(message.timestamp) }}</span>
      </div>
      <div v-if="message.data.detail?.subject" class="chat-msg__subject">
        {{ message.data.detail.subject }}
      </div>
      <div class="chat-msg__body markdown-content" v-html="renderedBody"></div>
    </div>
  </div>

  <!-- Agent chat bubble (left-aligned, parchment) -->
  <div v-else-if="message.type === 'bubble-agent'" class="chat-msg">
    <div class="chat-msg__bubble">
      <div class="chat-msg__header">
        <span class="chat-msg__time">{{ formatTime(message.timestamp) }}</span>
      </div>
      <div v-if="message.data.detail?.subject" class="chat-msg__subject">
        {{ message.data.detail.subject }}
      </div>
      <div class="chat-msg__body markdown-content" v-html="renderedBody"></div>
    </div>
  </div>

  <!-- Agent-to-agent communication (subtle, centered) -->
  <div v-else-if="message.type === 'agent-comm'" class="chat-agent-comm">
    <span class="chat-agent-comm__icon">
      <MIcon name="mail" />
    </span>
    <span class="chat-agent-comm__text">{{ agentCommText }}</span>
    <span class="chat-agent-comm__time">{{ formatTime(message.timestamp) }}</span>
  </div>

  <!-- Status pill (action events) -->
  <div v-else-if="message.type === 'pill'" class="chat-pill">
    <div class="chat-pill__capsule">
      <span class="chat-pill__icon">
        <MIcon :name="message.data.eventName === 'detected' ? 'search' : message.data.eventName === 'started' ? 'loader' : message.data.eventName === 'completed' ? 'check' : 'alert-circle'" />
      </span>
      <span class="chat-pill__text">{{ pillText }}</span>
      <span class="chat-pill__time">{{ formatTime(message.timestamp) }}</span>
    </div>
  </div>

  <!-- Thought (agent's inner monologue) -->
  <div v-else-if="message.type === 'thought'" class="chat-thought">
    <div class="chat-thought__bubble">
      <div class="chat-thought__label">
        <MIcon name="brain" />
        <span>{{ agentName || 'Agent' }} 的思考</span>
      </div>
      <div class="chat-thought__body">{{ thoughtText }}</div>
      <div class="chat-thought__footer">
        <span class="chat-thought__time">{{ formatTime(message.timestamp) }}</span>
      </div>
    </div>
  </div>

  <!-- System event (minimal, centered) -->
  <div v-else-if="message.type === 'system'" class="chat-system">
    <span class="chat-system__text">{{ systemText }}</span>
    <span class="chat-system__time">{{ formatTime(message.timestamp) }}</span>
  </div>
</template>

<style scoped>
/* ===== User chat bubble (right-aligned, green) ===== */
.chat-msg {
  display: flex;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 200ms var(--ease-out);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px) }
  to { opacity: 1; transform: translateY(0) }
}

.chat-msg__bubble {
  max-width: 75%;
  background: var(--parchment-100);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-md);
  border-bottom-left-radius: var(--radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
}

.chat-msg--user {
  justify-content: flex-end;
}

.chat-msg--user .chat-msg__bubble {
  background: var(--success-50);
  border-color: var(--success-200);
  border-radius: var(--radius-md);
  border-bottom-right-radius: var(--radius-sm);
}

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

.chat-msg__subject {
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--neutral-700);
  padding-bottom: 4px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--neutral-100);
}

.chat-msg__body {
  font-size: var(--font-sm);
  color: var(--neutral-700);
  line-height: var(--leading-relaxed);
}

/* ===== Agent-to-agent communication ===== */
.chat-agent-comm {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 4px 0;
  animation: fadeIn 200ms var(--ease-out);
}

.chat-agent-comm__icon {
  font-size: var(--font-xs);
  color: var(--neutral-300);
  display: flex;
  align-items: center;
}

.chat-agent-comm__text {
  font-size: 11px;
  color: var(--neutral-400);
  font-style: italic;
}

.chat-agent-comm__time {
  font-size: 10px;
  color: var(--neutral-300);
  flex-shrink: 0;
}

/* ===== Status pill ===== */
.chat-pill {
  display: flex;
  justify-content: center;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 200ms var(--ease-out);
}

.chat-pill__capsule {
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

.chat-pill__icon {
  display: flex;
  align-items: center;
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

.chat-pill__text {
  color: var(--neutral-500);
}

.chat-pill__time {
  font-size: 10px;
  color: var(--neutral-300);
  flex-shrink: 0;
}

/* ===== Thought (inner monologue) ===== */
.chat-thought {
  display: flex;
  padding: var(--spacing-xs) 0;
  animation: fadeIn 200ms var(--ease-out);
}

.chat-thought__bubble {
  max-width: 75%;
  background: var(--neutral-50);
  border: 1px dashed var(--neutral-200);
  border-radius: var(--radius-md);
  border-bottom-left-radius: var(--radius-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  opacity: 0.85;
}

.chat-thought__label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: var(--font-semibold);
  color: var(--neutral-400);
  margin-bottom: 4px;
}

.chat-thought__label .m-icon {
  font-size: var(--font-sm);
  color: var(--neutral-300);
}

.chat-thought__body {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  line-height: var(--leading-relaxed);
  font-style: italic;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-thought__footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.chat-thought__time {
  font-size: 10px;
  color: var(--neutral-300);
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
  color: var(--neutral-300);
}

.chat-system__time {
  font-size: 10px;
  color: var(--neutral-300);
}

/* ===== Markdown styles ===== */
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
