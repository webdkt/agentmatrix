import { defineStore } from 'pinia'
import { configAPI } from '@/api/config'

/**
 * 配置管理 Store
 */
export const useSettingsStore = defineStore('settings', {
  state: () => ({
    llmConfig: null,
    llmConfigs: [], // 存储所有 LLM 配置
    configStatus: null,
    agents: [],
    isLoading: false,
    error: null,

    // Email Proxy 配置
    emailProxyConfig: null,
    emailProxyLoading: false,
    emailProxyError: null,

    // HTTP Proxy 配置
    proxyConfig: null,
    proxyLoading: false,
    proxyError: null,
  }),

  getters: {
    /**
     * 是否已配置 LLM
     */
    isLLMConfigured: (state) => {
      return !!(state.configStatus?.llm_configured)
    },

    /**
     * 是否需要冷启动
     */
    needsColdStart: (state) => {
      return !!(state.configStatus?.needs_cold_start)
    },

    /**
     * Email Proxy 是否已启用
     */
    isEmailProxyEnabled: (state) => {
      return !!(state.emailProxyConfig?.enabled)
    },

    /**
     * Email Proxy 是否已配置
     */
    isEmailProxyConfigured: (state) => {
      return !!(state.emailProxyConfig?.email)
    },

    isProxyEnabled: (state) => {
      return !!(state.proxyConfig?.enabled)
    },
  },

  actions: {
    /**
     * 加载配置状态
     */
    async loadConfigStatus() {
      this.isLoading = true
      this.error = null
      try {
        const status = await configAPI.getConfigStatus()
        this.configStatus = status
        return status
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 加载所有 LLM 配置
     */
    async loadLLMConfig() {
      this.isLoading = true
      this.error = null
      try {
        const response = await configAPI.getLLMConfigs()
        // API 返回格式: { configs: [...] }
        this.llmConfigs = response.configs || []

        // 保持向后兼容，将 configs 包装成旧格式
        this.llmConfig = {
          configs: response.configs || []
        }

        return this.llmConfigs
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 保存 LLM 配置
     * @param {string} configName - 配置名称
     * @param {object} config - LLM 配置
     */
    async saveLLMConfig(configName, config) {
      this.isLoading = true
      this.error = null
      try {
        await configAPI.updateLLMConfig(configName, config)
        // 保存后重新加载配置
        await this.loadLLMConfig()
        await this.loadConfigStatus()
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 创建 LLM 配置
     * @param {object} config - LLM 配置
     */
    async createLLMConfig(config) {
      this.isLoading = true
      this.error = null
      try {
        await configAPI.createLLMConfig(config)
        await this.loadLLMConfig()
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 删除 LLM 配置
     * @param {string} configName - 配置名称
     */
    async deleteLLMConfig(configName) {
      this.isLoading = true
      this.error = null
      try {
        await configAPI.deleteLLMConfig(configName)
        await this.loadLLMConfig()
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 重置 LLM 配置为默认值
     * @param {string} configName - 配置名称
     */
    async resetLLMConfig(configName) {
      this.isLoading = true
      this.error = null
      try {
        await configAPI.resetLLMConfig(configName)
        await this.loadLLMConfig()
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 加载 Email Proxy 配置
     */
    async loadEmailProxyConfig() {
      this.emailProxyLoading = true
      this.emailProxyError = null
      try {
        const config = await configAPI.getEmailProxyConfig()
        this.emailProxyConfig = config
        return config
      } catch (error) {
        this.emailProxyError = error.message
        throw error
      } finally {
        this.emailProxyLoading = false
      }
    },

    /**
     * 更新 Email Proxy 配置
     * @param {object} config - Email Proxy 配置
     */
    async updateEmailProxyConfig(config) {
      this.emailProxyLoading = true
      this.emailProxyError = null
      try {
        await configAPI.updateEmailProxyConfig(config)
        await this.loadEmailProxyConfig()
      } catch (error) {
        this.emailProxyError = error.message
        throw error
      } finally {
        this.emailProxyLoading = false
      }
    },

    /**
     * 启用 Email Proxy
     */
    async enableEmailProxy() {
      this.emailProxyLoading = true
      this.emailProxyError = null
      try {
        await configAPI.enableEmailProxy()
        if (this.emailProxyConfig) {
          this.emailProxyConfig.enabled = true
        }
      } catch (error) {
        this.emailProxyError = error.message
        throw error
      } finally {
        this.emailProxyLoading = false
      }
    },

    /**
     * 禁用 Email Proxy
     */
    async disableEmailProxy() {
      this.emailProxyLoading = true
      this.emailProxyError = null
      try {
        await configAPI.disableEmailProxy()
        if (this.emailProxyConfig) {
          this.emailProxyConfig.enabled = false
        }
      } catch (error) {
        this.emailProxyError = error.message
        throw error
      } finally {
        this.emailProxyLoading = false
      }
    },

    /**
     * 测试 Email Proxy 连接
     */
    async testEmailProxyConnection() {
      this.emailProxyLoading = true
      this.emailProxyError = null
      try {
        const result = await configAPI.testEmailProxyConnection()
        return result
      } catch (error) {
        this.emailProxyError = error.message
        throw error
      } finally {
        this.emailProxyLoading = false
      }
    },

    async loadProxyConfig() {
      this.proxyLoading = true
      this.proxyError = null
      try {
        const config = await configAPI.getProxyConfig()
        this.proxyConfig = config
        return config
      } catch (error) {
        this.proxyError = error.message
        throw error
      } finally {
        this.proxyLoading = false
      }
    },

    async updateProxyConfig(config) {
      this.proxyLoading = true
      this.proxyError = null
      try {
        await configAPI.updateProxyConfig(config)
        this.proxyConfig = { ...config }
      } catch (error) {
        this.proxyError = error.message
        throw error
      } finally {
        this.proxyLoading = false
      }
    },

    async enableProxy() {
      this.proxyLoading = true
      this.proxyError = null
      try {
        await configAPI.enableProxy()
        if (this.proxyConfig) {
          this.proxyConfig.enabled = true
        }
      } catch (error) {
        this.proxyError = error.message
        throw error
      } finally {
        this.proxyLoading = false
      }
    },

    async disableProxy() {
      this.proxyLoading = true
      this.proxyError = null
      try {
        await configAPI.disableProxy()
        if (this.proxyConfig) {
          this.proxyConfig.enabled = false
        }
      } catch (error) {
        this.proxyError = error.message
        throw error
      } finally {
        this.proxyLoading = false
      }
    },

    async testProxyConnection() {
      this.proxyLoading = true
      this.proxyError = null
      try {
        const result = await configAPI.testProxyConnection()
        return result
      } catch (error) {
        this.proxyError = error.message
        throw error
      } finally {
        this.proxyLoading = false
      }
    },
  },
})
