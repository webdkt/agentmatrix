<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { agentAPI } from '@/api/agent'
import { sessionAPI } from '@/api/session'
import { addPendingEmail, removePendingEmail } from '@/composables/usePendingEmails'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  mode: {
    type: String,
    default: 'new',
    validator: (v) => ['new', 'reply'].includes(v)
  },
  preselectedAgent: {
    type: Object,
    default: null
  },
  replyToEmail: {
    type: Object,
    default: null
  },
  session: {
    type: Object,
    default: null
  }
})

const { t } = useI18n()
const emit = defineEmits(['close', 'sent', 'send-started', 'send-failed'])

// 状态
const agents = ref([])
const agentSearchQuery = ref('')
const showAgentDropdown = ref(false)
const selectedAgent = ref(null)
const messageBody = ref('')
const attachments = ref([])
const isSending = ref(false)
const isLoadingAgents = ref(false)
const isDragging = ref(false)

// 计算属性
const isReplyMode = computed(() => props.mode === 'reply')

const currentAgent = computed(() => {
  if (isReplyMode.value) {
    // reply 模式：自动解析收件人
    if (!props.replyToEmail) return null
    const recipientName = props.replyToEmail.is_from_user
      ? (props.replyToEmail.recipient || props.session?.name)
      : props.replyToEmail.sender
    return { name: recipientName }
  }
  // new 模式：手动选择的 agent
  return selectedAgent.value
})

const dialogTitle = computed(() => {
  if (isReplyMode.value) {
    return `Reply to ${props.replyToEmail?.sender || 'Agent'}`
  }
  return t('sessions.newEmail')
})

const filteredAgents = computed(() => {
  if (!agentSearchQuery.value) {
    return agents.value
  }

  const query = agentSearchQuery.value.toLowerCase()
  return agents.value.filter(agent => {
    return agent.name?.toLowerCase().includes(query) ||
           agent.description?.toLowerCase().includes(query)
  })
})

const canSend = computed(() => {
  return currentAgent.value && messageBody.value.trim() && !isSending.value
})

// 生命周期
onMounted(async () => {
  await loadAgents()
})

// 监听 show 变化，重置表单
watch(() => props.show, async (newValue) => {
  if (newValue) {
    resetForm()
    // 如果有预选的agent，等待agents加载后自动选择
    if (props.preselectedAgent && !isReplyMode.value) {
      // 确保agents已加载
      if (agents.value.length === 0) {
        await loadAgents()
      }
      // 查找匹配的agent（可能是对象或名称字符串）
      const agentName = typeof props.preselectedAgent === 'string'
        ? props.preselectedAgent
        : props.preselectedAgent.name
      const agent = agents.value.find(a => a.name === agentName)
      if (agent) {
        selectedAgent.value = agent
        agentSearchQuery.value = agent.name
      }
    }
  }
})

// 加载 Agent 列表
const loadAgents = async () => {
  isLoadingAgents.value = true
  try {
    const result = await agentAPI.getAgents()
    agents.value = result.agents || []
    console.log('Loaded agents:', agents.value.length)
  } catch (error) {
    console.error('Failed to load agents:', error)
  } finally {
    isLoadingAgents.value = false
  }
}

// 选择 Agent
const selectAgent = (agent) => {
  selectedAgent.value = agent
  agentSearchQuery.value = agent.name
  showAgentDropdown.value = false
}

// 移除选中的 Agent
const clearAgent = () => {
  selectedAgent.value = null
  agentSearchQuery.value = ''
}

// 处理文件选择
const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  attachments.value.push(...files)
}

// 拖拽处理
const handleDragEnter = (event) => {
  event.preventDefault()
  isDragging.value = true
}

const handleDragLeave = (event) => {
  event.preventDefault()
  isDragging.value = false
}

const handleDragOver = (event) => {
  event.preventDefault()
}

const handleFileDrop = (event) => {
  event.preventDefault()
  isDragging.value = false
  const files = Array.from(event.dataTransfer.files)
  attachments.value.push(...files)
}

