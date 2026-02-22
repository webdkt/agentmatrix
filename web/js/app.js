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

        // Settings state
        settingsView: 'main',  // 'main', 'agents', 'llm'
        agentProfiles: [],
        showAgentModal: false,
        editingAgent: null,
        isSavingAgent: false,
        agentFormErrors: {},
        newSkill: '',
        agentForm: {
            name: '',
            description: '',
            module: 'agentmatrix.agents.base',
            class_name: 'BaseAgent',
            instruction_to_caller: '',
            backend_model: 'default_llm',
            skills: [],
            personaBase: '',  // persona.base - 核心身份定义
            cerebellumModel: '',  // cerebellum.backend_model - 小脑模型
            visionBrainModel: ''  // vision_brain.backend_model - 视觉模型
        },
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

        // Open agent modal (for create or edit)
        openAgentModal(agent = null) {
            this.editingAgent = agent;
            this.agentFormErrors = {};
            this.newSkill = '';
            this.showAdvancedConfig = false;  // Reset advanced config visibility
            
            if (agent) {
                // Edit mode - populate form from agent data
                this.agentForm = {
                    name: agent.name,
                    description: agent.description || '',
                    module: agent.module || 'agentmatrix.agents.base',
                    class_name: agent.class_name || 'BaseAgent',
                    instruction_to_caller: agent.instruction_to_caller || '',
                    backend_model: agent.backend_model || 'default_llm',
                    skills: [...(agent.skills || [])],
                    // Persona base - 从 persona.base 或从 _raw_profile.persona.base 获取
                    personaBase: agent.persona?.base || agent._raw_profile?.persona?.base || '',
                    // Cerebellum model
                    cerebellumModel: agent.cerebellum?.backend_model || agent._raw_profile?.cerebellum?.backend_model || '',
                    // Vision brain model
                    visionBrainModel: agent.vision_brain?.backend_model || agent._raw_profile?.vision_brain?.backend_model || ''
                };
            } else {
                // Create mode - reset form
                this.agentForm = {
                    name: '',
                    description: '',
                    module: 'agentmatrix.agents.base',
                    class_name: 'BaseAgent',
                    instruction_to_caller: '',
                    backend_model: 'default_llm',
                    skills: [],
                    personaBase: '',
                    cerebellumModel: '',
                    visionBrainModel: ''
                };
            }
            
            this.showAgentModal = true;
        },

        // Close agent modal
        closeAgentModal() {
            this.showAgentModal = false;
            this.editingAgent = null;
            this.agentFormErrors = {};
            this.newSkill = '';
            this.showAdvancedConfig = false;
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

        // Save agent (create or update)
        async saveAgent() {
            if (!this.validateAgentForm()) return;
            
            this.isSavingAgent = true;
            
            try {
                // 构建基础表单数据
                const formData = {
                    description: this.agentForm.description,
                    instruction_to_caller: this.agentForm.instruction_to_caller,
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
                
                // 如果是编辑模式，保留原始配置中的其他字段（灵活性）
                if (this.editingAgent && this.editingAgent._raw_profile) {
                    // 提取未在前端表单中处理的原始字段作为 extra_fields
                    const preservedFields = {};
                    const handledFields = ['name', 'description', 'module', 'class_name', 
                                           'instruction_to_caller', 'backend_model', 'skills', 
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
                
                if (this.editingAgent) {
                    // Update existing agent
                    await API.updateAgentProfile(this.editingAgent.name, formData);
                    console.log('Agent updated:', this.editingAgent.name);
                } else {
                    // Create new agent
                    formData.name = this.agentForm.name;
                    formData.module = this.agentForm.module;
                    formData.class_name = this.agentForm.class_name;
                    await API.createAgentProfile(formData);
                    console.log('Agent created:', this.agentForm.name);
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
