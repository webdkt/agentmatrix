<template>
  <div class="agent-dashboard">
    <!-- Back Button -->
    <div class="agent-dashboard__header">
      <button class="back-button" @click="handleBack">
        <MIcon name="arrow-left" />
        <span>{{ $t('agents.backToAgents') }}</span>
      </button>
    </div>

    <!-- Tab 导航 -->
    <div class="agent-dashboard__tabs">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="agent-dashboard__tab"
        :class="{ 'agent-dashboard__tab--active': activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ $t(tab.label) }}
      </button>
    </div>

    <!-- Tab 内容 -->
    <div class="agent-dashboard__content">
      <template v-if="agentName">
        <ProfileTab v-if="activeTab === 'profile'" :agent-name="agentName" />
        <ResourcesTab v-else-if="activeTab === 'resources'" :agent-name="agentName" />
        <LogTab v-else-if="activeTab === 'log'" :agent-name="agentName" />
        <MemoryTab v-else-if="activeTab === 'memory'" :agent-name="agentName" />
      </template>
      <div v-else class="agent-dashboard__empty">
        {{ $t('agents.selectAgent') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'
import ProfileTab from '@/components/agent-tabs/ProfileTab.vue'
import ResourcesTab from '@/components/agent-tabs/ResourcesTab.vue'
import LogTab from '@/components/agent-tabs/LogTab.vue'
import MemoryTab from '@/components/agent-tabs/MemoryTab.vue'

const props = defineProps({
  agentName: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['back'])

const tabs = [
  { id: 'profile', label: 'matrix.tabs.profile' },
  { id: 'resources', label: 'matrix.tabs.resources' },
  { id: 'log', label: 'matrix.tabs.log' },
  { id: 'memory', label: 'matrix.tabs.memory' }
]

const activeTab = ref('profile')

const handleBack = () => {
  emit('back')
}
</script>

<style scoped>
.agent-dashboard {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

.agent-dashboard__header {
  padding: var(--spacing-4) var(--spacing-6);
  background: var(--surface-base);
  border-bottom: 1px solid var(--surface-hover);
}

.back-button {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: transparent;
  border: 1px solid var(--surface-hover);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.back-button:hover {
  background: var(--surface-secondary);
  border-color: var(--border);
  color: var(--text-primary);
}

.agent-dashboard__tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  background: var(--surface-base);
  padding: 0 var(--spacing-4);
}

.agent-dashboard__tab {
  padding: var(--spacing-4) var(--spacing-6);
  border: none;
  background: none;
  font-family: var(--font-sans);
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.agent-dashboard__tab:hover {
  color: var(--text-secondary);
}

.agent-dashboard__tab--active {
  color: var(--text-primary);
}

.agent-dashboard__tab--active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--accent);
}

.agent-dashboard__content {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.agent-dashboard__empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-family: var(--font-sans);
  font-size: 16px;
  font-style: italic;
}
</style>