// 移除附件
const removeAttachment = (index) => {
  attachments.value.splice(index, 1)
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// 重置表单
const resetForm = () => {
  selectedAgent.value = null
  agentSearchQuery.value = ''
  messageBody.value = ''
  attachments.value = []
  isSending.value = false
}

// 发送邮件
const handleSend = async () => {
  if (!canSend.value) return

  isSending.value = true
  let emailData
  let placeholder = null

  try {
    if (isReplyMode.value) {
      // reply 模式：构建回复数据
      emailData = {
        recipient: currentAgent.value.name,
        subject: '',
        body: messageBody.value,
        in_reply_to: props.replyToEmail.id,
        task_id: props.replyToEmail.task_id || props.session?.session_id
      }

      // 创建 placeholder
      placeholder = addPendingEmail(props.session.session_id, emailData)
      emit('send-started', { placeholder, emailData })
    } else {
      // new 模式：构建新邮件数据
      emailData = {
        recipient: selectedAgent.value.name,
        subject: '',
        body: messageBody.value
      }

      // new 模式：不创建 placeholder（SessionList 会处理）
      emit('send-started', emailData)
    }

    // 清空输入
    messageBody.value = ''

    // 关闭对话框（优化体验）
    emit('close')

    // 调用 API 发送
    const response = await sessionAPI.sendEmail(
      isReplyMode.value ? props.session.session_id : 'new',
      emailData,
      attachments.value
    )

    console.log('✅ Email sent successfully:', response)

    // 清理 placeholder
    if (placeholder) {
      removePendingEmail(placeholder.id)
    }

    emit('sent', { response, placeholderId: placeholder?.id })
  } catch (error) {
    console.error('❌ Failed to send email:', error)

    // 清理 placeholder
    if (placeholder) {
      removePendingEmail(placeholder.id)
      emit('send-failed', { placeholderId: placeholder.id, error: error.message })
    } else {
      emit('send-failed', { error: error.message })
    }

    alert(`Failed to send email: ${error.message}`)
  } finally {
    isSending.value = false
  }
}

// 关闭对话框
const close = () => {
  emit('close')
}
</script>

<template>
  <Transition name="modal">
    <div v-if="show" class="new-email-modal">
      <!-- Overlay -->
      <div class="new-email-modal__overlay" @click="close"></div>

      <!-- Modal Content (Larger) -->
      <div
        :class="['new-email-modal__content', { 'new-email-modal__content--dragging': isDragging }]"
        @dragenter="handleDragEnter"
        @dragleave="handleDragLeave"
        @dragover="handleDragOver"
        @drop="handleFileDrop"
      >
        <!-- Header -->
        <div class="new-email-modal__header">
          <h2 class="new-email-modal__title">{{ dialogTitle }}</h2>
          <button
            @click="close"
            class="new-email-modal__close"
          >
            <MIcon name="x" />
          </button>
        </div>

        <!-- Form -->
        <div class="new-email-modal__form">
          <!-- Recipient (new mode only) -->
          <div v-if="!isReplyMode" class="new-email-modal__field">
            <label class="new-email-modal__label">{{ t('emails.to') }}</label>
            <div class="new-email-modal__input-wrapper">
              <MIcon name="at" class="new-email-modal__input-icon" />
              <input
                v-model="agentSearchQuery"
                @focus="showAgentDropdown = true"
                :placeholder="t('emails.searchAgent')"
                class="new-email-modal__input"
              />

              <button
                v-if="selectedAgent"
                @click="clearAgent"
                class="new-email-modal__clear"
              >
                <MIcon name="x" />
              </button>
              </div>

              <!-- Dropdown -->
            <div
              v-show="showAgentDropdown && (filteredAgents.length > 0 || agentSearchQuery)"
              class="new-email-modal__dropdown"
            >
              <div
                v-for="agent in filteredAgents"
                :key="agent.name"
                @click="selectAgent(agent)"
                class="new-email-modal__dropdown-item"
              >
                <div class="new-email-modal__agent-name">{{ agent.name }}</div>
                <div class="new-email-modal__agent-desc">{{ agent.description || 'No description' }}</div>
              </div>

              <div
                v-if="filteredAgents.length === 0"
                class="new-email-modal__dropdown-empty"
              >
                No agents found
              </div>
            </div>
          </div>

          <!-- Recipient Display (reply mode only) -->
          <div v-else class="new-email-modal__field">
            <label class="new-email-modal__label">{{ t('emails.to') }}</label>
            <div class="new-email-modal__recipient-display">
              <MIcon name="at" class="new-email-modal__input-icon" />
              <span class="new-email-modal__recipient-name">{{ currentAgent?.name }}</span>
            </div>
          </div>

          <!-- Message (Large editing area) -->
          <div class="new-email-modal__message">
            <label class="new-email-modal__label">{{ t('emails.message') }}</label>
            <div class="new-email-modal__textarea-wrapper">
              <textarea
                v-model="messageBody"
                rows="12"
                :placeholder="t('emails.messagePlaceholder')"
                class="new-email-modal__textarea"
              ></textarea>

              <!-- Drag overlay hint -->
              <div v-if="isDragging" class="new-email-modal__drag-hint">
                <MIcon name="upload" />
                <span>Drop files to attach</span>
              </div>
            </div>
          </div>

          <!-- Attachments (Compact) -->
          <div v-if="attachments.length > 0" class="new-email-modal__attachments">
            <div class="new-email-modal__attachments-header">
              <span>{{ attachments.length }} {{ attachments.length === 1 ? 'file' : 'files' }}</span>
            </div>
            <div class="new-email-modal__attachments-list">
              <div
                v-for="(file, index) in attachments"
                :key="index"
                class="new-email-modal__attachment"
              >
                <div class="new-email-modal__attachment-icon">
                  <MIcon name="file" />
                </div>
                <div class="new-email-modal__attachment-info">
                  <span class="new-email-modal__attachment-name">{{ file.name }}</span>
                  <span class="new-email-modal__attachment-size">{{ formatFileSize(file.size) }}</span>
                </div>
                <button
                  @click="removeAttachment(index)"
                  class="new-email-modal__attachment-remove"
                >
                  <MIcon name="x" />
                </button>
              </div>
            </div>
          </div>

          <!-- Attachment upload button -->
          <div v-else class="new-email-modal__upload">
            <button
              @click="$refs.fileInput.click()"
              class="new-email-modal__upload-btn"
            >
              <MIcon name="paperclip" />
              <span>{{ t('emails.attachFile') }}</span>
            </button>
            <input
              ref="fileInput"
              type="file"
              @change="handleFileSelect"
              multiple
              class="hidden"
              accept="*/*"
            >
          </div>
        </div>

        <!-- Footer -->
        <div class="new-email-modal__footer">
          <button
            @click="close"
            class="new-email-modal__btn new-email-modal__btn--secondary"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            @click="handleSend"
            :disabled="!canSend"
            class="new-email-modal__btn new-email-modal__btn--primary"
          >
            <span v-if="!isSending">{{ t('emails.send') }}</span>
            <span v-else>{{ t('emails.sending') }}</span>
            <span v-if="isSending" class="animate-spin"><MIcon name="loader" /></span>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.new-email-modal {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
}

.new-email-modal__overlay {
  position: absolute;
  inset: 0;
  background: rgba(26, 26, 26, 0.3);
}

.new-email-modal__content {
  position: relative;
  background: white;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  width: 100%;
  max-width: 700px; /* Larger than before (was 2xl) */
  max-height: 90vh;
  margin: var(--spacing-md);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: modalEnter 250ms var(--ease-out);
}

.new-email-modal__content--dragging {
  border: 2px dashed var(--accent);
  background: rgba(194, 59, 34, 0.05);
}

/* Header */
.new-email-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--neutral-200);
  background: var(--neutral-50);
}

