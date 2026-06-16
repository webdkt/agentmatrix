<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useConfigStore } from '@/stores/config'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useSessionStore } from '@/stores/session'
import { sessionAPI } from '@/api/session'
import { useNewSessionSender } from '@/composables/useNewSessionSender'
import MIcon from '@/components/icons/MIcon.vue'
import ChatMessage from '@/components/collab/ChatMessage.vue'
import AgentStatusBadge from '@/components/knowledge/AgentStatusBadge.vue'

const emit = defineEmits(['close'])
const configStore = useConfigStore()
const knowledgeStore = useKnowledgeStore()
const sessionStore = useSessionStore()
const { sendAndWaitForSession } = useNewSessionSender()

const AGENT_NAME = '知识管家'
const userAgentName = computed(() => configStore.config?.user_agent_name || 'User')

const events = ref([])
const messagesContainer = ref(null)
const inputText = ref('')
const sending = ref(false)
const loading = ref(false)

const taskId = computed(() => {
  const kbName = knowledgeStore.currentKB?.name
  return kbName ? `kb-chat-${kbName}` : null
})
const agentSessionId = ref(null)

const chatTimeline = computed(() => {
  return events.value
    .map(ev => ({
      type: ev.renderType,
      id: ev.id,
      timestamp: ev.timestamp,
      data: ev,
    }))
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
})

function classifyEvent(type, name, detail) {
  if (type === 'email') {
    if (name === 'received' && detail.sender === userAgentName.value) return 'bubble-user'
    if (name === 'sent' && detail.recipient === userAgentName.value) return 'bubble-agent'
    return 'agent-comm'
  }
  if (type === 'think') return 'thought'
  if (type === 'chat-msg') return 'bubble-agent'
  if (type === 'action') {
    if (name === 'detected') return 'skip'
    if (detail.action_name === 'send_internal_mail') return 'skip'
    return 'pill'
  }
  if (type === 'session') {
    if (name === 'activated' || name === 'deactivated') return 'session-time'
    return 'skip'
  }
  return 'system'
}

function parseEvent(raw) {
  let detail = {}
  if (raw.event_detail) {
    try {
      detail = typeof raw.event_detail === 'string' ? JSON.parse(raw.event_detail) : raw.event_detail
    } catch { detail = {} }
  }
  const renderType = classifyEvent(raw.event_type, raw.event_name, detail)
  return { id: raw.id, timestamp: raw.timestamp, eventType: raw.event_type, eventName: raw.event_name, detail, renderType }
}

// ---- 持久化 session_id（存到 KB wiki 目录）----

async function getSessionFilePath() {
  const config = await invoke('get_config')
  const kbName = knowledgeStore.currentKB?.name
  if (!kbName) return null
  return `${config.matrix_world_path}/workspace/wiki/${kbName}/_chat_session`
}

async function loadSavedSessionId() {
  try {
    const path = await getSessionFilePath()
    if (!path) return
    const content = await invoke('read_text_file', { path })
    const sid = content.trim()
    if (sid) agentSessionId.value = sid
  } catch {
    // 文件不存在，正常
  }
}

async function saveSessionId(sid) {
  try {
    const path = await getSessionFilePath()
    if (!path) return
    await invoke('write_text_file', { path, content: sid })
    agentSessionId.value = sid
  } catch (e) {
    console.error('Failed to save session id:', e)
  }
}

// ---- 加载 events ----

