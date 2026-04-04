<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useAgentStore } from '@/stores/agent'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['close'])

const agentStore = useAgentStore()
const historyContainer = ref(null)

const agentData = computed(() => agentStore.getAgent(props.agentName))
const agentStatus = computed(() => agentStore.getAgentStatus(props.agentName))

const statusHistory = computed(() => {
  if (!agentData.value?.status_history) return []
  return agentData.value.status_history
})

// Format timestamp
const formatTime = (ts) => {
  if (!ts) return ''
  const date = new Date(ts)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// Auto-scroll to bottom when new entries arrive
watch(() => statusHistory.value.length, async () => {
  await nextTick()
  if (historyContainer.value) {
    historyContainer.value.scrollTop = historyContainer.value.scrollHeight
  }
})
</script>

<template>
  <div class="agent-status-panel">
    <header class="agent-status-panel__header">
      <div class="agent-status-panel__title">
        <span class="agent-status-panel__name">{{ agentName }}</span>
        <span class="agent-status-panel__status">{{ agentStatus }}</span>
      </div>
      <button class="agent-status-panel__close" @click="emit('close')">
        <MIcon name="close" />
      </button>
    </header>

    <div ref="historyContainer" class="agent-status-panel__body">
      <div v-if="statusHistory.length === 0" class="agent-status-panel__empty">
        <p>No status history</p>
      </div>

      <div
        v-for="(entry, index) in statusHistory"
        :key="index"
        class="agent-status-panel__entry"
      >
        <span class="agent-status-panel__entry-time">{{ formatTime(entry.timestamp) }}</span>
        <span class="agent-status-panel__entry-message">{{ entry.message }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-status-panel {
  width: 300px;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--parchment-50);
  border-left: 1px solid var(--neutral-200);
  flex-shrink: 0;
}

.agent-status-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md) var(--spacing-md);
  border-bottom: 1px solid var(--neutral-200);
  background: white;
  flex-shrink: 0;
}

.agent-status-panel__title {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.agent-status-panel__name {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--ink-700);
}

.agent-status-panel__status {
  font-size: var(--font-xs);
  color: var(--ink-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.agent-status-panel__close {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: none;
  background: transparent;
  color: var(--neutral-500);
  font-size: var(--icon-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-base) var(--ease-out);
}

.agent-status-panel__close:hover {
  background: var(--neutral-100);
  color: var(--neutral-700);
}

.agent-status-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-sm);
}

.agent-status-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--neutral-400);
  font-size: var(--font-sm);
}

.agent-status-panel__entry {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: background var(--duration-base) var(--ease-out);
}

.agent-status-panel__entry:hover {
  background: rgba(0, 0, 0, 0.03);
}

.agent-status-panel__entry-time {
  font-size: var(--font-xs);
  color: var(--ink-400);
  font-variant-numeric: tabular-nums;
}

.agent-status-panel__entry-message {
  font-size: var(--font-sm);
  color: var(--ink-600);
  line-height: var(--leading-normal);
}
</style>
