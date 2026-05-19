import { ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { useSessionStore } from '@/stores/session'

/**
 * Floating Window 管理器
 * 管理浮动窗口的创建/销毁。浮动窗口自己连 WebSocket，不需要转发。
 */
const isActive = ref(false)
let unlistenRestore = null

export function useFloatingWindow() {
  const sessionStore = useSessionStore()
  const currentSession = computed(() => sessionStore.currentSession)

  /**
   * 打开浮动窗口
   */
  async function openFloating() {
    const session = currentSession.value
    if (!session) return

    const agentName = session.agent_name || session.name
    const sessionId = session.session_id
    const agentSessionId = session.agent_session_id

    if (!agentName || !agentSessionId) {
      console.warn('useFloatingWindow: missing agent info')
      return
    }

    // 1. Create floating window with session params in URL
    try {
      await invoke('create_floating_window', {
        sessionId,
        agentName,
        agentSessionId,
      })
    } catch (e) {
      console.error('Failed to create floating window:', e)
      return
    }

    isActive.value = true

    // 2. Listen for restore request from floating window
    if (!unlistenRestore) {
      unlistenRestore = await listen('floating:restore', async () => {
        await closeFloating()
      })
    }

    // 3. Minimize main window
    try {
      await invoke('minimize_main_window')
    } catch (e) {
      console.error('Failed to minimize main window:', e)
    }
  }

  /**
   * 关闭浮动窗口并恢复主窗口
   */
  async function closeFloating() {
    // Close input and detail windows if open
    try { await invoke('destroy_input_window') } catch { /* ignore */ }
    try { await invoke('destroy_detail_window') } catch { /* ignore */ }
    try {
      await invoke('destroy_floating_window')
    } catch (e) {
      console.error('Failed to destroy floating window:', e)
    }

    isActive.value = false

    // Restore main window
    try {
      await invoke('restore_main_window')
    } catch (e) {
      console.error('Failed to restore main window:', e)
    }
  }

  return {
    isActive,
    openFloating,
    closeFloating,
  }
}
