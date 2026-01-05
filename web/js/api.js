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
        return this.request('/api/config/status');
    },

    async saveLLMConfig(config) {
        return this.request('/api/config/llm', {
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

    async sendEmail(sessionId, emailData) {
        return this.request(`/api/sessions/${sessionId}/emails`, {
            method: 'POST',
            body: JSON.stringify(emailData)
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
    }
};
