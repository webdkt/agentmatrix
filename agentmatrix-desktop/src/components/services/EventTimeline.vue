<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps({
  events: { type: Array, default: () => [] },
  maxHeight: { type: String, default: '100%' },
  emptyText: { type: String, default: '' },
})

const scrollEl = ref(null)

// Auto-scroll to bottom on new events
watch(
  () => props.events.length,
  async () => {
    await nextTick()
    if (scrollEl.value) {
      scrollEl.value.scrollTop = scrollEl.value.scrollHeight
    }
  },
)

// Parse event_detail (JSON string) into object
function parseDetail(evt) {
  const raw = evt.event_detail
  if (!raw) return {}
  if (typeof raw !== 'string') return raw
  try { return JSON.parse(raw) } catch { return { _raw: raw } }
}

// Service event label (i18n with interpolated detail fields)
function serviceLabel(evt) {
  const detail = parseDetail(evt)
  const key = `services.events.${evt.event_name}`
  const fallback = `${evt.event_name}${Object.keys(detail).length ? ' · ' + JSON.stringify(detail) : ''}`
  try {
    return t(key, { ...detail }) !== key ? t(key, { ...detail }) : fallback
  } catch {
    return fallback
  }
}

// Extract thought text (think.brain events)
function thoughtText(evt) {
  const detail = parseDetail(evt)
  return detail.thought || detail.text || ''
}

// Action pill label
function pillText(evt) {
  const detail = parseDetail(evt)
  if (evt.event_name === 'started') return detail.action_name || ''
  if (evt.event_name === 'completed') {
    const label = detail.action_label || detail.action_name || ''
    if (detail.status === 'error') return `${label} 出错`
    if (detail.status === 'canceled') return `${label} 已取消`
    return label
  }
  if (evt.event_name === 'error') {
    const label = detail.action_label || detail.action_name || ''
    return `${label} 出错`
  }
  if (evt.event_name === 'detected') {
    const actions = detail.actions || []
    return actions.length ? `detected: ${actions.join(', ')}` : ''
  }
  return `${evt.event_name}`
}

// Time-only formatting
function timeOnly(ts) {
  if (!ts) return ''
  // ISO "2026-06-14T10:23:45.123Z" → "10:23:45"
  return ts.slice(11, 19)
}
</script>

<template>
  <div ref="scrollEl" class="event-timeline" :style="{ maxHeight: props.maxHeight }">
    <div v-if="!events.length" class="event-timeline__empty">
      {{ emptyText || t('services.events.noEvents') }}
    </div>

    <template v-for="(evt, i) in events" :key="i">
      <!-- Service event: centered system line -->
      <div v-if="evt.event_type === 'service'" class="evt-system">
        <span class="evt-system__text">{{ serviceLabel(evt) }}</span>
        <span class="evt-system__time">{{ timeOnly(evt.timestamp) }}</span>
      </div>

      <!-- Think: thought style (inner monologue) -->
      <div v-else-if="evt.event_type === 'think' && thoughtText(evt)" class="evt-thought">
        <div class="evt-thought__body">{{ thoughtText(evt) }}</div>
      </div>

      <!-- Action: pill style (colored dot + label) -->
      <div v-else-if="evt.event_type === 'action'" class="evt-pill">
        <div :class="['evt-pill__capsule', `evt-pill__capsule--${evt.event_name}`]">
          <span class="evt-pill__text">{{ pillText(evt) }}</span>
        </div>
      </div>

      <!-- Fallback: minimal -->
      <div v-else class="evt-system">
        <span class="evt-system__text">{{ evt.event_type }}.{{ evt.event_name }}</span>
        <span class="evt-system__time">{{ timeOnly(evt.timestamp) }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.event-timeline {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-4);
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.event-timeline__empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--spacing-8);
  font-size: 13px;
  margin: auto 0;
}

/* ===== Service event: centered system line ===== */
.evt-system {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: 4px 0;
  animation: fadeIn 200ms var(--ease-out);
}

.evt-system__text {
  font-size: 11px;
  color: var(--text-quaternary, var(--text-tertiary));
  text-align: center;
}

.evt-system__time {
  font-size: 10px;
  color: var(--text-quaternary, var(--text-tertiary));
  font-variant-numeric: tabular-nums;
}

/* ===== Thought: inner monologue ===== */
.evt-thought {
  align-self: flex-start;
  max-width: 90%;
  animation: fadeIn 250ms var(--ease-out);
}

.evt-thought__body {
  color: rgba(60, 60, 60, 0.75);
  font-size: 13px;
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Monaco', 'PingFang SC', 'Microsoft YaHei', monospace;
  line-height: 1.5;
  letter-spacing: -0.01em;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ===== Action pill ===== */
.evt-pill {
  display: flex;
  justify-content: flex-start;
  animation: fadeIn 250ms var(--ease-out);
}

.evt-pill__capsule {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.evt-pill__capsule::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--teal, #14b8a6);
  flex-shrink: 0;
}

.evt-pill__capsule--started::before {
  background: var(--info, #3b82f6);
}

.evt-pill__capsule--completed::before {
  background: var(--success, #10b981);
}

.evt-pill__capsule--completed::after {
  content: '✓';
  color: #10b981;
  font-size: 13px;
  font-weight: 500;
  margin-left: 4px;
}

.evt-pill__capsule--error::before {
  background: var(--error, #ef4444);
}

.evt-pill__text {
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

/* ===== Animations ===== */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
