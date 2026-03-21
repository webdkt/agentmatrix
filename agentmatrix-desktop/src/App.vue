<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { useBackendStore } from '@/stores/backend'
import { useWebSocket } from '@/composables/useWebSocket'
import ViewSelector from '@/components/view-selector/ViewSelector.vue'
import ViewContainer from '@/components/view-container/ViewContainer.vue'

const currentView = ref('email')
const backendStore = useBackendStore()
const { isConnected } = useWebSocket()

// Computed
const backendStatus = computed(() => backendStore.status)

// Handle view changes
const handleViewChange = (viewId) => {
  currentView.value = viewId
}

// Lifecycle
onUnmounted(() => {
  backendStore.stopHealthMonitoring()
})
</script>

<template>
  <div class="app">
    <!-- View Selector (Left Sidebar) -->
    <ViewSelector :current-view="currentView" @view-change="handleViewChange">
      <template #status>
        <!-- Backend Status Indicator -->
        <div
          :class="['status-indicator', `status-indicator--${backendStatus}`]"
          :title="backendStatus.charAt(0).toUpperCase() + backendStatus.slice(1)"
        >
          <span
            :class="['status-indicator__dot', `status-indicator__dot--${backendStatus}`]"
          ></span>
        </div>

        <!-- WebSocket Status Indicator -->
        <div
          :class="['status-indicator', `status-indicator--${isConnected ? 'connected' : 'disconnected'}`]"
          :title="isConnected ? 'Connected' : 'Connecting...'"
        >
          <span
            :class="['status-indicator__dot', `status-indicator__dot--${isConnected ? 'connected' : 'disconnected'}`]"
          ></span>
        </div>
      </template>
    </ViewSelector>

    <!-- View Container (Main Content) -->
    <ViewContainer
      :current-view="currentView"
      @view-change="handleViewChange"
    />
  </div>
</template>

<style scoped>
.app {
  width: 100vw;
  height: 100vh;
  display: flex;
  overflow: hidden;
}

/* Status indicators in ViewSelector */
.status-indicator {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.status-indicator:hover {
  background: var(--parchment-300);
}

.status-indicator__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  transition: all var(--duration-base) var(--ease-out);
}

.status-indicator__dot--running,
.status-indicator__dot--connected {
  background: var(--verdant);
}

.status-indicator__dot--stopped,
.status-indicator__dot--disconnected {
  background: var(--fault);
}

.status-indicator__dot--starting,
.status-indicator__dot--stopping {
  background: var(--amber);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

/* Tooltip for status indicators */
.status-indicator[title]:hover::after {
  content: attr(title);
  position: absolute;
  left: calc(100% + 12px);
  top: 50%;
  transform: translateY(-50%);
  background: var(--neutral-800);
  color: white;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  white-space: nowrap;
  z-index: var(--z-tooltip);
}
</style>
