<template>
  <div class="memory-tab">
    <div v-if="isLoading" class="memory-tab__loading">
      <div class="thinking-bar"></div>
    </div>

    <div v-else-if="sessions.length > 0" class="memory-tab__content">
      <!-- Session 列表 -->
      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.session_id"
          class="session-item"
        >
          <div class="session-item__header">
            <span class="session-item__subject">{{ session.subject || '(no subject)' }}</span>
            <span class="session-item__time">{{ formatTime(session.last_email_time) }}</span>
          </div>
          <div class="session-item__meta">
            <span class="session-item__id">{{ truncateId(session.session_id) }}</span>
            <span class="session-item__participants">
              {{ session.participants?.join(', ') || '' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="memory-tab__empty">
      <div class="memory-tab__empty-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>
      </div>
      <div class="memory-tab__empty-text">{{ $t('matrix.memory.noSessions') }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useMatrixStore } from '@/stores/matrix'
import { storeToRefs } from 'pinia'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

const matrixStore = useMatrixStore()
const { sessions, isLoadingSessions } = storeToRefs(matrixStore)

const isLoading = ref(false)

watch(() => props.agentName, async (newName) => {
  if (newName) {
    isLoading.value = true
    await matrixStore.loadSessions(newName)
    isLoading.value = false
  }
}, { immediate: true })

function formatTime(timestamp) {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const now = new Date()
  const diff = now - date

  // 小于 1 小时
  if (diff < 3600000) {
    const mins = Math.floor(diff / 60000)
    return `${mins}m ago`
  }
  // 小于 24 小时
  if (diff < 86400000) {
    const hours = Math.floor(diff / 3600000)
    return `${hours}h ago`
  }
  // 超过 24 小时
  return date.toLocaleDateString()
}

function truncateId(id) {
  if (!id) return ''
  return id.substring(0, 8) + '...'
}
</script>

<style scoped>
.memory-tab {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--spacing-4);
}

.memory-tab__loading {
  padding: var(--spacing-8);
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

.session-list {
  display: flex;
  flex-direction: column;
}

.session-item {
  padding: var(--spacing-4);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  transition: background-color 0.15s;
}

.session-item:hover {
  background: var(--surface-hover);
}

.session-item__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 4px;
}

.session-item__subject {
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--text-primary);
  flex: 1;
  margin-right: var(--spacing-4);
}

.session-item__time {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.session-item__meta {
  display: flex;
  gap: var(--spacing-4);
  font-size: 12px;
  color: var(--text-tertiary);
}

.session-item__id {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-tertiary);
}

.session-item__participants {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--text-tertiary);
}

.memory-tab__empty {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
}

.memory-tab__empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: var(--spacing-4);
  color: var(--text-quaternary);
}

.memory-tab__empty-text {
  font-family: var(--font-sans);
  font-size: 14px;
  font-style: italic;
}
</style>
