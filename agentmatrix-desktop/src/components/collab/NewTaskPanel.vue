<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { sessionAPI } from '@/api/session'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { readFile } from '@tauri-apps/plugin-fs'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agent: {
    type: Object,
    required: true
  }
})

const { t } = useI18n()
const emit = defineEmits(['back', 'send-started', 'sent', 'send-failed'])

const messageBody = ref('')
const attachments = ref([])
const isSending = ref(false)
const isDragging = ref(false)

const canSend = computed(() => {
  return messageBody.value.trim() && !isSending.value
})

// ---- File handling ----

async function pathToFile(path) {
  const name = path.split('/').pop() || path
  const content = await readFile(path)
  const blob = new Blob([content])
  return new File([blob], name)
}

let unlistenDragDrop = null

onMounted(async () => {
  const webview = await getCurrentWebview()
  unlistenDragDrop = await webview.onDragDropEvent(async (event) => {
    if (event.payload.type === 'over') {
      isDragging.value = true
    } else if (event.payload.type === 'drop') {
      isDragging.value = false
      const paths = event.payload.paths
      if (paths && paths.length > 0) {
        for (const path of paths) {
          try {
            const file = await pathToFile(path)
            attachments.value.push(file)
          } catch (e) {
            console.error('Failed to read file:', path, e)
          }
        }
      }
    } else {
      isDragging.value = false
    }
  })
})

onUnmounted(() => {
  if (unlistenDragDrop) unlistenDragDrop()
})

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files)
  attachments.value.push(...files)
}

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

const removeAttachment = (index) => {
  attachments.value.splice(index, 1)
}

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// ---- Send ----

const handleSend = async () => {
  if (!canSend.value) return

  isSending.value = true

  const emailData = {
    recipient: props.agent.name,
    subject: '',
    body: messageBody.value,
  }

  emit('send-started', emailData)

  try {
    const response = await sessionAPI.sendEmail('new', emailData, attachments.value)
    emit('sent', response)
  } catch (error) {
    console.error('Failed to send task:', error)
    emit('send-failed', { error: error.message })
  } finally {
    isSending.value = false
  }
}

const goBack = () => {
  emit('back')
}
</script>

<template>
  <div
    :class="['new-task-panel', { 'new-task-panel--dragging': isDragging }]"
    @dragenter="handleDragEnter"
    @dragleave="handleDragLeave"
    @dragover="handleDragOver"
    @drop="handleFileDrop"
  >
    <!-- Header -->
    <div class="new-task-panel__header">
      <button class="new-task-panel__back" @click="goBack">
        <MIcon name="arrow-left" />
        <span>Back</span>
      </button>
      <h2 class="new-task-panel__title">New Task</h2>
    </div>

    <!-- Agent display -->
    <div class="new-task-panel__agent">
      <label class="new-task-panel__label">Assign to</label>
      <div class="new-task-panel__agent-display">
        <div class="new-task-panel__agent-avatar">
          {{ agent.name ? agent.name.charAt(0).toUpperCase() : '?' }}
        </div>
        <span class="new-task-panel__agent-name">{{ agent.name }}</span>
      </div>
    </div>

    <!-- Message -->
    <div class="new-task-panel__message">
      <label class="new-task-panel__label">Task Description</label>
      <div class="new-task-panel__textarea-wrapper">
        <textarea
          v-model="messageBody"
          :placeholder="'Describe the task you want to assign...'"
          class="new-task-panel__textarea"
        ></textarea>
        <div v-if="isDragging" class="new-task-panel__drag-hint">
          <MIcon name="upload" />
          <span>Drop files to attach</span>
        </div>
      </div>
    </div>

    <!-- Attachments -->
    <div v-if="attachments.length > 0" class="new-task-panel__attachments">
      <div class="new-task-panel__attachments-header">
        {{ attachments.length }} {{ attachments.length === 1 ? 'file' : 'files' }}
      </div>
      <div class="new-task-panel__attachments-list">
        <div
          v-for="(file, index) in attachments"
          :key="index"
          class="new-task-panel__attachment"
        >
          <MIcon name="file" class="new-task-panel__attachment-icon" />
          <div class="new-task-panel__attachment-info">
            <span class="new-task-panel__attachment-name">{{ file.name }}</span>
            <span class="new-task-panel__attachment-size">{{ formatFileSize(file.size) }}</span>
          </div>
          <button @click="removeAttachment(index)" class="new-task-panel__attachment-remove">
            <MIcon name="x" />
          </button>
        </div>
      </div>
    </div>

    <!-- Upload button -->
    <div v-else class="new-task-panel__upload">
      <button @click="$refs.fileInput.click()" class="new-task-panel__upload-btn">
        <MIcon name="paperclip" />
        <span>Attach files</span>
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

    <!-- Spacer -->
    <div class="new-task-panel__spacer"></div>

    <!-- Footer -->
    <div class="new-task-panel__footer">
      <button
        @click="handleSend"
        :disabled="!canSend"
        class="new-task-panel__send"
      >
        <span v-if="!isSending">Send</span>
        <span v-else class="new-task-panel__sending">
          <MIcon name="loader" class="new-task-panel__spinner" />
          Sending...
        </span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.new-task-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--spacing-6);
  position: relative;
}

