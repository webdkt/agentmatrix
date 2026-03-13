// Settings Store - 设置状态管理


/**
 * Settings Store: 管理 LLM 配置和系统设置
 */
function useSettingsStore() {
    return {
        // ========== 状态 ==========
        showAdvancedConfig: false,  // 控制高级配置折叠面板
        llmConfigs: [],
        showLLMModal: false,
        editingLLMConfig: null,
        isSavingLLM: false,
        isDeletingLLM: false,
        llmToDelete: null,
        showDeleteLLMConfirmModal: false,
        showLLMApiKey: false,
        llmFormErrors: {},
        llmForm: {
            name: '',
            url: '',
            api_key: '',
            model_name: ''
        },

        // ========== 方法 ==========

        /**
         * 加载 LLM 配置列表
         */
        async loadLLMConfigs() {
            try {
                const configs = await API.getLLMConfigs();
                this.llmConfigs = configs || [];
            } catch (error) {
                console.error('Failed to load LLM configs:', error);
                this.llmConfigs = [];
            }
        },

        /**
         * 打开 LLM 配置模态框
         * @param {Object} config - 配置对象（编辑时传入）
         */
        openLLMModal(config = null) {
            this.showLLMModal = true;
            this.editingLLMConfig = config;
            this.llmFormErrors = {};

            if (config) {
                // 编辑模式
                this.llmForm = {
                    name: config.name,
                    url: config.url,
                    api_key: config.api_key || '',
                    model_name: config.model_name
                };
            } else {
                // 创建模式
                this.llmForm = {
                    name: '',
                    url: '',
                    api_key: '',
                    model_name: ''
                };
            }
        },

        /**
         * 关闭 LLM 配置模态框
         */
        closeLLMModal() {
            this.showLLMModal = false;
            this.editingLLMConfig = null;
            this.llmForm = {
                name: '',
                url: '',
                api_key: '',
                model_name: ''
            };
            this.llmFormErrors = {};
        },

        /**
         * 验证 LLM 表单
         * @returns {boolean} 是否验证通过
         */
        validateLLMForm() {
            this.llmFormErrors = {};

            if (!this.editingLLMConfig && !this.llmForm.name.trim()) {
                this.llmFormErrors.name = 'Config name is required';
            }

            if (!this.editingLLMConfig && !/^[a-zA-Z0-9_-]+$/.test(this.llmForm.name)) {
                this.llmFormErrors.name = 'Name can only contain letters, numbers, underscores, and hyphens';
            }

            if (!this.llmForm.url.trim()) {
                this.llmFormErrors.url = 'API URL is required';
            } else if (!this.llmForm.url.startsWith('http://') && !this.llmForm.url.startsWith('https://')) {
                this.llmFormErrors.url = 'URL must start with http:// or https://';
            }

            if (!this.llmForm.model_name.trim()) {
                this.llmFormErrors.model_name = 'Model name is required';
            }

            return Object.keys(this.llmFormErrors).length === 0;
        },

        /**
         * 保存 LLM 配置（创建或更新）
         */
        async saveLLMConfig() {
            if (!this.validateLLMForm()) return;

            this.isSavingLLM = true;

            try {
                const formData = {
                    url: this.llmForm.url,
                    api_key: this.llmForm.api_key,
                    model_name: this.llmForm.model_name
                };

                if (this.editingLLMConfig) {
                    // 更新现有配置
                    await API.updateLLMConfig(this.editingLLMConfig.name, formData);
                    console.log('LLM config updated:', this.editingLLMConfig.name);
                } else {
                    // 创建新配置
                    formData.name = this.llmForm.name;
                    await API.createLLMConfig(formData);
                    console.log('LLM config created:', this.llmForm.name);
                }

                // 关闭模态框并刷新列表
                this.closeLLMModal();
                await this.loadLLMConfigs();
            } catch (error) {
                console.error('Failed to save LLM config:', error);
                alert(`Failed to save: ${error.message}`);
            } finally {
                this.isSavingLLM = false;
            }
        },

        /**
         * 删除 LLM 配置
         * @param {Object} config - 配置对象
         */
        confirmDeleteLLM(config) {
            this.llmToDelete = config;
            this.showDeleteLLMConfirmModal = true;
        },

        /**
         * 取消删除 LLM 配置
         */
        cancelDeleteLLM() {
            this.showDeleteLLMConfirmModal = false;
            this.llmToDelete = null;
        },

        /**
         * 执行删除 LLM 配置
         */
        async deleteLLMConfig() {
            if (!this.llmToDelete) return;

            this.isDeletingLLM = true;

            try {
                await API.deleteLLMConfig(this.llmToDelete.name);
                console.log('LLM config deleted:', this.llmToDelete.name);

                this.showDeleteLLMConfirmModal = false;
                this.llmToDelete = null;
                await this.loadLLMConfigs();
            } catch (error) {
                console.error('Failed to delete LLM config:', error);
                alert(`Failed to delete: ${error.message}`);
            } finally {
                this.isDeletingLLM = false;
            }
        },

        /**
         * 切换 API Key 显示/隐藏
         */
        toggleLLMApiKey() {
            this.showLLMApiKey = !this.showLLMApiKey;
        }
    };
}
