<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import { useEmailStore } from '@/stores/email'
import { useUIStore } from '@/stores/ui'

const props = defineProps({
  email: {
    type: Object,
    required: true
  },
  user_agent_name: {
    type: String,
    default: 'User'
  }
})

const emit = defineEmits(['reply'])

const emailStore = useEmailStore()
const uiStore = useUIStore()

// 渲染 Markdown
const renderedBody = computed(() => {
  if (!props.email.body) return ''
  try {
    return marked(props.email.body)
  } catch (error) {
    console.error('Markdown rendering error:', error)
    return props.email.body
  }
})

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return ''

  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / (1000 * 60))
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60))
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return date.toLocaleDateString('en-US', { weekday: 'short' })

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  })
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 计算属性
const displayName = computed(() => {
  if (props.email.is_from_user) {
    return props.email.recipient || 'To Agent'
  } else {
    return props.email.sender || 'From Agent'
  }
})

const avatarClass = computed(() => {
  return props.email.is_from_user
    ? 'from-accent-500 to-accent-600'
    : 'from-blue-400 to-blue-600'
})

const messageCardClass = computed(() => {
  return props.email.is_from_user
    ? 'message-card message-user'
    : 'message-card message-ai'
})

// 操作处理函数
const handleReply = () => {
  console.log('Reply to email:', props.email.id)
  emit('reply', props.email)
}

const handleCopy = async () => {
  try {
    // 复制邮件正文（纯文本）
    await navigator.clipboard.writeText(props.email.body)
    uiStore.showNotification('Copied to clipboard', 'success')
  } catch (error) {
    console.error('Failed to copy:', error)
    uiStore.showNotification('Failed to copy', 'error')
  }
}

const handleDelete = async () => {
  if (!confirm('Are you sure you want to delete this email?')) {
    return
  }

  try {
    // 需要从父组件获取 session_id，这里先使用 email.session_id
    await emailStore.deleteEmail(props.email.id, props.email.session_id)
    uiStore.showNotification('Email deleted', 'success')
  } catch (error) {
    console.error('Failed to delete email:', error)
    uiStore.showNotification('Failed to delete email', 'error')
  }
}
</script>

<template>
  <div class="flex gap-4 message-item">
    <!-- Avatar -->
    <div
      :class="avatarClass"
      class="w-10 h-10 rounded-full bg-gradient-to-br flex items-center justify-center text-white font-semibold shadow-card flex-shrink-0 mt-1"
    >
      <span v-if="email.is_from_user">{{ user_agent_name.charAt(0).toUpperCase() }}</span>
      <i v-else class="ti ti-brain text-lg"></i>
    </div>

    <!-- Message Card -->
    <div class="flex-1 flex flex-col gap-3">
      <!-- Main Card -->
      <div :class="messageCardClass">
        <!-- Header -->
        <div class="message-header">
          <div class="message-header-left">
            <span class="message-label">{{ email.is_from_user ? 'To' : 'From' }}</span>
            <div class="flex flex-col">
              <span :class="email.is_from_user ? 'message-recipient' : 'message-sender'">
                <i class="ti ti-robot"></i>
                <span>{{ displayName }}</span>
              </span>
            </div>
          </div>
          <span class="message-time">{{ formatTime(email.timestamp) }}</span>
        </div>

        <!-- Content -->
        <div class="message-content">
          <!-- Subject (if exists) -->
          <div v-if="email.subject" class="message-subject">{{ email.subject }}</div>

          <!-- Body -->
          <div class="message-body markdown-content" v-html="renderedBody"></div>

          <!-- Attachments -->
          <div v-if="email.attachments && email.attachments.length > 0" class="mt-3 space-y-2">
            <div class="text-xs font-medium text-surface-500 uppercase tracking-wide">Attachments</div>
            <div
              v-for="(attachment, index) in email.attachments"
              :key="index"
              class="flex items-center justify-between p-2 rounded-lg bg-surface-50 hover:bg-surface-100 transition-colors group"
            >
              <!-- 点击附件预览（新标签页） -->
              <a
                :href="`/api/sessions/${email.session_id}/emails/${email.id}/attachments/${attachment.filename}`"
                target="_blank"
                rel="noopener noreferrer"
                class="flex items-center gap-2 flex-1 min-w-0 cursor-pointer"
              >
                <div class="w-8 h-8 rounded bg-primary-100 flex items-center justify-center flex-shrink-0">
                  <i class="ti ti-file text-primary-600 text-sm"></i>
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="text-sm font-medium text-surface-700 truncate">{{ attachment.filename }}</span>
                  <span class="text-xs text-surface-400">{{ formatFileSize(attachment.size) }}</span>
                </div>
              </a>

              <!-- 下载按钮 -->
              <a
                :href="`/api/sessions/${email.session_id}/emails/${email.id}/attachments/${attachment.filename}`"
                :download="attachment.filename"
                class="opacity-0 group-hover:opacity-100 transition-opacity p-2 rounded hover:bg-surface-200 text-surface-600 hover:text-primary-600 flex-shrink-0"
                title="Download attachment"
              >
                <i class="ti ti-download"></i>
              </a>
            </div>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="message-actions">
          <button
            @click="handleReply"
            class="message-action-btn"
            title="Reply"
          >
            <i class="ti ti-arrow-back-up"></i>
            <span>Reply</span>
          </button>
          <button
            @click="handleCopy"
            class="message-action-btn"
            title="Copy"
          >
            <i class="ti ti-copy"></i>
          </button>
          <button
            @click="handleDelete"
            class="message-action-btn"
            title="Delete"
          >
            <i class="ti ti-trash"></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.shadow-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.message-item {
  animation: messageEnter 0.3s ease-out;
}

