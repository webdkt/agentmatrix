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
    host.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:2147483647;overflow:hidden;';
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
    var _splashActive = false;
    var _speechEl = null;

    // Overlay 统一管理：indicator / range / instruct / dialog 的 DOM 元素
    var _currentOverlay = null;
    var _indicatorEl = null, _indicatorBubble = null;
    var _rangeEl = null, _rangeBubble = null;
    var _instructBubble = null;
    var _askHost = null;
    var _overlayCleanups = [];

    // DOM 元素（在 __bh_init_agent_button 中赋值）
    var ab, btn, menu;

    // ==========================================
    // Overlay 统一管理（互斥 + 隐藏 Agent UI）
    // ==========================================

    /**
     * 打开一个 overlay。自动关闭上一个，自动隐藏 Agent Button 和 speech。
     * @param {'indicator'|'range'|'instruct'|'dialog'} name
     */
    function _showOverlay(name) {
        _clearOverlay();
        _currentOverlay = name;
        if (ab) ab.classList.remove('expanded');
        _syncOverlayUI();
    }

    /**
     * 关闭当前 overlay，清理 DOM，恢复 Agent Button 和 speech。
     */
    function _clearOverlay() {
        _overlayCleanups.forEach(function(fn) { try { fn(); } catch(e) {} });
        _overlayCleanups = [];
        if (_indicatorEl) { _indicatorEl.remove(); _indicatorEl = null; }
        if (_indicatorBubble) { _indicatorBubble.remove(); _indicatorBubble = null; }
        if (_rangeEl) { _rangeEl.remove(); _rangeEl = null; }
        if (_rangeBubble) { _rangeBubble.remove(); _rangeBubble = null; }
        if (_instructBubble) { _instructBubble.remove(); _instructBubble = null; }
        if (_askHost) { _askHost.remove(); _askHost = null; }
        _hideSpeechReply();
        // confirm overlay（bridge.js 创建，这里做安全清理）
        var confirmOverlay = document.getElementById('__bh_confirm_overlay__');
        if (confirmOverlay) confirmOverlay.remove();
        var confirmBubble = document.getElementById('__bh_confirm_bubble__');
        if (confirmBubble) confirmBubble.remove();
        var hlList = document.querySelectorAll('.__bh-confirm-highlight');
        for (var i = 0; i < hlList.length; i++) hlList[i].remove();
        _currentOverlay = null;
        _syncOverlayUI();
    }

    /**
     * 同步 overlay 活跃时的 UI 可见性。
     * - _currentOverlay（真正的 overlay）：隐藏 Agent Button + speech
     * - expanded（菜单展开）：只隐藏 speech（菜单是 Agent Button 的一部分，不触发按钮隐藏）
     */
    function _syncOverlayUI() {
        var hasOverlay = !!_currentOverlay;
        if (_speechEl) {
            _speechEl.style.display = hasOverlay ? 'none' : '';
        }
        if (ab) {
            ab.style.visibility = hasOverlay ? 'hidden' : '';
        }
    }

    // ==========================================
    // Confirm overlay API（供 bridge.js 的 __bh_confirm 调用）
    // ==========================================
    window.__bh_confirm_overlay__ = {
        show: function() {
            _clearOverlay();
            _currentOverlay = 'confirm';
            _syncOverlayUI();
        },
        hide: function() {
            _currentOverlay = null;
            _syncOverlayUI();
        }
    };

    // ==========================================
    // Helpers
    // ==========================================

    /** HTML 转义 */
    function _escHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /** 设置 agent 按钮状态 */
    function _setStatus(status) {
        _status = status;
        if (!btn) return;
        var cls = status.toLowerCase().replace(/_/g, '-');
        btn.className = 'ab-btn ' + cls;
        var dot = btn.querySelector('.ab-btn-dot');
        if (dot) dot.className = 'ab-btn-dot ' + cls;
        var label = btn.querySelector('.ab-btn-label');
        if (label) {
            label.textContent = status.replace(/_/g, ' ');
            // 非 IDLE 状态：label 加 shimmer 动画
            if (cls !== 'idle' && cls !== 'disconnected') {
                label.classList.add('active');
            } else {
                label.classList.remove('active');
            }
        }
        // IDLE 自动展开菜单，非 IDLE 自动收起
        _syncExpanded();
    }

    /** 创建 bubble（close + textarea + send），返回 {el, inp, sendBtn} */
    function _createBubble(placeholder, posFn) {
        var bubble = document.createElement('div');
        bubble.className = 'ab-bubble';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'ab-bubble-close';
        closeBtn.textContent = '\u2715';
        closeBtn.addEventListener('click', function(e) { e.stopPropagation(); _clearOverlay(); });
        var row = document.createElement('div');
        row.className = 'ab-bubble-row';
        var inp = document.createElement('textarea');
        inp.className = 'ab-bubble-input';
        inp.placeholder = placeholder;
        inp.rows = 3;
        inp.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 160) + 'px';
            if (posFn) posFn();
        });
        var sendBtn = document.createElement('button');
        sendBtn.className = 'ab-bubble-send';
        sendBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>';
        row.appendChild(inp);
        row.appendChild(sendBtn);
        bubble.appendChild(closeBtn);
        bubble.appendChild(row);
        return {el: bubble, inp: inp, sendBtn: sendBtn};
    }

    /** 绑定 submit：click + Enter + focus */
    function _bindSubmit(sendBtn, inp, submitFn) {
        sendBtn.addEventListener('click', submitFn);
        inp.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitFn(); }
        });
        inp.focus();
    }

    /** bubble 定位于参考点右侧，自动翻转 + viewport clamp，返回 pos 函数 */
    function _posBubbleRightOf(bubble, getRef) {
        function pos() {
            var ref = getRef();
            var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
            var vw = window.innerWidth, vh = window.innerHeight;
            var bx = ref.rightX + ref.gap, by = ref.centerY - bh / 2;
            if (bx + bw > vw - 12) bx = ref.leftX - ref.gap - bw;
            if (by < 12) by = 12;
            if (by + bh > vh - 12) by = vh - 12 - bh;
            bx = Math.max(12, bx);
            by = Math.max(12, by);
            bubble.style.left = bx + 'px';
            bubble.style.top = by + 'px';
        }
        return pos;
    }

    /** 可拖拽，返回 {destroy} 用于移除 document 监听器 */
    function _makeDraggable(el, handleEl, onMove) {
        var dragging = false, oX = 0, oY = 0;
        handleEl.addEventListener('mousedown', function(e) {
            dragging = true;
            var r = el.getBoundingClientRect();
            oX = e.clientX - (r.left + r.width / 2);
            oY = e.clientY - (r.top + r.height / 2);
            e.preventDefault();
        });
        function onMouseMove(e) {
            if (!dragging) return;
            el.style.left = (e.clientX - oX) + 'px';
            el.style.top = (e.clientY - oY) + 'px';
            if (onMove) onMove();
        }
        function onMouseUp() { dragging = false; }
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        return {
            destroy: function() {
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
            }
        };
    }

    // ==========================================
    // 模块文件插入点（Python 拼接时在此处插入 splash/speech/indicator/range/dialog）
    // ==========================================
