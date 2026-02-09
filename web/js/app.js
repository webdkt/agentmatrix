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
            body: ''
        },

        // Reply state - 使用 Map 存储每个邮件的回复状态
        replyStates: {},

        // File panel state
        showFilePanel: true,

        // Quick reply state
        quickReplyBody: '',

        // New email popup state
        newEmailPopup: null,

        // Computed property for filtered agents
        get filteredAgents() {
            if (!this.agentSearchQuery) {
                return this.agents;
            }
            return this.agents.filter(agent =>
                agent.name.toLowerCase().includes(this.agentSearchQuery.toLowerCase())
            );
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
                                console.log('Runtime event:', data.data);
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
            } catch (error) {
                console.error('Failed to load session emails:', error);
                this.currentSessionEmails = [];
            }
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
                });

                console.log('Email sent:', response);

                // Close modal
                this.showNewEmailModal = false;

                // Reset form
                this.newEmail = {
                    recipient: '',
                    body: ''
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

                // 使用原邮件的 user_session_id（重要：不是 currentSession.session_id！）
                const targetSessionId = email.user_session_id;
                console.log('Sending to session:', targetSessionId);

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
        async sendQuickReply() {
            if (!this.quickReplyBody.trim() || !this.currentSession) {
                return;
            }

            try {
                const emailData = {
                    recipient: this.currentSession.name,  // Send to the session's agent
                    subject: '',
                    body: this.quickReplyBody
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

            } catch (error) {
                console.error('Failed to send quick reply:', error);
                alert(`发送失败: ${error.message}`);
            }
        }
    };
}
