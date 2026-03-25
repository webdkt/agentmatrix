<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import { useEmailStore } from '@/stores/email'
import { useUIStore } from '@/stores/ui'
import { openAttachment, getAttachmentIcon } from '@/utils/attachmentHelper'
import MIcon from '@/components/icons/MIcon.vue'

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

const { t } = useI18n()
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

// 操作处理函数
const handleReply = () => {
  console.log('Reply to email:', props.email.id)
  emit('reply', props.email)
}

const handleCopy = async () => {
  try {
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
    await emailStore.deleteEmail(props.email.id, props.email.session_id)
    uiStore.showNotification('Email deleted', 'success')
  } catch (error) {
    console.error('Failed to delete email:', error)
    uiStore.showNotification('Failed to delete email', 'error')
  }
}

// 处理附件点击
const handleAttachmentClick = async (attachment) => {
  try {
    await openAttachment(
      props.email.recipient,
      props.email.task_id,
      attachment.filename
    )
  } catch (error) {
    console.error('Failed to open attachment:', error)
    uiStore.showNotification('Failed to open attachment', 'error')
  }
}
</script>

<template>
  <div class="email-item">
    <!-- Email Card (Direct card, no avatar + card layout) -->
    <div :class="['email-card', { 'email-card--user': email.is_from_user }]">
      <!-- Header -->
      <div class="email-card__header">
        <div class="email-card__sender">
          <span class="email-card__label">{{ email.is_from_user ? 'TO' : 'FROM' }}</span>
          <span class="email-card__name">
            <MIcon :name="email.is_from_user ? 'send' : 'agent-dispatch'" />
            {{ displayName }}
          </span>
        </div>
        <span class="email-card__time">{{ formatTime(email.timestamp) }}</span>
      </div>

      <!-- Content -->
      <div class="email-card__content">
        <!-- Subject (if exists) -->
        <div v-if="email.subject" class="email-card__subject">
          {{ email.subject }}
        </div>

        <!-- Body -->
        <div class="email-card__body markdown-content" v-html="renderedBody"></div>

        <!-- Attachments -->
        <div v-if="email.attachments && email.attachments.length > 0" class="email-card__attachments">
          <div class="email-card__attachments-label">Attachments</div>
          <div
            v-for="(attachment, index) in email.attachments"
            :key="index"
            class="email-card__attachment"
          >
            <div
              @click="handleAttachmentClick(attachment)"
              class="email-card__attachment-main"
            >
              <div class="email-card__attachment-icon">
                <MIcon :name="getAttachmentIcon(attachment.filename).replace('ti-', '')" />
              </div>
              <div class="email-card__attachment-info">
                <span class="email-card__attachment-name">{{ attachment.filename }}</span>
                <span class="email-card__attachment-size">{{ formatFileSize(attachment.size) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="email-card__actions">
        <button
          @click="handleReply"
          class="email-card__action"
          :title="t('emails.reply')"
        >
          <MIcon name="arrow-back-up" />
          <span>Reply</span>
        </button>
        <button
          @click="handleCopy"
          class="email-card__action"
          title="Copy"
        >
          <MIcon name="copy" />
        </button>
        <button
          @click="handleDelete"
          class="email-card__action"
          :title="t('common.delete')"
        >
          <MIcon name="trash" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.email-item {
  animation: emailItemEnter 250ms var(--ease-out);
}

@keyframes emailItemEnter {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Email Card */
.email-card {
  background: var(--parchment-100);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  padding: var(--spacing-md);
  transition: all var(--duration-base) var(--ease-out);
  position: relative;
}

.email-card:hover {
  border-color: var(--neutral-300);
  border-left: 3px solid var(--accent);
}

.email-card--user {
  background: var(--parchment-50);
  border-color: var(--success-200);
}

.email-card--user:hover {
  border-left-color: var(--success-500);
}

/* Header */
.email-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.email-card__sender {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.email-card__label {
  font-size: 11px;
  font-weight: var(--font-semibold);
  font-variant: small-caps;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  border: 1px solid;
}

/* 收到的邮件 - From标签 */
.email-card:not(.email-card--user) .email-card__label {
  color: var(--accent);
  background: var(--parchment-100);
  border-color: var(--neutral-200);
}

/* 发出的邮件 - To标签 */
.email-card--user .email-card__label {
  color: var(--success-600);
  background: var(--success-50);
  border-color: var(--success-200);
}

.email-card__name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
}

.email-card__name i {
  font-size: var(--font-base);
  color: var(--neutral-400);
}

/* 收到的邮件 - robot图标颜色 */
.email-card:not(.email-card--user) .email-card__name i {
  color: var(--accent);
}

/* 发出的邮件 - send图标颜色 */
.email-card--user .email-card__name i {
  color: var(--success-500);
}

.email-card__time {
  font-size: var(--font-xs);
  color: var(--neutral-400);
  flex-shrink: 0;
}

/* Content */
.email-card__content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.email-card__subject {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  padding-bottom: var(--spacing-xs);
  border-bottom: 1px solid var(--neutral-100);
}

.email-card__body {
  font-size: var(--font-sm);
  color: var(--neutral-600);
  line-height: var(--leading-relaxed);
}

/* Attachments */
.email-card__attachments {
  margin-top: var(--spacing-xs);
}

.email-card__attachments-label {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  color: var(--neutral-500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--spacing-xs);
}

.email-card__attachment {
  padding: var(--spacing-xs);
  background: var(--neutral-50);
  border-radius: var(--radius-sm);
  transition: all var(--duration-base) var(--ease-out);
}

.email-card__attachment:hover {
  background: var(--neutral-100);
}

.email-card__attachment-main {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  cursor: pointer;
}

.email-card__attachment-icon {
  width: 32px;
  height: 32px;
  background: var(--neutral-100);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-300);
  font-size: var(--font-sm);
  flex-shrink: 0;
}

.email-card__attachment-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.email-card__attachment-name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.email-card__attachment-size {
  font-size: var(--font-xs);
  color: var(--neutral-400);
}

/* Actions */
.email-card__actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--neutral-100);
  margin-top: var(--spacing-sm);
}

