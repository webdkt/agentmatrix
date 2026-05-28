<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useWhiteboard } from '@/composables/useWhiteboard'
import { useTodo } from '@/composables/useTodo'
import WhiteboardView from './WhiteboardView.vue'
import TodoView from './TodoView.vue'
import TaskFilesPanel from './TaskFilesPanel.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: { type: String, required: true },
  sessionId: { type: String, required: true },
  // Task files props (passed from AgentSessionPanel)
  files: { type: Array, default: () => [] },
  filesLoading: { type: Boolean, default: false },
  currentDir: { type: String, default: '' },
  rootDir: { type: String, default: '' },
  isAtRoot: { type: Boolean, default: true },
  relativePath: { type: String, default: '' },
  selectedFiles: { type: Object, default: () => new Set() },
  contextMenu: { type: Object, default: () => ({ show: false }) },
})

const emit = defineEmits([
  'load-files', 'open-entry', 'go-up', 'go-root',
  'select-file', 'contextmenu', 'hide-context-menu', 'menu-action',
])

const whiteboard = useWhiteboard({
  agentName: () => props.agentName,
  sessionId: () => props.sessionId,
})

const todo = useTodo({
  agentName: () => props.agentName,
  sessionId: () => props.sessionId,
})

// ---- Accordion ----
const expandedSection = ref('whiteboard')

function toggleSection(name) {
  expandedSection.value = expandedSection.value === name ? null : name
}

function switchTab(name) {
  expandedSection.value = name
}

// ---- Auto-switch tab on file change ----
watch(() => whiteboard.version.value, (v) => {
  if (v > 0 && expandedSection.value !== 'whiteboard') expandedSection.value = 'whiteboard'
})
watch(() => todo.version.value, (v) => {
  if (v > 0 && expandedSection.value !== 'todo') expandedSection.value = 'todo'
})

const entryCount = computed(() => {
  let n = 0
  for (const entries of Object.values(whiteboard.sections.value)) n += Object.keys(entries).length
  return n
})

const todoCount = computed(() => Object.keys(todo.todos.value).length)
const fileCount = computed(() => props.files.length)

// ---- Auto-refresh files when tab is expanded ----
let filesRefreshTimer = null

watch(expandedSection, (section) => {
  if (filesRefreshTimer) { clearInterval(filesRefreshTimer); filesRefreshTimer = null }
  if (section === 'files') {
    emit('load-files')
    filesRefreshTimer = setInterval(() => emit('load-files'), 1000)
  }
}, { immediate: true })

onUnmounted(() => {
  if (filesRefreshTimer) clearInterval(filesRefreshTimer)
})

defineExpose({ switchTab })
</script>

<template>
  <div class="task-info-panel">
    <!-- Whiteboard -->
    <div class="tip-section" :class="{ 'tip-section--collapsed': expandedSection !== 'whiteboard' }">
      <button class="tip-section__header" @click="toggleSection('whiteboard')">
        <span class="tip-section__header-icon"><MIcon name="clipboard" /></span>
        <span class="tip-section__header-label">Whiteboard</span>
        <span v-if="entryCount" class="tip-section__header-count">{{ entryCount }}</span>
        <MIcon name="chevron-down" class="tip-section__chevron" />
      </button>
      <div v-if="expandedSection === 'whiteboard'" class="tip-section__body">
        <WhiteboardView
          :sections="whiteboard.sections.value"
          :is-loaded="whiteboard.isLoaded.value"
          :agent-name="agentName"
          @save="whiteboard.replaceAll"
        />
      </div>
    </div>

    <!-- Todo -->
    <div class="tip-section" :class="{ 'tip-section--collapsed': expandedSection !== 'todo' }">
      <button class="tip-section__header" @click="toggleSection('todo')">
        <span class="tip-section__header-icon"><MIcon name="list-checks" /></span>
        <span class="tip-section__header-label">Todo</span>
        <span v-if="todoCount" class="tip-section__header-count">{{ todoCount }}</span>
        <MIcon name="chevron-down" class="tip-section__chevron" />
      </button>
      <div v-if="expandedSection === 'todo'" class="tip-section__body">
        <TodoView
          :todos="todo.todos.value"
          :is-loaded="todo.isLoaded.value"
        />
      </div>
    </div>

    <!-- Files -->
    <div class="tip-section" :class="{ 'tip-section--collapsed': expandedSection !== 'files' }">
      <button class="tip-section__header" @click="toggleSection('files')">
        <span class="tip-section__header-icon"><MIcon name="folder" /></span>
        <span class="tip-section__header-label">Files</span>
        <MIcon name="chevron-down" class="tip-section__chevron" />
      </button>
      <div v-if="expandedSection === 'files'" class="tip-section__body">
        <TaskFilesPanel
          :files="files"
          :files-loading="filesLoading"
          :current-dir="currentDir"
          :root-dir="rootDir"
          :is-at-root="isAtRoot"
          :relative-path="relativePath"
          :selected-files="selectedFiles"
          :context-menu="contextMenu"
          @load-files="emit('load-files')"
          @open-entry="(entry) => emit('open-entry', entry)"
          @go-up="emit('go-up')"
          @go-root="emit('go-root')"
          @select-file="(entry, event) => emit('select-file', entry, event)"
          @contextmenu="(entry, event) => emit('contextmenu', entry, event)"
          @hide-context-menu="emit('hide-context-menu')"
          @menu-action="(action) => emit('menu-action', action)"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-info-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  font-size: 12px;
  padding-bottom: 42px;
}

.tip-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.tip-section--collapsed { flex-shrink: 0; }
.tip-section:not(.tip-section--collapsed) { flex: 1; min-height: 0; }

/* ---- Unified tab header ---- */
.tip-section__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  width: 100%;
  border: none;
  border-left: 2px solid transparent;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  flex-shrink: 0;
  color: var(--text-secondary);
  background: transparent;
  transition: all 0.15s ease;
}
.tip-section__header:hover {
  color: var(--text-primary);
  background: rgba(0, 0, 0, 0.03);
}

/* Collapsed: subtle divider */
.tip-section + .tip-section > .tip-section__header {
  border-top: 1px solid var(--border);
}

/* Active: left accent + emphasis */
.tip-section:not(.tip-section--collapsed) > .tip-section__header {
  border-left-color: var(--text-secondary);
  color: var(--text-primary);
  background: rgba(0, 0, 0, 0.05);
}

.tip-section__header-icon {
  display: flex;
  font-size: 14px;
  opacity: 0.55;
  transition: opacity 0.15s ease;
}
.tip-section:not(.tip-section--collapsed) > .tip-section__header .tip-section__header-icon {
  opacity: 0.85;
}

.tip-section__header-label { flex: 1; text-align: left; }

.tip-section__header-count {
  font-size: 10px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  padding: 1px 7px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  color: var(--text-tertiary);
  transition: all 0.15s ease;
}
.tip-section:not(.tip-section--collapsed) > .tip-section__header .tip-section__header-count {
  background: rgba(0, 0, 0, 0.07);
  color: var(--text-secondary);
}

.tip-section__chevron {
  font-size: 12px;
  opacity: 0.4;
  transition: transform 0.2s ease, opacity 0.15s ease;
}
.tip-section--collapsed .tip-section__chevron { transform: rotate(-90deg); }
.tip-section:not(.tip-section--collapsed) > .tip-section__header .tip-section__chevron { opacity: 0.6; }

.tip-section__body { flex: 1; min-height: 0; overflow-y: auto; }
.tip-section__placeholder {
  display: flex; align-items: center; justify-content: center;
  padding: 24px; color: var(--text-quaternary); font-size: 12px;
}
</style>
