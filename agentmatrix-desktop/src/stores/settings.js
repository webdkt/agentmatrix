import { defineStore } from 'pinia'
import { configAPI } from '@/api/config'

export const useSettingsStore = defineStore('settings', {
  state: () => ({
    configStatus: null,
    agents: [],
    isLoading: false,
    error: null,

    emailProxyConfig: null,
    emailProxyLoading: false,
    emailProxyError: null,

    proxyConfig: null,
    proxyLoading: false,
    proxyError: null,
  }),

  getters: {
    isLLMConfigured: (state) => {
      return !!(state.configStatus?.llm_configured)
    },

    needsColdStart: (state) => {
      return !!(state.configStatus?.needs_cold_start)
    },

    isEmailProxyEnabled: (state) => {
      return !!(state.emailProxyConfig?.enabled)
    },

    isEmailProxyConfigured: (state) => {
      return !!(state.emailProxyConfig?.email)
    },

    isProxyEnabled: (state) => {
      return !!(state.proxyConfig?.enabled)
    },
  },

  actions: {
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