/**
 * Ask Dialog — 可拖动的提问对话框组件。
 *
 * 通过 window.__bh_ask_user__(config) 调用。
 * config: { question, choices?, multi? }
 *   - 无 choices → 纯文本输入
 *   - choices + 无 multi → 单选 + 自由输入
 *   - choices + multi: true → 多选 + 自由输入
 *
 * 提交时调用 __bh_emit__('user_answer', {choices: [...], text: "..."})
 *
 * 使用 Shadow DOM 隔离样式，可自由拖动。
 */
(function() {
    // 防止重复定义
    if (window.__bh_ask_user__) return;

    window.__bh_ask_user__ = function(config) {
        // 清除已有的 ask dialog
        var old = document.getElementById('__bh_ask_host__');
        if (old) old.remove();

        var question = config.question || '请输入';
        var choices = config.choices || [];
        var multi = !!config.multi;

        // Shadow DOM host
        var host = document.createElement('div');
        host.id = '__bh_ask_host__';
        host.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;pointer-events:none;z-index:2147483647;';
        var shadow = host.attachShadow({mode: 'open'});

        // 样式
        var style = document.createElement('style');
        style.textContent = [
            '.dialog { position:fixed; pointer-events:auto; background:#fff; border-radius:12px; box-shadow:0 12px 40px rgba(0,0,0,0.2); min-width:320px; max-width:480px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; color:#222; overflow:hidden; }',

            '.titlebar { display:flex; align-items:center; padding:10px 16px; background:#f5f5f5; border-bottom:1px solid #e0e0e0; cursor:move; user-select:none; }',
            '.titlebar-text { flex:1; font-weight:600; font-size:13px; color:#555; }',
            '.titlebar-close { background:none; border:none; font-size:18px; color:#999; cursor:pointer; padding:0 4px; line-height:1; }',
            '.titlebar-close:hover { color:#e53935; }',

            '.body { padding:16px; max-height:60vh; overflow-y:auto; }',
            '.question { font-size:15px; line-height:1.6; margin-bottom:14px; white-space:pre-wrap; word-break:break-word; }',

            '.choice-item { display:flex; align-items:center; padding:6px 0; cursor:pointer; }',
            '.choice-item input { margin-right:8px; cursor:pointer; }',
            '.choice-item label { cursor:pointer; flex:1; }',

            '.divider { height:1px; background:#e0e0e0; margin:12px 0; }',
            '.input-label { font-size:12px; color:#888; margin-bottom:6px; }',
            '.text-input { width:100%; box-sizing:border-box; padding:8px 10px; border:1px solid #ddd; border-radius:8px; font-size:14px; font-family:inherit; outline:none; resize:vertical; min-height:60px; }',
            '.text-input:focus { border-color:#1976d2; box-shadow:0 0 0 3px rgba(25,118,210,0.1); }',

            '.footer { padding:12px 16px; border-top:1px solid #eee; display:flex; justify-content:flex-end; }',
            '.submit-btn { padding:8px 24px; background:#1976d2; color:#fff; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; font-family:inherit; }',
            '.submit-btn:hover { background:#1565c0; }',
        ].join('\n');
        shadow.appendChild(style);

        // Dialog
        var dialog = document.createElement('div');
        dialog.className = 'dialog';
        // 初始居中
        dialog.style.left = Math.max(20, Math.round(window.innerWidth/2 - 200)) + 'px';
        dialog.style.top = Math.max(20, Math.round(window.innerHeight/2 - 150)) + 'px';

        // Titlebar
        var titlebar = document.createElement('div');
        titlebar.className = 'titlebar';
        var titleText = document.createElement('span');
        titleText.className = 'titlebar-text';
        titleText.textContent = 'Agent 提问';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'titlebar-close';
        closeBtn.textContent = '✕';
        closeBtn.title = '关闭';
        titlebar.appendChild(titleText);
        titlebar.appendChild(closeBtn);
        dialog.appendChild(titlebar);

        // Body
        var body = document.createElement('div');
        body.className = 'body';

        // 问题文本
        var q = document.createElement('div');
        q.className = 'question';
        q.textContent = question;
        body.appendChild(q);

        // 选项
        if (choices.length > 0) {
            var choiceGroup = document.createElement('div');
            choiceGroup.className = 'choice-group';
            choices.forEach(function(choice, idx) {
                var item = document.createElement('div');
                item.className = 'choice-item';
                var input = document.createElement('input');
                input.type = multi ? 'checkbox' : 'radio';
                input.name = '__bh_ask_choice__';
                input.value = choice;
                input.id = '__bh_choice_' + idx;
                var label = document.createElement('label');
                label.htmlFor = input.id;
                label.textContent = choice;
                item.appendChild(input);
                item.appendChild(label);
                choiceGroup.appendChild(item);
            });
            body.appendChild(choiceGroup);
        }

        // 分割线 + 自由输入
        var divider = document.createElement('div');
        divider.className = 'divider';
        body.appendChild(divider);

        var inputLabel = document.createElement('div');
        inputLabel.className = 'input-label';
        inputLabel.textContent = choices.length > 0 ? '补充说明（可选）' : '请输入你的回答';
        body.appendChild(inputLabel);

        var textInput = document.createElement('textarea');
        textInput.className = 'text-input';
        textInput.placeholder = '输入内容...';
        body.appendChild(textInput);

        dialog.appendChild(body);

        // Footer
        var footer = document.createElement('div');
        footer.className = 'footer';
        var submitBtn = document.createElement('button');
        submitBtn.className = 'submit-btn';
        submitBtn.textContent = '提交';
        footer.appendChild(submitBtn);
        dialog.appendChild(footer);

        shadow.appendChild(dialog);
        document.body.appendChild(host);

        // ---- 拖动 ----
        var dragging = false, startX = 0, startY = 0, startLeft = 0, startTop = 0;
        titlebar.addEventListener('mousedown', function(e) {
            if (e.target === closeBtn) return;
            dragging = true;
            startX = e.clientX;
            startY = e.clientY;
            startLeft = parseInt(dialog.style.left) || 0;
            startTop = parseInt(dialog.style.top) || 0;
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            var dx = e.clientX - startX;
            var dy = e.clientY - startY;
            var newLeft = startLeft + dx;
            var newTop = startTop + dy;
            // 限制不超出视口
            newLeft = Math.max(0, Math.min(newLeft, window.innerWidth - 100));
            newTop = Math.max(0, Math.min(newTop, window.innerHeight - 50));
            dialog.style.left = newLeft + 'px';
            dialog.style.top = newTop + 'px';
        });
        document.addEventListener('mouseup', function() { dragging = false; });

        // ---- 关闭 ----
        function close() {
            host.remove();
            window.__bh_emit__('user_answer', { choices: [], text: '', cancelled: true });
        }
        closeBtn.addEventListener('click', close);

        // ---- 提交 ----
        function submit() {
            var selected = [];
            var inputs = choiceGroup ? choiceGroup.querySelectorAll('input:checked') : [];
            inputs.forEach(function(inp) { selected.push(inp.value); });

            var text = textInput.value.trim();
            if (choices.length === 0 && !text) {
                textInput.style.borderColor = '#e53935';
                textInput.focus();
                return;
            }

            window.__bh_emit__('user_answer', {
                choices: selected,
                text: text,
                cancelled: false
            });
            host.remove();
        }
        submitBtn.addEventListener('click', submit);
        textInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey && choices.length === 0) {
                e.preventDefault();
                submit();
            }
        });

        // 自动聚焦
        if (choices.length === 0) {
            textInput.focus();
        }
    };
})();
