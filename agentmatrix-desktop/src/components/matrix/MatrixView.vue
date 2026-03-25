<template>
  <div class="matrix-view">
    <!-- 左侧 Agent 列表 -->
    <AgentList
      :agents="agents"
      :selected-agent="selectedAgent"
      @select="handleAgentSelect"
    />

    <!-- 右侧 Dashboard -->
    <AgentDashboard :agent-name="selectedAgent" />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMatrixStore } from '../../stores/matrix'
import AgentList from './AgentList.vue'
import AgentDashboard from './AgentDashboard.vue'

const matrixStore = useMatrixStore()
const { agents, selectedAgent } = storeToRefs(matrixStore)

onMounted(() => {
  matrixStore.loadAgents()
})

function handleAgentSelect(agentName) {
  matrixStore.selectAgent(agentName)
}
</script>

<style scoped>
.matrix-view {
  display: flex;
  height: 100%;
  background: var(--parchment-50);
}
</style>
