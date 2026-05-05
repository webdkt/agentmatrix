/**
 * Agent Button — 统一前端交互入口。
 *
 * 替代原聊天面板 + browser_learning 工具栏。
 * 提供：Agent 状态显示、指示器、范围选择器、文本输入、提问对话框。
 *
 * 通信机制不变：__bh_emit__ (前端→后端)，__bh_event_listeners__ (后端→前端)。
 */
(function() {
    if (window.__bh_agent_button__) return;
    window.__bh_agent_button__ = true;

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
    // 消息 Buffer（最近 500 条）
    // ==========================================
    window.__bh_message_buffer__ = window.__bh_message_buffer__ || [];
    var _MAX_BUFFER = 500;
    function _bufPush(msg) {
        window.__bh_message_buffer__.push(msg);
        if (window.__bh_message_buffer__.length > _MAX_BUFFER) {
            window.__bh_message_buffer__.splice(0, window.__bh_message_buffer__.length - _MAX_BUFFER);
        }
    }

    // ==========================================
    // Shadow DOM 宿主
    // ==========================================
    var host = document.createElement('div');
    host.id = '__bh_agent_btn_host__';
    host.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:2147483647;';
    var shadow = host.attachShadow({mode: 'open'});

    // ==========================================
    // CSS
    // ==========================================
    var style = document.createElement('style');
    style.textContent = [
        ':host { all: initial; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }',

        /* ---- CSS Variables ---- */
        '.ab { --bg: rgba(255,255,255,0.92); --glass: rgba(0,0,0,0.04); --border: rgba(0,0,0,0.12);',
        '  --text: #1a1a2e; --text-dim: rgba(0,0,0,0.45); --accent: #6366f1; --accent-glow: rgba(99,102,241,0.3);',
        '  --success: #16a34a; --warning: #d97706; --danger: #dc2626;',
        '  --radius: 16px; --radius-sm: 10px; --blur: blur(20px) saturate(180%);',
        '  color: var(--text); font-size: 13px; line-height: 1.5; }',

        /* ---- Agent Button (default) ---- */
        '.ab-btn { position:fixed; top:16px; right:16px; pointer-events:auto; cursor:pointer;',
        '  background: var(--bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);',
        '  border: 1.5px solid rgba(0,0,0,0.15); border-radius: var(--radius);',
        '  padding: 12px 20px; min-width: 160px; user-select:none;',
        '  box-shadow: 0 4px 20px rgba(0,0,0,0.1), 0 1px 3px rgba(0,0,0,0.08);',
        '  transition: transform 0.2s ease, opacity 0.2s ease, box-shadow 0.2s ease; }',
        '.ab-btn:hover { transform: scale(1.02); box-shadow: 0 6px 28px rgba(0,0,0,0.14), 0 1px 3px rgba(0,0,0,0.1); }',
        '.ab-btn:active { transform: scale(0.98); }',

        /* IDLE 可交互 */
        '.ab-btn.idle { cursor:pointer; opacity:1; }',
        /* 工作状态不可交互 */
        '.ab-btn.busy { cursor:default; opacity:0.6; pointer-events:none; }',
        /* 断连 */
        '.ab-btn.disconnected { opacity:0.4; }',

        '.ab-btn-name { font-size:12px; color:var(--text-dim); margin-bottom:2px; font-weight:500; letter-spacing:0.3px; }',
        '.ab-btn-status { display:flex; align-items:center; gap:8px; }',
        '.ab-btn-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; transition: background 0.3s; }',
        '.ab-btn-dot.idle { background:var(--success); }',
        '.ab-btn-dot.thinking { background:var(--warning); animation: ab-pulse 1.5s ease-in-out infinite; }',
        '.ab-btn-dot.working { background:var(--accent); animation: ab-pulse 1.5s ease-in-out infinite; }',
        '.ab-btn-dot.waiting { background:var(--danger); animation: ab-pulse 1.5s ease-in-out infinite; }',
        '.ab-btn-dot.disconnected { background:#aaa; animation: ab-pulse 2s ease-in-out infinite; }',
        '.ab-btn-label { font-size:14px; font-weight:600; letter-spacing:0.2px; }',

        '@keyframes ab-pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }',

        /* ---- Action Panel ---- */
        '.ab-panel { position:fixed; top:80px; right:16px; pointer-events:auto;',
        '  background: var(--bg); backdrop-filter: var(--blur); -webkit-backdrop-filter: var(--blur);',
        '  border: 1.5px solid rgba(0,0,0,0.15); border-radius: var(--radius);',
        '  padding: 8px; min-width: 200px;',
        '  box-shadow: 0 8px 32px rgba(0,0,0,0.12), 0 1px 3px rgba(0,0,0,0.08);',
        '  display:none; opacity:0; transform:translateY(-8px) scale(0.96);',
        '  transition: opacity 0.2s ease, transform 0.2s ease; }',
        '.ab-panel.show { display:block; opacity:1; transform:translateY(0) scale(1); }',

        '.ab-panel-btn { display:flex; align-items:center; gap:10px; width:100%; padding:10px 14px;',
        '  background:transparent; border:none; border-radius: var(--radius-sm);',
        '  color:var(--text); font-size:13px; font-family:inherit; cursor:pointer; text-align:left;',
        '  transition: background 0.15s; }',
        '.ab-panel-btn:hover { background:var(--glass); }',
        '.ab-panel-btn .ab-icon { width:20px; text-align:center; font-size:15px; opacity:0.7; }',

        '.ab-panel-sep { height:1px; background:var(--border); margin:4px 8px; }',

        '.ab-panel-input-wrap { display:flex; gap:6px; padding:8px 6px 4px; }',
        '.ab-panel-input { flex:1; background:rgba(0,0,0,0.03); border:1px solid var(--border);',
        '  border-radius: var(--radius-sm); padding:8px 12px; color:var(--text); font-size:13px;',
        '  font-family:inherit; outline:none; transition: border-color 0.2s; }',
        '.ab-panel-input:focus { border-color:var(--accent); }',
        '.ab-panel-input::placeholder { color:var(--text-dim); }',
        '.ab-panel-send { background:var(--accent); color:#fff; border:none; border-radius: var(--radius-sm);',
        '  padding:8px 16px; font-size:13px; font-weight:600; font-family:inherit; cursor:pointer;',
        '  transition: background 0.15s; }',
        '.ab-panel-send:hover { background:#5558e6; }',

        /* ---- Indicator ---- */
        '.ab-crosshair { position:fixed; width:200px; height:200px; transform:translate(-50%,-50%); pointer-events:none; z-index:2147483646; }',
        '.ab-ring { position:absolute; left:50%; top:50%; width:48px; height:48px; transform:translate(-50%,-50%);',
        '  border:3px solid #6366f1; border-radius:50%; box-shadow:0 0 20px rgba(99,102,241,0.5), 0 0 60px rgba(99,102,241,0.2); }',
        '.ab-seg { position:absolute; background:#6366f1; box-shadow:0 0 6px rgba(99,102,241,0.4); }',
        '.ab-seg.h { height:3px; width:32px; top:50%; transform:translateY(-50%); }',
        '.ab-seg.v { width:3px; height:32px; left:50%; transform:translateX(-50%); }',
        '.ab-seg.h.l { right:calc(50% + 28px); }',
        '.ab-seg.h.r { left:calc(50% + 28px); }',
        '.ab-seg.v.t { bottom:calc(50% + 28px); }',
        '.ab-seg.v.b { top:calc(50% + 28px); }',
        '.ab-crosshair-handle { position:absolute; left:50%; top:50%; width:60px; height:60px;',
        '  transform:translate(-50%,-50%); border-radius:50%; cursor:grab; pointer-events:auto; background:transparent; }',
        '.ab-crosshair-handle:active { cursor:grabbing; }',

        /* ---- Range Selector ---- */
        '.ab-range { position:fixed; border:3px solid #6366f1; border-radius:6px;',
        '  background:rgba(99,102,241,0.06); z-index:2147483645; cursor:move; box-sizing:border-box;',
        '  user-select:none; pointer-events:auto;',
        '  box-shadow:0 0 0 1px #fff, 0 0 0 3px rgba(0,0,0,0.4); }',
        '.ab-range-handle { position:absolute; width:14px; height:14px; background:#fff;',
        '  border:2.5px solid #6366f1; border-radius:3px; z-index:2147483647; box-sizing:border-box; pointer-events:auto;',
        '  box-shadow:0 0 0 1px #fff, 0 0 0 2px rgba(0,0,0,0.3), 0 2px 6px rgba(0,0,0,0.2); }',
        '.ab-range-handle.tl { top:-7px; left:-7px; cursor:nw-resize; }',
        '.ab-range-handle.tc { top:-7px; left:50%; margin-left:-7px; cursor:n-resize; }',
        '.ab-range-handle.tr { top:-7px; right:-7px; cursor:ne-resize; }',
        '.ab-range-handle.ml { top:50%; left:-7px; margin-top:-7px; cursor:w-resize; }',
        '.ab-range-handle.mr { top:50%; right:-7px; margin-top:-7px; cursor:e-resize; }',
        '.ab-range-handle.bl { bottom:-7px; left:-7px; cursor:sw-resize; }',
        '.ab-range-handle.bc { bottom:-7px; left:50%; margin-left:-7px; cursor:s-resize; }',
        '.ab-range-handle.br { bottom:-7px; right:-7px; cursor:se-resize; }',

        /* ---- Tool Bubble ---- */
        '.ab-bubble { position:fixed; z-index:2147483646; background:rgba(255,255,255,0.95); backdrop-filter:var(--blur);',
        '  -webkit-backdrop-filter:var(--blur); border-radius:var(--radius); border:1.5px solid rgba(0,0,0,0.12);',
        '  box-shadow:0 8px 32px rgba(0,0,0,0.12), 0 1px 3px rgba(0,0,0,0.08); padding:16px 18px; min-width:220px; max-width:340px;',
        '  font-size:14px; color:var(--text); line-height:1.5; pointer-events:auto; }',
        '.ab-bubble-text { margin-bottom:10px; white-space:pre-wrap; word-break:break-word; font-weight:500; font-size:13px; color:var(--text-dim); }',
        '.ab-bubble-input { width:100%; box-sizing:border-box; padding:8px 10px;',
        '  background:rgba(0,0,0,0.03); border:1px solid var(--border); border-radius:var(--radius-sm);',
        '  font-size:14px; font-family:inherit; outline:none; margin-bottom:10px; color:var(--text); }',
        '.ab-bubble-input:focus { border-color:var(--accent); }',
        '.ab-bubble-input::placeholder { color:var(--text-dim); }',
        '.ab-bubble-ok { display:block; width:100%; padding:8px 0; color:#fff; border:none;',
        '  border-radius:var(--radius-sm); font-size:14px; font-weight:600; font-family:inherit; cursor:pointer;',
        '  transition: background 0.15s; }',
        '.ab-bubble-ok.indicator { background:var(--accent); }',
        '.ab-bubble-ok.indicator:hover { background:#5558e6; }',
        '.ab-bubble-ok.range { background:var(--accent); }',
        '.ab-bubble-ok.range:hover { background:#5558e6; }',

        /* ---- Ask Dialog ---- */
        '.ab-dialog-overlay { position:fixed; top:0; left:0; right:0; bottom:0;',
        '  background:rgba(0,0,0,0.3); pointer-events:auto; z-index:2147483646;',
        '  display:flex; align-items:center; justify-content:center; }',
        '.ab-dialog { background:var(--bg); backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);',
        '  border:1.5px solid rgba(0,0,0,0.12); border-radius:var(--radius);',
        '  box-shadow:0 16px 48px rgba(0,0,0,0.15); min-width:340px; max-width:480px; overflow:hidden; }',
        '.ab-dialog-header { display:flex; align-items:center; padding:12px 16px;',
        '  border-bottom:1px solid var(--border); }',
        '.ab-dialog-title { flex:1; font-weight:600; font-size:13px; color:var(--text-dim); letter-spacing:0.3px; }',
        '.ab-dialog-close { background:none; border:none; color:var(--text-dim); cursor:pointer;',
        '  font-size:16px; padding:2px 6px; line-height:1; border-radius:6px; transition:color 0.15s; }',
        '.ab-dialog-close:hover { color:var(--danger); background:rgba(220,38,38,0.08); }',
        '.ab-dialog-body { padding:16px; max-height:60vh; overflow-y:auto; }',
        '.ab-dialog-question { font-size:15px; line-height:1.6; margin-bottom:14px; white-space:pre-wrap; word-break:break-word; }',
        '.ab-dialog-choice { display:flex; align-items:center; padding:6px 0; cursor:pointer; }',
        '.ab-dialog-choice input[type="radio"], .ab-dialog-choice input[type="checkbox"] {',
        '  appearance:none; -webkit-appearance:none; width:18px; height:18px; border:2px solid rgba(0,0,0,0.2);',
        '  border-radius:4px; margin-right:10px; cursor:pointer; position:relative; flex-shrink:0;',
        '  transition:border-color 0.15s, background 0.15s; }',
        '.ab-dialog-choice input[type="radio"] { border-radius:50%; }',
        '.ab-dialog-choice input:checked { border-color:var(--accent); background:var(--accent); }',
        '.ab-dialog-choice input:checked::after { content:""; position:absolute; }',
        '.ab-dialog-choice input[type="radio"]:checked::after { width:6px; height:6px; background:#fff;',
        '  border-radius:50%; top:50%; left:50%; transform:translate(-50%,-50%); }',
        '.ab-dialog-choice label { cursor:pointer; flex:1; font-size:14px; }',
        '.ab-dialog-divider { height:1px; background:var(--border); margin:12px 0; }',
        '.ab-dialog-input-label { font-size:12px; color:var(--text-dim); margin-bottom:6px; }',
        '.ab-dialog-textarea { width:100%; box-sizing:border-box; padding:8px 10px;',
        '  background:rgba(0,0,0,0.03); border:1px solid var(--border); border-radius:var(--radius-sm);',
        '  font-size:14px; font-family:inherit; outline:none; resize:vertical; min-height:60px; color:var(--text); }',
        '.ab-dialog-textarea:focus { border-color:var(--accent); }',
        '.ab-dialog-textarea::placeholder { color:var(--text-dim); }',
        '.ab-dialog-footer { padding:12px 16px; border-top:1px solid var(--border); display:flex; justify-content:flex-end; }',
        '.ab-dialog-submit { padding:8px 24px; background:var(--accent); color:#fff; border:none;',
        '  border-radius:var(--radius-sm); font-size:14px; font-weight:600; cursor:pointer; font-family:inherit;',
        '  transition: background 0.15s; }',
        '.ab-dialog-submit:hover { background:#5558e6; }',

        /* ---- Disconnect Banner ---- */
        '.ab-disconnect-banner { position:fixed; top:0; left:0; right:0; z-index:2147483647;',
        '  background:rgba(220,38,38,0.92); backdrop-filter:var(--blur); color:#fff; text-align:center;',
        '  padding:6px; font-size:12px; pointer-events:auto; letter-spacing:0.3px; }',
    ].join('\n');
    shadow.appendChild(style);

    // ==========================================
    // State
    // ==========================================
    var _status = 'IDLE';      // IDLE | THINKING | WORKING | WAITING_FOR_USER | DISCONNECTED
    var _agentName = (window.__bh_agent_meta__ && window.__bh_agent_meta__.agent_name) || 'Agent';
    var _panelOpen = false;
    var _activeTool = null;    // 'indicator' | 'range' | null
    var _indicatorEl = null, _indicatorBubble = null;
    var _rangeEl = null, _rangeBubble = null;
    var _askHost = null;

    // ==========================================
    // Agent Button (default)
    // ==========================================
    var ab = document.createElement('div');
    ab.className = 'ab';

    var btn = document.createElement('div');
    btn.className = 'ab-btn idle';
    btn.innerHTML = '<div class="ab-btn-name">' + _escHtml(_agentName) + '</div>' +
        '<div class="ab-btn-status"><div class="ab-btn-dot idle"></div><span class="ab-btn-label">IDLE</span></div>';
    ab.appendChild(btn);

    // ==========================================
    // Action Panel
    // ==========================================
    var panel = document.createElement('div');
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
    });
    document.addEventListener('mouseup', function() { _dragging = false; });

    // ==========================================
    // Helpers
    // ==========================================
    function _escHtml(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function _setStatus(s) {
        _status = s;
        var dot = btn.querySelector('.ab-btn-dot');
        var label = btn.querySelector('.ab-btn-label');
        var map = {
            'IDLE':            { cls: 'idle',        text: 'IDLE' },
            'THINKING':        { cls: 'thinking',    text: 'THINKING' },
            'WORKING':         { cls: 'working',     text: 'WORKING' },
            'WAITING_FOR_USER':{ cls: 'waiting',     text: 'WAITING' },
            'DISCONNECTED':    { cls: 'disconnected',text: 'DISCONNECTED' },
        };
        var m = map[s] || { cls: 'idle', text: s || 'UNKNOWN' };
        dot.className = 'ab-btn-dot ' + m.cls;
        label.textContent = m.text;

        if (s === 'IDLE') {
            btn.className = 'ab-btn idle';
        } else if (s === 'DISCONNECTED') {
            btn.className = 'ab-btn disconnected';
        } else {
            btn.className = 'ab-btn busy';
        }
    }

    function _closePanel() {
        _panelOpen = false;
        panel.classList.remove('show');
    }

    function _clearTool() {
        if (_indicatorEl) { _indicatorEl.remove(); _indicatorEl = null; }
        if (_indicatorBubble) { _indicatorBubble.remove(); _indicatorBubble = null; }
        if (_rangeEl) { _rangeEl.remove(); _rangeEl = null; }
        if (_rangeBubble) { _rangeBubble.remove(); _rangeBubble = null; }
        _activeTool = null;
    }

    // ==========================================
    // Agent Button click
    // ==========================================
    btn.addEventListener('click', function() {
        if (_status !== 'IDLE' || _dragMoved) return;
        _panelOpen = !_panelOpen;
        if (_panelOpen) {
            panel.classList.add('show');
        } else {
            _closePanel();
        }
    });

    // Close panel on outside click
    document.addEventListener('mousedown', function(e) {
        if (!_panelOpen) return;
        // Check if click is inside our shadow DOM
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
    var panelInput = panel.querySelector('.ab-panel-input');
    var panelSend = panel.querySelector('.ab-panel-send');
    function _sendText() {
        var text = panelInput.value.trim();
        if (!text) return;
        panelInput.value = '';
        window.__bh_emit__('chat_message', {text: text});
        _bufPush({type: 'chat_message', text: text, ts: Date.now(), from: 'user'});
        _closePanel();
        _setStatus('THINKING');
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
    // Indicator
    // ==========================================
    function _showIndicator(initX, initY, infoText) {
        _clearTool();
        _activeTool = 'indicator';

        var crosshair = document.createElement('div');
        crosshair.className = 'ab-crosshair';
        crosshair.style.left = initX + 'px';
        crosshair.style.top = initY + 'px';

        var ring = document.createElement('div');
        ring.className = 'ab-ring';
        crosshair.appendChild(ring);

        ['h l', 'h r', 'v t', 'v b'].forEach(function(cls) {
            var seg = document.createElement('div');
            seg.className = 'ab-seg ' + cls;
            crosshair.appendChild(seg);
        });

        var handle = document.createElement('div');
        handle.className = 'ab-crosshair-handle';
        crosshair.appendChild(handle);

        _indicatorEl = crosshair;
        shadow.appendChild(crosshair);

        // Bubble
        var bubble = document.createElement('div');
        bubble.className = 'ab-bubble';
        var textEl = document.createElement('div');
        textEl.className = 'ab-bubble-text';
        textEl.textContent = infoText;
        var inp = document.createElement('input');
        inp.className = 'ab-bubble-input';
        inp.type = 'text';
        inp.placeholder = '输入描述...';
        var okBtn = document.createElement('button');
        okBtn.className = 'ab-bubble-ok indicator';
        okBtn.textContent = 'OK';
        bubble.appendChild(textEl);
        bubble.appendChild(inp);
        bubble.appendChild(okBtn);
        _indicatorBubble = bubble;
        shadow.appendChild(bubble);

        function posBubble() {
            var cr = crosshair.getBoundingClientRect();
            var cx = cr.left + cr.width / 2, cy = cr.top + cr.height / 2;
            var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
            var vw = window.innerWidth, vh = window.innerHeight;
            var bx = cx + 70, by = cy - bh / 2;
            if (bx + bw > vw - 12) bx = cx - 70 - bw;
            if (by < 12) by = 12;
            if (by + bh > vh - 12) by = vh - 12 - bh;
            bx = Math.max(12, bx);
            by = Math.max(12, by);
            bubble.style.left = bx + 'px';
            bubble.style.top = by + 'px';
        }
        posBubble();

        // Drag
        var dragging = false, oX = 0, oY = 0;
        handle.addEventListener('mousedown', function(e) {
            dragging = true;
            var cr = crosshair.getBoundingClientRect();
            oX = e.clientX - (cr.left + cr.width / 2);
            oY = e.clientY - (cr.top + cr.height / 2);
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            crosshair.style.left = (e.clientX - oX) + 'px';
            crosshair.style.top = (e.clientY - oY) + 'px';
            posBubble();
        });
        document.addEventListener('mouseup', function() { dragging = false; });

        // Submit
        function submit() {
            var cr = crosshair.getBoundingClientRect();
            var x = Math.round(cr.left + cr.width / 2);
            var y = Math.round(cr.top + cr.height / 2);
            // Mark element
            var old = document.querySelector('[__bh_marked__]');
            if (old) old.removeAttribute('__bh_marked__');
            var h = document.getElementById('__bh_agent_btn_host__');
            if (h) h.style.display = 'none';
            var el = document.elementFromPoint(x, y);
            if (h) h.style.display = '';
            if (el) el.setAttribute('__bh_marked__', '1');

            _clearTool();
            _setStatus('THINKING');

            window.__bh_emit__('indicator_result', {x: x, y: y, text: inp.value});
        }
        okBtn.addEventListener('click', submit);
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter') submit(); });
        inp.focus();
    }

    // ==========================================
    // Range Selector
    // ==========================================
    function _showRangeSelector() {
        _clearTool();
        _activeTool = 'range';

        var INIT_W = 300, INIT_H = 200;
        var INIT_X = Math.round(window.innerWidth / 2 - INIT_W / 2);
        var INIT_Y = Math.round(window.innerHeight / 2 - INIT_H / 2);

        var rect = document.createElement('div');
        rect.className = 'ab-range';
        rect.style.left = INIT_X + 'px';
        rect.style.top = INIT_Y + 'px';
        rect.style.width = INIT_W + 'px';
        rect.style.height = INIT_H + 'px';

        ['tl', 'tc', 'tr', 'ml', 'mr', 'bl', 'bc', 'br'].forEach(function(p) {
            var h = document.createElement('div');
            h.className = 'ab-range-handle ' + p;
            h.dataset.pos = p;
            rect.appendChild(h);
        });

        _rangeEl = rect;
        shadow.appendChild(rect);

        // Bubble
        var bubble = document.createElement('div');
        bubble.className = 'ab-bubble';
        var textEl = document.createElement('div');
        textEl.className = 'ab-bubble-text';
        textEl.textContent = '拖动边角调整大小，拖动边框移动位置';
        var inp = document.createElement('input');
        inp.className = 'ab-bubble-input';
        inp.type = 'text';
        inp.placeholder = '描述这个区域...';
        var okBtn = document.createElement('button');
        okBtn.className = 'ab-bubble-ok range';
        okBtn.textContent = 'OK';
        bubble.appendChild(textEl);
        bubble.appendChild(inp);
        bubble.appendChild(okBtn);
        _rangeBubble = bubble;
        shadow.appendChild(bubble);

        function posBubble() {
            var rl = parseFloat(rect.style.left), rt = parseFloat(rect.style.top);
            var rw = parseFloat(rect.style.width), rh = parseFloat(rect.style.height);
            var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
            var bx = rl + rw + 18, by = rt + rh / 2 - bh / 2;
            if (bx + bw > window.innerWidth - 12) bx = rl - 18 - bw;
            if (by < 12) by = 12;
            if (by + bh > window.innerHeight - 12) by = window.innerHeight - 12 - bh;
            bx = Math.max(12, bx);
            by = Math.max(12, by);
            bubble.style.left = bx + 'px';
            bubble.style.top = by + 'px';
        }
        posBubble();

        // Resize & drag
        var mode = 'none', resizePos = '';
        var smx, smy, sml, smt, smw, smh, dragOX, dragOY;
        var MIN_W = 160, MIN_H = 100;

        rect.addEventListener('mousedown', function(e) {
            var handle = e.target.closest('.ab-range-handle');
            if (handle) {
                mode = 'resize'; resizePos = handle.dataset.pos;
                smx = e.clientX; smy = e.clientY;
                sml = parseFloat(rect.style.left); smt = parseFloat(rect.style.top);
                smw = parseFloat(rect.style.width); smh = parseFloat(rect.style.height);
                e.stopPropagation(); e.preventDefault();
            } else {
                mode = 'drag';
                dragOX = e.clientX - parseFloat(rect.style.left);
                dragOY = e.clientY - parseFloat(rect.style.top);
                e.preventDefault();
            }
        });
        document.addEventListener('mousemove', function(e) {
            if (mode === 'resize') {
                var dx = e.clientX - smx, dy = e.clientY - smy;
                var nl = sml, nt = smt, nw = smw, nh = smh;
                if (resizePos.indexOf('l') >= 0) { nl = sml + dx; nw = smw - dx; }
                if (resizePos.indexOf('r') >= 0) { nw = smw + dx; }
                if (resizePos.indexOf('t') >= 0) { nt = smt + dy; nh = smh - dy; }
                if (resizePos.indexOf('b') >= 0) { nh = smh + dy; }
                if (nw < MIN_W) { if (resizePos.indexOf('l') >= 0) nl = sml + smw - MIN_W; nw = MIN_W; }
                if (nh < MIN_H) { if (resizePos.indexOf('t') >= 0) nt = smt + smh - MIN_H; nh = MIN_H; }
                rect.style.left = nl + 'px'; rect.style.top = nt + 'px';
                rect.style.width = nw + 'px'; rect.style.height = nh + 'px';
                posBubble();
            }
            if (mode === 'drag') {
                rect.style.left = (e.clientX - dragOX) + 'px';
                rect.style.top = (e.clientY - dragOY) + 'px';
                posBubble();
            }
        });
        document.addEventListener('mouseup', function() { mode = 'none'; });

        // Submit
        function submit() {
            _clearTool();
            _setStatus('THINKING');

            window.__bh_emit__('range_result', {
                x: Math.round(parseFloat(rect.style.left)),
                y: Math.round(parseFloat(rect.style.top)),
                width: Math.round(parseFloat(rect.style.width)),
                height: Math.round(parseFloat(rect.style.height)),
                text: inp.value
            });
        }
        okBtn.addEventListener('click', submit);
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter') submit(); });
        inp.focus();
    }

    // ==========================================
    // Ask Dialog
    // ==========================================
    window.__bh_ask_user__ = function(config) {
        // Remove existing
        if (_askHost) { _askHost.remove(); _askHost = null; }

        var question = config.question || '请输入';
        var choices = config.choices || [];
        var multi = !!config.multi;

        var overlay = document.createElement('div');
        overlay.className = 'ab-dialog-overlay';

        var dialog = document.createElement('div');
        dialog.className = 'ab-dialog';

        // Header
        var header = document.createElement('div');
        header.className = 'ab-dialog-header';
        var title = document.createElement('span');
        title.className = 'ab-dialog-title';
        title.textContent = 'Agent 提问';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'ab-dialog-close';
        closeBtn.textContent = '\u2715';
        header.appendChild(title);
        header.appendChild(closeBtn);
        dialog.appendChild(header);

        // Body
        var body = document.createElement('div');
        body.className = 'ab-dialog-body';

        var q = document.createElement('div');
        q.className = 'ab-dialog-question';
        q.textContent = question;
        body.appendChild(q);

        var choiceGroup = null;
        if (choices.length > 0) {
            choiceGroup = document.createElement('div');
            choices.forEach(function(choice, idx) {
                var item = document.createElement('div');
                item.className = 'ab-dialog-choice';
                var input = document.createElement('input');
                input.type = multi ? 'checkbox' : 'radio';
                input.name = '__bh_ask_choice__';
                input.value = choice;
                input.id = '__bh_choice_' + idx;
                var label = document.createElement('label');
                label.htmlFor = input.id;
                label.textContent = choice;
                item.appendChild(input);
                item.appendChild(label);
                choiceGroup.appendChild(item);
            });
            body.appendChild(choiceGroup);
        }

        var divider = document.createElement('div');
        divider.className = 'ab-dialog-divider';
        body.appendChild(divider);

        var inputLabel = document.createElement('div');
        inputLabel.className = 'ab-dialog-input-label';
        inputLabel.textContent = choices.length > 0 ? '补充说明（可选）' : '请输入你的回答';
        body.appendChild(inputLabel);

        var textInput = document.createElement('textarea');
        textInput.className = 'ab-dialog-textarea';
        textInput.placeholder = '输入内容...';
        body.appendChild(textInput);

        dialog.appendChild(body);

        // Footer
        var footer = document.createElement('div');
        footer.className = 'ab-dialog-footer';
        var submitBtn = document.createElement('button');
        submitBtn.className = 'ab-dialog-submit';
        submitBtn.textContent = '提交';
        footer.appendChild(submitBtn);
        dialog.appendChild(footer);

        overlay.appendChild(dialog);
        shadow.appendChild(overlay);
        _askHost = overlay;

        // Close
        function close() {
            if (_askHost) { _askHost.remove(); _askHost = null; }
            window.__bh_emit__('user_answer', {choices: [], text: '', cancelled: true});
        }
        closeBtn.addEventListener('click', close);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) close();
        });

        // Submit
        function submit() {
            var selected = [];
            if (choiceGroup) {
                choiceGroup.querySelectorAll('input:checked').forEach(function(inp) {
                    selected.push(inp.value);
                });
            }
            var text = textInput.value.trim();
            if (choices.length === 0 && !text) {
                textInput.style.borderColor = 'var(--danger)';
                textInput.focus();
                return;
            }
            window.__bh_emit__('user_answer', {choices: selected, text: text, cancelled: false});
            if (_askHost) { _askHost.remove(); _askHost = null; }
        }
        submitBtn.addEventListener('click', submit);
        textInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey && choices.length === 0) {
                e.preventDefault();
                submit();
            }
        });

        if (choices.length === 0) textInput.focus();
    };

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
        } else if (type === 'connection_status') {
            if (data.connected) {
                _setStatus('IDLE');
                // Remove disconnect banner
                var banner = shadow.querySelector('.ab-disconnect-banner');
                if (banner) banner.remove();
            } else {
                _setStatus('DISCONNECTED');
                // Show disconnect banner
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
