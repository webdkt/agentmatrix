import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { knowledgeAPI } from '@/api/knowledge'

export const useKnowledgeStore = defineStore('knowledge', () => {
  // State
  const kbs = ref([])
  const currentKB = ref(null)
  const sources = ref([])
  const currentPage = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const schemaDraft = ref('')
  const schemaDraftLoading = ref(false)

  // ==================== KB 列表（Tauri 扫目录）====================

  async function fetchKBs() {
    loading.value = true
    error.value = null
    try {
      const config = await invoke('get_config')
      const wikiDir = `${config.matrix_world_path}/workspace/wiki`
      let entries
      try {
        entries = await invoke('read_directory', { path: wikiDir })
      } catch {
        entries = []
      }

      const result = []
      for (const entry of entries) {
        if (!entry.is_dir) continue
        // 检查 _schema.md 是否存在且非空
        let hasSchema = false
        try {
          const schemaContent = await invoke('read_text_file', {
            path: `${wikiDir}/${entry.name}/_schema.md`
          })
          hasSchema = !!schemaContent.trim()
        } catch {
          hasSchema = false
        }
        result.push({ name: entry.name, has_schema: hasSchema })
      }
      kbs.value = result
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  // ==================== 选择 KB ====================

  async function selectKB(name) {
    loading.value = true
    error.value = null
    currentPage.value = null
    try {
      // KB 基本信息（Tauri 读文件系统）
      const config = await invoke('get_config')
      const wikiDir = `${config.matrix_world_path}/workspace/wiki`
      let hasSchema = false
      let schema = ''
      try {
        schema = await invoke('read_text_file', { path: `${wikiDir}/${name}/_schema.md` })
        hasSchema = !!schema.trim()
      } catch {
        hasSchema = false
      }
      currentKB.value = { name, has_schema: hasSchema, schema }
      await fetchSources()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  // ==================== 页面内容（Tauri 读文件）====================

  async function selectPage(relPath) {
    if (!currentKB.value) return
    try {
      const config = await invoke('get_config')
      const fullPath = `${config.matrix_world_path}/workspace/wiki/${currentKB.value.name}/${relPath}`
      const content = await invoke('read_text_file', { path: fullPath })
      currentPage.value = { path: relPath, content }
    } catch (e) {
      error.value = e.message
    }
  }

  // ==================== Sources（后端 API — DB 操作）====================

  async function fetchSources() {
    if (!currentKB.value) return
    try {
      const data = await knowledgeAPI.listSources(currentKB.value.name)
      sources.value = data.sources || []
    } catch (e) {
      sources.value = []
    }
  }

  async function addSource(path, description = '') {
    if (!currentKB.value) return
    await knowledgeAPI.createSource(currentKB.value.name, path, description)
    await fetchSources()
  }

  async function removeSource(sourceId) {
    if (!currentKB.value) return
    await knowledgeAPI.deleteSource(currentKB.value.name, sourceId)
    await fetchSources()
  }

  // ==================== Schema Draft ====================

  async function fetchSchemaDraft(taskId) {
    schemaDraftLoading.value = true
    try {
      const data = await knowledgeAPI.getSchemaDraft(taskId)
      if (data.exists) {
        schemaDraft.value = data.content
      }
    } catch {
      // ignore
    } finally {
      schemaDraftLoading.value = false
    }
  }

  function clearCurrent() {
    currentKB.value = null
    sources.value = []
    currentPage.value = null
  }

  function clearSchemaDraft() {
    schemaDraft.value = ''
  }

  return {
    kbs, currentKB, sources, currentPage, loading, error,
    schemaDraft, schemaDraftLoading,
    fetchKBs, selectKB, selectPage,
    fetchSources, addSource, removeSource,
    fetchSchemaDraft, clearCurrent, clearSchemaDraft,
  }
})
