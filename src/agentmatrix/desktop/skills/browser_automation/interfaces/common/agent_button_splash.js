    // ==========================================
    // Splash Transition（发送后过渡动画）
    // 居中 overlay 显示 spinner → checkmark
    // ==========================================

    function _showSplash() {
        if (_splashActive) return;
        _splashActive = true;

        // 按 overlay 提交时：先关闭 overlay
        if (_currentOverlay) _clearOverlay();

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
            }, 800);
        }, duration);
    }
