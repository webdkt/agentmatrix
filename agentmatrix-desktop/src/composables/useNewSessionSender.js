import { watch } from 'vue'
import { useSessionStore } from '@/stores/session'
import { sessionAPI } from '@/api/session'

/**
 * 发送新邮件并等待 session 创建完成。
 * 复用自 AgentSessionPanel 和 CreateKBWizard 的公共逻辑。
 *
 * 用法:
 *   const { sendAndWaitForSession } = useNewSessionSender()
 *   const session = await sendAndWaitForSession('知识管家', { subject, body, task_id })
 *   // session 已自动 selectSession
 */
export function useNewSessionSender() {
  const sessionStore = useSessionStore()

  let pendingTarget = null

  watch(() => sessionStore.sessions.length, (newLen, oldLen) => {
    if (!pendingTarget) return
    if (newLen <= oldLen) return

    const { resolve, agentName } = pendingTarget
    const newSession = sessionStore.sessions.find(s =>
      s.agent_name === agentName && !s._isPlaceholder
    )
    if (newSession) {
      pendingTarget = null
      resolve(newSession)
    }
  })

  function waitForNewSession(agentName) {
    return new Promise((resolve, reject) => {
      pendingTarget = { resolve, agentName }
      setTimeout(() => {
        if (pendingTarget) {
          pendingTarget = null
          reject(new Error('等待会话创建超时'))
        }
      }, 15000)
    })
  }

  /**
   * 发送新邮件，等待 session 出现并自动 selectSession。
   * @param {string} agentName - 目标 agent 名称
   * @param {object} emailData - { subject, body, task_id, ... }
   * @returns {Promise<object>} 创建好的 session 对象
   */
  async function sendAndWaitForSession(agentName, emailData) {
    // 先设 pendingTarget，再发邮件。避免 sendEmail 期间 NEW_USER_SESSION 到达但 pendingTarget 还是 null
    const sessionPromise = waitForNewSession(agentName)
    await sessionAPI.sendEmail('new', {
      recipient: agentName,
      ...emailData,
    })
    const session = await sessionPromise
    await sessionStore.selectSession(session)
    return session
  }

  return {
    sendAndWaitForSession,
  }
}