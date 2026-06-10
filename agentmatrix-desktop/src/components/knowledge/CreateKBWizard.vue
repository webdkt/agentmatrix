<script setup>
import { ref, watch, onUnmounted, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useKnowledgeStore } from '@/stores/knowledge'
import { sessionAPI } from '@/api/session'
import { useSessionStore } from '@/stores/session'
import { useConfigStore } from '@/stores/config'
import { useChatTimeline } from '@/composables/useChatTimeline'
import { useNewSessionSender } from '@/composables/useNewSessionSender'
import { renderMarkdown } from '@/utils/markdown'
import MIcon from '@/components/icons/MIcon.vue'
import ChatMessage from '@/components/collab/ChatMessage.vue'
import AgentStatusBadge from '@/components/knowledge/AgentStatusBadge.vue'

const emit = defineEmits(['complete', 'cancel'])
const knowledgeStore = useKnowledgeStore()
const sessionStore = useSessionStore()
const configStore = useConfigStore()
const { sendAndWaitForSession } = useNewSessionSender()

const userAgentName = computed(() => configStore.config?.user_agent_name || 'User')

// ---- useChatTimeline（复用 AgentSessionPanel 的完整 session 数据逻辑）----
const {
  chatTimeline: rawTimeline,
  messagesContainer,
  currentSession,
  primaryAgentName,
  scrollToBottom,
  onScroll,
  handleEmailSendStarted,
  handleEmailSendFailed,
} = useChatTimeline({ userAgentName: () => userAgentName.value })

// 欢迎消息（Agent 思考期间显示，loadEvents 不会覆盖它）
const welcomeMessage = ref(null)

// 过滤掉第一条用户消息（系统提示），并在开头注入欢迎消息
const chatTimeline = computed(() => {
  const events = rawTimeline.value
  // 过滤第一条 bubble-user
  let filtered = events
  const firstUserIdx = events.findIndex(e => e.type === 'bubble-user')
  if (firstUserIdx === 0) filtered = events.slice(1)
  // 注入欢迎消息
  if (welcomeMessage.value) return [welcomeMessage.value, ...filtered]
  return filtered
})

// State machine: 'form' | 'creating' | 'done'
const state = ref('form')
const name = ref('')
const description = ref('')
const loading = ref(false)
const error = ref(null)

// Creating state
const taskId = ref('')
const schemaDraft = ref('')
const schemaRendered = ref('')
const inputText = ref('')

// Agent name from session (for status badge)
const currentAgentName = computed(() => {
  return primaryAgentName.value || '知识管家'
})

// Polling timers
let schemaPollTimer = null
let kbDetectTimer = null

onUnmounted(() => {
  stopPolling()
})

function stopPolling() {
  if (schemaPollTimer) { clearInterval(schemaPollTimer); schemaPollTimer = null }
  if (kbDetectTimer) { clearInterval(kbDetectTimer); kbDetectTimer = null }
}

function generateTaskId(kbName) {
  const now = new Date()
  const pad = (n, l = 2) => String(n).padStart(l, '0')
  const timeStr = [
    String(now.getFullYear()).slice(-2),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
  ].join('')
  const subject = `生成知识库${kbName}`
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .slice(0, 15)
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  const rand = Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
  return `${timeStr}-${subject}-${rand}`
}

function buildFirstMessage(kbName, kbDescription, tid, schemaPath) {
  return `你的任务是帮助用户确定一个知识库的初始 Schema。

【背景】
用户想创建一个叫"${kbName}"的知识库。${kbDescription}

【什么是 Schema】
Schema 是这个知识库的"信息蓝图"——它定义了这个知识库关注什么类型的信息、这些信息之间有什么关系、以及信息如何组织。Schema 不是具体的知识内容，而是知识内容的结构定义。用户后续往知识库里添加的每一条信息，都会按照 Schema 定义的结构来存放和检索。

一个好的 Schema 应该：
- 贴合用户描述的知识领域
- 信息类型数量适中（3-8个），每个类型有明确的关注维度
- 类型之间的关系清晰（包含、引用）
- 目录结构简洁实用

【Schema 格式】
包含三个部分：
1. 关注的信息类型
   每个类型有：名称、描述、关注维度（提取这个类型时应该注意什么）
2. 类型之间的关系
   - A 包含 B：B 是 A 的子组成部分
   - A 引用 B：A 和 B 之间存在交叉引用
3. 目录结构及用途
   每个目录的用途，以及什么类型的信息放入哪个目录

【你的工作流程】
1. 如果用户已经提供了比较丰富的描述，就根据用户描述，生成初始 Schema，写入 ${schemaPath}. 如果用户描述非常简略，就询问用户关注什么样的信息，需要如何使用这个知识库，理解用户需求后再设计生成 Schema。
2. 更新 ${schemaPath} 后告知用户，请用户查看左侧预览（会自动刷新）
3. 按照用户的要求，改进 ${schemaPath} 文件（用户界面会自动刷新），直到用户确认 Schema 没有问题了
4. 在用户确认后，调用 create_kb(name="${kbName}", description="${kbDescription}", draft_path="${schemaPath}")
5. 必须明确的要求用户确认，绝对不可以自主决定是否创建。

【注意】
- Schema 的唯一载体是 ${schemaPath} 文件，所有修改都必须通过编辑这个文件来完成
- 不要直接创建知识库，先和用户确认 Schema
- 如果用户描述不够清晰，主动提问
- 初始Schema保持简洁，后续可以迭代完善
- Schema内容会在界面上自动展示，你无需全文输出Schema内容，只需要输出必要的修改建议和确认信息即可
`
}

