<script setup>
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'

const { t } = useI18n()

const props = defineProps({
  systems: { type: Array, default: () => [] },
  search: { type: String, default: '' },
  loading: { type: Boolean, default: false },
  rootDir: { type: String, default: '' },
  loadError: { type: String, default: '' },
})

const emit = defineEmits(['select', 'update:search', 'new-system'])

function getStatusLabel(system) {
  if (system.hasActive) {
    const status = system.activeTask.project_status
    if (status === 'WAITING_FOR_USER') return t('automation.status.waiting')
    return t('automation.status.working')
  }
  if (system.latestTask) {
    return t('automation.status.last', { status: system.latestTask.project_status })
  }
  return null
}

function getStatusClass(system) {
  if (system.hasActive) {
    return system.activeTask.project_status === 'WAITING_FOR_USER'
      ? 'status--waiting' : 'status--active'
  }
  if (system.latestTask) {
    const s = system.latestTask.project_status
    if (s === 'COMPLETED') return 'status--completed'
    if (s === 'FAILED') return 'status--failed'
    if (s === 'STOPPED') return 'status--stopped'
  }
  return ''
}
</script>

<template>
  <div class="system-selector">
    <!-- Description -->
    <p class="system-selector__desc">{{ t('automation.systems.desc') }}</p>

    <!-- Search + New -->
    <div class="system-selector__toolbar">
      <div class="system-selector__search">
        <MIcon name="search" class="system-selector__search-icon" />
        <input
          type="text"
          :value="search"
          @input="emit('update:search', $event.target.value)"
          :placeholder="t('automation.systems.searchPlaceholder')"
          class="system-selector__search-input"
        />
      </div>
      <button class="system-selector__new-btn" @click="emit('new-system')">
        <MIcon name="plus" />
        <span>{{ t('automation.systems.newSystem') }}</span>
      </button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="system-selector__loading">
      <MIcon name="loader" class="spin" />
      <span>{{ t('automation.systems.loading') }}</span>
    </div>

    <!-- Error -->
    <div v-else-if="loadError" class="system-selector__error">
      <MIcon name="alert-triangle" class="system-selector__error-icon" />
      <p class="system-selector__error-text">{{ t('automation.systems.loadFailed') }}</p>
      <p class="system-selector__error-hint">{{ loadError }}</p>
    </div>

    <!-- Empty -->
    <div v-else-if="systems.length === 0" class="system-selector__empty">
      <MIcon name="folder" class="system-selector__empty-icon" />
      <p class="system-selector__empty-text">{{ t('automation.systems.noSystems') }}</p>
      <p class="system-selector__empty-hint">
        {{ t('automation.systems.noSystemsHint', { dir: rootDir || '~/automation_knowledge' }) }}
      </p>
    </div>

    <!-- Grid -->
    <div v-else class="system-selector__grid">
      <button
        v-for="system in systems"
        :key="system.name"
        class="system-card"
        @click="emit('select', system.name)"
      >
        <div class="system-card__header">
          <div class="system-card__icon">
            <MIcon :name="system.icon || 'globe'" />
          </div>
          <span v-if="getStatusLabel(system)" :class="['system-card__status', getStatusClass(system)]">
            <span v-if="system.hasActive" class="system-card__status-dot"></span>
            {{ getStatusLabel(system) }}
          </span>
        </div>
        <h3 class="system-card__name">{{ system.displayName }}</h3>
        <p v-if="system.description" class="system-card__desc">{{ system.description }}</p>
        <p v-if="system.taskCount > 0" class="system-card__meta">
          {{ t('automation.systems.tasks', system.taskCount) }}
        </p>
      </button>
    </div>
  </div>
</template>

<style scoped>
.system-selector {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px 32px;
  overflow-y: auto;
}

.system-selector__desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
  line-height: 1.5;
}

.system-selector__toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.system-selector__search {
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

.system-selector__search:focus-within {
  border-color: var(--accent);
}

.system-selector__search-icon {
  font-size: 14px;
  color: var(--text-quaternary);
  flex-shrink: 0;
}

.system-selector__search-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
}

.system-selector__search-input::placeholder {
  color: var(--text-quaternary);
}

.system-selector__new-btn {
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

.system-selector__new-btn:hover {
  background: var(--accent-hover);
}

.system-selector__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 48px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.system-selector__error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  text-align: center;
}

.system-selector__error-icon {
  font-size: 32px;
  color: var(--error, #dc2626);
  margin-bottom: 12px;
  opacity: 0.7;
}

.system-selector__error-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin: 0 0 6px 0;
}

.system-selector__error-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
  max-width: 400px;
  word-break: break-word;
}

.system-selector__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px;
  text-align: center;
}

.system-selector__empty-icon {
  font-size: 32px;
  color: var(--text-quaternary);
  margin-bottom: 12px;
  opacity: 0.5;
}

.system-selector__empty-text {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  margin: 0 0 6px 0;
}

.system-selector__empty-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin: 0;
}

.system-selector__empty-hint code {
  background: var(--surface-hover);
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 11px;
}

.system-selector__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.system-card {
  display: flex;
  flex-direction: column;
  padding: 20px;
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.system-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.system-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.system-card__icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: var(--accent);
}

.system-card__status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  letter-spacing: 0.02em;
}

.system-card__status-dot {
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

.system-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 2px 0;
}

.system-card__desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 0 0 8px 0;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.system-card__meta {
  font-size: 11px;
  color: var(--text-tertiary);
  margin: 0;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
