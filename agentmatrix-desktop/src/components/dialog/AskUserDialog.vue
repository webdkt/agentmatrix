<script setup>
import { ref, watch, computed } from 'vue'
import { useSessionStore } from '@/stores/session'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['close', 'submitted'])

const sessionStore = useSessionStore()

// 当前待处理问题
const currentQuestion = computed(() => {
  if (!sessionStore.currentSession) return null
  return sessionStore.getPendingQuestion(sessionStore.currentSession.session_id)
})

// 回答内容
const answer = ref('')
const isSubmitting = ref(false)

// 监听 show 变化，重置表单
watch(() => props.show, (newValue) => {
  if (newValue) {
    answer.value = ''
  }
})

// 提交回答
const submit = async () => {
  if (!currentQuestion.value || !answer.value.trim()) return

  isSubmitting.value = true
  try {
    await sessionStore.submitAskUserAnswer(
      sessionStore.currentSession.session_id,
      answer.value
    )

    // 标记对话框已显示（防止重复弹出）
    sessionStore.markDialogShown(sessionStore.currentSession.session_id)

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
  // 标记对话框已显示
  if (sessionStore.currentSession) {
    sessionStore.markDialogShown(sessionStore.currentSession.session_id)
  }
  emit('close')
}
</script>

<template>
  <Transition name="modal">
    <div v-if="show && currentQuestion" class="ask-user-dialog-overlay">
      <!-- Overlay -->
      <div class="ask-user-dialog-backdrop" @click="close"></div>

      <!-- Modal Content -->
      <div class="ask-user-dialog-content">
        <!-- Header -->
        <div class="ask-user-dialog-header">
          <div class="ask-user-dialog-header-left">
            <div class="ask-user-dialog-icon">
              <MIcon name="message-circle" />
            </div>
            <div class="ask-user-dialog-header-text">
              <h2 class="ask-user-dialog-title">{{ currentQuestion.agent_name }} 需要你的回答</h2>
              <p class="ask-user-dialog-subtitle">请回答以下问题继续</p>
            </div>
          </div>
          <button
            @click="close"
            class="ask-user-dialog-close"
            type="button"
          >
            <MIcon name="x" />
          </button>
        </div>

        <!-- Body -->
        <div class="ask-user-dialog-body">
          <!-- 问题显示 -->
          <div class="ask-user-dialog-question">
            <p>{{ currentQuestion.question }}</p>
          </div>

          <!-- 回答输入 -->
          <div class="ask-user-dialog-input-group">
            <label class="ask-user-dialog-label">你的回答</label>
            <textarea
              v-model="answer"
              rows="5"
              placeholder="输入你的回答..."
              class="ask-user-dialog-input"
            ></textarea>
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
            :disabled="!answer.trim() || isSubmitting"
            class="ask-user-dialog-btn ask-user-dialog-btn--primary"
            type="button"
          >
            <span v-if="!isSubmitting">提交回答</span>
            <span v-else>提交中...</span>
            <span v-if="isSending" class="animate-spin"><MIcon name="loader" /></span>
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
  padding: var(--spacing-lg);
}

.ask-user-dialog-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(26, 26, 26, 0.3);
}

/* Modal Content */
.ask-user-dialog-content {
  position: relative;
  background: white;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  width: 100%;
  max-width: 540px;
  overflow: hidden;
  animation: dialogScaleIn 200ms ease-out;
}

@keyframes dialogScaleIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

/* Header */
.ask-user-dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--neutral-200);
  background: var(--warning-50);
}

.ask-user-dialog-header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
}

.ask-user-dialog-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  background: var(--warning-100);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--warning-600);
  font-size: 20px;
}

.ask-user-dialog-header-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ask-user-dialog-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0;
}

.ask-user-dialog-subtitle {
  font-size: var(--font-xs);
  color: var(--neutral-500);
  margin: 0;
}

.ask-user-dialog-close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--neutral-400);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
}

.ask-user-dialog-close:hover {
  color: var(--neutral-600);
  background: var(--neutral-100);
}

/* Body */
.ask-user-dialog-body {
  padding: var(--spacing-xl);
}

.ask-user-dialog-question {
  padding: var(--spacing-md);
  background: var(--warning-50);
  border: 1px solid var(--warning-200);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-lg);
}

.ask-user-dialog-question p {
  font-size: var(--font-base);
  color: var(--neutral-900);
  margin: 0;
}

.ask-user-dialog-input-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.ask-user-dialog-label {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
}

.ask-user-dialog-input {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--neutral-50);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  font-size: var(--font-base);
  color: var(--neutral-700);
  resize: none;
  font-family: inherit;
  transition: all var(--duration-base) var(--ease-out);
}

.ask-user-dialog-input:focus {
  outline: none;
  border-color: var(--accent);
}

.ask-user-dialog-input::placeholder {
  color: var(--neutral-400);
}

/* Footer */
.ask-user-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg) var(--spacing-xl);
  border-top: 1px solid var(--neutral-200);
  background: var(--neutral-50);
}

.ask-user-dialog-btn {
  padding: var(--spacing-sm) var(--spacing-lg);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  border: none;
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.ask-user-dialog-btn--secondary {
  background: transparent;
  border: 1px solid var(--neutral-200);
  color: var(--neutral-700);
}

.ask-user-dialog-btn--secondary:hover {
  background: var(--neutral-100);
}

.ask-user-dialog-btn--primary {
  background: var(--accent);
  color: white;
}

.ask-user-dialog-btn--primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.ask-user-dialog-btn--primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Modal transitions */


/* Spin animation */

</style>
