// 验证工具函数

/**
 * 验证必填字段
 * @param {string} value - 字段值
 * @param {string} fieldName - 字段名称（用于错误消息）
 * @returns {string|null} 错误消息，null 表示验证通过
 */
export function validateRequired(value, fieldName = 'This field') {
    if (!value || !value.trim()) {
        return `${fieldName} is required`;
    }
    return null;
}

/**
 * 验证字母、数字、下划线格式
 * @param {string} value - 字段值
 * @param {string} fieldName - 字段名称（用于错误消息）
 * @returns {string|null} 错误消息，null 表示验证通过
 */
export function validateAlphanumeric(value, fieldName = 'Name') {
    if (!value || !/^[a-zA-Z0-9_]+$/.test(value)) {
        return `${fieldName} can only contain letters, numbers, and underscores`;
    }
    return null;
}

/**
 * 验证字母、数字、下划线、连字符格式
 * @param {string} value - 字段值
 * @param {string} fieldName - 字段名称（用于错误消息）
 * @returns {string|null} 错误消息，null 表示验证通过
 */
export function validateAlphanumericWithHyphen(value, fieldName = 'Name') {
    if (!value || !/^[a-zA-Z0-9_-]+$/.test(value)) {
        return `${fieldName} can only contain letters, numbers, underscores, and hyphens`;
    }
    return null;
}

/**
 * 验证 URL 格式
 * @param {string} value - 字段值
 * @param {string} fieldName - 字段名称（用于错误消息）
 * @returns {string|null} 错误消息，null 表示验证通过
 */
export function validateUrl(value, fieldName = 'URL') {
    if (!value || !value.trim()) {
        return `${fieldName} is required`;
    }

    if (!value.startsWith('http://') && !value.startsWith('https://')) {
        return `${fieldName} must start with http:// or https://`;
    }

    return null;
}

/**
 * 验证 Email 格式
 * @param {string} value - 字段值
 * @param {string} fieldName - 字段名称（用于错误消息）
 * @returns {string|null} 错误消息，null 表示验证通过
 */
export function validateEmail(value, fieldName = 'Email') {
    if (!value || !value.trim()) {
        return `${fieldName} is required`;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(value)) {
        return `${fieldName} must be a valid email address`;
    }

    return null;
}

/**
 * 验证多个字段
 * @param {Object} fields - 字段对象 {fieldName: value}
 * @returns {boolean} 是否所有字段都有效
 */
export function validateRequiredFields(fields) {
    for (const [fieldName, value] of Object.entries(fields)) {
        if (!value || !value.trim()) {
            return false;
        }
    }
    return true;
}

/**
 * 批量验证
 * @param {Array<Function>} validators - 验证函数数组
 * @returns {Array<string>} 错误消息数组
 */
export function runValidators(...validators) {
    const errors = [];
    for (const validator of validators) {
        const result = validator();
        if (result) {
            errors.push(result);
        }
    }
    return errors;
}
