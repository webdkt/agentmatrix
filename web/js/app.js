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

        // Computed property for filtered agents
        get filteredAgents() {
            if (!this.agentSearchQuery) {
                return this.agents;
            }
            return this.agents.filter(agent =>
                agent.toLowerCase().includes(this.agentSearchQuery.toLowerCase())
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

                // Agents are already loaded from runtime status in init()
                // Don't overwrite with API.getAgents() which returns empty

                // Load files
                const filesData = await API.getFiles();
                this.files = filesData.files || [];
            } catch (error) {
                console.error('Failed to load initial data:', error);
            }
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
        handleNewEmail(emailData) {
            console.log('📧 New email received:', emailData);

            // Show notification (could use browser notifications in the future)
            // For now, just log and potentially update UI
            const notification = `📧 New email from ${emailData.sender}: ${emailData.subject}`;
            console.log(notification);

            // TODO: Update session list or conversation history
            // This would be implemented when we have proper session management
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
            const diffTime = Math.abs(now - date);
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

            if (diffDays === 0) {
                return '今天';
            } else if (diffDays === 1) {
                return '昨天';
            } else if (diffDays < 7) {
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

        // Select agent from dropdown
        selectAgent(agent) {
            this.newEmail.recipient = agent;
            this.agentSearchQuery = agent;
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

                alert('Message sent successfully!');
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
        }
    };
}
