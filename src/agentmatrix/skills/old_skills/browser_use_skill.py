"""
Browser-Use Skill - 基于 browser-use 的浏览器自动化技能

提供高级的浏览器自动化能力，使用 browser-use 库让 LLM 驱动浏览器操作。

配置要求:
- 需要在 llm_config.json 中配置 browser-use-llm（优先）或 deepseek-chat（回退）
- 推荐使用支持结构化输出的模型（如 OpenAI GPT-4o）

国产模型兼容性:
- 自动检测 GLM、Mimo、DeepSeek 等国产模型
- 针对这些模型启用兼容性模式：
  * dont_force_structured_output=True - 禁用强制结构化输出
  * remove_min_items_from_schema=True - 移除 JSON schema 中的 minItems
  * remove_defaults_from_schema=True - 移除 JSON schema 中的默认值
- 对于 Mimo 等需要 extra_body 传递 thinking 参数的模型，会自动使用包装器
"""

import asyncio
import os
from typing import Optional, Dict, Any
from pathlib import Path
from ..core.action import register_action
from ..skills.parser_utils import simple_section_parser
from ..core.exceptions import LLMServiceUnavailableError
from browser_use import Agent


class BrowserUseSkillMixin:
    """
    基于 browser-use 的浏览器自动化技能

    特点:
    - 使用 LLM 驱动浏览器决策
    - 支持会话持久化（Chrome profile）
    - 自动处理导航、点击、输入等操作
    - **自动兼容国产模型**（GLM、Mimo、DeepSeek 等）

    配置要求:
    - 在 llm_config.json 中配置 browser-use-llm（优先）
    - 如果没有配置，回退到 deepseek-chat

    国产模型兼容性:
    - 自动检测模型厂商（从 model_name 或 URL）
    - 启用 browser-use 的 JSON schema 兼容性参数
    - 针对 thinking 模型自动禁用 thinking 模式
    """

    # 国产模型配置
    # 这些模型对结构化输出和 JSON schema 支持有限，需要特殊处理
    CHINESE_LLM_CONFIG = {
        # Zhipu AI (智谱)
        "glm": {
            "dont_force_structured_output": True,
            "remove_min_items_from_schema": True,
            "remove_defaults_from_schema": True,
            "use_extra_body": False,  # GLM 使用 thinking 参数直接传递
        },
        # Xiaomi Mimo
        "mimo": {
            "dont_force_structured_output": True,
            "remove_min_items_from_schema": True,
            "remove_defaults_from_schema": True,
            "use_extra_body": True,  # Mimo 使用 extra_body 传递 thinking 参数
        },
        # DeepSeek (如果需要)
        "deepseek": {
            "dont_force_structured_output": True,
            "remove_min_items_from_schema": True,
            "remove_defaults_from_schema": True,
            "use_extra_body": False,
        },
    }

    # 厂商识别规则（从模型名称或 URL 识别）
    VENDOR_PATTERNS = {
        "glm": ["glm", "bigmodel", "zhipu"],
        "mimo": ["xiaomi", "mimo"],
        "deepseek": ["deepseek"],
    }

    def _get_llm_config_path(self) -> str:
        """
        获取 llm_config.json 的路径

        Returns:
            str: llm_config.json 的绝对路径

        路径规则：
        - workspace_root 指向 MyWorld/workspace
        - llm_config.json 在 MyWorld/agents/llm_config.json
        """
        if not (hasattr(self, "workspace_root") and self.workspace_root):
            raise ValueError("workspace_root 未设置，无法确定 llm_config.json 路径")

        # 从 workspace_root 推断：workspace 是 MyWorld 的子目录
        # llm_config.json 现在在 .matrix/configs/ 目录下
        workspace_root_path = Path(self.workspace_root)
        config_path = (
            workspace_root_path.parent / ".matrix" / "configs" / "llm_config.json"
        )

        if not config_path.exists():
            raise FileNotFoundError(f"llm_config.json 不存在: {config_path}")

        return str(config_path)

    def _create_llm_client_for_browser_use(self, config_name: str):
        """
        为 browser-use 创建 LLMClient

        Args:
            config_name: 配置名称（如 "browser-use-llm" 或 "deepseek-chat"）

        Returns:
            LLMClient 实例
        """
        from ..core.loader import AgentLoader

        llm_config_path = self._get_llm_config_path()
        profile_path = str(Path(llm_config_path).parent)

        loader = AgentLoader(profile_path=profile_path, llm_config_path=llm_config_path)
        return loader._create_llm_client(config_name)

    def _create_browser_use_llm_from_client(self, llm_client):
        """
        从 LLMClient 创建 browser-use 的 LLM

        Args:
            llm_client: AgentMatrix 的 LLMClient 实例

        Returns:
            browser-use 的 LLM 实例（使用 ChatOpenAI，支持国产模型兼容性参数）
        """
        try:
            from browser_use.llm.openai.chat import ChatOpenAI as BUChatOpenAI
        except ImportError:
            raise ImportError(
                "使用 BrowserUseSkill 需要安装 browser-use: pip install browser-use"
            )

        # 从 LLMClient 提取配置
        url = getattr(llm_client, "url", None)
        api_key = getattr(llm_client, "api_key", None)
        model_name = getattr(llm_client, "model_name", "")

        self.logger.info(f"BrowserUseSkill 使用模型: {model_name}")

        # browser-use 的 ChatOpenAI 会自动添加 /chat/completions
        # 如果配置的 URL 已经包含 /chat/completions，需要去掉
        if url and url.endswith("/chat/completions"):
            url = url[: -len("/chat/completions")]

        # 检测厂商（从模型名称或 URL）
        model_lower = model_name.lower()
        url_lower = url.lower() if url else ""

        vendor = None
        for v, patterns in self.VENDOR_PATTERNS.items():
            if any(p in model_lower for p in patterns) or any(
                p in url_lower for p in patterns
            ):
                vendor = v
                break

        # 准备 ChatOpenAI 的基础参数
        llm_kwargs = {
            "model": model_name,
            "api_key": api_key,
            "base_url": url,
            "temperature": 0.1,
            "max_completion_tokens": 4096,
        }

        # 如果是国产模型，添加兼容性参数
        if vendor and vendor in self.CHINESE_LLM_CONFIG:
            config = self.CHINESE_LLM_CONFIG[vendor]
            llm_kwargs.update(
                {
                    "dont_force_structured_output": config[
                        "dont_force_structured_output"
                    ],
                    "remove_min_items_from_schema": config[
                        "remove_min_items_from_schema"
                    ],
                    "remove_defaults_from_schema": config[
                        "remove_defaults_from_schema"
                    ],
                }
            )

            self.logger.info(
                f"检测到国产模型 ({vendor})，启用兼容性模式："
                f"dont_force_structured_output={config['dont_force_structured_output']}, "
                f"remove_min_items_from_schema={config['remove_min_items_from_schema']}, "
                f"remove_defaults_from_schema={config['remove_defaults_from_schema']}"
            )

            # 如果需要使用 extra_body 传递 thinking 参数（Mimo）
            if config.get("use_extra_body", False):
                self.logger.info(f"使用 ChatOpenAI with extra_body for {vendor}")
                llm = self._create_llm_with_extra_body(BUChatOpenAI, llm_kwargs, vendor)
            else:
                # 直接使用 ChatOpenAI
                llm = BUChatOpenAI(**llm_kwargs)
        else:
            # 非国产模型，使用默认配置
            self.logger.info(f"使用标准 ChatOpenAI 配置")
            llm = BUChatOpenAI(**llm_kwargs)

        return llm

    def _create_llm_with_extra_body(self, llm_class, llm_kwargs, vendor):
        """
        创建支持 extra_body 参数的 LLM 实例

        用于像 Mimo 这样需要通过 extra_body 传递 thinking 参数的模型

        Args:
            llm_class: ChatOpenAI 类
            llm_kwargs: ChatOpenAI 的参数
            vendor: 厂商名称（用于日志）

        Returns:
            包装后的 LLM 实例
        """
        from typing import Any, TypeVar
        from browser_use.llm.messages import BaseMessage
        from functools import wraps

        T = TypeVar("T")

        class LLMWithExtraBodyWrapper:
            """Wrapper for models that need extra_body parameter"""

            def __init__(self, base_llm):
                self._base_llm = base_llm

            def __getattr__(self, name):
                """将所有其他属性访问委托给 base_llm"""
                return getattr(self._base_llm, name)

            async def ainvoke(
                self,
                messages: list[BaseMessage],
                output_format: type[T] | None = None,
                **kwargs: Any,
            ):
                """
                调用模型，自动添加 extra_body 参数

                使用 monkey patching 技术临时修改 openai client 的 completions.create 方法
                """
                original_create = self._base_llm.get_client().chat.completions.create

                @wraps(original_create)
                async def patched_create(*args, **create_kwargs):
                    # 添加 extra_body 参数
                    create_kwargs = create_kwargs.copy()
                    create_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
                    return await original_create(*args, **create_kwargs)

                # 临时替换 create 方法
                self._base_llm.get_client().chat.completions.create = patched_create

                try:
                    # 调用原始的 ainvoke
                    result = await self._base_llm.ainvoke(
                        messages, output_format, **kwargs
                    )
                    return result
                finally:
                    # 恢复原始 create 方法
                    self._base_llm.get_client().chat.completions.create = (
                        original_create
                    )

        # 创建基础 LLM 实例
        base_llm = llm_class(**llm_kwargs)

        # 返回包装后的实例
        return LLMWithExtraBodyWrapper(base_llm)

    def _get_browser_use_llm(self):
        """
        获取或创建 browser-use 所需的 LLM

        优先级：
        1. browser-use-llm（llm_config.json 中的专用配置）
        2. deepseek-chat（回退配置）

        Returns:
            browser-use 的 ChatOpenAI 实例
        """
        # 惰性初始化：检查属性是否存在
        if not hasattr(self, "_browser_use_llm"):
            self._browser_use_llm = None

        # 如果已经创建，直接返回
        if self._browser_use_llm is not None:
            return self._browser_use_llm

        # 确定配置名称（优先 browser-use-llm，回退到 deepseek-chat）
        config_name = "browser-use-llm"

        try:
            # 尝试创建 LLMClient
            llm_client = self._create_llm_client_for_browser_use(config_name)
            self.logger.info(f"BrowserUseSkill 使用配置: {config_name}")
        except Exception as e:
            # 回退到 deepseek-chat
            self.logger.warning(
                f"无法加载配置 '{config_name}': {e}，回退到 'deepseek-chat'"
            )
            config_name = "deepseek-chat"
            try:
                llm_client = self._create_llm_client_for_browser_use(config_name)
                self.logger.info(f"BrowserUseSkill 使用回退配置: {config_name}")
            except Exception as e2:
                raise ValueError(
                    f"无法加载 browser-use LLM 配置。"
                    f"请确保在 llm_config.json 中配置了 'browser-use-llm' 或 'deepseek-chat'。"
                    f"错误: {e2}"
                )

        # 从 LLMClient 创建 browser-use 的 LLM
        self._browser_use_llm = self._create_browser_use_llm_from_client(llm_client)

        return self._browser_use_llm

    async def _check_browser_llm_available(self) -> bool:
        """
        检查 browser-use-llm 服务是否可用

        Returns:
            bool: 服务是否可用
        """
        try:
            # 创建一个临时的 LLMClient 进行测试
            config_name = "browser-use-llm"

            # 尝试创建 browser-use-llm 的 client
            try:
                llm_client = self._create_llm_client_for_browser_use(config_name)
            except Exception:
                # 如果 browser-use-llm 不存在，尝试 deepseek-chat
                config_name = "deepseek-chat"
                llm_client = self._create_llm_client_for_browser_use(config_name)

            # 发送一个最小的测试请求
            test_messages = [{"role": "user", "content": "hi"}]

            # 设置短超时（10秒）
            response = await asyncio.wait_for(
                llm_client.think(messages=test_messages), timeout=10.0
            )

            # 检查响应
            if response and "reply" in response:
                self.logger.debug(f"✓ browser-use-llm ({config_name}) is available")
                return True
            else:
                self.logger.warning(
                    f"✗ browser-use-llm ({config_name}) returned invalid response"
                )
                return False

        except asyncio.TimeoutError:
            self.logger.warning(f"✗ browser-use-llm ({config_name}) timeout")
            return False
        except LLMServiceUnavailableError:
            self.logger.warning(
                f"✗ browser-use-llm ({config_name}) service unavailable"
            )
            return False
        except Exception as e:
            self.logger.warning(f"✗ browser-use-llm check failed: {str(e)}")
            return False

    async def _wait_for_browser_llm_recovery(self):
        """等待 browser-use-llm 服务恢复（轮询方式）"""
        check_interval = 5  # 每 5 秒检查一次
        waited_seconds = 0

        self.logger.info("⏳ Waiting for browser-use-llm recovery...")

        while True:
            await asyncio.sleep(check_interval)
            waited_seconds += check_interval

            # 检查是否恢复
            if await self._check_browser_llm_available():
                self.logger.info(
                    f"✅ browser-use-llm recovered after {waited_seconds}s"
                )
                break

            # 每 30 秒打印一次日志
            if waited_seconds % 30 == 0:
                self.logger.warning(
                    f"⏳ Still waiting for browser-use-llm... ({waited_seconds}s elapsed)"
                )

    async def _get_browser(self, headless: bool = False):
        """
        获取或创建 browser-use 的 Browser 实例

        每个 Agent 有自己的浏览器实例，使用固定的 profile 目录持久化浏览器状态。
        浏览器在 Agent 生命周期内保持打开，多次调用复用同一个实例。

        Args:
            headless: 是否使用无头模式（默认 False，显示浏览器）
        """
        # 惰性初始化：检查属性是否存在
        if not hasattr(self, "_browser_use_browser"):
            self._browser_use_browser = None

        # 检查现有浏览器实例是否可用
        if self._browser_use_browser is not None:
            # 简化逻辑：只要 browser 对象存在就复用
            # 如果浏览器真的死了，使用时会抛出异常，我们可以在调用时捕获
            self.logger.debug("BrowserUseSkill 复用现有浏览器实例")
            return self._browser_use_browser

        # 创建新浏览器实例
        try:
            from browser_use import Browser
        except ImportError:
            raise ImportError(
                "使用 BrowserUseSkill 需要安装 browser-use: pip install browser-use"
            )

        try:
            # 准备浏览器参数
            browser_kwargs = {
                "headless": headless,
                "keep_alive": True,  # 保持浏览器打开，不要在 Agent 关闭时自动关闭
            }

            # 使用固定的 profile 目录
            # 每个 Agent 有自己独立的浏览器 profile，持久化 cookies、历史等
            # 注意：必须使用根 Agent 的 name 和 workspace_root，而不是 MicroAgent 的
            import os
            from ..core.working_context import WorkingContext

            # 获取根 Agent 的 name 和 workspace_root（即使在 MicroAgent 中调用也能正确获取）
            if hasattr(self, "root_agent"):
                agent_name = self.root_agent.name
                workspace_root = self.root_agent.workspace_root
            else:
                # 如果是 BaseAgent 直接调用
                agent_name = self.name
                workspace_root = self.workspace_root

            user_data_dir = os.path.join(
                workspace_root, ".matrix", "browser_profile", agent_name
            )
            os.makedirs(user_data_dir, exist_ok=True)  # 确保 profile 目录存在

            browser_kwargs["user_data_dir"] = user_data_dir
            self.logger.info(f"BrowserUseSkill 使用 Chrome profile: {user_data_dir}")

            # 设置下载路径：使用 working_context 下的 download 目录
            working_context = self.working_context
            download_path = os.path.join(working_context.current_dir, "download")
            os.makedirs(download_path, exist_ok=True)
            self.logger.info(f"BrowserUseSkill 下载目录: {download_path}")

            browser_kwargs["downloads_path"] = download_path

            # 设置窗口大小（仅在非 headless 模式下）
            if not headless:
                # 窗口大小：宽度 2/3，高度 90%
                # 基于常见笔记本分辨率 1920x1080 或 1366x768
                # 使用保守值 1280x720，适合大多数屏幕
                browser_kwargs["window_size"] = {"width": 1280, "height": 720}
                self.logger.info("BrowserUseSkill 窗口大小: 1280x720")
            browser_kwargs["executable_path"] = (
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            )

            self._browser_use_browser = Browser(**browser_kwargs)
            await self._browser_use_browser.start()

            if headless:
                self.logger.info("BrowserUseSkill 浏览器已启动（无头模式）")
            else:
                self.logger.info("BrowserUseSkill 浏览器已启动（可视化模式）")
        except Exception as e:
            self.logger.error(f"BrowserUseSkill 启动浏览器失败: {e}")
            raise

        return self._browser_use_browser

    async def _close_browser(self):
        """
        关闭 browser-use 浏览器实例

        安全地关闭浏览器，即使出错也会清理引用
        """
        if self._browser_use_browser is not None:
            try:
                await self._browser_use_browser.close()
                self.logger.info("BrowserUseSkill 浏览器已关闭")
            except Exception as e:
                self.logger.warning(f"BrowserUseSkill 关闭浏览器时出错: {e}")
            finally:
                # 无论关闭是否成功，都清理引用
                self._browser_use_browser = None

    async def _is_browser_connected(self) -> bool:
        """
        检查浏览器连接是否还活着

        使用 CDP 连接检查，而不仅仅是检查对象是否存在

        Returns:
            bool: True 表示连接正常，False 表示连接断开
        """
        if self._browser_use_browser is None:
            return False

        try:
            # 使用 get_browser_state_summary 检查连接（3秒超时）
            state = await asyncio.wait_for(
                self._browser_use_browser.get_browser_state_summary(), timeout=3.0
            )
            return state is not None
        except (asyncio.TimeoutError, Exception) as e:
            self.logger.warning(f"浏览器连接检查失败：{e}")
            return False

    async def _cleanup_browser_and_agent(self):
        """
        清理 Agent 和 Browser

        同时清理 browser-use Agent 和 Browser 实例
        """
        # 清理 Agent 引用（Agent 没有 close 方法）
        if hasattr(self, "_browser_use_agent"):
            self._browser_use_agent = None

        # 清理 headless 模式记录
        if hasattr(self, "_browser_headless_mode"):
            self._browser_headless_mode = False

        # 关闭 Browser
        await self._close_browser()
        self._browser_use_browser = None

    async def _create_new_agent(self, task: str, headless: bool):
        """
        创建新的 browser-use Agent 实例

        Args:
            task: 任务描述
            headless: 是否无头模式

        Returns:
            Agent: 新创建的 Agent 实例
        """
        # 添加重试机制处理 browser-use-llm 服务异常
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                llm = self._get_browser_use_llm()
                break  # 成功获取 LLM，退出循环
            except LLMServiceUnavailableError as e:
                retry_count += 1
                self.logger.warning(
                    f"⚠️  browser-use-llm 服务错误 (创建 Agent，尝试 {retry_count}/{max_retries}): {str(e)}"
                )

                if retry_count >= max_retries:
                    raise ValueError(
                        f"browser-use-llm 服务不可用，无法创建 Agent。已重试 {max_retries} 次。"
                    )

                # 等待服务恢复
                await asyncio.sleep(3)
                if await self._check_browser_llm_available():
                    self.logger.info("✅ browser-use-llm 已恢复，继续创建 Agent...")
                    continue

                self.logger.warning("🔄 等待 browser-use-llm 恢复...")
                await self._wait_for_browser_llm_recovery()
                self.logger.info("✅ browser-use-llm 已恢复，继续创建 Agent...")
                continue

        browser = await self._get_browser(headless=headless)

        # 创建 Agent，使用默认参数
        agent = Agent(
            task=task, llm=llm, browser=browser, use_vision=False, use_judge=False
        )

        # 记录 headless 状态
        self._browser_headless_mode = headless

        # 保存 Agent 引用以便复用
        self._browser_use_agent = agent

        self.logger.info(f"✅ 已创建新的 browser-use Agent（headless={headless}）")
        return agent

    async def _get_or_create_agent(self, task: str, headless: bool = False):
        """
        获取或创建 Agent 实例

        实现一个 AgentMatrix Agent 对应一个 browser-use Agent 的设计：
        - 首次调用：创建新 Agent
        - 后续调用：使用 add_new_task() 复用
        - headless 改变：重新创建 Agent
        - 连接断开：重新创建 Agent 和 Browser

        Args:
            task: 任务描述
            headless: 是否无头模式（只在首次创建时生效）

        Returns:
            Agent: browser-use Agent 实例
        """
        # 惰性初始化：检查属性是否存在
        if not hasattr(self, "_browser_use_agent"):
            self._browser_use_agent = None
        if not hasattr(self, "_browser_headless_mode"):
            self._browser_headless_mode = False

        # 首次创建
        if self._browser_use_agent is None:
            self.logger.info("首次创建 browser-use Agent")
            return await self._create_new_agent(task, headless)

        # headless 模式改变，需要重新创建
        if headless != self._browser_headless_mode:
            self.logger.info(
                f"headless 模式改变：{self._browser_headless_mode} -> {headless}，"
                f"重新创建 Agent 和 Browser"
            )
            await self._cleanup_browser_and_agent()
            return await self._create_new_agent(task, headless)

        # 检查浏览器连接是否还活着
        if not await self._is_browser_connected():
            self.logger.warning("浏览器连接断开，重新创建 Agent 和 Browser")
            await self._cleanup_browser_and_agent()
            return await self._create_new_agent(task, headless)

        # 连接正常，复用现有 Agent，使用 add_new_task 更新任务
        self.logger.info(f"✅ 复用现有 Agent，更新任务：{task[:50]}...")
        self._browser_use_agent.add_new_task(task)
        return self._browser_use_agent

    @register_action(
        short_desc="(task) #描述任务",
        description="""操作浏览器，简单描述对浏览器做什么，例如访问某个网站，查看当前页面内容，点击某个按钮等等针对浏览器的操作,可以一次一个动作，也可以一次描述多个动作。""",
        param_infos={
            "task": "对浏览器器的具体操作和要求，包括访问哪里，要获取什么数据等等，注意区别用户描述里哪些是具体针对浏览器的，哪些是做这些事情的最终目的。这个参数应该只包含针对浏览器的操作描述，不需要包含更高级最终意图的描述。",
            "headless": "是否无头模式（默认False，显示浏览器窗口）",
        },
    )
    async def use_browser(self, task: str, headless: bool = False) -> str:

        if hasattr(self, "root_agent"):
            llm = self.root_agent._get_browser_use_llm()
        else:
            # self 是 BaseAgent，直接调用
            llm = self._get_browser_use_llm()

        '''
        # ========== 使用 think_with_retry 优化任务描述 ==========
        self.logger.info("开始优化任务描述...")

        # 构建 task 优化 prompt
        task_optimization_prompt = f"""你是 browser-use task 优化专家。
        请检查用户打算做的事情是否符合 browser-use 最佳实践的 task 描述。如果不符合，请将其转换为符合 browser-use 最佳实践的 task 描述。

用户打算做的动作：{task}


browser-use Prompting Guide 原则：
1. Be Specific 
2. Name Actions Directly - 直接引用 action 名称（如 extract, click, scroll, input, navigate, search）
3. Provide Error Recovery - 提供失败时的备选方案（如 "If page times out, refresh and retry"）
4. Use Emphasis - 使用 NEVER/ALLAYS 等强调词约束关键行为
5. Google May Not Available - 如果涉及使用google，必须提示当Google不可用时要尽早及时换成Bing



Task 优化示例：
用户任务："搜索 Python 教程并提取前5个结果"
优化后：
"1. Navigate to {{url}}
2. Use search action to search for 'Python tutorials'
3. Wait for results to load
4. Use extract action to extract the first 5 result titles and links
5. Return the results in a structured format"

**重要**
避免不必要的优化，如果用户的任务很简洁、明确，且已经基本符合 browser-use 的最佳实践，就不需要修改。
优化的目的是让任务更适合 browser-use 执行，而不是为了优化而优化。
并且要求browser-use尽快返回结果，不要执行很久很长。

请生成优化后的 task 描述，放在 [OPTIMIZED_TASK] section 中，如果无需优化也在[OTIMIZED_TASK]下写下原始输入。

输出例子：
```
(可选)简短的想法
[OPTIMIZED_TASK]
优化后的任务描述（如果无需优化，直接重复用户输入）
```

"""

        try:
            # 使用 brain 的 think_with_retry 优化 task
            optimized_task = await self.brain.think_with_retry(
                task_optimization_prompt,
                simple_section_parser,
                section_header="[OPTIMIZED_TASK]",
                max_retries=2
            )

            self.logger.info(f"✓ 任务描述已优化")
            self.logger.debug(f"  原始任务：{task}")
            self.logger.debug(f"  优化任务：{optimized_task}")

            # 使用优化后的任务
            full_task = optimized_task

        except Exception as e:
            # 如果优化失败，回退到原始任务
            self.logger.warning(f"⚠ 任务描述优化失败: {e}，使用原始任务")
            full_task = task
        '''

        # 构建完整任务描述（包含 URL）
        full_task = (
            task + "\n用完的tab尽早关闭。不要做太多重复尝试，尽早返回结果"
        )  # f"{full_task}"

        self.logger.info(f"BrowserUseSkill 开始任务")

        self.logger.info(f"  任务: {task}")

        # ========== 添加重试循环处理 browser-use-llm 服务异常 ==========
        max_retries = 3  # 最多重试 3 次
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 获取或创建 Agent（会自动复用）
                if hasattr(self, "root_agent"):
                    agent = await self.root_agent._get_or_create_agent(
                        full_task, headless
                    )
                else:
                    agent = await self._get_or_create_agent(full_task, headless)

                # 执行任务（关键调用）
                history = await agent.run()

                # 成功执行，退出重试循环
                break

            except LLMServiceUnavailableError as e:
                # browser-use-llm 服务异常
                retry_count += 1
                self.logger.warning(
                    f"⚠️  browser-use-llm 服务错误 (尝试 {retry_count}/{max_retries}): {str(e)}"
                )

                # 如果已经重试多次，放弃
                if retry_count >= max_retries:
                    error_msg = (
                        f"browser-use-llm 服务不可用，已重试 {max_retries} 次仍失败"
                    )
                    self.logger.error(error_msg)
                    return f"任务执行失败: {error_msg}"

                # 等待一小段时间让服务稳定（3秒）
                await asyncio.sleep(3)

                # 检查服务状态
                if await self._check_browser_llm_available():
                    # 已恢复，重试
                    self.logger.info("✅ browser-use-llm 已恢复，重试...")
                    continue

                # 仍不可用，进入等待模式
                self.logger.warning("🔄 browser-use-llm 不可用，进入等待模式...")
                await self._wait_for_browser_llm_recovery()

                # 恢复后重试
                self.logger.info("✅ browser-use-llm 已恢复，重新执行任务")
                continue

            except Exception as e:
                # 其他异常，直接返回错误
                error_msg = f"未知错误: {type(e).__name__}: {e}"
                self.logger.error(error_msg, exc_info=True)
                return f"任务执行失败: {error_msg}"

        # ========== 执行成功后的处理 ==========
        # 获取最终结果
        final_result = history.final_result()

        # 清理结果中的 Simple judge note（经常不准确）
        import re

        final_result = re.sub(
            r"\[Simple judge:.*?\]", "", final_result, flags=re.DOTALL
        ).strip()

        # 获取当前浏览器停留的 URL
        try:
            current_url = history.urls()[-1] if history.urls() else None
        except Exception:
            current_url = None

        # 🆕 保存最后访问的 URL（供 WebSearcherV2 使用）
        if current_url:
            # 通过 root_agent 保存，确保 WebSearcherV2 能读取到
            if hasattr(self, "root_agent"):
                self.root_agent._last_browser_url = current_url
            else:
                self._last_browser_url = current_url
            self.logger.debug(f"浏览器当前 URL: {current_url}")

        # 构建返回结果（使用显示用的 URL）
        current_url_display = current_url if current_url else "未知"

        # 构建返回结果
        result_parts = []
        if final_result:
            result_parts.append(f"【最终结果】\n{final_result}")
        else:
            result_parts.append("任务已完成，未返回结果")

        result_parts.append(f"\n【当前页面】\n{current_url_display}")

        self.logger.info("BrowserUseSkill 任务完成")
        return "\n".join(result_parts)
