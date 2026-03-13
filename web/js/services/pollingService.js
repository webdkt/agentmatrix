// Polling Service - 状态轮询业务逻辑

/**
 * Polling Service: 封装 Agent 状态轮询相关的业务逻辑
 */
export class PollingService {
    constructor() {
        this.pollingInterval = null;
        this.intervalTime = 2000;  // 2 秒
        this.isPolling = false;
        this.targetAgent = '';
        this.statusHistory = [];
        this.maxHistory = 3;
    }

    /**
     * 检查是否需要开始轮询
     * @param {Array} emails - 邮件列表
     * @returns {boolean} 是否需要轮询
     */
    shouldStartPolling(emails) {
        if (!emails || emails.length === 0) {
            return false;
        }

        const lastEmail = emails[emails.length - 1];
        // 只有最后一封邮件是用户发出的，才需要轮询
        return lastEmail.sender === 'User';
    }

    /**
     * 获取轮询目标 Agent
     * @param {Array} emails - 邮件列表
     * @param {string} sessionName - 会话名称
     * @returns {string} Agent 名称
     */
    getPollingTarget(emails, sessionName) {
        if (!emails || emails.length === 0) {
            return sessionName;
        }

        const lastEmail = emails[emails.length - 1];
        return lastEmail.recipient || sessionName;
    }

    /**
     * 开始轮询
     * @param {string} agentName - Agent 名称
     * @param {Function} onStatusUpdate - 状态更新回调
     * @returns {boolean} 是否成功开始轮询
     */
    startPolling(agentName, onStatusUpdate) {
        if (this.isPolling) {
            console.warn('Polling already in progress');
            return false;
        }

        this.isPolling = true;
        this.targetAgent = agentName;

        // 立即获取一次状态
        this.fetchStatus(agentName, onStatusUpdate);

        // 设置定时轮询
        this.pollingInterval = setInterval(() => {
            this.fetchStatus(agentName, onStatusUpdate);
        }, this.intervalTime);

        console.log(`✅ Started polling for agent: ${agentName}`);
        return true;
    }

    /**
     * 停止轮询
     */
    stopPolling() {
        if (!this.isPolling) {
            return;
        }

        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }

        this.isPolling = false;
        this.targetAgent = '';
        this.statusHistory = [];

        console.log('✅ Stopped polling');
    }

    /**
     * 获取 Agent 状态
     * @param {string} agentName - Agent 名称
     * @param {Function} onStatusUpdate - 状态更新回调
     */
    async fetchStatus(agentName, onStatusUpdate) {
        try {
            const response = await fetch(`/api/agents/${agentName}/status`);
            const data = await response.json();

            if (data.success && data.message) {
                // 更新状态历史
                this.addStatusToHistory({
                    message: data.message,
                    timestamp: data.timestamp || new Date().toISOString()
                });

                // 触发回调
                if (onStatusUpdate) {
                    onStatusUpdate(this.getStatusHistory());
                }
            }
        } catch (error) {
            console.error('Failed to fetch agent status:', error);
        }
    }

    /**
     * 添加状态到历史记录
     * @param {Object} status - 状态对象
     */
    addStatusToHistory(status) {
        this.statusHistory.push(status);

        // 保持最近 3 条
        if (this.statusHistory.length > this.maxHistory) {
            this.statusHistory.shift();
        }
    }

    /**
     * 获取状态历史
     * @returns {Array} 状态历史
     */
    getStatusHistory() {
        return this.statusHistory;
    }

    /**
     * 获取当前状态
     * @returns {Object|null} 当前状态
     */
    getCurrentStatus() {
        if (this.statusHistory.length === 0) {
            return null;
        }
        return this.statusHistory[this.statusHistory.length - 1];
    }

    /**
     * 检查是否正在轮询
     * @returns {boolean} 是否正在轮询
     */
    isActive() {
        return this.isPolling;
    }

    /**
     * 获取轮询目标
     * @returns {string} Agent 名称
     */
    getTarget() {
        return this.targetAgent;
    }

    /**
     * 格式化状态时间
     * @param {string} timestamp - 时间戳
     * @returns {string} 格式化后的时间
     */
    formatStatusTime(timestamp) {
        if (!timestamp) return '';

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

        // 大于 1 小时，显示时间
        return date.toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    /**
     * 清理资源
     */
    dispose() {
        this.stopPolling();
    }
}