.email-card__action {
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-sm);
  color: var(--neutral-600);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  gap: 4px;
}

.email-card__action:hover {
  color: var(--neutral-900);
  background: var(--neutral-100);
}

.email-card__action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Markdown Styles */
.markdown-content :deep(h1) {
  font-size: var(--font-xl);
  font-weight: var(--font-bold);
  color: var(--neutral-900);
  margin-bottom: var(--spacing-sm);
  margin-top: var(--spacing-md);
}

.markdown-content :deep(h2) {
  font-size: var(--font-lg);
  font-weight: var(--font-bold);
  color: var(--neutral-900);
  margin-bottom: var(--spacing-xs);
  margin-top: var(--spacing-sm);
}

.markdown-content :deep(h3) {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin-bottom: var(--spacing-xs);
  margin-top: var(--spacing-xs);
}

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
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
}

.markdown-content :deep(pre) {
  background: var(--neutral-800);
  color: var(--neutral-50);
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  overflow-x: auto;
  margin-bottom: var(--spacing-sm);
}

.markdown-content :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid var(--neutral-300);
  padding-left: var(--spacing-md);
  font-style: italic;
  color: var(--neutral-500);
  margin-bottom: var(--spacing-xs);
}

.markdown-content :deep(a) {
  color: var(--info-500);
  text-decoration: underline;
}

.markdown-content :deep(a:hover) {
  color: var(--info-700);
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: var(--spacing-sm);
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--neutral-300);
  padding: var(--spacing-xs) var(--spacing-sm);
  font-size: var(--font-sm);
}

.markdown-content :deep(th) {
  background: var(--neutral-100);
  font-weight: var(--font-semibold);
}
</style>
