<script setup>
import MIcon from '@/components/icons/MIcon.vue'

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

const emit = defineEmits(['category-change', 'back'])
</script>

<template>
  <aside class="settings-sidebar">
    <div class="sidebar-top">
      <button class="back-btn" @click="emit('back')">
        <MIcon name="arrow-left" class="back-icon" />
        <span>返回</span>
      </button>
    </div>

    <nav class="sidebar-nav">
      <button
        v-for="cat in categories"
        :key="cat.id"
        :class="['nav-item', { active: props.currentCategory === cat.id }]"
        @click="emit('category-change', cat.id)"
      >
        <div class="nav-indicator" />
        <MIcon :name="cat.icon" class="nav-icon" />
        <div class="nav-text">
          <span class="nav-label">{{ cat.labelZh }}</span>
          <span class="nav-sublabel">{{ cat.label }}</span>
        </div>
      </button>
    </nav>
  </aside>
</template>

<style scoped>
.settings-sidebar {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: white;
  border-right: 1px solid var(--border);
  padding: 20px 16px;
  gap: 24px;
}

.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
  color: var(--text-secondary);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  width: fit-content;
}

.back-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
  border-color: var(--border-strong);
}

.back-icon {
  font-size: 14px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: none;
  border-radius: var(--radius-lg);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  text-align: left;
  width: 100%;
  position: relative;
  transition: all var(--duration-base) var(--ease-out);
}

.nav-item:hover {
  background: var(--surface-secondary);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--surface-secondary);
  color: var(--text-primary);
}

.nav-indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 0;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
  transition: height var(--duration-base) var(--ease-out);
}

.nav-item.active .nav-indicator {
  height: 20px;
}

.nav-icon {
  font-size: 20px;
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity var(--duration-base) var(--ease-out);
}

.nav-item:hover .nav-icon,
.nav-item.active .nav-icon {
  opacity: 1;
  color: var(--accent);
}

.nav-text {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.nav-label {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  line-height: 1.3;
}

.nav-sublabel {
  font-size: 11px;
  font-weight: var(--font-normal);
  color: var(--text-tertiary);
  line-height: 1.3;
}
</style>
