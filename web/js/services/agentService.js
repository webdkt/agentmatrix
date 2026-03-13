// Agent Service - Agent 业务逻辑

import { API } from '../api.js';

/**
 * Agent Service: 封装 Agent 相关的业务逻辑
 */
export class AgentService {
    constructor() {
        this.api = API;
    }

    /**
     * 获取所有 Agent
     * @returns {Promise<Array>} Agent 列表
     */
    async getAgents() {
        try {
            const agentsData = await this.api.getAgents();
            return agentsData.agents || [];
        } catch (error) {
            console.error('Failed to get agents:', error);
            throw error;
        }
    }

    /**
     * 获取 Agent 详情
     * @param {string} agentName - Agent 名称
     * @returns {Promise<Object>} Agent 对象
     */
    async getAgent(agentName) {
        try {
            const agents = await this.getAgents();
            return agents.find(a => a.name === agentName) || null;
        } catch (error) {
            console.error('Failed to get agent:', error);
            throw error;
        }
    }

    /**
     * 创建 Agent
     * @param {Object} agentData - Agent 数据
     * @returns {Promise} 创建结果
     */
    async createAgent(agentData) {
        try {
            return await this.api.createAgent(agentData);
        } catch (error) {
            console.error('Failed to create agent:', error);
            throw error;
        }
    }

    /**
     * 更新 Agent
     * @param {string} agentName - Agent 名称
     * @param {Object} agentData - Agent 数据
     * @returns {Promise} 更新结果
     */
    async updateAgent(agentName, agentData) {
        try {
            return await this.api.updateAgentProfile(agentName, agentData);
        } catch (error) {
            console.error('Failed to update agent:', error);
            throw error;
        }
    }

    /**
     * 删除 Agent
     * @param {string} agentName - Agent 名称
     * @returns {Promise} 删除结果
     */
    async deleteAgent(agentName) {
        try {
            return await this.api.deleteAgent(agentName);
        } catch (error) {
            console.error('Failed to delete agent:', error);
            throw error;
        }
    }

    /**
     * 验证 Agent 数据
     * @param {Object} agentData - Agent 数据
     * @param {boolean} isEdit - 是否为编辑模式
     * @returns {Object} 验证结果 {valid: boolean, errors: Object}
     */
    validateAgentData(agentData, isEdit = false) {
        const errors = {};

        // 创建模式下，名称必填
        if (!isEdit && (!agentData.name || !agentData.name.trim())) {
            errors.name = 'Agent 名称不能为空';
        }

        // 名称格式验证
        if (!isEdit && agentData.name && !/^[a-zA-Z0-9_]+$/.test(agentData.name)) {
            errors.name = 'Agent 名称只能包含字母、数字和下划线';
        }

        // 描述验证
        if (agentData.description !== undefined && !agentData.description.trim()) {
            errors.description = 'Agent 描述不能为空';
        }

        // System prompt 验证
        if (agentData.system_prompt !== undefined && !agentData.system_prompt.trim()) {
            errors.system_prompt = 'System prompt 不能为空';
        }

        // LLM 名称验证
        if (agentData.llm_name !== undefined && !agentData.llm_name.trim()) {
            errors.llm_name = 'LLM 配置不能为空';
        }

        return {
            valid: Object.keys(errors).length === 0,
            errors
        };
    }

