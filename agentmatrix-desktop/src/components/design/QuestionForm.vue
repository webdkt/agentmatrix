<script setup>
import { ref, computed, watch } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'

/**
 * 提问表单 —— 由 DesignView 监听 design/question 事件后弹出。
 * 非阻塞：agent 调 ask_user_question 时已立即返回，用户提交后答案
 * 通过父组件走现有 user message 通道（sessionAPI.sendReply）。
 *
 * Props:
 *   questions: array of { question, options?, multi_select?, default? }
 * Emits:
 *   submit: (answers: string) — 父组件把 answers 作为一条 user message 发送
 *   cancel
 */
const props = defineProps({
  questions: { type: Array, default: () => [] },
})
const emit = defineEmits(['submit', 'cancel'])

// 每个 question 的本地答案状态
const answers = ref([])

function initAnswers() {
  answers.value = (props.questions || []).map(q => {
    const def = q.default
    if (q.multi_select) {
      const arr = Array.isArray(def) ? [...def] : (def ? [def] : [])
      return { type: 'multi', value: arr }
    }
    if (q.options && q.options.length) {
      return { type: 'choice', value: def || '' }
    }
    return { type: 'text', value: def || '' }
  })
}

watch(() => props.questions, initAnswers, { immediate: true })

function toggleMulti(qIdx, option) {
  const a = answers.value[qIdx]
  if (!a) return
  const i = a.value.indexOf(option)
  if (i === -1) a.value.push(option)
  else a.value.splice(i, 1)
}

const canSubmit = computed(() =>
  answers.value.every(a => {
    if (a.type === 'multi') return a.value.length > 0
    return String(a.value || '').trim() !== ''
  })
)

function buildAnswersText() {
  const lines = []
  props.questions.forEach((q, idx) => {
    const a = answers.value[idx]
    let val
    if (a.type === 'multi') val = a.value.join(', ')
    else val = a.value
    if (props.questions.length === 1) {
      // 单问直接给答案，对话更自然
      lines.push(String(val).trim())
    } else {
      lines.push(`Q: ${q.question}\nA: ${String(val).trim()}`)
    }
  })
  return lines.join('\n\n')
}

function handleSubmit() {
  if (!canSubmit.value) return
  emit('submit', buildAnswersText())
}

function handleCancel() {
  emit('cancel')
}
</script>

<template>
  <div class="qf-overlay" @click.self="handleCancel">
    <div class="qf-dialog">
      <div class="qf-header">
        <MIcon name="help-circle" />
        <h3>Agent 提问</h3>
      </div>

      <div class="qf-body">
        <div v-for="(q, idx) in questions" :key="idx" class="qf-item">
          <label class="qf-question">{{ q.question }}</label>

          <!-- 多选 -->
          <template v-if="q.options && q.options.length && q.multi_select">
            <div class="qf-options">
              <label
                v-for="opt in q.options"
                :key="opt"
                class="qf-option qf-option--check"
              >
                <input
                  type="checkbox"
                  :checked="answers[idx]?.value.includes(opt)"
                  @change="toggleMulti(idx, opt)"
                />
                <span>{{ opt }}</span>
              </label>
            </div>
          </template>

          <!-- 单选 -->
          <template v-else-if="q.options && q.options.length">
            <div class="qf-options">
              <label
                v-for="opt in q.options"
                :key="opt"
                class="qf-option"
                :class="{ 'qf-option--active': answers[idx]?.value === opt }"
              >
                <input
                  type="radio"
                  :name="`q-${idx}`"
                  :value="opt"
                  v-model="answers[idx].value"
                />
                <span>{{ opt }}</span>
              </label>
            </div>
          </template>

          <!-- 自由文本 -->
          <textarea
            v-else
            v-model="answers[idx].value"
            rows="2"
            placeholder="输入你的回答..."
          ></textarea>
        </div>
      </div>

      <div class="qf-footer">
        <button class="qf-btn qf-btn--ghost" @click="handleCancel">取消</button>
        <button class="qf-btn qf-btn--primary" :disabled="!canSubmit" @click="handleSubmit">
          提交
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.qf-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.qf-dialog {
  width: 480px;
  max-width: 90vw;
  max-height: 80vh;
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.2);
}

.qf-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  color: var(--text-primary);
}

.qf-header h3 {
  font-size: var(--font-md);
  font-weight: var(--font-weight-medium);
  margin: 0;
}

.qf-body {
  padding: var(--spacing-4);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.qf-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.qf-question {
  font-size: var(--font-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.qf-options {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.qf-option {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-sm);
  color: var(--text-secondary);
  background: var(--surface-secondary);
  transition: all var(--duration-fast);
}

.qf-option:hover {
  border-color: var(--accent);
}

.qf-option--active {
  border-color: var(--accent);
  background: rgba(184, 169, 201, 0.2);
  color: var(--text-primary);
}

.qf-option input {
  margin: 0;
}

.qf-item textarea {
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font-size: var(--font-sm);
  font-family: inherit;
  resize: vertical;
}

.qf-item textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.qf-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  border-top: 1px solid var(--border);
}

.qf-btn {
  padding: var(--spacing-1) var(--spacing-3);
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: opacity var(--duration-fast);
}

.qf-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.qf-btn--ghost {
  background: transparent;
  color: var(--text-secondary);
}

.qf-btn--ghost:hover {
  color: var(--text-primary);
}

.qf-btn--primary {
  background: var(--accent);
  color: white;
}

.qf-btn--primary:hover:not(:disabled) {
  opacity: 0.9;
}
</style>
