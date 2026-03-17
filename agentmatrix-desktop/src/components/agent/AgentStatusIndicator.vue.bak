<template>
  <div class="agent-status-indicator">
    <div class="flex items-center gap-2 p-3 bg-white rounded-lg border border-surface-200">
      <!-- Agent Icon -->
      <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center">
        <i class="ti ti-robot text-sm text-white"></i>
      </div>

      <!-- Agent Info -->
      <div class="flex-1">
        <div class="flex items-center gap-2">
          <span class="font-medium text-surface-900">{{ agentName }}</span>
          <span
            v-if="status"
            :class="statusClass"
            class="px-2 py-0.5 rounded-full text-xs font-medium"
          >
            {{ statusDisplay }}
          </span>
        </div>

        <!-- Status Details -->
        <div v-if="agentData" class="mt-1 text-sm">
          <!-- IDLE -->
          <div v-if="agentData.status === 'IDLE'" class="text-surface-500">
            {{ agentName }} is idle
          </div>

          <!-- Working on current session -->
          <div v-else-if="isWorkingOnCurrentSession" class="space-y-1">
            <div
              v-for="(historyItem, index) in recentHistory"
              :key="index"
              class="flex items-center gap-2 text-surface-600"
            >
              <span class="text-xs text-surface-400">
                {{ formatTime(historyItem.timestamp) }}
              </span>
              <span>{{ historyItem.status }}</span>
            </div>
          </div>

          <!-- Working on other session -->
          <div v-else class="flex items-center gap-2">
            <span class="text-amber-600">正在为其他任务工作</span>
            <button
              @click="switchToAgentSession"
              class="text-primary-600 hover:text-primary-700 text-sm font-medium"
            >
              切换查看 →
            </button>
          </div>
        </div>

        <!-- Loading State -->
        <div v-else class="text-surface-400 text-sm">
          Loading status...
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  },
  currentSessionId: {
    type: String,
    required: true
  }
})

const websocketStore = useWebSocketStore()

const agentData = computed(() => {
  return websocketStore.agentStatuses[props.agentName]
})

const status = computed(() => {
  return agentData.value?.status
})

const statusClass = computed(() => {
  switch (status.value) {
    case 'IDLE':
      return 'bg-surface-100 text-surface-600'
    case 'THINKING':
      return 'bg-blue-50 text-blue-600'
    case 'WORKING':
      return 'bg-amber-50 text-amber-600'
    case 'WAITING_FOR_USER':
      return 'bg-green-50 text-green-600'
    default:
      return 'bg-surface-50 text-surface-500'
  }
})

const statusDisplay = computed(() => {
  switch (status.value) {
    case 'IDLE':
      return 'IDLE'
    case 'THINKING':
      return '思考中'
    case 'WORKING':
      return '工作中'
    case 'WAITING_FOR_USER':
      return '等待用户'
    default:
      return status.value || 'Unknown'
  }
})

const isWorkingOnCurrentSession = computed(() => {
  return agentData.value?.current_user_session_id === props.currentSessionId
})

const recentHistory = computed(() => {
  if (!agentData.value?.status_history) return []

  // 获取最近3条符合当前session的历史记录
  return agentData.value.status_history
    .filter(item => item.user_session_id === props.currentSessionId)
    .slice(-3)
})

const switchToAgentSession = () => {
  if (agentData.value?.current_user_session_id) {
    // TODO: 切换到Agent正在工作的会话
    console.log('Switching to session:', agentData.value.current_user_session_id)
  }
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.agent-status-indicator {
  @apply border-t border-surface-100;
}
</style>
