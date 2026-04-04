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

    // 添加所有文件
    if (files && files.length > 0) {
      files.forEach((file, index) => {
        console.log(`📎 Adding file ${index + 1}:`, file.name, file.size, 'bytes')
        formData.append('attachments', file)
      })
    }

    // 使用 fetch 直接发送 FormData
    try {
      const response = await fetch(`/api/sessions/${sessionId}/emails`, {
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
}
