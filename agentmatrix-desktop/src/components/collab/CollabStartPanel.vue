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

// Morandi colors for left accent
const morandiColors = [
  'rose', 'sage', 'slate', 'mauve', 'taupe', 'terracotta', 'olive', 'blue'
]

const getAgentColor = (index) => {
  return morandiColors[index % morandiColors.length]
}

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
    IDLE: 'status.idle',
    THINKING: 'status.thinking',
    WORKING: 'status.working',
    WAITING_FOR_USER: 'status.waiting',
    PAUSED: 'status.paused',
    ERROR: 'status.error',
  }
  return labels[status] || 'status.idle'
}

const statusClass = (status) => {
  const classes = {
    IDLE: 'idle',
    THINKING: 'thinking',
    WORKING: 'working',
    WAITING_FOR_USER: 'waiting',
    PAUSED: 'paused',
    ERROR: 'error',
  }
  return classes[status] || 'idle'
}

const getSkillIcon = (description) => {
  const desc = description?.toLowerCase() || ''
  if (desc.includes('research') || desc.includes('研究')) return 'search'
  if (desc.includes('writ') || desc.includes('写') || desc.includes('文档')) return 'file-text'
  if (desc.includes('code') || desc.includes('programm') || desc.includes('开发')) return 'code'
  if (desc.includes('design') || desc.includes('设计') || desc.includes('ui')) return 'palette'
  if (desc.includes('plan') || desc.includes('规划')) return 'layout'
  if (desc.includes('test') || desc.includes('测试') || desc.includes('质量')) return 'check-circle'
  if (desc.includes('analy') || desc.includes('数据') || desc.includes('analyt')) return 'bar-chart'
  if (desc.includes('system') || desc.includes('admin') || desc.includes('运维')) return 'server'
  return 'star'
}

const getModelName = (className) => {
  if (!className) return 'GPT-4'
  const name = className.toLowerCase()
  if (name.includes('claude')) return 'Claude 3.5'
  if (name.includes('gpt')) return 'GPT-4'
  return 'GPT-4'
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

    <div v-else class="collab-start__grid">
      <div
        v-for="(agent, index) in agents"
        :key="agent.name"
        :class="['collab-start__card', `collab-start__card--${getAgentColor(index)}`]"
        @click="selectAgent(agent)"
      >
        <div class="collab-start__card-header">
          <div class="collab-start__name-row">
            <div class="collab-start__name">{{ agent.name }}</div>
            <div :class="['collab-start__status', `collab-start__status--${statusClass(getAgentStatus(agent.name))}`]">
              <span class="collab-start__status-dot"></span>
              {{ t(statusLabel(getAgentStatus(agent.name))) }}
            </div>
          </div>
          <div class="collab-start__description">{{ agent.description || t('agents.noData') }}</div>
        </div>

        <div class="collab-start__meta">
          <div class="collab-start__meta-row">
            <span class="collab-start__tag collab-start__tag--model">
              <MIcon name="cpu" />
              {{ getModelName(agent.className) }}
            </span>
            <span class="collab-start__tag collab-start__tag--skill">
              <MIcon :name="getSkillIcon(agent.description)" />
              {{ agent.name.split(' ')[0] }}
            </span>
          </div>
          <div class="collab-start__meta-row collab-start__meta-row--right">
            <MIcon :name="getSkillIcon(agent.description)" class="collab-start__decor" />
          </div>
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
  padding: var(--spacing-6);
  overflow-y: auto;
}

.collab-start__header {
  margin-bottom: 24px;
}

.collab-start__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.collab-start__subtitle {
  font-size: 14px;
  color: var(--text-tertiary);
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
  gap: 16px;
}

/* Morandi color accents */
.collab-start__card--rose { --card-color: #C4A4A0; }
.collab-start__card--sage { --card-color: #9CAF88; }
.collab-start__card--slate { --card-color: #8E9AAF; }
.collab-start__card--mauve { --card-color: #B8A9C9; }
.collab-start__card--taupe { --card-color: #B5A89A; }
.collab-start__card--terracotta { --card-color: #C08B6E; }
.collab-start__card--olive { --card-color: #A8B09A; }
.collab-start__card--blue { --card-color: #7B8FA1; }

.collab-start__card {
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  position: relative;
  min-height: 220px;
  overflow: hidden;
}

/* Left color accent */
.collab-start__card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--card-color);
  opacity: 0.6;
  transition: opacity 0.25s ease;
}

.collab-start__card:hover::before {
  opacity: 1;
}

.collab-start__card:hover {
  border-color: var(--card-color);
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  transform: translateY(-3px);
}

.collab-start__card:active {
  transform: translateY(-1px);
}

.collab-start__card-header {
  margin-bottom: 12px;
}

.collab-start__name-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.collab-start__name {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
  flex: 1;
}

.collab-start__status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 11px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  flex-shrink: 0;
  white-space: nowrap;
}

.collab-start__status--idle {
  background: var(--surface-secondary);
  color: var(--text-quaternary);
  border: 1px solid var(--border-light);
}

.collab-start__status--thinking,
.collab-start__status--working {
  background: rgba(196,162,101,0.12);
  color: #C4A265;
  border: 1px solid rgba(196,162,101,0.25);
}

.collab-start__status--error {
  background: rgba(181,113,113,0.12);
  color: #B57171;
  border: 1px solid rgba(181,113,113,0.25);
}

.collab-start__status--waiting {
  background: rgba(123,143,161,0.12);
  color: #7B8FA1;
  border: 1px solid rgba(123,143,161,0.25);
}

.collab-start__status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.collab-start__status--thinking .collab-start__status-dot,
.collab-start__status--working .collab-start__status-dot {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.1); }
}

.collab-start__description {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.collab-start__meta {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--border-light);
}

.collab-start__meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.collab-start__meta-row--right {
  justify-content: flex-end;
}

.collab-start__tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 11px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.collab-start__tag svg {
  width: 12px;
  height: 12px;
}

.collab-start__tag--model {
  background: rgba(166,123,123,0.08);
  color: var(--accent);
  border: 1px solid rgba(166,123,123,0.18);
}

.collab-start__tag--skill {
  background: var(--surface-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.collab-start__decor {
  width: 18px;
  height: 18px;
  color: var(--text-quaternary);
  opacity: 0.5;
  transition: all 0.25s ease;
}

.collab-start__card:hover .collab-start__decor {
  color: var(--card-color);
  opacity: 1;
  transform: rotate(15deg) scale(1.1);
}

@keyframes collab-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
