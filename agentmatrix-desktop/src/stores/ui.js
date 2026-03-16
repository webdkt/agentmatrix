import { defineStore } from 'pinia'

/**
 * UI 状态管理 Store
 */
export const useUIStore = defineStore('ui', {
  state: () => ({
    // 侧边栏宽度
    sidebarWidth: 320,
    minSidebarWidth: 250,
    maxSidebarWidth: 500,

    // 面板尺寸（百分比）
    panelSizes: [30, 70], // [左侧面板, 右侧面板]

    // 对话框状态
    modals: {
      newEmail: false,
      settings: false,
      agentConfig: false,
      confirmDialog: false,
    },

    // 通知列表
    notifications: [],

    // 加载状态
    isLoading: false,

    // 错误信息
    error: null,

    // 主题
    theme: 'light', // light, dark

    // 是否显示调试信息
    debugMode: false,
  }),

  getters: {
    /**
     * 是否有通知
     */
    hasNotifications: (state) => {
      return state.notifications.length > 0
    },

    /**
     * 未读通知数量
     */
    unreadNotificationCount: (state) => {
      return state.notifications.filter(n => !n.read).length
    },

    /**
     * 当前主题是否为暗色
     */
    isDarkMode: (state) => {
      return state.theme === 'dark'
    },
  },

  actions: {
    /**
     * 调整侧边栏宽度
     * @param {number} width - 新宽度
     */
    resizeSidebar(width) {
      if (width >= this.minSidebarWidth && width <= this.maxSidebarWidth) {
        this.sidebarWidth = width
        // 保存到 localStorage
        localStorage.setItem('sidebarWidth', width.toString())
      }
    },

    /**
     * 重置侧边栏宽度
     */
    resetSidebarWidth() {
      this.sidebarWidth = 320
      localStorage.removeItem('sidebarWidth')
    },

    /**
     * 调整面板尺寸
     * @param {number[]} sizes - 面板尺寸数组
     */
    resizePanels(sizes) {
      this.panelSizes = sizes
    },

    /**
     * 打开对话框
     * @param {string} modalName - 对话框名称
     * @param {object} data - 对话框数据
     */
    openModal(modalName, data = null) {
      if (this.modals.hasOwnProperty(modalName)) {
        this.modals[modalName] = true
        // 可以在这里存储对话框相关的数据
        if (data) {
          this.modals[`${modalName}Data`] = data
        }
      } else {
        console.warn(`Modal "${modalName}" not found`)
      }
    },

    /**
     * 关闭对话框
     * @param {string} modalName - 对话框名称
     */
    closeModal(modalName) {
      if (this.modals.hasOwnProperty(modalName)) {
        this.modals[modalName] = false
        // 清除对话框数据
        delete this.modals[`${modalName}Data`]
      }
    },

    /**
     * 关闭所有对话框
     */
    closeAllModals() {
      Object.keys(this.modals).forEach(key => {
        if (typeof this.modals[key] === 'boolean') {
          this.modals[key] = false
        }
      })
    },

    /**
     * 显示通知
     * @param {string} message - 通知消息
     * @param {string} type - 通知类型 (info, success, warning, error)
     * @param {number} duration - 持续时间（毫秒）
     */
    showNotification(message, type = 'info', duration = 3000) {
      const notification = {
        id: Date.now() + Math.random(),
        message,
        type,
        read: false,
        createdAt: new Date(),
      }

      this.notifications.push(notification)

      // 自动移除通知
      if (duration > 0) {
        setTimeout(() => {
          this.removeNotification(notification.id)
        }, duration)
      }

      return notification.id
    },

    /**
     * 移除通知
     * @param {number} notificationId - 通知 ID
     */
    removeNotification(notificationId) {
      const index = this.notifications.findIndex(n => n.id === notificationId)
      if (index !== -1) {
        this.notifications.splice(index, 1)
      }
    },

    /**
     * 标记通知为已读
     * @param {number} notificationId - 通知 ID
     */
    markNotificationAsRead(notificationId) {
      const notification = this.notifications.find(n => n.id === notificationId)
      if (notification) {
        notification.read = true
      }
    },

    /**
     * 清空所有通知
     */
    clearNotifications() {
      this.notifications = []
    },

    /**
     * 设置加载状态
     * @param {boolean} loading - 是否加载中
     */
    setLoading(loading) {
      this.isLoading = loading
    },

    /**
     * 设置错误信息
     * @param {string|null} error - 错误信息
     */
    setError(error) {
      this.error = error
      if (error) {
        this.showNotification(error, 'error')
      }
    },

    /**
     * 切换主题
     */
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light'
      // 保存到 localStorage
      localStorage.setItem('theme', this.theme)
      // 应用主题到 document
      document.documentElement.setAttribute('data-theme', this.theme)
    },

    /**
     * 设置主题
     * @param {string} theme - 主题名称
     */
    setTheme(theme) {
      this.theme = theme
      localStorage.setItem('theme', theme)
      document.documentElement.setAttribute('data-theme', theme)
    },

    /**
     * 切换调试模式
     */
    toggleDebugMode() {
      this.debugMode = !this.debugMode
    },

    /**
     * 初始化 UI 状态（从 localStorage 恢复）
     */
    initializeUI() {
      // 恢复侧边栏宽度
      const savedSidebarWidth = localStorage.getItem('sidebarWidth')
      if (savedSidebarWidth) {
        this.sidebarWidth = parseInt(savedSidebarWidth, 10)
      }

      // 恢复主题
      const savedTheme = localStorage.getItem('theme')
      if (savedTheme) {
        this.setTheme(savedTheme)
      }
    },
  },
})
