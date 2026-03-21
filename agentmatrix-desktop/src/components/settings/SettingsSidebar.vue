<script setup>
import { computed } from 'vue'

const props = defineProps({
  categories: {
    type: Array,
    required: true
  },
  currentCategory: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['category-change'])

const handleCategoryClick = (categoryId) => {
  emit('category-change', categoryId)
}

const isActive = (categoryId) => {
  return props.currentCategory === categoryId
}
</script>

<template>
  <aside class="settings-sidebar">
    <nav class="sidebar-nav">
      <button
        v-for="category in categories"
        :key="category.id"
        @click="handleCategoryClick(category.id)"
        :class="['nav-item', { active: isActive(category.id) }]"
        :title="category.description"
      >
        <div class="nav-item-icon-wrapper">
          <i :class="['ti', category.icon, 'nav-item-icon']"></i>
        </div>
        <div class="nav-item-content">
          <span class="nav-item-label">{{ category.label }}</span>
          <span class="nav-item-description">{{ category.description }}</span>
        </div>
      </button>
    </nav>
  </aside>
</template>

<style scoped>
.settings-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: var(--neutral-100);
  border-right: 1px solid var(--neutral-200);
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-nav {
  padding: var(--spacing-md);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
  border-radius: var(--radius-sm);
  border: 1px solid transparent;
  background: transparent;
  color: var(--neutral-600);
  text-align: left;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  width: 100%;
}

.nav-item:hover {
  background: var(--parchment-50);
  border-color: transparent;
  color: var(--neutral-900);
}

.nav-item.active {
  background: var(--parchment-50);
  border-left: 2px solid var(--accent);
  border-color: transparent;
  border-left-color: var(--accent);
  color: var(--neutral-900);
}

.nav-item-icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--neutral-200);
  transition: all var(--duration-base) var(--ease-out);
}

.nav-item:hover .nav-item-icon-wrapper {
  background: var(--neutral-300);
}

.nav-item.active .nav-item-icon-wrapper {
  background: var(--accent);
  color: white;
}

.nav-item-icon {
  font-size: var(--icon-lg);
  color: inherit;
}

.nav-item-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.nav-item-label {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: inherit;
  display: block;
}

.nav-item-description {
  font-size: var(--font-xs);
  color: var(--neutral-500);
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.nav-item.active .nav-item-description {
  color: var(--neutral-600);
}
</style>
