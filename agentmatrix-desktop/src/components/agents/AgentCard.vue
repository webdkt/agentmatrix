<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAgentStore } from '@/stores/agent'
import { useMatrixStore } from '@/stores/matrix'
import MIcon from '@/components/icons/MIcon.vue'
import AgentStatusIcon from '@/components/agent/AgentStatusIcon.vue'
import AgentStatusHistory from '@/components/agent/AgentStatusHistory.vue'
import PromptPreviewModal from '@/components/dialog/PromptPreviewModal.vue'

const props = defineProps({
  agent: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['click', 'new-message'])

const { t } = useI18n()
const agentStore = useAgentStore()
const matrixStore = useMatrixStore()

// Modal state
const showPromptModal = ref(false)

// Loading states
const isStopping = ref(false)
const isPausingResuming = ref(false)

// Get agent status from store
const agentStatus = computed(() => agentStore.getAgentStatus(props.agent.name))

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

// Handle card click (but not control buttons)
const handleCardClick = (event) => {
  if (event.target.closest('.control-button') || event.target.closest('.new-message-button')) {
    return
  }
  emit('click')
}

// Handle new message button
const handleNewMessage = (event) => {
  event.stopPropagation()
  emit('new-message')
}

// Handle Stop
async function handleStop(event) {
  event.stopPropagation()
  if (!props.agent.name || isStopping.value || !canStop.value) return

  isStopping.value = true
  try {
    await matrixStore.stopAgent(props.agent.name)
  } catch (error) {
    console.error('Failed to stop agent:', error)
  } finally {
    isStopping.value = false
  }
}

// Handle Pause/Resume
async function handlePauseResume(event) {
  event.stopPropagation()
  if (!props.agent.name || isPausingResuming.value || !canPauseResume.value) return

  isPausingResuming.value = true
  try {
    if (isPaused.value) {
      await matrixStore.resumeAgent(props.agent.name)
    } else {
      await matrixStore.pauseAgent(props.agent.name)
    }
  } catch (error) {
    console.error('Failed to pause/resume agent:', error)
  } finally {
    isPausingResuming.value = false
  }
}

// Handle Reload (placeholder)
function handleReload(event) {
  event.stopPropagation()
  console.log('Reload not implemented yet')
}

// Handle View Prompt
function handleViewPrompt(event) {
  event.stopPropagation()
  showPromptModal.value = true
}
</script>

<template>
  <div class="agent-card" @click="handleCardClick">
    <!-- Header -->
    <div class="agent-card__header">
      <div class="agent-card__info">
        <h3 class="agent-card__name">{{ agent.name }}</h3>
        <p class="agent-card__description">{{ agent.description || 'No description available' }}</p>
      </div>
      <div class="agent-card__status-icon">
        <AgentStatusIcon :agent-name="agent.name" />
      </div>
    </div>
    
    <!-- Status History Section -->
    <div class="agent-card__status">
      <AgentStatusHistory :agent-name="agent.name" />
    </div>
    
    <!-- Control Buttons -->
    <div class="agent-card__controls">
      <!-- View Prompt Button -->
      <button
        class="control-button control-button--prompt"
        :title="t('agents.viewPrompt')"
        @click="handleViewPrompt"
      >
        <MIcon name="terminal" />
      </button>

      <!-- Stop Button -->
      <button
        class="control-button control-button--stop"
        :class="{ 'control-button--disabled': !canStop }"
        :disabled="!canStop"
        :title="t('agents.stop')"
        @click="handleStop"
      >
        <MIcon name="square" />
      </button>
      
      <!-- Pause/Resume Button -->
      <button
        class="control-button control-button--pause"
        :class="{ 'control-button--disabled': !canPauseResume }"
        :disabled="!canPauseResume"
        :title="isPaused ? t('agents.resume') : t('agents.pause')"
        @click="handlePauseResume"
      >
        <MIcon :name="isPaused ? 'player-play' : 'player-pause'" />
      </button>

      <!-- Reload Button -->
      <button
        class="control-button control-button--reload"
        :title="t('agents.reload')"
        @click="handleReload"
      >
        <MIcon name="refresh" />
      </button>

      <!-- New Message Button -->
      <button class="new-message-button" @click="handleNewMessage">
        <MIcon name="mail" />
        <span>{{ t('agents.newMessage') }}</span>
      </button>
    </div>

    <!-- Prompt Preview Modal -->
    <PromptPreviewModal
      :show="showPromptModal"
      :agentName="agent.name"
      @close="showPromptModal = false"
    />
  </div>
</template>

<style scoped>
.agent-card {
  background: white;
  border: 1px solid var(--surface-hover);
  border-radius: var(--radius-md);
  padding: var(--spacing-6);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.agent-card:hover {
  border-color: var(--border);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.agent-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--spacing-2);
}

.agent-card__info {
  flex: 1;
  min-width: 0;
}

.agent-card__status-icon {
  flex-shrink: 0;
}

.agent-card__name {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-1) 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-card__description {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: 0;
  line-height: var(--leading-tight);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.agent-card__status {
  padding: var(--spacing-2) 0;
  border-top: 1px solid var(--surface-secondary);
  border-bottom: 1px solid var(--surface-secondary);
  min-height: 72px;
}

.agent-card__controls {
  display: flex;
  gap: var(--spacing-1);
  justify-content: flex-end;
  align-items: center;
}

.control-button {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: white;
  color: var(--text-secondary);
  font-size: var(--icon-sm, 14px);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  flex-shrink: 0;
}

.control-button:hover:not(:disabled) {
  background: var(--surface-secondary);
  border-color: var(--border);
}

.control-button--disabled,
.control-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.control-button--stop:hover:not(:disabled) {
  background: var(--error-50);
  border-color: var(--error-200);
  color: var(--error-600);
}

.control-button--pause:hover:not(:disabled) {
  background: var(--warning-50);
  border-color: var(--warning-200);
  color: var(--warning-600);
}

.control-button--prompt:hover:not(:disabled) {
  background: var(--accent-50);
  border-color: var(--accent-200);
  color: var(--accent);
}

.control-button--reload:hover:not(:disabled) {
  background: var(--info-50);
  border-color: var(--info-200);
  color: var(--info-600);
}

/* Tooltip for control buttons */
.control-button[title]:hover::after {
  content: attr(title);
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--text-primary);
  color: white;
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-xs);
  white-space: nowrap;
  z-index: var(--z-tooltip);
  pointer-events: none;
}

.new-message-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--surface-hover);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  flex-shrink: 0;
  height: 32px;
}

.new-message-button:hover {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.new-message-button:active {
  transform: scale(0.98);
}
</style>