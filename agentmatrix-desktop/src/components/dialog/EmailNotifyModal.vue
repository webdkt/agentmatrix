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
  background: var(--parchment-100, #faf8f5);
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.email-notify-modal__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid var(--parchment-300, #e5e0d8);
  background: var(--parchment-50, #fdfcfa);
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
  background: var(--accent-100, #f5efe9);
  border-radius: 10px;
  color: var(--accent-500, #6b4c3b);
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
  color: var(--neutral-800, #2d2d2d);
  margin: 0;
}

.email-notify-modal__time {
  font-size: 12px;
  color: var(--neutral-400, #9b9b9b);
}

.email-notify-modal__close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  color: var(--neutral-500, #6b6b6b);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.2s;
  font-size: 18px;
}

.email-notify-modal__close:hover {
  background: var(--parchment-200, #e8e4de);
  color: var(--neutral-700, #3d3d3d);
}

.email-notify-modal__body {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  background: var(--parchment-50, #fdfcfa);
}

.email-email-card {
  background: var(--parchment-100);
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-sm);
  padding: var(--spacing-lg);
  position: relative;
  border-left: 4px solid var(--accent);
}

.email-email-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--neutral-100);
}

.email-email-card__sender,
.email-email-card__recipient {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.email-email-card__label {
  font-size: 11px;
  font-weight: 600;
  font-variant: small-caps;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  color: var(--accent);
  background: var(--parchment-100);
  border: 1px solid var(--neutral-200);
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
  color: var(--neutral-900);
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
  color: var(--neutral-900);
  padding-bottom: var(--spacing-md);
  margin-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--neutral-100);
}

.email-email-card__body {
  font-size: 14px;
  color: var(--neutral-700);
  line-height: 1.7;
}

.email-notify-modal__footer {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding: 16px 24px;
  border-top: 1px solid var(--parchment-300, #e5e0d8);
  background: var(--parchment-50, #fdfcfa);
}

.email-notify-modal__btn {
  padding: 10px 20px;
  border-radius: 8px;
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
  background: var(--parchment-200, #e8e4de);
  color: var(--neutral-700, #3d3d3d);
}

.email-notify-modal__btn--secondary:hover {
  background: var(--parchment-300, #dcd8d2);
}

.email-notify-modal__btn--primary {
  background: var(--accent-500, #6b4c3b);
  color: white;
}

.email-notify-modal__btn--primary:hover {
  background: var(--accent-600, #5a3f2f);
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
  border: 1px solid var(--neutral-200);
  padding: 8px 12px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: var(--parchment-100);
  font-weight: 600;
}

.markdown-content :deep(code) {
  background: var(--parchment-200);
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