<script setup>
import { computed, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import MIcon from '@/components/icons/MIcon.vue'

const DESIGNER_AGENT = 'Designer'

const props = defineProps({
  // 是否高亮当前 currentSession（history tab 用得着，欢迎屏继续路径无所谓）
  highlightCurrent: { type: Boolean, default: true },
})

const emit = defineEmits(['select'])

const sessionStore = useSessionStore()

const designerSessions = computed(() => {
  return (sessionStore.sessions || [])
    .filter(s => (s.agent_name === DESIGNER_AGENT || s.name === DESIGNER_AGENT)
      && !s._isPlaceholder)
    .sort((a, b) => new Date(b.timestamp || b.last_email_time || 0)
      - new Date(a.timestamp || a.last_email_time || 0))
})

const currentSessionId = computed(() => sessionStore.currentSession?.session_id)

onMounted(async () => {
  // 保证列表有数据；welcome / history 都可能在本组件首次挂载时 store 还没填
  if (!sessionStore.sessions?.length) {
    try { await sessionStore.fetchSessions() } catch (e) {
      console.warn('DesignSessionList: fetchSessions failed:', e)
    }
  }
})

function formatTime(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))
  if (diffDays === 0) {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', hour12: false,
    })
  }
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) {
    return date.toLocaleDateString('en-US', { weekday: 'short' })
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function handleClick(session) {
  emit('select', session)
}
</script>

<template>
  <div class="design-session-list">
    <div v-if="designerSessions.length === 0" class="design-session-list__empty">
      <MIcon name="palette" />
      <p>还没有设计</p>
      <p class="design-session-list__empty-hint">开始一个新设计吧</p>
    </div>

    <div v-else class="design-session-list__items">
      <button
        v-for="session in designerSessions"
        :key="session.session_id"
        type="button"
        class="design-session-list__item"
        :class="{
          'design-session-list__item--active':
            highlightCurrent && session.session_id === currentSessionId,
        }"
        @click="handleClick(session)"
      >
        <div class="design-session-list__item-main">
          <div class="design-session-list__subject">
            {{ session.subject || '未命名设计' }}
          </div>
          <div class="design-session-list__time">
            {{ formatTime(session.timestamp || session.last_email_time) }}
          </div>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.design-session-list {
  height: 100%;
  overflow-y: auto;
  padding: var(--spacing-2);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
}

.design-session-list__items {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.design-session-list__item {
  display: flex;
  align-items: center;
  padding: var(--spacing-2) var(--spacing-3);
  background: transparent;
  border: 1px solid transparent;
  border-left: 2px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-base) var(--ease-out);
  font: inherit;
  color: var(--text-primary);
}

.design-session-list__item:hover {
  background: var(--surface-hover);
}

.design-session-list__item--active {
  background: var(--surface-secondary);
  border-left-color: var(--accent);
}

.design-session-list__item--active .design-session-list__subject {
  font-weight: var(--font-weight-semibold);
}

.design-session-list__item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.design-session-list__subject {
  font-size: var(--font-sm);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.design-session-list__time {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
}

/* Empty */
.design-session-list__empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  color: var(--text-tertiary);
  text-align: center;
  padding: var(--spacing-8) var(--spacing-4);
}

.design-session-list__empty .m-icon {
  font-size: 32px;
  color: var(--text-quaternary);
}

.design-session-list__empty p {
  margin: 0;
  font-size: var(--font-sm);
}

.design-session-list__empty-hint {
  font-size: var(--font-xs) !important;
  color: var(--text-quaternary);
}
</style>
