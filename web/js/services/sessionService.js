// Session Service - 会话业务逻辑

import { API } from '../api.js';

/**
 * Session Service: 封装会话相关的业务逻辑
 */
export class SessionService {
    constructor() {
        this.api = API;
    }

    /**
     * 获取所有会话
     * @returns {Promise<Array>} 会话列表
     */
    async getSessions() {
        try {
            const sessionsData = await this.api.getSessions();
            return sessionsData.sessions || [];
        } catch (error) {
            console.error('Failed to get sessions:', error);
            throw error;
        }
    }

    /**
     * 获取会话的邮件列表
     * @param {string} sessionId - 会话 ID
     * @returns {Promise<Array>} 邮件列表
     */
    async getSessionEmails(sessionId) {
        try {
            const response = await this.api.getSessionEmails(sessionId);
            return response.emails || [];
        } catch (error) {
            console.error('Failed to get session emails:', error);
            throw error;
        }
    }

    /**
     * 格式化会话数据用于显示
     * @param {Object} session - 会话对象
     * @returns {Object} 格式化后的会话对象
     */
    formatSessionForDisplay(session) {
        return {
            ...session,
            displayName: session.name || session.session_id,
            timestamp: session.created_at || new Date().toISOString()
        };
    }

    /**
     * 获取会话的最后一条消息预览
     * @param {Object} session - 会话对象
     * @param {Array} emails - 邮件列表
     * @returns {string} 消息预览
     */
    getLastMessagePreview(session, emails) {
        if (!emails || emails.length === 0) {
            return '暂无消息';
        }

        const lastEmail = emails[emails.length - 1];
        const body = lastEmail.body || '';
        const maxLength = 50;

        if (body.length <= maxLength) {
            return body;
        }

        return body.substring(0, maxLength) + '...';
    }

    /**
     * 检查会话是否有新消息
     * @param {Object} session - 会话对象
     * @param {Array} emails - 邮件列表
     * @returns {boolean} 是否有新消息
     */
    hasNewMessages(session, emails) {
        if (!emails || emails.length === 0) {
            return false;
        }

        const lastEmail = emails[emails.length - 1];
        return lastEmail.sender !== 'User';
    }
}
