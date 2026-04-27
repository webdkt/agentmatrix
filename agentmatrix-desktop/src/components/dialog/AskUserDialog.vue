<script setup>
import { ref, watch, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  isGlobal: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'submitted'])

const sessionStore = useSessionStore()

// 当前待处理问题
const currentQuestion = computed(() => {
  if (props.isGlobal) {
    return sessionStore.getGlobalPendingQuestion()
  }
  if (!sessionStore.currentSession) return null
  return sessionStore.getPendingQuestion(sessionStore.currentSession.session_id)
})

// 🔧 解析问题对象（支持新格式和旧格式）
const parsedQuestion = computed(() => {
  const q = currentQuestion.value
  if (!q) return null

  // 新格式：包含 question 字段的对象（AskUserQuestion.to_dict()）
  if (typeof q.question === 'object' && q.question !== null) {
    // AskUserQuestion 对象
    return {
      questionText: q.question.question || '',
      options: q.question.options || [],
      multiple: q.question.multiple || false,
      imagePath: q.question.image_path || null
    }
  }

  // 兼容旧格式：纯文本问题
  if (typeof q.question === 'string' && q.question) {
    return {
      questionText: q.question,
      options: [],
      multiple: false,
      imagePath: null
    }
  }

  return null
})

// 回答状态
const selectedOptions = ref([])     // 多选选项
const singleOption = ref('')        // 单选选项
const customAnswer = ref('')        // 自定义输入
const showCustomInput = ref(false)  // 是否显示自定义输入区
const isSubmitting = ref(false)
const imageLoadError = ref(false)   // 图片加载失败

// 监听 show 变化，重置表单
watch(() => props.show, (newValue) => {
  if (newValue) {
    selectedOptions.value = []
    singleOption.value = ''
    customAnswer.value = ''
    showCustomInput.value = false
    imageLoadError.value = false
  }
})

// 🔧 选择单选项
const selectSingleOption = (option) => {
  singleOption.value = option
}

// 🔧 选择多选项
const toggleMultiOption = (option) => {
  const index = selectedOptions.value.indexOf(option)
  if (index > -1) {
    selectedOptions.value.splice(index, 1)
  } else {
    selectedOptions.value.push(option)
  }
}

// 🔧 获取最终回答
const getFinalAnswer = () => {
  // 如果有自定义输入，优先使用自定义输入
  if (customAnswer.value.trim()) {
    return customAnswer.value.trim()
  }

  // 否则使用选项
  if (parsedQuestion.value && parsedQuestion.value.multiple) {
    return selectedOptions.value.join(',')
  } else {
    return singleOption.value
  }
}

// 🔧 检查是否可以提交
const canSubmit = computed(() => {
  if (isSubmitting.value) return false

  const answer = getFinalAnswer()
  return !!answer && answer.trim().length > 0
})

// 🔧 构建图片 URL
const imageUrl = computed(() => {
  if (!currentQuestion.value || !parsedQuestion.value || !parsedQuestion.value.imagePath) {
    return ''
  }

  const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
  return `${baseUrl}/api/agents/${currentQuestion.value.agent_name}/question_image?session_id=${currentQuestion.value.agent_session_id}&filename=${parsedQuestion.value.imagePath}`
})

// 🔧 处理图片加载错误
const handleImageError = () => {
  console.warn('Failed to load question image, session may have changed')
  imageLoadError.value = true
}

// 提交回答
const submit = async () => {
  if (!canSubmit.value) return

  const answer = getFinalAnswer()
  isSubmitting.value = true

  try {
    if (props.isGlobal) {
      await sessionStore.submitGlobalAskUserAnswer(answer)
      sessionStore.markGlobalDialogShown()
    } else {
      await sessionStore.submitAskUserAnswer(
        sessionStore.currentSession.session_id,
        answer
      )
      sessionStore.markDialogShown(sessionStore.currentSession.session_id)
    }

    emit('submitted')
    emit('close')
  } catch (error) {
    alert('提交失败: ' + error.message)
  } finally {
    isSubmitting.value = false
  }
}

// 关闭对话框
const close = () => {
  if (props.isGlobal) {
    sessionStore.markGlobalDialogShown()
  } else {
    if (sessionStore.currentSession) {
      sessionStore.markDialogShown(sessionStore.currentSession.session_id)
    }
  }
  emit('close')
}
</script>

