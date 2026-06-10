<script setup>
import { ref } from 'vue'
import WikiPageTree from './WikiPageTree.vue'
import WikiSourceManager from './WikiSourceManager.vue'

const activeTab = ref('pages')
</script>

<template>
  <div class="wiki-sidebar">
    <div class="wiki-sidebar__tabs">
      <button
        :class="['wiki-sidebar__tab', { 'wiki-sidebar__tab--active': activeTab === 'pages' }]"
        @click="activeTab = 'pages'"
      >
        目录
      </button>
      <button
        :class="['wiki-sidebar__tab', { 'wiki-sidebar__tab--active': activeTab === 'sources' }]"
        @click="activeTab = 'sources'"
      >
        源管理
      </button>
    </div>

    <div class="wiki-sidebar__content">
      <WikiPageTree v-if="activeTab === 'pages'" />
      <WikiSourceManager v-else-if="activeTab === 'sources'" />
    </div>
  </div>
</template>

<style scoped>
.wiki-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.wiki-sidebar__tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.wiki-sidebar__tab {
  flex: 1;
  padding: var(--spacing-2) var(--spacing-3);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-tertiary);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.wiki-sidebar__tab:hover {
  color: var(--text-secondary);
}

.wiki-sidebar__tab--active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}

.wiki-sidebar__content {
  flex: 1;
  overflow-y: auto;
}
</style>