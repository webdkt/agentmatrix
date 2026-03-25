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
            <h2 class="ask-user-dialog-title">{{ currentQuestion.agent_name }} 需要你的回答</h2>
            <div class="ask-user-dialog-divider"></div>
          </div>

          <!-- Question -->
          <div class="ask-user-dialog-question">
            <span class="ask-user-dialog-label">问题</span>
            <p class="ask-user-dialog-question-text">{{ currentQuestion.question }}</p>
          </div>

          <!-- Answer Input -->
          <div class="ask-user-dialog-input-group">
            <label class="ask-user-dialog-input-label">你的回答</label>
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
  background: rgba(26, 26, 26, 0.4);
  backdrop-filter: blur(2px);
}

/* Modal Content */
.ask-user-dialog-content {
  position: relative;
  background: var(--parchment-50);
  border-radius: var(--radius-sm);
  border: 1px solid var(--parchment-300);
  box-shadow: var(--shadow-xl);
  width: 100%;
  max-width: 540px;
  overflow: hidden;
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
  top: var(--spacing-md);
  right: var(--spacing-md);
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--ink-400);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  z-index: 1;
}

.ask-user-dialog-close:hover {
  color: var(--ink-700);
  background: var(--parchment-100);
  border-radius: var(--radius-sm);
}

/* Body */
.ask-user-dialog-body {
  padding: var(--spacing-xl);
}

/* Header */
.ask-user-dialog-header {
  margin-bottom: var(--spacing-lg);
}

.ask-user-dialog-title {
  font-family: var(--font-serif);
  font-size: var(--font-xl);
  font-weight: var(--font-medium);
  color: var(--ink-900);
  margin: 0 0 var(--spacing-md) 0;
  line-height: var(--leading-snug);
}

.ask-user-dialog-divider {
  height: 1px;
  background: var(--parchment-300);
  width: 100%;
}

/* Question */
.ask-user-dialog-question {
  padding: var(--spacing-md);
  background: var(--parchment-100);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  margin-bottom: var(--spacing-lg);
}

.ask-user-dialog-label {
  display: block;
  font-size: 11px;
  font-variant: small-caps;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-500);
  margin-bottom: var(--spacing-xs);
  font-weight: var(--font-medium);
}

.ask-user-dialog-question-text {
  font-size: var(--font-base);
  color: var(--ink-700);
  margin: 0;
  line-height: 1.8;
}

/* Input Group */
.ask-user-dialog-input-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.ask-user-dialog-input-label {
  font-size: 11px;
  font-variant: small-caps;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-700);
  font-weight: var(--font-medium);
}

.ask-user-dialog-input {
  width: 100%;
  padding: var(--spacing-md) 0;
  background: transparent;
  border: none;
  border-bottom: 1px solid var(--parchment-300);
  font-size: var(--font-base);
  color: var(--ink-700);
  resize: none;
  font-family: var(--font-serif);
  line-height: 1.8;
  transition: border-color var(--duration-base) var(--ease-out);
}

.ask-user-dialog-input:focus {
  outline: none;
  border-bottom-color: var(--accent);
  border-bottom-width: 2px;
}

.ask-user-dialog-input::placeholder {
  color: var(--ink-400);
  font-style: italic;
}

/* Footer */
.ask-user-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-md);
  padding: var(--spacing-lg) var(--spacing-xl);
  border-top: 1px solid var(--parchment-300);
  background: var(--parchment-100);
}

/* Buttons */
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
  letter-spacing: 0.05em;
}

.ask-user-dialog-btn--secondary {
  background: transparent;
  border: 1px solid var(--parchment-300);
  color: var(--ink-700);
}

.ask-user-dialog-btn--secondary:hover {
  background: var(--parchment-200);
  border-color: var(--parchment-300);
}

.ask-user-dialog-btn--primary {
  background: var(--ink-900);
  color: var(--parchment-50);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 11px;
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
