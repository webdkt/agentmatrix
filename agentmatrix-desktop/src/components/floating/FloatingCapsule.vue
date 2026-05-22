<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { listen, emit as tauriEmit } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { useAgentStore } from '@/stores/agent'
import { agentAPI } from '@/api/agent'
import GlassCard from './GlassCard.vue'
import FloatingMenu from './FloatingMenu.vue'

// ---- Session state: read from Rust global state ----
const userSessionId = ref(null)
const agentName = ref(null)
const agentSessionId = ref(null)
const taskId = ref(null)
const lastEmailId = ref(null)
const agentStatus = ref('IDLE')
const agentStatusData = ref({})

async function loadSessionFromGlobal() {
  try {
    const ctx = await invoke('get_current_session')
    userSessionId.value = ctx.user_session_id || null
    agentSessionId.value = ctx.agent_session_id || null
    agentName.value = ctx.agent_name || null
    taskId.value = ctx.task_id || null
    lastEmailId.value = ctx.last_email_id || null
  } catch (e) {
    console.error('[Capsule] Failed to load session:', e)
  }
}

const isValidSession = computed(() => !!(agentName.value && agentSessionId.value))

// ---- UI state ----
const showMenu = ref(false)
const CAPSULE_H = 72

watch(showMenu, async (open) => {
  if (open) {
    await nextTick()
    const menuDiv = document.querySelector('.floating-menu')
    if (menuDiv) {
      const h = CAPSULE_H + menuDiv.scrollHeight
      await invoke('set_capsule_height', { height: h })
    }
  } else {
    await invoke('set_capsule_height', { height: CAPSULE_H })
  }
})

// ---- Stores ----
const agentStore = useAgentStore()

// ---- Restore to desktop ----
async function restoreToDesktop() {
  const { emit } = await import('@tauri-apps/api/event')
  await emit('floating:restore')
}

// ---- Open/close input window ----
let isInputWindowOpen = false

async function openInputWindow() {
  if (!userSessionId.value || !agentName.value) return
  try {
    if (isInputWindowOpen) {
      await invoke('destroy_input_window')
      isInputWindowOpen = false
    } else {
      await invoke('create_input_window')
      isInputWindowOpen = true
    }
  } catch (e) {
    console.error('[Capsule] Failed to toggle input window:', e)
    isInputWindowOpen = false
  }
}

// ---- UI Actions ----
const agentUISchema = ref([])

async function loadAgentUISchema() {
  if (!agentName.value) return
  const cached = agentStore.getAgentUISchema(agentName.value)
  if (cached.length > 0) {
    agentUISchema.value = cached
    return
  }
  try {
    const result = await agentAPI.getAgentUIActions(agentName.value)
    agentUISchema.value = result.schema || []
    agentStore.setAgentUISchema(agentName.value, result.schema || [])
  } catch (e) {
    console.error('[Capsule] Failed to load UI schema:', e)
  }
}

async function invokeUIAction(actionNode) {
  if (!agentName.value) return
  try {
    const payload = { session_id: agentSessionId.value }
    await agentAPI.invokeAgentUIAction(agentName.value, actionNode.action, payload)
  } catch (e) {
    console.error('[Capsule] UI action failed:', e)
  }
}

// ---- Session-aware agent status ----
const isOnCurrentSession = computed(() => {
  const status = agentStatus.value
  if (status === 'IDLE') return true
  const activeSessionId = agentStatusData.value?.current_session_id
  if (!activeSessionId) return true
  return activeSessionId === agentSessionId.value
})

const otherUserSessionId = computed(() => {
  if (isOnCurrentSession.value) return null
  return agentStatusData.value?.current_user_session_id || null
})

async function handleSwitchSession() {
  const targetSessionId = otherUserSessionId.value
  if (!targetSessionId) return
  await tauriEmit('floating:switch-session', {
    sessionId: targetSessionId,
    agentName: agentName.value,
  })
  const data = agentStatusData.value
  if (data?.current_session_id) {
    agentSessionId.value = data.current_session_id
    userSessionId.value = data.current_user_session_id
  }
}

// ---- Lifecycle ----
let unlistenStatus = null
let unlistenReloadSession = null

onMounted(async () => {
  invoke('clip_window_rounded', { label: 'floating-capsule', radius: 20 })
  await loadSessionFromGlobal()

  // Listen for session reload requests
  unlistenReloadSession = await listen('session-changed', async () => {
    await loadSessionFromGlobal()
  })

  // Sync input window state when closed from InputPanel
  await listen('input:closed', () => {
    isInputWindowOpen = false
  })

  // Listen for agent status updates from the stream window
  unlistenStatus = await listen('floating:status-update', (event) => {
    agentStatusData.value = event.payload || {}
    agentStatus.value = event.payload?.status || 'IDLE'
  })
})

watch(isValidSession, async (valid) => {
  if (!valid) return
  await loadAgentUISchema()
}, { immediate: true })

onUnmounted(() => {
  if (unlistenStatus) unlistenStatus()
  if (unlistenReloadSession) unlistenReloadSession()
})
</script>

<template>
  <div class="capsule-panel">
    <template v-if="isValidSession">
      <div class="glass-capsule">
        <GlassCard
          :agent-name="agentName"
          :agent-status="agentStatus"
          :is-on-current-session="isOnCurrentSession"
          @toggle-menu="showMenu = !showMenu"
          @open-input="openInputWindow"
          @switch-session="handleSwitchSession"
        />

        <FloatingMenu
          ref="menuRef"
          :visible="showMenu"
          :schema="agentUISchema"
          :agent-name="agentName"
          :agent-status="agentStatus"
          @close="showMenu = false"
          @invoke-action="invokeUIAction"
          @restore="restoreToDesktop"
        />
      </div>
    </template>
  </div>
</template>

<style scoped>
.capsule-panel {
  background: transparent;
  padding: 0;
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
}

.glass-capsule {
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 0.5px solid rgba(0, 0, 0, 0.12);
  box-shadow:
    0 2px 8px rgba(0, 0, 0, 0.08),
    0 8px 24px rgba(0, 0, 0, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
  flex: 1;
}
</style>
