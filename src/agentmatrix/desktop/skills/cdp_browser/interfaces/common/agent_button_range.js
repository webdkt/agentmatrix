    // ==========================================
    // Range Selector
    // ==========================================
    function _showRangeSelector() {
        _showOverlay('range');

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

        // Bubble（deferred posBubble 解决循环依赖）
        var posBubble = function() {};
        var parts = _createBubble('拖动边角调整大小，拖动边框移动位置，然后告诉Agent这个区域是什么', function() { posBubble(); });
        var bubble = parts.el, inp = parts.inp, sendBtn = parts.sendBtn;
        _rangeBubble = bubble;
        shadow.appendChild(bubble);

        posBubble = _posBubbleRightOf(bubble, function() {
            var rl = parseFloat(rect.style.left), rt = parseFloat(rect.style.top);
            var rw = parseFloat(rect.style.width), rh = parseFloat(rect.style.height);
            return {rightX: rl + rw, leftX: rl, centerY: rt + rh / 2, gap: 18};
        });
        posBubble();

        // Resize & drag（命名函数，修复事件泄漏）
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

        function _rangeOnMouseMove(e) {
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
        }

        function _rangeOnMouseUp() { mode = 'none'; }

        document.addEventListener('mousemove', _rangeOnMouseMove);
        document.addEventListener('mouseup', _rangeOnMouseUp);
        _overlayCleanups.push(function() {
            document.removeEventListener('mousemove', _rangeOnMouseMove);
            document.removeEventListener('mouseup', _rangeOnMouseUp);
        });

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
        _bindSubmit(sendBtn, inp, submit);
    }
