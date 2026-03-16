import { API } from './client'

/**
 * Agent 相关 API
 */
export const agentAPI = {
  /**
   * 获取所有 Agent
   */
  async getAgents() {
    return API.get('/api/agents')
  },

  /**
   * 获取单个 Agent
   * @param {string} agentName - Agent 名称
   */
  async getAgent(agentName) {
    return API.get(`/api/agents/${agentName}`)
  },

  /**
   * 创建 Agent
   * @param {object} data - Agent 数据
   */
  async createAgent(data) {
    return API.post('/api/agents', data)
  },

  /**
   * 更新 Agent
   * @param {string} agentName - Agent 名称
   * @param {object} data - Agent 数据
   */
  async updateAgent(agentName, data) {
    return API.put(`/api/agents/${agentName}`, data)
  },

  /**
   * 删除 Agent
   * @param {string} agentName - Agent 名称
   */
  async deleteAgent(agentName) {
    return API.delete(`/api/agents/${agentName}`)
  },

  /**
   * 提交 ask_user 回答
   * @param {string} agentName - Agent 名称
   * @param {string} question - 问题
   * @param {string} answer - 回答
   */
  async submitUserInput(agentName, question, answer) {
    return API.request(`/api/agents/${agentName}/submit_user_input`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ question, answer })
    })
  },
}
