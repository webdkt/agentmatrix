<script setup>
import { computed } from 'vue'
import { useAgentStore } from '@/stores/agent'

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
    icon: 'ti-player-pause',
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
      class="flex items-center gap-2 text-sm text-slate-400"
    >
      <i :class="['ti', currentStatusConfig.icon, 'text-xs']"></i>
      <span>{{ agentName }}</span>
    </div>

    <!-- WORKING/THINKING/WAITING_FOR_USER 状态 -->
    <div v-else class="agent-status-active">
      <!-- 为当前会话工作 -->
      <div v-if="isWorkingOnCurrentSession" class="space-y-1.5">
        <div class="flex items-center gap-2 text-sm" :class="currentStatusConfig.color">
          <i :class="['ti', currentStatusConfig.icon, 'text-xs animate-spin']"></i>
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
        <i class="ti ti-arrow-right text-xs"></i>
        <span>{{ agentName }} 正在处理其他任务</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-status-natural {
  @apply w-full;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 2s linear infinite;
}
</style>
