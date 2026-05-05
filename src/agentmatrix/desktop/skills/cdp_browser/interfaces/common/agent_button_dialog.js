    // ==========================================
    // Ask Dialog
    // ==========================================
    window.__bh_ask_user__ = function(config) {
        // Remove existing
        if (_askHost) { _askHost.remove(); _askHost = null; }

        var question = config.question || '请输入';
        var choices = config.choices || [];
        var multi = !!config.multi;

        var overlay = document.createElement('div');
        overlay.className = 'ab-dialog-overlay';

        var dialog = document.createElement('div');
        dialog.className = 'ab-dialog';

        // Header
        var header = document.createElement('div');
        header.className = 'ab-dialog-header';
        var title = document.createElement('span');
        title.className = 'ab-dialog-title';
        title.textContent = 'Agent 提问';
        var closeBtn = document.createElement('button');
        closeBtn.className = 'ab-dialog-close';
        closeBtn.textContent = '\u2715';
        header.appendChild(title);
        header.appendChild(closeBtn);
        dialog.appendChild(header);

        // Body
        var body = document.createElement('div');
        body.className = 'ab-dialog-body';

        var q = document.createElement('div');
        q.className = 'ab-dialog-question';
        q.textContent = question;
        body.appendChild(q);

        var choiceGroup = null;
        if (choices.length > 0) {
            choiceGroup = document.createElement('div');
            choices.forEach(function(choice, idx) {
                var item = document.createElement('div');
                item.className = 'ab-dialog-choice';
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

        var divider = document.createElement('div');
        divider.className = 'ab-dialog-divider';
        body.appendChild(divider);

        var inputLabel = document.createElement('div');
        inputLabel.className = 'ab-dialog-input-label';
        inputLabel.textContent = choices.length > 0 ? '补充说明（可选）' : '请输入你的回答';
        body.appendChild(inputLabel);

        var textInput = document.createElement('textarea');
        textInput.className = 'ab-dialog-textarea';
        textInput.placeholder = '输入内容...';
        body.appendChild(textInput);

        dialog.appendChild(body);

        // Footer
        var footer = document.createElement('div');
        footer.className = 'ab-dialog-footer';
        var submitBtn = document.createElement('button');
        submitBtn.className = 'ab-dialog-submit';
        submitBtn.textContent = '提交';
        footer.appendChild(submitBtn);
        dialog.appendChild(footer);

        overlay.appendChild(dialog);
        shadow.appendChild(overlay);
        _askHost = overlay;

        // Close
        function close() {
            if (_askHost) { _askHost.remove(); _askHost = null; }
            window.__bh_emit__('user_answer', {choices: [], text: '', cancelled: true});
        }
        closeBtn.addEventListener('click', close);
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) close();
        });

        // Submit
        function submit() {
            var selected = [];
            if (choiceGroup) {
                choiceGroup.querySelectorAll('input:checked').forEach(function(inp) {
                    selected.push(inp.value);
                });
            }
            var text = textInput.value.trim();
            if (choices.length === 0 && !text) {
                textInput.style.borderColor = 'var(--danger)';
                textInput.focus();
                return;
            }
            window.__bh_emit__('user_answer', {choices: selected, text: text, cancelled: false});
            if (_askHost) { _askHost.remove(); _askHost = null; }
        }
        submitBtn.addEventListener('click', submit);
        textInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey && choices.length === 0) {
                e.preventDefault();
                submit();
            }
        });

        if (choices.length === 0) textInput.focus();
    };
