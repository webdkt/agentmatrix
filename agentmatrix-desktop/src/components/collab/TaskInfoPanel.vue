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

// ---- Active tab ----
const activeTab = ref('whiteboard')

watch(visiblePanels, (panels) => {
  if (panels.length === 0) {
    activeTab.value = null
    return
  }
  const ids = panels.map(p => p.id)
  if (activeTab.value && !ids.includes(activeTab.value)) {
    activeTab.value = ids[0]
  }
}, { immediate: true })

function switchTab(name) {
  activeTab.value = name
}

// ---- Auto-switch tab on file change ----
watch(() => whiteboard.version.value, (v) => {
  if (v > 0 && activeTab.value !== 'whiteboard') activeTab.value = 'whiteboard'
})
watch(() => todo.version.value, (v) => {
  if (v > 0 && todoCount.value > 0 && activeTab.value !== 'todo') activeTab.value = 'todo'
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

// ---- Auto-refresh files when tab is active ----
let filesRefreshTimer = null

watch(activeTab, (section) => {
  if (filesRefreshTimer) { clearInterval(filesRefreshTimer); filesRefreshTimer = null }
  if (section === 'files') {
    emit('load-files')
    filesRefreshTimer = setInterval(() => emit('load-files'), 1000)
  }
}, { immediate: true })

onUnmounted(() => {
  if (filesRefreshTimer) clearInterval(filesRefreshTimer)
})

// ---- First tab detection (for content corner radius) ----
const isFirstTabActive = computed(() => {
  if (!visiblePanels.value.length) return false
  return activeTab.value === visiblePanels.value[0].id
})

defineExpose({ switchTab })
</script>

<template>
  <div class="task-info-panel">
    <!-- Tab Bar -->
    <div class="tip-tabs">
      <button
        v-for="panel in visiblePanels"
        :key="panel.id"
        class="tip-tab"
        :class="{ 'tip-tab--active': activeTab === panel.id }"
        @click="activeTab = panel.id"
      >
        <MIcon :name="panel.icon" class="tip-tab__icon" />
        <span class="tip-tab__label">{{ panel.label }}</span>
        <span v-if="panelCounts[panel.id]" class="tip-tab__badge">{{ panelCounts[panel.id] }}</span>
      </button>
    </div>

    <!-- Active Panel Content -->
    <div class="tip-content" :class="{ 'tip-content--first-active': isFirstTabActive }">
      <!-- Whiteboard -->
      <template v-for="panel in visiblePanels" :key="panel.id">
        <component
          v-if="activeTab === panel.id"
          :is="panel.component"
          v-bind="getPanelProps(panel.id)"
          v-on="{
            'load-files': (...a) => onPanelEvent(panel.id, 'load-files', ...a),
            'open-entry': (...a) => onPanelEvent(panel.id, 'open-entry', ...a),
            'go-up': (...a) => onPanelEvent(panel.id, 'go-up', ...a),
            'go-root': (...a) => onPanelEvent(panel.id, 'go-root', ...a),
            'select-file': (...a) => onPanelEvent(panel.id, 'select-file', ...a),
            'contextmenu': (...a) => onPanelEvent(panel.id, 'contextmenu', ...a),
            'hide-context-menu': (...a) => onPanelEvent(panel.id, 'hide-context-menu', ...a),
            'menu-action': (...a) => onPanelEvent(panel.id, 'menu-action', ...a),
            'save': (...a) => onPanelEvent(panel.id, 'save', ...a),
          }"
        />
      </template>
    </div>
  </div>
</template>

<style scoped>
.task-info-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: visible;
  font-size: 14px;
  padding-top: 6px;
}

/* ---- Tab Bar ---- */
.tip-tabs {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  padding: 0 0 0 0;
  flex-shrink: 0;
  position: relative;
  z-index: 2;
}

/* ---- Tab (inactive = behind) ---- */
.tip-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  border: 1.5px solid var(--border);
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: var(--surface-secondary);
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  white-space: nowrap;
}

.tip-tab:hover {
  color: var(--text-primary);
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

/* ---- Active tab = connects to content, thick black outline ---- */
.tip-tab--active {
  border: 2px solid var(--text-primary);
  border-bottom: 2px solid var(--surface-base);
  border-radius: 10px 10px 0 0;
  background: var(--surface-base);
  color: var(--text-primary);
  font-weight: 600;
  z-index: 3;
  margin-bottom: -2px;
  padding-bottom: 7px;
  background-clip: padding-box;
}

.tip-tab--active:hover {
  color: var(--text-primary);
  background: var(--surface-base);
}

.tip-tab__icon {
  font-size: 15px;
  flex-shrink: 0;
}

/* Label hidden by default, shown on hover/active */
.tip-tab__label {
  max-width: 0;
  overflow: hidden;
  opacity: 0;
  transition: max-width 0.2s ease, opacity 0.15s ease;
}

.tip-tab:hover .tip-tab__label,
.tip-tab--active .tip-tab__label {
  max-width: 120px;
  opacity: 1;
}

.tip-tab__badge {
  font-size: 10px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.tip-tab--active .tip-tab__badge {
  background: var(--text-primary);
  color: var(--surface-base);
}

/* ---- Content Area = thick black outline, square right corners ---- */
.tip-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--surface-base);
  border: 2px solid var(--text-primary);
  border-radius: 10px 0 0 10px;
}

/* First tab active: top-left square so it aligns with the tab's bottom-left */
.tip-content--first-active {
  border-radius: 0 0 0 10px;
}
</style>
