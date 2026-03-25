<template>
  <div class="matrix-view">
    <!-- 左侧 Agent 列表 -->
    <AgentList
      :agents="agentsWithStatus"
      :selected-agent="selectedAgent"
      @select="handleAgentSelect"
    />

    <!-- 右侧 Dashboard -->
    <AgentDashboard :agent-name="selectedAgent" />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMatrixStore } from '../../stores/matrix'
import { useAgentStore } from '../../stores/agent'
import AgentList from './AgentList.vue'
import AgentDashboard from './AgentDashboard.vue'

const matrixStore = useMatrixStore()
const agentStore = useAgentStore()
const { agents, selectedAgent } = storeToRefs(matrixStore)
const { agents: agentStates } = storeToRefs(agentStore)

// 合并 API 列表数据 + WebSocket 实时状态
const agentsWithStatus = computed(() => {
  return agents.value.map(agent => ({
    ...agent,
    status: agentStates.value[agent.name]?.status || 'IDLE'
  }))
})

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
