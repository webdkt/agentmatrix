import { API } from './client'

export const serviceAPI = {
  async getServices() {
    return API.get('/api/services/')
  },

  async getServiceDetail(name) {
    return API.get(`/api/services/${name}`)
  },

  async invokeAction(name, actionId, payload = {}) {
    return API.post(`/api/services/${name}/actions/${actionId}`, payload)
  },

  async getServiceEvents(name, limit = 200) {
    return API.get(`/api/services/${name}/events?limit=${limit}`)
  },

  async getWorkerEvents(name, workerId, limit = 200) {
    return API.get(`/api/services/${name}/workers/${workerId}/events?limit=${limit}`)
  },
}
