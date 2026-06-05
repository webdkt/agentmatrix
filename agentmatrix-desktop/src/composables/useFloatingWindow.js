import { ref, computed, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { listen, emit as tauriEmit } from '@tauri-apps/api/event'
import { useSessionStore } from '@/stores/session'
import { useConfigStore } from '@/stores/config'

/**
 * Floating Window 管理器
 * 管理浮动窗口的创建/销毁。所有窗口通过 Tauri 事件接收后端 WS 数据（单一 Rust WS 连接）。
 */
const isActive = ref(false)
let unlistenRestore = null
let unlistenSwitchSession = null

export function useFloatingWindow() {
  const sessionStore = useSessionStore()
  const configStore = useConfigStore()
  const currentSession = computed(() => sessionStore.currentSession)

  /**
   * 将当前 session 写入 Rust 全局状态
   */
  async function syncCurrentSession(session) {
    await invoke('set_current_session', {
      session: {
        user_session_id: session.session_id || null,
        agent_session_id: session.agent_session_id || null,
        agent_name: session.agent_name || session.name || null,
        task_id: session.task_id || session.session_id || null,
        last_email_id: session.last_email_id || null,
        user_agent_name: configStore.config?.user_agent_name || null,
      },
    })
  }

  /**
   * 打开浮动窗口
   */
  async function openFloating() {
    const session = currentSession.value
    if (!session) return

    const agentName = session.agent_name || session.name
    const agentSessionId = session.agent_session_id

    if (!agentName || !agentSessionId) {
      console.warn('useFloatingWindow: missing agent info')
      return
    }

    // 1. Write session to Rust global state
    try {
      await syncCurrentSession(session)
    } catch (e) {
      console.error('Failed to set current session:', e)
      return
    }

    // 2. Create floating windows (they read from global state)
    try {
      await invoke('create_floating_window')
    } catch (e) {
      console.error('Failed to create floating window:', e)
      return
    }

    // 3. Re-emit session-changed as fallback (Rust already emitted from set_current_session,
    //    but floating windows may not have been ready at that point)
    await tauriEmit('session-changed')

    isActive.value = true

    // 4. Listen for restore request from floating window
    if (!unlistenRestore) {
      unlistenRestore = await listen('floating:restore', async () => {
        await closeFloating()
      })
    }

    // 5. Listen for session switch from floating window
    if (!unlistenSwitchSession) {
      unlistenSwitchSession = await listen('floating:switch-session', (event) => {
        const { sessionId } = event.payload
        const session = sessionStore.sessions.find(s => s.session_id === sessionId)
        if (session) {
          sessionStore.selectSession(session)
        }
      })
    }

    // 6. Minimize main window
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
    try { await invoke('destroy_input_window') } catch { /* ignore */ }
    try { await invoke('destroy_detail_window') } catch { /* ignore */ }
    try {
      await invoke('destroy_floating_window')
    } catch (e) {
      console.error('Failed to destroy floating window:', e)
    }

    isActive.value = false

    try {
      await invoke('restore_main_window')
    } catch (e) {
      console.error('Failed to restore main window:', e)
    }
  }

  // Watch for session changes during floating mode and sync to Rust
  watch(currentSession, async (newSession) => {
    if (!isActive.value || !newSession) return
    try {
      await syncCurrentSession(newSession)
    } catch (e) {
      console.error('Failed to sync session change:', e)
    }
  })

  return {
    isActive,
    openFloating,
    closeFloating,
    syncCurrentSession,
  }
}
