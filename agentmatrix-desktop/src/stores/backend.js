import { defineStore } from 'pinia'
import { invoke } from '@tauri-apps/api/core'

export const useBackendStore = defineStore('backend', {
  state: () => ({
    isRunning: false,
    isStarting: false,
    isStopping: false,
    error: null,
    lastCheckTime: null,
    healthCheckInterval: null,
    startupAttempts: 0,
    maxStartupAttempts: 3,
    autoStartEnabled: true,
    continuousMonitoring: true,
  }),

  getters: {
    status: (state) => {
      if (state.isStarting) return 'starting'
      if (state.isStopping) return 'stopping'
      if (state.isRunning) return 'running'
      return 'stopped'
    },

    canStart: (state) => !state.isRunning && !state.isStarting,
    canStop: (state) => state.isRunning && !state.isStopping,

    healthStatus: (state) => {
      if (state.error) return 'error'
      if (state.isRunning) return 'healthy'
      return 'unhealthy'
    },

    canRetry: (state) => state.startupAttempts < state.maxStartupAttempts,
  },

  actions: {
    async startBackend(autoRetry = true) {
      if (!this.canStart) {
        throw new Error('Cannot start backend in current state')
      }

      this.isStarting = true
      this.error = null
      this.startupAttempts++

      try {
        console.log(`Starting Python backend... (Attempt ${this.startupAttempts}/${this.maxStartupAttempts})`)
        await invoke('start_backend')

        // Wait for backend to start with progressive backoff
        const waitTime = Math.min(2000 * this.startupAttempts, 8000)
        await new Promise(resolve => setTimeout(resolve, waitTime))

        // Check if it's actually running
        const isRunning = await this.checkBackendInternal()

        if (!isRunning) {
          if (autoRetry && this.canRetry) {
            console.log('Backend health check failed, retrying...')
            await new Promise(resolve => setTimeout(resolve, 2000))
            return this.startBackend(autoRetry)
          } else {
            throw new Error('Backend failed to start after multiple attempts')
          }
        }

        console.log('✅ Backend started successfully')
        this.startupAttempts = 0 // Reset on success

        // Start continuous monitoring
        if (this.continuousMonitoring) {
          this.startHealthMonitoring()
        }

        // Show success notification
        await this.showNotification(
          'Backend Started',
          'AgentMatrix backend is now running'
        )

        return true
      } catch (error) {
        this.error = error.message || 'Failed to start backend'
        console.error('❌ Failed to start backend:', error)

        // Show error notification
        await this.showNotification(
          'Backend Startup Failed',
          error.message || 'Could not start backend'
        )

        throw error
      } finally {
        this.isStarting = false
      }
    },

    async stopBackend() {
      if (!this.canStop) {
        throw new Error('Cannot stop backend in current state')
      }

      this.isStopping = true
      this.error = null

      try {
        // Stop health monitoring first
        this.stopHealthMonitoring()

        console.log('Stopping Python backend...')
        await invoke('stop_backend')

        // Wait for backend to stop
        await new Promise(resolve => setTimeout(resolve, 2000))

        this.isRunning = false
        console.log('✅ Backend stopped successfully')

        await this.showNotification(
          'Backend Stopped',
          'AgentMatrix backend has been stopped'
        )
      } catch (error) {
        this.error = error.message || 'Failed to stop backend'
        console.error('❌ Failed to stop backend:', error)
        throw error
      } finally {
        this.isStopping = false
      }
    },

    async checkBackendInternal() {
      try {
        const isRunning = await invoke('check_backend')
        this.isRunning = isRunning
        this.lastCheckTime = new Date()
        return isRunning
      } catch (error) {
        console.error('Backend health check failed:', error)
        this.isRunning = false
        this.lastCheckTime = new Date()
        return false
      }
    },

    async checkBackend() {
      return await this.checkBackendInternal()
    },

    startHealthMonitoring() {
      if (this.healthCheckInterval) {
        return // Already monitoring
      }

      console.log('Starting continuous health monitoring...')
      this.healthCheckInterval = setInterval(async () => {
        await this.checkBackendInternal()
      }, 30000) // Check every 30 seconds
    },

    stopHealthMonitoring() {
      if (this.healthCheckInterval) {
        clearInterval(this.healthCheckInterval)
        this.healthCheckInterval = null
        console.log('Stopped continuous health monitoring')
      }
    },

    async initializeBackend() {
      console.log('🚀 Initializing backend...')

      // Reset state in case previous startup left isStarting = true (e.g. app crash)
      this.isStarting = false
      this.isStopping = false

      // Check if backend is already running
      const isRunning = await this.checkBackendInternal()

      if (!isRunning && this.autoStartEnabled) {
        console.log('Auto-starting backend...')
        try {
          await this.startBackend()
        } catch (error) {
          console.error('Auto-start failed, user will need to start manually:', error)
          // Don't throw - let user handle manually
        }
      } else if (isRunning) {
        console.log('Backend already running')
        this.startHealthMonitoring()
      }
    },

    async showNotification(title, body) {
      try {
        await invoke('show_notification', { title, body })
      } catch (error) {
        console.error('Failed to show notification:', error)
        // Fallback to browser notification if in development
        if (Notification.permission === 'granted') {
          new Notification(title, { body })
        }
      }
    },

    clearError() {
      this.error = null
    },

    setAutoStart(enabled) {
      this.autoStartEnabled = enabled
      console.log(`Auto-start ${enabled ? 'enabled' : 'disabled'}`)
    },

    setContinuousMonitoring(enabled) {
      this.continuousMonitoring = enabled
      if (enabled && this.isRunning && !this.healthCheckInterval) {
        this.startHealthMonitoring()
      } else if (!enabled) {
        this.stopHealthMonitoring()
      }
    },
  },
})
