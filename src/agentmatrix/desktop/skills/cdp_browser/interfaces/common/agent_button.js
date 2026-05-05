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
        ':host { all: initial; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;',
        '  --bg: rgba(255,255,255,0.92); --glass: rgba(0,0,0,0.04); --border: rgba(0,0,0,0.12);',
        '  --text: #1a1a2e; --text-dim: rgba(0,0,0,0.45); --accent: #6366f1; --accent-glow: rgba(99,102,241,0.3);',
        '  --success: #16a34a; --warning: #d97706; --danger: #dc2626;',
        '  --radius: 16px; --radius-sm: 10px; --blur: blur(20px) saturate(180%); }',

        '.ab { color: var(--text); font-size: 13px; line-height: 1.5; }',

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
        /* 工作状态 — 视觉变化但仍可交互 */
        '.ab-btn.busy { cursor:pointer; }',
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
        '.ab-ring { position:absolute; left:50%; top:50%; width:52px; height:52px; transform:translate(-50%,-50%);',
        '  border:4px solid #6366f1; border-radius:50%;',
        '  box-shadow:0 0 0 3px rgba(255,255,255,0.9), 0 0 0 6px rgba(99,102,241,0.4),',
        '    0 0 24px rgba(99,102,241,0.6), 0 0 60px rgba(99,102,241,0.25), inset 0 0 12px rgba(99,102,241,0.15); }',
        '.ab-seg { position:absolute; background:#6366f1;',
        '  box-shadow:0 0 0 2px rgba(255,255,255,0.9), 0 0 8px rgba(99,102,241,0.5); }',
        '.ab-seg.h { height:4px; width:36px; top:50%; transform:translateY(-50%); border-radius:2px; }',
        '.ab-seg.v { width:4px; height:36px; left:50%; transform:translateX(-50%); border-radius:2px; }',
        '.ab-seg.h.l { right:calc(50% + 30px); }',
        '.ab-seg.h.r { left:calc(50% + 30px); }',
        '.ab-seg.v.t { bottom:calc(50% + 30px); }',
        '.ab-seg.v.b { top:calc(50% + 30px); }',
        '.ab-crosshair-handle { position:absolute; left:50%; top:50%; width:60px; height:60px;',
        '  transform:translate(-50%,-50%); border-radius:50%; cursor:grab; pointer-events:auto; background:transparent; }',
        '.ab-crosshair-handle:active { cursor:grabbing; }',

        /* ---- Range Selector ---- */
        '.ab-range { position:fixed; border:4px solid #6366f1; border-radius:8px;',
        '  background:rgba(99,102,241,0.08); z-index:2147483645; cursor:move; box-sizing:border-box;',
        '  user-select:none; pointer-events:auto;',
        '  box-shadow:0 0 0 2px rgba(255,255,255,0.8), 0 0 0 5px rgba(99,102,241,0.35), 0 0 20px rgba(99,102,241,0.15); }',
        '.ab-range-handle { position:absolute; width:16px; height:16px; background:#fff;',
        '  border:3px solid #6366f1; border-radius:4px; z-index:2147483647; box-sizing:border-box; pointer-events:auto;',
        '  box-shadow:0 0 0 2px rgba(255,255,255,0.8), 0 0 0 4px rgba(99,102,241,0.3), 0 2px 8px rgba(0,0,0,0.2); }',
        '.ab-range-handle.tl { top:-8px; left:-8px; cursor:nw-resize; }',
        '.ab-range-handle.tc { top:-8px; left:50%; margin-left:-8px; cursor:n-resize; }',
        '.ab-range-handle.tr { top:-8px; right:-8px; cursor:ne-resize; }',
        '.ab-range-handle.ml { top:50%; left:-8px; margin-top:-8px; cursor:w-resize; }',
        '.ab-range-handle.mr { top:50%; right:-8px; margin-top:-8px; cursor:e-resize; }',
        '.ab-range-handle.bl { bottom:-8px; left:-8px; cursor:sw-resize; }',
        '.ab-range-handle.bc { bottom:-8px; left:50%; margin-left:-8px; cursor:s-resize; }',
        '.ab-range-handle.br { bottom:-8px; right:-8px; cursor:se-resize; }',

        /* ---- Tool Bubble ---- */
        '.ab-bubble { position:fixed; z-index:2147483646; background:rgba(255,255,255,0.95); backdrop-filter:var(--blur);',
        '  -webkit-backdrop-filter:var(--blur); border-radius:18px; border:1.5px solid rgba(0,0,0,0.12);',
        '  box-shadow:0 8px 32px rgba(0,0,0,0.12), 0 1px 3px rgba(0,0,0,0.08); padding:16px; min-width:280px; max-width:400px;',
        '  font-size:14px; color:var(--text); line-height:1.5; pointer-events:auto; }',
        '.ab-bubble-row { display:flex; gap:10px; align-items:flex-end; }',
        '.ab-bubble-input { flex:1; box-sizing:border-box; padding:14px 16px;',
        '  background:rgba(0,0,0,0.04); border:1.5px solid rgba(0,0,0,0.15); border-radius:14px;',
        '  font-size:15px; font-family:inherit; outline:none; color:var(--text); resize:none;',
        '  min-height:72px; max-height:160px; line-height:1.5; transition:border-color 0.2s; }',
        '.ab-bubble-input:focus { border-color:var(--accent); box-shadow:0 0 0 3px rgba(99,102,241,0.12); }',
        '.ab-bubble-input::placeholder { color:rgba(0,0,0,0.35); }',
        '.ab-bubble-send { width:44px; height:44px; border-radius:12px; background:var(--accent); color:#fff;',
        '  border:2px solid rgba(255,255,255,0.3); cursor:pointer; display:flex; align-items:center; justify-content:center; flex-shrink:0;',
        '  box-shadow:0 2px 8px rgba(99,102,241,0.35); transition:background 0.15s, transform 0.1s, box-shadow 0.15s; }',
        '.ab-bubble-send:hover { background:#5558e6; }',
        '.ab-bubble-send:active { transform:scale(0.92); }',
        '.ab-bubble-send:disabled { opacity:0.4; cursor:default; transform:none; }',
        '.ab-bubble-send svg { width:20px; height:20px; }',

        /* ---- Splash Transition ---- */
        '.ab-splash-overlay { position:fixed; top:0; left:0; right:0; bottom:0; z-index:2147483647;',
        '  display:flex; align-items:center; justify-content:center; pointer-events:auto; }',
        '.ab-splash { background:rgba(255,255,255,0.95); backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);',
        '  border:1.5px solid rgba(0,0,0,0.12); border-radius:18px; padding:28px 36px; min-width:240px;',
        '  box-shadow:0 12px 40px rgba(0,0,0,0.14), 0 1px 3px rgba(0,0,0,0.08);',
        '  display:flex; flex-direction:column; align-items:center; gap:12px;',
        '  animation:ab-splash-in 0.25s ease-out; }',
        '.ab-splash-spinner { width:28px; height:28px; border:3px solid rgba(99,102,241,0.2);',
        '  border-top-color:var(--accent); border-radius:50%; animation:ab-spin 0.8s linear infinite; }',
        '.ab-splash-text { font-size:15px; font-weight:600; color:var(--text); letter-spacing:0.2px; }',
        '.ab-splash-check { width:28px; height:28px; background:var(--success); border-radius:50%;',
        '  display:flex; align-items:center; justify-content:center; color:#fff; font-size:16px; font-weight:700;',
        '  animation:ab-splash-pop 0.3s ease-out; }',
        '@keyframes ab-spin { to { transform:rotate(360deg); } }',
        '@keyframes ab-splash-in { from { opacity:0; transform:scale(0.9); } to { opacity:1; transform:scale(1); } }',
        '@keyframes ab-splash-pop { 0% { transform:scale(0); } 60% { transform:scale(1.2); } 100% { transform:scale(1); } }',

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

        /* ---- Speech Bubble ---- */
        '.ab-speech { position:fixed; z-index:2147483645; width:320px; max-height:400px;',
        '  background:rgba(255,255,255,0.95); backdrop-filter:var(--blur); -webkit-backdrop-filter:var(--blur);',
        '  border:1.5px solid rgba(0,0,0,0.15); border-radius:14px;',
        '  padding:12px 16px; padding-right:32px; font-size:14px; line-height:1.6;',
        '  color:var(--text); pointer-events:auto; overflow-y:auto;',
        '  box-shadow:0 4px 16px rgba(0,0,0,0.1), 0 1px 3px rgba(0,0,0,0.06);',
        '  animation:ab-speech-in 0.2s ease-out; transition:opacity 0.2s; }',
        '.ab-speech.dimmed { opacity:0.15; pointer-events:none; z-index:2147483644; }',
        '@keyframes ab-speech-in { from { opacity:0; transform:scale(0.95); } to { opacity:1; transform:scale(1); } }',
        /* Tail uses two pseudo-elements: ::before for border, ::after for fill */
        '.ab-speech-tail { position:absolute; width:0; height:0; }',
        '.ab-speech-tail::before, .ab-speech-tail::after { content:""; position:absolute; width:0; height:0; }',
        /* tail-left: bubble is left of button, tail points right */
        '.ab-speech.tail-left .ab-speech-tail { right:-18px; top:14px; }',
        '.ab-speech.tail-left .ab-speech-tail::before { left:-1px; top:-11px;',
        '  border-left:20px solid rgba(0,0,0,0.15); border-top:11px solid transparent; border-bottom:11px solid transparent; }',
        '.ab-speech.tail-left .ab-speech-tail::after { left:1px; top:-9px;',
        '  border-left:17px solid rgba(255,255,255,0.95); border-top:9px solid transparent; border-bottom:9px solid transparent; }',
        /* tail-right: bubble is right of button, tail points left */
        '.ab-speech.tail-right .ab-speech-tail { left:-18px; top:14px; }',
        '.ab-speech.tail-right .ab-speech-tail::before { right:-1px; top:-11px;',
        '  border-right:20px solid rgba(0,0,0,0.15); border-top:11px solid transparent; border-bottom:11px solid transparent; }',
        '.ab-speech.tail-right .ab-speech-tail::after { right:1px; top:-9px;',
        '  border-right:17px solid rgba(255,255,255,0.95); border-top:9px solid transparent; border-bottom:9px solid transparent; }',
        /* tail-top: bubble is above button, tail points down */
        '.ab-speech.tail-top .ab-speech-tail { bottom:-18px; left:24px; }',
        '.ab-speech.tail-top .ab-speech-tail::before { left:-11px; top:-1px;',
        '  border-bottom:20px solid rgba(0,0,0,0.15); border-left:11px solid transparent; border-right:11px solid transparent; }',
        '.ab-speech.tail-top .ab-speech-tail::after { left:-9px; top:1px;',
        '  border-bottom:17px solid rgba(255,255,255,0.95); border-left:9px solid transparent; border-right:9px solid transparent; }',
        /* tail-bottom: bubble is below button, tail points up */
        '.ab-speech.tail-bottom .ab-speech-tail { top:-18px; left:24px; }',
        '.ab-speech.tail-bottom .ab-speech-tail::before { left:-11px; bottom:-1px;',
        '  border-top:20px solid rgba(0,0,0,0.15); border-left:11px solid transparent; border-right:11px solid transparent; }',
        '.ab-speech.tail-bottom .ab-speech-tail::after { left:-9px; bottom:1px;',
        '  border-top:17px solid rgba(255,255,255,0.95); border-left:9px solid transparent; border-right:9px solid transparent; }',
        '.ab-speech-close { position:absolute; top:6px; right:8px; background:none; border:none;',
        '  cursor:pointer; color:rgba(0,0,0,0.3); font-size:16px; line-height:1; padding:4px;',
        '  border-radius:4px; transition:color 0.15s; z-index:1; }',
        '.ab-speech-close:hover { color:var(--danger); }',
        '.ab-speech-text { word-break:break-word; }',
        '.ab-speech-text.clamped { display:-webkit-box; -webkit-line-clamp:5;',
        '  -webkit-box-orient:vertical; overflow:hidden; }',
        '.ab-speech-more { color:var(--accent); cursor:pointer; font-size:13px; margin-top:4px;',
        '  display:inline-block; }',
        '.ab-speech-more:hover { text-decoration:underline; }',
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
    var _speechEl = null;

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
        _positionSpeech();
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
        if (_speechEl) _speechEl.classList.remove('dimmed');
    }

    function _clearTool() {
        if (_indicatorEl) { _indicatorEl.remove(); _indicatorEl = null; }
        if (_indicatorBubble) { _indicatorBubble.remove(); _indicatorBubble = null; }
        if (_rangeEl) { _rangeEl.remove(); _rangeEl = null; }
        if (_rangeBubble) { _rangeBubble.remove(); _rangeBubble = null; }
        _activeTool = null;
    }

    // ==========================================
    // Splash Transition（发送后过渡动画）
    // ==========================================
    var _splashActive = false;

    function _showSplash() {
        if (_splashActive) return;
        _splashActive = true;

        // Disable OK/send buttons
        _setToolButtonsEnabled(false);

        var overlay = document.createElement('div');
        overlay.className = 'ab-splash-overlay';

        var splash = document.createElement('div');
        splash.className = 'ab-splash';

        var spinner = document.createElement('div');
        spinner.className = 'ab-splash-spinner';

        var text = document.createElement('div');
        text.className = 'ab-splash-text';
        text.textContent = '发送指令给Agent...';

        splash.appendChild(spinner);
        splash.appendChild(text);
        overlay.appendChild(splash);
        shadow.appendChild(overlay);

        // Random duration 1-3.5s
        var duration = 1000 + Math.random() * 2500;

        setTimeout(function() {
            // Phase 2: checkmark + "已发送"
            spinner.className = 'ab-splash-check';
            spinner.textContent = '\u2713';
            text.textContent = '已发送';

            setTimeout(function() {
                // Close splash
                overlay.remove();
                _splashActive = false;
                _setToolButtonsEnabled(true);
            }, 800);
        }, duration);
    }

    function _setToolButtonsEnabled(enabled) {
        var btns = shadow.querySelectorAll('.ab-bubble-send');
        for (var i = 0; i < btns.length; i++) {
            btns[i].disabled = !enabled;
        }
        var sendBtn = shadow.querySelector('.ab-panel-send');
        if (sendBtn) sendBtn.disabled = !enabled;
        var panelInp = shadow.querySelector('.ab-panel-input');
        if (panelInp) panelInp.disabled = !enabled;
    }

    // ==========================================
    // Speech Bubble（Agent 说话气泡）
    // ==========================================
    function _showSpeech(text) {
        if (_speechEl) {
            // Update existing
            var txt = _speechEl.querySelector('.ab-speech-text');
            if (txt) { txt.textContent = text; txt.className = 'ab-speech-text'; }
            var more = _speechEl.querySelector('.ab-speech-more');
            if (more) more.remove();
            _applySpeechClamp(_speechEl, txt);
            return;
        }

        var el = document.createElement('div');
        el.className = 'ab-speech';
        var tail = document.createElement('div');
        tail.className = 'ab-speech-tail';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'ab-speech-close';
        closeBtn.textContent = '\u2715';
        closeBtn.addEventListener('click', function(e) { e.stopPropagation(); _hideSpeech(); });
        var txt = document.createElement('div');
        txt.className = 'ab-speech-text';
        txt.textContent = text;
        el.appendChild(tail);
        el.appendChild(closeBtn);
        el.appendChild(txt);
        shadow.appendChild(el);
        _speechEl = el;
        _applySpeechClamp(el, txt);
        _positionSpeech();
    }

    function _applySpeechClamp(el, txt) {
        // Check if text overflows 5 lines
        setTimeout(function() {
            var lineHeight = parseFloat(getComputedStyle(txt).lineHeight) || 22.4;
            var maxHeight = lineHeight * 5;
            if (txt.scrollHeight > maxHeight + 2) {
                txt.classList.add('clamped');
                var more = document.createElement('span');
                more.className = 'ab-speech-more';
                more.textContent = '(more)';
                more.addEventListener('click', function(e) {
                    e.stopPropagation();
                    txt.classList.remove('clamped');
                    more.remove();
                });
                el.appendChild(more);
            }
        }, 30);
    }

    function _hideSpeech() {
        if (_speechEl) { _speechEl.remove(); _speechEl = null; }
    }

    function _positionSpeech() {
        if (!_speechEl) return;
        var bw = btn.offsetWidth, bh = btn.offsetHeight;
        var bx = btn.offsetLeft, by = btn.offsetTop;
        var sw = _speechEl.offsetWidth || 320, sh = _speechEl.offsetHeight || 60;
        var vw = window.innerWidth, vh = window.innerHeight;
        var gap = 12;

        // Try right side
        var rightSpace = vw - (bx + bw) - gap;
        var leftSpace = bx - gap;
        var topSpace = by - gap;
        var bottomSpace = vh - (by + bh) - gap;

        _speechEl.className = 'ab-speech';
        if (rightSpace >= sw + 10) {
            _speechEl.classList.add('tail-left');
            _speechEl.style.left = (bx + bw + gap) + 'px';
            _speechEl.style.top = Math.max(12, Math.min(by, vh - sh - 12)) + 'px';
        } else if (leftSpace >= sw + 10) {
            _speechEl.classList.add('tail-right');
            _speechEl.style.left = (bx - sw - gap) + 'px';
            _speechEl.style.top = Math.max(12, Math.min(by, vh - sh - 12)) + 'px';
        } else if (topSpace >= sh + 10) {
            _speechEl.classList.add('tail-bottom');
            _speechEl.style.left = Math.max(12, Math.min(bx, vw - sw - 12)) + 'px';
            _speechEl.style.top = (by - sh - gap) + 'px';
        } else {
            _speechEl.classList.add('tail-top');
            _speechEl.style.left = Math.max(12, Math.min(bx, vw - sw - 12)) + 'px';
            _speechEl.style.top = (by + bh + gap) + 'px';
        }
    }

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
        var row = document.createElement('div');
        row.className = 'ab-bubble-row';
        var inp = document.createElement('textarea');
        inp.className = 'ab-bubble-input';
        inp.placeholder = '拖动准星到目标位置，然后告诉Agent这是什么要做什么';
        inp.rows = 3;
        inp.addEventListener('input', function() { this.style.height = 'auto'; this.style.height = Math.min(this.scrollHeight, 160) + 'px'; posBubble(); });
        var sendBtn = document.createElement('button');
        sendBtn.className = 'ab-bubble-send';
        sendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
        row.appendChild(inp);
        row.appendChild(sendBtn);
        bubble.appendChild(row);
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
            if (_splashActive) return;
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

            window.__bh_emit__('indicator_result', {x: x, y: y, text: inp.value});
            inp.value = '';
            _showSplash();
        }
        sendBtn.addEventListener('click', submit);
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } });
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
        var row = document.createElement('div');
        row.className = 'ab-bubble-row';
        var inp = document.createElement('textarea');
        inp.className = 'ab-bubble-input';
        inp.placeholder = '拖动边角调整大小，拖动边框移动位置，然后告诉Agent这个区域是什么';
        inp.rows = 3;
        inp.addEventListener('input', function() { this.style.height = 'auto'; this.style.height = Math.min(this.scrollHeight, 160) + 'px'; posBubble(); });
        var sendBtn = document.createElement('button');
        sendBtn.className = 'ab-bubble-send';
        sendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
        row.appendChild(inp);
        row.appendChild(sendBtn);
        bubble.appendChild(row);
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
            if (_splashActive) return;
            window.__bh_emit__('range_result', {
                x: Math.round(parseFloat(rect.style.left)),
                y: Math.round(parseFloat(rect.style.top)),
                width: Math.round(parseFloat(rect.style.width)),
                height: Math.round(parseFloat(rect.style.height)),
                text: inp.value
            });
            inp.value = '';
            _showSplash();
        }
        sendBtn.addEventListener('click', submit);
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } });
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
            if (data.type === 'think' && data.text) {
                _showSpeech(data.text);
            } else {
                _hideSpeech();
            }
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
