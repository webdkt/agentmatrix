<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, inject } from 'vue'
import { useAgentStore } from '@/stores/agent'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { agentAPI } from '@/api/agent'
import { invoke } from '@tauri-apps/api/core'
import { getCurrentWebview } from '@tauri-apps/api/webview'
import { Command } from '@tauri-apps/plugin-shell'
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
    await invoke('open_folder', { path: collabFile.value })
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
  // 跳过 placeholder session（目录尚不存在）
  if (sessionStore.currentSession?._isPlaceholder) return
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
      await invoke('open_folder', { path: entry.path })
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

// ---- Vertical resize (Task Files / Terminal) ----

const filesSectionHeight = ref(0) // 0 means use flex ratio
const isResizingVertical = ref(false)
let verticalStartY = 0
let verticalStartHeight = 0

function onVerticalDividerDown(e) {
  isResizingVertical.value = true
  verticalStartY = e.clientY
  // Get current pixel height of the files section
  const filesEl = e.target.previousElementSibling
  verticalStartHeight = filesEl?.offsetHeight || 200
  document.addEventListener('mousemove', onVerticalDividerMove)
  document.addEventListener('mouseup', onVerticalDividerUp)
  e.preventDefault()
}

function onVerticalDividerMove(e) {
  if (!isResizingVertical.value) return
  const delta = e.clientY - verticalStartY
  const newHeight = Math.max(80, verticalStartHeight + delta)
  filesSectionHeight.value = newHeight
}

function onVerticalDividerUp() {
  isResizingVertical.value = false
  document.removeEventListener('mousemove', onVerticalDividerMove)
  document.removeEventListener('mouseup', onVerticalDividerUp)
}

const filesSectionStyle = computed(() => {
  if (filesSectionHeight.value > 0) {
    return { flex: 'none', height: `${filesSectionHeight.value}px` }
  }
  return {}
})

