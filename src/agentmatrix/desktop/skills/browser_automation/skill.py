"""
Browser Automation Skill — 浏览器自动化，支持前端 Interface 注入和双向事件。

所有实现方法在 ._shared.BrowserCommonMixin 中，此类只声明 @register_action 装饰器
并代理调用。新增 action 时：先在 BrowserCommonMixin 中加实现方法（无装饰器），
再在此加 @register_action 薄壳。

Agent Actions:
- open_url(url)               → 打开 URL（自动注入通信桥接）
- tab_operation(op, target_id?)→ 统一 tab 管理（list / close / switch_to）
- find_selector(...)           → 启动临时 Agent 探索 DOM 找 selector
- find_unique_selector_by_xy(...) → 同上，基于坐标
- confirm_element(selector)   → 高亮元素弹确认框
- try_js_code(code)            → 执行 JS 代码
- try_cdp_command(method, params?) → 发送 CDP 指令
- get_cdp_info()               → 获取 CDP 连接信息和示例代码
- set_work_mode(mode)          → 切换 develop/execute 模式
- load_site_knowledge(...)     → 加载站点知识
"""

from agentmatrix.core.action import register_action

from ._shared import BrowserCommonMixin, infra
from .interfaces import load_interface, list_interfaces


class Browser_automationSkillMixin(BrowserCommonMixin):
    """
    Browser Automation Skill — 浏览器自动化

    多 Agent 支持：
    - 所有 agent 共享一个 Chrome 实例
    - tab 按 agent_name 隔离
    - 浏览器事件按 tab 归属路由到正确的 agent signal_queue
    """

    _skill_description = """浏览器自动化开发：浏览器自动化流程和自动化脚本的生成、管理和运行
    `~/site_knowledge`目录是网站自动化代码仓库。
    ### ~/site_knowledge 的结构
    - 根目录（~/site_knowledge)
        - index.txt: 
            - 网站列表，每行格式 `url_prefix:说明:子目录名` （整行是一个唯一的site key）
            - url_prefix 可能重复，但说明和子目录名必须不同（因为有些单体站点可能包含多个不同的子系统，结构和元素差异较大）
            - 使用 load_site_knowledge(site_key) 来加载对应站点的概览和流程列表
        - 子目录（site 目录）
            - 每个site_key对应一个子目录(site 目录），存放该站点的所有自动化知识和脚本，site目录内有：
            - readme.md: 网站说明，必须的结构如下
                ```markdown
                # 站点说明
                {{简短说明该站点的用途}}
                ## 🚀 快速开始 (Quick Start)
                **首次使用？按以下顺序操作：**
                1. **确定你的业务场景**：
                - {{场景A}} → 使用 `{{流程A目录名}}` 流程
                - {{场景B}} → 使用 `{{流程B目录名}}` 流程
                2. **阅读流程文档**：
                - 前往对应的流程目录（如 `{{流程A目录名}}/`）
                - **首先阅读该目录下的 `readme.md`** - 了解流程概述、业务规则和步骤索引
                - **然后按 `step-00-*.md` → `step-01-*.md` → ... 的顺序执行**

                3. **重要提醒**：
                - {{列出该站点需要特别注意的事项，如前置条件、特殊阶段等}}
                - 请严格按照流程文档中的步骤顺序执行，不要跳过任何步骤
                ```
            - 流程子目录（process 目录），针对特定工作流程的子目录，内含该流程说明和针对该流程的自动化脚本，目录的名称即流程的名称
            - 使用 load_site_knowledge(site_key, process_dir_name) 来加载对应流程的自动化步骤和脚本列表
            - 每个流程子目录的结构
                - readme.md: 业务流程和规则的简要说明
                - step-{{step_index}}-{{step_name}}.md: 每个阶段每个步骤的说明文档，包含该步骤的具体自动化步骤。
                - scripts/ 目录：存放针对该流程的自动化脚本。自动化脚本有3类，.json (cdp命令）.js (注入浏览器执行的js脚本）,.py (python自动化脚本）
        
    ### site_knowledge 文件规范
    #### Python自动化脚本
    Python 脚本通过 Unix Domain Socket 与 Chrome 通信，协议为 null-terminated JSON（JSON + b'\\0'）。
    环境变量：CDP_SOCKET_PATH（socket路径）、CDP_CURRENT_TAB_ID（当前tab的target_id）。
    脚本示例：

    ```python
    import socket, json, os

    SOCK = os.environ.get("CDP_SOCKET_PATH", "/tmp/agentmatrix_chrome_cdp.sock")
    TAB_ID = os.environ.get("CDP_CURRENT_TAB_ID", "")

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK)

    _msg_id = 0
    def cdp(method, params=None, session_id=None):
        '''发送 CDP 命令并等待响应'''
        global _msg_id; _msg_id += 1
        msg = {"id": _msg_id, "method": method, "params": params or {}}
        if session_id: msg["sessionId"] = session_id
        s.sendall(json.dumps(msg).encode() + b'\\x00')
        buf = b''
        while b'\\x00' not in buf:
            chunk = s.recv(4096)
            if not chunk: raise ConnectionError("socket closed")
            buf += chunk
        resp = json.loads(buf.split(b'\\x00', 1)[0])
        if "error" in resp: raise RuntimeError(resp["error"])
        return resp.get("result", {})

    # 操作 tab 需先 attach
    r = cdp("Target.attachToTarget", {"targetId": TAB_ID, "flatten": True})
    sid = r.get("sessionId", "")
    cdp("Page.enable", session_id=sid)

    # 导航
    cdp("Page.navigate", {"url": "https://example.com"}, session_id=sid)

    # 执行 JS
    r = cdp("Runtime.evaluate", {"expression": "document.title"}, session_id=sid)
    print(r.get("result", {}).get("value"))

    s.close()
    ```
    注意事项：
    - 一个 socket 连接同一时间只能有一个未完成的请求（发一个，等响应，再发下一个），多脚本需串行执行
    - 操作 tab 必须先 Target.attachToTarget 拿到 sessionId，每次脚本运行都要重新 attach，不可复用旧的 sessionId
    - 环境变量 CDP_SOCKET_PATH 和 CDP_CURRENT_TAB_ID 已自动注入，直接从 os.environ 读取，不要硬编码
    - **如果脚本运行时发现环境变量为空或不存在**：说明 CDP 连接尚未就绪或 shell 会话已重启。应先调用 get_cdp_info() 获取 socket_path 和 current_tab.target_id，然后通过 bash 执行 `export CDP_SOCKET_PATH="..." && export CDP_CURRENT_TAB_ID="..."` 设置环境变量，再重新运行脚本。不要等待、不要重试旧的空值。
    - Chrome 重启后 socket 会重建，脚本重连即可
    - **刷新页面**：不要用 `location.reload()`（会触发 beforeunload 弹窗导致 CDP session 阻塞），应使用 CDP 命令 `Page.navigate` 到当前 URL，或 `Page.reload`（绕过 beforeunload）
    
    #### Javascript: No Console Output
    eval_js 不会返回console的输出。只会返回脚本 return的结果。
    #### 正式脚本 vs 探索脚本
    ~/site_knowledge 下只能存放正式的脚本。探索脚本放在 ~/current_task/tmp 下。
    #### 流程文档 step-{{index}}-{{step_name}}.md
    - 流程文档本质上是一个执行手册，是一份"代码"
    - 流程文档的基本结构
        - Part 1（Code): 带有编号的执行步骤。每个步骤要么是（a）自动化脚本，（b）手动执行的具体js or cdp命令,或者是(c) Agent 进行判断的、分支或者循环的说明。 Part 1 的目的是让任何Agent可以按照步骤完成该流程，无需懂的业务。
        - Part 2 (Doc): 对业务逻辑的补充说明，作为参考供debug, 后续开发和版本review用。
        - Part 3 (可选）：异常处理说明。执行过程中可能出现的、无法被Part 1吸收覆盖的异常情况的说明和处理建议。
    ### 其他开发规范
    - 元素必须使用稳定的、给予语义的定位器
    - 不进行全局撒网式的探索
    - 必须包含判断所在页面、当前状态的明确规则
    - 操作元素前必须等待其可交互
    - 流程知识更新后，执行load_site_knowledge，重新加载知识
  """

    # ── Action 薄壳：@register_action + 调用 mixin 实现 ──────────

    @register_action(
        short_desc="open_url(url)",
        description="在新的浏览器 tab 中打开指定 URL。"
                    "自动注入通信桥接 JS，使前端能与后端通信。",
        param_infos={"url": "要打开的 URL（如 https://github.com）"},
    )
    async def open_url(self, url: str) -> str:
        return await super().open_url(url)

    @register_action(
        short_desc="tab_operation(op, target_id?) 统一 tab 管理。op='list' 列出 tabs, op='close' 关闭 tab, op='switch_to' 切换 tab",
        description="统一 tab 管理。op='list' 列出当前 agent 的所有 tab（含 tab ID、URL、标题、是否当前 tab）；"
                    "op='close' 关闭指定 tab（关闭后自动切换到剩余 tab）；"
                    "op='switch_to' 切换到指定 tab（激活并注入 bridge）.",
        param_infos={
            "op": "操作类型：'list' / 'close' / 'switch_to'",
            "target_id": "tab 的 target_id（list 不需要，close/switch_to 必填）",
        },
    )
    async def tab_operation(self, op: str, target_id: str = None) -> str:
        return await super().tab_operation(op, target_id)

    @register_action(
        short_desc="find_selector(instruction_text, tab_id?) 启动一个临时Agent 在浏览器中探索 DOM，找到目标元素的最佳稳定selector。instruction_text关于要找什么、以及有什么已知信息后者scope的详细描述",
        description="find_selector(instruction_text, tab_id?) 启动一个临时Agent 在浏览器中探索 DOM，找到目标元素的最佳稳定selector。instruction_text关于要找什么、以及有什么已知信息后者scope的详细描述",
        param_infos={
            "additional_info": "用户对该元素的描述文字（从 indicator_result 信号获取）",
            "tab_id": "可选，目标 tab 的 tab_id，不传则使用当前 tab",
        },
    )
    async def find_selector(self, instruction_text: str, tab_id: str = None) -> str:
        return await super().find_selector(instruction_text, tab_id)

    @register_action(
        short_desc="find_unique_selector_by_xy(additional_info, tab_id?, x, y) 启动一个临时Agent 在浏览器中探索 DOM，找到用户指向元素的稳定的、唯一的selector。additional_info是额外、帮助Agent定位元素的信息",
        description="find_unique_selector_by_xy(additional_info, tab_id, x, y) 启动一个临时Agent 在浏览器中探索 DOM，找到用户指向元素的稳定的、唯一的selector。additional_info是额外、帮助Agent定位元素的信息",
        param_infos={
            "additional_info": "用户对该元素的描述文字,以及任何有助于定位元素的额外信息",
            "tab_id": "可选，目标 tab 的 tab_id，不传则使用当前 tab",
            "x": "用户指向的 x 坐标",
            "y": "用户指向的 y 坐标",
        },
    )
    async def find_unique_selector_by_xy(self, additional_info: str, tab_id: str = None, x: int = 0, y: int = 0) -> str:
        return await super().find_unique_selector_by_xy(additional_info, tab_id, x, y)

    @register_action(
        short_desc="confirm_element(selector, tab_id?) 在浏览器中高亮指定 selector 匹配的元素，并弹出确认对话框让用户确认。",
        description="在浏览器中高亮指定 selector 匹配的元素，并弹出确认对话框让用户确认。"
                    "立即返回，用户确认结果通过 element_confirmed 信号异步返回。",
        param_infos={
            "selector": "要确认的 CSS selector 或 XPath（XPath 以 'xpath:' 前缀）",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def confirm_element(self, selector: str, tab_id: str = None) -> str:
        return await super().confirm_element(selector, tab_id)

    @register_action(
        short_desc="(code, tab_id?)探索、试验js代码，不得用于测试，不得用于正式自动化执行，只用于探索和debug，默认当前tab",
        description="向当前（或指定）tab 发送 JavaScript 代码并返回执行结果。"
                    "支持返回 Promise / 使用 await，会等待 resolve 后返回最终值。",
        param_infos={
            "code": "要执行的 JavaScript 代码字符串（支持 async/await）",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def try_js_code(self, code: str, tab_id: str = None) -> str:
        return await super().try_js_code(code, tab_id)

    @register_action(
        short_desc="(method, params?, tab_id?) 试验CDP协议指令。params 必须是 dict 对象，不能用于正式执行和测试，只能用于探索试验和debug，不得用于正式自动化执行",
        description="向浏览器 tab 发送原始 CDP (Chrome DevTools Protocol) 指令并返回结果。"
                    "可用于执行 Input.dispatchMouseEvent（鼠标事件）、Input.dispatchKeyEvent（键盘事件）、"
                    "Page.captureScreenshot（截图）等任意 CDP 方法。\n\n"
                    "params 必须是 dict 对象，示例：\n"
                    '  cdp_command("Input.dispatchMouseEvent", {"type": "mousePressed", "x": 100, "y": 200, "button": "left", "clickCount": 1})\n'
                    '  cdp_command("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": 100, "y": 200, "button": "left", "clickCount": 1})\n'
                    '  cdp_command("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "text": "\\r"})\n\n'
                    "完整文档参考 https://chromedevtools.github.io/devtools-protocol/",
        param_infos={
            "method": "CDP 方法名，如 Input.dispatchMouseEvent",
            "params": "可选，CDP 参数 dict，如 {\"type\":\"mousePressed\",\"x\":100,\"y\":200}",
            "tab_id": "可选，目标 tab 的 target_id，不传则使用当前 tab",
        },
    )
    async def try_cdp_command(self, method: str, params=None, tab_id: str = None) -> str:
        return await super().try_cdp_command(method, params, tab_id)

    @register_action(
        short_desc="get_cdp_info() → 获取 CDP 连接信息和示例代码",
        description="获取当前 CDP 浏览器连接信息。"
                    "返回示例代码（含完整的 cdp() 函数和 attach 流程）。"
                    "关键规则："
                    "1) Python 脚本通过环境变量 CDP_SOCKET_PATH 和 CDP_CURRENT_TAB_ID 连接浏览器，无需硬编码路径；"
                    "2) 操作 tab 前必须先调用 Target.attachToTarget(targetId=TAB_ID) 获取 sessionId，不可省略；"
                    "3) 每次脚本运行都要重新 attach，不要复用旧的 sessionId；"
                    "4) 一个 socket 连接同一时间只能串行执行（发一个请求，等响应，再发下一个）。",
    )
    async def get_cdp_info(self) -> str:
        return await super().get_cdp_info()

    @register_action(
        short_desc="(mode)切换工作模式。mode='develop' 进入开发构建模式，mode='execute' 进入自动化执行模式。必须根据当前情况切换到合适的模式。",
        description="切换工作模式。mode='develop' 进入开发构建模式，mode='execute' 进入自动化执行模式。"
                    "会重建 system prompt（使用 profile 中对应的模式 persona）.",
        param_infos={"mode": "工作模式：'develop' 或 'execute'"},
    )
    async def set_work_mode(self, mode: str) -> str:
        return await super().set_work_mode(mode)

    @register_action(
        short_desc="(site_key, process_dir_name?) 加载站点知识或具体自动化流程。返回的<site-knowledge>内容已进入上下文，无需额外操作。",
        description="加载指定站点的知识。只传 site_key 时加载站点 readme 和流程列表；"
                    "同时传 process_dir_name 时加载具体流程的 readme 和步骤列表。"
                    "返回 <site-knowledge> 包裹的内容，自动进入对话上下文。",
        param_infos={
            "site_key": "站点 site_key（格式 url_prefix:desc:dir_name）",
            "process_dir_name": "可选，自动化流程子目录名称，加载具体流程的详细知识",
        },
    )
    async def load_site_knowledge(self, site_key: str, process_dir_name: str = None) -> str:
        return await super().load_site_knowledge(site_key, process_dir_name)

    # ── Internal (not registered) ────────────────────────────

    async def deprecated_show_interface(self, name: str) -> str:
        """注入前端 interface（已废弃，保留兼容）。"""
        await self._ensure_browser()
        tab = self._get_current_tab()

        if not tab:
            return json.dumps({
                "status": "error",
                "error": "没有活动的 tab。请先使用 open_url() 打开页面。",
            }, ensure_ascii=False)

        js = load_interface(name)
        if not js:
            available = [i["name"] for i in list_interfaces()]
            return json.dumps({
                "status": "error",
                "error": f"Interface '{name}' 不存在",
                "available": available,
            }, ensure_ascii=False)

        if infra["event_listener"]:
            await infra["event_listener"].inject_js(tab.session_id, js)
        else:
            await infra["cdp_client"].send(
                "Runtime.evaluate",
                {"expression": js},
                session_id=tab.session_id,
            )

        return json.dumps({
            "status": "ok",
            "message": f"Interface '{name}' 已注入到当前页面",
            "target_id": tab.target_id,
        }, ensure_ascii=False)