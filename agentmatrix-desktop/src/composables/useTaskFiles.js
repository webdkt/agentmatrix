import { ref, computed, watch, toValue } from 'vue'
import { invoke } from '@tauri-apps/api/core'

/**
 * Task files composable — extracted from CollabPanel.vue
 * Manages file browser state: root dir init, directory listing, navigation, breadcrumbs.
 * agentName and sessionId can be refs or getter functions.
 */
export function useTaskFiles({ agentName, sessionId } = {}) {
  const files = ref([])
  const filesLoading = ref(false)
  const rootDir = ref('')
  const currentDir = ref('')

  const isAtRoot = computed(() => {
    return !rootDir.value || currentDir.value === rootDir.value
  })

  const relativePath = computed(() => {
    if (!rootDir.value || !currentDir.value) return ''
    const rel = currentDir.value.slice(rootDir.value.length)
    return rel || ''
  })

  async function getWorldPath() {
    const config = await invoke('get_config')
    return config.matrix_world_path
  }

  const loadFiles = async () => {
    if (!currentDir.value) return
    filesLoading.value = true
    try {
      const entries = await invoke('read_directory', { path: currentDir.value })
      files.value = entries || []
    } catch (err) {
      console.error('Failed to load directory:', err)
      files.value = []
    } finally {
      filesLoading.value = false
    }
  }

  const initRootDir = async () => {
    const aName = toValue(agentName)
    const sId = toValue(sessionId)
    if (!aName || !sId) return
    const worldPath = await getWorldPath()
    rootDir.value = `${worldPath}/workspace/agent_files/${aName}/work_files/${sId}`
    currentDir.value = rootDir.value
    await loadFiles()
  }

  const openEntry = async (entry) => {
    if (entry.is_dir) {
      currentDir.value = entry.path
      await loadFiles()
    } else {
      try {
        await invoke('open_folder', { path: entry.path })
      } catch (err) {
        console.error('Failed to open file:', err)
      }
    }
  }

  const goUp = async () => {
    if (isAtRoot.value) return
    const parent = currentDir.value.replace(/\/[^/]+$/, '')
    if (parent.length >= rootDir.value.length) {
      currentDir.value = parent
    } else {
      currentDir.value = rootDir.value
    }
    await loadFiles()
  }

  const goRoot = async () => {
    if (!rootDir.value) return
    currentDir.value = rootDir.value
    await loadFiles()
  }

  const formatFileSize = (bytes) => {
    if (!bytes) return ''
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  /**
   * Copy files (absolute paths) to a destination directory.
   * If destDir is not provided, copies to rootDir.
   * After copy, navigates to destDir and refreshes.
   * Returns { fileNames, destDir } — fileNames is the list of successfully copied basenames.
   */
  const copyFiles = async (filePaths, destDir) => {
    destDir = destDir || rootDir.value
    if (!destDir || !filePaths?.length) return { fileNames: [], destDir }

    const fileNames = []
    for (const srcPath of filePaths) {
      const fileName = srcPath.split('/').pop()
      const destPath = `${destDir}/${fileName}`
      try {
        await invoke('copy_file', { src: srcPath, dest: destPath })
        fileNames.push(fileName)
      } catch (err) {
        console.error(`Failed to copy ${fileName}:`, err)
      }
    }

    if (fileNames.length > 0) {
      currentDir.value = destDir
      await loadFiles()
    }

    return { fileNames, destDir }
  }

  // Init file browser when both agent and session are available
  watch([() => toValue(agentName), () => toValue(sessionId)], ([aName, sId]) => {
    if (aName && sId) {
      initRootDir()
    } else {
      files.value = []
      rootDir.value = ''
      currentDir.value = ''
    }
  }, { immediate: true })

  return {
    files,
    filesLoading,
    rootDir,
    currentDir,
    isAtRoot,
    relativePath,
    loadFiles,
    initRootDir,
    openEntry,
    goUp,
    goRoot,
    formatFileSize,
    copyFiles,
  }
}
