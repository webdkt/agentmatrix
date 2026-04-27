<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import MIcon from '@/components/icons/MIcon.vue'
import { useUIStore } from '@/stores/ui'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  emailData: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['close', 'view'])

const uiStore = useUIStore()
const { t } = useI18n()

const email = computed(() => props.emailData || {})

const renderedBody = computed(() => {
  if (!email.value.body) return ''
  try {
    return marked(email.value.body)
  } catch (error) {
    console.error('Markdown rendering error:', error)
    return email.value.body
  }
})

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const close = () => {
  emit('close')
}

const viewSession = () => {
  emit('view', email.value)
  close()
}

const handleOverlayClick = () => {
  close()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="show" class="email-notify-modal">
        <div class="email-notify-modal__overlay" @click="handleOverlayClick"></div>

        <div class="email-notify-modal__content">
          <div class="email-notify-modal__header">
            <div class="email-notify-modal__title-group">
              <div class="email-notify-modal__icon">
                <MIcon name="mail" />
              </div>
              <div class="email-notify-modal__title-text">
                <h2 class="email-notify-modal__title">{{ t('emails.newEmail') }}</h2>
                <span class="email-notify-modal__time">{{ formatTime(email.timestamp) }}</span>
              </div>
            </div>
            <button @click="close" class="email-notify-modal__close">
              <MIcon name="x" />
            </button>
          </div>

          <div class="email-notify-modal__body">
            <div class="email-email-card">
              <div class="email-email-card__header">
                <div class="email-email-card__sender">
                  <span class="email-email-card__label">FROM</span>
                  <span class="email-email-card__name">
                    <MIcon name="agent-dispatch" />
                    {{ email.sender || '-' }}
                  </span>
                </div>
                <div class="email-email-card__recipient">
                  <span class="email-email-card__label">TO</span>
                  <span class="email-email-card__name">
                    <MIcon name="send" />
                    {{ email.recipient || '-' }}
                  </span>
                </div>
              </div>

              <div v-if="email.subject" class="email-email-card__subject">
                {{ email.subject }}
              </div>

              <div class="email-email-card__body markdown-content" v-html="renderedBody"></div>
            </div>
          </div>

          <div class="email-notify-modal__footer">
            <button @click="close" class="email-notify-modal__btn email-notify-modal__btn--secondary">
              {{ t('common.close') }}
            </button>
            <button @click="viewSession" class="email-notify-modal__btn email-notify-modal__btn--primary">
              <MIcon name="arrow-right" />
              {{ t('common.view') }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.email-notify-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}

.email-notify-modal__overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(2px);
}

.email-notify-modal__content {
  position: relative;
  width: 90vw;
  max-width: 800px;
  height: 80vh;
  max-height: 700px;
  background: var(--surface-secondary);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.email-notify-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--surface-base);
}

.email-notify-modal__title-group {
  display: flex;
  align-items: center;
  gap: 14px;
}

.email-notify-modal__icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-muted);
  border-radius: var(--radius-lg);
  color: var(--accent);
  font-size: 22px;
}

.email-notify-modal__title-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.email-notify-modal__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.email-notify-modal__time {
  font-size: 12px;
  color: var(--text-tertiary);
}

.email-notify-modal__close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  transition: all 0.2s;
  font-size: 18px;
}

.email-notify-modal__close:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.email-notify-modal__body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  background: var(--surface-base);
}

.email-email-card {
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--spacing-6);
  position: relative;
  border-left: 4px solid var(--accent);
}

.email-email-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-4);
  padding-bottom: var(--spacing-4);
  border-bottom: 1px solid var(--surface-hover);
}

.email-email-card__sender,
.email-email-card__recipient {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
}

.email-email-card__label {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  padding: 4px 10px;
  border-radius: var(--radius-md);
  color: var(--accent);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
}

.email-email-card__recipient .email-email-card__label {
  color: var(--success-600);
  background: var(--success-50);
  border-color: var(--success-200);
}

.email-email-card__name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.email-email-card__name i {
  font-size: 16px;
  color: var(--accent);
}

.email-email-card__recipient .email-email-card__name i {
  color: var(--success-500);
}

.email-email-card__subject {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  padding-bottom: var(--spacing-4);
  margin-bottom: var(--spacing-4);
  border-bottom: 1px solid var(--surface-hover);
}

.email-email-card__body {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.email-notify-modal__footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  background: var(--surface-base);
}

.email-notify-modal__btn {
  padding: 10px 20px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  display: flex;
  align-items: center;
  gap: 8px;
}

.email-notify-modal__btn--secondary {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.email-notify-modal__btn--secondary:hover {
  background: var(--border);
}

.email-notify-modal__btn--primary {
  background: var(--accent);
  color: white;
}

.email-notify-modal__btn--primary:hover {
  background: var(--accent-hover);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.markdown-content :deep(p) {
  margin-bottom: 12px;
}

.markdown-content :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--border);
  padding: 8px 12px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: var(--surface-secondary);
  font-weight: 600;
}

.markdown-content :deep(code) {
  background: var(--surface-hover);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}
</style>