import { defineStore } from 'pinia'
import { invoke } from '@tauri-apps/api/core'
import { configAPI } from '@/api/config'
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
        console.log('MatrixWorld path:', path)
        console.log('User name:', name)

        // 1. 创建目录和模板（Tauri，不需要后端）
        console.log('📁 Step 1: Creating matrix world from template...')
        await invoke('init_matrix_world', { matrixWorldPath: path, userName: name })
        console.log('✅ Matrix world created')

        // 2. 保存 .env（存放真实的 API key）
        console.log('🔐 Step 2: Saving .env file...')
        const envVars = {
          LLM_API_KEY: this.wizardData.default_llm.api_key,
          SLM_API_KEY: this.wizardData.default_slm.api_key,
        }
        await invoke('save_env_file', { matrixWorldPath: path, envVars })
        console.log('✅ .env saved')

        // 3. 保存 LLM 配置（API key 位置固定为环境变量名）
        console.log('⚙️  Step 3: Saving LLM config...')
        const llmConfig = {
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
        }
        await invoke('save_llm_config', { matrixWorldPath: path, llmConfig })
        console.log('✅ LLM config saved')

        // 4. 保存 Email Proxy 配置（如果有）
        if (this.wizardData.email_proxy.enabled) {
          console.log('📧 Step 4: Saving email proxy config...')
          await invoke('save_email_proxy_config_cmd', {
            matrixWorldPath: path,
            emailProxy: this.wizardData.email_proxy,
          })
          console.log('✅ Email proxy config saved')
        }

        // 5. 启动后端（此时目录和文件已存在）
        console.log('🔧 Step 5: Starting backend server...')
        try {
          await invoke('start_backend')
          console.log('✅ Backend server started')
        } catch (backendError) {
          console.error('❌ Failed to start backend:', backendError)
          throw new Error(
            `Failed to start backend server: ${backendError}\n\n` +
            'This usually means the Python server executable could not be found.\n' +
            'Please check the console logs for details.'
          )
        }

        // 等待后端启动
        console.log('⏳ Waiting for backend to be ready...')
        await new Promise(resolve => setTimeout(resolve, 3000))

        // 健康检查，最多重试 3 次
        let backendReady = false
        for (let i = 0; i < 3; i++) {
          console.log(`   Health check attempt ${i + 1}/3...`)
          const isRunning = await invoke('check_backend')
          if (isRunning) {
            console.log('✅ Backend is ready!')
            backendReady = true
            break
          }
          if (i < 2) {
            console.log('   Backend not ready, waiting 2 more seconds...')
            await new Promise(resolve => setTimeout(resolve, 2000))
          }
        }

        if (!backendReady) {
          throw new Error(
            'Backend server failed to start or is not responding.\n\n' +
            'The server may have crashed. Please check:\n' +
            '1. Python is installed on your system\n' +
            '2. All dependencies are available\n' +
            '3. The MatrixWorld directory is valid'
          )
        }

        // 6. 通知后端初始化 runtime（读取已有文件）
        console.log('🎯 Step 6: Initializing runtime...')
        const result = await configAPI.initRuntime({ matrix_world_path: path })

        if (!result.success) {
          throw new Error(
            `Runtime initialization failed: ${result.message || 'Unknown error'}\n\n` +
            'Please check that all configuration files are valid.'
          )
        }
        console.log('✅ Runtime initialized')

        this.submitResult = result

        // 5.5 首次运行专属操作（仅冷启动时执行一次）
        try {
          console.log('🎉 Performing first-run initialization...')
          await configAPI.firstRunInit({
            matrix_world_path: path,
            user_name: name,
          })
          console.log('✅ First-run init complete')
        } catch (e) {
          console.warn('⚠️  First-run init failed (non-blocking):', e)
        }

        // 6. 标记已配置
        console.log('💾 Saving configuration...')
        await invoke('mark_configured', { matrixWorldPath: path })
        console.log('✅ Configuration saved')

        this.isFirstRun = false
        console.log('🎊 Wizard completed successfully!')
        return result
      } catch (error) {
        console.error('❌ Wizard submission failed:', error)
        console.error('Error stack:', error.stack)
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
