import { defineStore } from 'pinia'
import { invoke } from '@tauri-apps/api/core'
import { confirm } from '@tauri-apps/plugin-dialog'
import llmPresets from '@/assets/llm-presets.json'

/**
 * 冷启动向导 Store
 * 管理首次启动的配置向导状态和数据
 */
export const useConfigStore = defineStore('config', {
  state: () => ({
    // 是否首次运行
    isFirstRun: false,
    isFirstRunChecked: false,

    // 向导步骤
    currentStep: 1,
    totalSteps: 4,

    // 向导数据
    wizardData: {
      user_name: '',
      matrix_world_path: '',
      default_llm: {
        provider: 'anthropic',
        url: '',
        api_key: '',
        model_name: '',
      },
      default_slm: {
        provider: 'anthropic',
        url: '',
        api_key: '',
        model_name: '',
      },
      email_proxy: {
        enabled: false,
        matrix_mailbox: '',
        user_mailbox: '',
        imap: { host: 'imap.gmail.com', port: 993, user: '', password: '' },
        smtp: { host: 'smtp.gmail.com', port: 587, user: '', password: '' },
      },
    },

    // LLM 预设
    llmPresets: {},

    // 提交状态
    isSubmitting: false,
    submitError: null,
    submitResult: null,

    // 加载状态
    isLoading: false,
    loadError: null,
  }),

  getters: {
    canGoBack: (state) => state.currentStep > 1,
    canGoNext: (state) => state.currentStep < state.totalSteps,
    isLastStep: (state) => state.currentStep === state.totalSteps,

    isStep1Valid: (state) => state.wizardData.user_name.trim().length > 0,
    isStep2Valid: (state) => state.wizardData.matrix_world_path.trim().length > 0,
    isStep3Valid: (state) => {
      const llm = state.wizardData.default_llm
      const slm = state.wizardData.default_slm
      return llm.url && llm.api_key && llm.model_name && slm.url && slm.api_key && slm.model_name
    },

    isCurrentStepValid: (state) => {
      switch (state.currentStep) {
        case 1: return state.wizardData.user_name.trim().length > 0
        case 2: return state.wizardData.matrix_world_path.trim().length > 0
        case 3: {
          const llm = state.wizardData.default_llm
          const slm = state.wizardData.default_slm
          return llm.url && llm.api_key && llm.model_name && slm.url && slm.api_key && slm.model_name
        }
        case 4: return true
        default: return false
      }
    },
  },

  actions: {
    /**
     * 检查是否首次运行（通过 Tauri command）
     */
    async checkFirstRun() {
      try {
        this.isFirstRun = await invoke('is_first_run')
        this.isFirstRunChecked = true
        return this.isFirstRun
      } catch (error) {
        console.error('Failed to check first run:', error)
        this.isFirstRun = true
        this.isFirstRunChecked = true
        return true
      }
    },

    /**
     * 加载 LLM 预设列表和默认路径
     */
    async loadPresets() {
      // Presets are static JSON, no API needed
      this.llmPresets = llmPresets

      // Auto-fill URL and model if provider is already set
      if (this.wizardData.default_llm.provider && !this.wizardData.default_llm.url) {
        this.selectLLMPreset('default_llm', this.wizardData.default_llm.provider)
      }
      if (this.wizardData.default_slm.provider && !this.wizardData.default_slm.url) {
        this.selectLLMPreset('default_slm', this.wizardData.default_slm.provider)
      }

      // Load Tauri config for default path
      try {
        const config = await invoke('get_config')
        if (!this.wizardData.matrix_world_path && config.matrix_world_path) {
          this.wizardData.matrix_world_path = config.matrix_world_path
        }
      } catch (e) {
        console.log('Failed to load Tauri config:', e)
      }
    },

    /**
     * 通过系统原生对话框选择目录
     */
    async selectDirectory() {
      try {
        const path = await invoke('select_directory')
        if (path) {
          this.wizardData.matrix_world_path = path
        }
        return path
      } catch (error) {
        console.error('Failed to select directory:', error)
        return null
      }
    },

    /**
     * 选择 LLM provider 预设，自动填充 URL 和 model
     */
    selectLLMPreset(field, provider) {
      const preset = this.llmPresets[provider]
      if (!preset) return

      this.wizardData[field].provider = provider
      this.wizardData[field].url = preset.url
      if (preset.models && preset.models.length > 0) {
        this.wizardData[field].model_name = preset.models[0]
      }
      // API key 不自动填充，需要用户输入
    },

    nextStep() {
      if (this.currentStep < this.totalSteps && this.isCurrentStepValid) {
        this.currentStep++
      }
    },

    prevStep() {
      if (this.currentStep > 1) {
        this.currentStep--
      }
    },

    goToStep(step) {
      if (step >= 1 && step <= this.totalSteps) {
        this.currentStep = step
      }
    },

    /**
     * 提交向导配置
     */
    async submitWizard() {
      this.isSubmitting = true
      this.submitError = null
      this.submitResult = null

      const path = this.wizardData.matrix_world_path
      const name = this.wizardData.user_name

      try {
        console.log('🚀 Starting wizard submission...')

        // 0. 检查容器运行时（冷启动时 podman 可能还没装）
        const runtimeInfo = await invoke('check_container_runtime')
        if (runtimeInfo.runtime === 'none') {
          const userConfirmed = await confirm(
            'Matrix requires Podman to run containers.\n\n' +
            'Podman is not installed on your system.\n\n' +
            'Would you like to install Podman now?',
            { title: 'Install Podman', kind: 'warning' }
          )
          if (userConfirmed) {
            await invoke('install_podman')
          }
          this.submitError = 'PODMAN_INSTALL_REQUIRED'
          throw new Error('PODMAN_INSTALL_REQUIRED')
        }

        // 1. 创建目录和模板
        await invoke('init_matrix_world', { matrixWorldPath: path, userName: name })

        // 2. 保存 .env
        await invoke('save_env_file', {
          matrixWorldPath: path,
          envVars: {
            LLM_API_KEY: this.wizardData.default_llm.api_key,
            SLM_API_KEY: this.wizardData.default_slm.api_key,
          },
        })

        // 3. 保存 LLM 配置
        await invoke('save_llm_config', {
          matrixWorldPath: path,
          llmConfig: {
            default_llm: {
              url: this.wizardData.default_llm.url,
              API_KEY: 'LLM_API_KEY',
              model_name: this.wizardData.default_llm.model_name,
            },
            default_slm: {
              url: this.wizardData.default_slm.url,
              API_KEY: 'SLM_API_KEY',
              model_name: this.wizardData.default_slm.model_name,
            },
          },
        })

        // 4. 保存 Email Proxy 配置（如果有）
        if (this.wizardData.email_proxy.enabled) {
          await invoke('save_email_proxy_config_cmd', {
            matrixWorldPath: path,
            emailProxy: this.wizardData.email_proxy,
          })
        }

        // 5. 标记已配置
        await invoke('mark_configured', { matrixWorldPath: path })
        this.isFirstRun = false

        console.log('🎊 Wizard completed successfully!')
        return { success: true }
      } catch (error) {
        this.submitError = error.message || String(error)
        throw error
      } finally {
        this.isSubmitting = false
      }
    },

    /**
     * 重置向导状态
     */
    reset() {
      this.currentStep = 1
      this.submitError = null
      this.submitResult = null
      this.isSubmitting = false
    },
  },
})
