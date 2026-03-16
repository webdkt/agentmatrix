import { defineStore } from 'pinia'
import { emailAPI } from '@/api/email'

/**
 * Email（邮件）管理 Store
 */
export const useEmailStore = defineStore('email', {
  state: () => ({
    emails: [],
    currentEmail: null,
    isLoading: false,
    error: null,
    searchQuery: '',
    filter: 'all', // all, unread, starred
  }),

  getters: {
    /**
     * 根据搜索和筛选条件过滤邮件
     */
    filteredEmails: (state) => {
      let filtered = [...state.emails]

      // 搜索过滤
      if (state.searchQuery) {
        const query = state.searchQuery.toLowerCase()
        filtered = filtered.filter(email => {
          return (
            email.subject?.toLowerCase().includes(query) ||
            email.body?.toLowerCase().includes(query) ||
            email.sender?.toLowerCase().includes(query)
          )
        })
      }

      // 状态过滤
      if (state.filter === 'unread') {
        filtered = filtered.filter(email => !email.read)
      } else if (state.filter === 'starred') {
        filtered = filtered.filter(email => email.starred)
      }

      return filtered
    },

    /**
     * 按时间排序的邮件（最新的在前）
     */
    sortedEmails: (state) => {
      return [...state.emails].sort((a, b) => {
        return new Date(b.timestamp) - new Date(a.timestamp)
      })
    },

    /**
     * 未读邮件数量
     */
    unreadCount: (state) => {
      return state.emails.filter(email => !email.read).length
    },
  },

  actions: {
    /**
     * 加载指定会话的邮件
     * @param {string} sessionId - 会话 ID
     */
    async loadEmails(sessionId) {
      this.isLoading = true
      this.error = null

      try {
        const result = await emailAPI.getEmails(sessionId)
        this.emails = result.emails || []
        console.log(`✅ Loaded ${this.emails.length} emails for session ${sessionId}`)
        return result
      } catch (error) {
        this.error = error.message
        console.error('Failed to load emails:', error)
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 发送邮件
     * @param {string} sessionId - 会话 ID
     * @param {object} emailData - 邮件数据
     * @param {File[]} files - 附件文件列表
     */
    async sendEmail(sessionId, emailData, files = []) {
      this.isLoading = true
      this.error = null

      try {
        const result = await emailAPI.sendEmail(sessionId, emailData, files)
        console.log('✅ Email sent successfully')

        // 刷新邮件列表
        await this.loadEmails(sessionId)

        return result
      } catch (error) {
        this.error = error.message
        console.error('Failed to send email:', error)
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 删除邮件
     * @param {string} emailId - 邮件 ID
     * @param {string} sessionId - 会话 ID（用于刷新列表）
     */
    async deleteEmail(emailId, sessionId) {
      this.isLoading = true
      this.error = null

      try {
        await emailAPI.deleteEmail(emailId)
        console.log(`✅ Email ${emailId} deleted successfully`)

        // 从本地列表中移除
        this.emails = this.emails.filter(email => email.id !== emailId)

        // 如果删除的是当前邮件，清除当前邮件
        if (this.currentEmail?.id === emailId) {
          this.currentEmail = null
        }
      } catch (error) {
        this.error = error.message
        console.error('Failed to delete email:', error)
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 搜索邮件
     * @param {string} query - 搜索关键词
     */
    async searchEmails(query) {
      this.searchQuery = query
      this.isLoading = true
      this.error = null

      try {
        if (!query) {
          // 如果搜索词为空，清空搜索
          this.emails = []
          return
        }

        const result = await emailAPI.searchEmails(query)
        this.emails = result.emails || []
        console.log(`✅ Found ${this.emails.length} emails matching "${query}"`)
        return result
      } catch (error) {
        this.error = error.message
        console.error('Failed to search emails:', error)
        throw error
      } finally {
        this.isLoading = false
      }
    },

    /**
     * 设置当前邮件
     * @param {object} email - 邮件对象
     */
    setCurrentEmail(email) {
      this.currentEmail = email
      // 标记为已读
      if (email && !email.read) {
        email.read = true
      }
    },

    /**
     * 清空邮件列表
     */
    clearEmails() {
      this.emails = []
      this.currentEmail = null
    },

    /**
     * 设置筛选条件
     * @param {string} filter - 筛选条件 (all, unread, starred)
     */
    setFilter(filter) {
      this.filter = filter
    },

    /**
     * 切换邮件星标状态
     * @param {string} emailId - 邮件 ID
     */
    toggleStarred(emailId) {
      const email = this.emails.find(e => e.id === emailId)
      if (email) {
        email.starred = !email.starred
      }
    },
  },
})
