<script setup>
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'

const { t } = useI18n()

const props = defineProps({
  systemName: { type: String, required: true },
  processes: { type: Array, default: () => [] },
  search: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  sendError: { type: String, default: '' },
})

const emit = defineEmits(['select', 'resume', 'back', 'update:search', 'new-process'])

function getStatusLabel(process) {
  if (process.hasActive) {
    const s = process.activeTask.project_status
    if (s === 'WAITING_FOR_USER') return t('automation.status.waiting')
    if (s === 'IN_PROGRESS') return t('automation.status.working')
    return s
  }
  if (process.terminalTask) {
    const s = process.terminalTask.project_status
    if (s === 'COMPLETED') return t('automation.status.completed')
    if (s === 'FAILED') return t('automation.status.failed')
    if (s === 'STOPPED') return t('automation.status.stopped')
  }
  return null
}

function getStatusClass(process) {
  if (process.hasActive) {
    return process.activeTask.project_status === 'WAITING_FOR_USER'
      ? 'status--waiting' : 'status--active'
  }
  if (process.terminalTask) {
    const s = process.terminalTask.project_status
    if (s === 'COMPLETED') return 'status--completed'
    if (s === 'FAILED') return 'status--failed'
    if (s === 'STOPPED') return 'status--stopped'
  }
  return ''
}
</script>

<template>
  <div class="process-selector">
    <!-- Header -->
    <div class="process-selector__header">
      <button class="process-selector__back" @click="emit('back')">
        <MIcon name="arrow-left" />
        <span>{{ t('automation.processes.back') }}</span>
      </button>
      <div>
        <h2 class="process-selector__title">{{ systemName }}</h2>
        <p class="process-selector__desc">{{ t('automation.processes.desc') }}</p>
      </div>
    </div>

    <!-- Search + New -->
    <div class="process-selector__toolbar">
      <div class="process-selector__search">
        <MIcon name="search" class="process-selector__search-icon" />
        <input
          type="text"
          :value="search"
          @input="emit('update:search', $event.target.value)"
          :placeholder="t('automation.processes.searchPlaceholder')"
          class="process-selector__search-input"
        />
      </div>
      <button class="process-selector__new-btn" @click="emit('new-process')">
        <MIcon name="plus" />
        <span>{{ t('automation.processes.newProcess') }}</span>
      </button>
    </div>

    <!-- Send Error -->
    <div v-if="sendError" class="process-selector__error">
      <MIcon name="alert-triangle" class="process-selector__error-icon" />
      <p class="process-selector__error-text">{{ sendError }}</p>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="process-selector__loading">
      <MIcon name="loader" class="spin" />
      <span>{{ t('automation.processes.loading') }}</span>
    </div>

    <!-- Empty -->
    <div v-else-if="processes.length === 0" class="process-selector__empty">
      <MIcon name="folder" class="process-selector__empty-icon" />
      <p class="process-selector__empty-text">{{ t('automation.processes.noProcesses') }}</p>
      <p class="process-selector__empty-hint">{{ t('automation.processes.noProcessesHint') }}</p>
    </div>

    <!-- Grid -->
    <div v-else class="process-selector__grid">
      <div
        v-for="process in processes"
        :key="process.name"
        class="process-card"
      >
        <div class="process-card__header">
          <div class="process-card__icon">
            <MIcon :name="process.hasActive ? 'loader' : 'folder'" :class="{ 'spin': process.hasActive && process.activeTask.project_status === 'IN_PROGRESS' }" />
          </div>
          <span v-if="getStatusLabel(process)" :class="['process-card__status', getStatusClass(process)]">
            <span v-if="process.hasActive" class="process-card__status-dot"></span>
            {{ getStatusLabel(process) }}
          </span>
        </div>
        <h3 class="process-card__name">{{ process.displayName }}</h3>
        <p v-if="process.description" class="process-card__desc">{{ process.description }}</p>

        <!-- Actions -->
        <div class="process-card__actions">
          <button
            v-if="process.hasActive"
            class="process-card__btn process-card__btn--primary"
            @click="emit('resume', process)"
          >
            {{ t('automation.processes.continue') }}
          </button>
          <template v-else-if="process.hasHistory">
            <button
              class="process-card__btn process-card__btn--primary"
              @click="emit('select', process.name)"
            >
              {{ t('automation.processes.newTask') }}
            </button>
            <button
              class="process-card__btn process-card__btn--secondary"
              @click="emit('resume', process)"
            >
              {{ t('automation.processes.lastTask') }}
            </button>
          </template>
          <button
            v-else
            class="process-card__btn process-card__btn--primary"
            @click="emit('select', process.name)"
          >
            {{ t('automation.processes.start') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.process-selector {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px 32px;
  overflow-y: auto;
}

.process-selector__header {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
}

.process-selector__back {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.12s;
  flex-shrink: 0;
  margin-top: 2px;
}

.process-selector__back:hover {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.process-selector__title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.process-selector__desc {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0;
}

.process-selector__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.process-selector__search {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: border-color 0.15s;
}

.process-selector__search:focus-within {
  border-color: var(--accent);
}

.process-selector__search-icon {
  font-size: 14px;
  color: var(--text-quaternary);
  flex-shrink: 0;
}

.process-selector__search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
}

.process-selector__search-input::placeholder {
  color: var(--text-quaternary);
}

.process-selector__new-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s;
  flex-shrink: 0;
}

.process-selector__new-btn:hover {
  background: var(--accent-hover);
}

.process-selector__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.process-selector__error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: rgba(234, 179, 8, 0.08);
  border: 1px solid rgba(234, 179, 8, 0.2);
  border-radius: var(--radius-md);
  font-size: 12px;
  color: #ca8a04;
}

.process-selector__error-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.process-selector__error-text {
  margin: 0;
}

.process-selector__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  text-align: center;
}

.process-selector__empty-icon {
  font-size: 32px;
  color: var(--text-quaternary);
  margin-bottom: 12px;
  opacity: 0.5;
}

.process-selector__empty-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin: 0 0 6px 0;
}

.process-selector__empty-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

.process-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.process-card {
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: all 0.15s ease;
}

.process-card:hover {
  border-color: var(--border-strong);
}

.process-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.process-card__icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: var(--accent);
}

.process-card__status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  letter-spacing: 0.02em;
}

.process-card__status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.status--active {
  background: rgba(34, 197, 94, 0.1);
  color: #16a34a;
}

.status--waiting {
  background: rgba(234, 179, 8, 0.1);
  color: #ca8a04;
}

.status--completed {
  background: rgba(34, 197, 94, 0.08);
  color: #16a34a;
}

.status--failed {
  background: rgba(239, 68, 68, 0.08);
  color: #dc2626;
}

.status--stopped {
  background: rgba(107, 114, 128, 0.08);
  color: #6b7280;
}

.process-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 2px 0;
}

.process-card__desc {
  font-size: 11px;
  color: var(--text-tertiary);
  margin: 0 0 12px 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.process-card__actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
}

.process-card__btn {
  flex: 1;
  padding: 7px 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.12s;
  border: none;
}

.process-card__btn--primary {
  background: var(--accent);
  color: white;
}

.process-card__btn--primary:hover {
  background: var(--accent-hover);
}

.process-card__btn--secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
}

.process-card__btn--secondary:hover {
  background: var(--surface-hover);
  border-color: var(--border-strong);
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
