<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { useAgentStore } from '@/stores/agent'
import { agentAPI } from '@/api/agent'
import GlassCard from './GlassCard.vue'
import FloatingMenu from './FloatingMenu.vue'

// ---- Parse session info from URL hash ----
function parseParams() {
  const hash = window.location.hash.slice(1)
  const params = {}
  hash.split('&').forEach(pair => {
    const [key, val] = pair.split('=')
    if (key && val) params[decodeURIComponent(key)] = decodeURIComponent(val)
  })
  return params
}

const sessionId = ref(null)
const agentName = ref(null)
const agentSessionId = ref(null)
const agentStatus = ref('IDLE')

function readParamsFromHash() {
  const params = parseParams()
  sessionId.value = params.sessionId || null
  agentName.value = params.agentName || null
  agentSessionId.value = params.agentSessionId || null
}
readParamsFromHash()
window.addEventListener('hashchange', readParamsFromHash)

const isValidSession = computed(() => !!(agentName.value && agentSessionId.value))

// ---- UI state ----
const showMenu = ref(false)
const CAPSULE_H = 64
const CAPSULE_MENU_H = 200

watch(showMenu, (open) => {
  invoke('set_capsule_height', { height: open ? CAPSULE_MENU_H : CAPSULE_H })
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
  if (!sessionId.value || !agentName.value) return
  try {
    if (isInputWindowOpen) {
      await invoke('destroy_input_window')
      isInputWindowOpen = false
    } else {
      await invoke('create_input_window', {
        sessionId: sessionId.value,
        agentName: agentName.value,
        agentSessionId: agentSessionId.value,
        lastEmailId: '',
      })
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
    const payload = { session_id: sessionId.value }
    await agentAPI.invokeAgentUIAction(agentName.value, actionNode.action, payload)
  } catch (e) {
    console.error('[Capsule] UI action failed:', e)
  }
}

// ---- Lifecycle: listen for status updates from stream window ----
let unlistenStatus = null
let unlistenRestore = null

onMounted(() => {
  invoke('clip_window_rounded', { label: 'floating-capsule', radius: 20 })
})

watch(isValidSession, async (valid) => {
  if (!valid) return
  await loadAgentUISchema()

  // Listen for agent status updates from stream window
  unlistenStatus = await listen('floating:status-update', (event) => {
    agentStatus.value = event.payload.status || 'IDLE'
  })
}, { immediate: true })

onUnmounted(() => {
  window.removeEventListener('hashchange', readParamsFromHash)
  if (unlistenStatus) unlistenStatus()
})
</script>

<template>
  <div class="capsule-panel">
    <template v-if="isValidSession">
      <div class="glass-capsule">
        <GlassCard
          :agent-name="agentName"
          :agent-status="agentStatus"
          @toggle-menu="showMenu = !showMenu"
          @open-input="openInputWindow"
        />

        <FloatingMenu
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
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(0, 0, 0, 0.06);
  flex: 1;
}
</style>
