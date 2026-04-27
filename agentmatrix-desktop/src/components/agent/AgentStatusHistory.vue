<script setup>
import { computed } from 'vue'
import { useAgentStore } from '@/stores/agent'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  },
  maxItems: {
    type: Number,
    default: 4
  }
})

const agentStore = useAgentStore()

// 获取 Agent 状态
const agentData = computed(() => agentStore.getAgent(props.agentName))

// 获取最近的状态历史
const recentStatusHistory = computed(() => {
  if (!agentData.value?.status_history) return []
  return agentData.value.status_history.slice(-props.maxItems)
})

// 获取当前状态文本
const agentStatus = computed(() => agentStore.getAgentStatus(props.agentName))

// 状态文本映射
const statusTextMap = {
  IDLE: '空闲中',
  THINKING: '思考中...',
  WORKING: '工作中...',
  WAITING_FOR_USER: '等待回复',
  PAUSED: '已暂停',
  ERROR: '错误'
}

const currentStatusText = computed(() => {
  return statusTextMap[agentStatus.value] || '空闲中'
})
</script>

<template>
  <div v-if="agentData" class="agent-status-history">
    <!-- 当前状态 -->
    <div class="status-current">
      <span class="status-current__text">{{ currentStatusText }}</span>
    </div>
    
    <!-- 状态历史消息 -->
    <div v-if="recentStatusHistory.length > 0" class="status-history">
      <div
        v-for="(historyItem, index) in recentStatusHistory"
        :key="index"
        class="status-history__item"
      >
        {{ historyItem.message }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.agent-status-history {
  width: 100%;
}

.status-current {
  margin-bottom: var(--spacing-1);
}

.status-current__text {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  font-weight: 500;
}

.status-history {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-history__item {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  line-height: 1.6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>