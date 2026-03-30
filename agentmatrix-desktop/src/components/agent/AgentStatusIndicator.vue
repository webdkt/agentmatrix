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

// 状态对应的样式和图标
const statusConfig = {
  IDLE: {
    icon: null,
    color: 'text-slate-400',
    text: 'IDLE'
  },
  THINKING: {
    icon: 'ti-brain',
    color: 'text-blue-400',
    text: '思考中...'
  },
  WORKING: {
    icon: 'ti-loader',
    color: 'text-emerald-400',
    text: '工作中...'
  },
  WAITING_FOR_USER: {
    icon: 'ti-message-circle',
    color: 'text-amber-400',
    text: '等待回复'
  }
}

const currentStatusConfig = computed(() => {
  return statusConfig[agentStatus.value] || statusConfig.IDLE
})
</script>

<template>
  <div v-if="agentData" class="agent-status-natural">
    <!-- IDLE 状态 -->
    <div
      v-if="agentStatus === 'IDLE'"
      class="flex items-center gap-2"
    >
      <span class="status-badge status-badge--idle">IDLE</span>
      <span class="text-sm text-slate-500">{{ agentName }}</span>
    </div>

    <!-- WORKING/THINKING/WAITING_FOR_USER 状态 -->
    <div v-else class="agent-status-active">
      <!-- 为当前会话工作 -->
      <div v-if="isWorkingOnCurrentSession" class="space-y-1.5">
        <div class="flex items-center gap-2 text-sm" :class="currentStatusConfig.color">
          <span class="animate-spin"><MIcon :name="currentStatusConfig.icon.replace('ti-', '')" /></span>
          <span>{{ agentName }}: {{ currentStatusConfig.text }}</span>
        </div>

        <!-- 状态历史消息 -->
        <div v-if="recentStatusHistory.length > 0" class="ml-4 space-y-1">
          <div
            v-for="(historyItem, index) in recentStatusHistory"
            :key="index"
            class="text-xs text-slate-500 leading-relaxed"
          >
            {{ historyItem.message }}
          </div>
        </div>
      </div>

      <!-- 为其他会话工作 -->
      <div v-else class="flex items-center gap-2 text-sm text-amber-400">
        <MIcon name="arrow-right" />
        <span>{{ agentName }} 正在处理其他任务</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-status-natural {
  width: 100%;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  border-radius: 4px;
  text-transform: uppercase;
}

.status-badge--idle {
  background: var(--parchment-200, #e8e4de);
  color: var(--ink-500, #6b6560);
}

:deep(.text-slate-400) {
  color: var(--ink-400);
}

:deep(.text-slate-500) {
  color: var(--ink-300);
}

:deep(.text-blue-400) {
  color: var(--accent);
}

:deep(.text-emerald-400) {
  color: var(--verdant);
}

:deep(.text-amber-400) {
  color: var(--amber);
}

:deep(.text-sm) {
  font-size: var(--font-sm);
}

:deep(.text-xs) {
  font-size: var(--font-xs);
}

:deep(.text-base) {
  font-size: var(--font-base);
}

:deep(.leading-relaxed) {
  line-height: var(--leading-relaxed);
}

:deep(.flex) {
  display: flex;
}

:deep(.items-center) {
  align-items: center;
}

:deep(.gap-2) {
  gap: var(--spacing-2);
}

:deep(.space-y-1\.5) > * + * {
  margin-top: var(--spacing-1);
}

:deep(.space-y-1) > * + * {
  margin-top: 4px;
}

:deep(.ml-4) {
  margin-left: var(--spacing-md);
}

:deep(.animate-spin) {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
