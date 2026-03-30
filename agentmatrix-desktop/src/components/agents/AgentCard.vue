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
  border: 1px solid var(--parchment-200);
  border-radius: var(--radius-sm);
  padding: var(--spacing-lg);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.agent-card:hover {
  border-color: var(--parchment-300);
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.agent-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--spacing-sm);
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
  color: var(--ink-900);
  margin: 0 0 var(--spacing-xs) 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-card__description {
  font-size: var(--font-sm);
  color: var(--ink-500);
  margin: 0;
  line-height: var(--leading-tight);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.agent-card__status {
  padding: var(--spacing-sm) 0;
  border-top: 1px solid var(--parchment-100);
  border-bottom: 1px solid var(--parchment-100);
}

.agent-card__controls {
  display: flex;
  gap: var(--spacing-xs);
  justify-content: flex-end;
  align-items: center;
}

.control-button {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--parchment-300);
  background: white;
  color: var(--ink-600);
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
  background: var(--parchment-100);
  border-color: var(--parchment-400);
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
  background: var(--neutral-800);
  color: white;
  padding: var(--spacing-xs) var(--spacing-sm);
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
  background: var(--parchment-200, #e8e4de);
  border: 1px solid var(--parchment-300, #d4cfc7);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm, 12px);
  font-weight: 500;
  color: var(--ink-700, #3d3833);
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