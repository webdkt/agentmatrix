"""
Dom Explorer Skill — 在浏览器中执行 JS 探索 DOM 结构。

供临时 MicroAgent 使用，通过 eval_js 自由探索页面 DOM，
找到稳定的 CSS selector。

使用方式：
    MicroAgent(available_skills=["cdp_browser.dom_explorer"], ...)
"""

import json
import logging

from agentmatrix.core.action import register_action

logger = logging.getLogger(__name__)


class Dom_explorerSkillMixin:
    """DOM 探索 skill — 提供 JS 执行能力，供 Agent 自由探索 DOM。"""

    _skill_description = "DOM 探索：在浏览器页面中执行 JavaScript 来探索 DOM 结构、测试 CSS selector"

    @register_action(
        short_desc="eval_js(code, tab_id)",
        description="在浏览器页面中执行 JavaScript 代码并返回结果。"
                    "可以写任意多行 JS（用 IIFE 包裹）。"
                    "可用的工具函数：__bh_el_info(el), __bh_tag_path(el), __bh_test(selector)。"
                    "查询被标记元素：document.querySelector('[__bh_marked__]')。",
        param_infos={
            "code": "要执行的 JavaScript 代码（字符串）",
            "tab_id": "目标 tab 的 target_id（从信号中获取）",
        },
    )
    async def eval_js(self, code: str, tab_id: str) -> str:
        from ..skill import _cdp_client, _tab_manager

        if not _cdp_client or not _cdp_client._connected:
            return json.dumps({"error": "CDP client not connected"})

        tab = _tab_manager._tabs.get(tab_id) if _tab_manager else None
        if not tab:
            return json.dumps({"error": f"Tab {tab_id} not found"})

        try:
            result = await _cdp_client.send(
                "Runtime.evaluate",
                {
                    "expression": code,
                    "returnByValue": True,
                    "awaitPromise": False,
                },
                session_id=tab.session_id,
                timeout=10,
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
        short_desc="return_selector(selector)",
        description="找到稳定的定位表达式后调用此函数返回结果。调用后探索结束。"
                    "CSS selector 直接返回，XPath 以 'xpath:' 前缀返回。",
        param_infos={"selector": "找到的唯一稳定 CSS selector 或 XPath（XPath 以 'xpath:' 前缀）"},
    )
    async def return_selector(self, selector: str) -> str:
        return selector