const formatFileSize = (bytes) => {
  if (!bytes) return ''
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

// ---- File Drop Upload ----

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

// ---- Agent Terminal ----

// Each line: { type: 'stdin'|'stdout'|'stderr', text: string }
const terminalLines = ref([])
const terminalContainer = ref(null)
const MAX_TERMINAL_LINES = 500

const STDIN_MAX_CHARS = 200
const OUTPUT_MAX_LINES = 15

const handleBashOutput = (data) => {
  const stream = data?.data?.stream
  const line = data?.data?.line
  if (!line) return

  const entry = { type: stream || 'stdout', text: line, truncated: false, collapsed: true }

  // Truncate long stdin commands
  if (entry.type === 'stdin' && line.length > STDIN_MAX_CHARS) {
    entry.truncated = true
    entry.shortText = line.slice(0, STDIN_MAX_CHARS) + '...'
  }

  // Truncate long output: accumulate and collapse
  if (entry.type !== 'stdin' && line.split('\n').length > 1) {
    const lines = line.split('\n')
    if (lines.length > OUTPUT_MAX_LINES) {
      entry.truncated = true
      entry.shortText = lines.slice(0, OUTPUT_MAX_LINES).join('\n')
      entry.hiddenLines = lines.length - OUTPUT_MAX_LINES
    }
  }

  terminalLines.value.push(entry)
  if (terminalLines.value.length > MAX_TERMINAL_LINES) {
    terminalLines.value = terminalLines.value.slice(-MAX_TERMINAL_LINES)
  }
  nextTick(scrollTerminalToBottom)
}

// ---- Terminal Input ----

const userInput = ref('')
const isExecuting = ref(false)

const INTERACTIVE_BLACKLIST = [
  'vi', 'vim', 'nvim', 'nano', 'emacs',
  'top', 'htop', 'btop', 'iotop',
  'less', 'more', 'man',
  'watch', 'tail -f',
  'python', 'python3', 'node', 'irb', 'php -a',
  'ssh', 'telnet', 'ftp', 'sftp',
]

const isBlacklisted = (cmd) => {
  const first = cmd.trim().split(/\s+/)[0].toLowerCase()
  return INTERACTIVE_BLACKLIST.includes(first)
}

const handleTerminalSubmit = async () => {
  const cmd = userInput.value.trim()
  if (!cmd || !props.agentName || isExecuting.value) return

  if (isBlacklisted(cmd)) {
    terminalLines.value.push({
      type: 'stderr',
      text: `Command '${cmd.split(/\s+/)[0]}' is not supported (interactive programs require a real terminal)`
    })
    userInput.value = ''
    return
  }

  isExecuting.value = true
  userInput.value = ''
  // stdin line is mirrored by backend via _output_callback, no need to push here

  try {
    const result = await agentAPI.terminalExec(props.agentName, cmd)
    if (result.timeout) {
      terminalLines.value.push({
        type: 'stderr',
        text: '[Command timed out after 10s]'
      })
    }
    // Note: stdout/stderr output already arrives via WebSocket mirror
    // We only need to handle timeout here
  } catch (err) {
    terminalLines.value.push({
      type: 'stderr',
      text: `[Error: ${err.message}]`
    })
  } finally {
    isExecuting.value = false
  }
}

function scrollTerminalToBottom() {
  if (terminalContainer.value) {
    terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight
  }
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

// Register COLLAB_BASH_OUTPUT listener + Tauri drag-drop
onMounted(async () => {
  websocketStore.registerListener('COLLAB_BASH_OUTPUT', handleBashOutput)

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
    <section class="collab-panel__section collab-panel__files" :style="filesSectionStyle">
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
      <!-- Drag-drop overlay -->
      <div v-if="isDragging" class="collab-panel__drop-overlay">
        <MIcon name="upload" />
        <span>Drop files to upload</span>
      </div>
    </section>

    <!-- Vertical divider between Task Files and Terminal -->
    <div
      class="collab-panel__vdivider"
      :class="{ 'collab-panel__vdivider--dragging': isResizingVertical }"
      @mousedown="onVerticalDividerDown"
    >
      <div class="collab-panel__vdivider-handle"></div>
    </div>

    <!-- Agent Terminal -->
    <section class="collab-panel__section collab-panel__terminal">
      <div class="collab-panel__section-header">
        <MIcon name="terminal" />
        <span class="collab-panel__section-title">Terminal</span>
      </div>
      <div ref="terminalContainer" class="collab-panel__terminal-output">
        <div v-if="terminalLines.length > 0" class="collab-panel__terminal-pre">
          <div
            v-for="(entry, i) in terminalLines"
            :key="i"
            :class="['terminal-line', `terminal-line--${entry.type}`]"
          >
            <!-- Long stdin: truncated with expand -->
            <template v-if="entry.type === 'stdin' && entry.truncated">
              <span class="terminal-line__typewriter">{{ entry.collapsed ? entry.shortText : entry.text }}</span>
              <span class="terminal-line__toggle" @click="entry.collapsed = !entry.collapsed">
                {{ entry.collapsed ? '[show more]' : '[collapse]' }}
              </span>
            </template>
            <!-- Normal stdin -->
            <span v-else-if="entry.type === 'stdin'" class="terminal-line__typewriter">{{ entry.text }}</span>
            <!-- Long output: truncated with expand -->
            <template v-else-if="entry.truncated">
              {{ entry.collapsed ? entry.shortText : entry.text }}
              <span class="terminal-line__toggle" @click="entry.collapsed = !entry.collapsed">
                {{ entry.collapsed ? `[+${entry.hiddenLines} more lines]` : '[collapse]' }}
              </span>
            </template>
            <!-- Normal output -->
            <template v-else>{{ entry.text }}</template>
          </div>
          <!-- Active prompt line (only when not executing) -->
          <div v-if="!isExecuting" class="terminal-line terminal-line--prompt">
            <span class="terminal-prompt-cursor">$&nbsp;<span class="terminal-cursor"></span></span>
          </div>
        </div>
        <div v-else class="collab-panel__terminal-empty">
          <span class="terminal-prompt-cursor">$&nbsp;<span class="terminal-cursor"></span></span>
        </div>
      </div>
      <!-- Terminal input -->
      <div class="collab-panel__terminal-input">
        <span class="collab-panel__terminal-prompt">$</span>
        <input
          v-model="userInput"
          type="text"
          :disabled="isExecuting"
          :placeholder="isExecuting ? 'Agent is running...' : 'Type a command...'"
          class="collab-panel__terminal-field"
          @keydown.enter="handleTerminalSubmit"
        />
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
  flex: 2;
  min-height: 0;
  border-bottom: 1px solid var(--neutral-200);
  position: relative;
}

.collab-panel__terminal {
  flex: 3;
  min-height: 0;
  flex-shrink: 0;
}

/* Vertical divider between Task Files and Terminal */
.collab-panel__vdivider {
  height: 4px;
  background: var(--neutral-200);
  cursor: row-resize;
  flex-shrink: 0;
  position: relative;
  transition: background 0.15s ease;
  user-select: none;
}

.collab-panel__vdivider:hover {
  background: var(--neutral-300);
}

.collab-panel__vdivider--dragging {
  background: var(--accent);
}

.collab-panel__vdivider-handle {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 40px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.collab-panel__vdivider-handle::before,
.collab-panel__vdivider-handle::after {
  content: '';
  position: absolute;
  width: 12px;
  height: 2px;
  background: var(--ink-400);
  border-radius: 1px;
}

.collab-panel__vdivider:hover .collab-panel__vdivider-handle,
.collab-panel__vdivider--dragging .collab-panel__vdivider-handle {
  opacity: 1;
}

.collab-panel__vdivider--dragging .collab-panel__vdivider-handle::before,
.collab-panel__vdivider--dragging .collab-panel__vdivider-handle::after {
  background: white;
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
  background: #1e1e1e;
  padding: var(--spacing-sm);
}

.collab-panel__terminal-empty {
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  color: #d4d4d4;
  padding: var(--spacing-sm);
}

.terminal-prompt-prefix {
  color: #569cd6;
}

.collab-panel__terminal-pre {
  margin: 0;
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.terminal-line {
  color: #d4d4d4;
}

.terminal-line--stdin {
  color: #6a9955;
  font-weight: var(--font-semibold);
}

.terminal-line--stderr {
  color: #f44747;
}

.terminal-line__toggle {
  color: #569cd6;
  cursor: pointer;
  font-size: 10px;
  margin-left: 4px;
}

.terminal-line__toggle:hover {
  text-decoration: underline;
}

/* Typewriter effect for agent commands (no cursor — cursor is on the prompt line) */
.terminal-line__typewriter {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  animation: typewriter 0.4s steps(30, end) forwards;
  max-width: 0;
}

@keyframes typewriter {
  from { max-width: 0 }
  to { max-width: 100% }
}

/* Active prompt line with blinking cursor */
.terminal-line--prompt {
  color: #d4d4d4;
}

.terminal-prompt-cursor {
  color: #6a9955;
}

.terminal-cursor {
  display: inline-block;
  width: 8px;
  height: 14px;
  background: #d4d4d4;
  vertical-align: text-bottom;
  animation: blink-cursor 1s step-end infinite;
}

@keyframes blink-cursor {
  50% { opacity: 0 }
}

/* Terminal input */
.collab-panel__terminal-input {
  display: flex;
  align-items: center;
  gap: 0;
  background: #1e1e1e;
  border-top: 1px solid #333;
  flex-shrink: 0;
}

.collab-panel__terminal-prompt {
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  color: #6a9955;
  padding: 6px 0 6px var(--spacing-sm);
  flex-shrink: 0;
  user-select: none;
}

.collab-panel__terminal-field {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #d4d4d4;
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  padding: 6px var(--spacing-sm);
  caret-color: #d4d4d4;
}

.collab-panel__terminal-field::placeholder {
  color: #555;
}

.collab-panel__terminal-field:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Empty hint */
.collab-panel__empty-hint {
  padding: var(--spacing-sm) var(--spacing-md);
  font-size: var(--font-xs);
  color: var(--neutral-400);
  font-style: italic;
}

/* Drag-drop overlay */
.collab-panel__drop-overlay {
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

.animate-spin {
  animation: spin 1s linear infinite;
  display: inline-flex;
}

@keyframes spin {
  to { transform: rotate(360deg) }
}
</style>
