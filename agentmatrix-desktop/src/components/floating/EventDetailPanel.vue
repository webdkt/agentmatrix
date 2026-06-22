<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { emit as tauriEmit } from '@tauri-apps/api/event'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import MIcon from '@/components/icons/MIcon.vue'
import { renderMarkdown } from '@/utils/markdown'

// Parse event data from URL hash
const event = ref(null)

function parseEventFromHash() {
  const hash = window.location.hash.slice(1)
  const params = {}
  hash.split('&').forEach(pair => {
    const eqIdx = pair.indexOf('=')
    if (eqIdx > 0) {
      const key = decodeURIComponent(pair.slice(0, eqIdx))
      const val = decodeURIComponent(pair.slice(eqIdx + 1))
      params[key] = val
    }
  })
  if (params.event) {
    try {
      event.value = JSON.parse(params.event)
    } catch (e) {
      console.error('[Detail] Failed to parse event JSON:', e)
    }
  }
}
parseEventFromHash()

const renderedMarkdown = computed(() => {
  if (!event.value) return ''
  const text = getFullText(event.value)
  return renderMarkdown(text || '')
})

function getFullText(evt) {
  const { renderType, detail } = evt
  switch (renderType) {
    case 'bubble-user':
    case 'bubble-agent':
      return detail.body_preview || detail.body || ''
    case 'thought':
      return detail.thought || ''
    case 'pill':
      return detail.action_label || detail.action_name || ''
    default:
      return evt.eventName || ''
  }
}

function typeLabel(renderType) {
  switch (renderType) {
    case 'bubble-user': return '用户消息'
    case 'bubble-agent': return 'Agent 回复'
    case 'thought': return '思考'
    case 'pill': return 'Action'
    case 'agent-comm': return '邮件'
    default: return renderType
  }
}

async function closeWindow() {
  await tauriEmit('detail:closed')
  const win = getCurrentWebviewWindow()
  await win.hide()
}

onMounted(() => {
  window.addEventListener('hashchange', parseEventFromHash)
  document.querySelector('.detail-panel__close')?.focus()
})

onUnmounted(() => {
  window.removeEventListener('hashchange', parseEventFromHash)
})
</script>

<template>
  <div class="detail-panel" v-if="event">
    <div class="detail-panel__header">
      <span class="detail-panel__type">{{ typeLabel(event.renderType) }}</span>
      <span class="detail-panel__time">
        {{ new Date(event.timestamp).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) }}
      </span>
      <button class="detail-panel__close" @click="closeWindow" title="Close">
        <MIcon name="x" />
      </button>
    </div>
    <div class="detail-panel__body" v-html="renderedMarkdown"></div>
  </div>
</template>

<style scoped>
.detail-panel {
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

.detail-panel__header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  flex-shrink: 0;
}

.detail-panel__type {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #52525b);
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 8px;
  border-radius: 6px;
}

.detail-panel__time {
  font-size: 11px;
  color: var(--text-quaternary, #d4d4d8);
  flex: 1;
}

.detail-panel__close {
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

.detail-panel__close:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary, #18181b);
}

.detail-panel__body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary, #52525b);
}

.detail-panel__body :deep(p) {
  margin: 0 0 8px;
}

.detail-panel__body :deep(p:last-child) {
  margin-bottom: 0;
}

.detail-panel__body :deep(code) {
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 12px;
  background: rgba(0, 0, 0, 0.04);
  padding: 1px 4px;
  border-radius: 3px;
}

.detail-panel__body :deep(pre) {
  background: rgba(0, 0, 0, 0.04);
  border-radius: 8px;
  padding: 12px;
  overflow-x: auto;
  margin: 8px 0;
}

.detail-panel__body :deep(pre code) {
  background: none;
  padding: 0;
}
</style>
