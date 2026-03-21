<script setup>
import { computed } from 'vue'

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  title: {
    type: String,
    default: 'Confirm Action'
  },
  message: {
    type: String,
    required: true
  },
  confirmText: {
    type: String,
    default: 'Confirm'
  },
  cancelText: {
    type: String,
    default: 'Cancel'
  },
  type: {
    type: String,
    default: 'danger',
    validator: (value) => ['danger', 'warning', 'info'].includes(value)
  },
  isDestructive: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['confirm', 'cancel'])

const handleConfirm = () => {
  emit('confirm')
}

const handleCancel = () => {
  emit('cancel')
}

const handleOverlayClick = () => {
  emit('cancel')
}

const buttonClass = computed(() => {
  return props.type === 'danger' ? 'btn-danger' : 'btn-warning'
})

const iconClass = computed(() => {
  const icons = {
    danger: 'ti-alert-circle',
    warning: 'ti-alert-triangle',
    info: 'ti-info-circle'
  }
  return icons[props.type] || icons.info
})

const iconColor = computed(() => {
  const colors = {
    danger: 'var(--error-500)',
    warning: 'var(--warning-500)',
    info: 'var(--info-500)'
  }
  return colors[props.type] || colors.info
})
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div
        v-if="show"
        class="confirm-dialog-overlay"
        @click="handleOverlayClick"
      >
        <Transition name="scale">
          <div
            v-if="show"
            class="confirm-dialog"
            @click.stop
          >
            <!-- Icon -->
            <div class="confirm-icon" :style="{ color: iconColor }">
              <i :class="['ti', iconClass]"></i>
            </div>

            <!-- Content -->
            <h3 class="confirm-title">{{ title }}</h3>
            <p class="confirm-message">{{ message }}</p>

            <!-- Actions -->
            <div class="confirm-actions">
              <button
                @click="handleCancel"
                class="btn-cancel"
                type="button"
              >
                {{ cancelText }}
              </button>
              <button
                @click="handleConfirm"
                :class="['btn-confirm', buttonClass]"
                type="button"
              >
                {{ confirmText }}
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(26, 26, 26, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  padding: var(--spacing-md);
}

.confirm-dialog {
  background: white;
  border-radius: var(--radius-sm);
  padding: var(--spacing-xl);
  box-shadow: var(--shadow-sm);
  max-width: 400px;
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--spacing-md);
}

.confirm-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  flex-shrink: 0;
}

.confirm-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0;
}

.confirm-message {
  font-size: var(--font-sm);
  color: var(--neutral-600);
  margin: 0;
  line-height: var(--leading-relaxed);
}

.confirm-actions {
  display: flex;
  gap: var(--spacing-3);
  width: 100%;
  margin-top: var(--spacing-2);
}

.btn-cancel,
.btn-confirm {
  flex: 1;
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-sm);
  border: none;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-cancel {
  background: var(--neutral-100);
  color: var(--neutral-700);
}

.btn-cancel:hover {
  background: var(--neutral-200);
}

.btn-confirm {
  background: var(--accent);
  color: white;
}

.btn-confirm:hover {
  opacity: 0.9;
}

.btn-danger {
  background: var(--error-600);
}

.btn-danger:hover {
  background: var(--error-700);
}

.btn-warning {
  background: var(--warning-600);
}

.btn-warning:hover {
  background: var(--warning-700);
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-base) var(--ease-out);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.scale-enter-active,
.scale-leave-active {
  transition: all var(--duration-base) var(--ease-out);
}

.scale-enter-from,
.scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
