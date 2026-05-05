    // ==========================================
    // Splash Transition（发送后过渡动画）
    // ==========================================

    function _showSplash() {
        if (_splashActive) return;
        _splashActive = true;

        // Disable OK/send buttons
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
