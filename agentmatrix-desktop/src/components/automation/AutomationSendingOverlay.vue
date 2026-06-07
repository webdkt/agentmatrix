<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'

const { t, tm } = useI18n()

const props = defineProps({
  systemName: { type: String, default: '' },
  processName: { type: String, default: '' },
})

const messages = computed(() => tm('automation.sending.messages'))

const currentIndex = ref(0)
let timer = null

onMounted(() => {
  timer = setInterval(() => {
    const list = messages.value
    if (list && list.length) {
      currentIndex.value = (currentIndex.value + 1) % list.length
    }
  }, 2000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="sending-overlay">
    <div class="sending-overlay__card">
      <div class="sending-overlay__spinner">
        <MIcon name="loader" class="spin" />
      </div>
      <h3 class="sending-overlay__title">{{ t('automation.sending.title') }}</h3>
      <p class="sending-overlay__subtitle" v-if="systemName && processName">
        {{ systemName }} / {{ processName }}
      </p>
      <p class="sending-overlay__message" :key="currentIndex">{{ messages[currentIndex] }}</p>
    </div>
  </div>
</template>

<style scoped>
.sending-overlay {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.sending-overlay__card {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 320px;
}

.sending-overlay__spinner {
  font-size: 32px;
  color: var(--accent);
  margin-bottom: 16px;
}

.sending-overlay__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 4px 0;
}

.sending-overlay__subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0 0 16px 0;
}

.sending-overlay__message {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  animation: fadeIn 0.3s ease;
}

.spin {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
