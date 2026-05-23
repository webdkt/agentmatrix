/**
 * Bridge JS — 注入到每个页面，提供前端→后端通信 + DOM 探索工具函数。
 *
 * 通信：
 *   __bh_emit__(type, data) — 前端→后端事件（通过 CDP Binding）
 *
 * DOM 工具（供 eval_js / dom_explorer 使用）：
 *   __bh_el_info(el), __bh_tag_path(el), __bh_xpath(el),
 *   __bh_test(selector), __bh_test_xpath(xpath),
 *   __bh_elements_at(x, y), __bh_highlight(els), __bh_flash(el)
 */
(function() {
    // 防止重复注入
    if (window.__bh_bridge_loaded__) return;
    window.__bh_bridge_loaded__ = true;

    window.__bh_agent_meta__ = window.__bh_agent_meta__ || {};

    /**
     * 前端 → 后端：发送事件。
     * 自动附带 agent 元数据（agent_name, agent_session_id）。
     */
    window.__bh_emit__ = function(eventType, data) {
        var payload = {
            type: eventType,
            ts: Date.now(),
            url: location.href,
            title: document.title
        };
        if (data && data.agent_name) {
            payload.agent_name = data.agent_name;
        } else if (window.__bh_agent_meta__) {
            payload.agent_name = window.__bh_agent_meta__.agent_name || '';
        }
        if (data && data.agent_session_id) {
            payload.agent_session_id = data.agent_session_id;
        } else if (window.__bh_agent_meta__) {
            payload.agent_session_id = window.__bh_agent_meta__.agent_session_id || '';
        }
        if (data && typeof data === 'object') {
            for (var k in data) {
                if (data.hasOwnProperty(k) && k !== 'agent_name' && k !== 'agent_session_id') {
                    payload[k] = data[k];
                }
            }
        }
        window.__bhSendEvent(JSON.stringify(payload));
    };

    /**
     * 工具：获取坐标处元素信息。
     */
    window.__bh_get_element_info__ = function(x, y) {
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
    // 元素闪烁高亮
    // ==========================================
    (function() {
        var s = document.createElement('style');
        s.textContent = [
            '@keyframes __bh_flash_pulse{0%,100%{outline-color:#6366f1;box-shadow:0 0 0 3px #6366f1,0 0 20px 4px rgba(99,102,241,0.5)}33%{outline-color:#06b6d4;box-shadow:0 0 0 3px #06b6d4,0 0 20px 4px rgba(6,182,212,0.5)}66%{outline-color:#a855f7;box-shadow:0 0 0 3px #a855f7,0 0 20px 4px rgba(168,85,247,0.5)}}',
            '.__bh-highlight{outline:3px solid #6366f1 !important;outline-offset:2px !important;animation:__bh_flash_pulse 1.2s linear infinite !important;}'
        ].join('\n');
        var _target = document.head || document.documentElement || document.body;
        if (_target) {
            _target.appendChild(s);
        } else {
            var _retries = 0;
            function _deferInject() {
                var t = document.head || document.documentElement || document.body;
                if (t) { t.appendChild(s); }
                else if (_retries++ < 100) { setTimeout(_deferInject, 50); }
            }
            _deferInject();
        }
    })();

    var _highlightedEls = [];

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

    window.__bh_clear_highlights = function(els) {
        if (!els) els = _highlightedEls.slice();
        els.forEach(function(el) {
            if (el && el.classList) el.classList.remove('__bh-highlight');
        });
        _highlightedEls = _highlightedEls.filter(function(el) {
            return els.indexOf(el) === -1;
        });
    };

    window.__bh_flash = function(el) {
        __bh_highlight(el, {duration: 2000});
    };

    // ==========================================
    // DOM 探索工具函数（供 eval_js 使用）
    // ==========================================

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

    window.__bh_elements_at = function(x, y) {
        var host = document.getElementById('__bh_host__');
        if (host) host.style.display = 'none';
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
    // Tab 可见性追踪
    // ==========================================
    document.addEventListener('visibilitychange', function() {
        if (!document.hidden) {
            window.__bh_emit__('tab_activated', {});
        }
    });
})();
