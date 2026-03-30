<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMatrixStore } from '@/stores/matrix'
import { useAgentStore } from '@/stores/agent'
import OverallDashboard from './OverallDashboard.vue'
import AgentDashboard from './AgentDashboard.vue'
import NewEmailModal from '@/components/dialog/NewEmailModal.vue'

const matrixStore = useMatrixStore()
const agentStore = useAgentStore()
const { agents, selectedAgent } = storeToRefs(matrixStore)
const { agents: agentStates } = storeToRefs(agentStore)

// View state: 'overall' or 'agent'
const currentView = ref('overall')
const selectedAgentName = ref(null)

// New email modal state
const showNewEmailModal = ref(false)
const newEmailAgent = ref(null)

// Merge API list data + WebSocket real-time status
const agentsWithStatus = computed(() => {
  return agents.value.map(agent => ({
    ...agent,
    status: agentStates.value[agent.name]?.status || 'IDLE'
  }))
})

// Handle agent selection from Overall Dashboard
const handleAgentSelect = (agentName) => {
  selectedAgentName.value = agentName
  currentView.value = 'agent'
  matrixStore.selectAgent(agentName)
}

// Back to Overall Dashboard
const handleBackToOverall = () => {
  currentView.value = 'overall'
  selectedAgentName.value = null
}

// Open new email dialog for specific agent
const handleNewMessage = (agent) => {
  newEmailAgent.value = agent
  showNewEmailModal.value = true
}

// Handle email sent
const handleEmailSent = () => {
  showNewEmailModal.value = false
  newEmailAgent.value = null
}

// Close email modal
const handleCloseEmailModal = () => {
  showNewEmailModal.value = false
  newEmailAgent.value = null
}

onMounted(() => {
  matrixStore.loadAgents()
})
</script>

<template>
  <div class="agents-view">
    <!-- Overall Dashboard -->
    <OverallDashboard
      v-if="currentView === 'overall'"
      :agents="agentsWithStatus"
      @select="handleAgentSelect"
      @new-message="handleNewMessage"
    />
    
    <!-- Agent Dashboard -->
    <AgentDashboard
      v-else
      :agent-name="selectedAgentName"
      @back="handleBackToOverall"
    />
    
    <!-- New Email Modal -->
    <NewEmailModal
      :show="showNewEmailModal"
      :preselected-agent="newEmailAgent"
      @close="handleCloseEmailModal"
      @sent="handleEmailSent"
    />
  </div>
</template>

<style scoped>
.agents-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--parchment-50);
}
</style>