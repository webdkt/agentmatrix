import { defineStore } from 'pinia'
import { sessionAPI } from '@/api/session'

/**
 * Session（会话）管理 Store
 */
export const useSessionStore = defineStore('session', {
  state: () => ({
    sessions: [],
    currentSession: null,
    currentPage: 1,
    perPage: 20,
    totalSessions: 0,
    isLoading: false,
    error: null,
    agentToUserSessionMap: {},   // { "agentName:agentSessionId": "userSessionId" }
    lastSessionEvent: null,      // 最新的 SESSION_EVENT { agent_name, session_id, data }
  }),

  getters: {
    /**
     * 是否有更多会话可以加载
     */
    hasMoreSessions: (state) => {
      return state.sessions.length < state.totalSessions
    },

    /**
     * 计算 session 未读状态（基于时间比较）
     */
    isSessionUnread: (state) => (sessionId) => {
      const session = state.sessions.find(s => s.session_id === sessionId)
      if (!session) return false

      const lastAgentTime = session.last_agent_mail_time
      const lastCheckTime = session.last_check_time

      if (!lastAgentTime) return false
      if (!lastCheckTime) return true
      return new Date(lastAgentTime) > new Date(lastCheckTime)
    },

    /**
     * 当前会话的参与者名称
     */
    currentParticipants: (state) => {
      return state.currentSession?.participants || []
    },

    /**
     * 是否已选择会话
     */
    hasSelectedSession: (state) => {
      return !!state.currentSession
    },

    /**
     * 是否有未读会话
     */
    hasUnreadSessions: (state) => {
      return state.sessions.some(s => {
        const lastAgentTime = s.last_agent_mail_time
        const lastCheckTime = s.last_check_time
        if (!lastAgentTime) return false
        if (!lastCheckTime) return true
        return new Date(lastAgentTime) > new Date(lastCheckTime)
      })
    },

    /**
     * 通过 agent_name + agent_session_id 反查 user_session_id
     */
    agentSessionLookup: (state) => (agentName, agentSessionId) => {
      if (!agentName || !agentSessionId) return null
      const key = `${agentName}:${agentSessionId}`
      return state.agentToUserSessionMap[key] || null
    },
  },

  actions: {
    /**
     * 加载会话列表
     * @param {boolean} loadMore - 是否加载更多（追加到现有列表）
     */
    async loadSessions(loadMore = false) {
      this.isLoading = true
      this.error = null

      try {
        const page = loadMore ? this.currentPage + 1 : 1
        const result = await sessionAPI.getSessions(page, this.perPage)

        // API 返回格式: { sessions: [...], total, page, ... }
        const newSessions = result.sessions || []

        if (loadMore) {
          // 追加模式：合并数据
          this.sessions = [...this.sessions, ...newSessions]
          this.currentPage = page
        } else {
          // 刷新模式：替换数据
          this.sessions = newSessions
          this.currentPage = 1
        }

        this.totalSessions = result.total || 0

        // 构建 agent→user session 映射
        this.buildAgentSessionMap()

        return result
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 选择会话
     * @param {object} session - 会话对象
     * @param {boolean} force - 是否强制刷新（即使会话相同也重新加载邮件）
     */
    async selectSession(session, force = false) {
      // 如果是同一个会话且不强制刷新，直接返回
      if (!force && this.currentSession?.session_id === session.session_id) {
        console.log('⏭️ Same session selected, skipping (use force=true to refresh)')
        return
      }

      // force=true 时创建新对象引用，触发 Vue watch 重新加载邮件
      if (force && this.currentSession?.session_id === session.session_id) {
        this.currentSession = { ...session }
      } else {
        this.currentSession = session
      }

      // 立即调用 API 更新查看时间
      this.updateCheckTime(session.session_id)

      console.log('🔄 Session selected (will trigger loadEmails):', this.currentSession.session_id)
    },

    /**
     * 创建新会话
     * @param {object} data - 会话数据
     */
    async createSession(data) {
      this.isLoading = true
      this.error = null

      try {
        const newSession = await sessionAPI.createSession(data)
        // 将新会话添加到列表顶部
        this.sessions.unshift(newSession)
        this.totalSessions += 1

        // 自动选择新会话
        await this.selectSession(newSession)

        return newSession
      } catch (error) {
        this.error = error.message
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 搜索会话
     * @param {string} query - 搜索关键词
     */
    searchSessions(query) {
      if (!query) {
        // 如果搜索词为空，重新加载所有会话
        this.loadSessions()
        return
      }

      // 客户端简单搜索（搜索主题和参与者）
      const lowerQuery = query.toLowerCase()
      this.sessions = this.sessions.filter(session => {
        const subjectMatch = session.subject?.toLowerCase().includes(lowerQuery)
        const participantsMatch = session.participants?.some(p =>
          p.toLowerCase().includes(lowerQuery)
        )
        return subjectMatch || participantsMatch
      })
    },

    /**
     * 更新会话查看时间（本地乐观更新）
     * 用户发信/查看会话时调用
     */
    updateCheckTimeLocal(sessionId) {
      const index = this.sessions.findIndex(s => s.session_id === sessionId)
      if (index !== -1) {
        this.sessions[index] = {
          ...this.sessions[index],
          last_check_time: new Date().toISOString()
        }
      }
    },

    /**
     * 更新 Agent 发信时间（本地乐观更新）
     * Agent 发信时调用
     */
    updateAgentMailTimeLocal(sessionId) {
      const index = this.sessions.findIndex(s => s.session_id === sessionId)
      if (index !== -1) {
        this.sessions[index] = {
          ...this.sessions[index],
          last_agent_mail_time: new Date().toISOString()
        }
      }
    },

    /**
     * 更新会话查看时间（API + 本地乐观更新）
     */
    async updateCheckTime(sessionId) {
      try {
        await sessionAPI.selectSession(sessionId)
        // 本地乐观更新
        this.updateCheckTimeLocal(sessionId)
      } catch (error) {
        console.error('❌ Failed to update check time:', error)
      }
    },

    /**
     * 清除当前会话
     */
    clearCurrentSession() {
      this.currentSession = null
    },

    /**
     * Alias for loadSessions (refresh mode)
     */
    async fetchSessions() {
      return this.loadSessions(false)
    },

    /**
     * 构建 agent_name + agent_session_id → user_session_id 的映射表（全量重建）
     */
    buildAgentSessionMap() {
      const map = {}
      for (const session of this.sessions) {
        const agentName = session.agent_name || session.name
        const agentSessionId = session.agent_session_id
        if (agentName && agentSessionId) {
          map[`${agentName}:${agentSessionId}`] = session.session_id
        }
      }
      this.agentToUserSessionMap = map
    },

    /**
     * 增量添加单个 session 映射（用于 NEW_USER_SESSION 等场景）
     * @param {object} session - session 对象
     */
    addAgentSessionMapping(session) {
      const agentName = session.agent_name || session.name
      const agentSessionId = session.agent_session_id
      if (agentName && agentSessionId) {
        const key = `${agentName}:${agentSessionId}`
        this.agentToUserSessionMap[key] = session.session_id
      }
    },

    /**
     * 设置最新的 SESSION_EVENT（供 ChatHistory 等组件 watch 增量更新）
     * @param {object} event - { agent_name, session_id, data }
     */
    setLastSessionEvent(event) {
      this.lastSessionEvent = event
    },
  },
})