.new-task-panel--dragging {
  outline: 2px dashed var(--accent);
  outline-offset: -4px;
}

.new-task-panel__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
  margin-bottom: var(--spacing-6);
}

.new-task-panel__back {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.new-task-panel__back:hover {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.new-task-panel__title {
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.new-task-panel__label {
  display: block;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-1);
}

.new-task-panel__agent {
  margin-bottom: var(--spacing-4);
}

.new-task-panel__agent-display {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.new-task-panel__agent-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  background: var(--accent-muted);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
}

.new-task-panel__agent-name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
}

.new-task-panel__message {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.new-task-panel__textarea-wrapper {
  position: relative;
  flex: 1;
  min-height: 200px;
}

.new-task-panel__textarea {
  width: 100%;
  height: 100%;
  padding: var(--spacing-4);
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--font-base);
  font-family: inherit;
  line-height: var(--leading-relaxed);
  color: var(--text-secondary);
  resize: none;
  transition: all var(--duration-base) var(--ease-out);
  box-sizing: border-box;
}

.new-task-panel__textarea::placeholder {
  color: var(--text-tertiary);
}

.new-task-panel__textarea:focus {
  outline: none;
  border-color: var(--accent);
  background: white;
}

.new-task-panel__drag-hint {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  background: rgba(255, 255, 255, 0.85);
  color: var(--text-secondary);
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  border-radius: var(--radius-md);
  border: 2px dashed var(--accent);
  pointer-events: none;
}

.new-task-panel__attachments {
  margin-top: var(--spacing-2);
}

.new-task-panel__attachments-header {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
  margin-bottom: var(--spacing-1);
}

.new-task-panel__attachments-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.new-task-panel__attachment {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-1) var(--spacing-2);
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.new-task-panel__attachment-icon {
  color: var(--accent);
  font-size: var(--font-sm);
}

.new-task-panel__attachment-info {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: var(--spacing-2);
}

.new-task-panel__attachment-name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.new-task-panel__attachment-size {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.new-task-panel__attachment-remove {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  transition: all var(--duration-base) var(--ease-out);
}

.new-task-panel__attachment-remove:hover {
  color: var(--error-500);
  background: var(--error-50);
}

.new-task-panel__upload {
  margin-top: var(--spacing-2);
}

.new-task-panel__upload-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--surface-hover);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.new-task-panel__upload-btn:hover {
  background: var(--border);
  border-color: var(--text-tertiary);
}

.new-task-panel__spacer {
  flex: 1;
  min-height: var(--spacing-4);
}

.new-task-panel__footer {
  padding-top: var(--spacing-4);
  border-top: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
}

.new-task-panel__send {
  height: 40px;
  padding: 0 var(--spacing-8);
  border-radius: var(--radius-md);
  border: 1px solid var(--accent);
  background: var(--accent);
  color: white;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
}

.new-task-panel__send:hover:not(:disabled) {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}

.new-task-panel__send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.new-task-panel__sending {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
}

.new-task-panel__spinner {
  animation: new-task-spin 1.2s linear infinite;
}

@keyframes new-task-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
