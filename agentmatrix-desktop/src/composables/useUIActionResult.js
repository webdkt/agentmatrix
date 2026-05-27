import { invoke } from '@tauri-apps/api/core'

export async function showUIActionResult(data) {
  const payload = {
    result: {
      agent_name: data.agent_name || null,
      action_name: data.action_name || null,
      result: data.result != null ? JSON.parse(JSON.stringify(data.result)) : null,
      display_mode: data.display_mode || null,
    },
  }
  console.log('[useUIActionResult] set_ui_action_result:', payload)
  try {
    await invoke('set_ui_action_result', payload)
    console.log('[useUIActionResult] state set, creating window...')
    await invoke('create_result_window')
    console.log('[useUIActionResult] done')
  } catch (e) {
    console.error('[useUIActionResult] Failed:', e)
  }
}
