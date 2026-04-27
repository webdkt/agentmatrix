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
  selectedFiles: { type: Object, default: () => new Set() },
  contextMenu: { type: Object, default: () => ({ show: false }) },
})

const emit = defineEmits(['load-files', 'open-entry', 'go-up', 'go-root', 'close', 'select-file', 'contextmenu', 'hide-context-menu', 'menu-action'])

const isFileSelected = (path) => props.selectedFiles.has(path)

const handleFileClick = (entry, event) => {
  // 阻止双击触发单击
  if (event.detail === 2) return
  emit('select-file', entry, event)
}

const handleContextMenu = (entry, event) => {
  emit('contextmenu', entry, event)
}

const formatFileSize = (bytes) => {
  if (!bytes) return ''
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
</script>

<template>
  <div class="task-files-panel" data-drop-zone="task-files" :style="{ width: `${width}px` }" @click="emit('hide-context-menu')">
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
        :class="{ 'task-files-panel__file-item--selected': isFileSelected(entry.path) }"
        @click="handleFileClick(entry, $event)"
        @dblclick="emit('open-entry', entry)"
        @contextmenu="handleContextMenu(entry, $event)"
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

    <!-- 右键菜单 -->
    <div
      v-if="contextMenu.show"
      class="task-files-panel__context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      @click.stop
    >
      <button @click="emit('menu-action', 'reveal')" class="task-files-panel__menu-item">
        <MIcon name="external-link" />
        <span>在文件管理器中显示</span>
      </button>
      <button @click="emit('menu-action', 'copy')" class="task-files-panel__menu-item">
        <MIcon name="copy" />
        <span>复制到本地</span>
      </button>
      <button @click="emit('menu-action', 'delete')" class="task-files-panel__menu-item task-files-panel__menu-item--danger">
        <MIcon name="trash" />
        <span>删除</span>
      </button>
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

.task-files-panel__file-item--selected {
  background: var(--accent-soft);
  border-left: 3px solid var(--accent);
  padding-left: calc(var(--spacing-4) - 3px);
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

.task-files-panel__context-menu {
  position: fixed;
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  min-width: 160px;
  z-index: var(--z-dropdown);
  overflow: hidden;
  animation: menuFadeIn 0.15s ease-out;
}

@keyframes menuFadeIn {
  from {
    opacity: 0;
    transform: scale(0.95);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.task-files-panel__menu-item {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--font-sm);
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.task-files-panel__menu-item:hover {
  background: var(--surface-hover);
}

.task-files-panel__menu-item--danger {
  color: var(--error);
}

.task-files-panel__menu-item .m-icon {
  font-size: var(--font-sm);
}
</style>
