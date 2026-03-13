// Agent Store - Agent 状态管理


/**
 * Agent Store: 管理 Agent 列表和配置
 */
function useAgentStore() {
    return {
        // ========== 状态 ==========
        agents: [],
        files: [],
        user_agent_name: 'User',
        agentSearchQuery: '',
        showAgentDropdown: false,

        // Agent Modal 状态
        showAgentModal: false,
        editingAgent: null,
        agentEditMode: 'simple',  // 'simple' | 'advanced'
        agentFormErrors: {},
        isSavingAgent: false,
        isDeletingAgent: false,
        agentToDelete: null,
        showDeleteAgentConfirmModal: false,
        agentForm: {
            name: '',
            description: '',
            system_prompt: '',
            llm_name: '',
            skills: []
        },
        agentRawYaml: '',

        // Skill Search Modal 状态
        showSkillSearchModal: false,
        skillSearchQuery: '',
        skillSearchResults: [],
        availableSkills: [],

        // Agent 状态轮询
        agentStatusPolling: false,
        agentStatusTarget: '',
        agentStatusHistory: [],
        agentStatusError: null,

        // ========== 方法 ==========

        /**
         * 加载所有 Agent
         */
        async loadAgents() {
            try {
                const agentsData = await API.getAgents();
                this.agents = agentsData.agents || [];
                console.log('Loaded agents:', this.agents);
            } catch (error) {
                console.error('Failed to load agents:', error);
            }
        },

        /**
         * 获取 Agent 描述
         * @param {string} agentName - Agent 名称
         * @returns {string} Agent 描述
         */
        getAgentDescription(agentName) {
            const agent = this.agents.find(a => a.name === agentName);
            return agent?.description || '';
        },

        /**
         * 打开 Agent 模态框（创建或编辑）
         * @param {Object} agent - Agent 对象（编辑时传入）
         */
        openAgentModal(agent = null) {
            this.showAgentModal = true;
            this.editingAgent = agent;
            this.agentEditMode = 'simple';
            this.agentFormErrors = {};

            if (agent) {
                // 编辑模式：填充表单
                this.agentForm = {
                    name: agent.name,
                    description: agent.description || '',
                    system_prompt: agent.system_prompt || '',
                    llm_name: agent.llm_name || '',
                    skills: agent.skills || []
                };
                this.agentRawYaml = this.agentToYaml(agent);
            } else {
                // 创建模式：清空表单
                this.agentForm = {
                    name: '',
                    description: '',
                    system_prompt: '',
                    llm_name: '',
                    skills: []
                };
                this.agentRawYaml = '';
            }
        },

        /**
         * 关闭 Agent 模态框
         */
        closeAgentModal() {
            this.showAgentModal = false;
            this.editingAgent = null;
            this.agentForm = {
                name: '',
                description: '',
                system_prompt: '',
                llm_name: '',
                skills: []
            };
            this.agentRawYaml = '';
            this.agentFormErrors = {};
        },

        /**
         * 验证 Agent 表单
         * @returns {boolean} 是否验证通过
         */
        validateAgentForm() {
            this.agentFormErrors = {};

            if (!this.editingAgent && !this.agentForm.name.trim()) {
                this.agentFormErrors.name = 'Agent name is required';
            }

            if (!this.editingAgent && !/^[a-zA-Z0-9_]+$/.test(this.agentForm.name)) {
                this.agentFormErrors.name = 'Name can only contain letters, numbers, and underscores';
            }

            return Object.keys(this.agentFormErrors).length === 0;
        },

        /**
         * 保存 Agent（创建或更新）
         */
        async saveAgent() {
            // Advanced 模式不需要验证表单
            if (this.agentEditMode === 'simple' && !this.validateAgentForm()) return;

            // Advanced 模式下验证 YAML
            if (this.agentEditMode === 'advanced') {
                try {
                    const parsed = this.parseYaml(this.agentRawYaml);
                    if (!parsed.name) {
                        this.agentFormErrors.yaml = 'YAML must have a "name" field';
                        return;
                    }
                } catch (e) {
                    this.agentFormErrors.yaml = 'Invalid YAML format: ' + e.message;
                    return;
                }
            }

            this.isSavingAgent = true;

            try {
                let formData;

                if (this.agentEditMode === 'advanced') {
                    // Advanced 模式：直接解析 YAML
                    formData = this.parseYaml(this.agentRawYaml);
                } else {
                    // Simple 模式：构建表单数据
                    formData = {
                        name: this.agentForm.name,
                        description: this.agentForm.description,
                        system_prompt: this.agentForm.system_prompt,
                        llm_name: this.agentForm.llm_name,
                        skills: this.agentForm.skills
                    };
                }

                if (this.editingAgent) {
                    // 更新现有 Agent
                    if (this.editingAgent._raw_profile) {
                        // 保留原始字段
                        for (const [key, value] of Object.entries(this.editingAgent._raw_profile)) {
                            if (!(key in formData)) {
                                formData[key] = value;
                            }
                        }
                    }
                    await API.updateAgentProfile(this.editingAgent.name, formData);
                    console.log('Agent updated:', this.editingAgent.name);
                } else {
                    // 创建新 Agent
                    await API.createAgent(formData);
                    console.log('Agent created:', formData.name);
                }

                // 关闭模态框并刷新列表
                this.closeAgentModal();
                await this.loadAgents();
            } catch (error) {
                console.error('Failed to save agent:', error);
                alert(`Failed to save: ${error.message}`);
            } finally {
                this.isSavingAgent = false;
            }
        },

        /**
         * 删除 Agent
         * @param {Object} agent - Agent 对象
         */
        confirmDeleteAgent(agent) {
            this.agentToDelete = agent;
            this.showDeleteAgentConfirmModal = true;
        },

        /**
         * 取消删除 Agent
         */
        cancelDeleteAgent() {
            this.showDeleteAgentConfirmModal = false;
            this.agentToDelete = null;
        },

        /**
         * 执行删除 Agent
         */
        async deleteAgent() {
            if (!this.agentToDelete) return;

            this.isDeletingAgent = true;

            try {
                await API.deleteAgent(this.agentToDelete.name);
                console.log('Agent deleted:', this.agentToDelete.name);

                this.showDeleteAgentConfirmModal = false;
                this.agentToDelete = null;
                await this.loadAgents();
            } catch (error) {
                console.error('Failed to delete agent:', error);
                alert(`Failed to delete: ${error.message}`);
            } finally {
                this.isDeletingAgent = false;
            }
        },

        /**
         * 切换 Simple/Advanced 模式
         */
        toggleAgentEditMode() {
            if (this.agentEditMode === 'simple') {
                // 切换到 Advanced：从表单生成 YAML
                if (this.editingAgent) {
                    this.agentRawYaml = this.agentToYaml(this.editingAgent);
                } else {
                    this.agentRawYaml = this.formToYaml(this.agentForm);
                }
                this.agentEditMode = 'advanced';
            } else {
                // 切换到 Simple：从 YAML 解析到表单
                try {
                    const parsed = this.parseYaml(this.agentRawYaml);
                    this.agentForm = {
                        name: parsed.name || '',
                        description: parsed.description || '',
                        system_prompt: parsed.system_prompt || '',
                        llm_name: parsed.llm_name || '',
                        skills: parsed.skills || []
                    };
                    this.agentEditMode = 'simple';
                } catch (e) {
                    alert('Invalid YAML: ' + e.message);
                }
            }
        },

        /**
         * 打开 Skill 搜索模态框
         */
        openSkillSearchModal() {
            this.showSkillSearchModal = true;
            this.skillSearchQuery = '';
            this.skillSearchResults = [];
            this.loadAvailableSkills();
        },

        /**
         * 关闭 Skill 搜索模态框
         */
        closeSkillSearchModal() {
            this.showSkillSearchModal = false;
            this.skillSearchQuery = '';
            this.skillSearchResults = [];
        },

        /**
         * 加载可用 Skills
         */
        async loadAvailableSkills() {
            try {
                const data = await API.getSkills();
                this.availableSkills = data.skills || [];
            } catch (error) {
                console.error('Failed to load skills:', error);
                this.availableSkills = [];
            }
        },

        /**
         * 搜索 Skills
         */
        searchSkills() {
            if (!this.skillSearchQuery.trim()) {
                this.skillSearchResults = this.availableSkills;
            } else {
                const query = this.skillSearchQuery.toLowerCase();
                this.skillSearchResults = this.availableSkills.filter(skill =>
                    skill.name.toLowerCase().includes(query) ||
                    (skill.description && skill.description.toLowerCase().includes(query))
                );
            }
        },

        /**
         * 添加 Skill
         * @param {Object} skill - Skill 对象
         */
        addSkill(skill) {
            if (!this.agentForm.skills.find(s => s.name === skill.name)) {
                this.agentForm.skills.push(skill);
            }
        },

        /**
         * 移除 Skill
         * @param {number} index - Skill 索引
         */
        removeSkill(index) {
            this.agentForm.skills.splice(index, 1);
        },

        /**
         * 解析 YAML
         * @param {string} yaml - YAML 字符串
         * @returns {Object} 解析后的对象
         */
        parseYaml(yaml) {
            // 简单的 YAML 解析（生产环境应使用 js-yaml 库）
            const lines = yaml.split('\n');
            const result = {};

            for (const line of lines) {
                const match = line.match(/^(\w+):\s*(.+)$/);
                if (match) {
                    const [, key, value] = match;
                    result[key] = value;
                }
            }

            return result;
        },

        /**
         * Agent 对象转 YAML
         * @param {Object} agent - Agent 对象
         * @returns {string} YAML 字符串
         */
        agentToYaml(agent) {
            const lines = ['name:', agent.name];

            if (agent.description) lines.push(`description: ${agent.description}`);
            if (agent.system_prompt) lines.push(`system_prompt: ${agent.system_prompt}`);
            if (agent.llm_name) lines.push(`llm_name: ${agent.llm_name}`);
            if (agent.skills && agent.skills.length > 0) {
                lines.push('skills:');
                for (const skill of agent.skills) {
                    lines.push(`  - ${skill.name}`);
                }
            }

            return lines.join('\n');
        },

        /**
         * 表单对象转 YAML
         * @param {Object} form - 表单对象
         * @returns {string} YAML 字符串
         */
        formToYaml(form) {
            const lines = [];

            if (form.name) lines.push(`name: ${form.name}`);
            if (form.description) lines.push(`description: ${form.description}`);
            if (form.system_prompt) lines.push(`system_prompt: ${form.system_prompt}`);
            if (form.llm_name) lines.push(`llm_name: ${form.llm_name}`);
            if (form.skills && form.skills.length > 0) {
                lines.push('skills:');
                for (const skill of form.skills) {
                    lines.push(`  - ${skill.name}`);
                }
            }

            return lines.join('\n');
        }
    };
}
