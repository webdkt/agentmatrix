<script setup>
import { ref, computed, onMounted } from 'vue'
import { agentAPI } from '@/api/agent'
import { useAgentStore } from '@/stores/agent'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['select-agent'])

const agentStore = useAgentStore()
const agents = ref([])
const isLoading = ref(true)

onMounted(async () => {
  try {
    const result = await agentAPI.getAgents()
    agents.value = result.agents || []
  } catch (error) {
    console.error('Failed to load agents:', error)
  } finally {
    isLoading.value = false
  }
})

const getAgentStatus = (agentName) => {
  return agentStore.agents[agentName]?.status || 'IDLE'
}

const statusLabel = (status) => {
  const labels = {
    THINKING: 'thinking',
    WORKING: 'working',
    WAITING_FOR_USER: 'waiting',
    PAUSED: 'paused',
    ERROR: 'error',
  }
  return labels[status] || ''
}

const statusIcon = (status) => {
  const icons = {
    THINKING: 'brain',
    WORKING: 'loader',
    WAITING_FOR_USER: 'message-circle',
    PAUSED: 'player-pause',
    ERROR: 'alert-circle',
  }
  return icons[status] || 'circle'
}

const isSpinning = (status) => status === 'THINKING' || status === 'WORKING'

const selectAgent = (agent) => {
  emit('select-agent', agent)
}
</script>

<template>
  <div class="collab-start">
    <div class="collab-start__header">
      <h2 class="collab-start__title">Pick an Agent to Assign Task</h2>
    </div>

    <div v-if="isLoading" class="collab-start__loading">
      <MIcon name="loader" class="collab-start__spinner" />
      <span>Loading agents...</span>
    </div>

    <div v-else-if="agents.length === 0" class="collab-start__empty">
      <MIcon name="users" class="collab-start__empty-icon" />
      <span>No agents available</span>
    </div>

    <div v-else class="collab-start__grid">
      <button
        v-for="agent in agents"
        :key="agent.name"
        class="collab-start__card"
        @click="selectAgent(agent)"
      >
        <div class="collab-start__card-header">
          <div class="collab-start__avatar">
            {{ agent.name ? agent.name.charAt(0).toUpperCase() : '?' }}
          </div>
          <div class="collab-start__card-info">
            <div class="collab-start__card-name">{{ agent.name }}</div>
            <div class="collab-start__card-desc">{{ agent.description || 'No description' }}</div>
          </div>
        </div>

        <div class="collab-start__card-status">
          <template v-if="getAgentStatus(agent.name) !== 'IDLE'">
            <span :class="['collab-start__status-icon', { 'collab-start__status-icon--spinning': isSpinning(getAgentStatus(agent.name)) }]">
              <MIcon :name="statusIcon(getAgentStatus(agent.name))" />
            </span>
            <span class="collab-start__status-label">{{ statusLabel(getAgentStatus(agent.name)) }}</span>
          </template>
          <template v-else>
            <span class="collab-start__status-label collab-start__status-label--idle">idle</span>
          </template>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.collab-start {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--spacing-6);
  overflow-y: auto;
}

.collab-start__header {
  margin-bottom: var(--spacing-6);
}

.collab-start__title {
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.collab-start__loading,
.collab-start__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: var(--spacing-2);
  flex: 1;
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.collab-start__spinner {
  animation: collab-spin 1.2s linear infinite;
  font-size: var(--icon-lg);
}

.collab-start__empty-icon {
  font-size: 32px;
  color: var(--border-strong);
}

.collab-start__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--spacing-4);
}

.collab-start__card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  padding: var(--spacing-4);
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  text-align: left;
  font-family: inherit;
}

.collab-start__card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.collab-start__card-header {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-2);
}

.collab-start__avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--accent-muted);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
}

.collab-start__card-info {
  flex: 1;
  min-width: 0;
}

.collab-start__card-name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

.collab-start__card-desc {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.collab-start__card-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  padding-top: var(--spacing-1);
  border-top: 1px solid var(--surface-hover);
}

.collab-start__status-icon {
  display: flex;
  align-items: center;
}

.collab-start__status-icon--spinning {
  animation: collab-spin 1.2s linear infinite;
}

.collab-start__status-label--idle {
  color: var(--border-strong);
}

@keyframes collab-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
