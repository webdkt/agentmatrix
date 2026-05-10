"""
Teaching Mode — auto-inject toolbar, capture navigation & indicator events.

When teaching mode is active:
- Listens to CDP events (Target, Page, Runtime)
- Auto-injects a teaching toolbar on every page load
- Captures indicator events (OK clicked) via console.log
- All events are buffered with tab info for the agent to consume
"""

import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .cdp_client import CDPClient
from .tab_manager import TabManager

logger = logging.getLogger(__name__)

# ---- Toolbar JS (injected on every page load) ----
TOOLBAR_JS = """
(function() {
    if (window.__bh_toolbar__) return;

    var bar = document.createElement('div');
    bar.id = '__bh_toolbar__';
    bar.style.cssText = 'position:fixed;top:0;left:0;right:0;height:36px;background:rgba(33,33,33,0.92);color:#fff;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:12px;display:flex;align-items:center;padding:0 12px;z-index:2147483647;gap:8px;box-shadow:0 1px 4px rgba(0,0,0,0.3);pointer-events:auto;';

    var status = document.createElement('span');
    status.textContent = 'Teaching Mode';
    status.style.cssText = 'opacity:0.7;margin-right:8px;';

    // "Indicator" button
    var indicatorBtn = document.createElement('button');
    indicatorBtn.textContent = '\\u6307\\u793a\\u5668';
    indicatorBtn.style.cssText = 'background:#e53935;color:#fff;border:none;border-radius:3px;padding:4px 12px;cursor:pointer;font-size:12px;font-family:inherit;';
    indicatorBtn.addEventListener('click', function() {
        // Clean up range selector first (mutual exclusion)
        if (window.__range_cleanup__) window.__range_cleanup__();
        console.log('__BH_EVENT__ ' + JSON.stringify({type:'start_teaching',mode:'indicator',url:location.href,title:document.title}));
        if (window.__bh_show_indicator__) {
            window.__bh_show_indicator__(Math.round(window.innerWidth/2), Math.round(window.innerHeight/2), '\\u8bf7\\u62d6\\u52a8\\u5706\\u5708\\u5230\\u76ee\\u6807\\u4f4d\\u7f6e');
        }
    });

    // "Range Selector" button
    var rangeBtn = document.createElement('button');
    rangeBtn.textContent = '\\u8303\\u56f4\\u6846\\u9009\\u5668';
    rangeBtn.style.cssText = 'background:#1976d2;color:#fff;border:none;border-radius:3px;padding:4px 12px;cursor:pointer;font-size:12px;font-family:inherit;';
    rangeBtn.addEventListener('click', function() {
        // Clean up indicator first (mutual exclusion)
        if (window.__indicator_cleanup__) window.__indicator_cleanup__();
        console.log('__BH_EVENT__ ' + JSON.stringify({type:'start_teaching',mode:'range',url:location.href,title:document.title}));
        if (window.__bh_show_range__) {
            window.__bh_show_range__();
        }
    });

    var urlSpan = document.createElement('span');
    urlSpan.style.cssText = 'opacity:0.5;margin-left:auto;max-width:400px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
    urlSpan.textContent = location.href;

    bar.appendChild(status);
    bar.appendChild(indicatorBtn);
    bar.appendChild(rangeBtn);
    bar.appendChild(urlSpan);
    document.body.style.paddingTop = '40px';
    document.body.appendChild(bar);
    window.__bh_toolbar__ = true;

    // ================================================================
    //  SHOW INDICATOR (crosshair + glass bubble)
    // ================================================================
    window.__bh_show_indicator__ = function(initX, initY, infoText) {
        if (window.__indicator_cleanup__) window.__indicator_cleanup__();
        var ID = '__bh_indicator__';

        var s = document.createElement('style');
        s.textContent = [
            '#' + ID + '-crosshair { position:fixed; left:' + initX + 'px; top:' + initY + 'px; width:120px; height:120px; transform:translate(-50%,-50%); z-index:2147483647; pointer-events:none; }',
            '#' + ID + '-ring { position:absolute; left:50%; top:50%; width:32px; height:32px; transform:translate(-50%,-50%); border:2.5px solid #e53935; border-radius:50%; box-sizing:border-box; box-shadow:0 0 10px rgba(229,57,53,0.35); }',
            '#' + ID + '-shl,#' + ID + '-shr,#' + ID + '-svt,#' + ID + '-svb { position:absolute; background:#e53935; }',
            '#' + ID + '-shl,#' + ID + '-shr { height:2.5px; width:16px; top:50%; transform:translateY(-50%); }',
            '#' + ID + '-svt,#' + ID + '-svb { width:2.5px; height:16px; left:50%; transform:translateX(-50%); }',
            '#' + ID + '-shl { right:calc(50% + 19px); }',
            '#' + ID + '-shr { left:calc(50% + 19px); }',
            '#' + ID + '-svt { bottom:calc(50% + 19px); }',
            '#' + ID + '-svb { top:calc(50% + 19px); }',
            '#' + ID + '-handle { position:absolute; left:50%; top:50%; width:44px; height:44px; transform:translate(-50%,-50%); border-radius:50%; cursor:grab; pointer-events:auto; background:transparent; }',
            '#' + ID + '-handle:active { cursor:grabbing; }',
            '#' + ID + '-bubble { position:fixed; z-index:2147483646; background:rgba(255,255,255,0.82); backdrop-filter:blur(16px) saturate(180%); -webkit-backdrop-filter:blur(16px) saturate(180%); border:2px dashed #e53935; border-radius:14px; box-shadow:0 8px 32px rgba(0,0,0,0.12); padding:16px 18px; min-width:220px; max-width:340px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; color:#222; line-height:1.5; pointer-events:auto; }',
            '#' + ID + '-arrow { position:absolute; width:0; height:0; }',
            '#' + ID + '-text { margin-bottom:10px; white-space:pre-wrap; word-break:break-word; font-weight:500; }',
            '#' + ID + '-input { width:100%; box-sizing:border-box; padding:8px 10px; border:1px solid rgba(0,0,0,0.12); border-radius:8px; font-size:14px; font-family:inherit; outline:none; margin-bottom:10px; background:rgba(255,255,255,0.6); pointer-events:auto; }',
            '#' + ID + '-input:focus { border-color:#e53935; box-shadow:0 0 0 3px rgba(229,57,53,0.12); }',
            '#' + ID + '-ok { display:block; width:100%; padding:8px 0; background:#e53935; color:#fff; border:none; border-radius:8px; font-size:14px; font-weight:600; font-family:inherit; cursor:pointer; pointer-events:auto; }',
            '#' + ID + '-ok:hover { background:#c62828; }',
        ].join('\\n');
        document.head.appendChild(s);

        var crosshair = document.createElement('div');
        crosshair.id = ID + '-crosshair';

        var ring = document.createElement('div');
        ring.id = ID + '-ring';
        crosshair.appendChild(ring);

        ['shl','shr','svt','svb'].forEach(function(t) {
            var seg = document.createElement('div');
            seg.id = ID + '-' + t;
            crosshair.appendChild(seg);
        });

        var handle = document.createElement('div');
        handle.id = ID + '-handle';
        crosshair.appendChild(handle);

        var bubble = document.createElement('div');
        bubble.id = ID + '-bubble';
        var arrow = document.createElement('div');
        arrow.id = ID + '-arrow';
        var textEl = document.createElement('div');
        textEl.id = ID + '-text';
        textEl.textContent = infoText;
        var inp = document.createElement('input');
        inp.id = ID + '-input';
        inp.type = 'text';
        inp.placeholder = 'Type here...';
        var okBtn = document.createElement('button');
        okBtn.id = ID + '-ok';
        okBtn.textContent = 'OK';
        bubble.appendChild(arrow);
        bubble.appendChild(textEl);
        bubble.appendChild(inp);
        bubble.appendChild(okBtn);
        document.body.appendChild(crosshair);
        document.body.appendChild(bubble);

        var gap = 32, arrSz = 18;

        function posBubble() {
            var cr = crosshair.getBoundingClientRect();
            var cx = cr.left + cr.width/2, cy = cr.top + cr.height/2;
            var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
            var vw = window.innerWidth, vh = window.innerHeight;
            var side = 'right';
            if (cx + 60 + gap + bw > vw - 12) {
                if (cx - 60 - gap - bw > 12) side = 'left';
                else if (cy + 60 + gap + bh < vh - 12) side = 'below';
                else side = 'above';
            }
            var bx, by;
            var ac = '#e53935';
            var aBase = 'position:absolute;width:0;height:0;';
            if (side==='right') {
                bx = cx + 60 + gap; by = cy - bh/2;
                arrow.style.cssText = aBase + 'left:-'+arrSz+'px;top:50%;transform:translateY(-50%);border-top:'+arrSz+'px solid transparent;border-bottom:'+arrSz+'px solid transparent;border-right:'+arrSz+'px solid '+ac+';';
            } else if (side==='left') {
                bx = cx - 60 - gap - bw; by = cy - bh/2;
                arrow.style.cssText = aBase + 'right:-'+arrSz+'px;top:50%;transform:translateY(-50%);border-top:'+arrSz+'px solid transparent;border-bottom:'+arrSz+'px solid transparent;border-left:'+arrSz+'px solid '+ac+';';
            } else if (side==='below') {
                bx = cx - bw/2; by = cy + 60 + gap;
                arrow.style.cssText = aBase + 'top:-'+arrSz+'px;left:50%;transform:translateX(-50%);border-left:'+arrSz+'px solid transparent;border-right:'+arrSz+'px solid transparent;border-bottom:'+arrSz+'px solid '+ac+';';
            } else {
                bx = cx - bw/2; by = cy - 60 - gap - bh;
                arrow.style.cssText = aBase + 'bottom:-'+arrSz+'px;left:50%;transform:translateX(-50%);border-left:'+arrSz+'px solid transparent;border-right:'+arrSz+'px solid transparent;border-top:'+arrSz+'px solid '+ac+';';
            }
            bx = Math.max(12, Math.min(bx, vw - bw - 12));
            by = Math.max(12, Math.min(by, vh - bh - 12));
            bubble.style.left = bx + 'px';
            bubble.style.top = by + 'px';
        }
        posBubble();

        var dragging = false, oX = 0, oY = 0;
        handle.addEventListener('mousedown', function(e) {
            dragging = true; handle.style.cursor = 'grabbing';
            var cr = crosshair.getBoundingClientRect();
            oX = e.clientX - (cr.left + cr.width/2);
            oY = e.clientY - (cr.top + cr.height/2);
            e.preventDefault();
        });
        document.addEventListener('mousemove', function(e) {
            if (!dragging) return;
            crosshair.style.left = (e.clientX - oX) + 'px';
            crosshair.style.top = (e.clientY - oY) + 'px';
            posBubble();
        });
        document.addEventListener('mouseup', function() { if (dragging) { dragging = false; handle.style.cursor = 'grab'; } });

        // OK: emit event, do NOT close
        okBtn.addEventListener('click', function() {
            var cr = crosshair.getBoundingClientRect();
            var result = {
                type: 'indicator_result',
                x: Math.round(cr.left + cr.width/2),
                y: Math.round(cr.top + cr.height/2),
                text: inp.value,
            };
            console.log('__BH_EVENT__ ' + JSON.stringify(result));
            window.__indicator_result__ = result;
        });
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter') okBtn.click(); });

        window.__indicator_cleanup__ = function() {
            crosshair.remove(); bubble.remove(); s.remove();
            delete window.__indicator_result__; delete window.__indicator_cleanup__;
        };
        window.__indicator_result__ = null;
        inp.focus();
    };

    // ================================================================
    //  SHOW RANGE SELECTOR (resizable rect + glass bubble)
    // ================================================================
    window.__bh_show_range__ = function() {
        if (window.__range_cleanup__) window.__range_cleanup__();
        var ID = '__bh_range__';
        var INIT_W = 300, INIT_H = 200;
        var vpW = window.innerWidth, vpH = window.innerHeight;
        var INIT_X = Math.round(vpW / 2 - INIT_W / 2);
        var INIT_Y = Math.round(vpH / 2 - INIT_H / 2);

        var s = document.createElement('style');
        s.textContent = [
            '#' + ID + '-rect { position:fixed; border:2px dashed #e53935; border-radius:6px; background:rgba(229,57,53,0.04); z-index:2147483645; cursor:move; box-sizing:border-box; user-select:none; }',
            '.' + ID + '-handle { position:absolute; width:12px; height:12px; background:#fff; border:2px solid #e53935; border-radius:2px; z-index:2147483647; box-sizing:border-box; pointer-events:auto; }',
            '.' + ID + '-tl { top:-6px; left:-6px; cursor:nw-resize; }',
            '.' + ID + '-tc { top:-6px; left:50%; margin-left:-6px; cursor:n-resize; }',
            '.' + ID + '-tr { top:-6px; right:-6px; cursor:ne-resize; }',
            '.' + ID + '-ml { top:50%; left:-6px; margin-top:-6px; cursor:w-resize; }',
            '.' + ID + '-mr { top:50%; right:-6px; margin-top:-6px; cursor:e-resize; }',
            '.' + ID + '-bl { bottom:-6px; left:-6px; cursor:sw-resize; }',
            '.' + ID + '-bc { bottom:-6px; left:50%; margin-left:-6px; cursor:s-resize; }',
            '.' + ID + '-br { bottom:-6px; right:-6px; cursor:se-resize; }',
            '#' + ID + '-bubble { position:fixed; z-index:2147483646; background:rgba(255,255,255,0.82); backdrop-filter:blur(16px) saturate(180%); -webkit-backdrop-filter:blur(16px) saturate(180%); border:2px dashed #e53935; border-radius:14px; box-shadow:0 8px 32px rgba(0,0,0,0.12); padding:16px 18px; min-width:220px; max-width:340px; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; font-size:14px; color:#222; line-height:1.5; pointer-events:auto; }',
            '#' + ID + '-arrow { position:absolute; width:0; height:0; }',
            '#' + ID + '-text { margin-bottom:10px; white-space:pre-wrap; word-break:break-word; font-weight:500; }',
            '#' + ID + '-input { width:100%; box-sizing:border-box; padding:8px 10px; border:1px solid rgba(0,0,0,0.12); border-radius:8px; font-size:14px; font-family:inherit; outline:none; margin-bottom:10px; background:rgba(255,255,255,0.6); pointer-events:auto; }',
            '#' + ID + '-input:focus { border-color:#e53935; box-shadow:0 0 0 3px rgba(229,57,53,0.12); }',
            '#' + ID + '-ok { display:block; width:100%; padding:8px 0; background:#e53935; color:#fff; border:none; border-radius:8px; font-size:14px; font-weight:600; font-family:inherit; cursor:pointer; pointer-events:auto; }',
            '#' + ID + '-ok:hover { background:#c62828; }',
        ].join('\\n');
        document.head.appendChild(s);

        // Rectangle
        var rect = document.createElement('div');
        rect.id = ID + '-rect';
        rect.style.left = INIT_X + 'px';
        rect.style.top = INIT_Y + 'px';
        rect.style.width = INIT_W + 'px';
        rect.style.height = INIT_H + 'px';

        var posNames = ['tl','tc','tr','ml','mr','bl','bc','br'];
        var handles = {};
        posNames.forEach(function(p) {
            var h = document.createElement('div');
            h.className = ID + '-handle ' + ID + '-' + p;
            h.setAttribute('data-pos', p);
            rect.appendChild(h);
            handles[p] = h;
        });

        // Bubble
        var bubble = document.createElement('div');
        bubble.id = ID + '-bubble';
        var arrow = document.createElement('div');
        arrow.id = ID + '-arrow';
        var textEl = document.createElement('div');
        textEl.id = ID + '-text';
        textEl.textContent = 'Drag edges/corners to resize.\\nDrag border to move.';
        var inp = document.createElement('input');
        inp.id = ID + '-input';
        inp.type = 'text';
        inp.placeholder = 'Describe the region...';
        var okBtn = document.createElement('button');
        okBtn.id = ID + '-ok';
        okBtn.textContent = 'OK';
        bubble.appendChild(arrow);
        bubble.appendChild(textEl);
        bubble.appendChild(inp);
        bubble.appendChild(okBtn);
        document.body.appendChild(rect);
        document.body.appendChild(bubble);

        var gap = 18, arrSz = 14;

        function posBubble() {
            var rl = parseFloat(rect.style.left), rt = parseFloat(rect.style.top);
            var rw = parseFloat(rect.style.width), rh = parseFloat(rect.style.height);
            var bw = bubble.offsetWidth, bh = bubble.offsetHeight;
            var vw = window.innerWidth, vh = window.innerHeight;
            var side = 'right';
            if (rl + rw + gap + bw > vw - 12) {
                if (rl - gap - bw > 12) side = 'left';
                else if (rt + rh + gap + bh < vh - 12) side = 'below';
                else side = 'above';
            }
            var bx, by;
            var ac = '#e53935';
            var aBase = 'position:absolute;width:0;height:0;';
            if (side==='right') {
                bx = rl + rw + gap; by = rt + rh/2 - bh/2;
                arrow.style.cssText = aBase + 'left:-'+arrSz+'px;top:50%;transform:translateY(-50%);border-top:'+arrSz+'px solid transparent;border-bottom:'+arrSz+'px solid transparent;border-right:'+arrSz+'px solid '+ac+';';
            } else if (side==='left') {
                bx = rl - gap - bw; by = rt + rh/2 - bh/2;
                arrow.style.cssText = aBase + 'right:-'+arrSz+'px;top:50%;transform:translateY(-50%);border-top:'+arrSz+'px solid transparent;border-bottom:'+arrSz+'px solid transparent;border-left:'+arrSz+'px solid '+ac+';';
            } else if (side==='below') {
                bx = rl + rw/2 - bw/2; by = rt + rh + gap;
                arrow.style.cssText = aBase + 'top:-'+arrSz+'px;left:50%;transform:translateX(-50%);border-left:'+arrSz+'px solid transparent;border-right:'+arrSz+'px solid transparent;border-bottom:'+arrSz+'px solid '+ac+';';
            } else {
                bx = rl + rw/2 - bw/2; by = rt - gap - bh;
                arrow.style.cssText = aBase + 'bottom:-'+arrSz+'px;left:50%;transform:translateX(-50%);border-left:'+arrSz+'px solid transparent;border-right:'+arrSz+'px solid transparent;border-top:'+arrSz+'px solid '+ac+';';
            }
            bx = Math.max(12, Math.min(bx, vw - bw - 12));
            by = Math.max(12, Math.min(by, vh - bh - 12));
            bubble.style.left = bx + 'px';
            bubble.style.top = by + 'px';
        }
        posBubble();

        // Resize
        var mode = 'none', resizePos = '';
        var smx, smy, sml, smt, smw, smh;
        var dragOX, dragOY;
        var MIN_W = 160, MIN_H = 100;

        posNames.forEach(function(p) {
            handles[p].addEventListener('mousedown', function(e) {
                e.stopPropagation(); e.preventDefault();
                mode = 'resize'; resizePos = p;
                smx = e.clientX; smy = e.clientY;
                sml = parseFloat(rect.style.left); smt = parseFloat(rect.style.top);
                smw = parseFloat(rect.style.width); smh = parseFloat(rect.style.height);
            });
        });

        rect.addEventListener('mousedown', function(e) {
            if (mode === 'resize') return;
            e.preventDefault();
            mode = 'drag';
            dragOX = e.clientX - parseFloat(rect.style.left);
            dragOY = e.clientY - parseFloat(rect.style.top);
        });

        document.addEventListener('mousemove', function(e) {
            if (mode === 'resize') {
                var dx = e.clientX - smx, dy = e.clientY - smy;
                var nl = sml, nt = smt, nw = smw, nh = smh;
                if (resizePos.indexOf('l') >= 0) { nl = sml + dx; nw = smw - dx; }
                if (resizePos.indexOf('r') >= 0) { nw = smw + dx; }
                if (resizePos.indexOf('t') >= 0) { nt = smt + dy; nh = smh - dy; }
                if (resizePos.indexOf('b') >= 0) { nh = smh + dy; }
                if (nw < MIN_W) { if (resizePos.indexOf('l') >= 0) nl = sml + smw - MIN_W; nw = MIN_W; }
                if (nh < MIN_H) { if (resizePos.indexOf('t') >= 0) nt = smt + smh - MIN_H; nh = MIN_H; }
                rect.style.left = nl + 'px'; rect.style.top = nt + 'px';
                rect.style.width = nw + 'px'; rect.style.height = nh + 'px';
                posBubble();
            }
            if (mode === 'drag') {
                rect.style.left = (e.clientX - dragOX) + 'px';
                rect.style.top = (e.clientY - dragOY) + 'px';
                posBubble();
            }
        });
        document.addEventListener('mouseup', function() { mode = 'none'; });

        // OK: emit event, do NOT close
        okBtn.addEventListener('click', function() {
            var result = {
                type: 'range_result',
                x: Math.round(parseFloat(rect.style.left)),
                y: Math.round(parseFloat(rect.style.top)),
                width: Math.round(parseFloat(rect.style.width)),
                height: Math.round(parseFloat(rect.style.height)),
                text: inp.value,
            };
            console.log('__BH_EVENT__ ' + JSON.stringify(result));
            window.__range_result__ = result;
        });
        inp.addEventListener('keydown', function(e) { if (e.key === 'Enter') okBtn.click(); });

        window.__range_cleanup__ = function() {
            rect.remove(); bubble.remove(); s.remove();
            delete window.__range_result__; delete window.__range_cleanup__;
        };
        window.__range_result__ = null;
        inp.focus();
    };
})();
"""


