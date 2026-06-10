<script setup>
import { ref, nextTick } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['close'])
const knowledgeStore = useKnowledgeStore()

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const chatContainer = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  // TODO: 接入 KnowledgeBaseAgent 的 session/email 通信
  // 当前为占位实现，后续通过 sessionAPI.sendEmail() 与 agent 通信
  setTimeout(() => {
    messages.value.push({
      role: 'assistant',
      content: '聊天功能将在后续版本中接入知识管家 Agent。',
    })
    loading.value = false
    scrollToBottom()
  }, 500)
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-panel__header">
      <span>知识管家</span>
      <button class="chat-panel__close" @click="emit('close')">
        <MIcon name="x" />
      </button>
    </div>

    <div ref="chatContainer" class="chat-panel__messages">
      <div v-if="messages.length === 0" class="chat-panel__empty">
        <p>向知识管家提问或请求操作</p>
      </div>
      <div
        v-for="(msg, i) in messages"
        :key="i"
        :class="['chat-panel__msg', `chat-panel__msg--${msg.role}`]"
      >
        <div class="chat-panel__msg-content">{{ msg.content }}</div>
      </div>
      <div v-if="loading" class="chat-panel__msg chat-panel__msg--assistant">
        <div class="chat-panel__msg-content chat-panel__loading">思考中...</div>
      </div>
    </div>

    <div class="chat-panel__input">
      <input
        v-model="inputText"
        type="text"
        placeholder="输入消息..."
        :disabled="loading"
        @keyup.enter="handleSend"
      />
      <button class="chat-panel__send" @click="handleSend" :disabled="loading || !inputText.trim()">
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
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  flex-shrink: 0;
}

.chat-panel__close {
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: var(--spacing-1);
  border-radius: var(--radius-sm);
}

.chat-panel__close:hover {
  background: var(--surface-hover);
}

.chat-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-3);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.chat-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.chat-panel__msg {
  display: flex;
}

.chat-panel__msg--user {
  justify-content: flex-end;
}

.chat-panel__msg--assistant {
  justify-content: flex-start;
}

.chat-panel__msg-content {
  max-width: 85%;
  padding: var(--spacing-2) var(--spacing-3);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-panel__msg--user .chat-panel__msg-content {
  background: var(--accent);
  color: white;
}

.chat-panel__msg--assistant .chat-panel__msg-content {
  background: var(--surface-secondary);
  color: var(--text-primary);
}

.chat-panel__loading {
  color: var(--text-tertiary);
}

.chat-panel__input {
  display: flex;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.chat-panel__input input {
  flex: 1;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-sm);
}

.chat-panel__input input:focus {
  outline: none;
  border-color: var(--accent);
}

.chat-panel__send {
  padding: var(--spacing-2);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.chat-panel__send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>