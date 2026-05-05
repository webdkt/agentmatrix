    // ==========================================
    // Indicator（十字准心）
    // ==========================================
    function _showIndicator(initX, initY, infoText) {
        _showOverlay('indicator');

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

        // Bubble（deferred posBubble 解决循环依赖）
        var posBubble = function() {};
        var parts = _createBubble('拖动准星到目标位置，然后告诉Agent这是什么要做什么', function() { posBubble(); });
        var bubble = parts.el, inp = parts.inp, sendBtn = parts.sendBtn;
        _indicatorBubble = bubble;
        shadow.appendChild(bubble);

        posBubble = _posBubbleRightOf(bubble, function() {
            var cr = crosshair.getBoundingClientRect();
            return {rightX: cr.left + cr.width / 2, leftX: cr.left + cr.width / 2, centerY: cr.top + cr.height / 2, gap: 70};
        });
        posBubble();

        // Drag（带清理）
        var dragCtrl = _makeDraggable(crosshair, handle, posBubble);
        _overlayCleanups.push(dragCtrl.destroy);

        // Submit（indicator 特有的 elementFromPoint 逻辑）
        function submit() {
            if (_splashActive) return;
            var cr = crosshair.getBoundingClientRect();
            var x = Math.round(cr.left + cr.width / 2);
            var y = Math.round(cr.top + cr.height / 2);
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
        _bindSubmit(sendBtn, inp, submit);
    }
