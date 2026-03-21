<script setup>
import { computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  message: {
    type: String,
    required: true
  },
  type: {
    type: String,
    default: 'info',
    validator: (value) => ['success', 'error', 'warning', 'info'].includes(value)
  },
  duration: {
    type: Number,
    default: 3000
  }
})

const emit = defineEmits(['close'])

let timeoutId = null

onMounted(() => {
  if (props.duration > 0) {
    timeoutId = setTimeout(() => {
      emit('close')
    }, props.duration)
  }
})

onUnmounted(() => {
  if (timeoutId) {
    clearTimeout(timeoutId)
  }
})

const iconClass = computed(() => {
  const icons = {
    success: 'ti-check-circle',
    error: 'ti-x-circle',
    warning: 'ti-alert-triangle',
    info: 'ti-info-circle'
  }
  return icons[props.type] || icons.info
})

const bgColor = computed(() => {
  const colors = {
    success: 'var(--success-50)',
    error: 'var(--error-50)',
    warning: 'var(--warning-50)',
    info: 'var(--info-50)'
  }
  return colors[props.type] || colors.info
})

const borderColor = computed(() => {
  const colors = {
    success: 'var(--success-200)',
    error: 'var(--error-200)',
    warning: 'var(--warning-200)',
    info: 'var(--info-200)'
  }
  return colors[props.type] || colors.info
})

const iconColor = computed(() => {
  const colors = {
    success: 'var(--success-600)',
    error: 'var(--error-600)',
    warning: 'var(--warning-600)',
    info: 'var(--info-600)'
  }
  return colors[props.type] || colors.info
})

const textColor = computed(() => {
  const colors = {
    success: 'var(--success-700)',
    error: 'var(--error-700)',
    warning: 'var(--warning-700)',
    info: 'var(--info-700)'
  }
  return colors[props.type] || colors.info
})
</script>

<template>
  <Transition name="slide">
    <div
      v-if="true"
      class="toast"
      :style="{
        background: bgColor,
        borderColor: borderColor
      }"
    >
      <i
        :class="['ti', iconClass, 'toast-icon']"
        :style="{ color: iconColor }"
      ></i>
      <span class="toast-message" :style="{ color: textColor }">
        {{ message }}
      </span>
      <button
        @click="emit('close')"
        class="toast-close"
        :style="{ color: textColor }"
      >
        <i class="ti ti-x"></i>
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.toast {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-sm);
  border-left: 4px solid;
  box-shadow: var(--shadow-sm);
  min-width: 300px;
  max-width: 500px;
}

.toast-icon {
  font-size: var(--icon-lg);
  flex-shrink: 0;
}

.toast-message {
  flex: 1;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  line-height: var(--leading-normal);
}

.toast-close {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-sm);
  flex-shrink: 0;
  transition: all var(--duration-base) var(--ease-out);
}

.toast-close:hover {
  opacity: 0.7;
}

/* Slide transition */
.slide-enter-active,
.slide-leave-active {
  transition: all var(--duration-base) var(--ease-out);
}

.slide-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.slide-leave-to {
  opacity: 0;
  transform: translateX(100%);
}
</style>
