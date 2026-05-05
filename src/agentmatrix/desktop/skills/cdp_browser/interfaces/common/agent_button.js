/**
 * Agent Button — 统一前端交互入口。
 *
 * 替代原聊天面板 + browser_learning 工具栏。
 * 提供：Agent 状态显示、指示器、范围选择器、文本输入、提问对话框。
 *
 * 通信机制不变：__bh_emit__ (前端→后端)，__bh_event_listeners__ (后端→前端)。
 *
 * 模块化结构（Python 拼接注入，共享同一 IIFE 闭包）：
 *   __bh_css__               — 由 Python 从 agent_button.css 生成
 *   agent_button.js (part 1) — 本文件：IIFE 开头、共享状态、helpers
 *   agent_button_splash.js   — 发送过渡动画
 *   agent_button_speech.js   — Agent 说话气泡
 *   agent_button_indicator.js — 指示器（十字准心）
 *   agent_button_range.js    — 范围选择器
 *   agent_button_dialog.js   — 提问对话框
 *   agent_button_init.js     — DOM 构建、事件绑定、IIFE 结尾
 */
(function() {
    if (window.__bh_agent_button__) return;
    window.__bh_agent_button__ = true;

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
    // CSS（从 __bh_css__ 变量注入，由 Python 从 agent_button.css 生成）
    // ==========================================
    var style = document.createElement('style');
    style.textContent = __bh_css__;
    shadow.appendChild(style);

    // ==========================================
    // 共享状态（IIFE 闭包作用域，供所有模块访问）
    // ==========================================
    var _status = 'IDLE';      // IDLE | THINKING | WORKING | WAITING_FOR_USER | DISCONNECTED
    var _agentName = (window.__bh_agent_meta__ && window.__bh_agent_meta__.agent_name) || 'Agent';
    var _panelOpen = false;
    var _activeTool = null;    // 'indicator' | 'range' | null
    var _splashActive = false;
    var _indicatorEl = null, _indicatorBubble = null;
    var _rangeEl = null, _rangeBubble = null;
    var _askHost = null;
    var _speechEl = null;

    // DOM 元素（在 __bh_init_agent_button 中赋值）
    var ab, btn, panel, panelInput, panelSend;

    // ==========================================
    // 共享 Helpers（IIFE 闭包作用域，供所有模块调用）
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
    // 模块文件插入点（Python 拼接时在此处插入 splash/speech/indicator/range/dialog）
    // ==========================================
