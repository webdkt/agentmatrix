<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useWhiteboard } from '@/composables/useWhiteboard'
import { useTodo } from '@/composables/useTodo'
import { resolvePanels } from './panels/panelRegistry'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: { type: String, required: true },
  sessionId: { type: String, required: true },
  agentSkills: { type: Array, default: () => [] },
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

// ---- Dynamic panel list based on agent skills ----
const visiblePanels = computed(() => resolvePanels(props.agentSkills))

// ---- Accordion ----
const expandedSection = ref('whiteboard')

watch(visiblePanels, (panels) => {
  if (panels.length === 0) {
    expandedSection.value = null
    return
  }
  const ids = panels.map(p => p.id)
  if (expandedSection.value && !ids.includes(expandedSection.value)) {
    expandedSection.value = ids[0]
  }
}, { immediate: true })

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

// ---- Per-panel count badge ----
const panelCounts = computed(() => ({
  whiteboard: entryCount.value || null,
  todo: todoCount.value || null,
  files: null,
  automationSpec: null,
}))

// ---- Per-panel props ----
function getPanelProps(panelId) {
  const common = { agentName: props.agentName, sessionId: props.sessionId }
  if (panelId === 'whiteboard') {
    return {
      ...common,
      sections: whiteboard.sections.value,
      isLoaded: whiteboard.isLoaded.value,
      onSave: whiteboard.replaceAll,
    }
  }
  if (panelId === 'todo') {
    return {
      ...common,
      todos: todo.todos.value,
      isLoaded: todo.isLoaded.value,
    }
  }
  if (panelId === 'files') {
    return {
      ...common,
      files: props.files,
      filesLoading: props.filesLoading,
      currentDir: props.currentDir,
      rootDir: props.rootDir,
      isAtRoot: props.isAtRoot,
      relativePath: props.relativePath,
      selectedFiles: props.selectedFiles,
      contextMenu: props.contextMenu,
    }
  }
  return common
}

// ---- Per-panel events ----
function onPanelEvent(panelId, eventName, ...args) {
  if (panelId === 'files') {
    const eventMap = {
      'load-files': () => emit('load-files'),
      'open-entry': (entry) => emit('open-entry', entry),
      'go-up': () => emit('go-up'),
      'go-root': () => emit('go-root'),
      'select-file': (entry, event) => emit('select-file', entry, event),
      'contextmenu': (entry, event) => emit('contextmenu', entry, event),
      'hide-context-menu': () => emit('hide-context-menu'),
      'menu-action': (action) => emit('menu-action', action),
      'save': (data) => { /* whiteboard save handled directly */ },
    }
    const handler = eventMap[eventName]
    if (handler) handler(...args)
  }
  if (panelId === 'whiteboard' && eventName === 'save') {
    whiteboard.replaceAll(...args)
  }
}

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
    <div
      v-for="panel in visiblePanels"
      :key="panel.id"
      class="tip-section"
      :class="{ 'tip-section--collapsed': expandedSection !== panel.id }"
    >
      <button class="tip-section__header" @click="toggleSection(panel.id)">
        <span class="tip-section__header-icon"><MIcon :name="panel.icon" /></span>
        <span class="tip-section__header-label">{{ panel.label }}</span>
        <span v-if="panelCounts[panel.id]" class="tip-section__header-count">{{ panelCounts[panel.id] }}</span>
        <MIcon name="chevron-down" class="tip-section__chevron" />
      </button>
      <div v-if="expandedSection === panel.id" class="tip-section__body">
        <!-- Whiteboard (needs composable data + save event) -->
        <component
          :is="panel.component"
          v-if="panel.id === 'whiteboard'"
          :sections="whiteboard.sections.value"
          :is-loaded="whiteboard.isLoaded.value"
          :agent-name="agentName"
          @save="whiteboard.replaceAll"
        />
        <!-- Todo (needs composable data) -->
        <component
          :is="panel.component"
          v-else-if="panel.id === 'todo'"
          :todos="todo.todos.value"
          :is-loaded="todo.isLoaded.value"
        />
        <!-- Files (needs many props from parent) -->
        <component
          :is="panel.component"
          v-else-if="panel.id === 'files'"
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
        <!-- Generic panels (receive agentName + sessionId) -->
        <component
          :is="panel.component"
          v-else
          :agent-name="agentName"
          :session-id="sessionId"
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