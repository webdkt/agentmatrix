import { API } from './client'

/**
 * Matrix View 相关 API
 */
export const matrixAPI = {
  /**
   * 获取所有 Agent 列表（不包括 User）
   */
  async getAgents() {
    return API.get('/api/agents')
  },

  /**
   * 获取 Agent 的 Profile 配置
   * @param {string} agentName - Agent 名称
   */
  async getProfile(agentName) {
    return API.get(`/api/agents/${agentName}/profile`)
  },

  /**
   * 获取 Agent 的日志内容
   * @param {string} agentName - Agent 名称
   * @param {number} lines - 返回的行数（默认 200）
   */
  async getLog(agentName, lines = 200) {
    return API.get(`/api/agents/${agentName}/log?lines=${lines}`)
  },

  /**
   * 获取 Agent 的 Session 历史
   * @param {string} agentName - Agent 名称
   */
  async getSessions(agentName) {
    return API.get(`/api/agents/${agentName}/sessions`)
  },

  /**
   * 获取 Agent 的完整 System Prompt
   * @param {string} agentName - Agent 名称
   */
  async getAgentPrompt(agentName) {
    return API.get(`/api/agents/${agentName}/prompt`)
  },

  /**
   * 获取 Agent 的状态
   * @param {string} agentName - Agent 名称
   */
  async getStatus(agentName) {
    return API.get(`/api/agents/${agentName}/status`)
  }
}
