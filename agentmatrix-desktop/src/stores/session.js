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
    pendingQuestions: {},        // { session_id: { agent_name, question, task_id, timestamp } }
    globalPendingQuestion: null, // 全局待处理问题（无 user session id）
    globalDialogShown: false,    // 全局对话框是否已显示
    askUserDialogShownFor: null, // 记录已弹出对话框的 session_id
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
     * 检查 session 是否有待处理问题
     */
    hasPendingQuestion: (state) => (sessionId) => {
      return !!state.pendingQuestions[sessionId]
    },

    /**
     * 获取待处理问题详情
     */
    getPendingQuestion: (state) => (sessionId) => {
      return state.pendingQuestions[sessionId] || null
    },

    /**
     * 检查是否应该显示对话框
     */
    shouldShowAskUserDialog: (state) => (sessionId) => {
      const question = state.pendingQuestions[sessionId]
      // 只有当有待处理问题且尚未弹出过对话框时才显示
      return question && state.askUserDialogShownFor !== sessionId
    },

    /**
     * 获取全局待处理问题
     */
    getGlobalPendingQuestion: (state) => () => {
      return state.globalPendingQuestion
    },

    /**
     * 检查是否应该显示全局对话框
     */
    shouldShowGlobalAskUserDialog: (state) => () => {
      return !!state.globalPendingQuestion && !state.globalDialogShown
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

      // 如果切换到不同的 session，重置对话框标记
      if (this.currentSession?.session_id !== session.session_id) {
        this.resetDialogShown()
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
     * 设置待处理问题
     */
    setPendingQuestion(sessionId, questionData) {
      // 使用 Vue.reactive 确保响应式
      this.pendingQuestions = {
        ...this.pendingQuestions,
        [sessionId]: questionData
      }
      console.log('📝 Pending question set for session:', sessionId)
      console.log('📝 Current pendingQuestions:', this.pendingQuestions)
      console.log('📝 Current sessions:', this.sessions.map(s => ({ id: s.session_id, subject: s.subject })))
    },

    /**
     * 清除待处理问题
     */
    clearPendingQuestion(sessionId) {
      if (this.pendingQuestions[sessionId]) {
        delete this.pendingQuestions[sessionId]
        console.log('✅ Pending question cleared for session:', sessionId)
      }
    },

    /**
     * 设置全局待处理问题
     */
    setGlobalPendingQuestion(questionData) {
      this.globalPendingQuestion = questionData
      this.globalDialogShown = false // 重置对话框显示状态
      console.log('📝 Global pending question set:', questionData)
    },

    /**
     * 清除全局待处理问题
     */
    clearGlobalPendingQuestion() {
      this.globalPendingQuestion = null
      console.log('✅ Global pending question cleared')
    },

    /**
     * 标记全局对话框已显示
     */
    markGlobalDialogShown() {
      this.globalDialogShown = true
    },

    /**
     * 重置全局对话框显示状态
     */
    resetGlobalDialogShown() {
      this.globalDialogShown = false
    },

    /**
     * 提交 ask_user 回答
     */
    async submitAskUserAnswer(sessionId, answer) {
      const question = this.pendingQuestions[sessionId]
      if (!question) {
        throw new Error('No pending question for this session')
      }

      try {
        // 调用 API 提交回答（传递 agent_session_id）
        const { agentAPI } = await import('@/api/agent')
        await agentAPI.submitUserInput(
          question.agent_name,
          question.agent_session_id,
          question.question,
          answer
        )

        console.log('✅ Answer submitted for', question.agent_name)

        // 提交成功后不立即清除状态
        // 等待 WebSocket 推送状态更新后再清除
      } catch (error) {
        console.error('❌ Failed to submit answer:', error)
        throw error
      }
    },

    /**
     * 提交全局 ask_user 回答
     */
    async submitGlobalAskUserAnswer(answer) {
      const question = this.globalPendingQuestion
      if (!question) {
        throw new Error('No global pending question')
      }

      try {
        // 调用 API 提交回答（传递 agent_session_id）
        const { agentAPI } = await import('@/api/agent')
        await agentAPI.submitUserInput(
          question.agent_name,
          question.agent_session_id,
          question.question,
          answer
        )

        console.log('✅ Global answer submitted for', question.agent_name)

        // 提交成功后立即清除全局问题
        this.clearGlobalPendingQuestion()
      } catch (error) {
        console.error('❌ Failed to submit global answer:', error)
        throw error
      }
    },

    /**
     * 标记对话框已显示
     */
    markDialogShown(sessionId) {
      this.askUserDialogShownFor = sessionId
    },

    /**
     * 重置对话框标记
     */
    resetDialogShown() {
      this.askUserDialogShownFor = null
    },

    /**
     * 关闭对话框（标记为已显示，防止再次弹出）
     */
    closeAskUserDialog(sessionId) {
      if (sessionId) {
        this.markDialogShown(sessionId)
      }
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
