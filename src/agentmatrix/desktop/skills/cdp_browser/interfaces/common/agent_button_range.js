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
