<script setup>
import { ref } from 'vue'
import { useNewSessionSender } from '@/composables/useNewSessionSender'
import DesignSessionList from './DesignSessionList.vue'
import MIcon from '@/components/icons/MIcon.vue'

const DESIGNER_AGENT = 'Designer'

const emit = defineEmits(['continue'])

const { sendAndWaitForSession } = useNewSessionSender()

const mode = ref('new')  // 'new' | 'list'
const initialPrompt = ref('')
const starting = ref(false)

function generateTaskId() {
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const timeStr = [
    String(now.getFullYear()).slice(-2),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
  ].join('')
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  const rand = Array.from({ length: 4 },
    () => chars[Math.floor(Math.random() * chars.length)]).join('')
  return `${timeStr}-design-${rand}`
}

async function handleStart() {
  const text = initialPrompt.value.trim()
  if (!text || starting.value) return
  starting.value = true
  try {
    await sendAndWaitForSession(DESIGNER_AGENT, {
      subject: '设计协作',
      body: text,
      task_id: generateTaskId(),
    })
    // selectSession 已在 sendAndWaitForSession 内完成，
    // 父级 DesignView 的 isCurrentDesigner 会自动变 true，本组件被卸载
    initialPrompt.value = ''
  } catch (e) {
    console.error('Failed to start design session:', e)
  } finally {
    starting.value = false
  }
}

function handlePickSession(session) {
  emit('continue', session)
}
</script>

<template>
  <div class="design-welcome">
    <!-- List mode: pick existing -->
    <div v-if="mode === 'list'" class="design-welcome__card">
      <div class="design-welcome__header">
        <h2>继续之前的设计</h2>
        <button class="design-welcome__new-btn" @click="mode = 'new'">
          <MIcon name="plus" />
          <span>新建设计</span>
        </button>
      </div>
      <div class="design-welcome__list-wrap">
        <DesignSessionList :highlight-current="false" @select="handlePickSession" />
      </div>
    </div>

    <!-- New mode (default): prompt form -->
    <div v-else class="design-welcome__card">
      <h2>设计协作</h2>
      <p class="design-welcome__hint">
        告诉 Designer 你想做什么 —— 它会产出 HTML 设计稿、交互原型或 PPT deck。
        左侧会实时预览产出物。
      </p>
      <textarea
        v-model="initialPrompt"
        placeholder="例如：做一个极简风格的个人博客首页 / 一个 3 页的产品介绍 PPT..."
        rows="5"
        :disabled="starting"
        @keydown.enter.meta="handleStart"
        @keydown.enter.ctrl="handleStart"
      ></textarea>
      <button
        class="design-welcome__start-btn"
        :disabled="!initialPrompt.trim() || starting"
        @click="handleStart"
      >
        <span v-if="starting">启动中...</span>
        <span v-else>开始</span>
      </button>

      <div class="design-welcome__divider"><span>或</span></div>

      <button class="design-welcome__continue-btn" @click="mode = 'list'">
        <MIcon name="history" />
        <span>继续之前的设计</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.design-welcome {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-6);
  overflow: auto;
}

.design-welcome__card {
  width: 100%;
  max-width: 560px;
  max-height: 80vh;
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-6);
  display: flex;
  flex-direction: column;
}

/* List mode layout */
.design-welcome__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-3);
}

.design-welcome__header h2,
.design-welcome__card > h2 {
  font-size: var(--font-xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0;
}

.design-welcome__new-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-3);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-xs);
  cursor: pointer;
  transition: opacity var(--duration-fast);
}

.design-welcome__new-btn:hover {
  opacity: 0.9;
}

.design-welcome__list-wrap {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}

/* New mode */
.design-welcome__hint {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin: var(--spacing-2) 0 var(--spacing-4);
  line-height: 1.6;
}

.design-welcome__card textarea {
  width: 100%;
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-sm);
  font-family: inherit;
  resize: vertical;
  line-height: 1.5;
}

.design-welcome__card textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.design-welcome__start-btn {
  margin-top: var(--spacing-4);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: opacity var(--duration-fast);
}

.design-welcome__start-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.design-welcome__divider {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  margin: var(--spacing-5) 0;
  color: var(--text-tertiary);
  font-size: var(--font-xs);
}

.design-welcome__divider::before,
.design-welcome__divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--border);
}

.design-welcome__continue-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-fast);
}

.design-welcome__continue-btn:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}
</style>
