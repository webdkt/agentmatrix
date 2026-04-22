<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

const steps = [
  { text: `Sending message to ${props.agentName}`, delay: 0 },
  { text: 'Preparing task environment', delay: 1200 },
  { text: 'Generating task name', delay: 3000 },
  { text: 'Waiting for agent...', delay: 5000 },
]

const currentStepIndex = ref(0)
const currentText = ref(steps[0].text)
const isTransitioning = ref(false)

let timers = []

onMounted(() => {
  for (let i = 1; i < steps.length; i++) {
    const timer = setTimeout(() => {
      isTransitioning.value = true
      setTimeout(() => {
        currentStepIndex.value = i
        currentText.value = steps[i].text
        isTransitioning.value = false
      }, 200)
    }, steps[i].delay)
    timers.push(timer)
  }
})

onUnmounted(() => {
  timers.forEach(clearTimeout)
})
</script>

<template>
  <div class="task-sending-overlay">
    <div class="task-sending-overlay__content">
      <MIcon name="loader" class="task-sending-overlay__spinner" />
      <Transition name="fade-slide" mode="out-in">
        <span :key="currentStepIndex" class="task-sending-overlay__text">
          {{ currentText }}
        </span>
      </Transition>
    </div>
  </div>
</template>

<style scoped>
.task-sending-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
  z-index: 10;
}

.task-sending-overlay__content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-md);
}

.task-sending-overlay__spinner {
  font-size: 32px;
  color: var(--accent);
  animation: overlay-spin 1.2s linear infinite;
}

.task-sending-overlay__text {
  font-size: var(--font-base);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.2s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@keyframes overlay-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
