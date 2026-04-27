<script setup>
import { computed, ref, watch } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'
import { useMatrixStore } from '@/stores/matrix'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  agentName: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['close'])

const matrixStore = useMatrixStore()
const isLoading = ref(false)
const promptContent = ref('')
const error = ref(null)

// 监听 show 变化，加载 prompt
watch(() => props.show, async (newVal) => {
  if (newVal && props.agentName) {
    isLoading.value = true
    error.value = null
    try {
      promptContent.value = await matrixStore.loadAgentPrompt(props.agentName)
    } catch (e) {
      error.value = e.message || 'Failed to load prompt'
    } finally {
      isLoading.value = false
    }
  }
}, { immediate: true })

const close = () => {
  emit('close')
}

const handleOverlayClick = () => {
  close()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="prompt-modal">
        <!-- Overlay -->
        <div class="prompt-modal__overlay" @click="handleOverlayClick"></div>

        <!-- Modal Content -->
        <div class="prompt-modal__content">
          <!-- Header -->
          <div class="prompt-modal__header">
            <div class="prompt-modal__title-group">
              <MIcon name="terminal" class="prompt-modal__icon" />
              <h2 class="prompt-modal__title">
                System Prompt: {{ agentName }}
              </h2>
            </div>
            <button @click="close" class="prompt-modal__close">
              <MIcon name="x" />
            </button>
          </div>

          <!-- Content -->
          <div class="prompt-modal__body">
            <!-- Loading State -->
            <div v-if="isLoading" class="prompt-modal__loading">
              <div class="thinking-bar"></div>
              <span>Loading prompt...</span>
            </div>

            <!-- Error State -->
            <div v-else-if="error" class="prompt-modal__error">
              <MIcon name="alert-circle" />
              <span>{{ error }}</span>
            </div>

            <!-- Prompt Content -->
            <div v-else class="prompt-modal__prompt">
              <pre class="prompt-modal__text">{{ promptContent }}</pre>
            </div>
          </div>

          <!-- Footer -->
          <div class="prompt-modal__footer">
            <button @click="close" class="prompt-modal__btn">
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.prompt-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.prompt-modal__overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(2px);
}

.prompt-modal__content {
  position: relative;
  width: 90vw;
  max-width: 900px;
  height: 80vh;
  max-height: 700px;
  background: var(--surface-secondary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.prompt-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-base);
}

.prompt-modal__title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.prompt-modal__icon {
  color: var(--accent);
  font-size: 18px;
}

.prompt-modal__title {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.prompt-modal__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-tertiary);
  transition: all 0.15s ease;
}

.prompt-modal__close:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.prompt-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.prompt-modal__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 100%;
  color: var(--text-tertiary);
  font-family: var(--font-sans);
  font-size: 14px;
}

.thinking-bar {
  width: 120px;
  height: 2px;
  background: var(--accent);
  animation: thinking 1.5s ease-in-out infinite;
}

@keyframes thinking {
  0% { width: 0; margin-left: 0; }
  50% { width: 60%; margin-left: 20%; }
  100% { width: 0; margin-left: 100%; }
}

.prompt-modal__error {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 100%;
  color: var(--error);
  font-family: var(--font-sans);
  font-size: 14px;
}

.prompt-modal__prompt {
  padding: 20px;
  height: 100%;
}

.prompt-modal__text {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  background: var(--surface-base);
  padding: 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border);
}

.prompt-modal__footer {
  display: flex;
  justify-content: flex-end;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  background: var(--surface-base);
}

.prompt-modal__btn {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: white;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.prompt-modal__btn:hover {
  background: var(--surface-secondary);
  border-color: var(--border);
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.fade-enter-active .prompt-modal__content,
.fade-leave-active .prompt-modal__content {
  transition: transform 0.2s ease;
}

.fade-enter-from .prompt-modal__content,
.fade-leave-to .prompt-modal__content {
  transform: scale(0.95) translateY(10px);
}
</style>
