<script setup>
import { computed } from 'vue'
import { useUIStore } from '@/stores/ui'
import Toast from './Toast.vue'

const uiStore = useUIStore()

const notifications = computed(() => uiStore.notifications)

const handleClose = (notificationId) => {
  uiStore.removeNotification(notificationId)
}
</script>

<template>
  <Teleport to="body">
    <div class="toast-container">
      <Toast
        v-for="notification in notifications"
        :key="notification.id"
        :message="notification.message"
        :type="notification.type"
        :duration="0"
        @close="handleClose(notification.id)"
      />
    </div>
  </Teleport>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: var(--spacing-6);
  right: var(--spacing-6);
  z-index: var(--z-popover);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  pointer-events: none;
}

.toast-container > * {
  pointer-events: auto;
}
</style>
