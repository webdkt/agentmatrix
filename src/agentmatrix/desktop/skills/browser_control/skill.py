"""
Browser Control Skill — 浏览器控制操作（精简版）。

与 browser_automation 共享同一套 Chrome/CDP 基础设施（同一个 Chrome 实例），
仅提供浏览器控制和 CDP 调试相关的 action，不包含 DOM 探索、站点知识、工作模式切换等自动化能力。
所有实现方法在 ._shared.BrowserCommonMixin 中，此类只声明 @register_action 装饰器
并代理调用。
"""

import json

from agentmatrix.core.action import register_action

from agentmatrix.desktop.skills.browser_automation._shared import BrowserCommonMixin


class Browser_controlSkillMixin(BrowserCommonMixin):
    """
    Browser Control Skill — 浏览器控制操作（精简版）

    与 browser_automation 共享同一个 Chrome 实例，
    仅提供控制、CDP 调试相关的 action。
    """

    _skill_description = """浏览器控制操作
    通过 CDP (Chrome DevTools Protocol) 控制浏览器，可以打开网页、管理标签页、执行 JavaScript 和 CDP 指令。
    不包含 DOM 探索、站点知识、自动化脚本执行等高级功能。
    """

    # ── Action 薄壳：@register_action + 调用 mixin 实现 ──────────

    @register_action(
        short_desc="open_url(url)",
        description="在浏览器中打开指定 URL。",
        param_infos={"url": "要打开的 URL（如 https://github.com）"},
    )
    async def open_url(self, url: str) -> str:
        return await super().open_url(url)

    @register_action(
        short_desc="tab_operation(op, target_id?) 统一 tab 管理。op='list' 列出 tabs, op='close' 关闭 tab, op='switch_to' 切换 tab",
        description="统一 tab 管理。op='list' 列出所有 tab；op='close' 关闭指定 tab；op='switch_to' 切换到指定 tab。",
        param_infos={
            "op": "操作类型：'list' / 'close' / 'switch_to'",
            "target_id": "tab 的 target_id（list 不需要，close/switch_to 必填）",
        },
    )
    async def tab_operation(self, op: str, target_id: str = None) -> str:
        return await super().tab_operation(op, target_id)

    @register_action(
        short_desc="(code, tab_id?) 在浏览器中执行 JavaScript 代码（仅探索和调试用途）",
        description="向当前（或指定）tab 发送 JavaScript 代码并返回执行结果。"
                    "支持返回 Promise / 使用 await，会等待 resolve 后返回最终值。"
                    "仅用于探索和调试，不得用于正式自动化执行。",
        param_infos={
            "code": "要执行的 JavaScript 代码字符串（支持 async/await）",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def try_js_code(self, code: str, tab_id: str = None) -> str:
        return await super().try_js_code(code, tab_id)

    @register_action(
        short_desc="(method, params?, tab_id?) 发送 CDP 协议指令（仅探索和调试用途）",
        description="向浏览器 tab 发送原始 CDP (Chrome DevTools Protocol) 指令并返回结果。"
                    "可用于执行 Input.dispatchMouseEvent、Input.dispatchKeyEvent、"
                    "Page.captureScreenshot 等任意 CDP 方法。仅用于探索和调试，不得用于正式自动化执行。",
        param_infos={
            "method": "CDP 方法名，如 Input.dispatchMouseEvent",
            "params": "可选，CDP 参数 dict",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def try_cdp_command(self, method: str, params=None, tab_id: str = None) -> str:
        return await super().try_cdp_command(method, params, tab_id)