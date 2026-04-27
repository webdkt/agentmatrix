/**
 * API 客户端基础类
 */
class APIClient {
  constructor() {
    this.baseURL = ''
  }

  async _resolveBaseURL() {
    if (this.baseURL) return
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      const port = await invoke('get_backend_port')
      if (port) {
        this.baseURL = `http://localhost:${port}`
      }
    } catch {
      // Dev mode or Tauri not available — baseURL stays ''
    }
  }

  /**
   * 通用请求方法
   * @param {string} url - 请求路径
   * @param {object} options - 请求选项
   * @returns {Promise<any>}
   */
  async request(url, options = {}) {
    await this._resolveBaseURL()
    const config = {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    }

    if (options.body && config.method !== 'GET') {
      config.body = options.body
    }

    // Append query parameters
    let fullURL = this.baseURL + url
    if (options.params) {
      const searchParams = new URLSearchParams()
      for (const [key, value] of Object.entries(options.params)) {
        if (value != null) searchParams.append(key, value)
      }
      const qs = searchParams.toString()
      if (qs) fullURL += (fullURL.includes('?') ? '&' : '?') + qs
    }

    try {
      const response = await fetch(fullURL, config)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Request failed')
      }

      return data
    } catch (error) {
      console.error('API request failed:', error)
      throw error
    }
  }

  /**
   * GET 请求
   */
  async get(url, options = {}) {
    return this.request(url, { ...options, method: 'GET' })
  }

  /**
   * POST 请求
   */
  async post(url, body, options = {}) {
    return this.request(url, {
      ...options,
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  /**
   * PUT 请求
   */
  async put(url, body, options = {}) {
    return this.request(url, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(body),
    })
  }

  /**
   * DELETE 请求
   */
  async delete(url, options = {}) {
    return this.request(url, { ...options, method: 'DELETE' })
  }
}

export const API = new APIClient()
