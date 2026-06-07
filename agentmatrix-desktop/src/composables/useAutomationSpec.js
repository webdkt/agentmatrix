import { ref, watch, toValue } from 'vue'
import { invoke } from '@tauri-apps/api/core'

// Convert directory name to display name: replace _/- with spaces, title case
function formatDisplayName(dirName) {
  return dirName
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, c => c.toUpperCase())
}

// Simple flat YAML parser for meta.yml (key: value only, no nesting)
function parseSimpleYaml(text) {
  const result = {}
  for (const line of text.split('\n')) {
    const m = line.match(/^(\w+)\s*:\s*(.+)$/)
    if (m) result[m[1]] = m[2].trim()
  }
  return result
}

// Read meta.yml from a directory, return parsed object or null
async function readMeta(dirPath) {
  try {
    const content = await invoke('read_text_file', { path: `${dirPath}/meta.yml` })
    return parseSimpleYaml(content)
  } catch {
    return null
  }
}

export function useAutomationSpec({ agentName }) {
  const systems = ref([])
  const isInitialLoad = ref(false)
  const error = ref(null)
  const rootDir = ref('')

  let _cachedWorldPath = null

  async function getWorldPath() {
    if (_cachedWorldPath) return _cachedWorldPath
    const config = await invoke('get_config')
    _cachedWorldPath = config.matrix_world_path
    return _cachedWorldPath
  }

  async function loadSystems() {
    const aName = toValue(agentName)
    if (!aName) return

    isInitialLoad.value = true
    error.value = null
    try {
      const worldPath = await getWorldPath()
      rootDir.value = `${worldPath}/workspace/agent_files/${aName}/home/automation_knowledge`

      const entries = await listDir(rootDir.value)
      const dirs = entries.filter(e => e.is_dir)

      // Read meta.yml for each system in parallel
      const metas = await Promise.all(dirs.map(d => readMeta(d.path)))
      systems.value = dirs.map((d, i) => {
        const meta = metas[i] || {}
        return {
          name: d.name,
          displayName: meta.display_name || formatDisplayName(d.name),
          description: meta.description || '',
          icon: meta.icon || null,
          path: d.path,
        }
      })
    } catch (e) {
      if (e && String(e).includes('not found')) {
        if (systems.value.length > 0) systems.value = []
      } else {
        console.error('[AutomationSpec] Failed to load systems:', e)
        error.value = String(e)
        systems.value = []
      }
    } finally {
      isInitialLoad.value = false
    }
  }

  async function listDir(dirPath) {
    try {
      const entries = await invoke('read_directory', { path: dirPath })
      return (entries || [])
        .filter(e => !e.name.startsWith('.'))
        .map(e => ({
          name: e.name,
          path: e.path,
          is_dir: e.is_dir,
          size: e.size || null,
        }))
    } catch {
      return []
    }
  }

  async function loadSystemProcesses(systemName) {
    const systemDir = `${rootDir.value}/${systemName}`
    const entries = await listDir(systemDir)
    const dirs = entries.filter(e => e.is_dir)

    // Read meta.yml for each process in parallel
    const metas = await Promise.all(dirs.map(d => readMeta(d.path)))
    return dirs.map((d, i) => {
      const meta = metas[i] || {}
      return {
        name: d.name,
        displayName: meta.display_name || formatDisplayName(d.name),
        description: meta.description || '',
        icon: meta.icon || null,
        path: d.path,
        is_dir: true,
      }
    })
  }

  async function loadProcessSteps(systemName, processName) {
    const processDir = `${rootDir.value}/${systemName}/${processName}`
    const entries = await listDir(processDir)
    const steps = []
    const otherFiles = []
    for (const e of entries) {
      if (e.is_dir) {
        otherFiles.push(e)
      } else {
        steps.push(e)
      }
    }
    return { steps, otherFiles }
  }

  async function revealPath(path) {
    try {
      await invoke('reveal_in_folder', { path })
    } catch (e) {
      console.error('[AutomationSpec] Failed to reveal:', e)
    }
  }

  watch(() => toValue(agentName), (name) => {
    if (name) {
      loadSystems()
    } else {
      systems.value = []
    }
  }, { immediate: true })

  return {
    systems,
    isInitialLoad,
    error,
    rootDir,
    loadSystems,
    listDir,
    loadSystemProcesses,
    loadProcessSteps,
    revealPath,
  }
}
