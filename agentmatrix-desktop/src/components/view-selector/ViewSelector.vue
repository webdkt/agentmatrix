<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSessionStore } from '@/stores/session'
import MIcon from '@/components/icons/MIcon.vue'

const sessionStore = useSessionStore()

const props = defineProps({
  currentView: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['view-change'])

const { t } = useI18n()

const views = [
  { id: 'collab', icon: 'message-circle', label: 'views.collab.title' },
  { id: 'automation', icon: 'bolt', label: 'views.automation.title' },
  { id: 'knowledge', icon: 'book', label: 'views.knowledge.title' },
  { id: 'agents', icon: 'grid', label: 'views.agents.title' },
  { id: 'settings', icon: 'settings', label: 'views.settings.title' }
]

const handleViewClick = (viewId) => {
  emit('view-change', viewId)
}
</script>

<template>
  <aside class="view-selector">
    <div class="view-selector__logo">
      <div class="logo-icon">
        <MIcon name="dispatch" />
      </div>
    </div>

    <nav class="view-selector__nav">
      <button
        v-for="view in views"
        :key="view.id"
        :class="['view-selector__item', { 'view-selector__item--active': currentView === view.id }]"
        @click="handleViewClick(view.id)"
      >
        <MIcon :name="view.icon" />
        <span class="view-selector__label">{{ t(view.label) }}</span>
        <span
          v-if="view.id === 'collab' && sessionStore.hasUnreadSessions"
          class="view-selector__badge"
        ></span>
      </button>
    </nav>

    <!-- Status indicators at bottom -->
    <div class="view-selector__status">
      <slot name="status"></slot>
    </div>
  </aside>
</template>

<style scoped>
.view-selector {
  width: var(--view-selector-width);
  height: 100vh;
  background: var(--surface-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-4) 0;
  flex-shrink: 0;
  transition: width 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.view-selector:hover {
  width: 180px;
  align-items: flex-start;
}

.view-selector__logo {
  margin-bottom: var(--spacing-6);
  padding: 0 8px;
}

.logo-icon {
  width: 44px;
  height: 44px;
  background: var(--accent);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.view-selector__nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  width: 100%;
  padding: 0 var(--spacing-2);
}

.view-selector__item {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: var(--icon-lg);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
  flex-shrink: 0;
  padding: 0 12px;
}

.view-selector:hover .view-selector__item {
  width: 100%;
}

.view-selector__item:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.view-selector__item--active {
  background: rgba(184, 169, 201, 0.35);
  color: var(--text-primary);
}

.view-selector__item--active::before {
  content: '';
  position: absolute;
  left: -8px;
  width: 3px;
  height: 24px;
  background: var(--accent);
  border-radius: 0 var(--radius-md) var(--radius-md) 0;
}

/* Label: hidden by default, revealed on hover */
.view-selector__label {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  opacity: 0;
  max-width: 0;
  transition: opacity 0.15s ease, max-width 0.2s ease;
  color: inherit;
}

.view-selector:hover .view-selector__label {
  opacity: 1;
  max-width: 100px;
}

/* Unread badge */
.view-selector__badge {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: var(--error);
  border-radius: 50%;
}

.view-selector__status {
  width: 100%;
  padding: 0 var(--spacing-2);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}
</style>
