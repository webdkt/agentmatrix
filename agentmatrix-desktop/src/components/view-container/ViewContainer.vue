<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { useBackendStore } from '@/stores/backend'
import { useConfigStore } from '@/stores/config'
import { configAPI } from '@/api/config'
import SessionList from '@/components/session/SessionList.vue'
import EmailList from '@/components/email/EmailList.vue'
import ChatHistory from '@/components/collab/ChatHistory.vue'
import CollabPanel from '@/components/collab/CollabPanel.vue'
import SettingsView from '@/components/settings/SettingsView.vue'
import AgentsView from '@/components/agents/AgentsView.vue'
import AgentStatusPanel from '@/components/agent/AgentStatusPanel.vue'
import ResizableDivider from '@/components/view-container/ResizableDivider.vue'
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

// Computed
const currentSession = computed(() => sessionStore.currentSession)

// Current agent name for collab panel
const currentAgentName = computed(() => {
  if (!currentSession.value) return null
  return currentSession.value.name || currentSession.value.participants?.[0] || null
})

// Dialog state
const showAskUserDialog = computed(() => {
  if (!currentSession.value) return false
  return sessionStore.shouldShowAskUserDialog(currentSession.value.session_id)
})

// Global dialog state
const showGlobalAskUserDialog = computed(() => {
  return sessionStore.shouldShowGlobalAskUserDialog()
})

// User agent name (fetched from backend on startup)
const userAgentName = ref('User')

// Setup app after backend is ready
async function setupAppAfterBackend() {
  try {
    // Fetch user_agent_name from backend
    try {
      const config = await configAPI.getFullConfig()
      if (config?.user_agent_name) {
        userAgentName.value = config.user_agent_name
      }
    } catch (e) {
      console.warn('Failed to fetch user_agent_name, using default:', e)
    }

    // Register email-related WebSocket listeners
    websocketStore.registerListener('email', (data) => {
      if (data.type === 'email_updated') {
        sessionStore.fetchSessions()
      }
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

// Handle global dialog submitted
const handleGlobalDialogSubmitted = () => {
  console.log('✅ Global ask user dialog submitted')
}

// Handle view change from within views
const handleViewChange = (viewId) => {
  emit('view-change', viewId)
}

// Agent status panel state
const expandedAgent = ref(null)
const agentPanelWidth = ref(450) // Default width in pixels
const collabPanelWidth = ref(450) // Default width in pixels

const handleAgentSelected = (agentName) => {
  if (expandedAgent.value === agentName) {
    expandedAgent.value = null
  } else {
    expandedAgent.value = agentName
  }
}

const handlePanelClose = () => {
  expandedAgent.value = null
}

const handlePanelWidthUpdate = (newWidth) => {
  agentPanelWidth.value = newWidth
}

// Reset expanded agent when session changes
watch(currentSession, () => {
  expandedAgent.value = null
})

// Lifecycle
onMounted(async () => {
  await setupAppAfterBackend()
})
</script>

<template>
  <main class="view-container">
    <!-- Collab View -->
    <div v-if="currentView === 'collab'" class="view-container__content">
      <KeepAlive>
        <SessionList mode="collab" />
      </KeepAlive>
      <ChatHistory
        :user_agent_name="userAgentName"
      />
      <ResizableDivider
        v-if="currentAgentName"
        :min-width="300"
        :max-width="800"
        :current-width="collabPanelWidth"
        @update:width="collabPanelWidth = $event"
      />
      <CollabPanel
        v-if="currentAgentName"
        :agent-name="currentAgentName"
        :style="{ width: `${collabPanelWidth}px` }"
      />
    </div>

    <!-- Email View -->
    <div v-else-if="currentView === 'email'" class="view-container__content">
      <KeepAlive>
        <SessionList />
      </KeepAlive>
      <EmailList
        :user_agent_name="userAgentName"
        :selected-agent="expandedAgent"
        @agent-selected="handleAgentSelected"
      />
      <ResizableDivider
        v-if="expandedAgent"
        :min-width="300"
        :max-width="600"
        :current-width="agentPanelWidth"
        @update:width="handlePanelWidthUpdate"
      />
      <Transition name="panel-slide">
        <AgentStatusPanel
          v-if="expandedAgent"
          :key="expandedAgent"
          :agent-name="expandedAgent"
          :style="{ width: `${agentPanelWidth}px` }"
          @close="handlePanelClose"
        />
      </Transition>
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

    <!-- Agents View -->
    <div v-else-if="currentView === 'agents'" class="view-container__content">
      <AgentsView />
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

    <!-- Global Ask User Dialog (for questions without user session) -->
    <AskUserDialog
      :show="showGlobalAskUserDialog"
      :isGlobal="true"
      @close="sessionStore.markGlobalDialogShown()"
      @submitted="handleGlobalDialogSubmitted"
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

/* Panel slide transition */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: all 0.25s var(--ease-out), opacity 0.2s var(--ease-out);
  overflow: hidden;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  width: 0;
  opacity: 0;
  flex-shrink: 0;
}

.panel-slide-enter-to,
.panel-slide-leave-from {
  width: 450px;
  opacity: 1;
  flex-shrink: 0;
}
</style>