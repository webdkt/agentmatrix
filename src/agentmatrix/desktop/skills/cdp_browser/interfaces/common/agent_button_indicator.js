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
