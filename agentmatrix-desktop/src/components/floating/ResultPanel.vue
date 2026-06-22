<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'
import { renderMarkdown } from '@/utils/markdown'

const { t } = useI18n()

const result = ref(null)
const contentRef = ref(null)

// Smart content type detection
const contentType = computed(() => {
  if (!result.value) return 'empty'
  const raw = result.value.result

  // Markdown display mode
  if (result.value.display_mode === 'markdown') return 'markdown'

  // String result
  if (typeof raw === 'string') return 'text'

  // Object with error key → error
  if (raw && typeof raw === 'object' && !Array.isArray(raw) && raw.error) return 'error'

  // JSON display mode or complex object → formatted json
  if (result.value.display_mode === 'json' || (raw && typeof raw === 'object')) return 'json'

  return 'text'
})

const errorMessage = computed(() => {
  if (contentType.value !== 'error') return ''
  const raw = result.value.result
  return typeof raw.error === 'string' ? raw.error : JSON.stringify(raw.error)
})

const jsonContent = computed(() => {
  const raw = result.value?.result
  if (typeof raw === 'string') return raw
  return JSON.stringify(raw, null, 2)
})

function closeWindow() {
  result.value = null
  invoke('destroy_result_window').catch(() => {})
}

function handleEscape(e) {
  if (e.key === 'Escape') closeWindow()
}

async function loadResult() {
  try {
    const data = await invoke('get_ui_action_result')
    if (data && data.action_name) {
      result.value = data
      await autoResize()
    }
  } catch (e) {
    console.error('[ResultPanel] loadResult failed:', e)
  }
}

async function autoResize() {
  await nextTick()
  requestAnimationFrame(() => {
    if (!contentRef.value) return
    const headerH = 44
    const footerH = 48
    const padV = 24
    const bodyH = contentRef.value.scrollHeight
    const desiredH = Math.min(600, Math.max(200, headerH + bodyH + footerH + padV))
    invoke('resize_result_window', { width: 520, height: desiredH }).catch(() => {})
  })
}

let unlistenResultChanged = null

onMounted(async () => {
  window.addEventListener('keydown', handleEscape)
  await loadResult()
  unlistenResultChanged = await listen('result:changed', async () => {
    await loadResult()
  })
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleEscape)
  if (unlistenResultChanged) unlistenResultChanged()
})
</script>

<template>
  <div class="result-panel">
    <div class="result-panel__header" data-tauri-drag-region>
      <span class="result-panel__title">{{ result ? t(`ui_actions.actions.${result.action_name}`, result.action_name) : 'Result' }}</span>
      <button class="result-panel__close" @click="closeWindow" title="Close">
        <MIcon name="x" />
      </button>
    </div>
    <div ref="contentRef" class="result-panel__body">
      <!-- Error -->
      <div v-if="contentType === 'error'" class="result-panel__error">
        <div class="result-panel__error-icon"><MIcon name="alert-circle" /></div>
        <div class="result-panel__error-text">{{ errorMessage }}</div>
      </div>

      <!-- Plain text (centered) -->
      <div v-else-if="contentType === 'text'" class="result-panel__text-centered">
        {{ result.result }}
      </div>

      <!-- Markdown -->
      <div v-else-if="contentType === 'markdown'" class="result-panel__markdown" v-html="renderMarkdown(result.result)"></div>

      <!-- JSON / structured data -->
      <div v-else-if="contentType === 'json'" class="result-panel__pre-wrap">
        <pre>{{ jsonContent }}</pre>
      </div>

      <!-- Waiting -->
      <div v-else class="result-panel__waiting">Waiting for data...</div>
    </div>
    <div class="result-panel__footer">
      <button class="result-panel__btn" @click="closeWindow">Close</button>
    </div>
  </div>
</template>

<style scoped>
.result-panel {
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

.result-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.result-panel__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #18181b);
}

.result-panel__close {
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

.result-panel__close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary, #18181b);
}

.result-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  min-height: 0;
}

/* ---- Error ---- */
.result-panel__error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: 10px;
}

.result-panel__error-icon {
  flex-shrink: 0;
  font-size: 18px;
  color: #ef4444;
  display: flex;
  align-items: center;
}

.result-panel__error-text {
  font-size: 13px;
  line-height: 1.5;
  color: #b91c1c;
}

/* ---- Plain text (centered) ---- */
.result-panel__text-centered {
  text-align: center;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary, #52525b);
  padding: 12px 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ---- JSON ---- */
.result-panel__pre-wrap pre {
  font-family: var(--font-mono, 'SF Mono', Menlo, monospace);
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.03);
  border-radius: 8px;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

/* ---- Markdown ---- */
.result-panel__markdown {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary, #52525b);
}

.result-panel__markdown :deep(h1),
.result-panel__markdown :deep(h2),
.result-panel__markdown :deep(h3) {
  margin: 8px 0 4px;
  font-size: 14px;
}

.result-panel__markdown :deep(p) {
  margin: 4px 0;
}

.result-panel__markdown :deep(pre) {
  background: rgba(0, 0, 0, 0.03);
  padding: 8px 10px;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 12px;
}

.result-panel__markdown :deep(code) {
  font-family: var(--font-mono, 'SF Mono', Menlo, monospace);
  font-size: 12px;
}

/* ---- Footer ---- */
.result-panel__footer {
  display: flex;
  justify-content: flex-end;
  padding: 10px 16px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.result-panel__btn {
  padding: 6px 16px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  background: white;
  color: var(--text-secondary, #52525b);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s ease;
}

.result-panel__btn:hover {
  background: rgba(0, 0, 0, 0.04);
}

.result-panel__waiting {
  font-size: 13px;
  color: var(--text-quaternary, #d4d4d8);
  text-align: center;
  padding: 24px;
}
</style>
