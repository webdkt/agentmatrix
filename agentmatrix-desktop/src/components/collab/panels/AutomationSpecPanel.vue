<script setup>
import { ref } from 'vue'
import { useAutomationSpec } from '@/composables/useAutomationSpec'
import { useSessionStore } from '@/stores/session'
import { sessionAPI } from '@/api/session'
import { addPendingEmail, removePendingEmail } from '@/composables/usePendingEmails'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: { type: String, required: true },
  sessionId: { type: String, required: true },
})

const sessionStore = useSessionStore()
const spec = useAutomationSpec({ agentName: () => props.agentName })

const expandedSystems = ref({})
const expandedProcesses = ref({})
const processDirs = ref({})
const processFiles = ref({})

const contextMenu = ref({ show: false, x: 0, y: 0, target: null })

function toggleSystem(systemName) {
  expandedSystems.value[systemName] = !expandedSystems.value[systemName]
  if (expandedSystems.value[systemName] && !processDirs.value[systemName]) {
    loadSystemProcesses(systemName)
  }
}

function toggleProcess(systemName, processName) {
  const key = `${systemName}/${processName}`
  expandedProcesses.value[key] = !expandedProcesses.value[key]
  if (expandedProcesses.value[key] && !processFiles.value[key]) {
    loadProcessFiles(systemName, processName)
  }
}

async function loadSystemProcesses(systemName) {
  const result = await spec.loadSystemProcesses(systemName)
  processDirs.value[systemName] = result
}

async function loadProcessFiles(systemName, processName) {
  const result = await spec.loadProcessSteps(systemName, processName)
  processFiles.value[`${systemName}/${processName}`] = result
}

function onContextMenu(e, target) {
  e.preventDefault()
  e.stopPropagation()
  contextMenu.value = { show: true, x: e.clientX, y: e.clientY, target }
}

function closeContextMenu() {
  contextMenu.value = { show: false, x: 0, y: 0, target: null }
}

async function openFolder() {
  const target = contextMenu.value.target
  closeContextMenu()
  if (!target) return
  await spec.revealPath(target.path)
}

async function loadSpec() {
  const target = contextMenu.value.target
  closeContextMenu()
  if (!target) return

  const systemName = target.systemName
  const processName = target.processName || null
  const session = sessionStore.currentSession
  if (!session) return

  const body = processName
    ? `Load Spec: ${systemName} ${processName}`
    : `Load Spec: ${systemName}`

  const emailData = {
    recipient: props.agentName,
    subject: '',
    body,
    task_id: session.task_id || session.session_id,
    in_reply_to: session.last_email_id || undefined,
    recipient_session_id: session.agent_session_id || undefined,
  }

  const placeholderObj = addPendingEmail(session.session_id, emailData)
  try {
    await sessionAPI.sendEmail(session.session_id, emailData)
    removePendingEmail(placeholderObj.id)
  } catch (e) {
    console.error('[AutomationSpec] Failed to send load spec message:', e)
    removePendingEmail(placeholderObj.id)
  }
}
</script>

<template>
  <div class="spec-panel" @click="closeContextMenu">
    <div v-if="spec.isInitialLoad.value" class="spec-panel__empty">Loading...</div>
    <div v-else-if="spec.error.value" class="spec-panel__empty spec-panel__empty--error">
      Failed to load automation knowledge
    </div>
    <div v-else-if="spec.systems.value.length === 0" class="spec-panel__empty">
      No automation systems found
    </div>
    <div v-else class="spec-panel__tree">
      <div v-for="system in spec.systems.value" :key="system.name" class="spec-panel__system">
        <div
          class="spec-panel__system-header"
          @click="toggleSystem(system.name)"
          @contextmenu="onContextMenu($event, { type: 'system', systemName: system.name, path: system.path })"
        >
          <MIcon name="chevron-right" class="spec-panel__chevron" :class="{ 'spec-panel__chevron--open': expandedSystems[system.name] }" />
          <MIcon name="globe" class="spec-panel__icon" />
          <span class="spec-panel__label">{{ system.name }}</span>
        </div>
        <div v-if="expandedSystems[system.name]" class="spec-panel__system-children">
          <div
            v-for="proc in (processDirs[system.name] || [])"
            :key="proc.name"
            class="spec-panel__process"
          >
            <div
              class="spec-panel__process-header"
              @click="toggleProcess(system.name, proc.name)"
              @contextmenu="onContextMenu($event, { type: 'process', systemName: system.name, processName: proc.name, path: proc.path })"
            >
              <MIcon name="chevron-right" class="spec-panel__chevron" :class="{ 'spec-panel__chevron--open': expandedProcesses[`${system.name}/${proc.name}`] }" />
              <MIcon name="folder" class="spec-panel__icon" />
              <span class="spec-panel__label">{{ proc.name }}</span>
            </div>
            <div v-if="expandedProcesses[`${system.name}/${proc.name}`]" class="spec-panel__process-children">
              <div
                v-for="step in (processFiles[`${system.name}/${proc.name}`]?.steps || [])"
                :key="step.path"
                class="spec-panel__file-item"
                @contextmenu="onContextMenu($event, { type: 'file', systemName: system.name, processName: proc.name, path: step.path })"
              >
                <MIcon name="file-text" class="spec-panel__file-icon" />
                <span class="spec-panel__file-name">{{ step.name }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Context Menu -->
    <div
      v-if="contextMenu.show"
      class="spec-panel__context-menu"
      :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      @click.stop
    >
      <button class="spec-panel__menu-item" @click="openFolder">
        <MIcon name="folder" />
        <span>Open Folder</span>
      </button>
      <button
        v-if="contextMenu.target?.type === 'system' || contextMenu.target?.type === 'process'"
        class="spec-panel__menu-item"
        @click="loadSpec"
      >
        <MIcon name="book-open" />
        <span>Load Spec</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.spec-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.spec-panel__empty {
  padding: 16px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: center;
}

.spec-panel__empty--error {
  color: var(--error);
}

.spec-panel__tree {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.spec-panel__system-header,
.spec-panel__process-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-secondary);
  transition: background 0.1s;
}

.spec-panel__system-header:hover,
.spec-panel__process-header:hover {
  background: var(--surface-base);
}

.spec-panel__chevron {
  font-size: 10px;
  opacity: 0.4;
  transition: transform 0.15s;
  flex-shrink: 0;
}

.spec-panel__chevron--open {
  transform: rotate(90deg);
}

.spec-panel__icon {
  font-size: 13px;
  opacity: 0.6;
  flex-shrink: 0;
}

.spec-panel__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}

.spec-panel__system-children,
.spec-panel__process-children {
  padding-left: 16px;
}

.spec-panel__file-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px 3px 22px;
  font-size: 11px;
  color: var(--text-tertiary);
  cursor: default;
}

.spec-panel__file-item:hover {
  color: var(--text-secondary);
}

.spec-panel__file-icon {
  font-size: 12px;
  flex-shrink: 0;
}

.spec-panel__file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spec-panel__context-menu {
  position: fixed;
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
  min-width: 160px;
  z-index: var(--z-dropdown);
  overflow: hidden;
  animation: specMenuFadeIn 0.15s ease-out;
}

@keyframes specMenuFadeIn {
  from { opacity: 0; transform: scale(0.95); }
  to { opacity: 1; transform: scale(1); }
}

.spec-panel__menu-item {
  width: 100%;
  padding: 7px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.spec-panel__menu-item:hover {
  background: var(--surface-hover);
}

.spec-panel__menu-item .m-icon {
  font-size: 13px;
}
</style>