def build_toolbar_js() -> str:
    return TOOLBAR_JS


def build_indicator_with_event_js(x: int, y: int, info_text: str) -> str:
    """Build JS that calls the toolbar's __bh_show_indicator__ function."""
    return (
        "if(window.__bh_show_indicator__){"
        f"window.__bh_show_indicator__({int(x)},{int(y)},{json.dumps(info_text)})"
        "}"
    )


def build_range_selector_js() -> str:
    """Build JS that calls the toolbar's __bh_show_range__ function."""
    return "if(window.__bh_show_range__){window.__bh_show_range__()}"


CHECK_RESULT_JS = "window.__indicator_result__ || null"
CHECK_RANGE_RESULT_JS = "window.__range_result__ || null"
CLEANUP_INDICATOR_JS = "if (window.__indicator_cleanup__) window.__indicator_cleanup__();"
CLEANUP_RANGE_JS = "if (window.__range_cleanup__) window.__range_cleanup__();"
CLEANUP_TOOLBAR_JS = """
(function() {
    var bar = document.getElementById('__bh_toolbar__');
    if (bar) bar.remove();
    document.body.style.paddingTop = '';
    delete window.__bh_toolbar__;
    if (window.__indicator_cleanup__) window.__indicator_cleanup__();
    if (window.__range_cleanup__) window.__range_cleanup__();
})();
"""


