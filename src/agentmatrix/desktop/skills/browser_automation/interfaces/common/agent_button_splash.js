    // ==========================================
    // Splash Transition（发送后过渡动画）
    // 直接在 speech bubble 上显示，保持位置和大小一致
    // ==========================================

    /**
     * @param {object} [opts] - 可选参数
     * @param {boolean} [opts.atSpeech] - 在 speech bubble 上显示（overlay 提交时使用）
     */
    function _showSplash(opts) {
        if (_splashActive) return;
        _splashActive = true;

        // 按 overlay 提交时：先关闭 overlay，恢复 Agent Button + speech
        if (_currentOverlay) _clearOverlay();

        var atSpeech = opts && opts.atSpeech;

        // 确保 speech bubble 存在
        if (atSpeech && !_speechEl) {
            _showSpeech('');
        }

        _setToolButtonsEnabled(false);

        if (atSpeech && _speechEl) {
            // ── 直接在 speech bubble 上显示 splash ──
            _hideSpeechReply();

            // 隐藏关闭按钮和 more 按钮
            var closeBtn = _speechEl.querySelector('.ab-speech-close');
            var moreBtn = _speechEl.querySelector('.ab-speech-more');
            if (closeBtn) closeBtn.style.display = 'none';
            if (moreBtn) moreBtn.style.display = 'none';

            // 替换文本内容为 spinner + 提示
            var txt = _speechEl.querySelector('.ab-speech-text');
            if (txt) {
                txt.className = 'ab-speech-text';
                txt.innerHTML = '<div class="ab-splash-spinner" style="display:inline-block;vertical-align:middle;margin-right:10px;width:22px;height:22px;border:2.5px solid rgba(99,102,241,0.2);border-top-color:#6366f1;border-radius:50%;animation:ab-spin 0.8s linear infinite;"></div><span style="font-weight:600;">发送指令给Agent...</span>';
            }

            // Random duration 1-3.5s
            var duration = 1000 + Math.random() * 2500;

            setTimeout(function() {
                // Phase 2: checkmark + "已发送"
                if (txt) {
                    txt.innerHTML = '<span style="color:#16a34a;font-weight:600;">✓ 已发送</span>';
                }

                setTimeout(function() {
                    // 恢复为等待状态，直到新消息替换
                    if (txt) {
                        txt.innerHTML = '<span style="color:var(--text-dim);font-style:italic;">等待Agent消息...</span>';
                        txt.className = 'ab-speech-text';
                    }
                    if (closeBtn) closeBtn.style.display = '';
                    _speechEl.style.minWidth = '';
                    _splashActive = false;
                    _setToolButtonsEnabled(true);
                }, 800);
            }, duration);

        } else {
            // ── Fallback: 无 speech bubble 时用居中 overlay ──
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
            shadow.appendChild(overlay);

            var duration = 1000 + Math.random() * 2500;

            setTimeout(function() {
                spinner.className = 'ab-splash-check';
                spinner.textContent = '\u2713';
                text.textContent = '已发送';

                setTimeout(function() {
                    overlay.remove();
                    _splashActive = false;
                    _setToolButtonsEnabled(true);
                }, 800);
            }, duration);
        }
    }

    function _setToolButtonsEnabled(enabled) {
        var btns = shadow.querySelectorAll('.ab-bubble-send, .ab-instruct-send');
        for (var i = 0; i < btns.length; i++) {
            btns[i].disabled = !enabled;
        }
    }
