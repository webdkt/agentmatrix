import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useAgentStore } from './agent'
import { useConfigStore } from './config'

/**
 * WebSocket 事件管理 Store
 * 处理后端 WebSocket 推送的实时事件
 */
export const useWebSocketStore = defineStore('websocket', {
  state: () => ({
    isConnected: false,
    lastEvent: null,
    listeners: {},               // 事件监听器 { eventType: [callback, ...] }
  }),

  getters: {},

  actions: {
    /**
     * 设置连接状态
     */
    setConnected(connected) {
      this.isConnected = connected
    },

    /**
     * 处理 WebSocket 消息
     */
    handle_message(data) {
      this.lastEvent = data

      // Trigger registered listeners
      const eventType = data.type || data.event
      if (eventType && this.listeners[eventType]) {
        this.listeners[eventType].forEach(cb => {
          try { cb(data) } catch (e) { console.error('Listener error:', e) }
        })
      }

      // 处理 SESSION_EVENT（session 级事件，替代 user_session_updated）
      if (data.type === 'SESSION_EVENT') {
        this.handleSessionEvent(data)
      }
      // 处理新 user session（Agent 主动发新邮件时推送）
      else if (data.type === 'NEW_USER_SESSION') {
        this.handleNewUserSession(data.data)
      }
      // 处理运行时事件（USER_INTERACTION 等）
      else if (data.type === 'runtime_event') {
        this.handleRuntimeEvent(data.data)
      }
      // 处理系统状态事件（新连接时推送完整状态）
      else if (data.type === 'SYSTEM_STATUS') {
        this.handleSystemStatus(data.data)
      }
      // 处理 Agent 状态增量更新（Agent 状态变化时推送）
      else if (data.type === 'AGENT_STATUS_UPDATE') {
        this.handleAgentStatusUpdate(data)
      }
    },

    /**
     * 处理 SESSION_EVENT — session 级事件的统一入口
     */
    handleSessionEvent(message) {
      const { agent_name, session_id: agentSessionId, data: eventData } = message
      const { event_type, event_name, event_detail, timestamp } = eventData

      const sessionStore = useSessionStore()

      // 反查 user_session_id
      let userSessionId = sessionStore.agentSessionLookup(agent_name, agentSessionId)

      if (!userSessionId) {
        // 🔥 防御性逻辑：映射表中找不到，尝试在 sessions 数组中直接查找
        // 可能原因：NEW_USER_SESSION 和 SESSION_EVENT 存在竞态条件
        const fallbackSession = sessionStore.sessions.find(s =>
          s.agent_name === agent_name && s.agent_session_id === agentSessionId
        )
        if (fallbackSession) {
          userSessionId = fallbackSession.session_id
          // 补充映射表，避免下次还要查找
          sessionStore.addAgentSessionMapping(fallbackSession)
          console.log(`📬 SESSION_EVENT: fallback found ${agent_name}:${agentSessionId} → ${userSessionId}`)
        } else {
          console.log(`📬 SESSION_EVENT: no user_session for ${agent_name}:${agentSessionId}`)
          return
        }
      }

      const isCurrentSession = userSessionId === sessionStore.currentSession?.session_id

      // 通知 ChatHistory 等组件增量 append
      sessionStore.setLastSessionEvent({
        agent_name,
        session_id: agentSessionId,
        data: eventData,
      })

      // 按 event_type 分发（email 事件需要处理 unread/reload）
      if (event_type === 'email') {
        this._handleEmailEvent(userSessionId, isCurrentSession, event_name, event_detail, agent_name)
      }
    },

    /**
     * 处理 email 类 SESSION_EVENT
     */
    _handleEmailEvent(userSessionId, isCurrentSession, eventName, detail, agentName) {
      const sessionStore = useSessionStore()
      const configStore = useConfigStore()
      const userAgentName = configStore.config?.user_agent_name

      if (!userAgentName) {
        console.warn('⚠️ user_agent_name not found in config, skipping email event handling')
        return
      }

      // Agent 发送邮件（sent）= 判断接收者
      if (eventName === 'sent') {
        const recipient = detail?.recipient

        if (recipient === userAgentName) {
          // 发送给 User → User 收到邮件
          // 1. 更新前端缓存，更新 Agent 发信时间
          sessionStore.updateAgentMailTimeLocal(userSessionId)

          // 2. 仅当不是当前正在查看的 session 时才显示 toast
          if (detail && !isCurrentSession) {
            import('@/stores/ui').then(({ useUIStore }) => {
              const uiStore = useUIStore()
              uiStore.emailToast = {
                show: true,
                emailData: {
                  recipient_session_id: userSessionId,
                  sender: detail.sender || agentName,
                  subject: detail.subject || '',
                  ...detail,
                },
              }
            })
          }
        }
        // 其他情况：发给其他 Agent 的邮件，不做任何处理
      }
      // Agent 收到邮件（received）= 判断发送者
      else if (eventName === 'received') {
        const sender = detail?.sender

        if (sender === userAgentName) {
          // 用户发送的邮件 → 用户发信 = 用户查看
          // 更新前端缓存，更新查看时间
          sessionStore.updateCheckTimeLocal(userSessionId)
        }
        // 其他情况：Agent 之间的邮件，不做任何处理
      }
      // 注意：不需要在这里调用 selectSession，因为：
      // - setLastSessionEvent 已经被调用（第 94 行）
      // - useChatTimeline 会 watch 这个事件并增量更新 timeline
    },

    /**
     * 🆕 处理 Agent 状态增量更新
     */
    handleAgentStatusUpdate(message) {
      const { agent_name, data } = message

      if (!agent_name || !data) {
        console.warn('Invalid AGENT_STATUS_UPDATE message:', message)
        return
      }

      const sessionStore = useSessionStore()
      const agentStore = useAgentStore()

      // 更新 agent store 中的状态
      agentStore.updateAgentStatus(agent_name, data)

      // 如果 agent 有 pending_question，设置到 session store
      if (data.pending_question && data.current_user_session_id) {
        sessionStore.setPendingQuestion(data.current_user_session_id, {
          agent_name: agent_name,
          agent_session_id: data.current_session_id,
          question: data.pending_question,
          task_id: data.current_task_id,
          timestamp: new Date().toISOString()
        })
      }
      // 如果有 pending_question 但没有 current_user_session_id，设置全局 pending_question
      else if (data.pending_question) {
        sessionStore.setGlobalPendingQuestion({
          agent_name: agent_name,
          agent_session_id: data.current_session_id,
          question: data.pending_question,
          task_id: data.current_task_id,
          timestamp: new Date().toISOString()
        })
      }
      // 如果 pending_question 被清空，清除 session store 中的记录
      else if (data.current_user_session_id) {
        sessionStore.clearPendingQuestion(data.current_user_session_id)
      }
      // 如果 pending_question 被清空且没有 current_user_session_id，清除全局 pending_question
      else if (!data.pending_question && !data.current_user_session_id) {
        sessionStore.clearGlobalPendingQuestion()
      }
    },

    /**
     * 处理运行时事件
     */
    handleRuntimeEvent(eventData) {
      const eventType = eventData.type

      // 处理 ASK_USER 事件
      if (eventType === 'ASK_USER') {
        this.handleAskUserEvent(eventData)
      }
    },

    /**
     * 处理 ASK_USER 事件
     */
    handleAskUserEvent(eventData) {
      const { source: agentName, content: question, payload } = eventData
      const sessionStore = useSessionStore()

      sessionStore.setPendingQuestion(payload.session_id, {
        agent_name: agentName,
        question: question,
        task_id: payload.task_id,
        timestamp: new Date().toISOString()
      })
    },

    /**
     * 处理 SYSTEM_STATUS 事件
     */
    handleSystemStatus(statusData) {
      const sessionStore = useSessionStore()
      const agentStore = useAgentStore()

      if (statusData.agents) {
        Object.entries(statusData.agents).forEach(([agentName, agentInfo]) => {
          agentStore.updateAgentStatus(agentName, agentInfo)

          if (agentInfo.pending_question && agentInfo.current_user_session_id) {
            sessionStore.setPendingQuestion(agentInfo.current_user_session_id, {
              agent_name: agentName,
              agent_session_id: agentInfo.current_session_id,
              question: agentInfo.pending_question,
              task_id: agentInfo.current_task_id,
              timestamp: new Date().toISOString()
            })
          } else if (agentInfo.pending_question) {
            sessionStore.setGlobalPendingQuestion({
              agent_name: agentName,
              agent_session_id: agentInfo.current_session_id,
              question: agentInfo.pending_question,
              task_id: agentInfo.current_task_id,
              timestamp: new Date().toISOString()
            })
          } else if (agentInfo.current_user_session_id) {
            sessionStore.clearPendingQuestion(agentInfo.current_user_session_id)
          } else if (!agentInfo.pending_question && !agentInfo.current_user_session_id) {
            sessionStore.clearGlobalPendingQuestion()
          }
        })
      }
    },

    /**
     * 处理 NEW_USER_SESSION — Agent 主动发新邮件时，后端推送新 user session
     */
    handleNewUserSession(sessionData) {
      const sessionStore = useSessionStore()
      // 检查是否已存在（避免重复插入）
      const exists = sessionStore.sessions.some(s => s.session_id === sessionData.session_id)
      if (!exists) {
        sessionStore.sessions.unshift(sessionData)
        // 🔥 增量更新映射表（避免全量重建的性能问题）
        sessionStore.addAgentSessionMapping(sessionData)
        console.log('📍 NEW_USER_SESSION: added mapping', sessionData.agent_name, sessionData.agent_session_id, '→', sessionData.session_id)
      }
    },

    /**
     * 注册事件监听器
     */
    registerListener(eventType, callback) {
      if (!this.listeners[eventType]) {
        this.listeners[eventType] = []
      }
      this.listeners[eventType].push(callback)
    },

    /**
     * 注销事件监听器
     */
    unregisterListener(eventType, callback) {
      if (!this.listeners[eventType]) return
      this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback)
    },
  }
})
