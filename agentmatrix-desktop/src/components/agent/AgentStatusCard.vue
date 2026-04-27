<script setup>
import { computed } from 'vue'
import { useAgentStore } from '@/stores/agent'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  },
  currentSessionId: {
    type: String,
    default: null
  },
  isSelected: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['select'])

const agentStore = useAgentStore()

const agentData = computed(() => agentStore.getAgent(props.agentName))
const agentStatus = computed(() => agentStore.getAgentStatus(props.agentName))

// Session-aware logic
const isWorkingOnCurrentSession = computed(() => {
  if (!agentData.value || !props.currentSessionId) return false
  return agentData.value.current_user_session_id === props.currentSessionId
})

const isWorkingOnOtherSession = computed(() => {
  if (!agentData.value) return false
  return agentData.value.current_user_session_id && agentData.value.current_user_session_id !== props.currentSessionId
})

const otherSessionId = computed(() => {
  if (!isWorkingOnOtherSession.value) return null
  return agentData.value.current_user_session_id
})

const isAssistingOtherAgent = computed(() => {
  if (!agentData.value) return false
  return !agentData.value.current_user_session_id && agentStatus.value !== 'IDLE'
})

const isClickable = computed(() => {
  return !isAssistingOtherAgent.value
})

// Status icon config
const statusIconConfig = {
  IDLE: { icon: null, color: '' },
  THINKING: { icon: 'brain', color: 'status--thinking' },
  WORKING: { icon: 'loader', color: 'status--working' },
  WAITING_FOR_USER: { icon: 'message-circle', color: 'status--waiting' },
  PAUSED: { icon: 'player-pause', color: 'status--paused' },
  ERROR: { icon: 'alert-circle', color: 'status--error' }
}

const currentIconConfig = computed(() => {
  return statusIconConfig[agentStatus.value] || statusIconConfig.IDLE
})

const isSpinning = computed(() => {
  return ['THINKING', 'WORKING'].includes(agentStatus.value)
})

// Status message
const statusMessage = computed(() => {
  if (agentStatus.value === 'IDLE') return null
  if (isWorkingOnCurrentSession.value) {
    const history = agentData.value?.status_history
    if (history && history.length > 0) {
      return history[history.length - 1].message
    }
    return null
  }
  if (isWorkingOnOtherSession.value) return '正在处理其他工作'
  if (isAssistingOtherAgent.value) return '正在协助其他Agent'
  return null
})

const handleClick = () => {
  if (!isClickable.value) return
  emit('select', props.agentName)
}
</script>

<template>
  <div
    v-if="agentData"
    class="agent-status-card"
    :class="{
      'agent-status-card--selected': isSelected,
      'agent-status-card--clickable': isClickable
    }"
    @click="handleClick"
  >
    <div class="agent-status-card__icon" :class="currentIconConfig.color">
      <span v-if="agentStatus === 'IDLE'" class="status-badge">IDLE</span>
      <span v-else :class="{ 'animate-spin': isSpinning }">
        <MIcon :name="currentIconConfig.icon" />
      </span>
    </div>
    <div class="agent-status-card__info">
      <span class="agent-status-card__name">{{ agentName }}</span>
      <span v-if="statusMessage" class="agent-status-card__message">{{ statusMessage }}</span>
    </div>
    <div v-if="isClickable" class="agent-status-card__arrow">
      <MIcon name="chevron-right" />
    </div>
  </div>
</template>

<style scoped>
.agent-status-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: var(--radius-md);
  background: white;
  border: 1px solid var(--border);
  transition: all var(--duration-base) var(--ease-out);
  user-select: none;
}

.agent-status-card--clickable {
  cursor: pointer;
}

.agent-status-card--clickable:hover {
  border-color: var(--border-strong);
  background: var(--surface-base);
}

.agent-status-card--selected {
  border-color: var(--accent);
  background: var(--surface-base);
  box-shadow: 0 0 0 1px var(--accent);
}

.agent-status-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-md);
  font-size: 14px;
  flex-shrink: 0;
}

.status-badge {
  font-size: 10px;
  font-weight: var(--font-medium);
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  color: var(--text-tertiary);
}

.agent-status-card__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-status-card__name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-status-card__message {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-status-card__arrow {
  font-size: 16px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  transition: transform var(--duration-base) var(--ease-out);
}

.agent-status-card--selected .agent-status-card__arrow {
  color: var(--accent);
}

/* Status colors */
.status--thinking { color: var(--accent); }
.status--working { color: var(--success); }
.status--waiting { color: var(--amber); }
.status--paused { color: var(--text-tertiary); }
.status--error { color: var(--error); }

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
