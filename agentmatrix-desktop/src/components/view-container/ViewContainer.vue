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
import AskUserDialog from '@/components/dialog/AskUserDialog.vue'
import ColdStartWizard from '@/components/wizard/ColdStartWizard.vue'

const props = defineProps({
  currentView: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['view-change', 'wizard-complete'])

const sessionStore = useSessionStore()
const websocketStore = useWebSocketStore()
const backendStore = useBackendStore()
const configStore = useConfigStore()
const { isConnected, connect, onMessage } = useWebSocket()
const { requestPermission } = useNotifications()

const showWizard = ref(false)
const isInitializing = ref(true)

// Computed
const currentSession = computed(() => sessionStore.currentSession)
const backendStatus = computed(() => backendStore.status)

// Dialog state
const showAskUserDialog = computed(() => {
  if (!currentSession.value) return false
  return sessionStore.shouldShowAskUserDialog(currentSession.value.session_id)
})

// Watch session changes for dialog
watch(currentSession, (newSession) => {
  // Dialog will show automatically via computed property
})

// Setup WebSocket listeners and email callbacks (shared between warm start and post-wizard)
async function setupAppAfterBackend() {
  await requestPermission()

  if (backendStore.isRunning) {
    console.log('Connecting WebSocket...')
    connect()
  }

  // Listen to WebSocket messages
  onMessage((data) => {
    websocketStore.handle_message(data)
  })

  // Register new email callback
  websocketStore.onNewEmail(async (emailData) => {
    console.log('📧 Handling new email from WebSocket:', emailData)
    console.log('📊 Current session:', currentSession.value?.session_id)
    console.log('📊 Email recipient_session_id:', emailData.recipient_session_id)

    // 1. Refresh session list (handle new session)
    await sessionStore.loadSessions()

    // 2. Use recipient_session_id to match session
    if (emailData.recipient_session_id) {
      const targetSession = sessionStore.sessions.find(
        s => s.session_id === emailData.recipient_session_id
      )

      if (targetSession) {
        if (targetSession.session_id === currentSession.value?.session_id) {
          // Is current session → force refresh
          console.log('✅ Email belongs to current session, forcing refresh...')
          await sessionStore.selectSession(targetSession, true)
        } else {
          // Is different session → switch to it
          console.log('🔄 Email belongs to different session, switching...')
          // Switch to email view if not already there
          if (props.currentView !== 'email') {
            emit('view-change', 'email')
          }
          await sessionStore.selectSession(targetSession, true)
        }
      } else {
        console.log('⚠️ Session not found in list, might be a new session')
      }
    } else {
      console.log('⚠️ Email has no recipient_session_id')
    }
  })
}

// Lifecycle
onMounted(async () => {
  console.log('🚀 AgentMatrix Desktop App mounted')

  try {
    // Check if this is a cold start
    const isFirstRun = await configStore.checkFirstRun()

    if (isFirstRun) {
      console.log('❄️ Cold start detected, showing wizard')
      showWizard.value = true
      isInitializing.value = false
      return
    }

    // Warm start: normal flow
    await backendStore.initializeBackend()
    await setupAppAfterBackend()
  } catch (error) {
    console.error('Failed to initialize:', error)
  } finally {
    isInitializing.value = false
  }
})

// Handle wizard completion
async function handleWizardComplete() {
  console.log('🎉 Wizard completed, transitioning to main app')
  showWizard.value = false

  // Backend is now running and configured (submitted by wizard)
  await setupAppAfterBackend()
  emit('wizard-complete')
}

// Handle dialog submitted
const handleDialogSubmitted = () => {
  console.log('✅ Ask user dialog submitted')
}

// Handle view change from within views
const handleViewChange = (viewId) => {
  emit('view-change', viewId)
}
</script>

<template>
  <main class="view-container">
    <!-- Loading state -->
    <div v-if="isInitializing" class="view-container__loading">
      <div class="view-container__loading-spinner"></div>
    </div>

    <!-- Cold Start Wizard -->
    <ColdStartWizard
      v-else-if="showWizard"
      @complete="handleWizardComplete"
    />

    <!-- Normal App -->
    <template v-else>
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
            <i class="ti ti-layout-dashboard"></i>
          </div>
          <h2>{{ $t('views.dashboard.title') }}</h2>
          <p>Coming soon...</p>
        </div>
      </div>

      <!-- Matrix View (Placeholder) -->
      <div v-else-if="currentView === 'matrix'" class="view-container__content view-container__content--full">
        <div class="placeholder-view">
          <div class="placeholder-view__icon">
            <i class="ti ti-grid"></i>
          </div>
          <h2>{{ $t('views.matrix.title') }}</h2>
          <p>Coming soon...</p>
        </div>
      </div>

      <!-- Magic View (Placeholder) -->
      <div v-else-if="currentView === 'magic'" class="view-container__content view-container__content--full">
        <div class="placeholder-view">
          <div class="placeholder-view__icon">
            <i class="ti ti-wand"></i>
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
    </template>
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

.view-container__loading {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.view-container__loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid var(--neutral-200);
  border-top-color: var(--primary-500);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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
  border-radius: var(--radius-xl);
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
