<template>
  <div class="agent-list">
    <!-- 搜索框 -->
    <div class="agent-list__search">
      <input
        v-model="searchQuery"
        type="text"
        class="agent-list__search-input"
        :placeholder="$t('matrix.searchPlaceholder')"
      />
    </div>

    <!-- Agent 列表 -->
    <div class="agent-list__items">
      <div
        v-for="agent in filteredAgents"
        :key="agent.name"
        class="agent-list__item"
        :class="{ 'agent-list__item--active': selectedAgent === agent.name }"
        @click="$emit('select', agent.name)"
      >
        <div class="agent-list__item-name">{{ agent.name }}</div>
        <div class="agent-list__item-desc">{{ agent.description }}</div>
        <div class="agent-list__item-status">
          <span
            class="agent-list__status-dot"
            :class="getStatusClass(agent.status)"
          ></span>
          <span class="agent-list__status-text">{{ agent.status || 'IDLE' }}</span>
        </div>
      </div>

      <div v-if="filteredAgents.length === 0" class="agent-list__empty">
        {{ searchQuery ? $t('matrix.noResults') : $t('matrix.noAgents') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  agents: {
    type: Array,
    default: () => []
  },
  selectedAgent: {
    type: String,
    default: null
  }
})

defineEmits(['select'])

const searchQuery = ref('')

const filteredAgents = computed(() => {
  if (!searchQuery.value) return props.agents
  const query = searchQuery.value.toLowerCase()
  return props.agents.filter(agent =>
    agent.name.toLowerCase().includes(query) ||
    (agent.description && agent.description.toLowerCase().includes(query))
  )
})

function getStatusClass(status) {
  switch (status) {
    case 'RUNNING':
    case 'WORKING':
      return 'agent-list__status-dot--running'
    case 'THINKING':
      return 'agent-list__status-dot--thinking'
    case 'WAITING_FOR_USER':
      return 'agent-list__status-dot--waiting'
    case 'PAUSED':
      return 'agent-list__status-dot--paused'
    case 'ERROR':
      return 'agent-list__status-dot--error'
    default:
      return 'agent-list__status-dot--idle'
  }
}
</script>

<style scoped>
.agent-list {
  width: 260px;
  height: 100%;
  border-right: 1px solid var(--parchment-300);
  display: flex;
  flex-direction: column;
  background: var(--parchment-100);
}

.agent-list__search {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--parchment-300);
}

.agent-list__search-input {
  width: 100%;
  padding: var(--spacing-sm) 0;
  border: none;
  border-bottom: 1px solid var(--ink-200);
  background: transparent;
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--ink-700);
  outline: none;
  transition: border-color 0.2s;
}

.agent-list__search-input:focus {
  border-bottom-color: var(--accent);
}

.agent-list__search-input::placeholder {
  color: var(--ink-400);
}

.agent-list__items {
  flex: 1;
  overflow-y: auto;
}

.agent-list__item {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--parchment-300);
  cursor: pointer;
  transition: background-color 0.15s;
  border-left: 3px solid transparent;
}

.agent-list__item:hover {
  background: var(--parchment-200);
}

.agent-list__item--active {
  background: var(--parchment-50);
  border-left-color: var(--accent);
}

.agent-list__item-name {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-900);
  margin-bottom: 2px;
}

.agent-list__item-desc {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--ink-500);
  margin-bottom: var(--spacing-xs);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.agent-list__item-status {
  display: flex;
  align-items: center;
  gap: 6px;
}

.agent-list__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ink-300);
}

.agent-list__status-dot--running,
.agent-list__status-dot--thinking {
  background: var(--verdant);
}

.agent-list__status-dot--waiting {
  background: var(--amber);
}

.agent-list__status-dot--paused {
  background: var(--ink-400);
}

.agent-list__status-dot--error {
  background: var(--fault);
}

.agent-list__status-dot--idle {
  background: var(--ink-300);
}

.agent-list__status-text {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.agent-list__empty {
  padding: var(--spacing-lg);
  text-align: center;
  color: var(--ink-400);
  font-family: var(--font-sans);
  font-size: 14px;
}
</style>