    /**
     * 解析 YAML 为 Agent 对象
     * @param {string} yaml - YAML 字符串
     * @returns {Object} Agent 对象
     */
    parseYaml(yaml) {
        // 简单的 YAML 解析（生产环境应使用 js-yaml 库）
        const lines = yaml.split('\n');
        const result = {};
        let currentKey = null;
        let inList = false;
        const listItems = [];

        for (const line of lines) {
            const trimmed = line.trim();

            // 跳过空行和注释
            if (!trimmed || trimmed.startsWith('#')) {
                continue;
            }

            // 列表项
            if (trimmed.startsWith('- ')) {
                inList = true;
                const value = trimmed.substring(2);
                listItems.push(value);
                continue;
            }

            // 如果之前在列表中，现在结束了
            if (inList) {
                result[currentKey] = listItems;
                inList = false;
                listItems.length = 0;
            }

            // 键值对
            const match = trimmed.match(/^(\w+):\s*(.+)$/);
            if (match) {
                currentKey = match[1];
                const value = match[2];

                // 尝试解析为布尔值或数字
                if (value === 'true') {
                    result[currentKey] = true;
                } else if (value === 'false') {
                    result[currentKey] = false;
                } else if (value === 'null') {
                    result[currentKey] = null;
                } else if (!isNaN(value)) {
                    result[currentKey] = Number(value);
                } else {
                    result[currentKey] = value;
                }
            }
        }

        // 处理最后的列表
        if (inList && currentKey) {
            result[currentKey] = listItems;
        }

        return result;
    }

    /**
     * Agent 对象转 YAML
     * @param {Object} agent - Agent 对象
     * @returns {string} YAML 字符串
     */
    agentToYaml(agent) {
        const lines = [];

        // 基本字段
        if (agent.name) lines.push(`name: ${agent.name}`);
        if (agent.description) lines.push(`description: ${agent.description}`);
        if (agent.system_prompt) lines.push(`system_prompt: ${agent.system_prompt}`);
        if (agent.llm_name) lines.push(`llm_name: ${agent.llm_name}`);

        // Skills 列表
        if (agent.skills && agent.skills.length > 0) {
            lines.push('skills:');
            for (const skill of agent.skills) {
                if (typeof skill === 'string') {
                    lines.push(`  - ${skill}`);
                } else if (skill.name) {
                    lines.push(`  - ${skill.name}`);
                }
            }
        }

        // 其他字段
        for (const [key, value] of Object.entries(agent)) {
            if (!['name', 'description', 'system_prompt', 'llm_name', 'skills'].includes(key)) {
                if (Array.isArray(value)) {
                    lines.push(`${key}:`);
                    for (const item of value) {
                        lines.push(`  - ${item}`);
                    });
                } else if (typeof value === 'boolean') {
                    lines.push(`${key}: ${value}`);
                } else if (value !== null && value !== undefined) {
                    lines.push(`${key}: ${value}`);
                }
            }
        }

        return lines.join('\n');
    }

    /**
     * 获取所有可用 Skills
     * @returns {Promise<Array>} Skills 列表
     */
    async getSkills() {
        try {
            const data = await this.api.getSkills();
            return data.skills || [];
        } catch (error) {
            console.error('Failed to get skills:', error);
            throw error;
        }
    }

    /**
     * 搜索 Skills
     * @param {Array} skills - Skills 列表
     * @param {string} query - 搜索关键词
     * @returns {Array} 匹配的 Skills
     */
    searchSkills(skills, query) {
        if (!query || !query.trim()) {
            return skills;
        }

        const lowerQuery = query.toLowerCase();
        return skills.filter(skill =>
            skill.name.toLowerCase().includes(lowerQuery) ||
            (skill.description && skill.description.toLowerCase().includes(lowerQuery))
        );
    }

    /**
     * 格式化 Agent 用于显示
     * @param {Object} agent - Agent 对象
     * @returns {Object} 格式化后的 Agent 对象
     */
    formatAgentForDisplay(agent) {
        return {
            ...agent,
            displayName: agent.name,
            displayDescription: agent.description || '暂无描述',
            skillCount: agent.skills ? agent.skills.length : 0,
            llmName: agent.llm_name || '默认'
        };
    }

    /**
     * 获取 Agent 描述
     * @param {Array} agents - Agent 列表
     * @param {string} agentName - Agent 名称
     * @returns {string} Agent 描述
     */
    getAgentDescription(agents, agentName) {
        const agent = agents.find(a => a.name === agentName);
        return agent?.description || '';
    }
}
