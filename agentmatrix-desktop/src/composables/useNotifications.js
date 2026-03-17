export function useNotifications() {
  const isTauri = window.__TAURI__ !== undefined

  const showNotification = async (title, body) => {
    if (isTauri) {
      // In Tauri environment, use backend notification system
      try {
        const { invoke } = await import('@tauri-apps/api/core')
        await invoke('show_notification', { title, body })
      } catch (error) {
        console.log('📱 Notification (Tauri):', title, '-', body)
      }
    } else {
      // In browser environment, use browser notifications
      try {
        if (Notification.permission === 'granted') {
          new Notification(title, { body })
        } else if (Notification.permission !== 'denied') {
          const permission = await Notification.requestPermission()
          if (permission === 'granted') {
            new Notification(title, { body })
          }
        }
      } catch (error) {
        console.log('📱 Notification (console):', title, '-', body)
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
    if (isTauri) {
      // Tauri doesn't need browser notification permission
      return 'granted'
    } else {
      // Request browser notification permission
      return await Notification.requestPermission()
    }
  }

  return {
    showNotification,
    notifyBackendStatus,
    requestPermission,
  }
}
