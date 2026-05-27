<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen, emit as tauriEmit } from '@tauri-apps/api/event'
import { sessionAPI } from '@/api/session'
import MIcon from '@/components/icons/MIcon.vue'

const userSessionId = ref(null)
const agentName = ref(null)
const agentSessionId = ref(null)
const taskId = ref(null)
const lastEmailId = ref(null)
const inputText = ref('')
const isSending = ref(false)
const hasSession = ref(false)

async function loadSessionFromGlobal() {
  try {
    const ctx = await invoke('get_current_session')
    userSessionId.value = ctx.user_session_id || null
    agentName.value = ctx.agent_name || null
    agentSessionId.value = ctx.agent_session_id || null
    taskId.value = ctx.task_id || null
    lastEmailId.value = ctx.last_email_id || null
    hasSession.value = !!(ctx.user_session_id && ctx.agent_name)
  } catch (e) {
    console.error('[Input] Failed to load session:', e)
  }
}

async function sendMessage() {
  const body = inputText.value.trim()
  if (!body || !userSessionId.value || !agentName.value || isSending.value) return

  isSending.value = true
  try {
    await sessionAPI.sendEmail(userSessionId.value, {
      recipient: agentName.value,
      subject: '',
      body: body,
      task_id: taskId.value || userSessionId.value,
      in_reply_to: lastEmailId.value || undefined,
      recipient_session_id: agentSessionId.value || undefined,
    })
    inputText.value = ''
    await closeWindow()
  } catch (err) {
    console.error('[Input] Send failed:', err)
  } finally {
    isSending.value = false
  }
}

async function closeWindow() {
  await invoke('destroy_input_window')
  await tauriEmit('input:closed')
}

// Read global state when window gains focus
function onFocus() {
  loadSessionFromGlobal().then(() => {
    document.querySelector('textarea')?.focus()
  })
}

let unlistenSessionChanged = null

onMounted(async () => {
  await loadSessionFromGlobal()
  document.querySelector('textarea')?.focus()
  window.addEventListener('focus', onFocus)

  unlistenSessionChanged = await listen('session-changed', async () => {
    await loadSessionFromGlobal()
  })
})

onUnmounted(() => {
  window.removeEventListener('focus', onFocus)
  if (unlistenSessionChanged) unlistenSessionChanged()
})
</script>

<template>
  <div class="input-panel" v-if="hasSession">
    <div class="input-panel__header" data-tauri-drag-region>
      <span class="input-panel__title">发送消息给 {{ agentName }}</span>
      <button class="input-panel__close" @click="closeWindow" title="Close">
        <MIcon name="x" />
      </button>
    </div>
    <div class="input-panel__body">
      <textarea
        v-model="inputText"
        class="input-panel__textarea"
        placeholder="输入消息..."
        rows="5"
        @keydown.enter.exact.prevent="sendMessage"
        @keydown.escape.exact="closeWindow"
        :disabled="isSending"
      />
      <button
        class="input-panel__send"
        @click="sendMessage"
        :disabled="!inputText.trim() || isSending"
      >
        <MIcon name="send" />
        <span>Send</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-panel {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-radius: 16px;
  font-family: var(--font-sans, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
  overflow: hidden;
}

.input-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.input-panel__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #18181b);
}

.input-panel__close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #a1a1aa);
  font-size: 16px;
  transition: all 0.12s ease;
}

.input-panel__close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary, #18181b);
}

.input-panel__body {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 12px 16px;
  gap: 10px;
}

.input-panel__textarea {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.5;
  resize: none;
  outline: none;
  background: rgba(255, 255, 255, 0.6);
  color: var(--text-primary, #18181b);
  font-family: inherit;
  transition: border-color 0.15s ease;
}

.input-panel__textarea:focus {
  border-color: var(--accent, #A67B7B);
}

.input-panel__textarea::placeholder {
  color: var(--text-quaternary, #d4d4d8);
}

.input-panel__textarea:disabled {
  opacity: 0.5;
}

.input-panel__send {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 20px;
  border: none;
  background: var(--accent, #A67B7B);
  color: white;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s ease;
  flex-shrink: 0;
}

.input-panel__send:hover:not(:disabled) {
  opacity: 0.85;
}

.input-panel__send:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
