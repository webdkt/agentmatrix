"""
Browser-Use Skill - 基于 browser-use 的浏览器自动化技能

提供高级的浏览器自动化能力，使用 browser-use 库让 LLM 驱动浏览器操作。

配置要求:
- 需要在 llm_config.json 中配置 browser_use_llm（优先）或 deepseek-chat（回退）
- 推荐使用支持结构化输出的模型（如 OpenAI GPT-4o）

模型支持:
- **DeepSeek**: 使用 browser-use 官方 ChatDeepSeek 类（最佳支持）
- **国产模型（GLM、Mimo）**: 自动检测并启用兼容性模式
  * dont_force_structured_output=True - 禁用强制结构化输出
  * remove_min_items_from_schema=True - 移除 JSON schema 中的 minItems
  * remove_defaults_from_schema=True - 移除 JSON schema 中的默认值
  * 对于 Mimo 等需要 extra_body 传递 thinking 参数的模型，会自动使用包装器
- **其他模型**: 使用标准的 ChatOpenAI 配置
"""
import asyncio
import os
from typing import Optional, Dict, Any
from pathlib import Path
from ..core.action import register_action
from ..skills.parser_utils import simple_section_parser
from ..core.exceptions import LLMServiceUnavailableError
from browser_use import Agent, Browser

