<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { agentAPI } from '@/api/agent'
import { sessionAPI } from '@/api/session'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'sent'])

// 状态
const agents = ref([])
const agentSearchQuery = ref('')
const showAgentDropdown = ref(false)
const selectedAgent = ref(null)
const messageBody = ref('')
const attachments = ref([])
const isSending = ref(false)
const isLoadingAgents = ref(false)

// 计算属性
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
  return selectedAgent.value && messageBody.value.trim() && !isSending.value
})

// 生命周期
onMounted(async () => {
  await loadAgents()
})

// 监听 show 变化，重置表单
watch(() => props.show, (newValue) => {
  if (newValue) {
    resetForm()
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

// 处理文件拖放
const handleFileDrop = (event) => {
  event.preventDefault()
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
const sendEmail = async () => {
  if (!canSend.value) return

  isSending.value = true
  try {
    // 🔑 关键修复：明确设置不传递 in_reply_to
    // 新建会话时不应该有 in_reply_to 字段
    const emailData = {
      recipient: selectedAgent.value.name,
      subject: '',
      body: messageBody.value
    }

    // 明确设置为 undefined（虽然不设置也可以，但为了保险）
    emailData.in_reply_to = undefined
    emailData.task_id = undefined

    console.log('📤 Sending new email with data:', emailData)

    // 直接调用 sendEmail API，sessionId 传 'new'
    const result = await sessionAPI.sendEmail('new', emailData, attachments.value)

    console.log('✅ Email sent successfully:', result)

    // 成功
    emit('sent', result)
    emit('close')
  } catch (error) {
    console.error('❌ Failed to send email:', error)
    alert('Failed to send email: ' + error.message)
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
    <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center">
      <!-- Overlay -->
      <div class="absolute inset-0 bg-surface-900/40 backdrop-blur-sm" @click="close"></div>

      <!-- Modal Content -->
      <div class="relative bg-white rounded-2xl shadow-elevated w-full max-w-2xl mx-4 overflow-hidden animate-scale-in">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-surface-100 flex items-center justify-between bg-surface-50/50">
          <h2 class="text-lg font-semibold text-surface-900 tracking-tight">New Session</h2>
          <button
            @click="close"
            class="w-8 h-8 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100 flex items-center justify-center transition-all duration-200 btn-press"
          >
            <i class="ti ti-x text-xl"></i>
          </button>
        </div>

        <!-- Form -->
        <div class="p-6 space-y-4">
          <!-- Recipient -->
          <div class="relative">
            <label class="block text-sm font-medium text-surface-700 mb-2">To</label>
            <div class="relative">
              <i class="ti ti-at absolute left-3 top-1/2 -translate-y-1/2 text-surface-400"></i>
              <input
                v-model="agentSearchQuery"
                @focus="showAgentDropdown = true"
                placeholder="Search for an agent..."
                class="w-full pl-10 pr-4 py-3 bg-surface-50 border border-surface-200 rounded-xl text-surface-700 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-300 transition-all duration-200"
              />

              <!-- Clear button -->
              <button
                v-if="selectedAgent"
                @click="clearAgent"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
              >
                <i class="ti ti-x"></i>
              </button>
            </div>

            <!-- Dropdown -->
            <div
              v-show="showAgentDropdown && (filteredAgents.length > 0 || agentSearchQuery)"
              class="absolute z-10 w-full mt-1 bg-white border border-surface-200 rounded-xl shadow-elevated max-h-48 overflow-y-auto"
            >
              <div
                v-for="agent in filteredAgents"
                :key="agent.name"
                @click="selectAgent(agent)"
                class="px-4 py-3 hover:bg-surface-50 cursor-pointer text-sm text-surface-700 transition-all duration-150"
              >
                <div class="font-medium">{{ agent.name }}</div>
                <div class="text-xs text-surface-400 truncate">{{ agent.description || 'No description' }}</div>
              </div>

              <div
                v-if="filteredAgents.length === 0"
                class="px-4 py-3 text-surface-400 text-sm"
              >
                No agents found
              </div>
            </div>
          </div>

          <!-- Message -->
          <div>
            <label class="block text-sm font-medium text-surface-700 mb-2">Message</label>
            <textarea
              v-model="messageBody"
              rows="8"
              placeholder="Type your message..."
              class="w-full px-4 py-3 bg-surface-50 border border-surface-200 rounded-xl text-surface-700 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-300 transition-all duration-200 resize-none"
            ></textarea>
          </div>

          <!-- Attachments -->
          <div>
            <label class="block text-sm font-medium text-surface-700 mb-2">Attachments</label>

            <!-- Drop Zone -->
            <div
              @dragenter.prevent
              @dragover.prevent
              @drop="handleFileDrop"
              @click="$refs.fileInput.click()"
              class="border-2 border-dashed border-surface-200 rounded-xl p-6 text-center hover:border-primary-300 hover:bg-primary-50/30 transition-all duration-200 cursor-pointer"
            >
              <input
                ref="fileInput"
                type="file"
                @change="handleFileSelect"
                multiple
                class="hidden"
                accept="*/*"
              >
              <i class="ti ti-upload text-3xl text-surface-400 mb-2"></i>
              <p class="text-sm text-surface-600 mb-1">
                <span class="font-medium text-primary-600">Click to upload</span> or drag and drop
              </p>
              <p class="text-xs text-surface-400">Any file type supported</p>
            </div>

            <!-- Attachment List -->
            <div v-if="attachments.length > 0" class="mt-3 space-y-2">
              <div
                v-for="(file, index) in attachments"
                :key="index"
                class="flex items-center justify-between p-3 bg-surface-50 rounded-lg border border-surface-200 hover:border-surface-300 transition-all duration-150"
              >
                <div class="flex items-center gap-3 flex-1 min-w-0">
                  <div class="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center flex-shrink-0">
                    <i class="ti ti-file text-primary-600"></i>
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-surface-700 truncate">{{ file.name }}</p>
                    <p class="text-xs text-surface-400">{{ formatFileSize(file.size) }}</p>
                  </div>
                </div>
                <button
                  @click="removeAttachment(index)"
                  class="ml-2 w-8 h-8 rounded-lg text-surface-400 hover:text-red-500 hover:bg-red-50 flex items-center justify-center transition-all duration-150 flex-shrink-0"
                >
                  <i class="ti ti-x"></i>
                </button>
              </div>
            </div>

            <!-- Attachment Count -->
            <div v-if="attachments.length > 0" class="mt-2 text-xs text-surface-400 text-center">
              {{ attachments.length }} file(s) selected
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-surface-100 flex justify-end gap-3 bg-surface-50/50">
          <button
            @click="close"
            class="px-6 py-2.5 border border-surface-200 rounded-xl text-surface-700 font-medium hover:bg-surface-100 transition-all duration-200 btn-press"
          >
            Cancel
          </button>
          <button
            @click="sendEmail"
            :disabled="!canSend"
            class="px-6 py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 transition-all duration-200 btn-press shadow-glow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <span v-if="!isSending">Send</span>
            <span v-else>Sending...</span>
            <i v-if="isSending" class="ti ti-loader animate-spin"></i>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
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

/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

/* Scale in animation */
@keyframes scaleIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.animate-scale-in {
  animation: scaleIn 0.2s ease-out;
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
