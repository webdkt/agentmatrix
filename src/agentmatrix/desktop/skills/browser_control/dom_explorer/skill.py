"""
Dom Explorer Skill — 在浏览器中执行 JS 探索 DOM 结构。

供临时 MicroAgent 使用，通过 eval_js 自由探索页面 DOM，
找到稳定的 CSS selector。

使用方式：
    MicroAgent(available_skills=["browser_automation.dom_explorer"], ...)
"""

import json
import logging

from agentmatrix.core.action import register_action

logger = logging.getLogger(__name__)


@register_action(
    short_desc="keep_user_from_bored(chat_message)，每次执行同时都要跟用户说点什么，避免用户无聊",
    description="向用户发送一条消息，避免用户无聊。消息会显示在浏览器页面的 agent 说话气泡中。",
    param_infos={
        "chat_message": "要发送给用户的消息文本",
    },
)
async def keep_user_from_bored(self, chat_message: str) -> str:
    from ..skill import _event_listener, _tab_manager

    pinned_id = getattr(self, '_pinned_tab_id', None)
    if not pinned_id:
        return json.dumps({"status": "error", "error": "未绑定 tab"})

    tab = _tab_manager._tabs.get(pinned_id) if _tab_manager else None
    if not tab:
        return json.dumps({"status": "error", "error": "绑定的 tab 已关闭"})

    if not _event_listener:
        return json.dumps({"status": "error", "error": "事件监听器未初始化"})

    try:
        await _event_listener.emit_to_browser(
            tab.session_id,
            "agent_output",
            {"type": "think", "text": chat_message},
        )
        return json.dumps({"status": "ok"})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


class Dom_explorerSkillMixin:
    """DOM 探索 skill — 提供 JS 执行能力，供 Agent 自由探索 DOM。"""

    _skill_description = "DOM 探索：在浏览器页面中执行 JavaScript 来探索 DOM 结构、测试 CSS selector"

    @register_action(
        short_desc="eval_js(code, tab_id?)在浏览器页面中执行 JavaScript 代码并返回结果。"
                    "可以写任意多行 JS（用 IIFE 包裹）。"
                    "可用的工具函数：__bh_el_info(el), __bh_tag_path(el), __bh_test(selector)。",
        description="在浏览器页面中执行 JavaScript 代码并返回结果。"
                    "可以写任意多行 JS（用 IIFE 包裹）。"
                    "可用的工具函数：__bh_el_info(el), __bh_tag_path(el), __bh_test(selector)。"
                    "查询被标记元素：document.querySelector('[__bh_marked__]')。",
        param_infos={
            "code": "要执行的 JavaScript 代码（字符串）",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def eval_js(self, code: str, tab_id: str = None) -> str:
        from ..skill import _cdp_client, _tab_manager, _tab_not_found_msg, _cdp_send_with_recovery

        if not _cdp_client or not _cdp_client._connected:
            return json.dumps({"error": "CDP client not connected"})

        if tab_id:
            tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
            if not tab:
                return json.dumps({"error": _tab_not_found_msg(tab_id)})
        else:
            pinned_id = getattr(self, '_pinned_tab_id', None)
            if not pinned_id:
                return json.dumps({"error": "未绑定 tab，请指定 tab_id"})
            tab = _tab_manager._tabs.get(pinned_id) if _tab_manager else None
            if not tab:
                return json.dumps({"error": f"绑定的 tab 已关闭 (tab_id={pinned_id})"})

        try:
            result = await _cdp_send_with_recovery(
                "Runtime.evaluate",
                {
                    "expression": code,
                    "returnByValue": True,
                    "awaitPromise": True,
                },
                tab=tab,
                timeout=15,
            )
            res = result.get("result", {})

            # CDP 执行报错
            if res.get("subtype") == "error":
                desc = res.get("description", "unknown JS error")
                logger.warning(f"[eval_js] JS exception: {desc}")
                return json.dumps({"error": desc})

            value = res.get("value")
            type_name = res.get("type", "undefined")

            if type_name == "undefined":
                return json.dumps({"type": "undefined", "value": None})
            if value is None:
                return json.dumps({"type": type_name, "value": None})
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)
        except Exception as e:
            logger.warning(f"[eval_js] CDP error: {e}")
            return json.dumps({"error": str(e)})

    @register_action(
        short_desc="return_selector(selector, addtional_info) 找到稳定的定位表达式后返回结果, addtional_info是你决定有必要的提供的关于该元素或者该selector的额外信息",
        description="找到稳定的定位表达式后调用此函数返回结果。调用后探索结束。"
                    "CSS selector 直接返回，XPath 以 'xpath:' 前缀返回。",
        param_infos={
            "selector": "找到的唯一稳定 CSS selector 或 XPath（XPath 以 'xpath:' 前缀）",
            "addtional_info": "关于元素的额外描述信息"
        },
    )
    async def return_selector(self, selector: str, addtional_info: str = "") -> str:
        return {"selector": selector, "additional_info": addtional_info}
