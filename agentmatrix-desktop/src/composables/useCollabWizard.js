import { ref, computed } from 'vue'

const wizardStep = ref('idle') // 'idle' | 'pick-agent' | 'new-task' | 'sending'
const selectedAgent = ref(null)
const sendTargetAgentName = ref(null)

export function useCollabWizard() {
  const isActive = computed(() => wizardStep.value !== 'idle')

  const enterWizard = () => {
    selectedAgent.value = null
    sendTargetAgentName.value = null
    wizardStep.value = 'pick-agent'
  }

  const selectAgent = (agent) => {
    selectedAgent.value = agent
    wizardStep.value = 'new-task'
  }

  const goBack = () => {
    wizardStep.value = 'pick-agent'
  }

  const startSending = (agentName) => {
    sendTargetAgentName.value = agentName
    wizardStep.value = 'sending'
  }

  const finishWizard = () => {
    wizardStep.value = 'idle'
    selectedAgent.value = null
    sendTargetAgentName.value = null
  }

  const cancelWizard = finishWizard

  return {
    wizardStep,
    selectedAgent,
    sendTargetAgentName,
    isActive,
    enterWizard,
    selectAgent,
    goBack,
    startSending,
    finishWizard,
    cancelWizard,
  }
}
