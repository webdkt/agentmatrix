<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-shell'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: {
    type: String,
    default: null
  }
})

const agentStore = useAgentStore()
const sessionStore = useSessionStore()
const websocketStore = useWebSocketStore()

// Use the selected session's session_id as task_id (they are the same value)
const currentSessionId = computed(() => sessionStore.currentSession?.session_id || null)

// ---- Collabring File ----

const collabFile = computed(() => {
  if (!props.agentName) return null
  return agentStore.getAgent(props.agentName)?.current_collab_file || null
})

const collabFileName = computed(() => {
  if (!collabFile.value) return null
  const parts = collabFile.value.split('/')
  return parts[parts.length - 1]
})

const openCollabFile = async () => {
  if (!collabFile.value) return
  try {
    await open(collabFile.value)
  } catch (err) {
    console.error('Failed to open collab file:', err)
  }
}

// ---- Current Task Files (File Manager) ----

const files = ref([])
const filesLoading = ref(false)
const rootDir = ref('')      // The work_files/{sessionId} base directory
const currentDir = ref('')   // The directory currently being browsed

async function getWorldPath() {
  const config = await invoke('get_config')
  return config.matrix_world_path
}

// Whether we're at the root of the task directory
const isAtRoot = computed(() => {
  return !rootDir.value || currentDir.value === rootDir.value
})

// Relative path from root (for breadcrumb display)
const relativePath = computed(() => {
  if (!rootDir.value || !currentDir.value) return ''
  const rel = currentDir.value.slice(rootDir.value.length)
  return rel || ''
})

const loadFiles = async () => {
  if (!currentDir.value) return
  filesLoading.value = true
  try {
    const entries = await invoke('read_directory', { path: currentDir.value })
    files.value = entries || []
  } catch (err) {
    console.error('Failed to load directory:', err)
    files.value = []
  } finally {
    filesLoading.value = false
  }
}

const initRootDir = async () => {
  if (!props.agentName || !currentSessionId.value) return
  const worldPath = await getWorldPath()
  rootDir.value = `${worldPath}/workspace/agent_files/${props.agentName}/work_files/${currentSessionId.value}`
  currentDir.value = rootDir.value
  await loadFiles()
}

const openEntry = async (entry) => {
  if (entry.is_dir) {
    // Navigate into directory
    currentDir.value = entry.path
    await loadFiles()
  } else {
    // Open file with system default app
    try {
      await open(entry.path)
    } catch (err) {
      console.error('Failed to open file:', err)
    }
  }
}

const goUp = async () => {
  if (isAtRoot.value) return
  // Go to parent directory, but not above root
  const parent = currentDir.value.replace(/\/[^/]+$/, '')
  if (parent.length >= rootDir.value.length) {
    currentDir.value = parent
  } else {
    currentDir.value = rootDir.value
  }
  await loadFiles()
}

const goRoot = async () => {
  if (!rootDir.value) return
  currentDir.value = rootDir.value
  await loadFiles()
}