.new-email-modal__title {
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0;
}

.new-email-modal__close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--neutral-400);
  font-size: var(--icon-lg);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.new-email-modal__close:hover {
  color: var(--neutral-600);
  background: var(--neutral-100);
}

/* Form */
.new-email-modal__form {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.new-email-modal__field {
  position: relative;
}

.new-email-modal__label {
  display: block;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
  margin-bottom: var(--spacing-xs);
}

.new-email-modal__input-wrapper {
  position: relative;
}

.new-email-modal__input-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: var(--icon-md);
  color: var(--neutral-400);
  pointer-events: none;
}

.new-email-modal__input {
  width: 100%;
  height: var(--input-height-md);
  padding: 0 var(--spacing-md) 0 40px;
  background: var(--neutral-50);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  color: var(--neutral-700);
  transition: all var(--duration-base) var(--ease-out);
}

.new-email-modal__input::placeholder {
  color: var(--neutral-400);
}

.new-email-modal__input:focus {
  outline: none;
  border-color: var(--accent);
  background: white;
}

.new-email-modal__clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--neutral-400);
  font-size: var(--icon-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.new-email-modal__clear:hover {
  color: var(--neutral-600);
}

/* Dropdown */
.new-email-modal__dropdown {
  position: absolute;
  z-index: var(--z-dropdown);
  width: 100%;
  max-height: 200px;
  background: white;
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  overflow-y: auto;
  margin-top: 4px;
}

.new-email-modal__dropdown-item {
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.new-email-modal__dropdown-item:hover {
  background: var(--neutral-50);
}

.new-email-modal__agent-name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
}

.new-email-modal__agent-desc {
  font-size: var(--font-xs);
  color: var(--neutral-400);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.new-email-modal__dropdown-empty {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

/* Recipient Display (reply mode) */
.new-email-modal__recipient-display {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: var(--neutral-50);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  min-height: var(--input-height-md);
}

.new-email-modal__recipient-name {
  flex: 1;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
}

/* Message */
.new-email-modal__message {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.new-email-modal__textarea-wrapper {
  position: relative;
  flex: 1;
}

.new-email-modal__textarea {
  width: 100%;
  min-height: 300px;
  padding: var(--spacing-md);
  background: var(--neutral-50);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  font-size: var(--font-base);
  font-family: inherit;
  line-height: var(--leading-relaxed);
  color: var(--neutral-700);
  resize: none;
  transition: all var(--duration-base) var(--ease-out);
}

.new-email-modal__textarea::placeholder {
  color: var(--neutral-400);
}

.new-email-modal__textarea:focus {
  outline: none;
  border-color: var(--accent);
  background: white;
}

.new-email-modal__drag-hint {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  background: rgba(194, 59, 34, 0.9);
  color: white;
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  border-radius: var(--radius-sm);
  pointer-events: none;
}

.new-email-modal__drag-hint i {
  font-size: 32px;
}

/* Attachments */
.new-email-modal__attachments {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.new-email-modal__attachments-header {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  color: var(--neutral-500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.new-email-modal__attachments-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.new-email-modal__attachment {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  background: var(--neutral-50);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  transition: all var(--duration-base) var(--ease-out);
}

.new-email-modal__attachment:hover {
  background: var(--neutral-100);
  border-color: var(--neutral-300);
}

.new-email-modal__attachment-icon {
  width: 28px;
  height: 28px;
  background: var(--primary-100);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-600);
  font-size: var(--font-sm);
  flex-shrink: 0;
}

.new-email-modal__attachment-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.new-email-modal__attachment-name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.new-email-modal__attachment-size {
  font-size: var(--font-xs);
  color: var(--neutral-400);
}

.new-email-modal__attachment-remove {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--neutral-400);
  font-size: var(--icon-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
}

.new-email-modal__attachment-remove:hover {
  color: var(--error-500);
  background: var(--error-50);
}

/* Upload button */
.new-email-modal__upload {
  padding: var(--spacing-sm) 0;
}

.new-email-modal__upload-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--neutral-100);
  border: 1px dashed var(--neutral-300);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.new-email-modal__upload-btn:hover {
  background: var(--neutral-200);
  border-color: var(--neutral-400);
}

/* Footer */
.new-email-modal__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg);
  border-top: 1px solid var(--neutral-200);
  background: var(--neutral-50);
}

.new-email-modal__btn {
  height: var(--button-height-md);
  padding: 0 var(--spacing-lg);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.new-email-modal__btn--secondary {
  background: transparent;
  border: 1px solid var(--neutral-200);
  color: var(--neutral-700);
}

.new-email-modal__btn--secondary:hover {
  background: var(--neutral-100);
}

.new-email-modal__btn--primary {
  background: var(--accent);
  border: 1px solid var(--accent);
  color: white;
}

.new-email-modal__btn--primary:hover:not(:disabled) {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}

.new-email-modal__btn--primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Animations */
@keyframes modalEnter {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}




</style>
