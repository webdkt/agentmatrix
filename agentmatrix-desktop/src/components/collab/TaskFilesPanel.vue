<script setup>
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  width: { type: Number, default: 400 },
  files: { type: Array, default: () => [] },
  filesLoading: { type: Boolean, default: false },
  currentDir: { type: String, default: '' },
  rootDir: { type: String, default: '' },
  isAtRoot: { type: Boolean, default: true },
  relativePath: { type: String, default: '' },
})

const emit = defineEmits(['load-files', 'open-entry', 'go-up', 'go-root', 'close'])

const formatFileSize = (bytes) => {
  if (!bytes) return ''
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
</script>

<template>
  <div class="task-files-panel" data-drop-zone="task-files" :style="{ width: `${width}px` }">
    <!-- Header -->
    <div class="task-files-panel__header">
      <MIcon name="folder" />
      <span class="task-files-panel__title">Task Files</span>
      <button
        class="task-files-panel__refresh"
        @click="emit('load-files')"
        :disabled="filesLoading || !currentDir"
        title="Refresh"
      >
        <MIcon name="refresh" />
      </button>
      <button class="task-files-panel__close" @click="emit('close')" title="Close">
        <MIcon name="x" />
      </button>
    </div>

    <!-- Path breadcrumb -->
    <div v-if="relativePath" class="task-files-panel__path-bar">
      <span class="task-files-panel__path-root" @click="emit('go-root')">~/</span>
      <span class="task-files-panel__path-segments">{{ relativePath.replace(/^\//, '') }}</span>
    </div>

    <!-- File list -->
    <div class="task-files-panel__list">
      <div
        v-if="!isAtRoot"
        class="task-files-panel__file-item task-files-panel__file-item--parent"
        @dblclick="emit('go-up')"
      >
        <MIcon name="arrow-left" />
        <span class="task-files-panel__file-name">..</span>
      </div>
      <div
        v-for="entry in files"
        :key="entry.path"
        class="task-files-panel__file-item"
        @dblclick="emit('open-entry', entry)"
      >
        <MIcon :name="entry.is_dir ? 'folder' : 'file-text'" />
        <span class="task-files-panel__file-name">{{ entry.name }}</span>
        <span v-if="!entry.is_dir && entry.size" class="task-files-panel__file-size">
          {{ formatFileSize(entry.size) }}
        </span>
      </div>
      <div v-if="files.length === 0 && !filesLoading" class="task-files-panel__empty">
        Empty directory
      </div>
      <div v-if="filesLoading" class="task-files-panel__empty">
        Loading...
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-files-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;
  border-left: 1px solid var(--border);
  flex-shrink: 0;
  overflow: hidden;
  z-index: 5;
}

.task-files-panel__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-2) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.task-files-panel__header .m-icon {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
}

.task-files-panel__title {
  flex: 1;
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
}

.task-files-panel__refresh,
.task-files-panel__close {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-sm);
  transition: all var(--duration-base) var(--ease-out);
}

.task-files-panel__refresh:hover:not(:disabled),
.task-files-panel__close:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.task-files-panel__refresh:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.task-files-panel__path-bar {
  display: flex;
  align-items: center;
  padding: 2px var(--spacing-4);
  font-size: 10px;
  color: var(--text-tertiary);
  background: var(--surface-base);
  border-bottom: 1px solid var(--surface-hover);
  flex-shrink: 0;
  overflow: hidden;
}

.task-files-panel__path-root {
  cursor: pointer;
  color: var(--accent);
  flex-shrink: 0;
}

.task-files-panel__path-root:hover {
  text-decoration: underline;
}

.task-files-panel__path-segments {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-files-panel__list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-1) 0;
  position: relative;
}

.task-files-panel__file-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: 4px var(--spacing-4);
  font-size: var(--font-sm);
  color: var(--text-secondary);
  cursor: default;
  transition: background var(--duration-base) var(--ease-out);
}

.task-files-panel__file-item:hover {
  background: var(--surface-base);
}

.task-files-panel__file-item .m-icon {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.task-files-panel__file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-files-panel__file-size {
  font-size: 10px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.task-files-panel__empty {
  padding: var(--spacing-2) var(--spacing-4);
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  font-style: italic;
}
</style>