const formatFileSize = (bytes) => {
  if (!bytes) return ''
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// ---- Agent Terminal ----

const terminalLines = ref([])
const terminalContainer = ref(null)
const MAX_TERMINAL_LINES = 500

const handleBashOutput = (data) => {
  const line = data?.data?.line
  if (!line) return
  terminalLines.value.push(line)
  if (terminalLines.value.length > MAX_TERMINAL_LINES) {
    terminalLines.value = terminalLines.value.slice(-MAX_TERMINAL_LINES)
  }
  nextTick(() => {
    if (terminalContainer.value) {
      terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight
    }
  })
}

// ---- Lifecycle ----

// Init file browser when both agent and session are available
watch([() => props.agentName, currentSessionId], ([agentName, sessionId]) => {
  if (agentName && sessionId) {
    initRootDir()
  } else {
    files.value = []
    rootDir.value = ''
    currentDir.value = ''
    terminalLines.value = []
  }
}, { immediate: true })

// Register COLLAB_BASH_OUTPUT listener
onMounted(() => {
  websocketStore.registerListener('COLLAB_BASH_OUTPUT', handleBashOutput)
})
</script>

<template>
  <aside class="collab-panel">
    <!-- Collabring File -->
    <section class="collab-panel__section collab-panel__collab-file">
      <div class="collab-panel__section-header">
        <MIcon name="file" />
        <span class="collab-panel__section-title">Collabring File</span>
      </div>
      <div
        v-if="collabFileName"
        class="collab-panel__file-link"
        @click="openCollabFile"
      >
        <MIcon name="external-link" />
        <span class="collab-panel__file-name">{{ collabFileName }}</span>
      </div>
      <div v-else class="collab-panel__empty-hint">
        No collab file
      </div>
    </section>

    <!-- Current Task Files -->
    <section class="collab-panel__section collab-panel__files">
      <div class="collab-panel__section-header">
        <MIcon name="folder" />
        <span class="collab-panel__section-title">Task Files</span>
        <button
          class="collab-panel__refresh-btn"
          @click="loadFiles"
          :disabled="filesLoading || !currentDir"
          title="Refresh"
        >
          <MIcon name="refresh" />
        </button>
      </div>
      <!-- Path breadcrumb -->
      <div v-if="relativePath" class="collab-panel__path-bar">
        <span class="collab-panel__path-root" @click="goRoot">~/</span>
        <span class="collab-panel__path-segments">{{ relativePath.replace(/^\//, '') }}</span>
      </div>
      <div class="collab-panel__file-list">
        <!-- Parent directory entry -->
        <div
          v-if="!isAtRoot"
          class="collab-panel__file-item collab-panel__file-item--parent"
          @dblclick="goUp"
        >
          <MIcon name="arrow-left" />
          <span class="collab-panel__file-item-name">..</span>
        </div>
        <!-- Directory entries (sorted first by Rust) -->
        <div
          v-for="entry in files"
          :key="entry.path"
          class="collab-panel__file-item"
          @dblclick="openEntry(entry)"
        >
          <MIcon :name="entry.is_dir ? 'folder' : 'file-text'" />
          <span class="collab-panel__file-item-name">{{ entry.name }}</span>
          <span v-if="!entry.is_dir && entry.size" class="collab-panel__file-item-size">
            {{ formatFileSize(entry.size) }}
          </span>
        </div>
        <div v-if="files.length === 0 && !filesLoading" class="collab-panel__empty-hint">
          Empty directory
        </div>
        <div v-if="filesLoading" class="collab-panel__empty-hint">
          Loading...
        </div>
      </div>
    </section>

    <!-- Agent Terminal -->
    <section class="collab-panel__section collab-panel__terminal">
      <div class="collab-panel__section-header">
        <MIcon name="terminal" />
        <span class="collab-panel__section-title">Terminal</span>
      </div>
      <div ref="terminalContainer" class="collab-panel__terminal-output">
        <pre v-if="terminalLines.length > 0" class="collab-panel__terminal-pre">{{ terminalLines.join('') }}</pre>
        <div v-else class="collab-panel__empty-hint">
          No output
        </div>
      </div>
    </section>
  </aside>
</template>

<style scoped>
.collab-panel {
  width: 0; /* Width controlled by parent via inline style */
  height: 100%;
  background: white;
  border-left: 1px solid var(--neutral-200);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  overflow: hidden;
}

/* Sections */
.collab-panel__section {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.collab-panel__collab-file {
  flex-shrink: 0;
  border-bottom: 1px solid var(--neutral-200);
}

.collab-panel__files {
  flex: 1;
  min-height: 0;
  border-bottom: 1px solid var(--neutral-200);
}

.collab-panel__terminal {
  height: 200px;
  flex-shrink: 0;
}

/* Section header */
.collab-panel__section-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--neutral-100);
  flex-shrink: 0;
}

.collab-panel__section-header .m-icon {
  font-size: var(--font-sm);
  color: var(--neutral-400);
}

.collab-panel__section-title {
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--neutral-600);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  flex: 1;
}

.collab-panel__refresh-btn {
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

.collab-panel__refresh-btn:hover:not(:disabled) {
  background: var(--neutral-100);
  color: var(--neutral-600);
}

.collab-panel__refresh-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* Collab file link */
.collab-panel__file-link {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: var(--spacing-sm) var(--spacing-md);
  cursor: pointer;
  color: var(--accent);
  font-size: var(--font-sm);
  transition: background var(--duration-base) var(--ease-out);
}

.collab-panel__file-link:hover {
  background: var(--neutral-50);
}

.collab-panel__file-link .m-icon {
  font-size: var(--font-sm);
  flex-shrink: 0;
}

.collab-panel__file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Path breadcrumb */
.collab-panel__path-bar {
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

.collab-panel__path-root {
  cursor: pointer;
  color: var(--accent);
  flex-shrink: 0;
}

.collab-panel__path-root:hover {
  text-decoration: underline;
}

.collab-panel__path-segments {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* File list */
.collab-panel__file-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xs) 0;
}

.collab-panel__file-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 4px var(--spacing-md);
  font-size: var(--font-sm);
  color: var(--neutral-700);
  cursor: default;
  transition: background var(--duration-base) var(--ease-out);
}

.collab-panel__file-item:hover {
  background: var(--neutral-50);
}

.collab-panel__file-item .m-icon {
  font-size: var(--font-sm);
  color: var(--neutral-400);
  flex-shrink: 0;
}

.collab-panel__file-item-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.collab-panel__file-item-size {
  font-size: 10px;
  color: var(--neutral-400);
  flex-shrink: 0;
}

/* Terminal */
.collab-panel__terminal-output {
  flex: 1;
  overflow-y: auto;
  background: var(--neutral-900);
  padding: var(--spacing-sm);
}

.collab-panel__terminal-pre {
  margin: 0;
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--neutral-200);
  white-space: pre-wrap;
  word-break: break-all;
}

/* Empty hint */
.collab-panel__empty-hint {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-xs);
  color: var(--neutral-400);
  font-style: italic;
}

.animate-spin {
  animation: spin 1s linear infinite;
  display: inline-flex;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>
