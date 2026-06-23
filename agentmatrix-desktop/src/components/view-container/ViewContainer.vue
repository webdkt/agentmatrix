<script setup>
import { ref, computed, watch, onMounted, provide } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useWebSocketStore } from '@/stores/websocket'
import { useBackendStore } from '@/stores/backend'
import { useConfigStore } from '@/stores/config'
import { useCollabWizard } from '@/composables/useCollabWizard'
import { configAPI } from '@/api/config'
import SessionList from '@/components/session/SessionList.vue'
import AgentSessionPanel from '@/components/collab/AgentSessionPanel.vue'
import SettingsView from '@/components/settings/SettingsView.vue'
import AgentsView from '@/components/agents/AgentsView.vue'
import AutomationView from '@/components/automation/AutomationView.vue'
import HomeView from '@/components/home/HomeView.vue'
import KnowledgeBaseView from '@/components/knowledge/KnowledgeBaseView.vue'
import DesignView from '@/components/design/DesignView.vue'
import ServicesView from '@/components/services/ServicesView.vue'

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

// Collab wizard (shared between SessionList and AgentSessionPanel)
const collabWizard = useCollabWizard()
provide('collabWizard', collabWizard)

// Computed
const currentSession = computed(() => sessionStore.currentSession)

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
        // 存储到 configStore，供其他组件使用（如 websocket store）
        configStore.config.user_agent_name = config.user_agent_name
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

// Handle view change from within views
const handleViewChange = (viewId) => {
  emit('view-change', viewId)
}

// Collab draft message — set by CollabPanel on file drop, consumed by EmailReply
const collabDraftMessage = ref('')
provide('collabDraftMessage', collabDraftMessage)

// Lifecycle
onMounted(async () => {
  await setupAppAfterBackend()
})

// Refresh session list when switching back to CollabView
watch(() => props.currentView, (newView) => {
  if (newView === 'collab') {
    sessionStore.fetchSessions()
  }
})
</script>

<template>
  <main class="view-container">
    <!-- Home View -->
    <div v-if="currentView === 'home'" class="view-container__content view-container__content--full">
      <HomeView @view-change="handleViewChange" />
    </div>

    <!-- Collab View -->
    <div v-else-if="currentView === 'collab'" class="view-container__content">
      <KeepAlive>
        <SessionList mode="collab" />
      </KeepAlive>
      <AgentSessionPanel :user-agent-name="userAgentName" />
    </div>

    <!-- Settings View -->
    <div v-else-if="currentView === 'settings'" class="view-container__content view-container__content--full">
      <SettingsView @view-change="handleViewChange" />
    </div>

    <!-- Agents View -->
    <div v-else-if="currentView === 'agents'" class="view-container__content">
      <AgentsView />
    </div>

    <!-- Automation View -->
    <div v-else-if="currentView === 'automation'" class="view-container__content view-container__content--full">
      <AutomationView />
    </div>

    <!-- Knowledge Base View -->
    <div v-else-if="currentView === 'knowledge'" class="view-container__content view-container__content--full">
      <KnowledgeBaseView />
    </div>

    <!-- Design View -->
    <div v-else-if="currentView === 'design'" class="view-container__content view-container__content--full">
      <DesignView />
    </div>

    <!-- Services View -->
    <div v-else-if="currentView === 'services'" class="view-container__content view-container__content--full">
      <ServicesView />
    </div>

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
  padding: var(--spacing-6);
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