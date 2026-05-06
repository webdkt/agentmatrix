    // ==========================================
    // Speech Bubble（Agent 说话气泡）
    // ==========================================
    function _showSpeech(text) {
        if (_speechEl) {
            // Update existing
            var txt = _speechEl.querySelector('.ab-speech-text');
            if (txt) { txt.textContent = text; txt.className = 'ab-speech-text'; }
            var more = _speechEl.querySelector('.ab-speech-more');
            if (more) more.remove();
            _applySpeechClamp(_speechEl, txt);
            return;
        }

        var el = document.createElement('div');
        el.className = 'ab-speech';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'ab-speech-close';
        closeBtn.textContent = '\u2715';
        closeBtn.addEventListener('click', function(e) { e.stopPropagation(); _hideSpeech(); });
        var txt = document.createElement('div');
        txt.className = 'ab-speech-text';
        txt.textContent = text;
        el.appendChild(closeBtn);
        el.appendChild(txt);
        shadow.appendChild(el);
        _speechEl = el;
        _applySpeechClamp(el, txt);
        _positionSpeech();
        // 新建的元素需要继承当前 dim 状态
        _syncSpeechDim();
    }

    function _applySpeechClamp(el, txt) {
        // Check if text overflows 5 lines
        setTimeout(function() {
            var lineHeight = parseFloat(getComputedStyle(txt).lineHeight) || 22.4;
            var maxHeight = lineHeight * 5;
            if (txt.scrollHeight > maxHeight + 2) {
                txt.classList.add('clamped');
                var more = document.createElement('span');
                more.className = 'ab-speech-more';
                more.textContent = '(more)';
                more.addEventListener('click', function(e) {
                    e.stopPropagation();
                    txt.classList.remove('clamped');
                    more.remove();
                });
                el.appendChild(more);
            }
        }, 30);
    }

    function _hideSpeech() {
        if (_speechEl) { _speechEl.remove(); _speechEl = null; }
    }

    function _positionSpeech() {
        if (!_speechEl) return;
        var br = btn.getBoundingClientRect();
        var bx = br.left, by = br.top, bw = br.width, bh = br.height;
        var sw = _speechEl.offsetWidth || 320, sh = _speechEl.offsetHeight || 60;
        var vw = window.innerWidth, vh = window.innerHeight;
        var gap = 12;

        // Try right side
        var rightSpace = vw - (bx + bw) - gap;
        var leftSpace = bx - gap;
        var topSpace = by - gap;
        var bottomSpace = vh - (by + bh) - gap;

        _speechEl.className = 'ab-speech';
        if (rightSpace >= sw + 10) {
            _speechEl.classList.add('tail-left');
            _speechEl.style.left = (bx + bw + gap) + 'px';
            _speechEl.style.top = Math.max(12, Math.min(by, vh - sh - 12)) + 'px';
        } else if (leftSpace >= sw + 10) {
            _speechEl.classList.add('tail-right');
            _speechEl.style.left = (bx - sw - gap) + 'px';
            _speechEl.style.top = Math.max(12, Math.min(by, vh - sh - 12)) + 'px';
        } else if (topSpace >= sh + 10) {
            _speechEl.classList.add('tail-bottom');
            _speechEl.style.left = Math.max(12, Math.min(bx, vw - sw - 12)) + 'px';
            _speechEl.style.top = (by - sh - gap) + 'px';
        } else {
            _speechEl.classList.add('tail-top');
            _speechEl.style.left = Math.max(12, Math.min(bx, vw - sw - 12)) + 'px';
            _speechEl.style.top = (by + bh + gap) + 'px';
        }
    }