@keyframes messageEnter {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.message-card {
  background-color: white;
  border-radius: 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid rgb(229 228 226 / 0.6);
  padding: 1.25rem;
  transition: all 0.2s;
}

.message-card.message-user {
  background: linear-gradient(to bottom right, rgb(254 250 240), white);
  border-color: rgb(254 243 199);
}

.message-card.message-ai {
  background-color: white;
  border-color: rgb(229 228 226 / 0.6);
}

.message-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.message-header-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.message-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: rgb(168 163 158);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.125rem 0.5rem;
  background-color: rgb(243 244 246);
  border-radius: 9999px;
}

.message-sender {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(23 23 23);
}

.message-recipient {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(107 33 132);
}

.message-time {
  font-size: 0.75rem;
  color: rgb(168 163 158);
  flex-shrink: 0;
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.message-subject {
  font-size: 0.875rem;
  font-weight: 600;
  color: rgb(23 23 23);
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgb(243 244 246);
}

.message-body {
  font-size: 0.875rem;
  color: rgb(87 83 78);
  line-height: 1.6;
}

/* Markdown 样式 */
.markdown-content :deep(h1) {
  font-size: 1.25rem;
  font-weight: 700;
  color: rgb(23 23 23);
  margin-bottom: 0.75rem;
  margin-top: 1rem;
}

.markdown-content :deep(h2) {
  font-size: 1.125rem;
  font-weight: 700;
  color: rgb(23 23 23);
  margin-bottom: 0.5rem;
  margin-top: 0.75rem;
}

.markdown-content :deep(h3) {
  font-size: 1rem;
  font-weight: 600;
  color: rgb(23 23 23);
  margin-bottom: 0.5rem;
  margin-top: 0.5rem;
}

.markdown-content :deep(p) {
  margin-bottom: 0.5rem;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin-left: 1rem;
  margin-bottom: 0.5rem;
}

.markdown-content :deep(li) {
  margin-bottom: 0.25rem;
}

.markdown-content :deep(code) {
  background-color: rgb(243 244 246);
  color: rgb(107 33 132);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
  font-size: 0.875rem;
}

.markdown-content :deep(pre) {
  background-color: rgb(38 38 38);
  color: rgb(249 250 251);
  padding: 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  margin-bottom: 0.75rem;
}

.markdown-content :deep(pre code) {
  background-color: transparent;
  color: rgb(249 250 251);
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid rgb(209 213 219);
  padding-left: 1rem;
  font-style: italic;
  color: rgb(115 115 115);
  margin-bottom: 0.5rem;
}

.markdown-content :deep(a) {
  color: rgb(5 122 185);
  text-decoration: underline;
}

.markdown-content :deep(a:hover) {
  color: rgb(3 105 143);
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0.75rem;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid rgb(209 213 219);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}

.markdown-content :deep(th) {
  background-color: rgb(243 244 246);
  font-weight: 600;
}

.message-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid rgb(243 244 246);
  margin-top: 0.75rem;
}

.message-action-btn {
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
  color: rgb(87 83 78);
  border-radius: 0.5rem;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.375rem;
  background: transparent;
  border: none;
  cursor: pointer;
}

.message-action-btn:hover {
  color: rgb(23 23 23);
  background-color: rgb(243 244 246);
}

.message-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
