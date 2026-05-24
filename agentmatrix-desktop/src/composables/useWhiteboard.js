import { ref, watch, toValue, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'

/**
 * Whiteboard composable — sections 嵌套结构。
 *
 * 文件格式:
 * { "sections": { "sectionName": { "key": { "content": "...", "last_modified": "..." } } } }
 */
export function useWhiteboard({ agentName, sessionId }) {
  const sections = ref({})     // {section: {key: {content, last_modified}}}
  const filePath = ref('')
  const isLoaded = ref(false)

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
    filePath.value = `${worldPath}/workspace/agent_files/${aName}/work_files/${sId}/.matrix/whiteboard.json`
    await loadFromFile()
    startWatching()
  }

  async function loadFromFile() {
    if (!filePath.value) return
    try {
      const raw = await invoke('read_text_file', { path: filePath.value })
      _lastRaw = raw
      const data = JSON.parse(raw)
      sections.value = {}
      for (const [sec, entries] of Object.entries(data.sections || {})) {
        sections.value[sec] = {}
        for (const [k, v] of Object.entries(entries)) {
          sections.value[sec][k] = { content: v.content || '', last_modified: v.last_modified || '' }
        }
      }
      isLoaded.value = true
    } catch {
      sections.value = {}
      _lastRaw = ''
      isLoaded.value = true
    }
  }

  async function saveToFile() {
    if (!filePath.value) return
    const obj = { sections: {} }
    for (const [sec, entries] of Object.entries(sections.value)) {
      obj.sections[sec] = {}
      for (const [k, v] of Object.entries(entries)) {
        obj.sections[sec][k] = { content: v.content, last_modified: v.last_modified }
      }
    }
    const raw = JSON.stringify(obj, null, 2)
    _lastRaw = raw
    await invoke('write_text_file', { path: filePath.value, content: raw })
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
          const newSections = {}
          for (const [sec, entries] of Object.entries(data.sections || {})) {
            newSections[sec] = {}
            for (const [k, v] of Object.entries(entries)) {
              newSections[sec][k] = { content: v.content || '', last_modified: v.last_modified || '' }
            }
          }
          sections.value = newSections
        }
      } catch { /* ignore */ }
    }, 1000)
  }

  function stopWatching() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null }
  }

  async function setEntry(section, key, content) {
    const now = new Date().toISOString()
    if (!sections.value[section]) sections.value[section] = {}
    sections.value[section][key] = { content, last_modified: now }
    await saveToFile()
  }

  async function deleteEntry(section, key) {
    if (sections.value[section]) {
      delete sections.value[section][key]
      if (!Object.keys(sections.value[section]).length) delete sections.value[section]
    }
    await saveToFile()
  }

  async function deleteSection(section) {
    delete sections.value[section]
    await saveToFile()
  }

  async function replaceAll(newSections) {
    sections.value = newSections
    await saveToFile()
  }

  watch([() => toValue(agentName), () => toValue(sessionId)], ([aName, sId]) => {
    if (aName && sId) { init() }
    else { stopWatching(); sections.value = {}; filePath.value = ''; isLoaded.value = false }
  }, { immediate: true })

  onUnmounted(() => stopWatching())

  return { sections, isLoaded, filePath, setEntry, deleteEntry, deleteSection, replaceAll }
}
