import { API } from './client'

export const knowledgeAPI = {
  async createKB(name, description, schema) {
    return API.post('/api/knowledge/kbs', { name, description, schema })
  },

  async updateSchema(name, content) {
    return API.put(`/api/knowledge/kbs/${name}/schema`, { content })
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
