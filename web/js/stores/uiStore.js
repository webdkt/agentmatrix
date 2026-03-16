// UI Store - UI 状态管理（优化版）

/**
 * UI Store: 管理 UI 交互状态
 */
function useUiStore() {
    return {
        // ========== 状态 ==========
        // 当前标签页
        currentTab: 'master',

        // 应用状态
        isColdStart: false,
        isLoading: true,
        runtimeError: null,
        runtimeStatus: null,

        // 面板尺寸调整
        leftPanelWidth: 280,
        rightPanelWidth: 280,
        isResizing: false,
        resizingEdge: null,
        startX: 0,
        startLeftWidth: 0,
        startRightWidth: 0,

        // ask_user 对话框状态（🆕 改为 Map，每个 session 一个）
        askUserDialogs: {},  // { session_id: { show, agent_name, question, answer, submitting, error } }

        // ========== askUserDialog 辅助方法 ==========
        
        /**
         * 获取当前会话的 ask_user 对话框状态
         * @returns {Object|null} 对话框状态
         */
        getCurrentAskUserDialog() {
            if (!this.currentSession) return null;
            return this.askUserDialogs[this.currentSession.session_id] || null;
        },
        
        /**
         * 获取当前会话的答案（用于 x-model）
         * @returns {string}
         */
        getAskUserAnswer() {
            const dialog = this.getCurrentAskUserDialog();
            return dialog ? dialog.answer : '';
        },
        
        /**
         * 设置当前会话的答案（用于 x-model）
         * @param {string} value
         */
        setAskUserAnswer(value) {
            if (!this.currentSession) return;
            const sessionId = this.currentSession.session_id;
            if (!this.askUserDialogs[sessionId]) {
                this.askUserDialogs[sessionId] = {};
            }
            this.askUserDialogs[sessionId].answer = value;
        },
        
        /**
         * 检查当前会话是否有 ask_user 对话框显示
         * @returns {boolean}
         */
        hasAskUserDialog() {
            const dialog = this.getCurrentAskUserDialog();
            return dialog && dialog.show;
        },

        // 🆕 系统状态缓存（从 WebSocket 广播接收）
        systemStatus: {
            timestamp: null,
            agents: {}  // 每个 agent 包含: {status, pending_question, current_session_id, current_task_id, current_user_session_id, status_history}
        },

        // ========== 方法 ==========

        /**
         * 切换标签页
         * @param {string} tabName - 标签页名称
         */
        switchTab(tabName) {
            this.currentTab = tabName;
        },

        /**
         * 开始调整面板大小
         * @param {string} edge - 边缘 ('left' | 'right')
         * @param {MouseEvent} event - 鼠标事件
         */
        startResize(edge, event) {
            this.isResizing = true;
            this.resizingEdge = edge;
            this.startX = event.clientX;
            this.startLeftWidth = this.leftPanelWidth;
            this.startRightWidth = this.rightPanelWidth;

            // 添加全局事件监听
            document.addEventListener('mousemove', this.onResize);
            document.addEventListener('mouseup', this.stopResize);
        },

        /**
         * 调整面板大小中
         * @param {MouseEvent} event - 鼠标事件
         */
        onResize(event) {
            if (!this.isResizing) return;

            const deltaX = event.clientX - this.startX;

            if (this.resizingEdge === 'left') {
                // 调整左面板
                this.leftPanelWidth = Math.max(200, Math.min(600, this.startLeftWidth + deltaX));
            } else if (this.resizingEdge === 'right') {
                // 调整右面板
                this.rightPanelWidth = Math.max(200, Math.min(600, this.startRightWidth - deltaX));
            }
        },

        /**
         * 停止调整面板大小
         */
        stopResize() {
            this.isResizing = false;
            this.resizingEdge = null;

            // 移除全局事件监听
            document.removeEventListener('mousemove', this.onResize);
            document.removeEventListener('mouseup', this.stopResize);
        },

        /**
         * 处理 Runtime Event
         * @param {string} eventData - 事件数据
         */
        async handleRuntimeEvent(eventData) {
            try {
                // eventData 是字符串，需要解析 AgentEvent
                // 格式: "AgentEvent(event_type='...', source='...', ...)"
                const eventMatch = eventData.match(/AgentEvent\(([^)]+)\)/);
                if (!eventMatch) {
                    console.warn('Invalid runtime event format:', eventData);
                    return;
                }

                // 解析事件属性
                const eventStr = eventMatch[1];
                const eventTypeMatch = eventStr.match(/event_type='([^']*)'/);
                const sourceMatch = eventStr.match(/source='([^']*)'/);
                const contentMatch = eventStr.match(/content='([^']*)'/);
                const payloadMatch = eventStr.match(/payload=({[^}]*})/);

                if (!eventTypeMatch || !sourceMatch || !contentMatch) {
                    console.warn('Failed to parse event:', eventData);
                    return;
                }

                const eventType = eventTypeMatch[1];
                const source = sourceMatch[1];
                const content = contentMatch[1];

                // 解析 payload（如果是字典格式）
                let payload = {};
                if (payloadMatch) {
                    try {
                        // 移除单引号，替换为双引号，解析 JSON
                        const payloadStr = payloadMatch[1]
                            .replace(/'/g, '"')
                            .replace(/True/g, 'true')
                            .replace(/False/g, 'false')
                            .replace(/None/g, 'null');
                        payload = JSON.parse(payloadStr);
                    } catch (e) {
                        console.warn('Failed to parse payload:', payloadMatch[1]);
                    }
                }

                // 处理不同类型的事件
                if (eventType === 'ASK_USER') {
                    this.handleAskUser(source, content, payload);
                } else if (eventType === 'SYSTEM_STATUS') {
                    this.handleSystemStatus(payload);
                }
            } catch (error) {
                console.error('Failed to handle runtime event:', error);
            }
        },

        /**
         * 处理 ask_user 事件（🆕 改为在对应 session 显示）
         * @param {string} agentName - Agent 名称
         * @param {string} question - 问题
         * @param {Object} payload - 事件载荷
         */
        async handleAskUser(agentName, question, payload) {
            console.log('ASK_USER event:', { agentName, question, payload });

            // 🆕 获取 target session_id
            const targetSessionId = payload.session_id;
            if (!targetSessionId) {
                console.warn('ASK_USER event missing session_id');
                return;
            }

            // 🆕 在对应的 session 显示对话框
            this.askUserDialogs[targetSessionId] = {
                show: true,
                agent_name: agentName,
                question: question,
                task_id: payload.task_id || null,
                session_id: targetSessionId,
                answer: '',
                submitting: false,
                error: null
            };

            console.log(`💬 在 session ${targetSessionId.slice(0, 8)} 显示 ask_user 对话框`);
        },

        /**
         * 提交用户回答（🆕 指定 session_id）
         */
        async submitUserAnswer(sessionId) {
            const dialog = this.askUserDialogs[sessionId];
            if (!dialog || !dialog.answer.trim()) {
                if (dialog) {
                    dialog.error = 'Please enter your answer';
                }
                return;
            }

            dialog.submitting = true;
            dialog.error = null;

            try {
                await API.submitUserInput(dialog.agent_name, {
                    question: dialog.question,
                    answer: dialog.answer
                });

                // 关闭对话框
                this.closeAskUserDialog(sessionId);
            } catch (error) {
                console.error('Failed to submit user answer:', error);
                dialog.error = error.message;
            } finally {
                dialog.submitting = false;
            }
        },

        /**
         * 关闭 ask_user 对话框（🆕 指定 session_id）
         */
        closeAskUserDialog(sessionId) {
            if (this.askUserDialogs[sessionId]) {
                this.askUserDialogs[sessionId].show = false;
                this.askUserDialogs[sessionId].answer = '';
                this.askUserDialogs[sessionId].error = null;
            }
        },

        /**
         * 🆕 处理 SYSTEM_STATUS 事件（状态广播）
         * @param {Object} payload - 事件载荷
         */
        handleSystemStatus(payload) {
            if (!payload || !payload.status) {
                console.warn('Invalid SYSTEM_STATUS payload:', payload);
                return;
            }

            const status = payload.status;

            // 更新系统状态缓存
            this.systemStatus = {
                timestamp: status.timestamp,
                agents: status.agents || {}
            };

            console.log('📊 System status updated:', this.systemStatus);

            // 🆕 检查是否有 Agent 在等待用户输入（会在对应 session 显示）
            this.checkForWaitingUser();
        },

        /**
         * 🆕 检查是否有 Agent 在等待用户输入
         */
        checkForWaitingUser() {
            console.log('🔍 checkForWaitingUser called');
            console.log('📊 systemStatus.agents:', this.systemStatus.agents);
            console.log('📊 askUserDialogs before check:', this.askUserDialogs);
            
            for (const [agentName, agentInfo] of Object.entries(this.systemStatus.agents)) {
                console.log(`🔍 Checking agent ${agentName}:`, {
                    has_pending: !!agentInfo.pending_question,
                    has_user_session: !!agentInfo.current_user_session_id,
                    pending_question: agentInfo.pending_question,
                    user_session_id: agentInfo.current_user_session_id
                });
                
                if (agentInfo.pending_question && agentInfo.current_user_session_id) {
                    const sessionId = agentInfo.current_user_session_id;
                    console.log(`🔔 Agent ${agentName} 在 session ${sessionId.slice(0, 8)} 等待用户输入`);
                    console.log(`📊 Current dialog state for ${sessionId.slice(0, 8)}:`, this.askUserDialogs[sessionId]);

                    // 如果对话框未显示，显示对话框
                    if (!this.askUserDialogs[sessionId] || !this.askUserDialogs[sessionId].show) {
                        console.log(`✅ 显示对话框 for session ${sessionId.slice(0, 8)}`);
                        const payload = {
                            agent_name: agentName,
                            task_id: agentInfo.current_task_id,
                            session_id: sessionId
                        };
                        this.handleAskUser(agentName, agentInfo.pending_question, payload);
                    } else {
                        console.log(`⚠️ 对话框已存在 for session ${sessionId.slice(0, 8)}`);
                    }
                }
            }
            
            console.log('📊 askUserDialogs after check:', this.askUserDialogs);
        },

        /**
         * 🆕 处理 Agent 状态增量更新
         * @param {Object} payload - 事件载荷
         */
        handleAgentStatusUpdate(payload) {
            console.log('🔍 handleAgentStatusUpdate called:', payload);
            const { agent_name, data } = payload;

            if (!agent_name || !data) {
                console.warn('Invalid AGENT_STATUS_UPDATE payload:', payload);
                return;
            }

            console.log(`📊 Processing update for ${agent_name}:`, {
                status: data.status,
                pending_question: data.pending_question,
                current_user_session_id: data.current_user_session_id,
                current_session_id: data.current_session_id
            });

            // 🔧 确保该 Agent 存在
            if (!this.systemStatus.agents[agent_name]) {
                this.systemStatus.agents[agent_name] = {};
            }

            // 🔧 合并更新（data 的结构和 systemStatus.agents[agent_name] 完全一样）
            Object.assign(this.systemStatus.agents[agent_name], data);

            console.log(`✅ Agent ${agent_name} status updated in systemStatus`);
            console.log('📊 Current systemStatus.agents:', this.systemStatus.agents);

            // 🔧 同样的逻辑：检查是否等待用户输入
            this.checkForWaitingUser();
        },

        /**
         * 🆕 获取 Agent 的状态显示文案
         * @param {string} agentName - Agent 名称
         * @param {string} sessionId - 会话 ID
         * @returns {Object} { text, status }
         */
        getAgentStatusDisplay(agentName, sessionId) {
            if (!this.systemStatus.agents || !this.systemStatus.agents[agentName]) {
                return {
                    text: 'Agent 未知',
                    status: 'unknown'
                };
            }

            const agentInfo = this.systemStatus.agents[agentName];

            // Agent 空闲
            if (agentInfo.status === 'IDLE') {
                return {
                    text: '空闲',
                    status: 'idle'
                };
            }

            // Agent 正在为当前会话工作
            if (agentInfo.current_user_session_id === sessionId) {
                const statusMap = {
                    'THINKING': '正在思考...',
                    'WORKING': '正在工作...',
                    'WAITING_FOR_USER': '等待你的回答'
                };
                return {
                    text: statusMap[agentInfo.status] || agentInfo.status,
                    status: agentInfo.status.toLowerCase()
                };
            }

            // Agent 正在为其他会话工作
            const statusMap = {
                'THINKING': '正在为其他会话思考',
                'WORKING': '正在为其他会话工作',
                'WAITING_FOR_USER': '正在为其他会话等待用户回答'
            };
            return {
                text: statusMap[agentInfo.status] || `${agentInfo.status} (其他会话)`,
                status: 'busy-on-other'
            };
        },

        /**
         * 🆕 获取 Agent 的状态历史
         * @param {string} agentName - Agent 名称
         * @returns {Array} 状态历史
         */
        getAgentStatusHistory(agentName) {
            if (!this.systemStatus.agents || !this.systemStatus.agents[agentName]) {
                return [];
            }
            return this.systemStatus.agents[agentName].status_history || [];
        },

        /**
         * 🆕 格式化状态时间戳
         * @param {string} timestamp - ISO 时间戳
         * @returns {string} 格式化的时间
         */
        formatStatusTime(timestamp) {
            if (!timestamp) return '';
            try {
                const date = new Date(timestamp);
                return date.toLocaleTimeString('zh-CN', { hour12: false });
            } catch (e) {
                return '';
            }
        },

        /**
         * 初始化应用
         */
        async init() {
            // 绑定 resize 方法以保持 'this' 上下文
            this.onResize = this.onResize.bind(this);
            this.stopResize = this.stopResize.bind(this);

            try {
                // 检查是否是冷启动并获取配置
                const status = await API.getConfigStatus();
                this.isColdStart = !status.configured;
                this.user_agent_name = status.user_agent_name || 'User';
                this.isLoading = false;

                if (!this.isColdStart) {
                    // 检查运行时状态
                    const runtimeStatus = await API.getRuntimeStatus();
                    this.runtimeStatus = runtimeStatus;

                    // 加载配置数据
                    await Promise.all([
                        this.loadSessions(),
                        this.loadAgents(),
                        this.loadLLMConfigs()
                    ]);

                    // 连接 WebSocket
                    wsClient.connect();

                    // 如果有会话，自动选择第一个
                    if (this.sessions.length > 0) {
                        await this.selectSession(this.sessions[0]);
                    }
                }
            } catch (error) {
                console.error('Failed to initialize app:', error);
                this.runtimeError = error.message;
                this.isLoading = false;
            }
        }
    };
}
