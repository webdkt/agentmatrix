<template>
  <div class="agent-dashboard">
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
        {{ $t('matrix.selectAgent') }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ProfileTab from './tabs/ProfileTab.vue'
import ResourcesTab from './tabs/ResourcesTab.vue'
import LogTab from './tabs/LogTab.vue'
import MemoryTab from './tabs/MemoryTab.vue'

defineProps({
  agentName: {
    type: String,
    default: null
  }
})

const tabs = [
  { id: 'profile', label: 'matrix.tabs.profile' },
  { id: 'resources', label: 'matrix.tabs.resources' },
  { id: 'log', label: 'matrix.tabs.log' },
  { id: 'memory', label: 'matrix.tabs.memory' }
]

const activeTab = ref('profile')
</script>

<style scoped>
.agent-dashboard {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  overflow: hidden;
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
