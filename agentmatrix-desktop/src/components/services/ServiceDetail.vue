<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useServiceStore } from '@/stores/service'
import { serviceAPI } from '@/api/service'
import MIcon from '@/components/icons/MIcon.vue'
import EventTimeline from './EventTimeline.vue'

const { t } = useI18n()
const serviceStore = useServiceStore()

const props = defineProps({
  service: { type: Object, required: true },
})

const emit = defineEmits(['back'])

const status = computed(() => props.service.status || {})
const workers = computed(() => props.service.workers || [])
const actions = computed(() => props.service.actions || [])

const isRunning = computed(() => status.value.running)
const isScanning = computed(() => status.value.scanning)
const inflight = computed(() => status.value.inflight ?? 0)

// Right-panel mode: null = activity feed, workerId = worker events
const selectedWorkerId = computed(() => serviceStore.selectedWorkerId)
const activityEvents = computed(() => serviceStore.serviceEvents)
const workerEventsList = computed(() => {
  const id = selectedWorkerId.value
  return id ? (serviceStore.workerEvents[id] || []) : []
})

async function invokeAction(action) {
  try {
    await serviceAPI.invokeAction(status.value.name, action.id)
  } catch (e) {
    console.error('Action failed:', e)
  }
}

function selectWorker(workerId) {
  serviceStore.selectWorker(workerId)
}

function backToActivity() {
  serviceStore.selectWorker(null)
}

function statusBadgeClass(running) {
  return running ? 'status-badge--running' : 'status-badge--stopped'
}
</script>

<template>
  <div class="service-detail">
    <!-- Top header bar -->
    <div class="service-detail__header">
      <button class="back-btn" @click="emit('back')">
        <MIcon name="arrow-left" :size="18" />
      </button>
      <h2 class="service-detail__name">{{ status.name }}</h2>
      <span :class="['status-badge', statusBadgeClass(isRunning)]">
        {{ isRunning ? t('services.status.running') : t('services.status.stopped') }}
      </span>
    </div>

    <!-- Split panel -->
    <div class="service-detail__body">
      <!-- Left panel: status + actions + workers -->
      <div class="left-panel">
        <!-- Status summary -->
        <div class="status-card">
          <div v-if="isScanning !== undefined" class="status-row">
            <span class="status-row__label">{{ t('services.detail.scanning') }}</span>
            <span :class="['status-row__value', isScanning ? 'status-row__value--active' : '']">
              {{ isScanning ? t('services.detail.yes') : t('services.detail.no') }}
            </span>
          </div>
          <div v-if="inflight !== undefined" class="status-row">
            <span class="status-row__label">{{ t('services.detail.inflight') }}</span>
            <span class="status-row__value">{{ inflight }}</span>
          </div>
        </div>

        <!-- Actions -->
        <div v-if="actions.length" class="actions-block">
          <div class="block-title">{{ t('services.detail.actions') }}</div>
          <div class="actions-list">
            <button
              v-for="action in actions"
              :key="action.id"
              class="action-btn"
              :disabled="isScanning && action.id === 'trigger_scan'"
              @click="invokeAction(action)"
            >
              <MIcon name="play" :size="14" />
              {{ action.name }}
            </button>
          </div>
        </div>

        <!-- Workers -->
        <div class="workers-block">
          <div class="block-title">{{ t('services.workers.title') }}</div>
          <div v-if="!workers.length" class="workers-empty">
            {{ t('services.workers.noWorkers') }}
          </div>
          <div v-else class="workers-list">
            <button
              v-for="w in workers"
              :key="w.id"
              :class="['worker-row', { 'worker-row--active': w.id === selectedWorkerId }]"
              @click="selectWorker(w.id)"
            >
              <span
                :class="['worker-row__dot', w.status === 'working' ? 'worker-row__dot--working' : 'worker-row__dot--idle']"
              ></span>
              <span class="worker-row__name">{{ w.name }}</span>
              <span v-if="w.queue_size" class="worker-row__queue">{{ w.queue_size }}</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Right panel: events (activity or worker) -->
      <div class="right-panel">
        <div class="right-panel__header">
          <template v-if="selectedWorkerId">
            <button class="back-btn" @click="backToActivity">
              <MIcon name="arrow-left" :size="16" />
              <span>{{ t('services.detail.backToActivity') }}</span>
            </button>
            <span class="right-panel__title">{{ selectedWorkerId }}</span>
          </template>
          <template v-else>
            <span class="right-panel__title">{{ t('services.detail.activity') }}</span>
          </template>
        </div>

        <EventTimeline
          :events="selectedWorkerId ? workerEventsList : activityEvents"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.service-detail {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.service-detail__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--spacing-1);
  border-radius: var(--radius-md);
  font-size: 13px;
}

.back-btn:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.service-detail__name {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.status-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 99px;
  font-weight: 500;
}

.status-badge--running {
  background: rgba(46, 160, 67, 0.15);
  color: var(--success);
}

.status-badge--stopped {
  background: var(--surface-hover);
  color: var(--text-tertiary);
}

/* Body split */
.service-detail__body {
  flex: 1;
  display: flex;
  overflow: hidden;
  min-height: 0;
}

.left-panel {
  flex: 0 0 38%;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  padding: var(--spacing-3);
  overflow-y: auto;
  border-right: 1px solid var(--border);
}

.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.right-panel__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.right-panel__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono, monospace);
}

/* Status card */
.status-card {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.status-row__label {
  color: var(--text-secondary);
}

.status-row__value {
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.status-row__value--active {
  color: var(--accent);
  font-weight: 500;
}

/* Blocks */
.block-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: var(--spacing-2);
}

.actions-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
  color: var(--text-primary);
  transition: all var(--duration-base);
}

.action-btn:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--surface-hover);
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Workers list */
.workers-empty {
  color: var(--text-tertiary);
  font-size: 13px;
  padding: var(--spacing-2);
}

.workers-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.worker-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  font-size: 13px;
  cursor: pointer;
  color: var(--text-primary);
  text-align: left;
  transition: all var(--duration-base);
}

.worker-row:hover {
  background: var(--surface-hover);
}

.worker-row--active {
  background: var(--surface-hover);
  border-color: var(--border);
}

.worker-row__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.worker-row__dot--working {
  background: var(--accent);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.worker-row__dot--idle {
  background: var(--text-tertiary);
}

.worker-row__name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-mono, monospace);
}

.worker-row__queue {
  font-size: 11px;
  color: var(--text-tertiary);
  background: var(--surface-secondary);
  padding: 0 6px;
  border-radius: 99px;
  font-variant-numeric: tabular-nums;
}
</style>
