<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  karaokeTriple: {
    type: Array,
    default: () => [],
  },
  isAutoScrolling: {
    type: Boolean,
    default: true,
  },
  unreadCount: {
    type: Number,
    default: 0,
  },
})

const emit = defineEmits(['scroll-pause', 'scroll-resume'])

// ---- Alignment detection ----
const streamRef = ref(null)
const alignLeft = ref(false)

function checkAlignment() {
  if (!streamRef.value) return
  const rect = streamRef.value.getBoundingClientRect()
  // If the stream's left edge is at or past screen left, switch to left-align
  alignLeft.value = rect.left < 4
}

// ---- Timestamp formatting ----
function formatTimestamp(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  const date = d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
  return `${date} ${time}`
}

// ---- Event display helpers ----
function eventSummary(event) {
  const { renderType, detail, eventName } = event
  switch (renderType) {
    case 'thought':
      return truncate(detail.thought || detail.body_preview || '', 120)
    case 'agent-comm': {
      if (eventName === 'received') return `收到来自 ${detail.sender || '未知'} 的邮件`
      return ''
    }
    case 'system':
      return eventName
    default:
      return ''
  }
}

function eventIcon(event) {
  switch (event.renderType) {
    case 'thought': return 'logo'
    case 'agent-comm': return 'mail'
    case 'system': return 'info'
    default: return null
  }
}

function truncate(str, len) {
  if (!str) return ''
  return str.length > len ? str.slice(0, len) + '...' : str
}

// ---- Mouse interaction ----
function onMouseEnter() {
  emit('scroll-pause')
  checkAlignment()
}

function onMouseLeave() {
  emit('scroll-resume')
}

async function handleClick(event) {
  const hasContent = event.renderType === 'thought'
  if (!hasContent) return

  try {
    await invoke('create_detail_window')
  } catch (e) {
    console.error('[KaraokeStream] Failed to open detail:', e)
  }
}

// ---- Lifecycle ----
onMounted(() => {
  checkAlignment()
  window.addEventListener('resize', checkAlignment)
})
onUnmounted(() => {
  window.removeEventListener('resize', checkAlignment)
})
</script>

<template>
  <div
    ref="streamRef"
    class="karaoke-stream"
    :class="{ 'karaoke-stream--align-left': alignLeft }"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
  >
    <!-- Empty state -->
    <div v-if="karaokeTriple.length === 0" class="karaoke-empty">
      No events yet
    </div>

    <TransitionGroup name="karaoke-roll" tag="div" class="karaoke-roller">
      <div
        v-for="event in karaokeTriple"
        :key="event.id"
        class="karaoke-slot"
        :class="`karaoke-slot--${event._slot}`"
      >
        <!-- Coming placeholder -->
        <template v-if="event._placeholder">
          <div class="karaoke-coming">
            <span class="karaoke-coming__dots">
              <span class="karaoke-coming__dot"></span>
              <span class="karaoke-coming__dot"></span>
              <span class="karaoke-coming__dot"></span>
            </span>
            <!-- Unread badge when paused -->
            <span v-if="unreadCount > 0" class="karaoke-unread">
              {{ unreadCount }}
            </span>
          </div>
        </template>

        <!-- Session time -->
        <template v-else-if="event.renderType === 'session-time'">
          <div class="karaoke-time">
            {{ formatTimestamp(event.timestamp) }}
          </div>
        </template>

        <!-- Normal message -->
        <template v-else>
          <div class="karaoke-msg" @click="handleClick(event)">
            <div class="karaoke-msg__icon" v-if="eventIcon(event)">
              <MIcon :name="eventIcon(event)" />
            </div>
            <div class="karaoke-msg__body">
              <div class="karaoke-msg__text">
                {{ eventSummary(event) }}
              </div>
              <div class="karaoke-msg__ts">{{ formatTimestamp(event.timestamp) }}</div>
            </div>
          </div>
        </template>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.karaoke-stream {
  position: relative;
  width: 100%;
  padding: 0 14px;
  overflow: hidden;
  flex: 1;
  min-height: 0;
  box-sizing: border-box;
}

.karaoke-stream--align-left {
  align-self: flex-start;
}

.karaoke-roller {
  display: flex;
  flex-direction: column;
  position: relative;
  background: transparent;
  border: none;
  border-radius: 16px;
  padding: 8px 14px;
  height: 100%;
  box-sizing: border-box;
}

.karaoke-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px 0;
  color: var(--text-quaternary, #d4d4d8);
  font-size: 12px;
}

/* ---- Slot states ---- */
.karaoke-slot {
  transition: opacity 0.4s ease;
  cursor: pointer;
}

.karaoke-slot--previous {
  opacity: 0.35;
  -webkit-mask-image: linear-gradient(to bottom, black 50%, transparent 100%);
  mask-image: linear-gradient(to bottom, black 50%, transparent 100%);
  flex-shrink: 0;
  margin-top: auto;
}

.karaoke-slot--current {
  opacity: 1.0;
  flex-shrink: 0;
}

.karaoke-slot--coming {
  opacity: 0.6;
  flex-shrink: 0;
  margin-bottom: auto;
}

.karaoke-slot--previous + .karaoke-slot--current {
  margin-top: 8px;
}

.karaoke-slot--current + .karaoke-slot--coming {
  margin-top: 8px;
}

/* ---- Coming placeholder ---- */
.karaoke-coming {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 6px 0;
}

.karaoke-coming__dots {
  display: flex;
  gap: 4px;
}

.karaoke-coming__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--text-quaternary, #d4d4d8);
  animation: coming-pulse 1.4s ease-in-out infinite;
}

.karaoke-coming__dot:nth-child(2) {
  animation-delay: 0.2s;
}

.karaoke-coming__dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes coming-pulse {
  0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
  40% { opacity: 1; transform: scale(1.2); }
}

/* ---- Unread badge ---- */
.karaoke-unread {
  background: var(--error, #B57171);
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 1;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 5px;
}

/* ---- Message ---- */
.karaoke-msg {
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.karaoke-msg__icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  font-size: 13px;
  color: var(--text-quaternary, #d4d4d8);
  margin-top: 2px;
}

.karaoke-msg__body {
  flex: 1;
  min-width: 0;
}

.karaoke-msg__text {
  font-size: 13px;
  line-height: 1.5;
  color: var(--text-secondary, #52525b);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.karaoke-slot--previous .karaoke-msg__text {
  -webkit-line-clamp: 2;
}

.karaoke-slot--coming .karaoke-msg__text {
  -webkit-line-clamp: 2;
}

.karaoke-msg__ts {
  font-size: 10px;
  color: var(--text-quaternary, #d4d4d8);
  margin-top: 1px;
}


/* ---- Time ---- */
.karaoke-time {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px 8px;
  font-size: 10px;
  color: var(--text-quaternary, #d4d4d8);
  opacity: 0.6;
}

/* ---- Roller transition (vertical slide) ---- */
.karaoke-roll-enter-active {
  transition: all 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}
.karaoke-roll-leave-active {
  transition: all 0.35s ease-in;
  position: absolute;
  width: calc(100% - 28px);
}
.karaoke-roll-move {
  transition: transform 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}
.karaoke-roll-enter-from {
  opacity: 0;
  transform: translateY(20px);
}
.karaoke-roll-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
</style>
