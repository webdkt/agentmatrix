<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'
import AgentCard from './AgentCard.vue'

const props = defineProps({
  agents: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['select', 'new-message'])

const { t } = useI18n()
const searchQuery = ref('')

// Filter agents based on search query (full-text search on name and description)
const filteredAgents = computed(() => {
  if (!searchQuery.value) return props.agents
  const query = searchQuery.value.toLowerCase()
  return props.agents.filter(agent =>
    agent.name.toLowerCase().includes(query) ||
    (agent.description && agent.description.toLowerCase().includes(query))
  )
})

// Handle agent card click
const handleAgentClick = (agentName) => {
  emit('select', agentName)
}

// Handle new message button click
const handleNewMessage = (agentName) => {
  const agent = props.agents.find(a => a.name === agentName)
  emit('new-message', agent || agentName)
}

// Handle control actions
const handleStopAgent = (agentName) => {
  console.log('Stop agent:', agentName)
  // TODO: Implement stop agent action
}

const handleStartAgent = (agentName) => {
  console.log('Start agent:', agentName)
  // TODO: Implement start agent action
}

const handlePauseAgent = (agentName) => {
  console.log('Pause agent:', agentName)
  // TODO: Implement pause agent action
}

const handleViewPrompt = (agentName) => {
  console.log('View prompt for agent:', agentName)
  // TODO: Implement view full prompt action
}
</script>

<template>
  <div class="overall-dashboard">
    <!-- Search Header -->
    <div class="overall-dashboard__search">
      <div class="search-input-wrapper">
        <MIcon name="search" class="search-icon" />
        <input
          v-model="searchQuery"
          type="text"
          class="search-input"
          :placeholder="t('agents.searchPlaceholder')"
        />
      </div>
    </div>
    
    <!-- Agent Cards Grid -->
    <div class="overall-dashboard__content">
      <div class="agents-grid">
        <AgentCard
          v-for="agent in filteredAgents"
          :key="agent.name"
          :agent="agent"
          @click="handleAgentClick(agent.name)"
          @new-message="handleNewMessage(agent.name)"
          @stop="handleStopAgent(agent.name)"
          @start="handleStartAgent(agent.name)"
          @pause="handlePauseAgent(agent.name)"
          @view-prompt="handleViewPrompt(agent.name)"
        />
      </div>
      
      <!-- Empty state -->
      <div v-if="filteredAgents.length === 0" class="overall-dashboard__empty">
        <div class="empty-icon">
          <MIcon name="agent" />
        </div>
        <h3>{{ t('agents.noAgentsFound') }}</h3>
        <p>{{ searchQuery ? t('agents.tryDifferentSearch') : t('agents.noAgentsAvailable') }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overall-dashboard {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.overall-dashboard__search {
  padding: var(--spacing-lg);
  background: var(--parchment-50);
  border-bottom: 1px solid var(--parchment-200);
  flex-shrink: 0;
}

.search-input-wrapper {
  position: relative;
  max-width: 600px;
  margin: 0 auto;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: var(--icon-md);
  color: var(--ink-400);
  pointer-events: none;
}

.search-input {
  width: 100%;
  height: var(--input-height-md);
  padding: 0 var(--spacing-md) 0 40px;
  background: white;
  border: 1px solid var(--parchment-300);
  border-radius: var(--radius-sm);
  font-size: var(--font-base);
  color: var(--ink-700);
  transition: all var(--duration-base) var(--ease-out);
}

.search-input::placeholder {
  color: var(--ink-400);
}

.search-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(194, 59, 34, 0.1);
}

.overall-dashboard__content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

.agents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--spacing-lg);
  max-width: 1400px;
  margin: 0 auto;
}

.overall-dashboard__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 300px;
  text-align: center;
  color: var(--ink-500);
}

.empty-icon {
  width: 80px;
  height: 80px;
  background: var(--parchment-100);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: var(--ink-300);
  margin-bottom: var(--spacing-lg);
}

.overall-dashboard__empty h3 {
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--ink-700);
  margin: 0 0 var(--spacing-sm) 0;
}

.overall-dashboard__empty p {
  font-size: var(--font-base);
  color: var(--ink-500);
  margin: 0;
}
</style>