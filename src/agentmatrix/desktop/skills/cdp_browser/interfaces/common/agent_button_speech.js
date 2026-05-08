    // ==========================================
    // Speech Bubble（Agent 说话气泡）
    // ==========================================
    var _speechReplyEl = null;

    /** 轻量 markdown → HTML（标题统一为正文大小） */
    function _renderMarkdown(text) {
        // escape HTML
        var s = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        // code blocks (```...```)
        s = s.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
        // inline code
        s = s.replace(/`([^`\n]+)`/g, '<code>$1</code>');
        // headings (any level → same size)
        s = s.replace(/^#{1,6}\s+(.+)$/gm, '<strong>$1</strong>');
        // bold
        s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        // italic
        s = s.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
        // blockquote
        s = s.replace(/^&gt;\s?(.+)$/gm, '<blockquote>$1</blockquote>');
        // hr
        s = s.replace(/^[-*_]{3,}$/gm, '<hr>');
        // unordered list
        s = s.replace(/^[\-\*]\s+(.+)$/gm, '<li>$1</li>');
        s = s.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');
        // ordered list
        s = s.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
        // links [text](url)
        s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
        // paragraphs: double newline → <p>, single newline → <br>
        s = s.replace(/\n\n+/g, '</p><p>');
        s = s.replace(/\n/g, '<br>');
        s = '<p>' + s + '</p>';
        // clean empty p
        s = s.replace(/<p>\s*<\/p>/g, '');
        return s;
    }

    function _showSpeech(text) {
        if (_speechEl) {
            // Update existing
            _hideSpeechReply();
            var txt = _speechEl.querySelector('.ab-speech-text');
            if (txt) txt.innerHTML = _renderMarkdown(text);
            _positionSpeech();
            return;
        }

        var el = document.createElement('div');
        el.className = 'ab-speech';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'ab-speech-close';
        closeBtn.textContent = '\u2715';
        closeBtn.addEventListener('click', function(e) { e.stopPropagation(); _hideSpeech(); });
        var txt = document.createElement('div');
        txt.className = 'ab-speech-text';
        txt.innerHTML = _renderMarkdown(text);
        el.appendChild(closeBtn);
        el.appendChild(txt);
        shadow.appendChild(el);
        _speechEl = el;
        _positionSpeech();
        // 新建的元素需要继承当前 dim 状态
        _syncOverlayUI();

        // 点击 speech → 弹出回复输入框
        el.addEventListener('click', function(e) {
            if (e.target.closest('.ab-speech-close')) return;
            _showSpeechReply();
        });
    }

    function _hideSpeech() {
        _hideSpeechReply();
        if (_speechEl) { _speechEl.remove(); _speechEl = null; }
    }

    function _showSpeechReply() {
        if (_speechReplyEl) return;
        if (!_speechEl) return;

        var reply = document.createElement('div');
        reply.className = 'ab-speech-reply';

        // 关闭按钮
        var closeBtn = document.createElement('button');
        closeBtn.className = 'ab-speech-reply-close';
        closeBtn.textContent = '\u2715';
        closeBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            _hideSpeechReply();
        });

        var inp = document.createElement('textarea');
        inp.className = 'ab-speech-reply-input';
        inp.placeholder = '回复 Agent...';
        inp.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        var sendBtn = document.createElement('button');
        sendBtn.className = 'ab-speech-reply-send';
        sendBtn.textContent = '发送';

        reply.appendChild(closeBtn);
        reply.appendChild(inp);
        reply.appendChild(sendBtn);
        shadow.appendChild(reply);
        _speechReplyEl = reply;

        // 定位到 speech 下方
        var sr = _speechEl.getBoundingClientRect();
        reply.style.left = sr.left + 'px';
        reply.style.top = (sr.bottom + 8) + 'px';
        reply.style.width = sr.width + 'px';

        function submit(e) {
            if (e) { e.preventDefault(); e.stopPropagation(); }
            if (_splashActive) return;
            var text = inp.value.trim();
            if (!text) return;
            window.__bh_emit__('chat_message', {text: text});
            _bufPush({type: 'chat_message', text: text, ts: Date.now(), from: 'user'});
            _hideSpeechReply();
            _showSplash({atSpeech: true});
        }

        sendBtn.addEventListener('click', submit);
        sendBtn.addEventListener('mousedown', function(e) { e.stopPropagation(); });
        inp.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
            if (e.key === 'Escape') { _hideSpeechReply(); }
        });

        inp.focus();
    }

    function _hideSpeechReply() {
        if (_speechReplyEl) { _speechReplyEl.remove(); _speechReplyEl = null; }
    }

    function _positionSpeech() {
        if (!_speechEl || _speechEl.style.display === 'none') return;
        // 用整个 ab 容器（包含展开的菜单）而非仅 btn，避免 speech 与菜单重叠
        var ar = ab.getBoundingClientRect();
        var ax = ar.left, ay = ar.top, aw = ar.width, ah = ar.height;
        var sw = _speechEl.offsetWidth || 320, sh = _speechEl.offsetHeight || 60;
        var vw = window.innerWidth, vh = window.innerHeight;
        // tail 伸出约 10px，再留 12px 间距避免覆盖按钮
        var gap = 24;

        var rightSpace = vw - (ax + aw) - gap;
        var leftSpace = ax - gap;
        var topSpace = ay - gap;
        var bottomSpace = vh - (ay + ah) - gap;

        _speechEl.className = 'ab-speech';
        if (rightSpace >= sw) {
            // bubble RIGHT of button — anchor LEFT edge, expand right
            _speechEl.classList.add('tail-left');
            _speechEl.style.right = '';
            _speechEl.style.left = (ax + aw + gap) + 'px';
            _speechEl.style.top = Math.max(12, Math.min(ay, vh - sh - 12)) + 'px';
        } else if (leftSpace >= sw) {
            // bubble LEFT of button — anchor RIGHT edge, expand left
            _speechEl.classList.add('tail-right');
            _speechEl.style.left = '';
            _speechEl.style.right = (vw - ax + gap) + 'px';
            _speechEl.style.top = Math.max(12, Math.min(ay, vh - sh - 12)) + 'px';
        } else if (bottomSpace >= sh) {
            _speechEl.classList.add('tail-top');
            _speechEl.style.right = '';
            _speechEl.style.left = Math.max(12, Math.min(ax, vw - sw - 12)) + 'px';
            _speechEl.style.top = (ay + ah + gap) + 'px';
        } else {
            _speechEl.classList.add('tail-bottom');
            _speechEl.style.right = '';
            _speechEl.style.left = Math.max(12, Math.min(ax, vw - sw - 12)) + 'px';
            _speechEl.style.top = (ay - sh - gap) + 'px';
        }
    }

    // 窗口大小变化时重新定位
    window.addEventListener('resize', function() { _positionSpeech(); });
