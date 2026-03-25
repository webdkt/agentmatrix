import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { matrixAPI } from '../api/matrix'

/**
 * Matrix View 状态管理
 */
export const useMatrixStore = defineStore('matrix', () => {
  // 状态
  const agents = ref([])           // Agent 列表
  const selectedAgent = ref(null)  // 当前选中的 Agent 名称
  const profile = ref(null)        // Agent 配置
  const logContent = ref('')       // 日志内容
  const sessions = ref([])         // Session 历史
  const isLoadingAgents = ref(false)
  const isLoadingProfile = ref(false)
  const isLoadingLog = ref(false)
  const isLoadingSessions = ref(false)

  // 计算属性
  const selectedAgentData = computed(() => {
    return agents.value.find(a => a.name === selectedAgent.value)
  })

  const agentNames = computed(() => {
    return agents.value.map(a => a.name)
  })

  // Actions

  /**
   * 加载所有 Agent 列表
   */
  async function loadAgents() {
    isLoadingAgents.value = true
    try {
      const data = await matrixAPI.getAgents()
      agents.value = data.agents || []
    } catch (error) {
      console.error('Failed to load agents:', error)
      agents.value = []
    } finally {
      isLoadingAgents.value = false
    }
  }

  /**
   * 选择 Agent
   * @param {string} agentName - Agent 名称
   */
  async function selectAgent(agentName) {
    if (selectedAgent.value === agentName) return

    selectedAgent.value = agentName
    profile.value = null
    logContent.value = ''
    sessions.value = []

    // 并行加载数据
    await Promise.all([
      loadProfile(agentName),
      loadLog(agentName),
      loadSessions(agentName)
    ])
  }

  /**
   * 加载 Agent Profile
   * @param {string} agentName - Agent 名称
   */
  async function loadProfile(agentName) {
    isLoadingProfile.value = true
    try {
      const data = await matrixAPI.getProfile(agentName)
      profile.value = data
    } catch (error) {
      console.error('Failed to load profile:', error)
      profile.value = null
    } finally {
      isLoadingProfile.value = false
    }
  }

  /**
   * 加载 Agent 日志
   * @param {string} agentName - Agent 名称
   * @param {number} lines - 返回行数
   */
  async function loadLog(agentName, lines = 500) {
    isLoadingLog.value = true
    try {
      const data = await matrixAPI.getLog(agentName, lines)
      logContent.value = data.content || ''
    } catch (error) {
      console.error('Failed to load log:', error)
      logContent.value = ''
    } finally {
      isLoadingLog.value = false
    }
  }

  /**
   * 加载 Agent Sessions
   * @param {string} agentName - Agent 名称
   */
  async function loadSessions(agentName) {
    isLoadingSessions.value = true
    try {
      const data = await matrixAPI.getSessions(agentName)
      sessions.value = data.sessions || []
    } catch (error) {
      console.error('Failed to load sessions:', error)
      sessions.value = []
    } finally {
      isLoadingSessions.value = false
    }
  }

  /**
   * 刷新日志
   */
  async function refreshLog() {
    if (!selectedAgent.value) return
    await loadLog(selectedAgent.value)
  }

  return {
    // State
    agents,
    selectedAgent,
    profile,
    logContent,
    sessions,
    isLoadingAgents,
    isLoadingProfile,
    isLoadingLog,
    isLoadingSessions,

    // Computed
    selectedAgentData,
    agentNames,

    // Actions
    loadAgents,
    selectAgent,
    loadProfile,
    loadLog,
    loadSessions,
    refreshLog
  }
})
