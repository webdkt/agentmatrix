import { API } from './client'

/**
 * 配置相关 API
 */
export const configAPI = {
  /**
   * 获取配置状态（含冷启动信息）
   */
  async getConfigStatus() {
    return API.get('/api/config/status')
  },

  /**
   * 获取完整配置（含 user_agent_name）
   */
  async getFullConfig() {
    return API.get('/api/config')
  },

  /**
   * 获取 LLM 预设 provider 列表
   */
  async getLLMPresets() {
    return API.get('/api/config/llm-presets')
  },

  /**
   * 初始化 runtime（文件已由 Tauri 创建，后端只读取）
   * @param {object} data - { matrix_world_path }
   */
  async initRuntime(data) {
    return API.post('/api/config/init', data)
  },

  /**
   * 获取所有 LLM 配置
   */
  async getLLMConfigs() {
    return API.get('/api/llm-configs')
  },

  /**
   * 获取单个 LLM 配置
   * @param {string} configName - 配置名称
   */
  async getLLMConfig(configName) {
    return API.get(`/api/llm-configs/${configName}`)
  },

  /**
   * 创建 LLM 配置
   * @param {object} configData - 配置数据
   */
  async createLLMConfig(configData) {
    return API.post('/api/llm-configs', configData)
  },

  /**
   * 更新 LLM 配置
   * @param {string} configName - 配置名称
   * @param {object} configData - 配置数据
   */
  async updateLLMConfig(configName, configData) {
    return API.put(`/api/llm-configs/${configName}`, configData)
  },

  /**
   * 删除 LLM 配置
   * @param {string} configName - 配置名称
   */
  async deleteLLMConfig(configName) {
    return API.delete(`/api/llm-configs/${configName}`)
  },

  /**
   * 重置 LLM 配置为默认值
   * @param {string} configName - 配置名称
   */
  async resetLLMConfig(configName) {
    return API.post(`/api/llm-configs/${configName}/reset`, {})
  },

  /**
   * 获取 Email Proxy 配置
   */
  async getEmailProxyConfig() {
    return API.get('/api/email-proxy/config')
  },

  /**
   * 更新 Email Proxy 配置
   * @param {object} config - Email Proxy 配置
   */
  async updateEmailProxyConfig(config) {
    return API.put('/api/email-proxy/config', config)
  },

  /**
   * 启用 Email Proxy
   */
  async enableEmailProxy() {
    return API.post('/api/email-proxy/enable')
  },

  /**
   * 禁用 Email Proxy
   */
  async disableEmailProxy() {
    return API.post('/api/email-proxy/disable')
  },

  /**
   * 测试 Email Proxy 连接
   */
  async testEmailProxyConnection() {
    return API.post('/api/email-proxy/test')
  },
}
