// UI Store - UI 状态管理

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

        // ask_user 对话框状态
        askUserDialog: {
            show: false,
            agent_name: '',
            question: '',
            task_id: null,
            session_id: null,
            answer: '',
            submitting: false,
            error: null
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

                console.log('Runtime event received:', { eventType, source, content, payload });

                // 处理不同类型的事件
                if (eventType === 'ASK_USER') {
                    this.handleAskUser(source, content, payload);
                }
            } catch (error) {
                console.error('Failed to handle runtime event:', error);
            }
        },

        /**
         * 处理 ask_user 事件
         * @param {string} agentName - Agent 名称
         * @param {string} question - 问题
         * @param {Object} payload - 事件载荷
         */
        async handleAskUser(agentName, question, payload) {
            console.log('ASK_USER event:', { agentName, question, payload });

            // 如果有 task_id，切换到对应的会话
            if (payload.task_id) {
                // 查找对应的 session
                const targetSession = this.sessions.find(s => s.task_id === payload.task_id);
                if (targetSession && this.currentSession?.task_id !== payload.task_id) {
                    await this.selectSession(targetSession);
                }
            }

            // 显示 ask_user 对话框
            this.askUserDialog = {
                show: true,
                agent_name: agentName,
                question: question,
                task_id: payload.task_id || null,
                session_id: payload.session_id || null,
                answer: '',
                submitting: false,
                error: null
            };
        },

        /**
         * 提交用户回答
         */
        async submitUserAnswer() {
            if (!this.askUserDialog.answer.trim()) {
                this.askUserDialog.error = 'Please enter your answer';
                return;
            }

            this.askUserDialog.submitting = true;
            this.askUserDialog.error = null;

            try {
                await API.submitUserInput(this.askUserDialog.agent_name, {
                    question: this.askUserDialog.question,
                    answer: this.askUserDialog.answer
                });

                // 关闭对话框
                this.closeAskUserDialog();
            } catch (error) {
                console.error('Failed to submit user answer:', error);
                this.askUserDialog.error = error.message;
            } finally {
                this.askUserDialog.submitting = false;
            }
        },

        /**
         * 关闭 ask_user 对话框
         */
        closeAskUserDialog() {
            this.askUserDialog = {
                show: false,
                agent_name: '',
                question: '',
                task_id: null,
                session_id: null,
                answer: '',
                submitting: false,
                error: null
            };
        },

        /**
         * 检查并开始状态轮询
         */
        checkAndStartStatusPolling() {
            // 停止之前的轮询
            this.stopAgentStatusPolling();

            if (!this.currentSession || !this.currentSessionEmails.length) {
                return;
            }

            const lastEmail = this.currentSessionEmails[this.currentSessionEmails.length - 1];

            // 只有最后一封邮件是用户发出的，才需要轮询
            if (lastEmail.sender === 'User') {
                const targetAgent = lastEmail.recipient || this.currentSession.name;
                this.startAgentStatusPolling(targetAgent);
            }
        },

        /**
         * 开始 Agent 状态轮询
         * @param {string} agentName - Agent 名称
         */
        startAgentStatusPolling(agentName) {
            this.agentStatusPolling = true;
            this.agentStatusTarget = agentName;

            // 立即获取一次状态
            this.fetchAgentStatus();

            // 设置轮询
            this.pollingInterval = setInterval(() => {
                this.fetchAgentStatus();
            }, 2000);  // 每 2 秒轮询一次
        },

        /**
         * 停止 Agent 状态轮询
         */
        stopAgentStatusPolling() {
            this.agentStatusPolling = false;
            this.agentStatusTarget = '';
            this.agentStatusHistory = [];
            this.agentStatusError = null;

            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
                this.pollingInterval = null;
            }
        },

        /**
         * 获取 Agent 状态
         */
        async fetchAgentStatus() {
            if (!this.agentStatusTarget) return;

            try {
                const response = await fetch(`/api/agents/${this.agentStatusTarget}/status`);
                const data = await response.json();

                if (data.success) {
                    // 更新状态历史
                    this.agentStatusHistory = [
                        {
                            message: data.message,
                            timestamp: data.timestamp
                        }
                    ];
                    this.agentStatusError = null;
                }
            } catch (error) {
                console.error('Failed to fetch agent status:', error);
                this.agentStatusError = error.message;
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
