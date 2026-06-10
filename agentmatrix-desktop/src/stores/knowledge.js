import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { knowledgeAPI } from '@/api/knowledge'

export const useKnowledgeStore = defineStore('knowledge', () => {
  // State
  const kbs = ref([])
  const currentKB = ref(null)
  const pages = ref([])
  const sources = ref([])
  const currentPage = ref(null)
  const loading = ref(false)
  const error = ref(null)
  const schemaDraft = ref('')
  const schemaDraftLoading = ref(false)

  // Actions
  async function fetchKBs() {
    loading.value = true
    error.value = null
    try {
      const data = await knowledgeAPI.listKBs()
      kbs.value = data.kbs || []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function selectKB(name) {
    loading.value = true
    error.value = null
    try {
      const data = await knowledgeAPI.getKB(name)
      currentKB.value = data
      await fetchPages()
      await fetchSources()
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchPages() {
    if (!currentKB.value) return
    try {
      const data = await knowledgeAPI.listPages(currentKB.value.name)
      pages.value = data.pages || []
    } catch (e) {
      pages.value = []
    }
  }

  async function selectPage(path) {
    if (!currentKB.value) return
    loading.value = true
    try {
      const data = await knowledgeAPI.getPage(currentKB.value.name, path)
      currentPage.value = data
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

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

  async function fetchSchemaDraft(taskId) {
    schemaDraftLoading.value = true
    try {
      const data = await knowledgeAPI.getSchemaDraft(taskId)
      if (data.exists) {
        schemaDraft.value = data.content
      }
    } catch (e) {
      // ignore
    } finally {
      schemaDraftLoading.value = false
    }
  }

  function clearCurrent() {
    currentKB.value = null
    pages.value = []
    sources.value = []
    currentPage.value = null
  }

  function clearSchemaDraft() {
    schemaDraft.value = ''
  }

  return {
    kbs, currentKB, pages, sources, currentPage, loading, error,
    schemaDraft, schemaDraftLoading,
    fetchKBs, selectKB, fetchPages, selectPage, fetchSources,
    addSource, removeSource, fetchSchemaDraft, clearCurrent, clearSchemaDraft,
  }
})