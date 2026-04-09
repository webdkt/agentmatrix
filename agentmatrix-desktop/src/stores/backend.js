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
  },

  actions: {
    async startBackend() {
      if (!this.canStart) {
        throw new Error('Cannot start backend in current state')
      }

      this.isStarting = true
      this.error = null

      try {
        console.log('Starting Python backend...')
        await invoke('start_backend')

        // Poll health check until backend is ready or we time out
        const maxAttempts = 5
        let isRunning = false
        for (let attempt = 1; attempt <= maxAttempts; attempt++) {
          const waitTime = Math.min(2000 * attempt, 8000)
          console.log(`Health check attempt ${attempt}/${maxAttempts}, waiting ${waitTime}ms...`)
          await new Promise(resolve => setTimeout(resolve, waitTime))

          isRunning = await this.checkBackendInternal()
          if (isRunning) break
        }

        if (!isRunning) {
          throw new Error('Backend failed to start after multiple attempts')
        }

        console.log('✅ Backend started successfully')

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

      // Reset state in case previous startup left stale state (e.g. app crash)
      this.isStarting = false
      this.isStopping = false
      this.isRunning = false

      // Server is already running (started by Rust setup before frontend loads)
      const isRunning = await this.checkBackendInternal()
      if (isRunning) {
        console.log('✅ Backend is running')
        this.startHealthMonitoring()
      } else {
        console.warn('Backend not detected, will retry via health monitoring')
        this.startWaitingForBackend()
      }
    },

    startWaitingForBackend() {
      if (this.healthCheckInterval) {
        clearInterval(this.healthCheckInterval)
      }
      console.log('Waiting for backend to start...')
      this.healthCheckInterval = setInterval(async () => {
        const isRunning = await this.checkBackendInternal()
        if (isRunning) {
          console.log('✅ Backend detected, switching to health monitoring')
          clearInterval(this.healthCheckInterval)
          this.healthCheckInterval = null
          this.startHealthMonitoring()
        }
      }, 3000)
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
