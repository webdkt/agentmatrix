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
  showName: {
    type: Boolean,
    default: false
  }
})

const agentStore = useAgentStore()

// 获取 Agent 状态
const agentData = computed(() => agentStore.getAgent(props.agentName))
const agentStatus = computed(() => agentStore.getAgentStatus(props.agentName))

// 检查 Agent 是否正在为当前会话工作
const isWorkingOnCurrentSession = computed(() => {
  if (!agentData.value || !props.currentSessionId) return false
  return agentData.value.current_user_session_id === props.currentSessionId
})

// 获取最近的状态历史（最近3条）
const recentStatusHistory = computed(() => {
  if (!agentData.value?.status_history) return []
  return agentData.value.status_history.slice(-3)
})

// 状态对应的图标
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

// 判断是否需要旋转动画
const isSpinning = computed(() => {
  return ['THINKING', 'WORKING'].includes(agentStatus.value)
})
</script>

<template>
  <div v-if="agentData" class="agent-status-icon">
    <div class="status-icon" :class="currentIconConfig.color">
      <!-- IDLE: 显示文字badge -->
      <span v-if="agentStatus === 'IDLE'" class="status-badge">IDLE</span>
      <!-- 其他状态: 显示图标 -->
      <span v-else :class="{ 'animate-spin': isSpinning }">
        <MIcon :name="currentIconConfig.icon" />
      </span>
    </div>
    <span v-if="showName" class="status-name">{{ agentName }}</span>
  </div>
</template>

<style scoped>
.agent-status-icon {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-xs);
}

.status-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  font-size: 14px;
}

.status-badge {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 3px 6px;
  border-radius: 3px;
  text-transform: uppercase;
  background: var(--parchment-200, #e8e4de);
  color: var(--ink-500, #6b6560);
  width: auto;
  height: auto;
}

.status-name {
  font-size: var(--font-sm);
  color: var(--ink-500);
}

/* 状态颜色 */
.status--thinking {
  color: var(--accent, #c23b22);
}

.status--working {
  color: var(--verdant, #22c55e);
}

.status--waiting {
  color: var(--amber, #f59e0b);
}

.status--paused {
  color: var(--ink-400, #9ca3af);
}

.status--error {
  color: var(--fault, #ef4444);
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>