<script setup>
import { ref, computed, inject, onMounted, onUnmounted } from 'vue'
import { useTaskFiles } from '@/composables/useTaskFiles'
import { Command } from '@tauri-apps/plugin-shell'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: { type: String, default: null },
  sessionId: { type: String, default: null },
  width: { type: Number, default: 400 },
})

const emit = defineEmits(['close'])

const {
  files,
  filesLoading,
  currentDir,
  isAtRoot,
  relativePath,
  loadFiles,
  openEntry,
  goUp,
  goRoot,
  formatFileSize,
} = useTaskFiles({
  agentName: () => props.agentName,
  sessionId: () => props.sessionId,
})

// File drop upload
const collabDraftMessage = inject('collabDraftMessage', null)
const isDragging = ref(false)
let unlistenDragDrop = null

const handleFilesDrop = async (filePaths) => {
  if (!currentDir.value) return

  const isWindows = navigator.platform.startsWith('Win')
  const fileNames = []
  for (const srcPath of filePaths) {
    const fileName = srcPath.split('/').pop()
    const destPath = `${currentDir.value}/${fileName}`
    try {
      const cmd = isWindows
        ? Command.create('copy-file', ['cmd', '/C', 'copy', srcPath, destPath])
        : Command.create('copy-file', ['cp', srcPath, destPath])
      const output = await cmd.execute()
      if (output.code === 0) {
        fileNames.push(fileName)
      } else {
        console.error(`Failed to copy ${fileName}:`, output.stderr)
      }
    } catch (err) {
      console.error(`Failed to copy ${fileName}:`, err)
    }
  }

  if (fileNames.length > 0) {
    await loadFiles()
    if (collabDraftMessage) {
      collabDraftMessage.value = `I've uploaded these files:\n${fileNames.map(n => `- ${n}`).join('\n')}\n`
    }
  }
}

onMounted(async () => {
  const webview = await getCurrentWebview()
  unlistenDragDrop = await webview.onDragDropEvent(async (event) => {
    if (event.payload.type === 'over') {
      isDragging.value = true
    } else if (event.payload.type === 'drop') {
      isDragging.value = false
      const paths = event.payload.paths
      if (paths?.length > 0) {
        await handleFilesDrop(paths)
      }
    } else {
      isDragging.value = false
    }
  })
})

onUnmounted(() => {
  if (unlistenDragDrop) unlistenDragDrop()
})
</script>

<template>
  <div class="task-files-panel" :style="{ width: `${width}px` }">
    <!-- Header -->
    <div class="task-files-panel__header">
      <MIcon name="folder" />
      <span class="task-files-panel__title">Task Files</span>
      <button
        class="task-files-panel__refresh"
        @click="loadFiles"
        :disabled="filesLoading || !currentDir"
        title="Refresh"
      >
        <MIcon name="refresh" />
      </button>
      <button class="task-files-panel__close" @click="$emit('close')" title="Close">
        <MIcon name="x" />
      </button>
    </div>

    <!-- Path breadcrumb -->
    <div v-if="relativePath" class="task-files-panel__path-bar">
      <span class="task-files-panel__path-root" @click="goRoot">~/</span>
      <span class="task-files-panel__path-segments">{{ relativePath.replace(/^\//, '') }}</span>
    </div>

    <!-- File list -->
    <div class="task-files-panel__list">
      <div
        v-if="!isAtRoot"
        class="task-files-panel__file-item task-files-panel__file-item--parent"
        @dblclick="goUp"
      >
        <MIcon name="arrow-left" />
        <span class="task-files-panel__file-name">..</span>
      </div>
      <div
        v-for="entry in files"
        :key="entry.path"
        class="task-files-panel__file-item"
        @dblclick="openEntry(entry)"
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

    <!-- Drag-drop overlay -->
    <div v-if="isDragging" class="task-files-panel__drop-overlay">
      <MIcon name="upload" />
      <span>Drop files to upload</span>
    </div>
  </div>
</template>

<style scoped>
.task-files-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;
  border-left: 1px solid var(--neutral-200);
  flex-shrink: 0;
  overflow: hidden;
  z-index: 5;
}

.task-files-panel__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--neutral-200);
  flex-shrink: 0;
}

.task-files-panel__header .m-icon {
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

.task-files-panel__title {
  flex: 1;
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--neutral-600);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.task-files-panel__refresh,
.task-files-panel__close {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--neutral-400);
  cursor: pointer;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-sm);
  transition: all var(--duration-base) var(--ease-out);
}

.task-files-panel__refresh:hover:not(:disabled),
.task-files-panel__close:hover {
  background: var(--neutral-100);
  color: var(--neutral-600);
}

.task-files-panel__refresh:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.task-files-panel__path-bar {
  display: flex;
  align-items: center;
  padding: 2px var(--spacing-md);
  font-size: 10px;
  color: var(--neutral-400);
  background: var(--neutral-50);
  border-bottom: 1px solid var(--neutral-100);
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
  padding: var(--spacing-xs) 0;
  position: relative;
}

.task-files-panel__file-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 4px var(--spacing-md);
  font-size: var(--font-sm);
  color: var(--neutral-700);
  cursor: default;
  transition: background var(--duration-base) var(--ease-out);
}

.task-files-panel__file-item:hover {
  background: var(--neutral-50);
}

.task-files-panel__file-item .m-icon {
  font-size: var(--font-sm);
  color: var(--neutral-400);
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
  color: var(--neutral-400);
  flex-shrink: 0;
}

.task-files-panel__empty {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-xs);
  color: var(--neutral-400);
  font-style: italic;
}

.task-files-panel__drop-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--accent);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  border: 2px dashed var(--accent);
  border-radius: var(--radius-sm);
  z-index: 10;
  pointer-events: none;
}
</style>
