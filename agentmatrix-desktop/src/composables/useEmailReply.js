import { computed } from 'vue'

/**
 * 回复邮件逻辑 Composable
 * 处理收件人解析、回复邮件数据构建
 * @param {object} currentSession - 当前会话对象
 */
export function useEmailReply(currentSession) {
  /**
   * 获取回复收件人
   * @param {object} targetEmail - 要回复的邮件对象
   * @returns {string} 收件人名称
   */
  const getRecipient = (targetEmail) => {
    if (!targetEmail) {
      // 没有目标邮件，回复给会话的 agent
      return currentSession?.name || ''
    }

    if (targetEmail.is_from_user) {
      // 用户发的邮件，回复给收件人（Agent）
      return targetEmail.recipient || currentSession?.name || ''
    } else {
      // Agent 发的邮件，回复给发件人（Agent）
      return targetEmail.sender || ''
    }
  }

  /**
   * 构建回复邮件数据
   * @param {object} targetEmail - 要回复的邮件对象
   * @param {string} body - 回复内容
   * @returns {object} 邮件数据 { recipient, subject, body, in_reply_to, task_id }
   */
  const buildReplyData = (targetEmail, body) => {
    const recipient = getRecipient(targetEmail)

    const emailData = {
      recipient,
      subject: '',  // 回复邮件通常不设置主题
      body,
    }

    // 如果有目标邮件，设置引用和 task_id
    if (targetEmail) {
      emailData.in_reply_to = targetEmail.id
      // 优先使用邮件的 task_id，保持线程一致性
      emailData.task_id = targetEmail.task_id || currentSession?.session_id
    } else {
      // 没有目标邮件，使用 session_id 作为 task_id
      emailData.task_id = currentSession?.session_id
    }

    return emailData
  }

  /**
   * 计算属性：回复提示文本
   * @param {object} targetEmail - 要回复的邮件对象
   * @returns {string} 提示文本
   */
  const getReplyPlaceholder = (targetEmail) => {
    if (!targetEmail) {
      return 'Send message...'
    }

    const recipientName = getRecipient(targetEmail)
    return `Replying to ${recipientName}...`
  }

  return {
    getRecipient,
    buildReplyData,
    getReplyPlaceholder
  }
}
