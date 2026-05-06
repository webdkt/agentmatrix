    // ==========================================
    // Splash Transition（发送后过渡动画）
    // ==========================================

    /**
     * @param {object} [opts] - 可选参数
     * @param {boolean} [opts.atSpeech] - 定位到 speech bubble 位置（overlay 提交时使用）
     */
    function _showSplash(opts) {
        if (_splashActive) return;
        _splashActive = true;

        // 按 overlay 提交时：先关闭 overlay，恢复 Agent Button + speech
        if (_currentOverlay) _clearOverlay();

        var atSpeech = opts && opts.atSpeech;

        // 更新 speech 为"处理中..."（保持原始宽度）
        if (atSpeech) {
            if (_speechEl) {
                var prevW = _speechEl.offsetWidth;
                var txt = _speechEl.querySelector('.ab-speech-text');
                if (txt) { txt.textContent = '处理中...'; txt.className = 'ab-speech-text'; }
                var more = _speechEl.querySelector('.ab-speech-more');
                if (more) more.remove();
                _speechEl.style.minWidth = prevW + 'px';
            }
            // 如果没有 speech bubble，创建一个
            if (!_speechEl) {
                _showSpeech('处理中...');
            }
        }

        // 获取 speech 位置（在 _clearOverlay 之后，speech 已可见）
        var pos = atSpeech && _speechEl ? _speechEl.getBoundingClientRect() : null;

        _setToolButtonsEnabled(false);

        var overlay = document.createElement('div');
        overlay.className = 'ab-splash-overlay';

        var splash = document.createElement('div');
        splash.className = 'ab-splash';

        var spinner = document.createElement('div');
        spinner.className = 'ab-splash-spinner';

        var text = document.createElement('div');
        text.className = 'ab-splash-text';
        text.textContent = '发送指令给Agent...';

        splash.appendChild(spinner);
        splash.appendChild(text);
        overlay.appendChild(splash);

        // 定位到 speech bubble 位置（或居中 fallback）
        if (pos && pos.width > 0) {
            overlay.style.cssText = 'position:fixed;left:' + Math.round(pos.left) + 'px;top:' + Math.round(pos.top) +
                'px;width:' + Math.round(pos.width) + 'px;height:' + Math.round(pos.height) +
                'px;display:flex;align-items:center;justify-content:center;z-index:2147483647;pointer-events:auto;';
            splash.style.cssText = 'background:rgba(255,255,255,0.95);backdrop-filter:blur(20px) saturate(180%);-webkit-backdrop-filter:blur(20px) saturate(180%);border:1.5px solid rgba(0,0,0,0.12);border-radius:18px;box-shadow:0 12px 40px rgba(0,0,0,0.14),0 1px 3px rgba(0,0,0,0.08);padding:18px 24px;display:flex;flex-direction:column;align-items:center;gap:10px;animation:ab-splash-in 0.25s ease-out;';
        }

        shadow.appendChild(overlay);

        // Random duration 1-3.5s
        var duration = 1000 + Math.random() * 2500;

        setTimeout(function() {
            // Phase 2: checkmark + "已发送"
            spinner.className = 'ab-splash-check';
            spinner.textContent = '\u2713';
            text.textContent = '已发送';

            setTimeout(function() {
                // Close splash
                overlay.remove();
                if (atSpeech && _speechEl) _speechEl.style.minWidth = '';
                _splashActive = false;
                _setToolButtonsEnabled(true);
            }, 800);
        }, duration);
    }

    function _setToolButtonsEnabled(enabled) {
        var btns = shadow.querySelectorAll('.ab-bubble-send, .ab-instruct-send');
        for (var i = 0; i < btns.length; i++) {
            btns[i].disabled = !enabled;
        }
    }
