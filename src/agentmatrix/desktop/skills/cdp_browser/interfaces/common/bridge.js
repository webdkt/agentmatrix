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
        window.__bh_flash(el);
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
    // 元素闪烁高亮（检查/验证时自动触发）
    // ==========================================
    (function() {
        var s = document.createElement('style');
        s.textContent = '@keyframes __bh_flash_pulse{0%,100%{outline:3px solid rgba(99,102,241,0.9);box-shadow:0 0 12px 4px rgba(99,102,241,0.5)}50%{outline:3px solid rgba(255,100,50,0.9);box-shadow:0 0 12px 4px rgba(255,100,50,0.5)}}';
        (document.head || document.documentElement).appendChild(s);
    })();

    window.__bh_flash = function(el) {
        if (!el || !el.style) return;
        var prev = {outline: el.style.outline, outlineOffset: el.style.outlineOffset, animation: el.style.animation};
        el.style.outline = '3px solid rgba(99,102,241,0.9)';
        el.style.outlineOffset = '2px';
        el.style.animation = '__bh_flash_pulse 0.6s ease-in-out 3';
        setTimeout(function() {
            el.style.outline = prev.outline;
            el.style.outlineOffset = prev.outlineOffset;
            el.style.animation = prev.animation;
        }, 2000);
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
        window.__bh_flash(el);
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
        if (els.length > 0) window.__bh_flash(els[0]);
        return els.map(function(el) {
            var r = el.getBoundingClientRect ? el.getBoundingClientRect() : {};
            return {
                tag: el.tagName ? el.tagName.toLowerCase() : '',
                id: el.id || '',
                cls: (el.className || '').toString().substring(0, 80),
                text: (el.textContent || '').substring(0, 120).trim(),
                rect: {x: Math.round(r.left || 0), y: Math.round(r.top || 0), w: Math.round(r.width || 0), h: Math.round(r.height || 0)},
                attrs: Array.from(el.attributes || []).reduce(function(acc, a) {
                    if (['class', 'id', 'style'].indexOf(a.name) === -1) acc[a.name] = a.value;
                    return acc;
                }, {})
            };
        });
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
            el.style.outline = '3px solid #6366f1';
            el.style.outlineOffset = '2px';
            el.scrollIntoView({behavior: 'smooth', block: 'center'});

            // 确认气泡（挂到 body，避开 shadow DOM）
            var bubble = document.createElement('div');
            bubble.id = '__bh_confirm_bubble__';
            bubble.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);z-index:2147483647;background:rgba(255,255,255,0.95);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);border:1.5px solid rgba(0,0,0,0.12);border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.12),0 1px 3px rgba(0,0,0,0.08);padding:14px 20px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:14px;color:#1a1a2e;display:flex;align-items:center;gap:12px;pointer-events:auto;';
            bubble.innerHTML = '<span style="font-size:13px;color:rgba(0,0,0,0.45);">是这个元素吗？</span>' +
                '<button id="__bh_confirm_yes__" style="background:#6366f1;color:#fff;border:none;border-radius:10px;padding:8px 18px;cursor:pointer;font-size:13px;font-weight:600;font-family:inherit;transition:background 0.15s;">是</button>' +
                '<button id="__bh_confirm_no__" style="background:rgba(0,0,0,0.04);color:#1a1a2e;border:1px solid rgba(0,0,0,0.12);border-radius:10px;padding:8px 18px;cursor:pointer;font-size:13px;font-family:inherit;transition:background 0.15s;">不是</button>';
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
})();
