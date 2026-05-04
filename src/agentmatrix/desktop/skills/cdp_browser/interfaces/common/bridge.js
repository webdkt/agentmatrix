/**
 * Bridge JS — 注入到每个页面，提供前后端通信基础设施。
 *
 * 前端→后端：window.__bh_emit__(type, data)
 * 后端→前端：window.__bh_on_event__(type, data)（由 interface 设置处理函数）
 *
 * agent 元数据（agent_name, agent_session_id）由后端注入 bridge 后设置，
 * 每次事件自动附带，用于后端路由到正确的 agent session。
 */
(function() {
    // 防止重复注入
    if (window.__bh_bridge_loaded__) return;
    window.__bh_bridge_loaded__ = true;

    /**
     * 后端调用此函数设置 agent 元数据。
     * 在 bridge 注入后由后端设置，或由前端从页面存储恢复。
     */
    window.__bh_agent_meta__ = window.__bh_agent_meta__ || {};

    /**
     * 前端 → 后端：发送事件
     * 所有 UI 组件通过此函数与后端通信。
     * 自动附带 agent 元数据（agent_name, agent_session_id）。
     *
     * @param {string} eventType - 事件类型（如 'click', 'indicator_result', 'user_input'）
     * @param {object} data - 事件数据
     */
    window.__bh_emit__ = function(eventType, data) {
        var payload = {
            type: eventType,
            ts: Date.now(),
            url: location.href,
            title: document.title
        };
        // 附带 agent 元数据
        if (window.__bh_agent_meta__) {
            payload.agent_name = window.__bh_agent_meta__.agent_name || '';
            payload.agent_session_id = window.__bh_agent_meta__.agent_session_id || '';
        }
        if (data && typeof data === 'object') {
            for (var k in data) {
                if (data.hasOwnProperty(k)) payload[k] = data[k];
            }
        }
        console.log('__BH_EVENT__ ' + JSON.stringify(payload));
    };

    /**
     * 后端 → 前端：多监听器事件分发。
     * 组件通过 __bh_event_listeners__.push(handler) 注册。
     * 后端调用 __bh_on_event__(type, data) 时，所有监听器都会收到。
     */
    window.__bh_event_listeners__ = [];
    window.__bh_on_event__ = function(type, data) {
        var listeners = window.__bh_event_listeners__ || [];
        for (var i = 0; i < listeners.length; i++) {
            try { listeners[i](type, data); } catch(e) {}
        }
    };

    /**
     * 工具：获取页面元素在视口中的位置信息
     */
    window.__bh_get_element_info__ = function(x, y) {
        // 暂时隐藏 bridge 自身的 UI，以免遮挡目标元素
        var host = document.getElementById('__bh_host__');
        if (host) host.style.display = 'none';
        var el = document.elementFromPoint(x, y);
        if (host) host.style.display = '';

        if (!el) return null;
        return {
            tagName: el.tagName.toLowerCase(),
            id: el.id || '',
            className: el.className || '',
            text: (el.textContent || '').substring(0, 200).trim(),
            rect: {
                x: Math.round(el.getBoundingClientRect().left),
                y: Math.round(el.getBoundingClientRect().top),
                width: Math.round(el.getBoundingClientRect().width),
                height: Math.round(el.getBoundingClientRect().height)
            },
            attributes: Array.from(el.attributes).reduce(function(acc, attr) {
                if (['class', 'id', 'style'].indexOf(attr.name) === -1) {
                    acc[attr.name] = attr.value;
                }
                return acc;
            }, {})
        };
    };

    // ==========================================
    // DOM 探索工具函数（供 Agent eval_js 使用）
    // ==========================================

    /**
     * 获取元素的结构化信息。
     * @param {Element} el - DOM 元素
     * @returns {object} {tag, id, cls, text, rect, attrs}
     */
    window.__bh_el_info = function(el) {
        if (!el) return null;
        var r = el.getBoundingClientRect ? el.getBoundingClientRect() : {};
        return {
            tag: el.tagName ? el.tagName.toLowerCase() : '',
            id: el.id || '',
            cls: (el.className || '').toString().substring(0, 80),
            text: (el.textContent || '').substring(0, 120).trim(),
            rect: {
                x: Math.round(r.left || 0), y: Math.round(r.top || 0),
                w: Math.round(r.width || 0), h: Math.round(r.height || 0)
            },
            attrs: Array.from(el.attributes || []).reduce(function(acc, a) {
                if (['class', 'id', 'style'].indexOf(a.name) === -1) acc[a.name] = a.value;
                return acc;
            }, {})
        };
    };

    /**
     * 获取从 html 根到元素的标签路径。
     * @param {Element} el - DOM 元素
     * @returns {string} 如 "html > body > div#app > button.submit"
     */
    window.__bh_tag_path = function(el) {
        if (!el) return '';
        var path = [];
        while (el && el !== document.documentElement) {
            var s = el.tagName.toLowerCase();
            if (el.id) s += '#' + el.id;
            else if (el.className && typeof el.className === 'string') {
                var cls = el.className.trim().split(/\s+/)[0];
                if (cls) s += '.' + cls;
            }
            path.unshift(s);
            el = el.parentElement;
        }
        path.unshift('html');
        return path.join(' > ');
    };

    /**
     * 测试 CSS selector 的唯一性。
     * @param {string} selector - CSS 选择器
     * @returns {object} {count, first: __bh_el_info(firstMatch) | null}
     */
    window.__bh_test = function(selector) {
        try {
            var matches = document.querySelectorAll(selector);
            return {
                count: matches.length,
                first: matches.length > 0 ? window.__bh_el_info(matches[0]) : null
            };
        } catch (e) {
            return {count: -1, error: e.message};
        }
    };

    /**
     * 生成元素的 XPath。
     * @param {Element} el - DOM 元素
     * @returns {string} 如 "/html/body/div[2]/button[1]"
     */
    window.__bh_xpath = function(el) {
        if (!el) return '';
        var path = [];
        while (el && el !== document.documentElement) {
            var tag = el.tagName.toLowerCase();
            var parent = el.parentElement;
            if (parent) {
                var siblings = Array.from(parent.children).filter(function(c) {
                    return c.tagName === el.tagName;
                });
                if (siblings.length > 1) {
                    var idx = siblings.indexOf(el) + 1;
                    tag += '[' + idx + ']';
                }
            }
            path.unshift(tag);
            el = el.parentElement;
        }
        path.unshift('html');
        return '/' + path.join('/');
    };

    /**
     * 测试 XPath 的唯一性。
     * @param {string} xpath - XPath 表达式
     * @returns {object} {count, first: __bh_el_info(firstMatch) | null}
     */
    window.__bh_test_xpath = function(xpath) {
        try {
            var result = document.evaluate(xpath, document, null,
                XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
            var count = result.snapshotLength;
            var first = count > 0 ? result.snapshotItem(0) : null;
            return {count: count, first: first ? window.__bh_el_info(first) : null};
        } catch (e) {
            return {count: -1, error: e.message};
        }
    };

    /**
     * 获取坐标处所有元素（从最顶层到底层），隐藏 __bh_host__ 后探测。
     * @param {number} x
     * @param {number} y
     * @returns {Array} 元素信息数组
     */
    window.__bh_elements_at = function(x, y) {
        var host = document.getElementById('__bh_host__');
        if (host) host.style.display = 'none';
        // elementsFromPoint 返回从最顶层到最底层的所有元素
        var els = document.elementsFromPoint ? document.elementsFromPoint(x, y) : [document.elementFromPoint(x, y)];
        if (host) host.style.display = '';
        return els.map(function(el) { return window.__bh_el_info(el); });
    };

    /**
     * 高亮元素并弹出确认对话框。
     * 用户点击后触发 __bh_emit__('element_confirmed', {selector, confirmed}).
     * @param {string} selector - CSS 选择器
     */
    window.__bh_confirm = function(selector) {
        try {
            var el = document.querySelector(selector);
            if (!el) {
                window.__bh_emit__('element_confirmed', {selector: selector, confirmed: false, error: 'not_found'});
                return;
            }
            // 高亮
            el.style.outline = '3px solid #e53935';
            el.style.outlineOffset = '2px';
            el.scrollIntoView({behavior: 'smooth', block: 'center'});

            // 确认气泡（挂到 body，避开 shadow DOM）
            var bubble = document.createElement('div');
            bubble.id = '__bh_confirm_bubble__';
            bubble.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:2147483647;background:rgba(255,255,255,0.95);backdrop-filter:blur(12px);border-radius:14px;box-shadow:0 8px 32px rgba(0,0,0,0.15);padding:14px 20px;font-family:-apple-system,sans-serif;font-size:14px;color:#222;display:flex;align-items:center;gap:12px;pointer-events:auto;';
            bubble.innerHTML = '<span>是这个元素吗？</span>' +
                '<button id="__bh_confirm_yes__" style="background:#4caf50;color:#fff;border:none;border-radius:8px;padding:8px 16px;cursor:pointer;font-size:14px;">是</button>' +
                '<button id="__bh_confirm_no__" style="background:#e53935;color:#fff;border:none;border-radius:8px;padding:8px 16px;cursor:pointer;font-size:14px;">不是</button>';
            // 清除旧气泡
            var old = document.getElementById('__bh_confirm_bubble__');
            if (old) old.remove();
            document.body.appendChild(bubble);

            var cleanup = function() {
                el.style.outline = '';
                el.style.outlineOffset = '';
                bubble.remove();
            };

            document.getElementById('__bh_confirm_yes__').onclick = function() {
                cleanup();
                window.__bh_emit__('element_confirmed', {selector: selector, confirmed: true});
            };
            document.getElementById('__bh_confirm_no__').onclick = function() {
                cleanup();
                window.__bh_emit__('element_confirmed', {selector: selector, confirmed: false});
            };
        } catch (e) {
            window.__bh_emit__('element_confirmed', {selector: selector, confirmed: false, error: e.message});
        }
    };

    // ==========================================
    // 聊天面板（始终可用，可拖动/最小化）
    // ==========================================
    (function() {
        // 清理旧 panel（防御重复注入）
        var oldPanel = document.getElementById('__bh_chat_panel__');
        if (oldPanel) oldPanel.remove();

        var panel = document.createElement('div');
        panel.id = '__bh_chat_panel__';
        panel.style.cssText = 'position:fixed;bottom:20px;right:20px;width:320px;z-index:2147483646;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:13px;pointer-events:auto;box-shadow:0 4px 24px rgba(0,0,0,0.18);border-radius:12px;overflow:visible;background:#fff;';

        var agentName = (window.__bh_agent_meta__ && window.__bh_agent_meta__.agent_name) || 'Agent';
        var statusText = 'idle';
        var collapsed = false;

        // Header
        var header = document.createElement('div');
        header.style.cssText = 'height:36px;background:#1a1a2e;color:#fff;display:flex;align-items:center;padding:0 12px;cursor:move;user-select:none;gap:8px;';
        header.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:#4caf50;display:inline-block;" id="__bh_status_dot__"></span>' +
            '<span style="flex:1;font-weight:600;" id="__bh_agent_label__">' + agentName + '</span>' +
            '<span style="opacity:0.6;font-size:11px;" id="__bh_status_text__">idle</span>' +
            '<span id="__bh_chat_toggle__" style="cursor:pointer;opacity:0.7;font-size:16px;line-height:1;">&#x2212;</span>';
        panel.appendChild(header);

        // Messages
        var messages = document.createElement('div');
        messages.id = '__bh_chat_messages__';
        messages.style.cssText = 'height:240px;overflow-y:auto;padding:10px;background:#f8f9fa;';
        panel.appendChild(messages);

        // Input area
        var inputArea = document.createElement('div');
        inputArea.style.cssText = 'display:flex;gap:6px;padding:8px;background:#fff;border-top:1px solid #eee;';
        var input = document.createElement('input');
        input.type = 'text';
        input.placeholder = '输入消息...';
        input.style.cssText = 'flex:1;border:1px solid #ddd;border-radius:6px;padding:6px 10px;font-size:13px;font-family:inherit;outline:none;';
        inputArea.appendChild(input);
        var sendBtn = document.createElement('button');
        sendBtn.textContent = '发送';
        sendBtn.style.cssText = 'background:#1a1a2e;color:#fff;border:none;border-radius:6px;padding:6px 14px;cursor:pointer;font-size:13px;font-family:inherit;';
        inputArea.appendChild(sendBtn);
        panel.appendChild(inputArea);

        document.body.appendChild(panel);

        // Helpers
        function addMessage(text, cls) {
            var div = document.createElement('div');
            div.style.cssText = 'margin:4px 0;padding:6px 10px;border-radius:8px;word-break:break-word;white-space:pre-wrap;';
            if (cls === 'user') {
                div.style.background = '#e3f2fd';
                div.style.marginLeft = '20px';
                div.textContent = text;
            } else if (cls === 'think') {
                div.style.background = '#fff3e0';
                div.style.fontStyle = 'italic';
                div.textContent = text;
            } else if (cls === 'action') {
                div.style.background = '#f3e5f5';
                div.style.fontFamily = 'monospace';
                div.style.fontSize = '12px';
                div.textContent = text;
            } else {
                div.style.background = '#e8f5e9';
                div.textContent = text;
            }
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        function setStatus(status) {
            statusText = status;
            var dot = document.getElementById('__bh_status_dot__');
            var txt = document.getElementById('__bh_status_text__');
            if (!dot || !txt) return;
            var s = (status || '').toUpperCase();
            if (s === 'IDLE') { dot.style.background = '#4caf50'; txt.textContent = 'idle'; }
            else if (s === 'THINKING') { dot.style.background = '#ff9800'; txt.textContent = 'thinking...'; }
            else if (s === 'WORKING') { dot.style.background = '#2196f3'; txt.textContent = 'working...'; }
            else if (s === 'WAITING_FOR_USER') { dot.style.background = '#e91e63'; txt.textContent = 'waiting'; }
            else { dot.style.background = '#9e9e9e'; txt.textContent = status || 'unknown'; }
        }

        // Send message
        function sendMessage() {
            var text = input.value.trim();
            if (!text) return;
            input.value = '';
            addMessage(text, 'user');
            window.__bh_emit__('chat_message', {text: text});
        }
        sendBtn.addEventListener('click', sendMessage);
        input.addEventListener('keydown', function(e) { if (e.key === 'Enter') sendMessage(); });

        // Drag
        var dragging = false, dragOX = 0, dragOY = 0;
        header.addEventListener('mousedown', function(e) {
            if (e.target.id === '__bh_chat_toggle__') return;
            dragging = true;
            dragOX = e.clientX - panel.offsetLeft;
            dragOY = e.clientY - panel.offsetTop;
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            panel.style.left = (e.clientX - dragOX) + 'px';
            panel.style.top = (e.clientY - dragOY) + 'px';
            panel.style.right = 'auto';
            panel.style.bottom = 'auto';
        });
        document.addEventListener('mouseup', function() { dragging = false; }, true);

        // Minimize
        document.getElementById('__bh_chat_toggle__').addEventListener('click', function() {
            collapsed = !collapsed;
            messages.style.display = collapsed ? 'none' : '';
            inputArea.style.display = collapsed ? 'none' : '';
            panel.style.width = collapsed ? '200px' : '320px';
            this.textContent = collapsed ? '+' : '\u2212';
        });

        // Listen for backend events
        window.__bh_event_listeners__.push(function(type, data) {
            if (type === 'agent_status') {
                setStatus(data.status);
            } else if (type === 'agent_output') {
                var txt = data.text || '';
                if (data.type === 'think') addMessage(txt, 'think');
                else if (data.type === 'action_started' || data.type === 'action_completed' || data.type === 'action_detected') addMessage(txt, 'action');
                else addMessage(txt, '');
            } else if (type === 'agent_thinking') {
                setStatus('THINKING');
            } else if (type === 'agent_done') {
                setStatus('IDLE');
            }
        });
    })();
})();
