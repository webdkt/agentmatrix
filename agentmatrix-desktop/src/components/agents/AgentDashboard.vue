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
import ProfileTab from '@/components/matrix/tabs/ProfileTab.vue'
import ResourcesTab from '@/components/matrix/tabs/ResourcesTab.vue'
import LogTab from '@/components/matrix/tabs/LogTab.vue'
import MemoryTab from '@/components/matrix/tabs/MemoryTab.vue'

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
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--parchment-50);
  border-bottom: 1px solid var(--parchment-200);
}

.back-button {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: transparent;
  border: 1px solid var(--parchment-200);
  border-radius: var(--radius-sm);
  color: var(--ink-600);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.back-button:hover {
  background: var(--parchment-100);
  border-color: var(--parchment-300);
  color: var(--ink-800);
}

.agent-dashboard__tabs {
  display: flex;
  border-bottom: 1px solid var(--parchment-300);
  background: var(--parchment-50);
  padding: 0 var(--spacing-md);
}

.agent-dashboard__tab {
  padding: var(--spacing-md) var(--spacing-lg);
  border: none;
  background: none;
  font-family: var(--font-sans);
  font-size: 13px;
  color: var(--ink-500);
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
  font-variant: small-caps;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.agent-dashboard__tab:hover {
  color: var(--ink-700);
}

.agent-dashboard__tab--active {
  color: var(--ink-900);
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
  overflow: auto;
}

.agent-dashboard__empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-400);
  font-family: var(--font-serif);
  font-size: 16px;
  font-style: italic;
}
</style>