<script setup>
import { computed } from 'vue'
import { useAgentStore } from '@/stores/agent'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: {
    type: String,
    required: true,
  },
})

const agentStore = useAgentStore()

const agentStatus = computed(() => {
  const agent = agentStore.agents[props.agentName]
  return agent?.status || 'IDLE'
})

const STATUS_MAP = {
  THINKING:        { icon: 'logo',           label: '思考中',     spinning: true },
  WORKING:         { icon: 'loader',         label: '执行中',     spinning: true },
  RECOVERING:      { icon: 'loader',         label: '恢复中',     spinning: true },
  WAITING_FOR_USER:{ icon: 'message-circle', label: '等待输入',   spinning: false },
  PAUSED:          { icon: 'player-pause',   label: '已暂停',     spinning: false },
  ERROR:           { icon: 'alert-circle',   label: '出错',       spinning: false },
  STOPPED:         { icon: 'circle',         label: '已停止',     spinning: false },
  IDLE:            { icon: 'circle-check',   label: '空闲',       spinning: false },
}

const statusMeta = computed(() => STATUS_MAP[agentStatus.value] || STATUS_MAP.IDLE)
const isActive = computed(() => agentStatus.value !== 'IDLE' && agentStatus.value !== 'STOPPED')
</script>

<template>
  <span
    class="status-badge"
    :class="{ 'status-badge--active': isActive }"
  >
    <span :class="['status-badge__icon', { 'status-badge__icon--spinning': statusMeta.spinning }]">
      <MIcon :name="statusMeta.icon" />
    </span>
    <span class="status-badge__label">{{ statusMeta.label }}</span>
  </span>
</template>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--surface-secondary);
  font-size: 11px;
  color: var(--text-secondary);
}

.status-badge--active {
  background: rgba(196, 162, 101, 0.1);
}

.status-badge__icon {
  display: inline-flex;
  font-size: 12px;
  color: var(--text-tertiary);
}

.status-badge__icon--spinning {
  animation: spin 1s linear infinite;
  color: var(--accent);
}

@keyframes spin {
  from { transform: rotate(0deg) }
  to { transform: rotate(360deg) }
}

.status-badge__label {
  color: var(--text-secondary);
  font-size: 11px;
}
</style>