/**
 * Bridge JS — 注入到每个页面，提供前后端通信基础设施。
 *
 * 前端→后端：window.__bh_emit__(type, data)
 * 后端→前端：window.__bh_on_event__(type, data)（由 interface 设置处理函数）
 */
(function() {
    // 防止重复注入
    if (window.__bh_bridge_loaded__) return;
    window.__bh_bridge_loaded__ = true;

    /**
     * 前端 → 后端：发送事件
     * 所有 UI 组件通过此函数与后端通信。
     *
     * @param {string} eventType - 事件类型（如 'click', 'indicator_result', 'user_input'）
     * @param {object} data - 事件数据
     */
    window.__bh_emit__ = function(eventType, data) {
        var payload = {
            type: eventType,
            ts: Date.now(),
            url: location.href,
            title: document.title
        };
        if (data && typeof data === 'object') {
            for (var k in data) {
                if (data.hasOwnProperty(k)) payload[k] = data[k];
            }
        }
        console.log('__BH_EVENT__ ' + JSON.stringify(payload));
    };

    /**
     * 后端 → 前端：事件接收函数
     * Interface 可以设置此函数来处理后端推送的事件。
     *
     * 事件类型约定：
     * - 'agent_thinking': Agent 正在思考，前端显示等待状态
     * - 'agent_done': Agent 处理完成，前端恢复可交互
     * - 'highlight': 高亮某个元素 {selector, duration}
     * - 'message': 显示消息 {text, level}
     */
    window.__bh_on_event__ = null;

    /**
     * 工具：获取页面元素在视口中的位置信息
     */
    window.__bh_get_element_info__ = function(x, y) {
        // 暂时隐藏 bridge 自身的 UI，以免遮挡目标元素
        var host = document.getElementById('__bh_host__');
        if (host) host.style.pointerEvents = 'none';
        var el = document.elementFromPoint(x, y);
        if (host) host.style.pointerEvents = '';

        if (!el) return null;
        return {
            tagName: el.tagName.toLowerCase(),
            id: el.id || '',
            className: el.className || '',
            text: (el.textContent || '').substring(0, 200).trim(),
            rect: {
                x: Math.round(el.getBoundingClientRect().left),
                y: Math.round(el.getBoundingClientRect().top),
                width: Math.round(el.getBoundingClientRect().width),
                height: Math.round(el.getBoundingClientRect().height)
            },
            attributes: Array.from(el.attributes).reduce(function(acc, attr) {
                if (['class', 'id', 'style'].indexOf(attr.name) === -1) {
                    acc[attr.name] = attr.value;
                }
                return acc;
            }, {})
        };
    };
})();
