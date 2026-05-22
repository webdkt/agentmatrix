"""
Indicator — draggable on-page indicator with info bubble.

Injects a red hollow circle + speech bubble into the page via JS.
The circle is draggable; the bubble follows and flips at viewport edges.
When OK is clicked, the result (x, y, input_text) is stored in
window.__indicator_result__ for the backend to read.
"""

import json

# JS that creates the indicator. Injected via Runtime.evaluate.
# After injection, poll window.__indicator_result__ to get the user's response.
INDICATOR_JS = """
(function() {
    // Clean up any existing indicator
    if (window.__indicator_cleanup__) window.__indicator_cleanup__();

    const INIT_X = __INIT_X__;
    const INIT_Y = __INIT_Y__;
    const INFO_TEXT = __INFO_TEXT__;
    const ID = '__bh_indicator__';

    // ---- Styles ----
    const style = document.createElement('style');
    style.textContent = `
        #${ID}-circle {
            position: fixed;
            width: 32px; height: 32px;
            border: 3px solid #e53935;
            border-radius: 50%;
            background: transparent;
            cursor: grab;
            z-index: 2147483647;
            transform: translate(-50%, -50%);
            box-shadow: 0 0 8px rgba(229,57,53,0.3);
            transition: box-shadow 0.15s;
            pointer-events: auto;
        }
        #${ID}-circle:hover {
            box-shadow: 0 0 16px rgba(229,57,53,0.5);
        }
        #${ID}-bubble {
            position: fixed;
            z-index: 2147483646;
            background: #fff;
            border: 1px solid #ccc;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            padding: 12px 14px;
            min-width: 180px;
            max-width: 300px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            font-size: 13px;
            color: #333;
            line-height: 1.4;
            pointer-events: auto;
        }
        #${ID}-arrow {
            position: absolute;
            width: 0; height: 0;
        }
        #${ID}-text {
            margin-bottom: 8px;
            white-space: pre-wrap;
            word-break: break-word;
        }
        #${ID}-input {
            width: 100%;
            box-sizing: border-box;
            padding: 6px 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 13px;
            font-family: inherit;
            outline: none;
            margin-bottom: 8px;
        }
        #${ID}-input:focus {
            border-color: #e53935;
            box-shadow: 0 0 0 2px rgba(229,57,53,0.15);
        }
        #${ID}-ok {
            display: block;
            width: 100%;
            padding: 6px 0;
            background: #e53935;
            color: #fff;
            border: none;
            border-radius: 4px;
            font-size: 13px;
            font-family: inherit;
            cursor: pointer;
            transition: background 0.15s;
        }
        #${ID}-ok:hover { background: #c62828; }
    `;
    document.head.appendChild(style);

    // ---- Circle ----
    const circle = document.createElement('div');
    circle.id = ID + '-circle';
    circle.style.left = INIT_X + 'px';
    circle.style.top  = INIT_Y + 'px';

    // ---- Bubble ----
    const bubble = document.createElement('div');
    bubble.id = ID + '-bubble';

    // Arrow (CSS triangle)
    const arrow = document.createElement('div');
    arrow.id = ID + '-arrow';

    // Text
    const textEl = document.createElement('div');
    textEl.id = ID + '-text';
    textEl.textContent = INFO_TEXT;

    // Input
    const input = document.createElement('input');
    input.id = ID + '-input';
    input.type = 'text';
    input.placeholder = 'Type here...';

    // OK button
    const okBtn = document.createElement('button');
    okBtn.id = ID + '-ok';
    okBtn.textContent = 'OK';

    bubble.appendChild(arrow);
    bubble.appendChild(textEl);
    bubble.appendChild(input);
    bubble.appendChild(okBtn);

    document.body.appendChild(circle);
    document.body.appendChild(bubble);

    // ---- Position bubble relative to circle ----
    // placement: 'right', 'left', 'below', 'above'
    let placement = 'right';

    function positionBubble() {
        const cr = circle.getBoundingClientRect();
        const cx = cr.left + cr.width / 2;
        const cy = cr.top + cr.height / 2;
        const bw = bubble.offsetWidth;
        const bh = bubble.offsetHeight;
        const gap = 14;  // space between circle and bubble
        const arrowSize = 8;
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        // Try right first, then left, below, above
        const tries = ['right', 'left', 'below', 'above'];
        let chosen = 'right';

        for (const p of tries) {
            if (p === 'right'  && cx + 16 + gap + bw < vw - 8)  { chosen = 'right';  break; }
            if (p === 'left'   && cx - 16 - gap - bw > 8)       { chosen = 'left';   break; }
            if (p === 'below'  && cy + 16 + gap + bh < vh - 8)  { chosen = 'below';  break; }
            if (p === 'above'  && cy - 16 - gap - bh > 8)       { chosen = 'above';  break; }
        }
        placement = chosen;

        let bx, by;

        if (placement === 'right') {
            bx = cx + 16 + gap;
            by = cy - bh / 2;
            arrow.style.cssText = `
                left: -${arrowSize}px; top: 50%; transform: translateY(-50%);
                border-top: ${arrowSize}px solid transparent;
                border-bottom: ${arrowSize}px solid transparent;
                border-right: ${arrowSize}px solid #ccc;
            `;
        } else if (placement === 'left') {
            bx = cx - 16 - gap - bw;
            by = cy - bh / 2;
            arrow.style.cssText = `
                right: -${arrowSize}px; top: 50%; transform: translateY(-50%);
                border-top: ${arrowSize}px solid transparent;
                border-bottom: ${arrowSize}px solid transparent;
                border-left: ${arrowSize}px solid #ccc;
            `;
        } else if (placement === 'below') {
            bx = cx - bw / 2;
            by = cy + 16 + gap;
            arrow.style.cssText = `
                top: -${arrowSize}px; left: 50%; transform: translateX(-50%);
                border-left: ${arrowSize}px solid transparent;
                border-right: ${arrowSize}px solid transparent;
                border-bottom: ${arrowSize}px solid #ccc;
            `;
        } else { // above
            bx = cx - bw / 2;
            by = cy - 16 - gap - bh;
            arrow.style.cssText = `
                bottom: -${arrowSize}px; left: 50%; transform: translateX(-50%);
                border-left: ${arrowSize}px solid transparent;
                border-right: ${arrowSize}px solid transparent;
                border-top: ${arrowSize}px solid #ccc;
            `;
        }

        // Clamp to viewport
        bx = Math.max(8, Math.min(bx, vw - bw - 8));
        by = Math.max(8, Math.min(by, vh - bh - 8));

        bubble.style.left = bx + 'px';
        bubble.style.top  = by + 'px';
    }

    positionBubble();

    // ---- Drag ----
    let dragging = false;
    let offsetX = 0, offsetY = 0;

    circle.addEventListener('mousedown', (e) => {
        dragging = true;
        circle.style.cursor = 'grabbing';
        const cr = circle.getBoundingClientRect();
        offsetX = e.clientX - (cr.left + cr.width / 2);
        offsetY = e.clientY - (cr.top + cr.height / 2);
        e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        circle.style.left = (e.clientX - offsetX) + 'px';
        circle.style.top  = (e.clientY - offsetY) + 'px';
        positionBubble();
    });

    document.addEventListener('mouseup', () => {
        if (dragging) {
            dragging = false;
            circle.style.cursor = 'grab';
        }
    });

    // ---- OK click ----
    okBtn.addEventListener('click', () => {
        const cr = circle.getBoundingClientRect();
        const finalX = Math.round(cr.left + cr.width / 2);
        const finalY = Math.round(cr.top + cr.height / 2);
        const inputVal = input.value;

        window.__indicator_result__ = {
            x: finalX,
            y: finalY,
            text: inputVal,
        };

        // Visual feedback: fade out
        circle.style.transition = 'opacity 0.3s';
        bubble.style.transition = 'opacity 0.3s';
        circle.style.opacity = '0';
        bubble.style.opacity = '0';
        setTimeout(() => {
            circle.remove();
            bubble.remove();
            style.remove();
        }, 350);
    });

    // Enter key submits
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') okBtn.click();
    });

    // ---- Cleanup function ----
    window.__indicator_cleanup__ = function() {
        circle.remove();
        bubble.remove();
        style.remove();
        delete window.__indicator_result__;
        delete window.__indicator_cleanup__;
    };

    // Clear any previous result
    window.__indicator_result__ = null;

    // Focus the input
    input.focus();
})();
"""


def build_indicator_js(x: int, y: int, info_text: str) -> str:
    """Build the JS string with coordinates and text injected."""
    js = INDICATOR_JS
    js = js.replace("__INIT_X__", str(x))
    js = js.replace("__INIT_Y__", str(y))
    js = js.replace("__INFO_TEXT__", json.dumps(info_text))
    return js


# JS to check if the user has clicked OK
CHECK_RESULT_JS = "window.__indicator_result__ || null"

# JS to remove the indicator
CLEANUP_INDICATOR_JS = """
if (window.__indicator_cleanup__) window.__indicator_cleanup__();
"""