async function loadEvents() {
  if (!agentSessionId.value) return
  loading.value = true
  try {
    const result = await sessionAPI.getSessionEvents(AGENT_NAME, agentSessionId.value, 200)
    events.value = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
  } catch {
    events.value = []
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

onMounted(async () => {
  await loadSavedSessionId()
  if (agentSessionId.value) {
    await loadEvents()
  }
})

// ---- 发送消息 ----

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || sending.value || !taskId.value) return

  inputText.value = ''
  sending.value = true

  // 乐观 placeholder
  events.value.push({
    id: `placeholder-${Date.now()}`,
    timestamp: new Date().toISOString(),
    eventType: 'email',
    eventName: 'received',
    detail: { body_preview: text, sender: userAgentName.value, recipient: AGENT_NAME, _isPlaceholder: true },
    renderType: 'bubble-user',
  })
  nextTick(() => scrollToBottom())

  try {
    if (agentSessionId.value) {
      // 已有 session，直接回复
      await sessionAPI.sendEmail(agentSessionId.value, {
        recipient: AGENT_NAME,
        subject: '',
        body: text,
        task_id: taskId.value,
      })
    } else {
      // 首次：创建 session
      const session = await sendAndWaitForSession(AGENT_NAME, {
        subject: '',
        body: text,
        task_id: taskId.value,
      })
      await saveSessionId(session.agent_session_id)
    }
  } catch (e) {
    console.error('Failed to send message:', e)
    const idx = events.value.findIndex(ev => ev.detail?._isPlaceholder)
    if (idx !== -1) events.value.splice(idx, 1)
  } finally {
    sending.value = false
  }
}

// ---- 新 session ----

async function handleNewSession() {
  if (sending.value) return
  agentSessionId.value = null
  events.value = []
  // 清空存储的 session_id
  try {
    const path = await getSessionFilePath()
    if (path) await invoke('write_text_file', { path, content: '' })
  } catch {}
}

// ---- 实时事件 ----

watch(() => sessionStore.lastSessionEvent, (evt) => {
  if (!evt || !agentSessionId.value) return
  if (evt.agent_name !== AGENT_NAME || evt.session_id !== agentSessionId.value) return

  const parsed = parseEvent(evt.data)
  if (parsed.renderType === 'skip' || parsed.renderType === 'bubble-user') return

  events.value.push(parsed)
  nextTick(() => scrollToBottom())
})
</script>

<template>
  <div class="chat-panel">
    <div class="chat-panel__header">
      <span>{{ AGENT_NAME }}</span>
      <AgentStatusBadge :agent-name="AGENT_NAME" />
      <button class="chat-panel__action" @click="handleNewSession" title="新会话">
        <MIcon name="plus" />
      </button>
      <button class="chat-panel__close" @click="emit('close')">
        <MIcon name="x" />
      </button>
    </div>

    <div ref="messagesContainer" class="chat-panel__messages">
      <div v-if="loading" class="chat-panel__empty">
        <p>连接中...</p>
      </div>
      <div v-else-if="chatTimeline.length === 0" class="chat-panel__empty">
        <p>向知识管家提问或请求操作</p>
      </div>
      <ChatMessage
        v-for="item in chatTimeline"
        :key="item.id"
        :message="item"
        :user_agent_name="userAgentName"
        :agent-name="AGENT_NAME"
      />
    </div>

    <div class="chat-panel__input">
      <textarea
        v-model="inputText"
        placeholder="输入消息..."
        rows="3"
        :disabled="sending || loading"
        @keydown.enter.exact.prevent="handleSend"
      ></textarea>
      <button class="chat-panel__send" @click="handleSend" :disabled="sending || !inputText.trim()">
        <MIcon name="send" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface-base);
  border-left: 1px solid var(--border);
}

.chat-panel__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  flex-shrink: 0;
}

.chat-panel__header span:first-child {
  flex: 1;
}

.chat-panel__action,
.chat-panel__close {
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: var(--spacing-1);
  border-radius: var(--radius-sm);
}

.chat-panel__action:hover,
.chat-panel__close:hover {
  background: var(--surface-hover);
}

.chat-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-3);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.chat-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.chat-panel__input {
  display: flex;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  align-items: flex-end;
}

.chat-panel__input textarea {
  flex: 1;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-sm);
  font-family: inherit;
  resize: none;
  line-height: 1.5;
}

.chat-panel__input textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.chat-panel__send {
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
  height: fit-content;
}

.chat-panel__send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
