<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { agentAPI } from '@/api/agent'
import { useAgentStore } from '@/stores/agent'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['select-agent'])

const { t } = useI18n()
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

const statusMeta = (status) => {
  const map = {
    IDLE:           { label: 'status.idle',     cls: 'idle',     color: '#A1A1AA' },
    THINKING:       { label: 'status.thinking', cls: 'thinking', color: '#C4A265' },
    WORKING:        { label: 'status.working',  cls: 'working',  color: '#C4A265' },
    WAITING_FOR_USER: { label: 'status.waiting', cls: 'waiting', color: '#7B8FA1' },
    PAUSED:         { label: 'status.paused',   cls: 'paused',   color: '#B57171' },
    ERROR:          { label: 'status.error',    cls: 'error',    color: '#B57171' },
  }
  return map[status] || map.IDLE
}

const selectAgent = (agent) => {
  emit('select-agent', agent)
}
</script>

<template>
  <div class="collab-start">
    <div class="collab-start__header">
      <h2 class="collab-start__title">{{ t('collab.pickAgentTitle') }}</h2>
      <p class="collab-start__subtitle">{{ t('collab.pickAgentSubtitle') }}</p>
    </div>

    <div v-if="isLoading" class="collab-start__loading">
      <MIcon name="loader" class="collab-start__spinner" />
      <span>{{ t('collab.loadingAgents') }}</span>
    </div>

    <div v-else-if="agents.length === 0" class="collab-start__empty">
      <MIcon name="users" class="collab-start__empty-icon" />
      <span>{{ t('collab.noAgentsAvailable') }}</span>
    </div>

    <div v-else class="collab-start__list">
      <div
        v-for="agent in agents"
        :key="agent.name"
        class="collab-start__item"
        @click="selectAgent(agent)"
      >
        <div class="collab-start__item-main">
          <div class="collab-start__name">{{ agent.name }}</div>
          <div class="collab-start__description">
            {{ agent.description || t('agents.noData') }}
          </div>
        </div>

        <div class="collab-start__item-side">
          <div
            class="collab-start__status"
            :class="`collab-start__status--${statusMeta(getAgentStatus(agent.name)).cls}`"
          >
            <span class="collab-start__status-dot" />
            <span>{{ t(statusMeta(getAgentStatus(agent.name)).label) }}</span>
          </div>
          <MIcon name="chevron-right" class="collab-start__arrow" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.collab-start {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--spacing-8) var(--spacing-8);
  overflow-y: auto;
  background: var(--surface-base);
}

.collab-start__header {
  margin-bottom: var(--spacing-8);
}

.collab-start__title {
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-2) 0;
  letter-spacing: var(--tracking-tight);
}

.collab-start__subtitle {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: 0;
}

.collab-start__loading,
.collab-start__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-3);
  flex: 1;
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.collab-start__spinner {
  animation: spin 1.2s linear infinite;
  font-size: var(--icon-lg);
}

.collab-start__empty-icon {
  font-size: 28px;
  color: var(--border-strong);
}

/* ---- Agent list ---- */
.collab-start__list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.collab-start__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-4);
  padding: var(--spacing-4) var(--spacing-5);
  background: var(--surface-base);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all 0.2s var(--ease-out);
}

.collab-start__item:hover {
  border-color: var(--border);
  background: var(--surface-secondary);
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.collab-start__item:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm);
}

.collab-start__item-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
  flex: 1;
}

.collab-start__name {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  line-height: var(--leading-snug);
}

.collab-start__description {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  line-height: var(--leading-normal);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.collab-start__item-side {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  flex-shrink: 0;
}

/* ---- Status pill ---- */
.collab-start__status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: var(--font-medium);
  letter-spacing: 0.02em;
  white-space: nowrap;
  border: 1px solid transparent;
}

.collab-start__status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.collab-start__status--idle {
  color: var(--text-tertiary);
  background: var(--surface-secondary);
  border-color: var(--border-light);
}

.collab-start__status--thinking,
.collab-start__status--working {
  color: #C4A265;
  background: rgba(196, 162, 101, 0.08);
  border-color: rgba(196, 162, 101, 0.18);
}

.collab-start__status--thinking .collab-start__status-dot,
.collab-start__status--working .collab-start__status-dot {
  animation: pulse 1.5s ease-in-out infinite;
}

.collab-start__status--waiting {
  color: #7B8FA1;
  background: rgba(123, 143, 161, 0.08);
  border-color: rgba(123, 143, 161, 0.18);
}

.collab-start__status--paused {
  color: #B57171;
  background: rgba(181, 113, 113, 0.08);
  border-color: rgba(181, 113, 113, 0.18);
}

.collab-start__status--error {
  color: #B57171;
  background: rgba(181, 113, 113, 0.08);
  border-color: rgba(181, 113, 113, 0.18);
}

.collab-start__arrow {
  font-size: var(--icon-sm);
  color: var(--text-quaternary);
  transition: color 0.15s ease;
}

.collab-start__item:hover .collab-start__arrow {
  color: var(--text-tertiary);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.5; transform: scale(1.1); }
}
</style>
