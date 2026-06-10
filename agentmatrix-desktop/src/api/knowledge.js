import { API } from './client'

export const knowledgeAPI = {
  async listKBs() {
    return API.get('/api/knowledge/kbs')
  },

  async createKB(name, description, schema) {
    return API.post('/api/knowledge/kbs', { name, description, schema })
  },

  async getKB(name) {
    return API.get(`/api/knowledge/kbs/${name}`)
  },

  async updateSchema(name, content) {
    return API.put(`/api/knowledge/kbs/${name}/schema`, { content })
  },

  async listPages(name) {
    return API.get(`/api/knowledge/kbs/${name}/pages`)
  },

  async getPage(name, path) {
    return API.get(`/api/knowledge/kbs/${name}/pages/${path}`)
  },

  async listSources(name) {
    return API.get(`/api/knowledge/kbs/${name}/sources`)
  },

  async createSource(name, path, description = '') {
    return API.post(`/api/knowledge/kbs/${name}/sources`, { path, description })
  },

  async deleteSource(name, sourceId) {
    return API.delete(`/api/knowledge/kbs/${name}/sources/${sourceId}`)
  },

  async getSchemaDraft(taskId) {
    return API.get(`/api/knowledge/schema-draft/${taskId}`)
  },
}