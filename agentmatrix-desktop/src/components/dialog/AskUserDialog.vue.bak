<script setup>
import { ref, watch, computed } from 'vue'
import { useSessionStore } from '@/stores/session'

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
    <div v-if="show && currentQuestion" class="fixed inset-0 z-50 flex items-center justify-center">
      <!-- Overlay -->
      <div class="absolute inset-0 bg-surface-900/40 backdrop-blur-sm" @click="close"></div>

      <!-- Modal Content -->
      <div class="relative bg-white rounded-2xl shadow-elevated w-full max-w-lg mx-4 overflow-hidden animate-scale-in">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-surface-100 flex items-center justify-between bg-amber-50/50">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
              <i class="ti ti-message-circle text-amber-600 text-xl"></i>
            </div>
            <div>
              <h2 class="text-lg font-semibold text-surface-900">{{ currentQuestion.agent_name }} 需要你的回答</h2>
              <p class="text-xs text-surface-500">请回答以下问题继续</p>
            </div>
          </div>
          <button
            @click="close"
            class="w-8 h-8 rounded-lg text-surface-400 hover:text-surface-600 hover:bg-surface-100 flex items-center justify-center transition-all duration-200"
          >
            <i class="ti ti-x text-xl"></i>
          </button>
        </div>

        <!-- Body -->
        <div class="p-6">
          <!-- 问题显示 -->
          <div class="mb-4 p-4 bg-amber-50 rounded-xl border border-amber-200">
            <p class="text-surface-900">{{ currentQuestion.question }}</p>
          </div>

          <!-- 回答输入 -->
          <div>
            <label class="block text-sm font-medium text-surface-700 mb-2">你的回答</label>
            <textarea
              v-model="answer"
              rows="5"
              placeholder="输入你的回答..."
              class="w-full px-4 py-3 bg-surface-50 border border-surface-200 rounded-xl text-surface-700 placeholder-surface-400 focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-300 transition-all duration-200 resize-none"
            ></textarea>
          </div>
        </div>

        <!-- Footer -->
        <div class="px-6 py-4 border-t border-surface-100 flex justify-end gap-3 bg-surface-50/50">
          <button
            @click="close"
            class="px-6 py-2.5 border border-surface-200 rounded-xl text-surface-700 font-medium hover:bg-surface-100 transition-all duration-200"
          >
            稍后回答
          </button>
          <button
            @click="submit"
            :disabled="!answer.trim() || isSubmitting"
            class="px-6 py-2.5 bg-primary-600 text-white rounded-xl font-medium hover:bg-primary-700 transition-all duration-200 shadow-glow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            <span v-if="!isSubmitting">提交回答</span>
            <span v-else>提交中...</span>
            <i v-if="isSubmitting" class="ti ti-loader animate-spin"></i>
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
