import { API } from './client'

/**
 * Session（会话）相关 API
 */
export const sessionAPI = {
  /**
   * 获取会话列表
   * @param {number} page - 页码
   * @param {number} perPage - 每页数量
   */
  async getSessions(page = 1, perPage = 20) {
    return API.get(`/api/sessions?page=${page}&per_page=${perPage}`)
  },

  /**
   * 获取单个会话详情
   * @param {string} sessionId - 会话 ID
   */
  async getSession(sessionId) {
    return API.get(`/api/sessions/${sessionId}`)
  },

  /**
   * 创建新会话
   * @param {object} data - 会话数据
   */
  async createSession(data) {
    return API.post('/api/sessions', data)
  },

  /**
   * 发送邮件
   * @param {string} sessionId - 会话 ID
   * @param {object} emailData - 邮件数据
   * @param {File[]} files - 附件文件列表
   */
  async sendEmail(sessionId, emailData, files = []) {
    console.log('📤 Sending email' + (files && files.length > 0 ? ` with ${files.length} attachment(s)` : ' without attachments'))

    // 使用 FormData（服务器端接受 FormData）
    const formData = new FormData()

    // 字段顺序必须与服务器端参数顺序一致
    formData.append('recipient', emailData.recipient)
    formData.append('subject', emailData.subject || '')
    formData.append('body', emailData.body)

    if (emailData.task_id) {
      formData.append('task_id', emailData.task_id)
    }
    if (emailData.in_reply_to) {
      formData.append('in_reply_to', emailData.in_reply_to)
    }
    if (emailData.recipient_session_id) {
      formData.append('recipient_session_id', emailData.recipient_session_id)
    }

    // 添加所有文件
    if (files && files.length > 0) {
      files.forEach((file, index) => {
        console.log(`📎 Adding file ${index + 1}:`, file.name, file.size, 'bytes')
        formData.append('attachments', file)
      })
    }

    // 使用 API 客户端的 baseURL 发送 FormData（Tauri 中不能用相对路径）
    try {
      await API._resolveBaseURL()
      const response = await fetch(`${API.baseURL}/api/sessions/${sessionId}/emails`, {
        method: 'POST',
        body: formData
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Failed to send email')
      }

      return data
    } catch (error) {
      console.error('Send email error:', error)
      throw error
    }
  },

  /**
   * 获取会话中的邮件列表
   * @param {string} sessionId - 会话 ID
   */
  async getEmails(sessionId) {
    return API.get(`/api/sessions/${sessionId}/emails`)
  },

  /**
   * 标记会话为已读
   * @param {string} sessionId - 会话 ID
   */
  async markAsRead(sessionId) {
    return API.post(`/api/sessions/${sessionId}/mark-read`)
  },

  /**
   * 获取 Agent session 的事件列表
   * @param {string} agentName - Agent 名称
   * @param {string} sessionId - Agent session ID
   * @param {number} limit - 最大数量
   * @param {number} offset - 偏移量
   * @param {string} direction - 'latest' 或 'older'
   * @param {string} before - direction='older' 时的时间戳
   */
  async getSessionEvents(agentName, sessionId, limit = 200, offset = 0, direction = 'latest', before = null) {
    const params = { limit, offset, direction }
    if (before) params.before = before
    return API.get(`/api/agents/${agentName}/sessions/${sessionId}/events`, { params })
  },
}
