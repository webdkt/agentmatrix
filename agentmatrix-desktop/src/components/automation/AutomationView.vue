<script setup>
import { ref, onMounted, provide } from 'vue'
import { useAutomationView } from '@/composables/useAutomationView'
import { configAPI } from '@/api/config'
import { invoke } from '@tauri-apps/api/core'
import AutomationNav from './AutomationNav.vue'
import SystemSelector from './SystemSelector.vue'
import ProcessSelector from './ProcessSelector.vue'
import AutomationSendingOverlay from './AutomationSendingOverlay.vue'
import AgentSessionPanel from '@/components/collab/AgentSessionPanel.vue'

const av = useAutomationView()

// Provide a mock collabWizard that's always idle (so AgentSessionPanel skips wizard mode)
const mockWizard = {
  isActive: { value: false },
  wizardStep: { value: 'idle' },
  selectedAgent: { value: null },
  sendTargetAgentName: { value: null },
  enterWizard: () => {},
  selectAgent: () => {},
  goBack: () => {},
  startSending: () => {},
  finishWizard: () => {},
  cancelWizard: () => {},
}
provide('collabWizard', mockWizard)

// Provide draft message for AgentSessionPanel's child components
const collabDraftMessage = ref('')
provide('collabDraftMessage', collabDraftMessage)

// User agent name
const userAgentName = ref('User')

onMounted(async () => {
  // Fetch user_agent_name from backend (same as ViewContainer)
  try {
    const config = await configAPI.getFullConfig()
    if (config?.user_agent_name) {
      userAgentName.value = config.user_agent_name
    }
  } catch (e) {
    console.warn('[AutomationView] Failed to fetch user_agent_name:', e)
  }
  av.init()
})

function handleNavigate(target) {
  if (target === 'home') {
    av.reset()
  } else if (target === 'system') {
    const sys = av.selectedSystem.value
    if (sys) {
      av.navigateToProcessList(sys)
    }
  }
}

function handleNewSystem() {
  if (av.rootDir.value) {
    invoke('reveal_in_folder', { path: av.rootDir.value }).catch(() => {})
  }
}

async function handleNewProcess() {
  // Open the system directory
  try {
    const worldPath = av.rootDir.value
    const systemDir = `${worldPath}/${av.selectedSystem.value}`
    await invoke('reveal_in_folder', { path: systemDir })
  } catch {}
}

function handleResume(process) {
  if (process.activeTask) {
    av.resumeTask(process.activeTask)
  } else if (process.latestTask) {
    av.resumeTask(process.latestTask)
  }
}
</script>

<template>
  <div class="automation-view">
    <AutomationNav
      :state="av.state.value"
      :selected-system="av.selectedSystem.value"
      :selected-process="av.selectedProcess.value"
      :system-display-name="av.selectedSystemDisplayName.value"
      :process-display-name="av.selectedProcessDisplayName.value"
      @navigate="handleNavigate"
    />

    <!-- System Select -->
    <SystemSelector
      v-if="av.state.value === 'system-select'"
      :systems="av.filteredSystems.value"
      :search="av.systemSearch.value"
      :loading="av.isInitialLoad.value"
      :root-dir="av.rootDir.value"
      :load-error="av.loadError.value"
      @select="av.selectSystem"
      @update:search="v => av.systemSearch.value = v"
      @new-system="handleNewSystem"
    />

    <!-- Process Select -->
    <ProcessSelector
      v-else-if="av.state.value === 'process-select'"
      :system-name="av.selectedSystem.value"
      :system-display-name="av.selectedSystemDisplayName.value"
      :processes="av.filteredProcesses.value"
      :search="av.processSearch.value"
      :loading="av.processesLoading.value"
      :send-error="av.sendError.value"
      @select="av.selectProcess"
      @resume="handleResume"
      @back="av.goBack"
      @update:search="v => av.processSearch.value = v"
      @new-process="handleNewProcess"
    />

    <!-- Sending -->
    <AutomationSendingOverlay
      v-else-if="av.state.value === 'sending'"
      :system-name="av.selectedSystemDisplayName.value"
      :process-name="av.selectedProcessDisplayName.value"
    />

    <!-- Session (AgentSessionPanel embedded) -->
    <AgentSessionPanel
      v-else-if="av.state.value === 'session'"
      :user-agent-name="userAgentName"
    />
  </div>
</template>

<style scoped>
.automation-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  background: var(--surface-base);
}
</style>