// ---- 发送第一条消息 ----

async function handleStart() {
  if (!name.value.trim() || !description.value.trim()) {
    error.value = '请填写名称和描述'
    return
  }

  loading.value = true
  error.value = null

  try {
    const tid = generateTaskId(name.value)
    taskId.value = tid
    const schemaPath = `/tmp/${tid}-schema-draft.md`

    const firstMessage = buildFirstMessage(name.value, description.value, tid, schemaPath)

    await sendAndWaitForSession('知识管家', {
      subject: `创建知识库${name.value}`,
      body: firstMessage,
      task_id: tid,
    })

    state.value = 'creating'

    // 设置欢迎消息，让用户在 Agent 思考期间了解流程
    welcomeMessage.value = {
      id: 'welcome',
      timestamp: new Date().toISOString(),
      type: 'bubble-agent',
      data: {
        detail: {
          body_preview: `好的，现在为你准备知识库 **${name.value}**。创建知识库之前，我们要先创建一个基础的结构大纲\n\n**什么是知识库结构大纲？**\n知识库不是简单的文件夹，而是有结构的信息集合。结构定义了三件事：\n1. **信息类型** — 你关注什么类型的信息（比如：技术方案、会议记录、学习笔记）\n2. **信息关系** — 这些类型之间有什么联系（比如：会议记录引用技术方案）\n3. **组织方式** — 信息按什么规则存放和检索\n\n**接下来会发生什么？**\n- 我会根据你的描述，生成一份「知识库结构大纲」\n- 大纲会显示在左侧，你可以随时查看和提出修改\n- 确认无误后，我会创建知识库\n\n现在请稍等片刻，我正在思考...`,
        },
      },
    }

    // 开始轮询 schema 文件
    startSchemaPolling(schemaPath)
    // 开始检测知识库创建完成
    startKBDetect()
  } catch (e) {
    error.value = e.message || '创建失败'
  } finally {
    loading.value = false
  }
}

function startSchemaPolling(schemaPath) {
  schemaPollTimer = setInterval(async () => {
    try {
      const content = await invoke('read_text_file', { path: schemaPath })
      if (content) {
        schemaDraft.value = content
        schemaRendered.value = renderMarkdown(content)
      }
    } catch (e) {
      // 文件不存在，忽略
    }
  }, 3000)
}

function startKBDetect() {
  kbDetectTimer = setInterval(async () => {
    await knowledgeStore.fetchKBs()
    const found = knowledgeStore.kbs.find(kb => kb.name === name.value)
    if (found && found.has_schema) {
      stopPolling()
      state.value = 'done'
      await knowledgeStore.selectKB(name.value)
      emit('complete')
    }
  }, 3000)
}

// ---- 发送用户消息 ----

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || !currentSession.value) return

  inputText.value = ''

  const session = currentSession.value
  const placeholderId = `placeholder-${Date.now()}`

  handleEmailSendStarted({
    placeholder: {
      id: placeholderId,
      body: text,
      recipient: session.agent_name,
      subject: '',
    },
  })

  try {
    await sessionAPI.sendReply(session, text)
  } catch (e) {
    console.error('Failed to send message:', e)
    handleEmailSendFailed({ placeholderId })
  }
}
</script>

