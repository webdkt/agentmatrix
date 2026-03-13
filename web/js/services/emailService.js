// Email Service - 邮件业务逻辑

import { API } from '../api.js';

/**
 * Email Service: 封装邮件相关的业务逻辑
 */
export class EmailService {
    constructor() {
        this.api = API;
    }

    /**
     * 发送邮件
     * @param {string} agentName - Agent 名称
     * @param {Object} emailData - 邮件数据
     * @param {string} emailData.recipient - 收件人
     * @param {string} emailData.body - 邮件正文
     * @param {string} emailData.session_id - 会话 ID
     * @param {string} [emailData.in_reply_to] - 回复的邮件 ID
     * @param {Array} [files] - 附件列表
     * @returns {Promise} 发送结果
     */
    async sendEmail(agentName, emailData, files = []) {
        try {
            const formData = new FormData();
            formData.append('recipient', emailData.recipient);
            formData.append('body', emailData.body);
            formData.append('session_id', emailData.session_id);

            if (emailData.in_reply_to) {
                formData.append('in_reply_to', emailData.in_reply_to);
            }

            // 添加附件
            for (const file of files) {
                formData.append('files', file);
            }

            return await this.api.sendEmail(agentName, formData);
        } catch (error) {
            console.error('Failed to send email:', error);
            throw error;
        }
    }

    /**
     * 验证邮件数据
     * @param {Object} emailData - 邮件数据
     * @returns {Object} 验证结果 {valid: boolean, errors: Object}
     */
    validateEmailData(emailData) {
        const errors = {};

        if (!emailData.recipient || !emailData.recipient.trim()) {
            errors.recipient = '收件人不能为空';
        }

        if (!emailData.body || !emailData.body.trim()) {
            errors.body = '邮件正文不能为空';
        }

        return {
            valid: Object.keys(errors).length === 0,
            errors
        };
    }

    /**
     * 验证附件
     * @param {FileList} files - 文件列表
     * @returns {Object} 验证结果 {valid: boolean, errors: Array, validFiles: Array}
     */
    validateAttachments(files) {
        const errors = [];
        const validFiles = [];

        for (const file of files) {
            // 只允许图片文件
            if (!file.type.startsWith('image/')) {
                errors.push(`${file.name}: 只支持图片文件`);
                continue;
            }

            // 检查文件大小（限制 10MB）
            const maxSize = 10 * 1024 * 1024;
            if (file.size > maxSize) {
                errors.push(`${file.name}: 文件大小不能超过 10MB`);
                continue;
            }

            validFiles.push(file);
        }

        return {
            valid: errors.length === 0,
            errors,
            validFiles
        };
    }

    /**
     * 格式化邮件用于显示
     * @param {Object} email - 邮件对象
     * @returns {Object} 格式化后的邮件对象
     */
    formatEmailForDisplay(email) {
        return {
            ...email,
            displayTime: this.formatEmailTime(email.timestamp),
            senderName: this.formatSenderName(email.sender),
            hasAttachments: email.attachments && email.attachments.length > 0
        };
    }

    /**
     * 格式化邮件时间
     * @param {string} timestamp - 时间戳
     * @returns {string} 格式化后的时间
     */
    formatEmailTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;

        // 小于 1 分钟
        if (diff < 60000) {
            return '刚刚';
        }

        // 小于 1 小时
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes} 分钟前`;
        }

        // 今天
        if (date.getDate() === now.getDate() &&
            date.getMonth() === now.getMonth() &&
            date.getFullYear() === now.getFullYear()) {
            return date.toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit'
            });
        }

        // 昨天
        const yesterday = new Date(now);
        yesterday.setDate(yesterday.getDate() - 1);
        if (date.getDate() === yesterday.getDate() &&
            date.getMonth() === yesterday.getMonth() &&
            date.getFullYear() === yesterday.getFullYear()) {
            return '昨天';
        }

        // 更早
        return date.toLocaleDateString('zh-CN');
    }

    /**
     * 格式化发送者名称
     * @param {string} sender - 发送者
     * @returns {string} 格式化后的发送者名称
     */
    formatSenderName(sender) {
        if (!sender) return '未知';

        // 如果是 User，显示为"你"
        if (sender === 'User') {
            return '你';
        }

        // 如果是 Agent，显示 Agent 名称
        return sender;
    }

    /**
     * 获取回复收件人
     * @param {Object} email - 邮件对象
     * @param {string} mode - 回复模式 ('reply' | 'replyAll')
     * @returns {string} 回复收件人
     */
    getReplyRecipient(email, mode = 'reply') {
        if (mode === 'replyAll') {
            return email.replyAll || email.recipient;
        }
        return email.recipient;
    }

    /**
     * 创建回复邮件数据
     * @param {Object} originalEmail - 原始邮件
     * @param {string} replyBody - 回复正文
     * @param {string} sessionId - 会话 ID
     * @returns {Object} 回复邮件数据
     */
    createReplyEmail(originalEmail, replyBody, sessionId) {
        return {
            recipient: originalEmail.recipient,
            body: replyBody,
            session_id: sessionId,
            in_reply_to: originalEmail.id
        };
    }
}
