// Email Store - 邮件状态管理


/**
 * Email Store: 管理邮件发送、回复和邮件状态
 */
function useEmailStore() {
    return {
        // ========== 状态 ==========
        showNewEmailModal: false,
        isSendingEmail: false,
        agentSearchQuery: '',
        showAgentDropdown: false,
        newEmail: {
            recipient: '',
            body: '',
            attachments: []
        },

        // Reply state - 使用 Map 存储每个邮件的回复状态
        replyStates: {},

        // File panel state
        showFilePanel: true,

        // Quick reply state
        quickReplyBody: '',

        // New email popup state
        newEmailPopup: null,

        // ========== 方法 ==========

        /**
         * 打开新邮件模态框
         */
        openNewEmailModal() {
            this.showNewEmailModal = true;
            this.newEmail = {
                recipient: '',
                body: '',
                attachments: []
            };
        },

        /**
         * 关闭新邮件模态框
         */
        closeNewEmailModal() {
            this.showNewEmailModal = false;
            this.newEmail = {
                recipient: '',
                body: '',
                attachments: []
            };
            this.agentSearchQuery = '';
            this.showAgentDropdown = false;
        },

        /**
         * 发送邮件
         */
        async sendEmail() {
            if (!this.newEmail.recipient || !this.newEmail.body) {
                alert('Please fill in recipient and message');
                return;
            }

            if (!this.currentSession) {
                alert('Please select a session first');
                return;
            }

            this.isSendingEmail = true;

            try {
                const formData = new FormData();
                formData.append('recipient', this.newEmail.recipient);
                formData.append('body', this.newEmail.body);
                formData.append('session_id', this.currentSession.session_id);

                // 添加附件
                for (const file of this.newEmail.attachments) {
                    formData.append('files', file);
                }

                await API.sendEmail(this.currentSession.name, formData);

                // 重新加载当前会话的邮件
                await this.loadSessionEmails(this.currentSession.session_id);

                // 关闭模态框
                this.closeNewEmailModal();
            } catch (error) {
                console.error('Failed to send email:', error);
                alert(`Failed to send: ${error.message}`);
            } finally {
                this.isSendingEmail = false;
            }
        },

        /**
         * 开始回复邮件
         * @param {Object} email - 邮件对象
         * @param {string} mode - 回复模式 ('reply' | 'replyAll')
         */
        startReply(email, mode = 'reply') {
            const replyTo = mode === 'replyAll' ? email.replyAll || email.recipient : email.recipient;

            this.replyStates[email.id] = {
                show: true,
                mode: mode,
                recipient: replyTo,
                body: ''
            };
        },

        /**
         * 取消回复
         * @param {Object} email - 邮件对象
         */
        cancelReply(email) {
            if (this.replyStates[email.id]) {
                this.replyStates[email.id].show = false;
            }
        },

        /**
         * 发送回复
         * @param {Object} email - 邮件对象
         */
        async sendReply(email) {
            const replyState = this.replyStates[email.id];
            if (!replyState || !replyState.body.trim()) {
                alert('Please enter a message');
                return;
            }

            if (!this.currentSession) {
                alert('Please select a session first');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('recipient', replyState.recipient);
                formData.append('body', replyState.body);
                formData.append('session_id', this.currentSession.session_id);
                formData.append('in_reply_to', email.id);

                await API.sendEmail(this.currentSession.name, formData);

                // 重新加载邮件列表
                await this.loadSessionEmails(this.currentSession.session_id);

                // 清除回复状态
                this.replyStates[email.id] = {
                    show: false,
                    mode: 'reply',
                    recipient: '',
                    body: ''
                };
            } catch (error) {
                console.error('Failed to send reply:', error);
                alert(`Failed to send reply: ${error.message}`);
            }
        },

        /**
         * 处理新收到的邮件
         * @param {Object} emailData - 邮件数据
         */
        async handleNewEmail(emailData) {
            console.log('New email received:', emailData);

            // 检查是否属于当前会话
            if (this.currentSession &&
                emailData.session_id === this.currentSession.session_id) {

                // 添加到邮件列表
                this.currentSessionEmails.push(emailData);

                // 滚动到底部
                this.$nextTick(() => {
                    this.scrollToBottom();
                });

                // ✅ 收到邮件后停止状态轮询
                this.stopAgentStatusPolling();
            }

            // 更新会话列表（刷新会话时间戳）
            await this.loadSessions();
        },

        /**
         * 获取最后一封邮件的发送者
         * @returns {string} 发送者名称
         */
        getLastEmailSender() {
            if (!this.currentSessionEmails || this.currentSessionEmails.length === 0) {
                return null;
            }
            const lastEmail = this.currentSessionEmails[this.currentSessionEmails.length - 1];
            return lastEmail.sender;
        },

        /**
         * 添加附件
         * @param {FileList} files - 文件列表
         */
        addAttachments(files) {
            for (const file of files) {
                // 检查是否是图片
                if (file.type.startsWith('image/')) {
                    this.newEmail.attachments.push(file);
                } else {
                    alert('Only image files are supported');
                }
            }
        },

        /**
         * 移除附件
         * @param {number} index - 附件索引
         */
        removeAttachment(index) {
            this.newEmail.attachments.splice(index, 1);
        },

        /**
         * 处理文件拖拽
         * @param {DragEvent} event - 拖拽事件
         */
        handleFileDrop(event) {
            event.preventDefault();
            const files = event.dataTransfer.files;
            this.addAttachments(files);
        },

        /**
         * 处理文件拖拽悬停
         * @param {DragEvent} event - 拖拽事件
         */
        handleFileDragOver(event) {
            event.preventDefault();
        },

        /**
         * 打开快速回复模态框
         */
        openQuickReply() {
            if (!this.currentSession) {
                alert('Please select a session first');
                return;
            }

            const lastEmail = this.currentSessionEmails[this.currentSessionEmails.length - 1];
            if (!lastEmail) {
                alert('No emails in this session');
                return;
            }

            this.quickReplyBody = '';
            this.newEmailPopup = {
                recipient: lastEmail.recipient || this.currentSession.name,
                in_reply_to: lastEmail.id
            };
        },

        /**
         * 关闭快速回复模态框
         */
        closeQuickReply() {
            this.newEmailPopup = null;
            this.quickReplyBody = '';
        },

        /**
         * 发送快速回复
         */
        async sendQuickReply() {
            if (!this.quickReplyBody.trim()) {
                alert('Please enter a message');
                return;
            }

            if (!this.currentSession || !this.newEmailPopup) {
                alert('Invalid state');
                return;
            }

            try {
                const formData = new FormData();
                formData.append('recipient', this.newEmailPopup.recipient);
                formData.append('body', this.quickReplyBody);
                formData.append('session_id', this.currentSession.session_id);

                if (this.newEmailPopup.in_reply_to) {
                    formData.append('in_reply_to', this.newEmailPopup.in_reply_to);
                }

                await API.sendEmail(this.currentSession.name, formData);

                // 重新加载邮件列表
                await this.loadSessionEmails(this.currentSession.session_id);

                // 关闭模态框
                this.closeQuickReply();
            } catch (error) {
                console.error('Failed to send quick reply:', error);
                alert(`Failed to send: ${error.message}`);
            }
        }
    };
}
