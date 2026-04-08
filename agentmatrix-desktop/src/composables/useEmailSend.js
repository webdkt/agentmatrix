import { ref } from 'vue'
import { sessionAPI } from '@/api/session'
import { addPendingEmail, removePendingEmail } from '@/composables/usePendingEmails'

/**
 * 邮件发送逻辑 Composable
 * 统一处理邮件发送、状态管理、占位符、错误处理
 */
export function useEmailSend() {
  const isSending = ref(false)

  /**
   * 发送邮件
   * @param {string} sessionId - 会话 ID
   * @param {object} emailData - 邮件数据 { recipient, subject, body, in_reply_to, task_id }
   * @param {File[]} files - 附件列表
   * @returns {Promise<{response, placeholder}>}
   */
  const sendEmail = async (sessionId, emailData, files = []) => {
    // 参数验证
    if (!sessionId) {
      throw new Error('Session ID is required')
    }
    if (!emailData.recipient) {
      throw new Error('Recipient is required')
    }
    if (!emailData.body) {
      throw new Error('Email body is required')
    }

    isSending.value = true
    let placeholder = null

    try {
      // 1. 创建占位符，立即显示在 UI 中
      placeholder = addPendingEmail(sessionId, emailData)

      console.log('📤 Sending email:', {
        sessionId,
        recipient: emailData.recipient,
        hasAttachments: files.length > 0,
        inReplyTo: emailData.in_reply_to,
        taskId: emailData.task_id
      })

      // 2. 调用 API 发送邮件
      const response = await sessionAPI.sendEmail(sessionId, emailData, files)

      console.log('✅ Email sent successfully:', response)

      // 3. 清理占位符
      if (placeholder) {
        removePendingEmail(placeholder.id)
      }

      return { response, placeholder }

    } catch (error) {
      console.error('❌ Failed to send email:', error)

      // 清理占位符
      if (placeholder) {
        removePendingEmail(placeholder.id)
      }

      throw error
    } finally {
      isSending.value = false
    }
  }

  return {
    isSending,
    sendEmail
  }
}
