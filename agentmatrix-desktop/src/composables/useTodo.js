import { ref, watch, toValue, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'

/**
 * Todo composable — 只读，agent 自己管理 todo，前端只展示。
 *
 * 文件格式:
 * { "todos": { "index": { "item": "...", "status": "planned|working|canceled|done" } } }
 */
export function useTodo({ agentName, sessionId }) {
  const todos = ref({})       // {index: {item, status}}
  const filePath = ref('')
  const isLoaded = ref(false)
  const version = ref(0)

  let _lastRaw = ''
  let _pollTimer = null

  async function getWorldPath() {
    const config = await invoke('get_config')
    return config.matrix_world_path
  }

  async function init() {
    const aName = toValue(agentName)
    const sId = toValue(sessionId)
    if (!aName || !sId) return

    const worldPath = await getWorldPath()
    filePath.value = `${worldPath}/workspace/agent_files/${aName}/work_files/${sId}/.matrix/todo.json`
    await loadFromFile()
    startWatching()
  }

  async function loadFromFile() {
    if (!filePath.value) return
    try {
      const raw = await invoke('read_text_file', { path: filePath.value })
      _lastRaw = raw
      const data = JSON.parse(raw)
      todos.value = {}
      for (const [idx, val] of Object.entries(data.todos || {})) {
        todos.value[idx] = { item: val.item || '', status: val.status || 'planned' }
      }
      isLoaded.value = true
    } catch {
      todos.value = {}
      _lastRaw = ''
      isLoaded.value = true
    }
  }

  function startWatching() {
    stopWatching()
    _pollTimer = setInterval(async () => {
      if (!filePath.value) return
      try {
        const raw = await invoke('read_text_file', { path: filePath.value })
        if (raw !== _lastRaw) {
          _lastRaw = raw
          const data = JSON.parse(raw)
          const newTodos = {}
          for (const [idx, val] of Object.entries(data.todos || {})) {
            newTodos[idx] = { item: val.item || '', status: val.status || 'planned' }
          }
          todos.value = newTodos
          version.value++
        }
      } catch { /* ignore */ }
    }, 1000)
  }

  function stopWatching() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null }
  }

  watch([() => toValue(agentName), () => toValue(sessionId)], ([aName, sId]) => {
    if (aName && sId) { init() }
    else { stopWatching(); todos.value = {}; filePath.value = ''; isLoaded.value = false }
  }, { immediate: true })

  onUnmounted(() => stopWatching())

  return { todos, isLoaded, filePath, version }
}
