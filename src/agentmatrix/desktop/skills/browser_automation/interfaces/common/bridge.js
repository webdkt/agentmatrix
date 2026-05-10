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
        s.textContent = [
            // 流动边框：颜色循环 + 光晕脉冲
            '@keyframes __bh_flash_pulse{0%,100%{outline-color:#6366f1;box-shadow:0 0 0 3px #6366f1,0 0 20px 4px rgba(99,102,241,0.5)}33%{outline-color:#06b6d4;box-shadow:0 0 0 3px #06b6d4,0 0 20px 4px rgba(6,182,212,0.5)}66%{outline-color:#a855f7;box-shadow:0 0 0 3px #a855f7,0 0 20px 4px rgba(168,85,247,0.5)}}',
            // 统一元素高亮（探索 + confirm 共用）
            '.__bh-highlight{outline:3px solid #6366f1 !important;outline-offset:2px !important;animation:__bh_flash_pulse 1.2s linear infinite !important;}',
            // Confirm overlay
            '.__bh-confirm-overlay{position:absolute;left:0;top:0;z-index:2147483645;background:rgba(0,0,0,0.45);pointer-events:auto;}',
            '.__bh-confirm-highlight{position:absolute;z-index:2147483646;pointer-events:none;border-radius:6px;animation:__bh_flash_pulse 1.2s linear infinite;}',
            '.__bh-confirm-bubble{position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:2147483647;' +
                'background:rgba(255,255,255,0.95);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);' +
                'border:1.5px solid rgba(0,0,0,0.12);border-radius:16px;' +
                'box-shadow:0 8px 32px rgba(0,0,0,0.12),0 1px 3px rgba(0,0,0,0.08);' +
                'padding:16px 24px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;' +
                'font-size:14px;color:#1a1a2e;display:flex;align-items:center;gap:14px;pointer-events:auto;' +
                'cursor:move;user-select:none;}',
            '.__bh-confirm-bubble button{border:none;border-radius:10px;padding:10px 22px;cursor:pointer;font-size:14px;font-family:inherit;}',
            '.__bh-confirm-yes{background:#6366f1;color:#fff;font-weight:600;}',
            '.__bh-confirm-no{background:rgba(0,0,0,0.04);color:#1a1a2e;border:1px solid rgba(0,0,0,0.12) !important;}',
            '.__bh-confirm-info{font-size:13px;color:rgba(0,0,0,0.45);}'
        ].join('\n');
        var _target = document.head || document.documentElement || document.body;
        if (_target) {
            _target.appendChild(s);
        } else {
            // DOM 还没准备好，延迟注入（最多重试 100 次 = 5 秒）
            var _retries = 0;
            function _deferInject() {
                var t = document.head || document.documentElement || document.body;
                if (t) { t.appendChild(s); }
                else if (_retries++ < 100) { setTimeout(_deferInject, 50); }
            }
            _deferInject();
        }
    })();

    // ==========================================
    // 统一元素高亮（CSS class，非 inline style）
    // ==========================================
    var _highlightedEls = [];

    /**
     * 高亮一个或多个元素。
     * @param {Element|Element[]} els
     * @param {object} [opts]
     * @param {number} [opts.duration] - 自动清除时间（ms），0=不自动清除。默认 2000
     */
    window.__bh_highlight = function(els, opts) {
        if (!els) return;
        if (!Array.isArray(els)) els = [els];
        var duration = opts && opts.duration !== undefined ? opts.duration : 2000;
        els.forEach(function(el) {
            if (!el || !el.classList) return;
            el.classList.add('__bh-highlight');
            _highlightedEls.push(el);
        });
        if (duration > 0) {
            setTimeout(function() { __bh_clear_highlights(els); }, duration);
        }
    };

    /**
     * 清除指定元素的高亮。不传参则清除全部。
     * @param {Element[]} [els]
     */
    window.__bh_clear_highlights = function(els) {
        if (!els) els = _highlightedEls.slice();
        els.forEach(function(el) {
            if (el && el.classList) el.classList.remove('__bh-highlight');
        });
        _highlightedEls = _highlightedEls.filter(function(el) {
            return els.indexOf(el) === -1;
        });
    };

    /** 兼容旧调用：__bh_flash(el) → __bh_highlight(el) */
    window.__bh_flash = function(el) {
        __bh_highlight(el, {duration: 2000});
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

    // ==========================================
    // Tab 可见性追踪 — 页面变为可见时通知后端
    // ==========================================
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            window.__bh_emit__('tab_activated', {});
        }
    });

    /**
     * 遮罩 + 高亮确认对话框。
     * 匹配多个元素时全部高亮，遮罩盖住页面但不遮匹配元素。
     * 页面可自由滚动，确认气泡始终可见且可拖动。
     * @param {string} selector - CSS 选择器 或 XPath（以 'xpath:' 前缀）
     */
    window.__bh_confirm = function(selector) {
        try {
            // 1. 多元素匹配
            var elements;
            if (selector.indexOf('xpath:') === 0) {
                var xpath = selector.substring(6);
                var result = document.evaluate(xpath, document, null,
                    XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                elements = [];
                for (var i = 0; i < result.snapshotLength; i++) {
                    elements.push(result.snapshotItem(i));
                }
            } else {
                elements = Array.from(document.querySelectorAll(selector));
            }

            if (elements.length === 0) {
                window.__bh_emit__('element_confirmed', {selector: selector, confirmed: false, error: 'not_found'});
                return;
            }

            // 2. 通知 agent_button 隐藏 UI
            if (window.__bh_confirm_overlay__) {
                window.__bh_confirm_overlay__.show();
            } else {
                var fallbackHost = document.getElementById('__bh_agent_btn_host__');
                if (fallbackHost) fallbackHost.style.display = 'none';
            }

            // 3. 滚动到第一个匹配元素（距顶部约 300px，避免贴顶看不到）
            var _rect = elements[0].getBoundingClientRect();
            var _scrollTo = window.scrollY + _rect.top - 300;
            window.scrollTo({top: Math.max(0, _scrollTo), behavior: 'smooth'});

            // 4. 高亮匹配元素（统一机制，duration=0 不自动消失）
            __bh_highlight(elements, {duration: 0});

            // 5. 遮罩（position:absolute 覆盖整个文档，随页面滚动）
            var docH = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, window.innerHeight);
            var docW = Math.max(document.body.scrollWidth, document.documentElement.scrollWidth, window.innerWidth);
            var overlay = document.createElement('div');
            overlay.id = '__bh_confirm_overlay__';
            overlay.className = '__bh-confirm-overlay';
            overlay.style.width = docW + 'px';
            overlay.style.height = docH + 'px';
            document.body.appendChild(overlay);

            // 6. 确认气泡
            var bubble = document.createElement('div');
            bubble.id = '__bh_confirm_bubble__';
            bubble.className = '__bh-confirm-bubble';
            bubble.innerHTML =
                '<span class="__bh-confirm-info">找到 <b>' + elements.length + '</b> 个匹配元素</span>' +
                '<button class="__bh-confirm-yes">确认</button>' +
                '<button class="__bh-confirm-no">取消</button>';
            document.body.appendChild(bubble);

            // 7. 气泡拖动
            (function() {
                var dragging = false, ox = 0, oy = 0;
                bubble.addEventListener('mousedown', function(e) {
                    if (e.target.tagName === 'BUTTON') return;
                    dragging = true;
                    var br = bubble.getBoundingClientRect();
                    ox = e.clientX - br.left;
                    oy = e.clientY - br.top;
                    bubble.style.transform = 'none';
                    bubble.style.left = br.left + 'px';
                    bubble.style.top = br.top + 'px';
                    e.preventDefault();
                });
                document.addEventListener('mousemove', function(e) {
                    if (!dragging) return;
                    bubble.style.left = (e.clientX - ox) + 'px';
                    bubble.style.top = (e.clientY - oy) + 'px';
                });
                document.addEventListener('mouseup', function() { dragging = false; });
            })();

            // 8. 清理 + 发送结果（done flag 防重入）
            var done = false;
            function emit(confirmed) {
                if (done) return;
                done = true;
                if (overlay.parentNode) overlay.remove();
                if (bubble.parentNode) bubble.remove();
                __bh_clear_highlights(elements);
                if (window.__bh_confirm_overlay__) {
                    window.__bh_confirm_overlay__.hide();
                } else {
                    var fh = document.getElementById('__bh_agent_btn_host__');
                    if (fh) fh.style.display = '';
                }
                window.__bh_emit__('element_confirmed', {selector: selector, confirmed: confirmed, count: elements.length});
            }

            // 9. 事件
            bubble.querySelector('.__bh-confirm-yes').onclick = function() { emit(true); };
            bubble.querySelector('.__bh-confirm-no').onclick = function() { emit(false); };
            overlay.addEventListener('click', function(e) {
                if (e.target === overlay) emit(false);
            });

        } catch (e) {
            window.__bh_emit__('element_confirmed', {selector: selector, confirmed: false, error: e.message});
        }
    };
})();
