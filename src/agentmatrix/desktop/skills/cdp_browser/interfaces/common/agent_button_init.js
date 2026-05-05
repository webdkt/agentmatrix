    // ==========================================
    // DOM 构建 + 事件绑定 + IIFE 结尾
    // 此文件在拼接时位于所有模块文件之后
    // ==========================================

    function __bh_init_agent_button() {
    if (!document.body) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', __bh_init_agent_button);
        } else {
            setTimeout(__bh_init_agent_button, 50);
        }
        return;
    }

    // ==========================================
    // Agent Button (default)
    // ==========================================
    ab = document.createElement('div');
    ab.className = 'ab';

    btn = document.createElement('div');
    btn.className = 'ab-btn idle';
    btn.innerHTML = '<div class="ab-btn-name">' + _escHtml(_agentName) + '</div>' +
        '<div class="ab-btn-status"><div class="ab-btn-dot idle"></div><span class="ab-btn-label">IDLE</span></div>';
    ab.appendChild(btn);

    // ==========================================
    // Action Panel
    // ==========================================
    panel = document.createElement('div');
    panel.className = 'ab-panel';
    panel.innerHTML =
        '<button class="ab-panel-btn" data-action="indicator"><span class="ab-icon">+</span> 指给 AI 看</button>' +
        '<button class="ab-panel-btn" data-action="range"><span class="ab-icon">[]</span> 选择范围</button>' +
        '<div class="ab-panel-sep"></div>' +
        '<div class="ab-panel-input-wrap"><input class="ab-panel-input" type="text" placeholder="输入指示..." /><button class="ab-panel-send">发送</button></div>';
    ab.appendChild(panel);

    // ==========================================
    // Mount
    // ==========================================
    document.body.appendChild(host);
    shadow.appendChild(ab);

    // ==========================================
    // Drag
    // ==========================================
    var _dragging = false, _dragMoved = false, _dragOX = 0, _dragOY = 0;
    btn.addEventListener('mousedown', function(e) {
        _dragging = true;
        _dragMoved = false;
        _dragOX = e.clientX - btn.offsetLeft;
        _dragOY = e.clientY - btn.offsetTop;
        e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
        if (!_dragging) return;
        var dx = e.clientX - _dragOX - btn.offsetLeft;
        var dy = e.clientY - _dragOY - btn.offsetTop;
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) _dragMoved = true;
        btn.style.left = (e.clientX - _dragOX) + 'px';
        btn.style.top = (e.clientY - _dragOY) + 'px';
        btn.style.right = 'auto';
        // Panel follows button
        panel.style.left = btn.style.left;
        panel.style.top = (btn.offsetTop + btn.offsetHeight + 8) + 'px';
        panel.style.right = 'auto';
        _positionSpeech();
    });
    document.addEventListener('mouseup', function() { _dragging = false; });

    // ==========================================
    // Agent Button click
    // ==========================================
    btn.addEventListener('click', function() {
        if (_dragMoved) return;
        _panelOpen = !_panelOpen;
        if (_panelOpen) {
            panel.classList.add('show');
            if (_speechEl) _speechEl.classList.add('dimmed');
        } else {
            _closePanel();
        }
    });

    // Close panel on outside click
    document.addEventListener('mousedown', function(e) {
        if (!_panelOpen) return;
        var path = e.composedPath();
        for (var i = 0; i < path.length; i++) {
            if (path[i] === ab) return;
        }
        _closePanel();
    });

    // ==========================================
    // Panel button actions
    // ==========================================
    panel.addEventListener('click', function(e) {
        var target = e.target.closest('.ab-panel-btn');
        if (!target) return;
        var action = target.dataset.action;
        if (action === 'indicator') {
            _closePanel();
            _showIndicator(Math.round(window.innerWidth / 2), Math.round(window.innerHeight / 2), '拖动准心到目标位置');
        } else if (action === 'range') {
            _closePanel();
            _showRangeSelector();
        }
    });

    // Text input send
    panelInput = panel.querySelector('.ab-panel-input');
    panelSend = panel.querySelector('.ab-panel-send');
    function _sendText() {
        if (_splashActive) return;
        var text = panelInput.value.trim();
        if (!text) return;
        panelInput.value = '';
        window.__bh_emit__('chat_message', {text: text});
        _bufPush({type: 'chat_message', text: text, ts: Date.now(), from: 'user'});
        _closePanel();
        _showSplash();
    }
    panelSend.addEventListener('click', _sendText);
    panelInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') _sendText(); });

    // ==========================================
    // Escape key to cancel active tool
    // ==========================================
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (_activeTool) {
                _clearTool();
            } else if (_panelOpen) {
                _closePanel();
            }
        }
    });

    // ==========================================
    // Backend event handler
    // ==========================================
    window.__bh_event_listeners__.push(function(type, data) {
        if (type === 'agent_status') {
            _setStatus((data.status || '').toUpperCase().replace(' ', '_'));
        } else if (type === 'agent_thinking') {
            _setStatus('THINKING');
        } else if (type === 'agent_done') {
            _setStatus('IDLE');
        } else if (type === 'agent_output') {
            _bufPush({type: 'agent_output', data: data, ts: Date.now()});
            if (data.type === 'think' && data.text) {
                _showSpeech(data.text);
            } else {
                _hideSpeech();
            }
        } else if (type === 'connection_status') {
            if (data.connected) {
                _setStatus('IDLE');
                var banner = shadow.querySelector('.ab-disconnect-banner');
                if (banner) banner.remove();
            } else {
                _setStatus('DISCONNECTED');
                if (!shadow.querySelector('.ab-disconnect-banner')) {
                    var b = document.createElement('div');
                    b.className = 'ab-disconnect-banner';
                    b.textContent = 'Backend disconnected \u2014 reconnecting...';
                    shadow.appendChild(b);
                }
            }
        }
    });

    // ==========================================
    // Update agent name from meta (may be set after bridge)
    // ==========================================
    var _nameInterval = setInterval(function() {
        var meta = window.__bh_agent_meta__;
        if (meta && meta.agent_name && meta.agent_name !== _agentName) {
            _agentName = meta.agent_name;
            btn.querySelector('.ab-btn-name').textContent = _agentName;
        }
    }, 2000);

    } // end __bh_init_agent_button
    __bh_init_agent_button();
})();