<template>
  <Transition name="modal">
    <div v-if="show && currentQuestion && parsedQuestion" class="ask-user-dialog-overlay">
      <!-- Overlay -->
      <div class="ask-user-dialog-backdrop" @click="close"></div>

      <!-- Modal Content -->
      <div class="ask-user-dialog-content">
        <!-- Close button -->
        <button
          @click="close"
          class="ask-user-dialog-close"
          type="button"
        >
          <MIcon name="x" />
        </button>

        <!-- Body -->
        <div class="ask-user-dialog-body">
          <!-- Header -->
          <div class="ask-user-dialog-header">
            <h2 class="ask-user-dialog-title">
              <template v-if="isGlobal">
                Agent {{ currentQuestion.agent_name }} 有一个临时问题
              </template>
              <template v-else>
                {{ currentQuestion.agent_name }} 需要你的回答
              </template>
            </h2>
            <div class="ask-user-dialog-divider"></div>
          </div>

          <!-- 🔧 图片显示 -->
          <div v-if="parsedQuestion.imagePath && imageUrl" class="ask-user-dialog-image">
            <span class="ask-user-dialog-label">图片</span>
            <img
              v-if="!imageLoadError"
              :src="imageUrl"
              alt="Question Image"
              class="ask-user-dialog-question-image"
              @error="handleImageError"
            />
            <div v-else class="ask-user-dialog-image-error">
              ⚠️ 问题可能已经被回答（或会话已切换）
            </div>
          </div>

          <!-- Question -->
          <div class="ask-user-dialog-question">
            <span class="ask-user-dialog-label">问题</span>
            <p class="ask-user-dialog-question-text">{{ parsedQuestion.questionText }}</p>
          </div>

          <!-- 🔧 选项按钮 -->
          <div v-if="parsedQuestion.options.length > 0" class="ask-user-dialog-options">
            <span class="ask-user-dialog-label">选项</span>

            <!-- 单选按钮 -->
            <div v-if="!parsedQuestion.multiple" class="ask-user-dialog-single-options">
              <button
                v-for="option in parsedQuestion.options"
                :key="option"
                @click="selectSingleOption(option)"
                :class="[
                  'ask-user-dialog-option-btn',
                  'ask-user-dialog-option-btn--single',
                  { 'ask-user-dialog-option-btn--selected': singleOption === option }
                ]"
                type="button"
              >
                {{ option }}
              </button>
            </div>

            <!-- 多选按钮 -->
            <div v-else class="ask-user-dialog-multi-options">
              <button
                v-for="option in parsedQuestion.options"
                :key="option"
                @click="toggleMultiOption(option)"
                :class="[
                  'ask-user-dialog-option-btn',
                  'ask-user-dialog-option-btn--multi',
                  { 'ask-user-dialog-option-btn--selected': selectedOptions.includes(option) }
                ]"
                type="button"
              >
                {{ option }}
              </button>
            </div>
          </div>

          <!-- 🔧 自定义输入区 -->
          <div class="ask-user-dialog-input-group">
            <div class="ask-user-dialog-input-header">
              <label class="ask-user-dialog-input-label">你的回答</label>
              <button
                v-if="parsedQuestion.options.length > 0"
                @click="showCustomInput = !showCustomInput"
                class="ask-user-dialog-toggle-btn"
                type="button"
              >
                {{ showCustomInput ? '隐藏自定义输入' : '或输入自定义回答' }}
              </button>
            </div>

            <div v-show="showCustomInput || parsedQuestion.options.length === 0">
              <textarea
                v-model="customAnswer"
                rows="5"
                placeholder="输入你的回答..."
                class="ask-user-dialog-input"
              ></textarea>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="ask-user-dialog-footer">
          <button
            @click="close"
            class="ask-user-dialog-btn ask-user-dialog-btn--secondary"
            type="button"
          >
            稍后回答
          </button>
          <button
            @click="submit"
            :disabled="!canSubmit || isSubmitting"
            class="ask-user-dialog-btn ask-user-dialog-btn--primary"
            type="button"
          >
            <span v-if="!isSubmitting">提交回答</span>
            <span v-else>提交中...</span>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Overlay */
.ask-user-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-6);
}

.ask-user-dialog-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(26, 26, 26, 0.4);
  backdrop-filter: blur(2px);
}

/* Modal Content */
.ask-user-dialog-content {
  position: relative;
  background: var(--surface-base);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  box-shadow: var(--shadow-xl);
  width: 100%;
  max-width: 540px;
  max-height: 90vh;
  overflow-y: auto;
  animation: dialogScaleIn 200ms ease-out;
}

