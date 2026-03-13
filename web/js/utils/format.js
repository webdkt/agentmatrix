// 格式化工具函数

/**
 * 格式化时间戳为时间字符串
 * @param {string} timestamp - ISO 时间戳
 * @returns {string} 格式化的时间 (HH:MM)
 */
export function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * 格式化时间戳为日期字符串
 * @param {string} timestamp - ISO 时间戳
 * @returns {string} 格式化的日期（今天/昨天/X天前）
 */
export function formatDate(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();

    // Check if it's today (same day)
    const isToday = date.getDate() === now.getDate() &&
                   date.getMonth() === now.getMonth() &&
                   date.getFullYear() === now.getFullYear();

    if (isToday) {
        return '今天';
    }

    // Check if it's yesterday
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = date.getDate() === yesterday.getDate() &&
                       date.getMonth() === yesterday.getMonth() &&
                       date.getFullYear() === yesterday.getFullYear();

    if (isYesterday) {
        return '昨天';
    }

    // Calculate days difference for "X days ago"
    const diffTime = Math.abs(now - date);
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays < 7) {
        return `${diffDays}天前`;
    } else {
        return date.toLocaleDateString('zh-CN');
    }
}

/**
 * 格式化文件大小
 * @param {number} bytes - 字节数
 * @returns {string} 格式化的大小 (例如: "1.5 MB")
 */
export function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

/**
 * 格式化状态时间戳（用于 Agent 状态显示）
 * @param {string} timestamp - ISO 时间戳
 * @returns {string} 相对时间描述
 */
export function formatStatusTime(timestamp) {
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
        minute: '2-digit',
        second: '2-digit'
    });
}
