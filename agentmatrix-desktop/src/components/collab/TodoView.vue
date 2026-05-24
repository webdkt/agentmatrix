<script setup>
import { computed } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  todos: { type: Object, required: true },  // {index: {item, status}}
  isLoaded: { type: Boolean, default: false },
})

const sortedEntries = computed(() => {
  return Object.entries(props.todos)
    .sort(([a], [b]) => {
      const na = parseInt(a), nb = parseInt(b)
      if (!isNaN(na) && !isNaN(nb)) return na - nb
      return a.localeCompare(b)
    })
})

const statusConfig = {
  planned: { icon: 'circle', cls: 'todo-item--planned' },
  working: { icon: 'loader', cls: 'todo-item--working' },
  done: { icon: 'check-circle', cls: 'todo-item--done' },
  canceled: { icon: 'x-circle', cls: 'todo-item--canceled' },
}
</script>

<template>
  <div class="todo-view">
    <!-- Loading -->
    <div v-if="!isLoaded" class="todo-view__loading">
      <span class="animate-spin"><MIcon name="loader" /></span>
    </div>

    <!-- Empty -->
    <div v-else-if="!sortedEntries.length" class="todo-view__empty">
      No Todo Defined
    </div>

    <!-- Item list -->
    <div v-else class="todo-view__items">
      <div
        v-for="[idx, entry] in sortedEntries"
        :key="idx"
        class="todo-item"
        :class="statusConfig[entry.status]?.cls || ''"
      >
        <MIcon :name="statusConfig[entry.status]?.icon || 'circle'" class="todo-item__icon" :class="{ 'animate-spin': entry.status === 'working' }" />
        <span class="todo-item__index">{{ idx }}.</span>
        <span class="todo-item__text">{{ entry.item }}</span>
        <span class="todo-item__status">{{ entry.status }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.todo-view {
  padding: 8px 10px;
  min-height: 40px;
  user-select: none;
}
.todo-view__loading {
  display: flex; align-items: center; justify-content: center;
  padding: 16px; color: var(--text-quaternary); font-size: 12px;
}
.todo-view__empty {
  color: var(--text-quaternary); font-size: 11px;
  text-align: center; padding: 20px 0; font-style: italic;
}

.todo-view__items {
  display: flex; flex-direction: column; gap: 4px;
}

.todo-item {
  display: flex; align-items: center; gap: 5px;
  font-size: 12px; line-height: 1.4;
  padding: 4px 6px; border-radius: 4px;
  background: var(--surface-secondary);
}

.todo-item__icon {
  font-size: 12px; flex-shrink: 0;
}

.todo-item__index {
  font-size: 11px; font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0; min-width: 18px;
}

.todo-item__text {
  flex: 1; color: var(--text-primary);
  white-space: pre-wrap; word-break: break-word;
}

.todo-item__status {
  font-size: 10px; font-weight: 600;
  padding: 1px 5px; border-radius: 3px;
  flex-shrink: 0; text-transform: capitalize;
}

/* Status variants */
.todo-item--planned .todo-item__icon { color: var(--text-tertiary); }
.todo-item--planned .todo-item__status {
  background: var(--surface-hover); color: var(--text-tertiary);
}

.todo-item--working .todo-item__icon { color: var(--accent); }
.todo-item--working .todo-item__status {
  background: color-mix(in srgb, var(--accent) 15%, transparent);
  color: var(--accent);
}

.todo-item--done .todo-item__icon { color: var(--success, #10b981); }
.todo-item--done .todo-item__text {
  text-decoration: line-through; color: var(--text-tertiary);
}
.todo-item--done .todo-item__status {
  background: color-mix(in srgb, var(--success, #10b981) 15%, transparent);
  color: var(--success, #10b981);
}

.todo-item--canceled .todo-item__icon { color: var(--text-quaternary); }
.todo-item--canceled .todo-item__text {
  text-decoration: line-through; color: var(--text-quaternary);
}
.todo-item--canceled .todo-item__status {
  background: var(--surface-hover); color: var(--text-quaternary);
}
</style>
