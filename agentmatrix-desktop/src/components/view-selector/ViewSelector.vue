<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  currentView: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['view-change'])

const { t } = useI18n()

const views = [
  { id: 'dashboard', icon: 'ti-layout-dashboard', label: 'views.dashboard.title' },
  { id: 'email', icon: 'ti-mail', label: 'views.email.title' },
  { id: 'matrix', icon: 'ti-grid', label: 'views.matrix.title' },
  { id: 'magic', icon: 'ti-wand', label: 'views.magic.title' },
  { id: 'settings', icon: 'ti-settings', label: 'views.settings.title' }
]

const handleViewClick = (viewId) => {
  emit('view-change', viewId)
}
</script>

<template>
  <aside class="view-selector">
    <div class="view-selector__logo">
      <div class="logo-icon">
        <i class="ti ti-robot"></i>
      </div>
    </div>

    <nav class="view-selector__nav">
      <button
        v-for="view in views"
        :key="view.id"
        :class="['view-selector__item', { 'view-selector__item--active': currentView === view.id }]"
        :title="t(view.label)"
        @click="handleViewClick(view.id)"
      >
        <i :class="['view-selector__icon', view.icon]"></i>
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
  background: var(--neutral-100);
  border-right: 1px solid var(--neutral-200);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-md) 0;
  flex-shrink: 0;
}

.view-selector__logo {
  margin-bottom: var(--spacing-lg);
}

.logo-icon {
  width: 44px;
  height: 44px;
  background: var(--primary-500);
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
  box-shadow: var(--shadow-sm);
}

.view-selector__nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  width: 100%;
  padding: 0 var(--spacing-sm);
}

.view-selector__item {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--neutral-500);
  font-size: var(--icon-lg);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.view-selector__item:hover {
  background: var(--neutral-200);
  color: var(--neutral-700);
}

.view-selector__item--active {
  background: var(--primary-50);
  color: var(--primary-600);
}

.view-selector__item--active::before {
  content: '';
  position: absolute;
  left: -8px;
  width: 3px;
  height: 24px;
  background: var(--primary-500);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.view-selector__icon {
  font-size: var(--icon-lg);
}

.view-selector__status {
  width: 100%;
  padding: 0 var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

/* Tooltip styles */
.view-selector__item[title]:hover::after {
  content: attr(title);
  position: absolute;
  left: calc(100% + 12px);
  top: 50%;
  transform: translateY(-50%);
  background: var(--neutral-800);
  color: white;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--duration-fast) var(--ease-out);
  z-index: var(--z-tooltip);
}

.view-selector__item[title]:hover::after {
  opacity: 1;
}
</style>
