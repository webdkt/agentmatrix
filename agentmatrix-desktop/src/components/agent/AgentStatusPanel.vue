<script setup>
import { computed, ref, watch, nextTick } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useMatrixStore } from '@/stores/matrix'
import MIcon from '@/components/icons/MIcon.vue'
import LogViewerDialog from '@/components/agent/LogViewerDialog.vue'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['close'])

const agentStore = useAgentStore()
const matrixStore = useMatrixStore()
const historyContainer = ref(null)

// Log viewer dialog state
const showLogDialog = ref(false)

// Loading states for control buttons
const isStopping = ref(false)
const isPausingResuming = ref(false)

const agentData = computed(() => agentStore.getAgent(props.agentName))
const agentStatus = computed(() => agentStore.getAgentStatus(props.agentName))

// Agent is paused
const isPaused = computed(() => agentStatus.value === 'PAUSED')

// Can stop: only when WORKING or THINKING
const canStop = computed(() => {
  const status = agentStatus.value
  return ['WORKING', 'THINKING'].includes(status) && !isStopping.value
})

// Can pause/resume: not IDLE or ERROR
const canPauseResume = computed(() => {
  const status = agentStatus.value
  return !['IDLE', 'ERROR'].includes(status) && !isPausingResuming.value
})

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

// Handle Stop
async function handleStop() {
  if (!props.agentName || isStopping.value || !canStop.value) return

  isStopping.value = true
  try {
    await matrixStore.stopAgent(props.agentName)
  } catch (error) {
    console.error('Failed to stop agent:', error)
  } finally {
    isStopping.value = false
  }
}

// Handle Pause/Resume
async function handlePauseResume() {
  if (!props.agentName || isPausingResuming.value || !canPauseResume.value) return

  isPausingResuming.value = true
  try {
    if (isPaused.value) {
      await matrixStore.resumeAgent(props.agentName)
    } else {
      await matrixStore.pauseAgent(props.agentName)
    }
  } catch (error) {
    console.error('Failed to pause/resume agent:', error)
  } finally {
    isPausingResuming.value = false
  }
}

// Handle View Log
function handleViewLog() {
  showLogDialog.value = true
}
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

    <!-- Control Toolbar -->
    <div class="agent-status-panel__toolbar">
      <!-- Stop Button -->
      <button
        class="toolbar-button toolbar-button--stop"
        :class="{ 'toolbar-button--disabled': !canStop }"
        :disabled="!canStop"
        title="Stop Agent"
        @click="handleStop"
      >
        <MIcon name="square" />
      </button>

      <!-- Pause/Resume Button -->
      <button
        class="toolbar-button toolbar-button--pause"
        :class="{ 'toolbar-button--disabled': !canPauseResume }"
        :disabled="!canPauseResume"
        :title="isPaused ? 'Resume Agent' : 'Pause Agent'"
        @click="handlePauseResume"
      >
        <MIcon :name="isPaused ? 'player-play' : 'player-pause'" />
      </button>

      <!-- View Log Button -->
      <button
        class="toolbar-button toolbar-button--log"
        title="View Agent Log"
        @click="handleViewLog"
      >
        <MIcon name="file-text" />
      </button>
    </div>

    <!-- Log Viewer Dialog -->
    <LogViewerDialog
      :show="showLogDialog"
      :agentName="agentName"
      @close="showLogDialog = false"
    />
  </div>
</template>

<style scoped>
.agent-status-panel {
  width: 450px; /* Default width, can be overridden by inline styles */
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

/* Control Toolbar */
.agent-status-panel__toolbar {
  display: flex;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border-top: 1px solid var(--neutral-200);
  background: white;
  flex-shrink: 0;
  justify-content: center;
}

.toolbar-button {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--neutral-300);
  background: white;
  color: var(--ink-600);
  font-size: var(--icon-sm, 14px);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.toolbar-button:hover:not(:disabled) {
  background: var(--neutral-100);
  border-color: var(--neutral-400);
}

.toolbar-button--disabled,
.toolbar-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-button--stop:hover:not(:disabled) {
  background: var(--error-50, #fee2e2);
  border-color: var(--error-300, #fca5a5);
  color: var(--error-600, #dc2626);
}

.toolbar-button--pause:hover:not(:disabled) {
  background: var(--warning-50, #fef3c7);
  border-color: var(--warning-300, #fcd34d);
  color: var(--warning-600, #d97706);
}

.toolbar-button--log:hover:not(:disabled) {
  background: var(--accent-50, #f5e6d3);
  border-color: var(--accent-300, #c9a882);
  color: var(--accent-600, #8b6f47);
}
</style>
