<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { useWebSocket } from '@/composables/useWebSocket'
import { useBackendStore } from '@/stores/backend'
import { useNotifications } from '@/composables/useNotifications'
import { useConfigStore } from '@/stores/config'
import SessionList from '@/components/session/SessionList.vue'
import EmailList from '@/components/email/EmailList.vue'
import SettingsView from '@/components/settings/SettingsView.vue'
import MatrixView from '@/components/matrix/MatrixView.vue'
import AskUserDialog from '@/components/dialog/AskUserDialog.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  currentView: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['view-change'])

const sessionStore = useSessionStore()
const websocketStore = useWebSocketStore()
const backendStore = useBackendStore()
const configStore = useConfigStore()
const { isConnected, connect, onMessage } = useWebSocket()
const { requestPermission } = useNotifications()

// Computed
const currentSession = computed(() => sessionStore.currentSession)

// Dialog state
const showAskUserDialog = computed(() => {
  if (!currentSession.value) return false
  return sessionStore.shouldShowAskUserDialog(currentSession.value.session_id)
})

// Setup WebSocket listeners and email callbacks
async function setupAppAfterBackend() {
  try {
    await connect()

    // Register email-related WebSocket listeners
    websocketStore.registerListener('email', (data) => {
      if (data.type === 'email_updated') {
        sessionStore.fetchSessions()
      }
    })

    // Register callback for new email notifications
    websocketStore.registerCallback('on_new_email', async (emailData) => {
      const granted = await requestPermission()
      if (granted) {
        new Notification('New Email', {
          body: `From: ${emailData.from}\nSubject: ${emailData.subject}`,
        })
      }
      sessionStore.fetchSessions()
    })

    // Fetch initial data
    await sessionStore.fetchSessions()
  } catch (error) {
    console.error('Failed to setup app:', error)
  }
}

// Handle dialog submitted
const handleDialogSubmitted = () => {
  console.log('✅ Ask user dialog submitted')
}

// Handle view change from within views
const handleViewChange = (viewId) => {
  emit('view-change', viewId)
}

// Lifecycle
onMounted(async () => {
  await setupAppAfterBackend()
})
</script>

<template>
  <main class="view-container">
    <!-- Email View -->
    <div v-if="currentView === 'email'" class="view-container__content">
      <SessionList />
      <EmailList :user_agent_name="configStore.submitResult?.user_agent_name || 'User'" />
    </div>

    <!-- Settings View -->
    <div v-else-if="currentView === 'settings'" class="view-container__content view-container__content--full">
      <SettingsView @view-change="handleViewChange" />
    </div>

    <!-- Dashboard View (Placeholder) -->
    <div v-else-if="currentView === 'dashboard'" class="view-container__content view-container__content--full">
      <div class="placeholder-view">
        <div class="placeholder-view__icon">
          <MIcon name="layout-dashboard" />
        </div>
        <h2>{{ $t('views.dashboard.title') }}</h2>
        <p>Coming soon...</p>
      </div>
    </div>

    <!-- Matrix View -->
    <div v-else-if="currentView === 'matrix'" class="view-container__content">
      <MatrixView />
    </div>

    <!-- Magic View (Placeholder) -->
    <div v-else-if="currentView === 'magic'" class="view-container__content view-container__content--full">
      <div class="placeholder-view">
        <div class="placeholder-view__icon">
          <MIcon name="wand" />
        </div>
        <h2>{{ $t('views.magic.title') }}</h2>
        <p>Coming soon...</p>
      </div>
    </div>

    <!-- Ask User Dialog -->
    <AskUserDialog
      :show="showAskUserDialog"
      @close="sessionStore.closeAskUserDialog(currentSession?.session_id)"
      @submitted="handleDialogSubmitted"
    />
  </main>
</template>

<style scoped>
.view-container {
  flex: 1;
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.view-container__content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.view-container__content--full {
  padding: var(--spacing-lg);
}

.placeholder-view {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--neutral-500);
}

.placeholder-view__icon {
  width: 80px;
  height: 80px;
  background: var(--neutral-100);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: var(--neutral-300);
  margin-bottom: var(--spacing-lg);
}

.placeholder-view h2 {
  font-size: var(--font-2xl);
  font-weight: var(--font-semibold);
  color: var(--neutral-700);
  margin-bottom: var(--spacing-sm);
}

.placeholder-view p {
  font-size: var(--font-base);
  color: var(--neutral-500);
}
</style>