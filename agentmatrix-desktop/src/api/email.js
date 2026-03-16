import { API } from './client'

/**
 * Email（邮件）相关 API
 */
export const emailAPI = {
  /**
   * 获取会话中的邮件列表
   * @param {string} sessionId - 会话 ID
   */
  async getEmails(sessionId) {
    return API.get(`/api/sessions/${sessionId}/emails`)
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
   * 删除邮件
   * @param {string} emailId - 邮件 ID
   */
  async deleteEmail(emailId) {
    return API.delete(`/api/emails/${emailId}`)
  },

  /**
   * 搜索邮件
   * @param {string} query - 搜索关键词
   */
  async searchEmails(query) {
    return API.get(`/api/emails/search?q=${encodeURIComponent(query)}`)
  },

  /**
   * 获取邮件详情
   * @param {string} emailId - 邮件 ID
   */
  async getEmail(emailId) {
    return API.get(`/api/emails/${emailId}`)
  },
}