@keyframes dialogScaleIn {
  from {
    opacity: 0;
    transform: scale(0.96);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Close button */
.ask-user-dialog-close {
  position: absolute;
  top: var(--spacing-4);
  right: var(--spacing-4);
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  z-index: 1;
}

.ask-user-dialog-close:hover {
  color: var(--text-secondary);
  background: var(--surface-secondary);
  border-radius: var(--radius-md);
}

/* Body */
.ask-user-dialog-body {
  padding: var(--spacing-8);
}

/* Header */
.ask-user-dialog-header {
  margin-bottom: var(--spacing-6);
}

.ask-user-dialog-title {
  font-family: var(--font-sans);
  font-size: var(--font-xl);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-4) 0;
  line-height: var(--leading-snug);
}

.ask-user-dialog-divider {
  height: 1px;
  background: var(--border);
  width: 100%;
}

/* 🔧 图片样式 */
.ask-user-dialog-image {
  margin-bottom: var(--spacing-6);
  padding: var(--spacing-4);
  background: var(--surface-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}

.ask-user-dialog-question-image {
  max-width: 100%;
  height: auto;
  border-radius: var(--radius-md);
  margin-top: var(--spacing-2);
  display: block;
}

.ask-user-dialog-image-error {
  padding: var(--spacing-4);
  background: var(--surface-hover);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-align: center;
  font-size: var(--font-sm);
}

/* Question */
.ask-user-dialog-question {
  padding: var(--spacing-4);
  background: var(--surface-secondary);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
  margin-bottom: var(--spacing-6);
}

.ask-user-dialog-label {
  display: block;
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--spacing-1);
  font-weight: var(--font-medium);
}

.ask-user-dialog-question-text {
  font-size: var(--font-base);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.8;
}

/* 🔧 选项按钮样式 */
.ask-user-dialog-options {
  margin-bottom: var(--spacing-6);
}

.ask-user-dialog-single-options,
.ask-user-dialog-multi-options {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  margin-top: var(--spacing-2);
}

.ask-user-dialog-option-btn {
  padding: var(--spacing-4);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-base);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  text-align: left;
  font-size: var(--font-base);
  font-family: var(--font-sans);
  line-height: 1.6;
}

.ask-user-dialog-option-btn:hover {
  background: var(--surface-secondary);
  border-color: var(--border);
}

.ask-user-dialog-option-btn--selected {
  background: var(--accent);
  color: var(--surface-base);
  border-color: var(--accent);
}

.ask-user-dialog-option-btn--multi {
  position: relative;
  padding-left: calc(var(--spacing-4) + 24px);
}

.ask-user-dialog-option-btn--multi::before {
  content: '☐';
  position: absolute;
  left: var(--spacing-4);
  top: 50%;
  transform: translateY(-50%);
  font-size: 18px;
}

.ask-user-dialog-option-btn--multi.ask-user-dialog-option-btn--selected::before {
  content: '☑';
}

/* Input Group */
.ask-user-dialog-input-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.ask-user-dialog-input-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-2);
}

.ask-user-dialog-input-label {
  font-size: var(--font-xs);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.ask-user-dialog-toggle-btn {
  background: transparent;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: var(--font-sm);
  padding: 0;
  text-decoration: underline;
  transition: color var(--duration-base) var(--ease-out);
}

.ask-user-dialog-toggle-btn:hover {
  color: var(--text-primary);
}

.ask-user-dialog-input {
  width: 100%;
  padding: var(--spacing-4) 0;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--border);
  font-size: var(--font-base);
  color: var(--text-secondary);
  resize: none;
  font-family: var(--font-sans);
  line-height: 1.8;
  transition: border-color var(--duration-base) var(--ease-out);
}

.ask-user-dialog-input:focus {
  outline: none;
  border-bottom-color: var(--accent);
  border-bottom-width: 2px;
}

.ask-user-dialog-input::placeholder {
  color: var(--text-tertiary);
  font-style: italic;
}

/* Footer */
.ask-user-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-4);
  padding: var(--spacing-6) var(--spacing-8);
  border-top: 1px solid var(--border);
  background: var(--surface-secondary);
}

/* Buttons */
.ask-user-dialog-btn {
  padding: var(--spacing-2) var(--spacing-6);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
}

.ask-user-dialog-btn--secondary {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-secondary);
}

.ask-user-dialog-btn--secondary:hover {
  background: var(--surface-hover);
  border-color: var(--border);
}

.ask-user-dialog-btn--primary {
  background: var(--accent);
  color: var(--surface-base);
}

.ask-user-dialog-btn--primary:hover:not(:disabled) {
  background: var(--accent);
}

.ask-user-dialog-btn--primary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 200ms var(--ease-out);
}

.modal-enter-active .ask-user-dialog-content,
.modal-leave-active .ask-user-dialog-content {
  transition: all 200ms var(--ease-out);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .ask-user-dialog-content,
.modal-leave-to .ask-user-dialog-content {
  opacity: 0;
  transform: scale(0.96);
}
</style>
