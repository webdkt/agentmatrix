<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'
import { useMatrixStore } from '@/stores/matrix'
import { storeToRefs } from 'pinia'

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
const { logContent, isLoadingLog } = storeToRefs(matrixStore)

const logContainer = ref(null)
const autoScroll = ref(true)
const isLoading = ref(false)

const logLines = computed(() => {
  if (!logContent.value) return []
  return logContent.value.split('\n').filter(line => line.trim())
})

// 监听 show 变化，加载日志
watch(() => props.show, async (newVal) => {
  if (newVal && props.agentName) {
    isLoading.value = true
    await matrixStore.loadLog(props.agentName)
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}, { immediate: true })

// 监听日志内容变化，自动滚动
watch(logLines, async () => {
  if (autoScroll.value && props.show) {
    await nextTick()
    scrollToBottom()
  }
})

// 定时刷新
let refreshInterval = null
onMounted(() => {
  refreshInterval = setInterval(() => {
    if (props.show && props.agentName && autoScroll.value) {
      matrixStore.refreshLog()
    }
  }, 3000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

const close = () => {
  emit('close')
}

const handleOverlayClick = () => {
  close()
}

async function refreshLog() {
  isLoading.value = true
  await matrixStore.refreshLog()
  isLoading.value = false
}

function scrollToBottom() {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
}

function handleScroll() {
  if (!logContainer.value) return
  const { scrollTop, scrollHeight, clientHeight } = logContainer.value
  // 如果用户手动滚动到非底部，关闭自动滚动
  if (scrollHeight - scrollTop - clientHeight > 50) {
    autoScroll.value = false
  }
}

function getLineClass(line) {
  if (line.includes('ERROR') || line.includes('❌')) return 'log-line__text--error'
  if (line.includes('WARNING') || line.includes('⚠️')) return 'log-line__text--warning'
  if (line.includes('INFO') || line.includes('✅')) return 'log-line__text--info'
  if (line.includes('DEBUG')) return 'log-line__text--debug'
  return ''
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="log-modal">
        <!-- Overlay -->
        <div class="log-modal__overlay" @click="handleOverlayClick"></div>

        <!-- Modal Content -->
        <div class="log-modal__content">
          <!-- Header -->
          <div class="log-modal__header">
            <div class="log-modal__title-group">
              <MIcon name="file-text" class="log-modal__icon" />
              <h2 class="log-modal__title">
                Agent Log: {{ agentName }}
              </h2>
            </div>
            <button @click="close" class="log-modal__close">
              <MIcon name="x" />
            </button>
          </div>

          <!-- Toolbar -->
          <div class="log-modal__toolbar">
            <button
              class="log-modal__btn"
              :class="{ 'log-modal__btn--active': autoScroll }"
              @click="autoScroll = !autoScroll"
            >
              Auto Scroll
            </button>
            <button class="log-modal__btn" @click="refreshLog">
              Refresh
            </button>
            <span class="log-modal__info">
              {{ logLines.length }} lines
            </span>
          </div>

          <!-- Content -->
          <div class="log-modal__body">
            <!-- Loading State -->
            <div v-if="isLoading" class="log-modal__loading">
              <div class="thinking-bar"></div>
              <span>Loading logs...</span>
            </div>

            <!-- Log Content -->
            <div v-else>
              <div
                ref="logContainer"
                class="log-modal__log-content"
                @scroll="handleScroll"
              >
                <div
                  v-for="(line, index) in logLines"
                  :key="index"
                  class="log-line"
                >
                  <span class="log-line__num">{{ index + 1 }}</span>
                  <span class="log-line__text" :class="getLineClass(line)">{{ line }}</span>
                </div>
                <div v-if="logLines.length === 0" class="log-modal__empty">
                  No logs available
                </div>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="log-modal__footer">
            <button @click="close" class="log-modal__btn">
              Close
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.log-modal {
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

.log-modal__overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(2px);
}

.log-modal__content {
  position: relative;
  width: 90vw;
  max-width: 1000px;
  height: 80vh;
  max-height: 700px;
  background: var(--surface-secondary);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.log-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-base);
}

.log-modal__title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.log-modal__icon {
  color: var(--accent);
  font-size: 18px;
}

.log-modal__title {
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.log-modal__close {
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

.log-modal__close:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.log-modal__toolbar {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  background: var(--surface-secondary);
}

.log-modal__btn {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--text-tertiary);
  background: none;
  border: 1px solid var(--border);
  padding: 4px 10px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease;
}

.log-modal__btn:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.log-modal__btn--active {
  background: var(--accent-muted);
  border-color: var(--accent);
  color: var(--accent);
}

.log-modal__info {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
}

.log-modal__body {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0;
}

.log-modal__loading {
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

.log-modal__log-content {
  flex: 1;
  overflow-y: auto;
  background: var(--surface-secondary);
  padding: var(--spacing-2) 0;
}

.log-line {
  display: flex;
  padding: 0 var(--spacing-4);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  min-width: 0;
}

.log-line:hover {
  background: var(--surface-hover);
}

.log-line__num {
  min-width: 40px;
  color: var(--text-quaternary);
  text-align: right;
  padding-right: var(--spacing-2);
  user-select: none;
}

.log-line__text {
  flex: 1;
  min-width: 0;
  color: var(--text-secondary);
  white-space: pre;
  overflow-x: auto;
}

.log-line__text--error {
  color: var(--error);
}

.log-line__text--warning {
  color: var(--amber);
}

.log-line__text--info {
  color: var(--success);
}

.log-line__text--debug {
  color: var(--text-tertiary);
}

.log-modal__empty {
  padding: var(--spacing-8);
  text-align: center;
  color: var(--text-tertiary);
  font-family: var(--font-sans);
  font-style: italic;
}

.log-modal__footer {
  display: flex;
  justify-content: flex-end;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  background: var(--surface-base);
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

.fade-enter-active .log-modal__content,
.fade-leave-active .log-modal__content {
  transition: transform 0.2s ease;
}

.fade-enter-from .log-modal__content,
.fade-leave-to .log-modal__content {
  transform: scale(0.95) translateY(10px);
}
</style>
