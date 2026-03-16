import { defineStore } from 'pinia'
import { invoke } from '@tauri-apps/api/core'

export const useBackendStore = defineStore('backend', {
  state: () => ({
    isRunning: false,
    isStarting: false,
    isStopping: false,
    error: null,
    lastCheckTime: null,
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

        // Wait a bit for the backend to start
        await new Promise(resolve => setTimeout(resolve, 3000))

        // Check if it's actually running
        this.isRunning = await this.checkBackend()

        if (!this.isRunning) {
          throw new Error('Backend started but health check failed')
        }

        console.log('Backend started successfully')
      } catch (error) {
        this.error = error.message || 'Failed to start backend'
        console.error('Failed to start backend:', error)
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
        console.log('Stopping Python backend...')
        await invoke('stop_backend')

        // Wait a bit for the backend to stop
        await new Promise(resolve => setTimeout(resolve, 1000))

        this.isRunning = false
        console.log('Backend stopped successfully')
      } catch (error) {
        this.error = error.message || 'Failed to stop backend'
        console.error('Failed to stop backend:', error)
        throw error
      } finally {
        this.isStopping = false
      }
    },

    async checkBackend() {
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
  },
})
