<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  emailData: {
    type: Object,
    default: () => ({})
  },
  duration: {
    type: Number,
    default: 3000
  }
})

const emit = defineEmits(['close', 'click'])

const { t } = useI18n()
const localShow = ref(props.show)
let timer = null

const truncatedSubject = computed(() => {
  const subject = (props.emailData || {}).subject || ''
  return subject.length > 30 ? subject.substring(0, 30) + '...' : subject
})

const emailSender = computed(() => (props.emailData || {}).sender || '')

const handleClick = () => {
  emit('click', props.emailData)
  hide()
}

const hide = () => {
  localShow.value = false
  emit('close')
}

onMounted(() => {
  if (props.show && props.duration > 0) {
    timer = setTimeout(() => {
      hide()
    }, props.duration)
  }
})

onUnmounted(() => {
  if (timer) {
    clearTimeout(timer)
  }
})
</script>

<template>
  <Teleport to="body">
    <Transition name="toast">
      <div v-if="show" class="email-toast" @click="handleClick">
        <div class="email-toast__icon">
          <MIcon name="mail" />
        </div>
        <div class="email-toast__content">
          <div class="email-toast__title">{{ t('emails.newEmail') }}</div>
          <div class="email-toast__sender">{{ emailSender }}</div>
          <div class="email-toast__subject">{{ truncatedSubject }}</div>
        </div>
        <button class="email-toast__close" @click.stop="hide">
          <MIcon name="x" />
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.email-toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 2000;
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  background: var(--parchment-100, #faf8f5);
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  max-width: 300px;
  transition: all 0.2s ease;
  border: 1px solid var(--parchment-300, #e5e0d8);
}

.email-toast:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.2);
}

.email-toast__icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-100, #f5efe9);
  border-radius: 8px;
  color: var(--accent-500, #6b4c3b);
  font-size: 18px;
}

.email-toast__content {
  flex: 1;
  min-width: 0;
}

.email-toast__title {
  font-size: 12px;
  font-weight: 500;
  color: var(--accent-500, #6b4c3b);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.email-toast__sender {
  font-size: 13px;
  font-weight: 600;
  color: var(--neutral-800, #2d2d2d);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.email-toast__subject {
  font-size: 12px;
  color: var(--neutral-500, #6b6b6b);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.email-toast__close {
  flex-shrink: 0;
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: var(--neutral-400, #9b9b9b);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
  font-size: 14px;
}

.email-toast__close:hover {
  background: var(--parchment-200, #e8e4de);
  color: var(--neutral-600, #5d5d5d);
}

.toast-enter-active {
  animation: toast-in 0.3s ease;
}

.toast-leave-active {
  animation: toast-out 0.3s ease;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes toast-out {
  from {
    opacity: 1;
    transform: translateX(0);
  }
  to {
    opacity: 0;
    transform: translateX(100%);
  }
}
</style>