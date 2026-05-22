    // ==========================================
    // 事件绑定 + IIFE 结尾
    // 此文件在拼接时位于所有模块文件之后
    // ==========================================

    function __bh_init_overlay() {
    if (!document.body) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', __bh_init_overlay);
        } else {
            setTimeout(__bh_init_overlay, 50);
        }
        return;
    }

    // ==========================================
    // Mount Shadow DOM host
    // ==========================================
    document.body.appendChild(host);

    // ==========================================
    // Health check：确保 host 始终在 DOM 中且位于最顶层
    // 适应复杂页面框架（Oracle ADF、React SPA 等）的 DOM 重构
    // ==========================================
    setInterval(function() {
        // 1. Host 被框架移除（如 document.body 被替换）→ 重新挂载
        if (!host.isConnected) {
            (document.body || document.documentElement).appendChild(host);
        }
        // 2. 确保 host 是 body 最后一个子元素
        //    同 z-index 时，后出现的元素在上层
        if (document.body && host.parentElement === document.body && host !== document.body.lastElementChild) {
            document.body.appendChild(host);
        }
    }, 2000);

    // ==========================================
    // 暴露 indicator / range 触发函数（供后端 CDP 调用）
    // ==========================================
    window.__bh_show_indicator__ = function(agentName, sessionId) {
        _showIndicator(Math.round(window.innerWidth / 2), Math.round(window.innerHeight / 2), '拖动准心到目标位置', agentName, sessionId);
    };
    window.__bh_show_range__ = function(agentName, sessionId) {
        _showRangeSelector(agentName, sessionId);
    };

    // ==========================================
    // Escape key to cancel active tool
    // ==========================================
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            if (_currentOverlay) {
                _clearOverlay();
            }
        }
    });

    // ==========================================
    // Backend event handler
    // ==========================================
    window.__bh_event_listeners__.push(function(type, data) {
        if (type === 'show_indicator') {
            _showIndicator(
                data.x || Math.round(window.innerWidth / 2),
                data.y || Math.round(window.innerHeight / 2),
                data.text || '拖动准心到目标位置'
            );
        } else if (type === 'show_range') {
            _showRangeSelector();
        } else if (type === 'connection_status') {
            if (!data.connected) {
                if (!shadow.querySelector('.ab-disconnect-banner')) {
                    var b = document.createElement('div');
                    b.className = 'ab-disconnect-banner';
                    b.textContent = 'Backend disconnected \u2014 reconnecting...';
                    shadow.appendChild(b);
                }
            } else {
                var banner = shadow.querySelector('.ab-disconnect-banner');
                if (banner) banner.remove();
            }
        }
    });

    } // end __bh_init_overlay
    __bh_init_overlay();
})();
