// Main application logic for AgentMatrix

function app() {
    return {
        // Application state
        currentTab: 'master',
        isColdStart: false,
        isLoading: true,
        runtimeError: null,
        runtimeStatus: null,
        sessions: [],
        currentSession: null,
        currentSessionEmails: [],
        agents: [],
        files: [],
        user_agent_name: 'User',  // Store user agent name dynamically

        // Panel resizing state
        leftPanelWidth: 280,
        rightPanelWidth: 280,
        isResizing: false,
        resizingEdge: null,
        startX: 0,
        startLeftWidth: 0,
        startRightWidth: 0,

        // New email modal state
        showNewEmailModal: false,
        isSendingEmail: false,
        agentSearchQuery: '',
        showAgentDropdown: false,
        newEmail: {
            recipient: '',
            body: '',
            attachments: []  // 存储附件文件
        },

        // Reply state - 使用 Map 存储每个邮件的回复状态
        replyStates: {},

        // File panel state
        showFilePanel: true,

        // Quick reply state
        quickReplyBody: '',

        // New email popup state
        newEmailPopup: null,
        
        // ask_user 对话框状态
        askUserDialog: {
            show: false,
            agent_name: '',
            question: '',
            user_session_id: null,
            answer: '',
            submitting: false,
            error: null
        },
        
        // Agent 状态轮询
        agentStatusPolling: false,  // 是否正在轮询
        agentStatusTarget: '',      // 目标 Agent 名称
        agentStatusHistory: [],     // 状态历史（最近 3 条）
        agentStatusError: null,     // 错误信息

        // Settings state
        settingsView: 'main',  // 'main', 'agents', 'llm'
        agentProfiles: [],
        
        // Agent Modal state
        showAgentModal: false,
        editingAgent: null,
        agentEditMode: 'simple',  // 'simple' 或 'advanced'
        isSavingAgent: false,
        agentFormErrors: {},
        newSkill: '',
        agentForm: {
            name: '',
            description: '',
            module: 'agentmatrix.agents.base',
            class_name: 'BaseAgent',
            backend_model: 'default_llm',
            skills: [],
            personaBase: '',  // persona.base - 核心身份定义
            cerebellumModel: '',  // cerebellum.backend_model - 小脑模型
            visionBrainModel: ''  // vision_brain.backend_model - 视觉模型
        },
        // Advanced mode: raw YAML editing
        agentRawYaml: '',
        
        // Skill search modal
        showSkillSearchModal: false,
        availableSkills: [],  // 系统可用的所有 skills
        skillSearchQuery: '',
        
        showDeleteConfirmModal: false,
        agentToDelete: null,
        isDeletingAgent: false,
        showAdvancedConfig: false,  // 控制高级配置折叠面板

        // LLM Config state
        llmConfigs: [],
        showLLMModal: false,
        editingLLMConfig: null,
        isSavingLLM: false,
        showLLMApiKey: false,
        llmFormErrors: {},
        llmForm: {
            name: '',
            url: '',
            api_key: '',
            model_name: ''
        },
        showDeleteLLMConfirmModal: false,
        llmToDelete: null,
        isDeletingLLM: false,

        // Computed property for filtered agents
        get filteredAgents() {
            if (!this.agentSearchQuery) {
                return this.agents;
            }
            return this.agents.filter(agent =>
                agent.name.toLowerCase().includes(this.agentSearchQuery.toLowerCase())
            );
        },

        // 附件管理函数
        addAttachments(files) {
            console.log('➕ addAttachments called with', files.length, 'files');
            console.log('➕ Current attachments count:', this.newEmail.attachments.length);
            
            if (!files || files.length === 0) return;
            
            for (let file of files) {
                // 检查是否已存在同名文件
                const exists = this.newEmail.attachments.some(f => f.name === file.name);
                if (!exists) {
                    console.log('➕ Adding file:', file.name, file.size, 'bytes');
                    this.newEmail.attachments.push(file);
                } else {
                    console.log('⚠️ File already exists:', file.name);
                }
            }
            
            console.log('➕ New attachments count:', this.newEmail.attachments.length);
        },
        
        removeAttachment(index) {
            this.newEmail.attachments.splice(index, 1);
        },
        
        handleFileSelect(event) {
            console.log('📁 handleFileSelect called');
            const files = event.target.files;
            console.log('📁 Files selected:', files.length, files);
            this.addAttachments(files);
            // 清空 input 以允许再次选择相同文件
            event.target.value = '';
        },
        
        handleFileDrop(event) {
            event.preventDefault();
            const files = event.dataTransfer.files;
            this.addAttachments(files);
        },
        
        handleFileDragOver(event) {
            event.preventDefault();
        },
        
        formatFileSize(bytes) {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        },

        // Initialize application
        async init() {
            // Bind resize methods to maintain 'this' context when called by window events
            this.onResize = this.onResize.bind(this);
            this.stopResize = this.stopResize.bind(this);

            try {
                // Check if this is a cold start and get config
                const status = await API.getConfigStatus();
                this.isColdStart = !status.configured;
                this.user_agent_name = status.user_agent_name || 'User';  // Load user agent name
                this.isLoading = false;

                if (!this.isColdStart) {
                    // Check runtime status
                    const runtimeStatus = await API.getRuntimeStatus();
                    this.runtimeStatus = runtimeStatus;

                    if (!runtimeStatus.initialized) {
                        this.runtimeError = 'AgentMatrix runtime 未能初始化，请检查服务器日志';
                        console.error('Runtime not initialized');
                        return;
                    }

                    if (!runtimeStatus.running) {
                        this.runtimeError = 'AgentMatrix runtime 运行异常，请检查服务器日志';
                        console.error('Runtime not running properly');
                        return;
                    }

                    // Update agents from runtime (convert Proxy to Array and filter out User)
                    if (runtimeStatus.agents && runtimeStatus.agents.length > 0) {
                        const rawAgents = [...runtimeStatus.agents];
                        console.log('Raw agents:', rawAgents, 'Type:', Array.isArray(rawAgents));
                        const filtered = rawAgents.filter(a => a !== this.user_agent_name);
                        console.log('Filtered agents:', filtered, 'Length:', filtered.length);
                        this.agents = filtered;
                    } else {
                        console.log('No agents found in runtimeStatus');
                    }

                    // Initialize WebSocket connection
                    initWebSocket();

                    // Set up WebSocket event handlers
                    if (typeof wsClient !== 'undefined' && wsClient) {
                        // Listen for new emails
                        wsClient.on('message', (data) => {
                            if (data.type === 'new_email') {
                                this.handleNewEmail(data.data);
                            } else if (data.type === 'runtime_event') {
                                this.handleRuntimeEvent(data.data);
                            }
                        });
                    }

                    await this.loadInitialData();
                }
            } catch (error) {
                console.error('Failed to initialize application:', error);
                this.runtimeError = `初始化失败: ${error.message}`;
                this.isLoading = false;
            }
        },

        // Load initial data
        async loadInitialData() {
            try {
                await this.loadSessions();

                // Load agents with their details (including description/role)
                await this.loadAgents();

                // Load files
                const filesData = await API.getFiles();
                this.files = filesData.files || [];
            } catch (error) {
                console.error('Failed to load initial data:', error);
            }
        },

        // Load agents with details
        async loadAgents() {
            try {
                const agentsData = await API.getAgents();
                this.agents = agentsData.agents || [];
                console.log('Loaded agents:', this.agents);
            } catch (error) {
                console.error('Failed to load agents:', error);
            }
        },

        // Get agent description by name
        getAgentDescription(agentName) {
            const agent = this.agents.find(a => a.name === agentName);
            return agent?.description || '';
        },

        // Load sessions
        async loadSessions() {
            try {
                const sessionsData = await API.getSessions();
                this.sessions = sessionsData.sessions || [];
            } catch (error) {
                console.error('Failed to load sessions:', error);
                throw error;
            }
        },

        // Handle new email received via WebSocket
        async handleNewEmail(emailData) {
        
        // ========== Runtime Event Handling ==========
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
                
                // 处理 ASK_USER 事件
                if (eventType === 'ASK_USER') {
                    console.log('📬 收到 ASK_USER 事件:', { source, content, payload });
                    await this.handleAskUser(source, content, payload);
                }
                
            } catch (error) {
                console.error('Failed to handle runtime event:', error);
            }
        },
        
        /**
         * 处理 Agent ask_user 事件
         */
        async handleAskUser(agentName, question, payload) {
            const { user_session_id } = payload;
            
            // 1. 查找并切换到对应的对话
            if (user_session_id) {
                const session = this.sessions.find(s => s.session_id === user_session_id);
                
                if (session) {
                    // 如果不在当前对话，切换过去
                    if (!this.currentSession || this.currentSession.session_id !== user_session_id) {
                        this.currentSession = session;
                        await this.loadSessionEmails(session.session_id);
                        console.log('✅ 切换到对话:', session.name);
                    }
                } else {
                    console.warn('⚠️ 未找到对应的对话:', user_session_id);
                }
            }
            
            // 2. 显示用户输入对话框
            this.showAskUserDialog({
                agent_name: agentName,
                question: question,
                user_session_id: user_session_id
            });
        },
        
        /**
         * 显示用户输入对话框
         */
        showAskUserDialog(data) {
            this.askUserDialog = {
                show: true,
                agent_name: data.agent_name,
                question: data.question,
                user_session_id: data.user_session_id,
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
                this.askUserDialog.error = '请输入回答内容';
                return;
            }
            
            this.askUserDialog.submitting = true;
            this.askUserDialog.error = null;
            
            try {
                await API.submitUserInput(this.askUserDialog.agent_name, {
                    answer: this.askUserDialog.answer
                });
                
                console.log('✅ 用户回答已提交');
                
                // 关闭对话框
                this.askUserDialog.show = false;
                this.askUserDialog.answer = '';
                
            } catch (error) {
                console.error('❌ 提交回答失败:', error);
                this.askUserDialog.error = error.message || '提交失败';
            } finally {
                this.askUserDialog.submitting = false;
            }
        },
        
        /**
         * 关闭用户输入对话框
         */
        closeAskUserDialog() {
            this.askUserDialog = {
                show: false,
                agent_name: '',
                question: '',
                user_session_id: null,
                answer: '',
                submitting: false,
                error: null
            };
        },
        
        // Handle new email received via WebSocket
        async handleNewEmail(emailData) {
            console.log('📧 New email received:', emailData);

            // Close any existing popup (only show latest)
            this.newEmailPopup = null;

            // Show new email popup
            this.newEmailPopup = emailData;

            // Refresh session list
            await this.loadSessions();

            // Select the session if user_session_id is available
            if (emailData.user_session_id) {
                const session = this.sessions.find(s => s.session_id === emailData.user_session_id);
                if (session) {
                    await this.selectSession(session);
                }
            }
        },

        // Close new email popup
        closeNewEmailPopup() {
            this.newEmailPopup = null;
        },

        // Tab navigation
        switchTab(tabName) {
            this.currentTab = tabName;
        },

        // Session management
        async selectSession(session) {
            this.currentSession = session;
            await this.loadSessionEmails(session.session_id);
        },

        // Load session emails
        async loadSessionEmails(sessionId) {
            try {
                const response = await API.getSessionEmails(sessionId);
                this.currentSessionEmails = response.emails || [];
                
                // ✅ 检查最后一封邮件，判断是否需要轮询 Agent 状态
                this.checkAndStartStatusPolling();
                
                // 等待 DOM 更新后滚动到底部
                this.$nextTick(() => {
                    this.scrollToBottom();
                });
            } catch (error) {
                console.error('Failed to load session emails:', error);
                this.currentSessionEmails = [];
            }
        },

        // 滚动到消息容器底部
        scrollToBottom() {
            const container = document.getElementById('messages-container');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        },
        
        // ========== Agent 状态轮询 ==========
        
        /**
         * 检查最后一封邮件，判断是否需要开始轮询 Agent 状态
         */
        checkAndStartStatusPolling() {
            // 停止之前的轮询
            this.stopAgentStatusPolling();
            
            // 检查是否有邮件
            if (!this.currentSessionEmails || this.currentSessionEmails.length === 0) {
                return;
            }
            
            // 获取最后一封邮件
            const lastEmail = this.currentSessionEmails[this.currentSessionEmails.length - 1];
            
            // 判断是否是用户发出的邮件
            if (lastEmail.is_from_user) {
                // 获取收件人（目标 Agent）
                const targetAgent = lastEmail.recipient || this.currentSession?.name;
                
                console.log('📊 最后一封邮件是用户发出的，开始轮询 Agent 状态:', targetAgent);
                
                // 开始轮询
                this.startAgentStatusPolling(targetAgent);
            } else {
                console.log('📊 最后一封邮件是 Agent 回复的，不需要轮询状态');
            }
        },
        
        /**
         * 开始轮询 Agent 状态
         * @param {string} agentName - Agent 名称
         */
        startAgentStatusPolling(agentName) {
            if (this.agentStatusPolling) {
                console.warn('⚠️ Status polling already active');
                return;
            }
            
            this.agentStatusPolling = true;
            this.agentStatusTarget = agentName;
            this.agentStatusError = null;
            
            // 立即获取一次状态
            this.fetchAgentStatus();
            
            // 每 2 秒轮询一次
            this.pollingInterval = setInterval(() => {
                this.fetchAgentStatus();
            }, 2000);
        },
        
        /**
         * 停止轮询 Agent 状态
         */
        stopAgentStatusPolling() {
            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
                this.pollingInterval = null;
            }
            
            this.agentStatusPolling = false;
            this.agentStatusTarget = '';
            this.agentStatusHistory = [];
            this.agentStatusError = null;
        },
        
        /**
         * 获取 Agent 状态
         */
        async fetchAgentStatus() {
            if (!this.agentStatusTarget) {
                return;
            }
            
            try {
                const response = await fetch(`/api/agents/${this.agentStatusTarget}/status/history`);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                
                // 更新状态历史
                this.agentStatusHistory = data || [];
                this.agentStatusError = null;
                
                console.log('📊 Agent 状态更新:', this.agentStatusHistory);
                
                // 检查最后一封邮件是否还是用户发出的
                // 如果不是（收到新回复），停止轮询
                this.checkLastEmailChanged();
                
            } catch (error) {
                console.error('❌ 获取 Agent 状态失败:', error);
                this.agentStatusError = error.message;
            }
        },
        
        /**
         * 检查最后一封邮件是否变化（收到 Agent 回复）
         */
        checkLastEmailChanged() {
            if (!this.currentSessionEmails || this.currentSessionEmails.length === 0) {
                // 没有邮件了，停止轮询
                this.stopAgentStatusPolling();
                return;
            }
            
            const lastEmail = this.currentSessionEmails[this.currentSessionEmails.length - 1];
            
            // 如果最后一封邮件不是用户发出的，说明收到回复了
            if (!lastEmail.is_from_user) {
                console.log('✅ 收到 Agent 回复，停止状态轮询');
                this.stopAgentStatusPolling();
            }
        },
        
        /**
         * 格式化状态时间戳
         */
        formatStatusTime(timestamp) {
            if (!timestamp) return '';
            
            const date = new Date(timestamp);
            const now = new Date();
            const diff = now - date;
            
            // 小于 1 分钟
            if (diff < 60000) {
                return '刚刚';
            }
            
            // 小于 1 小时
            if (diff < 3600000) {
                const minutes = Math.floor(diff / 60000);
                return `${minutes} 分钟前`;
            }
            
            // 大于 1 小时，显示时间
            return date.toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        },

        // Format timestamp
        formatTime(timestamp) {
            const date = new Date(timestamp);
            return date.toLocaleTimeString('zh-CN', {
                hour: '2-digit',
                minute: '2-digit'
            });
        },

        // Format date
        formatDate(timestamp) {
            const date = new Date(timestamp);
            const now = new Date();
            
            // Check if it's today (same day)
            const isToday = date.getDate() === now.getDate() &&
                           date.getMonth() === now.getMonth() &&
                           date.getFullYear() === now.getFullYear();
            
            if (isToday) {
                return '今天';
            }
            
            // Check if it's yesterday
            const yesterday = new Date(now);
            yesterday.setDate(yesterday.getDate() - 1);
            const isYesterday = date.getDate() === yesterday.getDate() &&
                               date.getMonth() === yesterday.getMonth() &&
                               date.getFullYear() === yesterday.getFullYear();
            
            if (isYesterday) {
                return '昨天';
            }
            
            // Calculate days difference for "X days ago"
            const diffTime = Math.abs(now - date);
            const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
            
            if (diffDays < 7) {
                return `${diffDays}天前`;
            } else {
                return date.toLocaleDateString('zh-CN');
            }
        },

        // Get avatar name (1-2 characters)
        getAvatarName(name) {
            if (!name) return '?';
            if (name === this.user_agent_name) return 'U';
            return name.substring(0, 2).toUpperCase();
        },

        // Render Markdown content
        renderMarkdown(content) {
            if (!content) return '';
            try {
                // Configure marked options for better rendering
                marked.setOptions({
                    breaks: true,      // Convert \n to <br>
                    gfm: true,         // GitHub Flavored Markdown
                    headerIds: false,  // Don't generate header IDs
                    mangle: false      // Don't mangle email addresses
                });
                return marked.parse(content);
            } catch (error) {
                console.error('Markdown rendering error:', error);
                // Fallback to plain text with line breaks
                return content.replace(/\n/g, '<br>');
            }
        },

        // Select agent from dropdown
        selectAgent(agent) {
            this.newEmail.recipient = agent.name;
            this.agentSearchQuery = agent.name;
            this.showAgentDropdown = false;
        },

        // Send email
        async sendEmail() {
            if (!this.newEmail.recipient || !this.newEmail.body) {
                alert('Please fill in recipient and message');
                return;
            }

            this.isSendingEmail = true;

            try {
                // Use empty string for subject, let user_proxy generate it
                const response = await API.sendEmail('new', {
                    recipient: this.newEmail.recipient,
                    subject: '',  // Empty string, user_proxy will auto-generate
                    body: this.newEmail.body
                }, this.newEmail.attachments);  // 传递附件

                console.log('Email sent:', response);

                // Close modal
                this.showNewEmailModal = false;

                // Reset form
                this.newEmail = {
                    recipient: '',
                    body: '',
                    attachments: []
                };
                this.agentSearchQuery = '';

                // Refresh sessions
                await this.loadSessions();

                // Auto-select the newly created session
                if (response.user_session_id) {
                    // Find the new session in the updated list
                    const newSession = this.sessions.find(s => s.session_id === response.user_session_id);
                    if (newSession) {
                        await this.selectSession(newSession);
                    }
                }
            } catch (error) {
                console.error('Failed to send email:', error);
                alert(`Failed to send: ${error.message}`);
            } finally {
                this.isSendingEmail = false;
            }
        },

        // Panel resizing methods
        startResize(edge, event) {
            this.isResizing = true;
            this.resizingEdge = edge;
            this.startX = event.clientX;
            this.startLeftWidth = this.leftPanelWidth;
            this.startRightWidth = this.rightPanelWidth;

            // Add body class for visual feedback
            document.body.classList.add('is-resizing');

            // Add window-level event listeners
            window.addEventListener('mousemove', this.onResize);
            window.addEventListener('mouseup', this.stopResize);
        },

        onResize(event) {
            if (!this.isResizing) return;

            const deltaX = event.clientX - this.startX;
            const minWidth = 200;
            const maxWidth = 600;

            if (this.resizingEdge === 'left') {
                // Resize left panel
                const newWidth = this.startLeftWidth + deltaX;
                if (newWidth >= minWidth && newWidth <= maxWidth) {
                    this.leftPanelWidth = newWidth;
                }
            } else if (this.resizingEdge === 'right') {
                // Resize right panel (deltaX is inverted)
                const newWidth = this.startRightWidth - deltaX;
                if (newWidth >= minWidth && newWidth <= maxWidth) {
                    this.rightPanelWidth = newWidth;
                }
            }
        },

        stopResize() {
            this.isResizing = false;
            this.resizingEdge = null;

            // Remove body class
            document.body.classList.remove('is-resizing');

            // Remove window-level event listeners
            window.removeEventListener('mousemove', this.onResize);
            window.removeEventListener('mouseup', this.stopResize);
        },

        // 显示回复框
        startReply(email, mode = 'reply') {
            // 直接在 email 对象上添加属性
            email.showReplyBox = true;
            email.replyMode = mode;
            email.replyBody = email.replyBody || '';  // 保持已有内容或初始化为空
            
            // 回复逻辑：
            // - 如果是回复自己发的邮件，收件人保持为原来的收件人
            // - 如果是回复 Agent 发来的邮件，收件人为该邮件的发件人
            if (mode === 'reply') {
                if (email.is_from_user) {
                    // 回自己的邮件 → 收件人是原来的收件人
                    email.replyRecipient = email.recipient;
                } else {
                    // 回 Agent 的邮件 → 收件人是发件人
                    email.replyRecipient = email.sender;
                }
            } else {
                // forward 模式，收件人为空让用户填写
                email.replyRecipient = '';
            }
        },

        // 隐藏回复框
        cancelReply(email) {
            email.showReplyBox = false;
        },

        // 发送回复
        async sendReply(email) {
            if (!email.replyBody || email.replyBody.trim() === '') {
                alert('请输入消息内容');
                return;
            }

            if (email.replyMode === 'forward' && (!email.replyRecipient || email.replyRecipient.trim() === '')) {
                alert('请输入收件人');
                return;
            }

            // 确保有有效的 user_session_id
            const targetSessionId = email.user_session_id || this.currentSession?.session_id;
            if (!targetSessionId) {
                console.error('Cannot determine session ID', { 
                    emailUserSessionId: email.user_session_id, 
                    currentSessionId: this.currentSession?.session_id 
                });
                alert('无法确定会话 ID，请刷新页面重试');
                return;
            }

            try {
                const emailData = {
                    recipient: email.replyRecipient,
                    subject: '',  // 空字符串，user_proxy会自动生成
                    body: email.replyBody
                };

                // 如果是回复模式，添加 in_reply_to
                if (email.replyMode === 'reply') {
                    emailData.in_reply_to = email.id;
                }

                // 关闭回复框（在刷新之前，避免引用失效）
                email.showReplyBox = false;

                console.log('Sending reply to session:', targetSessionId, 'in_reply_to:', email.id);

                const response = await API.sendEmail(
                    targetSessionId,
                    emailData
                );

                console.log('Message sent:', response);

                // Refresh session list to update time
                await this.loadSessions();

                // 如果目标会话与当前会话相同，刷新邮件列表
                if (this.currentSession && this.currentSession.session_id === targetSessionId) {
                    await this.loadSessionEmails(this.currentSession.session_id);
                }

            } catch (error) {
                console.error('Failed to send:', error);
                alert(`发送失败: ${error.message}`);
            }
        },

        // Send quick reply from input box
        // 获取最后一封邮件的发送者（用于显示）
        getLastEmailSender() {
            if (!this.currentSessionEmails || this.currentSessionEmails.length === 0) {
                return this.currentSession?.name || 'Unknown';
            }
            const lastEmail = this.currentSessionEmails[this.currentSessionEmails.length - 1];
            
            // 如果最后一封是用户发的，回复给收件人
            if (lastEmail.is_from_user) {
                return lastEmail.recipient || this.currentSession.name;
            }
            // 如果最后一封是别人发的，回复给发送者
            return lastEmail.sender || this.currentSession.name;
        },

        async sendQuickReply() {
            if (!this.quickReplyBody.trim() || !this.currentSession) {
                return;
            }

            // 如果没有邮件，发送给会话的 agent
            if (this.currentSessionEmails.length === 0) {
                try {
                    const emailData = {
                        recipient: this.currentSession.name,
                        subject: '',
                        body: this.quickReplyBody
                    };

                    const response = await API.sendEmail(
                        this.currentSession.session_id,
                        emailData
                    );

                    console.log('Quick reply sent:', response);
                    this.quickReplyBody = '';
                    await this.loadSessions();
                    await this.loadSessionEmails(this.currentSession.session_id);
                    return;
                } catch (error) {
                    console.error('Failed to send quick reply:', error);
                    alert(`发送失败: ${error.message}`);
                    return;
                }
            }

            // 获取最后一封邮件
            const lastEmail = this.currentSessionEmails[this.currentSessionEmails.length - 1];
            
            // 确定回复对象和 in_reply_to
            let recipient;
            let inReplyTo;
            
            if (lastEmail.is_from_user) {
                // 最后一封是用户发的，回复给收件人
                recipient = lastEmail.recipient || this.currentSession.name;
            } else {
                // 最后一封是别人发的，回复给发送者
                recipient = lastEmail.sender;
            }
            
            // 使用邮件 ID 作为 in_reply_to
            inReplyTo = lastEmail.id;

            try {
                const emailData = {
                    recipient: recipient,
                    subject: '',
                    body: this.quickReplyBody,
                    in_reply_to: inReplyTo
                };

                const response = await API.sendEmail(
                    this.currentSession.session_id,
                    emailData
                );

                console.log('Quick reply sent:', response);

                // Clear input
                this.quickReplyBody = '';

                // Refresh session list and messages
                await this.loadSessions();
                await this.loadSessionEmails(this.currentSession.session_id);
                
                // 滚动到底部（loadSessionEmails 已经会自动滚动，但为了保险再调用一次）
                this.$nextTick(() => {
                    this.scrollToBottom();
                });

            } catch (error) {
                console.error('Failed to send quick reply:', error);
                alert(`发送失败: ${error.message}`);
            }
        },

        // ===== Settings Methods =====

        // Module to class name mapping
        get moduleClassMap() {
            return {
                'agentmatrix.agents.base': 'BaseAgent',
                'agentmatrix.agents.deep_researcher': 'DeepResearcher',
                'agentmatrix.agents.user_proxy': 'UserProxyAgent'
            };
        },

        // Update class name when module changes
        updateClassNameFromModule() {
            this.agentForm.class_name = this.moduleClassMap[this.agentForm.module] || 'BaseAgent';
        },

        // Switch settings view
        switchSettingsView(view) {
            this.settingsView = view;
            if (view === 'agents') {
                this.loadAgentProfiles();
            } else if (view === 'llm') {
                this.loadLLMConfigs();
            }
        },

        // Format URL for display
        formatUrl(url) {
            if (!url) return '';
            try {
                const urlObj = new URL(url);
                return urlObj.hostname + (urlObj.pathname !== '/' ? urlObj.pathname : '');
            } catch {
                return url.length > 30 ? url.substring(0, 30) + '...' : url;
            }
        },

        // Load agent profiles
        async loadAgentProfiles() {
            try {
                const response = await API.getAgentProfiles();
                this.agentProfiles = response.agents || [];
                console.log('Loaded agent profiles:', this.agentProfiles);
            } catch (error) {
                console.error('Failed to load agent profiles:', error);
                this.agentProfiles = [];
            }
        },

        // Load available skills from system
        async loadAvailableSkills() {
            try {
                const response = await API.getAvailableSkills();
                this.availableSkills = response.skills || [];
                console.log('Loaded available skills:', this.availableSkills);
            } catch (error) {
                console.error('Failed to load available skills:', error);
                this.availableSkills = [];
            }
        },

        // Open agent modal (for create or edit)
        async openAgentModal(agent = null) {
            this.editingAgent = agent;
            this.agentFormErrors = {};
            this.newSkill = '';
            this.showAdvancedConfig = false;
            this.agentEditMode = 'simple';  // Default to simple mode
            this.agentRawYaml = '';
            
            // Load available skills
            await this.loadAvailableSkills();
            
            if (agent) {
                // Edit mode - populate form from agent data
                this.agentForm = {
                    name: agent.name,
                    description: agent.description || '',
                    module: agent.module || 'agentmatrix.agents.base',
                    class_name: agent.class_name || 'BaseAgent',
                    backend_model: agent.backend_model || 'default_llm',
                    skills: [...(agent.skills || [])],
                    // Persona base - 从 persona.base 或从 _raw_profile.persona.base 获取
                    personaBase: agent.persona?.base || agent._raw_profile?.persona?.base || '',
                    // Cerebellum model
                    cerebellumModel: agent.cerebellum?.backend_model || agent._raw_profile?.cerebellum?.backend_model || '',
                    // Vision brain model
                    visionBrainModel: agent.vision_brain?.backend_model || agent._raw_profile?.vision_brain?.backend_model || ''
                };
                
                // Prepare raw YAML for advanced mode
                if (agent._raw_profile) {
                    this.agentRawYaml = this.objectToYaml(agent._raw_profile);
                } else {
                    // Build YAML from current form
                    this.agentRawYaml = this.buildAgentYamlFromForm();
                }
            } else {
                // Create mode - reset form
                this.agentForm = {
                    name: '',
                    description: '',
                    module: 'agentmatrix.agents.base',
                    class_name: 'BaseAgent',
                    backend_model: 'default_llm',
                    skills: [],
                    personaBase: '',
                    cerebellumModel: '',
                    visionBrainModel: ''
                };
                this.agentRawYaml = this.buildAgentYamlFromForm();
            }
            
            this.showAgentModal = true;
        },

        // Convert object to YAML-like string (simplified)
        objectToYaml(obj) {
            const lines = [];
            for (const [key, value] of Object.entries(obj)) {
                if (value === null || value === undefined) continue;
                
                if (typeof value === 'object' && !Array.isArray(value)) {
                    // Nested object
                    lines.push(`${key}:`);
                    for (const [subKey, subValue] of Object.entries(value)) {
                        if (typeof subValue === 'string' && subValue.includes('\n')) {
                            lines.push(`  ${subKey}: |`);
                            subValue.split('\n').forEach(line => lines.push(`    ${line}`));
                        } else {
                            lines.push(`  ${subKey}: ${subValue}`);
                        }
                    }
                } else if (Array.isArray(value)) {
                    lines.push(`${key}:`);
                    value.forEach(item => lines.push(`  - ${item}`));
                } else if (typeof value === 'string' && value.includes('\n')) {
                    lines.push(`${key}: |`);
                    value.split('\n').forEach(line => lines.push(`  ${line}`));
                } else {
                    lines.push(`${key}: ${value}`);
                }
            }
            return lines.join('\n');
        },

        // Build YAML from current form
        buildAgentYamlFromForm() {
            const profile = {
                name: this.agentForm.name || 'NewAgent',
                description: this.agentForm.description || 'New agent',
                module: this.agentForm.module,
                class_name: this.agentForm.class_name
            };

            if (this.agentForm.backend_model && this.agentForm.backend_model !== 'default_llm') {
                profile.backend_model = this.agentForm.backend_model;
            }
            if (this.agentForm.skills && this.agentForm.skills.length > 0) {
                profile.skills = this.agentForm.skills;
            }
            if (this.agentForm.personaBase) {
                profile.persona = { base: this.agentForm.personaBase };
            }
            if (this.agentForm.cerebellumModel) {
                profile.cerebellum = { backend_model: this.agentForm.cerebellumModel };
            }
            if (this.agentForm.visionBrainModel) {
                profile.vision_brain = { backend_model: this.agentForm.visionBrainModel };
            }
            
            return this.objectToYaml(profile);
        },

        // Parse YAML string to object (simplified)
        parseYaml(yamlStr) {
            const result = {};
            const lines = yamlStr.split('\n');
            let currentKey = null;
            let currentSubKey = null;
            let isMultiline = false;
            let multilineBuffer = [];
            
            for (let line of lines) {
                // Check for multiline end
                if (isMultiline && (line.startsWith('  ') || line === '')) {
                    if (line.startsWith('  ')) {
                        multilineBuffer.push(line.slice(2));
                        continue;
                    }
                }
                
                if (isMultiline && !line.startsWith('  ')) {
                    // End of multiline
                    if (currentSubKey) {
                        result[currentKey][currentSubKey] = multilineBuffer.join('\n');
                    } else {
                        result[currentKey] = multilineBuffer.join('\n');
                    }
                    isMultiline = false;
                    multilineBuffer = [];
                    currentSubKey = null;
                }
                
                // Skip empty lines
                if (!line.trim()) continue;
                
                // Top-level key
                if (!line.startsWith(' ') && line.includes(':')) {
                    const [key, ...rest] = line.split(':');
                    const value = rest.join(':').trim();
                    currentKey = key.trim();
                    
                    if (value === '|') {
                        isMultiline = true;
                        multilineBuffer = [];
                    } else if (value) {
                        result[currentKey] = value;
                    } else {
                        result[currentKey] = {};
                    }
                    continue;
                }
                
                // Second-level key (4 spaces or 2 spaces)
                if ((line.startsWith('  ') || line.startsWith('    ')) && line.includes(':') && !line.trim().startsWith('-')) {
                    const trimmed = line.trim();
                    const [key, ...rest] = trimmed.split(':');
                    const value = rest.join(':').trim();
                    currentSubKey = key.trim();
                    
                    if (!result[currentKey]) result[currentKey] = {};
                    
                    if (value === '|') {
                        isMultiline = true;
                        multilineBuffer = [];
                    } else if (value) {
                        result[currentKey][currentSubKey] = value;
                    }
                    continue;
                }
                
                // Array items
                if (line.trim().startsWith('- ') && currentKey) {
                    if (!result[currentKey]) result[currentKey] = [];
                    if (!Array.isArray(result[currentKey])) result[currentKey] = [];
                    result[currentKey].push(line.trim().slice(2));
                }
            }
            
            // Handle last multiline
            if (isMultiline && multilineBuffer.length > 0) {
                if (currentSubKey) {
                    result[currentKey][currentSubKey] = multilineBuffer.join('\n');
                } else {
                    result[currentKey] = multilineBuffer.join('\n');
                }
            }
            
            return result;
        },

        // Close agent modal
        closeAgentModal() {
            this.showAgentModal = false;
            this.editingAgent = null;
            this.agentFormErrors = {};
            this.newSkill = '';
            this.showAdvancedConfig = false;
            this.agentEditMode = 'simple';
            this.agentRawYaml = '';
            this.showSkillSearchModal = false;
        },

        // Open skill search modal
        openSkillSearchModal() {
            this.skillSearchQuery = '';
            this.showSkillSearchModal = true;
        },

        // Close skill search modal
        closeSkillSearchModal() {
            this.showSkillSearchModal = false;
            this.skillSearchQuery = '';
        },

        // Add skill from search
        addSkillFromSearch(skillName) {
            if (!this.agentForm.skills.includes(skillName)) {
                this.agentForm.skills.push(skillName);
            }
            this.closeSkillSearchModal();
        },

        // Get filtered skills for search
        get filteredAvailableSkills() {
            if (!this.skillSearchQuery) {
                return this.availableSkills;
            }
            const query = this.skillSearchQuery.toLowerCase();
            return this.availableSkills.filter(skill => 
                skill.name.toLowerCase().includes(query) ||
                (skill.description && skill.description.toLowerCase().includes(query))
            );
        },

        // Add skill to form
        addSkill() {
            if (!this.newSkill.trim()) return;
            
            const skill = this.newSkill.trim();
            if (!this.agentForm.skills.includes(skill)) {
                this.agentForm.skills.push(skill);
            }
            this.newSkill = '';
        },

        // Remove skill from form
        removeSkill(index) {
            this.agentForm.skills.splice(index, 1);
        },

        // Validate agent form
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

        // Save agent (create or update) - 支持 Simple 和 Advanced 两种模式
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
                    const parsedYaml = this.parseYaml(this.agentRawYaml);
                    formData = {
                        ...parsedYaml,
                        // 确保必需字段存在
                        name: parsedYaml.name,
                        description: parsedYaml.description || '',
                        module: parsedYaml.module || 'agentmatrix.agents.base',
                        class_name: parsedYaml.class_name || 'BaseAgent'
                    };
                } else {
                    // Simple 模式：从表单构建
                    formData = {
                        description: this.agentForm.description,
                        backend_model: this.agentForm.backend_model,
                        skills: this.agentForm.skills,
                        module: this.agentForm.module,
                        class_name: this.agentForm.class_name
                    };
                    
                    // 添加 persona（如果有值）
                    if (this.agentForm.personaBase && this.agentForm.personaBase.trim()) {
                        formData.persona = {
                            base: this.agentForm.personaBase.trim()
                        };
                    }
                    
                    // 添加 cerebellum 配置（如果有值）
                    if (this.agentForm.cerebellumModel && this.agentForm.cerebellumModel.trim()) {
                        formData.cerebellum = {
                            backend_model: this.agentForm.cerebellumModel.trim()
                        };
                    }
                    
                    // 添加 vision_brain 配置（如果有值）
                    if (this.agentForm.visionBrainModel && this.agentForm.visionBrainModel.trim()) {
                        formData.vision_brain = {
                            backend_model: this.agentForm.visionBrainModel.trim()
                        };
                    }
                    
                    // 保留原始配置中的未处理字段（灵活性）
                    if (this.editingAgent && this.editingAgent._raw_profile) {
                        const preservedFields = {};
                        const handledFields = ['name', 'description', 'module', 'class_name',
                                               'backend_model', 'skills',
                                               'persona', 'cerebellum', 'vision_brain'];
                        
                        for (const [key, value] of Object.entries(this.editingAgent._raw_profile)) {
                            if (!handledFields.includes(key) && value !== undefined) {
                                preservedFields[key] = value;
                            }
                        }
                        
                        if (Object.keys(preservedFields).length > 0) {
                            formData.extra_fields = preservedFields;
                        }
                    }
                }
                
                if (this.editingAgent) {
                    // Update existing agent
                    await API.updateAgentProfile(this.editingAgent.name, formData);
                    console.log('Agent updated:', this.editingAgent.name);
                } else {
                    // Create new agent
                    formData.name = this.agentEditMode === 'advanced' 
                        ? formData.name 
                        : this.agentForm.name;
                    await API.createAgentProfile(formData);
                    console.log('Agent created:', formData.name);
                }
                
                // Close modal and refresh list
                this.closeAgentModal();
                await this.loadAgentProfiles();
                
                // Also refresh runtime agents list
                await this.loadAgents();
                
            } catch (error) {
                console.error('Failed to save agent:', error);
                alert(`Failed to save: ${error.message}`);
            } finally {
                this.isSavingAgent = false;
            }
        },

        // Confirm delete agent
        confirmDeleteAgent(agent) {
            this.agentToDelete = agent;
            this.showDeleteConfirmModal = true;
        },

        // Delete agent
        async deleteAgent() {
            if (!this.agentToDelete) return;
            
            this.isDeletingAgent = true;
            
            try {
                await API.deleteAgentProfile(this.agentToDelete.name);
                console.log('Agent deleted:', this.agentToDelete.name);
                
                this.showDeleteConfirmModal = false;
                this.agentToDelete = null;
                await this.loadAgentProfiles();
                
                // Also refresh runtime agents list
                await this.loadAgents();
                
            } catch (error) {
                console.error('Failed to delete agent:', error);
                alert(`Failed to delete: ${error.message}`);
            } finally {
                this.isDeletingAgent = false;
            }
        },

        // ===== LLM Config Methods =====

        // Load LLM configs
        async loadLLMConfigs() {
            try {
                const response = await API.getLLMConfigs();
                this.llmConfigs = response.configs || [];
                console.log('Loaded LLM configs:', this.llmConfigs);
            } catch (error) {
                console.error('Failed to load LLM configs:', error);
                this.llmConfigs = [];
            }
        },

        // Open LLM modal (for create or edit)
        openLLMModal(config = null) {
            this.editingLLMConfig = config;
            this.llmFormErrors = {};
            this.showLLMApiKey = false;
            
            if (config) {
                // Edit mode - populate form
                this.llmForm = {
                    name: config.name,
                    url: config.url || '',
                    api_key: config.api_key || '',
                    model_name: config.model_name || ''
                };
            } else {
                // Create mode - reset form
                this.llmForm = {
                    name: '',
                    url: '',
                    api_key: '',
                    model_name: ''
                };
            }
            
            this.showLLMModal = true;
        },

        // Close LLM modal
        closeLLMModal() {
            this.showLLMModal = false;
            this.editingLLMConfig = null;
            this.llmFormErrors = {};
            this.showLLMApiKey = false;
        },

        // Validate LLM form
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

        // Save LLM config (create or update)
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
                    // Update existing config
                    await API.updateLLMConfig(this.editingLLMConfig.name, formData);
                    console.log('LLM config updated:', this.editingLLMConfig.name);
                } else {
                    // Create new config
                    formData.name = this.llmForm.name;
                    await API.createLLMConfig(formData);
                    console.log('LLM config created:', this.llmForm.name);
                }
                
                // Close modal and refresh list
                this.closeLLMModal();
                await this.loadLLMConfigs();
                
            } catch (error) {
                console.error('Failed to save LLM config:', error);
                alert(`Failed to save: ${error.message}`);
            } finally {
                this.isSavingLLM = false;
            }
        },

        // Reset LLM config to defaults
        async resetLLMConfig(configName) {
            if (!confirm(`Reset ${configName} to default values?`)) return;
            
            try {
                await API.resetLLMConfig(configName);
                console.log('LLM config reset:', configName);
                await this.loadLLMConfigs();
            } catch (error) {
                console.error('Failed to reset LLM config:', error);
                alert(`Failed to reset: ${error.message}`);
            }
        },

        // Confirm delete LLM config
        confirmDeleteLLM(config) {
            this.llmToDelete = config;
            this.showDeleteLLMConfirmModal = true;
        },

        // Delete LLM config
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
        }
    };
}
