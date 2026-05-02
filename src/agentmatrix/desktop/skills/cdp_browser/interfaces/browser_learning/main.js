/**
 * Browser Learning Interface — 浏览器自动化学习工具栏。
 *
 * 功能：
 * - 顶部工具栏，包含"指示器"和"范围选择器"按钮
 * - 指示器：可拖动的十字准心 + 信息气泡，用户可输入文本后点 OK
 * - 范围选择器：可调整大小的矩形框 + 信息气泡
 * - 所有交互通过 __bh_emit__ 与后端通信
 * - 支持接收后端事件（agent_thinking / agent_done 等）
 *
 * 使用 Shadow DOM 隔离样式，但可访问页面 DOM。
 */
(function() {
    if (window.__bh_browser_learning__) return;
    window.__bh_browser_learning__ = true;

    // ---- Shadow DOM 容器 ----
    var host = document.createElement('div');
    host.id = '__bh_host__';
    host.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:2147483647;';
    var shadow = host.attachShadow({mode: 'open'});

    // ---- 样式 ----
    var style = document.createElement('style');
    style.textContent = [
        ':host { all: initial; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }',

        /* ---- Toolbar ---- */
        '#toolbar { position:fixed; top:0; left:0; right:0; height:36px; background:rgba(33,33,33,0.92); color:#fff; font-size:12px; display:flex; align-items:center; padding:0 12px; gap:8px; box-shadow:0 1px 4px rgba(0,0,0,0.3); pointer-events:auto; z-index:2147483647; }',
        '#toolbar .status { opacity:0.7; margin-right:8px; }',
        '#toolbar button { background:none; border:none; color:#fff; border-radius:3px; padding:4px 12px; cursor:pointer; font-size:12px; font-family:inherit; }',
        '#toolbar .btn-indicator { background:#e53935; }',
        '#toolbar .btn-indicator:hover { background:#c62828; }',
        '#toolbar .btn-range { background:#1976d2; }',
        '#toolbar .btn-range:hover { background:#1565c0; }',
        '#toolbar .btn-clear { background:rgba(255,255,255,0.15); margin-left:auto; }',
        '#toolbar .btn-clear:hover { background:rgba(255,255,255,0.25); }',
        '#toolbar .url { opacity:0.5; max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }',
        '#toolbar .thinking { color:#ffd54f; margin-left:8px; display:none; }',
        '#toolbar .thinking.active { display:inline; }',

        /* ---- Indicator ---- */
        '.indicator-crosshair { position:fixed; width:120px; height:120px; transform:translate(-50%,-50%); pointer-events:none; z-index:2147483646; }',
        '.indicator-ring { position:absolute; left:50%; top:50%; width:32px; height:32px; transform:translate(-50%,-50%); border:2.5px solid #e53935; border-radius:50%; box-shadow:0 0 10px rgba(229,57,53,0.35); }',
        '.indicator-seg { position:absolute; background:#e53935; }',
        '.indicator-seg.h { height:2.5px; width:16px; top:50%; transform:translateY(-50%); }',
        '.indicator-seg.v { width:2.5px; height:16px; left:50%; transform:translateX(-50%); }',
        '.indicator-seg.h.l { right:calc(50% + 19px); }',
        '.indicator-seg.h.r { left:calc(50% + 19px); }',
        '.indicator-seg.v.t { bottom:calc(50% + 19px); }',
        '.indicator-seg.v.b { top:calc(50% + 19px); }',
        '.indicator-handle { position:absolute; left:50%; top:50%; width:44px; height:44px; transform:translate(-50%,-50%); border-radius:50%; cursor:grab; pointer-events:auto; background:transparent; }',
        '.indicator-handle:active { cursor:grabbing; }',

        /* ---- Range Selector ---- */
        '.range-rect { position:fixed; border:2px dashed #1976d2; border-radius:6px; background:rgba(25,118,210,0.04); z-index:2147483645; cursor:move; box-sizing:border-box; user-select:none; pointer-events:auto; }',
        '.range-handle { position:absolute; width:12px; height:12px; background:#fff; border:2px solid #1976d2; border-radius:2px; z-index:2147483647; box-sizing:border-box; pointer-events:auto; }',
        '.range-handle.tl { top:-6px; left:-6px; cursor:nw-resize; }',
        '.range-handle.tc { top:-6px; left:50%; margin-left:-6px; cursor:n-resize; }',
        '.range-handle.tr { top:-6px; right:-6px; cursor:ne-resize; }',
        '.range-handle.ml { top:50%; left:-6px; margin-top:-6px; cursor:w-resize; }',
        '.range-handle.mr { top:50%; right:-6px; margin-top:-6px; cursor:e-resize; }',
        '.range-handle.bl { bottom:-6px; left:-6px; cursor:sw-resize; }',
        '.range-handle.bc { bottom:-6px; left:50%; margin-left:-6px; cursor:s-resize; }',
        '.range-handle.br { bottom:-6px; right:-6px; cursor:se-resize; }',

        /* ---- Bubble ---- */
        '.bubble { position:fixed; z-index:2147483646; background:rgba(255,255,255,0.82); backdrop-filter:blur(16px) saturate(180%); -webkit-backdrop-filter:blur(16px) saturate(180%); border-radius:14px; box-shadow:0 8px 32px rgba(0,0,0,0.12); padding:16px 18px; min-width:220px; max-width:340px; font-size:14px; color:#222; line-height:1.5; pointer-events:auto; }',
        '.bubble.indicator-bubble { border:2px dashed #e53935; }',
        '.bubble.range-bubble { border:2px dashed #1976d2; }',
        '.bubble-text { margin-bottom:10px; white-space:pre-wrap; word-break:break-word; font-weight:500; }',
        '.bubble-input { width:100%; box-sizing:border-box; padding:8px 10px; border:1px solid rgba(0,0,0,0.12); border-radius:8px; font-size:14px; font-family:inherit; outline:none; margin-bottom:10px; background:rgba(255,255,255,0.6); }',
        '.bubble-input:focus { border-color:#1976d2; box-shadow:0 0 0 3px rgba(25,118,210,0.12); }',
        '.bubble-ok { display:block; width:100%; padding:8px 0; color:#fff; border:none; border-radius:8px; font-size:14px; font-weight:600; font-family:inherit; cursor:pointer; }',
        '.bubble-ok.red { background:#e53935; }',
        '.bubble-ok.red:hover { background:#c62828; }',
        '.bubble-ok.blue { background:#1976d2; }',
        '.bubble-ok.blue:hover { background:#1565c0; }',
    ].join('\n');
    shadow.appendChild(style);

    // ---- Toolbar DOM ----
    var toolbar = document.createElement('div');
    toolbar.id = 'toolbar';
    toolbar.innerHTML = [
        '<span class="status">Browser Learning</span>',
        '<button class="btn-indicator" data-action="indicator">指示器</button>',
        '<button class="btn-range" data-action="range">范围选择器</button>',
        '<span class="thinking" id="thinking-status">Agent 思考中...</span>',
        '<button class="btn-clear" data-action="clear">清除</button>',
        '<span class="url"></span>',
    ].join('');
    shadow.appendChild(toolbar);
    document.body.appendChild(host);
    toolbar.querySelector('.url').textContent = location.href;

    // 状态
    var currentUI = null; // 'indicator' | 'range' | null
    var indicatorEl = null, indicatorBubble = null;
    var rangeEl = null, rangeBubble = null;

    // ---- 清除所有 UI ----
    function clearAll() {
        if (indicatorEl) { indicatorEl.remove(); indicatorEl = null; }
        if (indicatorBubble) { indicatorBubble.remove(); indicatorBubble = null; }
        if (rangeEl) { rangeEl.remove(); rangeEl = null; }
        if (rangeBubble) { rangeBubble.remove(); rangeBubble = null; }
        currentUI = null;
    }

    // ---- Toolbar 按钮事件 ----
    toolbar.addEventListener('click', function(e) {
        var btn = e.target.closest('button');
        if (!btn) return;
        var action = btn.dataset.action;

        if (action === 'indicator') {
            clearAll();
            showIndicator(Math.round(window.innerWidth/2), Math.round(window.innerHeight/2), '请拖动圆圈到目标位置，然后输入描述');
            window.__bh_emit__('start_tool', { tool: 'indicator', url: location.href });
        } else if (action === 'range') {
            clearAll();
            showRangeSelector();
            window.__bh_emit__('start_tool', { tool: 'range', url: location.href });
        } else if (action === 'clear') {
            clearAll();
            window.__bh_emit__('clear_tool', { url: location.href });
        }
    });

    // ---- Indicator ----
    function showIndicator(initX, initY, infoText) {
        currentUI = 'indicator';

        var crosshair = document.createElement('div');
        crosshair.className = 'indicator-crosshair';
        crosshair.style.left = initX + 'px';
        crosshair.style.top = initY + 'px';

        var ring = document.createElement('div');
        ring.className = 'indicator-ring';
        crosshair.appendChild(ring);

        ['h l','h r','v t','v b'].forEach(function(cls) {
            var seg = document.createElement('div');
            seg.className = 'indicator-seg ' + cls;
            crosshair.appendChild(seg);
        });

        var handle = document.createElement('div');
        handle.className = 'indicator-handle';
        crosshair.appendChild(handle);

        indicatorEl = crosshair;
        shadow.appendChild(crosshair);

        // Bubble
        var bubble = document.createElement('div');
        bubble.className = 'bubble indicator-bubble';
        var textEl = document.createElement('div');
        textEl.className = 'bubble-text';
        textEl.textContent = infoText;
        var inp = document.createElement('input');
        inp.className = 'bubble-input';
        inp.type = 'text';
        inp.placeholder = '输入描述...';
        var okBtn = document.createElement('button');
        okBtn.className = 'bubble-ok red';
        okBtn.textContent = 'OK';
        bubble.appendChild(textEl);
        bubble.appendChild(inp);
        bubble.appendChild(okBtn);
        indicatorBubble = bubble;
        shadow.appendChild(bubble);

        function posBubble() {
            var cr = crosshair.getBoundingClientRect();
            var cx = cr.left + cr.width/2, cy = cr.top + cr.height/2;
            var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
            var vw = window.innerWidth, vh = window.innerHeight;
            var bx = cx + 70, by = cy - bh/2;
            if (bx + bw > vw - 12) bx = cx - 70 - bw;
            if (by < 12) by = 12;
            if (by + bh > vh - 12) by = vh - 12 - bh;
            bx = Math.max(12, bx);
            by = Math.max(12, by);
            bubble.style.left = bx + 'px';
            bubble.style.top = by + 'px';
        }
        posBubble();

        // 拖动
        var dragging = false, oX = 0, oY = 0;
        handle.addEventListener('mousedown', function(e) {
            dragging = true;
            var cr = crosshair.getBoundingClientRect();
            oX = e.clientX - (cr.left + cr.width/2);
            oY = e.clientY - (cr.top + cr.height/2);
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            crosshair.style.left = (e.clientX - oX) + 'px';
            crosshair.style.top = (e.clientY - oY) + 'px';
            posBubble();
        });
        document.addEventListener('mouseup', function() { dragging = false; });

        // OK
        function submit() {
            var cr = crosshair.getBoundingClientRect();
            var x = Math.round(cr.left + cr.width/2);
            var y = Math.round(cr.top + cr.height/2);
            // 获取坐标处的元素信息
            var elInfo = window.__bh_get_element_info__ ? window.__bh_get_element_info__(x, y) : null;
            window.__bh_emit__('indicator_result', {
                x: x, y: y,
                text: inp.value,
                element: elInfo
            });
        }
        okBtn.addEventListener('click', submit);
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter') submit(); });
        inp.focus();
    }

    // ---- Range Selector ----
    function showRangeSelector() {
        currentUI = 'range';
        var INIT_W = 300, INIT_H = 200;
        var INIT_X = Math.round(window.innerWidth/2 - INIT_W/2);
        var INIT_Y = Math.round(window.innerHeight/2 - INIT_H/2);

        var rect = document.createElement('div');
        rect.className = 'range-rect';
        rect.style.left = INIT_X + 'px';
        rect.style.top = INIT_Y + 'px';
        rect.style.width = INIT_W + 'px';
        rect.style.height = INIT_H + 'px';

        ['tl','tc','tr','ml','mr','bl','bc','br'].forEach(function(p) {
            var h = document.createElement('div');
            h.className = 'range-handle ' + p;
            h.dataset.pos = p;
            rect.appendChild(h);
        });

        rangeEl = rect;
        shadow.appendChild(rect);

        // Bubble
        var bubble = document.createElement('div');
        bubble.className = 'bubble range-bubble';
        var textEl = document.createElement('div');
        textEl.className = 'bubble-text';
        textEl.textContent = '拖动边角调整大小，拖动边框移动位置';
        var inp = document.createElement('input');
        inp.className = 'bubble-input';
        inp.type = 'text';
        inp.placeholder = '描述这个区域...';
        var okBtn = document.createElement('button');
        okBtn.className = 'bubble-ok blue';
        okBtn.textContent = 'OK';
        bubble.appendChild(textEl);
        bubble.appendChild(inp);
        bubble.appendChild(okBtn);
        rangeBubble = bubble;
        shadow.appendChild(bubble);

        function posBubble() {
            var rl = parseFloat(rect.style.left), rt = parseFloat(rect.style.top);
            var rw = parseFloat(rect.style.width), rh = parseFloat(rect.style.height);
            var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
            var bx = rl + rw + 18, by = rt + rh/2 - bh/2;
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
            var handle = e.target.closest('.range-handle');
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

        // OK
        function submit() {
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

    // ---- 后端事件处理 ----
    window.__bh_on_event__ = function(eventType, data) {
        if (eventType === 'agent_thinking') {
            var status = toolbar.querySelector('#thinking-status');
            if (status) status.classList.add('active');
        } else if (eventType === 'agent_done') {
            var status = toolbar.querySelector('#thinking-status');
            if (status) status.classList.remove('active');
        } else if (eventType === 'highlight') {
            // data: {selector, duration}
            try {
                var el = document.querySelector(data.selector);
                if (el) {
                    el.style.outline = '3px solid #e53935';
                    el.style.outlineOffset = '2px';
                    setTimeout(function() {
                        el.style.outline = '';
                        el.style.outlineOffset = '';
                    }, data.duration || 3000);
                }
            } catch(e) {}
        }
    };

    // 通知后端 interface 已加载
    window.__bh_emit__('interface_loaded', { name: 'browser_learning', url: location.href });

    // 调整页面顶部间距
    document.body.style.paddingTop = '40px';
})();
