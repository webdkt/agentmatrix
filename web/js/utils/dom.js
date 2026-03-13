// DOM 操作工具函数

/**
 * 滚动消息容器到底部
 * @param {string} containerId - 容器元素 ID
 */
export function scrollToBottom(containerId = 'messages-container') {
    const container = document.getElementById(containerId);
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

/**
 * 获取 Agent 头像名称
 * @param {string} name - Agent 名称
 * @returns {string} 头像名称（首字母大写，User 用 'U'）
 */
export function getAvatarName(name, user_agent_name = 'User') {
    if (!name) return '?';
    if (name === user_agent_name) return 'U';
    return name.substring(0, 2).toUpperCase();
}

/**
 * 查找 DOM 元素
 * @param {string} selector - CSS 选择器
 * @returns {Element|null} DOM 元素
 */
export function getElement(selector) {
    return document.querySelector(selector);
}

/**
 * 显示元素
 * @param {string} selector - CSS 选择器
 */
export function showElement(selector) {
    const el = document.querySelector(selector);
    if (el) {
        el.style.display = '';
    }
}

/**
 * 隐藏元素
 * @param {string} selector - CSS 选择器
 */
export function hideElement(selector) {
    const   el = document.querySelector(selector);
    if (el) {
        el.style.display = 'none';
    }
}

/**
 * 切换元素的显示状态
 * @param {string} selector - CSS 选择器
 */
export function toggleElement(selector) {
    const el = document.querySelector(selector);
    if (el) {
        if (el.style.display === 'none') {
            el.style.display = '';
        } else {
            el.style.display = 'none';
        }
    }
}
