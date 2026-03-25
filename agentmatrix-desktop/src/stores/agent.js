import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Agent 状态管理 Store
 * 跟踪所有 Agent 的状态信息
 */
export const useAgentStore = defineStore('agent', () => {
  // 状态
  const agents = ref({})  // { agentName: { status, status_history, current_user_session_id, ... } }

  // 计算属性
  const getAgent = (agentName) => {
    return agents.value[agentName]
  }

  const getAgentStatus = (agentName) => {
    return agents.value[agentName]?.status || 'IDLE'
  }

  // Actions
  const updateAgentStatus = (agentName, data) => {
    console.log('📊 [AgentStore] Updating agent status:', agentName, data)

    agents.value[agentName] = {
      ...agents.value[agentName],
      ...data,
      lastUpdated: new Date().toISOString()
    }

    // 确保存储 current_session_id（agent 的会话ID）
    if (data.current_session_id) {
      agents.value[agentName].current_session_id = data.current_session_id
    }
  }

  // 获取 agent 的 current_session_id
  const getAgentSessionId = (agentName) => {
    return agents.value[agentName]?.current_session_id || null
  }

  const clearAgentStatus = (agentName) => {
    console.log('📊 [AgentStore] Clearing agent status:', agentName)
    delete agents.value[agentName]
  }

  return {
    agents,
    getAgent,
    getAgentStatus,
    getAgentSessionId,
    updateAgentStatus,
    clearAgentStatus
  }
})
