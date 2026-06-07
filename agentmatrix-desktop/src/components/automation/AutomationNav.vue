<script setup>
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'

const { t } = useI18n()

const props = defineProps({
  state: { type: String, required: true },
  selectedSystem: { type: String, default: null },
  selectedProcess: { type: String, default: null },
})

const emit = defineEmits(['navigate'])

function goHome() {
  emit('navigate', 'home')
}

function goSystem() {
  emit('navigate', 'system')
}
</script>

<template>
  <nav class="automation-nav">
    <button class="automation-nav__item" :class="{ 'automation-nav__item--current': state === 'system-select' }" @click="goHome">
      <MIcon name="bolt" class="automation-nav__icon" />
      <span>{{ t('automation.nav.automation') }}</span>
    </button>
    <template v-if="selectedSystem">
      <MIcon name="chevron-right" class="automation-nav__separator" />
      <button
        class="automation-nav__item"
        :class="{ 'automation-nav__item--current': state === 'process-select' }"
        @click="goSystem"
      >
        <MIcon name="globe" class="automation-nav__icon" />
        <span>{{ selectedSystem }}</span>
      </button>
    </template>
    <template v-if="selectedProcess && (state === 'session' || state === 'sending')">
      <MIcon name="chevron-right" class="automation-nav__separator" />
      <span class="automation-nav__item automation-nav__item--current">
        <MIcon name="folder" class="automation-nav__icon" />
        <span>{{ selectedProcess }}</span>
      </span>
    </template>
  </nav>
</template>

<style scoped>
.automation-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 16px;
  background: var(--surface-secondary);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
  min-height: 36px;
}

.automation-nav__item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 6px;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all 0.12s ease;
}

.automation-nav__item:hover:not(.automation-nav__item--current) {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.automation-nav__item--current {
  color: var(--text-primary);
  font-weight: 600;
  cursor: default;
}

.automation-nav__icon {
  font-size: 12px;
  opacity: 0.6;
}

.automation-nav__separator {
  font-size: 10px;
  color: var(--text-quaternary);
}
</style>
