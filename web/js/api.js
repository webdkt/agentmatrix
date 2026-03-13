// API utility functions for AgentMatrix

const API = {
    baseURL: '',

    async request(url, options = {}) {
        try {
            const response = await fetch(this.baseURL + url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    },

    // Config APIs
    async getConfigStatus() {
        return this.request('/api/config');
    },

    async saveLLMConfig(config) {
        return this.request('/api/config/llm', {
            method: 'POST',
            body: JSON.stringify(config)
        });
    },

    async completeColdStart(config) {
        return this.request('/api/config/complete', {
            method: 'POST',
            body: JSON.stringify(config)
        });
    },

    // Session APIs
    async getSessions() {
        return this.request('/api/sessions');
    },

    async getSession(sessionId) {
        return this.request(`/api/sessions/${sessionId}`);
    },

    async createSession(data) {
        return this.request('/api/sessions', {
            method: 'POST',
            body: JSON.stringify(data)
        });
    },

    async sendEmail(sessionId, emailData, files = []) {
        console.log('📤 Sending email' + (files && files.length > 0 ? ` with ${files.length} attachment(s)` : ' without attachments'));
        
        // 始终使用 FormData（服务器端现在只接受 FormData）
        const formData = new FormData();
        // 字段顺序必须与服务器端参数顺序一致
        formData.append('recipient', emailData.recipient);
        formData.append('subject', emailData.subject || '');
        formData.append('body', emailData.body);
        
        if (emailData.user_session_id) {
            formData.append('user_session_id', emailData.user_session_id);
        }
        if (emailData.in_reply_to) {
            formData.append('in_reply_to', emailData.in_reply_to);
        }
        
        // 添加所有文件
        if (files && files.length > 0) {
            files.forEach((file, index) => {
                console.log(`📎 Adding file ${index + 1}:`, file.name, file.size, 'bytes');
                formData.append('attachments', file);
            });
        }

        console.log('📤 Sending request...');

        try {
            const response = await fetch(this.baseURL + `/api/sessions/${sessionId}/emails`, {
                method: 'POST',
                body: formData
                // 注意：不要设置 Content-Type，让浏览器自动设置
            });

            console.log('📤 Response status:', response.status);

            if (!response.ok) {
                // 尝试读取错误详情
                let errorDetail = '';
                try {
                    const errorData = await response.json();
                    console.error('❌ API error response:', errorData);
                    
                    // FastAPI 验证错误通常是数组
                    if (Array.isArray(errorData.detail)) {
                        errorDetail = errorData.detail.map(err => {
                            return `${err.loc?.join('.') || 'field'}: ${err.msg}`;
                        }).join('; ');
                    } else {
                        errorDetail = errorData.detail || JSON.stringify(errorData);
                    }
                } catch (e) {
                    errorDetail = await response.text();
                }
                console.error('❌ API error details:', errorDetail);
                console.error('❌ FormData contents:');
                for (let [key, value] of formData.entries()) {
                    if (value instanceof File) {
                        console.log(`  - ${key}: ${value.name} (${value.size} bytes)`);
                    } else {
                        console.log(`  - ${key}: ${value}`);
                    }
                }
                throw new Error(`HTTP error! status: ${response.status}, detail: ${errorDetail}`);
            }

            const result = await response.json();
            console.log('✅ Email sent successfully:', result);
            return result;
        } catch (error) {
            console.error('❌ API request failed:', error);
            throw error;
        }
    },

    async submitUserInput(agentName, inputData) {
        console.log('💬 Submitting user input to', agentName);
        
        return this.request(`/api/agents/${agentName}/submit_user_input`, {
            method: 'POST',
            body: JSON.stringify(inputData)
        });
    },

        async getSessionEmails(sessionId) {
        return this.request(`/api/sessions/${sessionId}/emails`);
    },

    // Agent APIs
    async getAgents() {
        return this.request('/api/agents');
    },

    async getAgent(agentName) {
        return this.request(`/api/agents/${agentName}`);
    },

    // File APIs
    async getFiles(path = '') {
        return this.request(`/api/files?path=${encodeURIComponent(path)}`);
    },

    // System APIs
    async getSystemStatus() {
        return this.request('/api/system/status');
    },

    // Runtime APIs
    async getRuntimeStatus() {
        return this.request('/api/runtime/status');
    },

    // Skills APIs
    async getAvailableSkills() {
        return this.request('/api/skills');
    },

    // Agent Profile Management APIs
    async getAgentProfiles() {
        return this.request('/api/agent-profiles');
    },

    async getAgentProfile(agentName) {
        return this.request(`/api/agent-profiles/${agentName}`);
    },

    async createAgentProfile(agentData) {
        return this.request('/api/agent-profiles', {
            method: 'POST',
            body: JSON.stringify(agentData)
        });
    },

    async updateAgentProfile(agentName, agentData) {
        return this.request(`/api/agent-profiles/${agentName}`, {
            method: 'PUT',
            body: JSON.stringify(agentData)
        });
    },

    async deleteAgentProfile(agentName) {
        return this.request(`/api/agent-profiles/${agentName}`, {
            method: 'DELETE'
        });
    },

    async reloadAgentProfile(agentName) {
        return this.request(`/api/agent-profiles/${agentName}/reload`);
    },

    // LLM Configuration APIs
    async getLLMConfigs() {
        return this.request('/api/llm-configs');
    },

    async getLLMConfig(configName) {
        return this.request(`/api/llm-configs/${configName}`);
    },

    async createLLMConfig(configData) {
        return this.request('/api/llm-configs', {
            method: 'POST',
            body: JSON.stringify(configData)
        });
    },

    async updateLLMConfig(configName, configData) {
        return this.request(`/api/llm-configs/${configName}`, {
            method: 'PUT',
            body: JSON.stringify(configData)
        });
    },

    async deleteLLMConfig(configName) {
        return this.request(`/api/llm-configs/${configName}`, {
            method: 'DELETE'
        });
    },

    async resetLLMConfig(configName) {
        return this.request(`/api/llm-configs/${configName}/reset`, {
            method: 'POST'
        });
    }
};
