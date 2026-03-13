// Session Store - 会话状态管理


/**
 * Session Store: 管理会话列表和当前会话
 */
function useSessionStore() {
    return {
        // ========== 状态 ==========
        sessions: [],
        currentSession: null,
        currentSessionEmails: [],
        isLoadingSessions: false,

        // ========== 方法 ==========

        /**
         * 加载所有会话
         */
        async loadSessions() {
            try {
                const sessionsData = await API.getSessions();
                this.sessions = sessionsData.sessions || [];
            } catch (error) {
                console.error('Failed to load sessions:', error);
                throw error;
            }
        },

        /**
         * 选择会话
         * @param {Object} session - 会话对象
         */
        async selectSession(session) {
            this.currentSession = session;
            await this.loadSessionEmails(session.session_id);
        },

        /**
         * 加载会话邮件
         * @param {string} sessionId - 会话 ID
         */
        async loadSessionEmails(sessionId) {
            try {
                const response = await API.getSessionEmails(sessionId);
                this.currentSessionEmails = response.emails || [];

                // ✅ 检查最后一封邮件，判断是否需要轮询 Agent 状态
                this.checkAndStartStatusPolling();

                // 等待 DOM 更新后滚动到底部
                this.$nextTick(() => {
                    this.scrollToBottom();
                });
            } catch (error) {
                console.error('Failed to load session emails:', error);
                this.currentSessionEmails = [];
            }
        },

        /**
         * 获取 Agent 头像名称
         * @param {string} name - Agent 名称
         * @returns {string} 头像名称（首字母大写，User 用 'U'）
         */
        getAvatarName(name) {
            if (!name) return '?';
            if (name === this.user_agent_name) return 'U';
            return name.substring(0, 2).toUpperCase();
        }
    };
}
