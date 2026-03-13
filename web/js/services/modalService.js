// Modal Service - 模态框业务逻辑

/**
 * Modal Service: 封装模态框相关的业务逻辑
 */
export class ModalService {
    constructor() {
        this.modals = {};
        this.modalStack = [];
    }

    /**
     * 注册模态框
     * @param {string} modalName - 模态框名称
     * @param {Object} initialState - 初始状态
     */
    registerModal(modalName, initialState = {}) {
        this.modals[modalName] = {
            show: false,
            ...initialState
        };
    }

    /**
     * 打开模态框
     * @param {string} modalName - 模态框名称
     * @param {Object} data - 模态框数据
     * @returns {boolean} 是否成功打开
     */
    openModal(modalName, data = {}) {
        if (!this.modals[modalName]) {
            console.warn(`Modal "${modalName}" not registered`);
            return false;
        }

        // 更新模态框状态
        this.modals[modalName] = {
            ...this.modals[modalName],
            show: true,
            ...data
        };

        // 添加到栈中
        this.modalStack.push(modalName);

        console.log(`✅ Opened modal: ${modalName}`);
        return true;
    }

    /**
     * 关闭模态框
     * @param {string} modalName - 模态框名称
     * @returns {boolean} 是否成功关闭
     */
    closeModal(modalName) {
        if (!this.modals[modalName]) {
            console.warn(`Modal "${modalName}" not registered`);
            return false;
        }

        // 隐藏模态框
        this.modals[modalName].show = false;

        // 从栈中移除
        const index = this.modalStack.indexOf(modalName);
        if (index > -1) {
            this.modalStack.splice(index, 1);
        }

        console.log(`✅ Closed modal: ${modalName}`);
        return true;
    }

    /**
     * 关闭所有模态框
     */
    closeAllModals() {
        for (const modalName of Object.keys(this.modals)) {
            this.modals[modalName].show = false;
        }
        this.modalStack = [];
        console.log('✅ Closed all modals');
    }

    /**
     * 获取模态框状态
     * @param {string} modalName - 模态框名称
     * @returns {Object|null} 模态框状态
     */
    getModalState(modalName) {
        return this.modals[modalName] || null;
    }

    /**
     * 检查模态框是否打开
     * @param {string} modalName - 模态框名称
     * @returns {boolean} 是否打开
     */
    isModalOpen(modalName) {
        return this.modals[modalName]?.show || false;
    }

    /**
     * 获取当前打开的模态框
     * @returns {string} 模态框名称
     */
    getCurrentModal() {
        return this.modalStack.length > 0
            ? this.modalStack[this.modalStack.length - 1]
            : null;
    }

    /**
     * 检查是否有任何模态框打开
     * @returns {boolean} 是否有模态框打开
     */
    hasOpenModal() {
        return this.modalStack.length > 0;
    }

    /**
     * 切换模态框显示状态
     * @param {string} modalName - 模态框名称
     * @returns {boolean} 切换后的状态
     */
    toggleModal(modalName) {
        if (this.isModalOpen(modalName)) {
            this.closeModal(modalName);
            return false;
        } else {
            this.openModal(modalName);
            return true;
        }
    }

    /**
     * 更新模态框数据
     * @param {string} modalName - 模态框名称
     * @param {Object} data - 新数据
     * @returns {boolean} 是否成功更新
     */
    updateModalData(modalName, data) {
        if (!this.modals[modalName]) {
            console.warn(`Modal "${modalName}" not registered`);
            return false;
        }

        this.modals[modalName] = {
            ...this.modals[modalName],
            ...data
        };

        return true;
    }

    /**
     * 重置模态框到初始状态
     * @param {string} modalName - 模态框名称
     * @returns {boolean} 是否成功重置
     */
    resetModal(modalName) {
        if (!this.modals[modalName]) {
            console.warn(`Modal "${modalName}" not registered`);
            return false;
        }

        // 保留初始状态，重置其他
        const initialState = Object.keys(this.modals[modalName]).reduce((acc, key) => {
            if (key !== 'show') {
                acc[key] = this.modals[modalName][key];
            }
            return acc;
        }, {});

        this.modals[modalName] = {
            show: false,
            ...initialState
        };

        return true;
    }

    /**
     * 获取所有模态框状态
     * @returns {Object} 所有模态框状态
     */
    getAllModals() {
        return { ...this.modals };
    }

    /**
     * 处理模态框确认操作
     * @param {string} modalName - 模态框名称
     * @param {Function} onConfirm - 确认回调
     */
    handleConfirm(modalName, onConfirm) {
        const result = onConfirm();

        // 如果确认成功（返回 true 或 Promise resolve），关闭模态框
        if (result === true || (result && typeof result.then === 'function')) {
            if (typeof result.then === 'function') {
                result.then(() => {
                    this.closeModal(modalName);
                });
            } else {
                this.closeModal(modalName);
            }
        }
    }

    /**
     * 处理模态框取消操作
     * @param {string} modalName - 模态框名称
     * @param {Function} onCancel - 取消回调
     */
    handleCancel(modalName, onCancel) {
        if (onCancel) {
            onCancel();
        }
        this.closeModal(modalName);
    }

    /**
     * 清理所有模态框
     */
    dispose() {
        this.closeAllModals();
        this.modals = {};
        this.modalStack = [];
    }
}
