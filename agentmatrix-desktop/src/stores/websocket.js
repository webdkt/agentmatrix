import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSessionStore } from './session'

/**
 * WebSocket 事件管理 Store
 * 处理后端 WebSocket 推送的实时事件
 */
export const useWebSocketStore = defineStore('websocket', {
  state: () => ({
    isConnected: false,
    lastEvent: null,
    newEmailCallbacks: [], // 新邮件回调函数列表
    agentStatuses: {}, // 存储每个Agent的状态
  }),

  getters: {
    hasNewEmailCallbacks: (state) => {
      return state.newEmailCallbacks.length > 0
    }
  },

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

      console.log('📨 WebSocket message received:', data.type, data)

      // 处理新邮件事件
      if (data.type === 'new_email') {
        this.handleNewEmail(data.data)
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
     * 处理 Agent 状态增量更新
     */
    handleAgentStatusUpdate(message) {
      console.log('📊 AGENT_STATUS_UPDATE received:', message)
      const { agent_name, data } = message

      if (!agent_name || !data) {
        console.warn('Invalid AGENT_STATUS_UPDATE message:', message)
        return
      }

      // 更新 Agent 状态存储
      this.agentStatuses[agent_name] = {
        ...this.agentStatuses[agent_name],
        ...data,
        lastUpdated: new Date().toISOString()
      }

      console.log(`📊 Updated agent status for ${agent_name}:`, this.agentStatuses[agent_name])

      const sessionStore = useSessionStore()

      console.log(`📊 Processing update for ${agent_name}:`, {
        status: data.status,
        pending_question: data.pending_question,
        current_user_session_id: data.current_user_session_id
      })

      // 如果 agent 有 pending_question，设置到 session store
      if (data.pending_question && data.current_user_session_id) {
        console.log(`✅ Setting pending question for session ${data.current_user_session_id}`)
        sessionStore.setPendingQuestion(data.current_user_session_id, {
          agent_name: agent_name,
          question: data.pending_question,
          task_id: data.current_task_id,
          timestamp: new Date().toISOString()
        })
      }
      // 如果 pending_question 被清空，清除 session store 中的记录
      else if (data.current_user_session_id) {
        console.log(`❌ Clearing pending question for session ${data.current_user_session_id}`)
        sessionStore.clearPendingQuestion(data.current_user_session_id)
      }
    },

    /**
     * 处理新邮件事件
     */
    handleNewEmail(emailData) {
      console.log('📧 New email received via WebSocket:', emailData)

      // 通知所有注册的回调
      this.newEmailCallbacks.forEach(callback => {
        try {
          callback(emailData)
        } catch (error) {
          console.error('Error in new email callback:', error)
        }
      })
    },

    /**
     * 处理运行时事件
     */
    handleRuntimeEvent(eventData) {
      console.log('🎯 Runtime event received via WebSocket:', eventData)

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

      console.log('💬 ASK_USER event:', { agentName, question, payload })

      // 更新 session store 的 pendingQuestions
      sessionStore.setPendingQuestion(payload.session_id, {
        agent_name: agentName,
        question: question,
        task_id: payload.task_id,
        timestamp: new Date().toISOString()
      })
    },

    /**
     * 处理 SYSTEM_STATUS 事件（统一处理函数）
     */
    handleSystemStatus(statusData) {
      console.log('📊 SYSTEM_STATUS received:', statusData)

      const sessionStore = useSessionStore()

      // 更新所有 Agent 的状态
      if (statusData.agents) {
        Object.entries(statusData.agents).forEach(([agentName, agentInfo]) => {
          console.log(`  - Agent ${agentName}:`, agentInfo)

          // 存储到 agentStatuses
          this.agentStatuses[agentName] = {
            ...agentInfo,
            lastUpdated: new Date().toISOString()
          }

          // 如果 agent 有 pending_question
          if (agentInfo.pending_question && agentInfo.current_user_session_id) {
            console.log(`    ✅ Found pending question for session ${agentInfo.current_user_session_id}`)
            sessionStore.setPendingQuestion(agentInfo.current_user_session_id, {
              agent_name: agentName,
              question: agentInfo.pending_question,
              task_id: agentInfo.current_task_id,
              timestamp: new Date().toISOString()
            })
          }
          // 如果 agent 的 pending_question 被清空
          else if (agentInfo.current_user_session_id) {
            console.log(`    ❌ No pending question for session ${agentInfo.current_user_session_id}`)
            sessionStore.clearPendingQuestion(agentInfo.current_user_session_id)
          }
        })
      }
    },

    /**
     * 注册新邮件回调
     */
    onNewEmail(callback) {
      this.newEmailCallbacks.push(callback)

      // 返回清理函数
      return () => {
        this.newEmailCallbacks = this.newEmailCallbacks.filter(cb => cb !== callback)
      }
    },

    /**
     * 移除新邮件回调
     */
    offNewEmail(callback) {
      this.newEmailCallbacks = this.newEmailCallbacks.filter(cb => cb !== callback)
    }
  }
})
