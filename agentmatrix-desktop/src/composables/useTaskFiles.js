import { ref, computed, watch, toValue } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { open, confirm } from '@tauri-apps/plugin-dialog'
import { useUIStore } from '@/stores/ui'

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

  // 文件选中状态
  const selectedFiles = ref(new Set())
  const lastSelectedFile = ref(null)

  // 右键菜单状态
  const contextMenu = ref({
    show: false,
    x: 0,
    y: 0,
    targetFile: null
  })

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
      // 进入目录时清空选中状态
      clearSelection()
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
    // 返回上级目录时清空选中状态
    clearSelection()
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
   * 切换文件选中状态
   */
  const toggleFileSelection = (entry, event) => {
    const path = entry.path

    // Ctrl/Cmd + Click：多选切换
    if (event.ctrlKey || event.metaKey) {
      if (selectedFiles.value.has(path)) {
        selectedFiles.value.delete(path)
      } else {
        selectedFiles.value.add(path)
      }
    }
    // Shift + Click：范围选择
    else if (event.shiftKey && lastSelectedFile.value) {
      selectRange(lastSelectedFile.value, entry)
    }
    // 单击：单选
    else {
      selectedFiles.value.clear()
      selectedFiles.value.add(path)
    }

    lastSelectedFile.value = path
  }

  /**
   * 范围选择
   */
  const selectRange = (fromPath, toPath) => {
    const fromIndex = files.value.findIndex(f => f.path === fromPath)
    const toIndex = files.value.findIndex(f => f.path === toPath)
    const start = Math.min(fromIndex, toIndex)
    const end = Math.max(fromIndex, toIndex)

    selectedFiles.value.clear()
    for (let i = start; i <= end; i++) {
      selectedFiles.value.add(files.value[i].path)
    }
  }

  /**
   * 清空选中状态
   */
  const clearSelection = () => {
    selectedFiles.value.clear()
    lastSelectedFile.value = null
  }

  /**
   * 检查文件是否被选中
   */
  const isFileSelected = (path) => selectedFiles.value.has(path)

  /**
   * 显示右键菜单
   */
  const showContextMenu = (entry, event) => {
    event.preventDefault()
    event.stopPropagation()

    contextMenu.value = {
      show: true,
      x: event.clientX,
      y: event.clientY,
      targetFile: entry
    }
  }

  /**
   * 隐藏右键菜单
   */
  const hideContextMenu = () => {
    contextMenu.value.show = false
    contextMenu.value.targetFile = null
  }

  /**
   * 复制文件到本地目录（不切换文件浏览器的当前目录）
   */
  const copyFilesToLocal = async (filePaths) => {
    const uiStore = useUIStore()

    try {
      // 打开目录选择对话框
      const selected = await open({
        directory: true,
        multiple: false,
        title: '选择目标目录'
      })

      if (!selected) return

      console.log('📁 Selected directory:', selected)
      console.log('📄 Files to copy:', filePaths)

      // 过滤掉目录，只复制文件
      const validFiles = []
      const skippedDirs = []

      for (const path of filePaths) {
        const entry = files.value.find(f => f.path === path)
        if (entry) {
          if (entry.is_dir) {
            skippedDirs.push(entry.name)
          } else {
            validFiles.push(path)
          }
        }
      }

      // 如果有目录被跳过，提示用户
      if (skippedDirs.length > 0) {
        console.log(`⚠️ Skipped ${skippedDirs.length} directories:`, skippedDirs)
      }

      // 如果没有有效的文件，直接返回
      if (validFiles.length === 0) {
        if (skippedDirs.length > 0) {
          uiStore.showNotification('请选择文件而不是目录', 'warning')
        }
        return
      }

      // 复制文件
      const fileNames = []
      for (const srcPath of validFiles) {
        const fileName = srcPath.split('/').pop()
        const destPath = `${selected}/${fileName}`

        console.log(`Checking: ${destPath}`)

        // 检查目标文件是否存在
        const destExists = await invoke('file_exists', { path: destPath })

        if (destExists) {
          // 询问用户是否覆盖
          const confirmed = await confirm(
            `文件 "${fileName}" 已存在，是否覆盖？`,
            { title: '确认覆盖', kind: 'warning' }
          )

          if (!confirmed) {
            console.log(`⏭️ Skipped: ${fileName}`)
            continue
          }
        }

        console.log(`Copying: ${srcPath} -> ${destPath}`)

        try {
          await invoke('copy_file', { src: srcPath, dest: destPath })
          fileNames.push(fileName)
          console.log(`✅ Copied: ${fileName}`)
        } catch (err) {
          console.error(`❌ Failed to copy ${fileName}:`, err)
          uiStore.showNotification(`复制失败: ${fileName}`, 'error')
        }
      }

      console.log(`📊 Copy result: ${fileNames.length}/${validFiles.length} files copied`)

      // 显示结果通知
      if (fileNames.length > 0) {
        let message = `成功复制 ${fileNames.length} 个文件`
        if (skippedDirs.length > 0) {
          message += `，跳过了 ${skippedDirs.length} 个目录`
        }
        uiStore.showNotification(message, 'success')
      }
    } catch (err) {
      console.error('❌ Copy to local failed:', err)
      uiStore.showNotification(`复制失败: ${err}`, 'error')
    }
  }

  /**
   * 处理右键菜单操作
   */
  const handleMenuAction = async (action) => {
    // 先保存 targetFile，避免 hideContextMenu 清空它
    const targetFile = contextMenu.value.targetFile
    hideContextMenu()

    console.log('=== handleMenuAction ===')
    console.log('Action:', action)
    console.log('Selected files:', Array.from(selectedFiles.value))
    console.log('Context menu target file:', targetFile)
    console.log('Current directory:', currentDir.value)

    const filesToProcess = selectedFiles.value.size > 0
      ? Array.from(selectedFiles.value)
      : targetFile ? [targetFile.path] : []

    console.log('Files to process:', filesToProcess)

    if (action === 'copy') {
      await copyFilesToLocal(filesToProcess)
    } else if (action === 'delete') {
      // 删除功能在后续阶段实现
      console.log('Delete action not implemented yet')
    }
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
    selectedFiles,
    toggleFileSelection,
    clearSelection,
    isFileSelected,
    contextMenu,
    showContextMenu,
    hideContextMenu,
    handleMenuAction,
  }
}