@dataclass
class TeachingEvent:
    """A captured teaching mode event."""
    event_type: str          # 'navigated', 'page_loaded', 'start_teaching', 'indicator_result', 'range_result', ...
    target_id: str           # CDP target ID
    session_id: str          # CDP session ID
    timestamp: float         # time.time()
    data: Dict[str, Any] = field(default_factory=dict)   # event payload

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "target_id": self.target_id,
            "timestamp": self.timestamp,
            **self.data,
        }


class TeachingListener:
    """
    Background CDP event listener for teaching mode.

    Monitors CDP events and produces TeachingEvents.
    """

    def __init__(self, cdp: CDPClient, tab_mgr: TabManager):
        self.cdp = cdp
        self.tab_mgr = tab_mgr
        self.active = False
        self.events: deque[TeachingEvent] = deque(maxlen=200)
        self._handlers_registered = False

    def start(self):
        """Start listening to CDP events."""
        if self.active:
            return
        self.active = True
        self._register_handlers()
        logger.info("Teaching listener started")

    def stop(self):
        """Stop listening."""
        self.active = False
        logger.info("Teaching listener stopped")

    def drain_events(self, event_type: str = None) -> List[TeachingEvent]:
        """Get and clear buffered events."""
        events = list(self.events)
        self.events.clear()
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events

    def _register_handlers(self):
        if self._handlers_registered:
            return

        # Target events (new/closed tabs)
        self.cdp.on_event("Target.targetCreated", self._on_target_created)
        self.cdp.on_event("Target.targetDestroyed", self._on_target_destroyed)

        # Page events (navigation, load)
        self.cdp.on_event("Page.frameNavigated", self._on_navigated)
        self.cdp.on_event("Page.loadEventFired", self._on_load)

        # Console events (indicator results, toolbar actions)
        self.cdp.on_event("Runtime.consoleAPICalled", self._on_console)

        self._handlers_registered = True

    def _on_target_created(self, params):
        if not self.active:
            return
        info = params.get("targetInfo", {})
        self.events.append(TeachingEvent(
            event_type="tab_created",
            target_id=info.get("targetId", ""),
            session_id="",
            timestamp=time.time(),
            data={
                "url": info.get("url", ""),
                "type": info.get("type", ""),
            },
        ))

    def _on_target_destroyed(self, params):
        if not self.active:
            return
        self.events.append(TeachingEvent(
            event_type="tab_closed",
            target_id=params.get("targetId", ""),
            session_id="",
            timestamp=time.time(),
        ))

    def _on_navigated(self, params):
        if not self.active:
            return
        frame = params.get("frame", {})
        self.events.append(TeachingEvent(
            event_type="navigated",
            target_id=frame.get("id", ""),
            session_id=params.get("_sessionId", ""),
            timestamp=time.time(),
            data={
                "url": frame.get("url", ""),
                "loader_id": frame.get("loaderId", ""),
            },
        ))

    def _on_load(self, params):
        if not self.active:
            return
        self.events.append(TeachingEvent(
            event_type="page_loaded",
            target_id="",
            session_id=params.get("_sessionId", ""),
            timestamp=time.time(),
        ))

    def _on_console(self, params):
        if not self.active:
            return
        args = params.get("args", [])
        if not args:
            return
        # Check for __BH_EVENT__ prefix
        val = args[0].get("value", "")
        if not isinstance(val, str) or not val.startswith("__BH_EVENT__ "):
            return
        try:
            payload = json.loads(val[len("__BH_EVENT__ "):])
            event_type = payload.pop("type", "unknown")
            self.events.append(TeachingEvent(
                event_type=event_type,
                target_id="",
                session_id=params.get("_sessionId", ""),
                timestamp=time.time(),
                data=payload,
            ))
        except (json.JSONDecodeError, KeyError):
            pass

    async def inject_toolbar(self, session_id: str):
        """Inject the teaching toolbar into a tab."""
        try:
            await self.cdp.send(
                "Runtime.evaluate",
                {"expression": build_toolbar_js()},
                session_id=session_id,
            )
        except Exception as e:
            logger.warning(f"Failed to inject toolbar: {e}")
