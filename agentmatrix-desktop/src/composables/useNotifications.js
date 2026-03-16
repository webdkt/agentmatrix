import { invoke } from '@tauri-apps/api/core'
import { useBackendStore } from '@/stores/backend'

export function useNotifications() {
  const backendStore = useBackendStore()

  const showNotification = async (title, body) => {
    try {
      // Try to use native notification through Tauri
      await invoke('show_notification', { title, body })
    } catch (error) {
      console.error('Native notification failed:', error)

      // Fallback to browser notification (for development)
      if (import.meta.env.DEV) {
        if (Notification.permission === 'granted') {
          new Notification(title, { body })
        } else if (Notification.permission !== 'denied') {
          Notification.requestPermission().then((permission) => {
            if (permission === 'granted') {
              new Notification(title, { body })
            }
          })
        }
      }
    }
  }

  const notifyBackendStatus = async (status) => {
    const messages = {
      starting: { title: 'AgentMatrix', body: 'Starting backend server...' },
      running: { title: 'AgentMatrix', body: 'Backend server is running' },
      stopping: { title: 'AgentMatrix', body: 'Stopping backend server...' },
      stopped: { title: 'AgentMatrix', body: 'Backend server stopped' },
      error: { title: 'AgentMatrix Error', body: 'Backend operation failed' },
    }

    const message = messages[status]
    if (message) {
      await showNotification(message.title, message.body)
    }
  }

  const requestPermission = async () => {
    if (import.meta.env.DEV) {
      return Notification.requestPermission()
    }
    return 'granted' // Tauri has permission by default
  }

  return {
    showNotification,
    notifyBackendStatus,
    requestPermission,
  }
}
