    // ==========================================
    // Instruct Bubble（给AI指示 — 屏幕居中大输入框）
    // ==========================================
    function _showInstructBubble() {
        _showOverlay('instruct');

        var overlay = document.createElement('div');
        overlay.className = 'ab-instruct-overlay';

        var card = document.createElement('div');
        card.className = 'ab-instruct';

        var cardClose = document.createElement('button');
        cardClose.className = 'ab-bubble-close';
        cardClose.textContent = '\u2715';
        cardClose.addEventListener('click', function(e) { e.stopPropagation(); _clearOverlay(); });
        card.appendChild(cardClose);

        var inp = document.createElement('textarea');
        inp.className = 'ab-instruct-input';
        inp.placeholder = '给AI指示，告诉他要做什么要找什么';
        inp.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, window.innerHeight * 0.5) + 'px';
        });

        var footer = document.createElement('div');
        footer.className = 'ab-instruct-footer';

        var cancelBtn = document.createElement('button');
        cancelBtn.className = 'ab-instruct-cancel';
        cancelBtn.textContent = '取消';

        var sendBtn = document.createElement('button');
        sendBtn.className = 'ab-instruct-send';
        sendBtn.textContent = '发送';

        footer.appendChild(cancelBtn);
        footer.appendChild(sendBtn);
        card.appendChild(inp);
        card.appendChild(footer);
        overlay.appendChild(card);
        shadow.appendChild(overlay);
        _instructBubble = overlay;

        cancelBtn.addEventListener('click', function() { _clearOverlay(); });

        function submit() {
            if (_splashActive) return;
            var text = inp.value.trim();
            if (!text) return;
            window.__bh_emit__('chat_message', {text: text});
            _bufPush({type: 'chat_message', text: text, ts: Date.now(), from: 'user'});
            _showSplash({atSpeech: true});
        }
        _bindSubmit(sendBtn, inp, submit);
    }
