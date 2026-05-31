"""
Dom Explorer Skill — 在浏览器中执行 JS 探索 DOM 结构。

供临时 MicroAgent 使用，通过 eval_js 自由探索页面 DOM，
找到稳定的 CSS selector。

使用方式：
    MicroAgent(available_skills=["browser_automation.dom_explorer"], ...)
"""

import json
import logging
import asyncio

from agentmatrix.core.action import register_action

logger = logging.getLogger(__name__)


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
        from .._shared import infra, _tab_not_found_msg, _cdp_send_with_recovery

        cdp = infra["cdp_client"]
        if not cdp or not cdp._connected:
            return json.dumps({"error": "CDP client not connected"})

        if tab_id:
            tab = infra["tab_manager"]._tabs.get(tab_id) if infra["tab_manager"] else None
            if not tab:
                return json.dumps({"error": _tab_not_found_msg(tab_id)})
        else:
            pinned_id = getattr(self, '_pinned_tab_id', None)
            if not pinned_id:
                return json.dumps({"error": "未绑定 tab，请指定 tab_id"})
            tab = infra["tab_manager"]._tabs.get(pinned_id) if infra["tab_manager"] else None
            if not tab:
                return json.dumps({"error": f"绑定的 tab 已关闭 (tab_id={pinned_id})"})

        try:
            # 清理残留 overlay（静默，失败不影响后续执行）
            try:
                await cdp.send(
                    "Runtime.evaluate",
                    {"expression": "window.__bh_cleanup_all && __bh_cleanup_all()"},
                    session_id=tab.session_id,
                    timeout=3,
                )
            except Exception:
                pass

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
        except asyncio.TimeoutError:
            # 超时后强制终止 Chrome 中正在执行的 JS，释放主线程
            logger.warning("[eval_js] Timeout after 15s, terminating execution")
            try:
                if cdp and cdp._connected:
                    await cdp.send(
                        "Runtime.terminateExecution",
                        session_id=tab.session_id,
                        timeout=3,
                    )
            except Exception as term_err:
                logger.debug(f"[eval_js] terminateExecution failed: {term_err}")
            return json.dumps({"error": "JS execution timeout (15s), terminated"})
        except Exception as e:
            logger.warning(f"[eval_js] CDP error: {e}")
            return json.dumps({"error": str(e)})
