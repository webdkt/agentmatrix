import { ref, watch, toValue, onUnmounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export function useSiteKnowledge({ agentName }) {
  const sites = ref([])
  const isInitialLoad = ref(false)
  const error = ref(null)
  const rootDir = ref('')

  let _pollTimer = null
  let _cachedWorldPath = null

  async function getWorldPath() {
    if (_cachedWorldPath) return _cachedWorldPath
    const config = await invoke('get_config')
    _cachedWorldPath = config.matrix_world_path
    return _cachedWorldPath
  }

  const shallowEqualSites = (a, b) => {
    if (a.length !== b.length) return false
    for (let i = 0; i < a.length; i++) {
      if (a[i].site_key !== b[i].site_key) return false
    }
    return true
  }

  async function loadIndex(silent = false) {
    const aName = toValue(agentName)
    if (!aName) return

    if (!silent) {
      isInitialLoad.value = true
    }
    error.value = null
    try {
      const worldPath = await getWorldPath()
      rootDir.value = `${worldPath}/workspace/agent_files/${aName}/home/site_knowledge`
      const indexPath = `${rootDir.value}/index.txt`

      const content = await invoke('read_text_file', { path: indexPath })
      const entries = []
      for (const line of content.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith('#')) continue
        const parts = trimmed.split(':', 3)
        if (parts.length < 3) continue
        entries.push({
          site_key: trimmed,
          url_prefix: parts[0].trim(),
          desc: parts[1].trim(),
          dirname: parts[2].trim(),
        })
      }
      if (!shallowEqualSites(sites.value, entries)) {
        sites.value = entries
      }
    } catch (e) {
      if (e && String(e).includes('not found')) {
        if (sites.value.length > 0) sites.value = []
      } else {
        console.error('[SiteKnowledge] Failed to load index:', e)
        error.value = String(e)
        sites.value = []
      }
    } finally {
      if (!silent) {
        isInitialLoad.value = false
      }
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

  async function loadSiteProcesses(site) {
    const siteDir = `${rootDir.value}/${site.dirname}`
    const entries = await listDir(siteDir)
    const processes = entries.filter(e => e.is_dir)
    const files = entries.filter(e => !e.is_dir)
    return { processes, files }
  }

  async function loadProcessSteps(site, processDirName) {
    const processDir = `${rootDir.value}/${site.dirname}/${processDirName}`
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
      console.error('[SiteKnowledge] Failed to reveal:', e)
    }
  }

  function startPolling(interval = 10000) {
    stopPolling()
    loadIndex(false)
    _pollTimer = setInterval(() => loadIndex(true), interval)
  }

  function stopPolling() {
    if (_pollTimer) {
      clearInterval(_pollTimer)
      _pollTimer = null
    }
  }

  watch(() => toValue(agentName), (name) => {
    if (name) {
      startPolling()
    } else {
      stopPolling()
      sites.value = []
    }
  }, { immediate: true })

  onUnmounted(() => {
    stopPolling()
  })

  return {
    sites,
    isInitialLoad,
    error,
    rootDir,
    loadIndex,
    listDir,
    loadSiteProcesses,
    loadProcessSteps,
    revealPath,
  }
}