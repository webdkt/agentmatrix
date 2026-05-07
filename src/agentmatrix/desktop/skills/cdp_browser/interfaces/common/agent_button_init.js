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
    // Agent Button + Hover Menu
    // ==========================================
    ab = document.createElement('div');
    ab.className = 'ab';

    btn = document.createElement('div');
    btn.className = 'ab-btn idle';
    btn.innerHTML = '<div class="ab-btn-name">' + _escHtml(_agentName) + '</div>' +
        '<div class="ab-btn-status"><div class="ab-btn-dot idle"></div><span class="ab-btn-label">IDLE</span></div>';
    ab.appendChild(btn);

    menu = document.createElement('div');
    menu.className = 'ab-menu';
    menu.innerHTML =
        '<button class="ab-menu-item" data-action="indicator"><span class="ab-menu-icon">\u25CE</span>指给 AI 看</button>' +
        '<button class="ab-menu-item" data-action="range"><span class="ab-menu-icon">\u25AD</span>选择范围</button>' +
        '<button class="ab-menu-item" data-action="instruct"><span class="ab-menu-icon">\u270E</span>给AI指示</button>';
    ab.appendChild(menu);

    // ==========================================
    // Mount
    // ==========================================
    document.body.appendChild(host);
    shadow.appendChild(ab);

    // ==========================================
    // Hover expand/collapse
    // ==========================================
    var _hoverTimeout = null;
    ab.addEventListener('mouseenter', function() {
        clearTimeout(_hoverTimeout);
        ab.classList.add('expanded');
        _syncOverlayUI();
    });
    ab.addEventListener('mouseleave', function() {
        _hoverTimeout = setTimeout(function() {
            ab.classList.remove('expanded');
            _syncOverlayUI();
        }, 200);
    });

    // ==========================================
    // Drag（基于 getBoundingClientRect，兼容 right 定位）
    // ==========================================
    var _dragging = false, _dragMoved = false, _dragOX = 0, _dragOY = 0;
    btn.addEventListener('mousedown', function(e) {
        _dragging = true;
        _dragMoved = false;
        var r = ab.getBoundingClientRect();
        _dragOX = e.clientX - r.left;
        _dragOY = e.clientY - r.top;
        e.preventDefault();
    });
    document.addEventListener('mousemove', function(e) {
        if (!_dragging) return;
        var r = ab.getBoundingClientRect();
        var dx = e.clientX - _dragOX - r.left;
        var dy = e.clientY - _dragOY - r.top;
        if (Math.abs(dx) > 2 || Math.abs(dy) > 2) _dragMoved = true;
        ab.style.left = (e.clientX - _dragOX) + 'px';
        ab.style.top = (e.clientY - _dragOY) + 'px';
        ab.style.right = 'auto';
        _positionSpeech();
    });
    document.addEventListener('mouseup', function() { _dragging = false; });

    // ==========================================
    // Menu item actions
    // ==========================================
    menu.addEventListener('click', function(e) {
        if (_dragMoved) return;
        var item = e.target.closest('.ab-menu-item');
        if (!item) return;
        ab.classList.remove('expanded');
        var action = item.dataset.action;
        if (action === 'indicator') {
            _showIndicator(Math.round(window.innerWidth / 2), Math.round(window.innerHeight / 2), '拖动准心到目标位置');
        } else if (action === 'range') {
            _showRangeSelector();
        } else if (action === 'instruct') {
            _showInstructBubble();
        }
    });

    // ==========================================
    // Escape key to cancel active tool or menu
    // ==========================================
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (_currentOverlay) {
                _clearOverlay();
            } else if (ab.classList.contains('expanded')) {
                ab.classList.remove('expanded');
                _syncOverlayUI();
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
            }
            // action_detected/started/completed 不隐藏气泡，让 think 内容持续显示
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
