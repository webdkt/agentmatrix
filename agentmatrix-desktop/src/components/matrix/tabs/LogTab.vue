<template>
  <div class="log-tab">
    <!-- 工具栏 -->
    <div class="log-tab__toolbar">
      <button
        class="log-tab__btn"
        :class="{ 'log-tab__btn--active': autoScroll }"
        @click="autoScroll = !autoScroll"
      >
        {{ $t('matrix.log.autoScroll') }}
      </button>
      <button class="log-tab__btn" @click="refreshLog">
        {{ $t('matrix.log.refresh') }}
      </button>
      <span class="log-tab__info">
        {{ logLines.length }} {{ $t('matrix.log.lines') }}
      </span>
    </div>

    <!-- 日志内容 -->
    <div
      ref="logContainer"
      class="log-tab__content"
      @scroll="handleScroll"
    >
      <div v-if="isLoading" class="log-tab__loading">
        <div class="thinking-bar"></div>
      </div>
      <template v-else>
        <div
          v-for="(line, index) in logLines"
          :key="index"
          class="log-line"
        >
          <span class="log-line__num">{{ index + 1 }}</span>
          <span class="log-line__text" :class="getLineClass(line)">{{ line }}</span>
        </div>
        <div v-if="logLines.length === 0" class="log-tab__empty">
          {{ $t('matrix.log.noLogs') }}
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useMatrixStore } from '../../../stores/matrix'
import { storeToRefs } from 'pinia'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

const matrixStore = useMatrixStore()
const { logContent, isLoadingLog } = storeToRefs(matrixStore)

const logContainer = ref(null)
const autoScroll = ref(true)
const isLoading = ref(false)

const logLines = computed(() => {
  if (!logContent.value) return []
  return logContent.value.split('\n').filter(line => line.trim())
})

// 监听日志内容变化，自动滚动
watch(logLines, async () => {
  if (autoScroll.value) {
    await nextTick()
    scrollToBottom()
  }
})

watch(() => props.agentName, async (newName) => {
  if (newName) {
    isLoading.value = true
    await matrixStore.loadLog(newName)
    isLoading.value = false
    await nextTick()
    scrollToBottom()
  }
}, { immediate: true })

// 定时刷新
let refreshInterval = null
onMounted(() => {
  refreshInterval = setInterval(() => {
    if (props.agentName && autoScroll.value) {
      matrixStore.refreshLog()
    }
  }, 3000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})

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

<style scoped>
.log-tab {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.log-tab__toolbar {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--parchment-300);
  background: var(--parchment-100);
}

.log-tab__btn {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--ink-500);
  background: none;
  border: 1px solid var(--parchment-300);
  padding: 4px 10px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.15s;
}

.log-tab__btn:hover {
  background: var(--parchment-200);
  color: var(--ink-700);
}

.log-tab__btn--active {
  background: var(--accent-muted);
  border-color: var(--accent);
  color: var(--accent);
}

.log-tab__info {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-400);
}

.log-tab__content {
  flex: 1;
  overflow-y: auto;
  background: var(--parchment-100);
  padding: var(--spacing-sm) 0;
}

.log-tab__loading {
  padding: var(--spacing-xl);
}

.thinking-bar {
  height: 2px;
  background: var(--accent);
  animation: thinking 1.5s ease-in-out infinite;
}

@keyframes thinking {
  0% { width: 0; margin-left: 0; }
  50% { width: 60%; margin-left: 20%; }
  100% { width: 0; margin-left: 100%; }
}

.log-line {
  display: flex;
  padding: 0 var(--spacing-md);
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.log-line:hover {
  background: var(--parchment-200);
}

.log-line__num {
  min-width: 40px;
  color: var(--ink-300);
  text-align: right;
  padding-right: var(--spacing-sm);
  user-select: none;
}

.log-line__text {
  flex: 1;
  color: var(--ink-700);
  white-space: pre;
  overflow-x: auto;
}

.log-line__text--error {
  color: var(--fault);
}

.log-line__text--warning {
  color: var(--amber);
}

.log-line__text--info {
  color: var(--verdant);
}

.log-line__text--debug {
  color: var(--ink-400);
}

.log-tab__empty {
  padding: var(--spacing-xl);
  text-align: center;
  color: var(--ink-400);
  font-family: var(--font-serif);
  font-style: italic;
}
</style>