class BrowserSkillMixin:
    """
    基于 browser-use 的浏览器自动化技能

    特点:
    - 使用 LLM 驱动浏览器决策
    - 支持会话持久化（Chrome profile）
    - 自动处理导航、点击、输入等操作
    - **自动兼容国产模型**（GLM、Mimo、DeepSeek 等）

    配置要求:
    - 在 llm_config.json 中配置 browser_use_llm（优先）
    - 如果没有配置，回退到 deepseek-chat

    国产模型兼容性:
    - 自动检测模型厂商（从 model_name 或 URL）
    - 启用 browser-use 的 JSON schema 兼容性参数
    - 针对 thinking 模型自动禁用 thinking 模式
    """

    # 国产模型配置
    # 这些模型对结构化输出和 JSON schema 支持有限，需要特殊处理
    # 注意：DeepSeek 使用 browser-use 官方 ChatDeepSeek 类，不需要在此配置
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
            "use_extra_body": True,   # Mimo 使用 extra_body 传递 thinking 参数
        },
    }

    # 厂商识别规则（从模型名称或 URL 识别）
    VENDOR_PATTERNS = {
        "glm": ["glm", "bigmodel", "zhipu"],
        "mimo": ["xiaomi", "mimo"],
        "deepseek": ["deepseek"],
    }

    # 🆕 Skill 级别元数据
    _skill_description = "浏览器自动化技能：使用 LLM 驱动浏览器，自动完成导航、点击、输入等操作"

    _skill_usage_guide = """
使用场景：
- 需要访问和操作网页
- 需要从网页提取信息
- 需要自动化浏览器操作（点击、输入、导航）

使用建议：
- 使用 use_browser 操作浏览器
- 技能会自动处理页面交互（无需手动指定点击目标）

注意事项：
- 支持 Chrome profile 持久化
- 自动兼容国产模型（GLM、Mimo、DeepSeek）
- 需要 Playwright 和 browser-use 依赖
"""

    def _get_llm_config_path(self) -> str:
        """
        获取 llm_config.json 的路径

        Returns:
            str: llm_config.json 的绝对路径

        路径规则：
        - workspace_root 指向 MyWorld/workspace
        - llm_config.json 在 MyWorld/agents/llm_config.json
        """
        if self.root_agent.runtime is None:
            raise ValueError("runtime 未注入，无法确定 llm_config.json 路径")

        # 通过 runtime.paths 获取配置路径
        config_path = self.root_agent.runtime.paths.llm_config_path

        if not config_path.exists():
            raise FileNotFoundError(f"llm_config.json 不存在: {config_path}")

        return str(config_path)

    def _create_llm_client_for_browser_use(self, config_name: str):
        """
        为 browser-use 创建 LLMClient

        Args:
            config_name: 配置名称（如 "browser_use_llm" 或 "deepseek-chat"）

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
                "使用 BrowserUseSkill 需要安装 browser-use: "
                "pip install browser-use"
            )

        # 从 LLMClient 提取配置
        url = getattr(llm_client, 'url', None)
        api_key = getattr(llm_client, 'api_key', None)
        model_name = getattr(llm_client, 'model_name', '')

        self.logger.info(f"BrowserUseSkill 使用模型: {model_name}")

        # browser-use 的 ChatOpenAI 会自动添加 /chat/completions
        # 如果配置的 URL 已经包含 /chat/completions，需要去掉
        if url and url.endswith("/chat/completions"):
            url = url[:-len("/chat/completions")]

        # 检测厂商（从模型名称或 URL）
        model_lower = model_name.lower()
        url_lower = url.lower() if url else ""

        vendor = None
        for v, patterns in self.VENDOR_PATTERNS.items():
            if any(p in model_lower for p in patterns) or any(p in url_lower for p in patterns):
                vendor = v
                break

        # 🔥 DeepSeek 专用：使用 browser-use 官方支持的 ChatDeepSeek
        if vendor == "deepseek":
            self.logger.info(f"检测到 DeepSeek 模型，使用 browser-use 官方 ChatDeepSeek 类")
            try:
                from browser_use.llm import ChatDeepSeek
            except ImportError:
                raise ImportError(
                    "使用 ChatDeepSeek 需要更新 browser-use: "
                    "pip install -U browser-use"
                )

            # ChatDeepSeek 的参数
            # 注意：base_url 不包含 /chat/completions 后缀
            deepseek_llm = ChatDeepSeek(
                model=model_name,
                api_key=api_key,
                base_url=url,  # browser-use 会自动添加正确的路径
            )
            return deepseek_llm

        # 准备 ChatOpenAI 的基础参数（用于其他模型）
        llm_kwargs = {
            "model": model_name,
            "api_key": api_key,
            "base_url": url,
            "temperature": 0.1,
            "max_completion_tokens": 4096,
        }

        # 如果是国产模型（除了 DeepSeek，因为上面已经处理），添加兼容性参数
        if vendor and vendor in self.CHINESE_LLM_CONFIG and vendor != "deepseek":
            config = self.CHINESE_LLM_CONFIG[vendor]
            llm_kwargs.update({
                "dont_force_structured_output": config["dont_force_structured_output"],
                "remove_min_items_from_schema": config["remove_min_items_from_schema"],
                "remove_defaults_from_schema": config["remove_defaults_from_schema"],
            })

            self.logger.info(
                f"检测到国产模型 ({vendor})，启用兼容性模式："
                f"dont_force_structured_output={config['dont_force_structured_output']}, "
                f"remove_min_items_from_schema={config['remove_min_items_from_schema']}, "
                f"remove_defaults_from_schema={config['remove_defaults_from_schema']}"
            )

            # 如果需要使用 extra_body 传递 thinking 参数（Mimo）
            if config.get("use_extra_body", False):
                self.logger.info(f"使用 ChatOpenAI with extra_body for {vendor}")
                llm = self._create_llm_with_extra_body(
                    BUChatOpenAI, llm_kwargs, vendor
                )
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

        T = TypeVar('T')

        class LLMWithExtraBodyWrapper:
            """Wrapper for models that need extra_body parameter"""

            def __init__(self, base_llm):
                self._base_llm = base_llm

            def __getattr__(self, name):
                """将所有其他属性访问委托给 base_llm"""
                return getattr(self._base_llm, name)

            async def ainvoke(self, messages: list[BaseMessage], output_format: type[T] | None = None, **kwargs: Any):
                """
                调用模型，自动添加 extra_body 参数

                使用 monkey patching 技术临时修改 openai client 的 completions.create 方法
                """
                original_create = self._base_llm.get_client().chat.completions.create

                @wraps(original_create)
                async def patched_create(*args, **create_kwargs):
                    # 添加 extra_body 参数
                    create_kwargs = create_kwargs.copy()
                    create_kwargs['extra_body'] = {"thinking": {"type": "disabled"}}
                    return await original_create(*args, **create_kwargs)

                # 临时替换 create 方法
                self._base_llm.get_client().chat.completions.create = patched_create

                try:
                    # 调用原始的 ainvoke
                    result = await self._base_llm.ainvoke(messages, output_format, **kwargs)
                    return result
                finally:
                    # 恢复原始 create 方法
                    self._base_llm.get_client().chat.completions.create = original_create

        # 创建基础 LLM 实例
        base_llm = llm_class(**llm_kwargs)

        # 返回包装后的实例
        return LLMWithExtraBodyWrapper(base_llm)

    def _get_browser_use_llm(self):
        """
        获取或创建 browser-use 所需的 LLM

        优先级：
        1. browser_use_llm（llm_config.json 中的专用配置）
        2. deepseek-chat（回退配置）

        Returns:
            browser-use 的 ChatOpenAI 实例
        """
        # 惰性初始化：检查属性是否存在
        if not hasattr(self, '_browser_use_llm'):
            self._browser_use_llm = None

        # 如果已经创建，直接返回
        if self._browser_use_llm is not None:
            return self._browser_use_llm

        # 确定配置名称（优先 browser_use_llm，回退到 deepseek-chat）
        config_name = "browser_use_llm"

        try:
            # 尝试创建 LLMClient
            llm_client = self._create_llm_client_for_browser_use(config_name)
            self.logger.info(f"BrowserUseSkill 使用配置: {config_name}")
        except Exception as e:
            # 回退到 deepseek-chat
            self.logger.warning(f"无法加载配置 '{config_name}': {e}，回退到 'deepseek_chat'")
            config_name = "deepseek_chat"
            try:
                llm_client = self._create_llm_client_for_browser_use(config_name)
                self.logger.info(f"BrowserUseSkill 使用回退配置: {config_name}")
            except Exception as e2:
                raise ValueError(
                    f"无法加载 browser-use LLM 配置。"
                    f"请确保在 llm_config.json 中配置了 'browser_use_llm' 或 'deepseek_chat'。"
                    f"错误: {e2}"
                )

        # 从 LLMClient 创建 browser-use 的 LLM
        self._browser_use_llm = self._create_browser_use_llm_from_client(llm_client)

        return self._browser_use_llm

    async def _check_browser_llm_available(self) -> bool:
        """
        检查 browser_use_llm 服务是否可用

        Returns:
            bool: 服务是否可用
        """
        try:
            # 创建一个临时的 LLMClient 进行测试
            config_name = "browser_use_llm"

            # 尝试创建 browser_use_llm 的 client
            try:
                llm_client = self._create_llm_client_for_browser_use(config_name)
            except Exception:
                # 如果 browser_use_llm 不存在，尝试 deepseek-chat
                config_name = "deepseek-chat"
                llm_client = self._create_llm_client_for_browser_use(config_name)

            # 发送一个最小的测试请求
            test_messages = [{"role": "user", "content": "hi"}]

            # 设置短超时（10秒）
            response = await asyncio.wait_for(
                llm_client.think(messages=test_messages),
                timeout=10.0
            )

            # 检查响应
            if response and 'reply' in response:
                self.logger.debug(f"✓ browser_use_llm ({config_name}) is available")
                return True
            else:
                self.logger.warning(f"✗ browser_use_llm ({config_name}) returned invalid response")
                return False

        except asyncio.TimeoutError:
            self.logger.warning(f"✗ browser_use_llm ({config_name}) timeout")
            return False
        except LLMServiceUnavailableError:
            self.logger.warning(f"✗ browser_use_llm ({config_name}) service unavailable")
            return False
        except Exception as e:
            self.logger.warning(f"✗ browser_use_llm check failed: {str(e)}")
            return False

    async def _wait_for_browser_llm_recovery(self):
        """等待 browser_use_llm 服务恢复（轮询方式）"""
        check_interval = 10  # 每 5 秒检查一次
        waited_seconds = 0

        self.logger.info("⏳ Waiting for browser_use_llm recovery...")

        while True:
            await asyncio.sleep(check_interval)
            waited_seconds += check_interval

            # 检查是否恢复
            if await self._check_browser_llm_available():
                self.logger.info(f"✅ browser_use_llm recovered after {waited_seconds}s")
                break

            # 每 30 秒打印一次日志
            if waited_seconds % 30 == 0:
                self.logger.warning(
                    f"⏳ Still waiting for browser_use_llm... ({waited_seconds}s elapsed)"
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
        if not hasattr(self, '_browser_use_browser'):
            self._browser_use_browser = None

        # 检查现有浏览器实例是否可用
        if self._browser_use_browser is not None:
            # 简化逻辑：只要 browser 对象存在就复用
            # 如果浏览器真的死了，使用时会抛出异常，我们可以在调用时捕获
            self.logger.debug("BrowserUseSkill 复用现有浏览器实例")
            return self._browser_use_browser

       

        try:
            # 准备浏览器参数
            browser_kwargs = {
                "headless": headless,
                "keep_alive": True,  # 保持浏览器打开，不要在 Agent 关闭时自动关闭
            }

            # 使用固定的 profile 目录
            # 每个 Agent 有自己独立的浏览器 profile，持久化 cookies、历史等
            # 注意：使用 root_agent（BaseAgent）的名字，而不是当前 MicroAgent 的名字
            # 这样即使 MicroAgent 调用 browser skill，profile 路径也是基于 BaseAgent 的
            import os

            # 获取 BaseAgent（通过 root_agent）
            # MicroAgent 会通过 root_agent 找到最上层的 BaseAgent
            if hasattr(self, 'root_agent'):
                root_agent = self.root_agent
                agent_name = root_agent.name
            else:
                # 如果是 BaseAgent 直接调用（没有 root_agent 属性）
                root_agent = self
                agent_name = self.name

            # 通过 runtime.paths 获取路径
            if root_agent.runtime is None:
                raise ValueError("runtime 未注入，无法确定 browser 路径")
            
            user_data_dir = str(root_agent.runtime.paths.get_browser_profile_dir(agent_name))
            os.makedirs(user_data_dir, exist_ok=True)  # 确保 profile 目录存在

            browser_kwargs["user_data_dir"] = user_data_dir
            self.logger.info(f"BrowserUseSkill 使用 Chrome profile: {user_data_dir}")

            # 设置下载路径：使用工作目录
            task_id = root_agent.current_task_id or "default"

            # 通过 runtime.paths 获取工作目录
            work_files_dir = root_agent.runtime.paths.get_agent_work_files_dir(agent_name, task_id)
            download_path = str(work_files_dir / "download")

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
            browser_kwargs["executable_path"] = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

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
                self._browser_use_browser.get_browser_state_summary(),
                timeout=3.0
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
        if hasattr(self, '_browser_use_agent'):
            self._browser_use_agent = None

        # 清理 headless 模式记录
        if hasattr(self, '_browser_headless_mode'):
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
        # 添加重试机制处理 browser_use_llm 服务异常
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                llm = self._get_browser_use_llm()
                break  # 成功获取 LLM，退出循环
            except LLMServiceUnavailableError as e:
                
                await self._wait_for_browser_llm_recovery()
                self.logger.info("✅ browser_use_llm 已恢复，继续创建 Agent...")
                continue

        browser = await self._get_browser(headless=headless)

        # 创建 Agent，使用默认参数
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            use_vision=False,
            use_judge=False
        )

        # 记录 headless 状态
        self._browser_headless_mode = headless

        # 保存 Agent 引用以便复用
        self._browser_use_agent = agent

        self.logger.info(f"✅ 已创建新的 browser-use Agent（headless={headless}）")
        return agent

    
    


    @register_action(
        short_desc="给浏览器自然语言命令[task]",
        description="""操作浏览器，简单描述对浏览器做什么，例如访问某个网站，查看当前页面内容，点击某个按钮等等针对浏览器的操作,可以一次一个动作，也可以一次描述多个动作。""",
        param_infos={
            "task": "对浏览器器的具体操作和要求，包括访问哪里，要获取什么数据等等，注意区别用户描述里哪些是具体针对浏览器的，哪些是做这些事情的最终目的。这个参数应该只包含针对浏览器的操作描述，不需要包含更高级最终意图的描述。",
            "headless": "是否无头模式（默认False，显示浏览器窗口）"
        }
    )
    async def use_browser(
        self,
        task: str,
        headless: bool = False
    ) -> str:
        # 构建完整任务描述
        full_task = task + "\n不要做太多重复尝试，尽早返回结果。结束时只保留最后的tab，关闭多余的tab，但不要全部关闭"


        self.logger.info(f"BrowserUseSkill 开始任务")

        self.logger.info(f"  任务: {task}")

        # ========== 添加重试循环处理 browser_use_llm 服务异常 ==========
        max_retries = 10  # 最多重试10次
        retry_count = 0
        agent = None
        llm_available = self._check_browser_llm_available()  # 预先检查服务状态，记录日志
        if not llm_available:
            self.logger.warning("⚠️  browser_use_llm 服务不可用，开始重试...")
            while retry_count < max_retries and not llm_available:
                await asyncio.sleep(60)  # 等待一小段时间让服务稳定
                llm_available = self._check_browser_llm_available()
                retry_count += 1
                self.logger.warning(f"⚠️  browser_use_llm 仍不可用，重试 {retry_count}/{max_retries}...")
            if retry_count >= max_retries:
                error_msg = f"browser_use_llm 服务不可用"
                self.logger.error(error_msg)
                return f"任务执行失败: {error_msg}"
        self.logger.info(f"browser_use_llm 服务可用")
        retry_count = 0
        last_error = None
        while True:
            agent = None
            try:
                # 获取或创建 Agent（会自动复用）
                agent = await self._create_new_agent(full_task, headless)


                history = await agent.run()

                # 成功执行，退出重试循环
                break

            except LLMServiceUnavailableError as e:
                # browser_use_llm 服务异常
                
                await self._wait_for_browser_llm_recovery()

                # 恢复后重试
                self.logger.info("✅ browser_use_llm 已恢复，重新执行任务")
                continue

            except Exception as e:
                # 其他异常，直接返回错误
                error_msg = f"未知错误: {type(e).__name__}: {e}"
                self.logger.error(error_msg, exc_info=True)
                last_error = error_msg
            finally:
                try:
                    if agent:
                        agent.close()
                except Exception as e:
                    self.logger.warning(f"关闭 Agent 时发生错误: {e}")

                


        # ========== 执行成功后的处理 ==========
        # 获取最终结果
        final_result = history.final_result() or last_error or ""
        

        # 清理结果中的 Simple judge note（经常不准确）
        import re
        final_result = re.sub(r'\[Simple judge:.*?\]', '', final_result, flags=re.DOTALL).strip()

        # 获取当前浏览器停留的 URL
        try:
            current_url = history.urls()[-1] if history.urls() else None
        except Exception:
            current_url = None

        # 🆕 保存最后访问的 URL
        if current_url:
            self._last_browser_url = current_url
            self.logger.debug(f"浏览器当前 URL: {current_url}")

        # 构建返回结果（使用显示用的 URL）
        current_url_display = current_url if current_url else "未知"

        # 构建返回结果
        result_parts = []
        if final_result:
            result_parts.append(f"{final_result}")
        else:
            result_parts.append("任务已完成，未返回结果")

        result_parts.append(f"\n【当前页面】\n{current_url_display}")

        self.logger.info("BrowserUseSkill 任务完成")
        return "\n".join(result_parts)