<template>
  <div class="wizard">
    <!-- Form State -->
    <div v-if="state === 'form'" class="wizard__form">
      <div class="wizard__header">
        <button class="wizard__back" @click="emit('cancel')">
          <MIcon name="arrow-left" />
          <span>返回</span>
        </button>
        <h2>创建知识库</h2>
      </div>

      <div class="wizard__content">
        <h3>基本信息</h3>
        <div class="wizard__field">
          <label>知识库名称</label>
          <input
            v-model="name"
            type="text"
            placeholder="例如：work, reading, personal"
            :disabled="loading"
          />
        </div>
        <div class="wizard__field">
          <label>描述</label>
          <textarea
            v-model="description"
            placeholder="描述这个知识库的用途和关注领域..."
            rows="4"
            :disabled="loading"
          />
        </div>
        <div v-if="error" class="wizard__error">{{ error }}</div>
        <div class="wizard__actions">
          <button class="wizard__btn wizard__btn--primary" @click="handleStart" :disabled="loading">
            <span v-if="loading">创建中...</span>
            <span v-else>开始创建</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Creating State -->
    <div v-else-if="state === 'creating'" class="wizard__creating">
      <div class="wizard__split">
        <!-- Left: Schema Preview -->
        <div class="wizard__schema-panel">
          <div class="wizard__schema-header">
            <h3>知识库结构大纲</h3>
          </div>
          <div v-if="!schemaDraft" class="wizard__schema-empty">
            等待 Agent 生成 Schema...
          </div>
          <div v-else class="wizard__schema-content markdown-content" v-html="schemaRendered"></div>
        </div>

        <!-- Right: Chat -->
        <div class="wizard__chat-panel">
          <div class="wizard__chat-header">
            <h3>准备创建知识库</h3>
            <AgentStatusBadge :agent-name="currentAgentName" class="wizard__status" />
          </div>
          <div ref="messagesContainer" class="wizard__messages" @scroll="onScroll">
            <ChatMessage
              v-for="item in chatTimeline"
              :key="item.id"
              :message="item"
              :user_agent_name="userAgentName"
              :agent-name="currentAgentName"
            />
          </div>
          <div class="wizard__input">
            <textarea
              v-model="inputText"
              placeholder="输入消息..."
              rows="3"
              @keydown.enter.exact.prevent="handleSend"
            ></textarea>
            <button class="wizard__send" @click="handleSend" :disabled="!inputText.trim()">
              <MIcon name="send" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Form State */
.wizard__form {
  padding: var(--spacing-6);
  overflow-y: auto;
}

.wizard__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-6);
}

.wizard__header h2 {
  font-size: var(--font-xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0;
}

.wizard__back {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--font-sm);
}

.wizard__back:hover {
  color: var(--text-primary);
}

.wizard__content {
  max-width: 640px;
}

.wizard__content h3 {
  font-size: var(--font-lg);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-4) 0;
}

.wizard__field {
  margin-bottom: var(--spacing-4);
}

.wizard__field label {
  display: block;
  font-size: var(--font-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-2);
}

.wizard__field input,
.wizard__field textarea {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-sm);
  font-family: inherit;
  resize: vertical;
}

.wizard__field input:focus,
.wizard__field textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.wizard__error {
  color: var(--error);
  font-size: var(--font-sm);
  margin-bottom: var(--spacing-4);
}

.wizard__actions {
  display: flex;
  gap: var(--spacing-3);
  margin-top: var(--spacing-6);
}

.wizard__btn {
  padding: var(--spacing-2) var(--spacing-4);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-sm);
  transition: opacity var(--duration-fast);
}

.wizard__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.wizard__btn--primary {
  background: var(--accent);
  color: white;
}

.wizard__btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}

/* Creating State */
.wizard__creating {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.wizard__split {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Schema Panel */
.wizard__schema-panel {
  width: 45%;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.wizard__schema-header {
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.wizard__schema-header h3 {
  font-size: var(--font-md);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  margin: 0;
}

.wizard__schema-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.wizard__schema-content {
  flex: 1;
  padding: var(--spacing-4);
  overflow-y: auto;
}

/* Chat Panel */
.wizard__chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.wizard__chat-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.wizard__chat-header h3 {
  font-size: var(--font-md);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  margin: 0;
}

/* Status indicator */
.wizard__status {
  margin-left: auto;
}

.wizard__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-3);
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.wizard__input {
  display: flex;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  align-items: flex-end;
}

.wizard__input textarea {
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

.wizard__input textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.wizard__send {
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
  height: fit-content;
}

.wizard__send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

<style>
@import '@/styles/markdown.css';
</style>