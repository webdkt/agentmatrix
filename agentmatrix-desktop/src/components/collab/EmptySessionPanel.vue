<script setup>
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['start-new-task'])

const { t } = useI18n()

const handleStartNew = () => {
  emit('start-new-task')
}
</script>

<template>
  <div class="empty-session-panel">
    <div class="empty-session-panel__content">
      <div class="empty-session-panel__icon">
        <MIcon name="sparkles" />
      </div>
      <h2 class="empty-session-panel__title">
        {{ t('collab.emptyTitle', 'Ready when you are') }}
      </h2>
      <p class="empty-session-panel__description">
        {{ t('collab.emptyDescription', 'Select a conversation from the sidebar, or start a new task to collaborate with an agent.') }}
      </p>

      <div class="empty-session-panel__actions">
        <button class="empty-session-panel__primary-btn" @click="handleStartNew">
          <MIcon name="plus" />
          <span>{{ t('collab.startNewTask', 'Start New Task') }}</span>
        </button>
      </div>

      <p class="empty-session-panel__hint">
        {{ t('collab.emptyHint', 'or select an existing session from the sidebar') }}
      </p>
    </div>

    <!-- Subtle background decoration -->
    <div class="empty-session-panel__bg-decoration" aria-hidden="true">
      <div class="empty-session-panel__bg-ring" />
      <div class="empty-session-panel__bg-ring empty-session-panel__bg-ring--secondary" />
    </div>
  </div>
</template>

<style scoped>
.empty-session-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  background: var(--surface-base);
  min-height: 0;
}

.empty-session-panel__content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 380px;
  padding: var(--spacing-8);
}

.empty-session-panel__icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-xl);
  background: var(--surface-secondary);
  border: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-xl);
  color: var(--text-tertiary);
  margin-bottom: var(--spacing-6);
  transition: all 0.3s var(--ease-out);
}

.empty-session-panel:hover .empty-session-panel__icon {
  color: var(--accent);
  border-color: var(--accent-medium);
  background: var(--accent-muted);
}

.empty-session-panel__title {
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-3) 0;
  letter-spacing: var(--tracking-tight);
}

.empty-session-panel__description {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  line-height: var(--leading-relaxed);
  margin: 0 0 var(--spacing-6) 0;
}

.empty-session-panel__actions {
  margin-bottom: var(--spacing-5);
}

.empty-session-panel__primary-btn {
  height: var(--button-height-lg);
  padding: var(--button-padding-lg);
  background: var(--text-primary);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.empty-session-panel__primary-btn:hover {
  background: #27272A;
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.empty-session-panel__primary-btn:active {
  transform: scale(0.98);
}

.empty-session-panel__hint {
  font-size: var(--font-xs);
  color: var(--text-quaternary);
  margin: 0;
}

/* Background decoration — subtle concentric rings */
.empty-session-panel__bg-decoration {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 0;
}

.empty-session-panel__bg-ring {
  position: absolute;
  width: 480px;
  height: 480px;
  border-radius: 50%;
  border: 1px solid var(--border-light);
  opacity: 0.4;
  animation: ring-pulse 8s ease-in-out infinite;
}

.empty-session-panel__bg-ring--secondary {
  width: 360px;
  height: 360px;
  opacity: 0.25;
  animation-delay: -4s;
  animation-duration: 10s;
}

@keyframes ring-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.3;
  }
  50% {
    transform: scale(1.03);
    opacity: 0.5;
  }
}
</style>
