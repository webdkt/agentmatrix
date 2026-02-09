"""
Browser-Use Skill - 基于 browser-use 的浏览器自动化技能

提供高级的浏览器自动化能力，使用 browser-use 库让 LLM 驱动浏览器操作。
"""
import asyncio
import os
from typing import Optional, Dict, Any
from pathlib import Path
from ..core.action import register_action


class BrowserUseSkillMixin:
    """
    基于 browser-use 的浏览器自动化技能
    
    特点:
    - 使用 LLM 驱动浏览器决策
    - 支持视觉模式（如果 Agent 配置了 vision_brain）
    - 自动处理导航、点击、输入等操作
    
    配置要求:
    - 需要在 llm_config.json 中配置 default_vision（可选，用于视觉模式）
    - 或者 Agent YAML 中配置 vision_brain
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._browser_use_browser = None
        self._browser_use_llm = None
        self._browser_use_vision_llm = None
    
    def _get_llm_client_config(self, llm_client) -> Dict[str, str]:
        """
        从 AgentMatrix 的 LLMClient 获取配置
        
        Args:
            llm_client: LLMClient 实例 (brain 或 vision_brain)
        
        Returns:
            包含 url, api_key, model_name 的字典
        """
        if llm_client is None:
            return None
        
        # LLMClient 有 url, api_key, model_name 属性
        return {
            "url": getattr(llm_client, 'url', None),
            "api_key": getattr(llm_client, 'api_key', None),
            "model_name": getattr(llm_client, 'model_name', None),
        }
    
    def _create_browser_use_llm(self, config: Dict[str, str]):
        """
        使用 AgentMatrix LLMClient 的配置创建 browser-use 的 LLM
        
        Args:
            config: 包含 url, api_key, model_name 的配置字典
        
        Returns:
            browser-use 的 ChatOpenAI 实例
        """
        try:
            from browser_use.llm.openai.chat import ChatOpenAI as BUChatOpenAI
        except ImportError:
            raise ImportError(
                "使用 BrowserUseSkill 需要安装 browser-use: "
                "pip install browser-use"
            )
        
        url = config.get("url")
        api_key = config.get("api_key")
        model_name = config.get("model_name", "gpt-4o-mini")
        
        # browser-use 的 ChatOpenAI 会自动添加 /chat/completions
        # 如果配置的 URL 已经包含 /chat/completions，需要去掉
        if url and url.endswith("/chat/completions"):
            url = url[:-len("/chat/completions")]
        
        # 创建 browser-use 的 ChatOpenAI
        # browser-use 的 ChatOpenAI 直接使用 openai 库，不是 langchain
        llm = BUChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=url,
            temperature=0.1,
            max_completion_tokens=4096,
        )
        
        return llm
    
    def _get_browser_use_llm(self, use_vision: bool = False):
        """
        获取或创建 browser-use 所需的 LLM
        
        Args:
            use_vision: 是否使用视觉模型
        
        Returns:
            browser-use 的 ChatOpenAI 实例
        """
        # 如果请求视觉模式且 vision_brain 已配置
        if use_vision:
            if self._browser_use_vision_llm is not None:
                return self._browser_use_vision_llm
            
            # 检查 Agent 是否有 vision_brain
            vision_brain = getattr(self, 'vision_brain', None)
            if vision_brain:
                config = self._get_llm_client_config(vision_brain)
                if config:
                    self._browser_use_vision_llm = self._create_browser_use_llm(config)
                    self.logger.info(f"BrowserUseSkill 使用 Vision Brain: {config.get('model_name')}")
                    return self._browser_use_vision_llm
            
            # vision_brain 未配置，回退到普通 brain
            self.logger.warning("Vision Brain 未配置，回退到普通 Brain")
        
        # 使用普通 brain
        if self._browser_use_llm is not None:
            return self._browser_use_llm
        
        brain = getattr(self, 'brain', None)
        if brain is None:
            raise ValueError("Agent 没有配置 brain，无法使用 BrowserUseSkill")
        
        config = self._get_llm_client_config(brain)
        self._browser_use_llm = self._create_browser_use_llm(config)
        self.logger.info(f"BrowserUseSkill 使用 Brain: {config.get('model_name')}")
        
        return self._browser_use_llm
    
    def _has_vision_brain(self) -> bool:
        """检查 Agent 是否配置了 vision_brain"""
        vision_brain = getattr(self, 'vision_brain', None)
        return vision_brain is not None
    
    async def _get_browser(self, headless: bool = True):
        """
        获取或创建 browser-use 的 Browser 实例

        Args:
            headless: 是否使用无头模式（True=隐藏浏览器，False=显示浏览器）
        """
        # 检查现有浏览器实例是否可用
        if self._browser_use_browser is not None:
            try:
                # 尝试访问 context 来检查浏览器是否还在运行
                if hasattr(self._browser_use_browser, 'context') and \
                   self._browser_use_browser.context is not None:
                    self.logger.debug("BrowserUseSkill 复用现有浏览器实例")
                    return self._browser_use_browser
                else:
                    # 浏览器已关闭，清理后重新创建
                    self.logger.debug("BrowserUseSkill 现有浏览器已关闭，将创建新实例")
                    self._browser_use_browser = None
            except Exception as e:
                # 浏览器实例可能已损坏，清理后重新创建
                self.logger.warning(f"BrowserUseSkill 浏览器实例检查失败: {e}，将创建新实例")
                self._browser_use_browser = None

        # 创建新浏览器实例
        try:
            from browser_use import Browser
        except ImportError:
            raise ImportError(
                "使用 BrowserUseSkill 需要安装 browser-use: "
                "pip install browser-use"
            )

        try:
            self._browser_use_browser = Browser(headless=headless)
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
    
    @register_action(
        description="使用 browser-use 访问指定URL并执行导航任务，可以自动点击、填写表单、提取信息",
        param_infos={
            "url": "要访问的网页URL",
            "task": "具体的任务描述，例如'点击登录按钮并填写用户名密码'",
            "use_vision": "是否使用视觉模式（需要配置 vision_brain）",
            "headless": "是否隐藏浏览器窗口（默认True隐藏，设为False可看浏览器运行）",
            "max_actions": "最大动作步数（默认10）"
        }
    )
    async def browser_navigate(
        self,
        url: str,
        task: str,
        use_vision: Optional[bool] = None,
        headless: bool = True,
        max_actions: int = 10
    ) -> str:
        """
        使用 browser-use 访问网页并执行任务

        Args:
            url: 要访问的网页 URL
            task: 自然语言描述的任务
            use_vision: 是否使用视觉模式（None=自动检测，需要配置 vision_brain）
            max_actions: 最大执行步数

        Returns:
            任务执行结果
        """
        # 检查 browser-use 是否安装
        try:
            from browser_use import Agent
        except ImportError as e:
            error_msg = "错误：未安装 browser-use。请运行: pip install browser-use"
            self.logger.error(error_msg)
            return error_msg

        # 检查是否请求视觉模式但没有配置 vision_brain
        if use_vision and not self._has_vision_brain():
            self.logger.warning("请求使用视觉模式，但 Agent 未配置 vision_brain，将使用普通模式")
            use_vision = False

        # 自动检测：如果配置了 vision_brain 且没有明确禁用，则启用
        if use_vision is None:
            use_vision = self._has_vision_brain()

        # 获取 LLM
        try:
            llm = self._get_browser_use_llm(use_vision=use_vision)
        except ValueError as e:
            # Agent 没有配置 brain
            error_msg = f"配置错误: {e}"
            self.logger.error(error_msg)
            return error_msg
        except ImportError as e:
            # browser-use 导入失败
            error_msg = f"依赖错误: {e}"
            self.logger.error(error_msg)
            return error_msg
        except Exception as e:
            # 其他 LLM 加载错误
            error_msg = f"无法加载 LLM: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            return error_msg

        # 构建完整任务描述
        full_task = f"访问 {url}，然后执行以下任务：{task}"

        self.logger.info(f"BrowserUseSkill 开始任务")
        self.logger.info(f"  URL: {url}")
        self.logger.info(f"  任务: {task}")
        self.logger.info(f"  视觉模式: {use_vision}")
        self.logger.info(f"  最大动作数: {max_actions}")

        try:
            # 获取浏览器（根据 headless 参数决定是否显示界面）
            browser = await self._get_browser(headless=headless)

            # 创建 Agent
            agent = Agent(
                task=full_task,
                llm=llm,
                browser=browser,
                use_vision=use_vision,
                max_actions=max_actions,
            )

            # 执行任务
            history = await agent.run()

            # 获取最终结果
            result = history.final_result()

            self.logger.info("BrowserUseSkill 任务完成")
            return f"任务执行结果：\n{result if result else '任务已完成，但没有返回结构化结果'}"

        except ImportError as e:
            error_msg = f"导入错误: {e}"
            self.logger.error(error_msg, exc_info=True)
            return f"任务执行失败: {error_msg}"
        except ValueError as e:
            error_msg = f"参数错误: {e}"
            self.logger.error(error_msg, exc_info=True)
            return f"任务执行失败: {error_msg}"
        except RuntimeError as e:
            error_msg = f"运行时错误: {e}"
            self.logger.error(error_msg, exc_info=True)
            return f"任务执行失败: {error_msg}"
        except Exception as e:
            error_msg = f"未知错误: {type(e).__name__}: {e}"
            self.logger.error(error_msg, exc_info=True)
            return f"任务执行失败: {error_msg}"
    
    @register_action(
        description="在指定网站搜索关键词，自动处理搜索流程",
        param_infos={
            "site_url": "网站首页URL",
            "keyword": "要搜索的关键词",
            "search_instruction": "可选，特殊的搜索说明，例如'在顶部的搜索框中输入'",
            "use_vision": "是否使用视觉模式（需要配置 vision_brain）",
            "headless": "是否隐藏浏览器窗口（默认True隐藏，设为False可看浏览器运行）",
            "max_actions": "最大动作步数（默认15）"
        }
    )
    async def browser_search(
        self,
        site_url: str,
        keyword: str,
        search_instruction: str = "",
        use_vision: Optional[bool] = None,
        headless: bool = True,
        max_actions: int = 15
    ) -> str:
        """
        在指定网站搜索关键词
        
        Args:
            site_url: 网站首页 URL
            keyword: 搜索关键词
            search_instruction: 特殊的搜索说明（可选）
            use_vision: 是否使用视觉模式
            max_actions: 最大执行步数
        
        Returns:
            搜索结果
        """
        # 构建搜索任务
        if search_instruction:
            task = f"{search_instruction}，搜索关键词：'{keyword}'，然后返回搜索结果列表"
        else:
            task = (
                f"1. 在页面上找到搜索框（通常在页面顶部或导航栏附近）\n"
                f"2. 在搜索框中输入关键词：'{keyword}'\n"
                f"3. 点击搜索按钮或按回车\n"
                f"4. 等待搜索结果页面加载\n"
                f"5. 提取并返回搜索结果的主要内容（标题、摘要等）"
            )
        
        return await self.browser_navigate(
            url=site_url,
            task=task,
            use_vision=use_vision,
            headless=headless,
            max_actions=max_actions
        )
    
    @register_action(
        description="访问深圳图书馆官网并搜索图书",
        param_infos={
            "book_name": "要搜索的书名",
            "use_vision": "是否使用视觉模式（需要配置 vision_brain）",
            "headless": "是否隐藏浏览器窗口（默认True隐藏，设为False可看浏览器运行）",
            "max_actions": "最大动作步数（默认15）"
        }
    )
    async def search_szlib_book(
        self,
        book_name: str,
        use_vision: Optional[bool] = None,
        headless: bool = True,
        max_actions: int = 15
    ) -> str:
        """
        访问深圳图书馆官网搜索图书
        
        Demo 功能：展示 browser-use 的基本能力
        
        Args:
            book_name: 要搜索的书名
            use_vision: 是否使用视觉模式
            max_actions: 最大执行步数
        
        Returns:
            搜索结果
        """
        site_url = "https://www.szlib.org.cn/"
        
        task = (
            f"1. 在页面上找到图书搜索框\n"
            f"2. 在搜索框中输入书名：'{book_name}'\n"
            f"3. 点击搜索按钮\n"
            f"4. 等待搜索结果页面加载\n"
            f"5. 提取搜索结果：书名、作者、出版社、可借状态等信息\n"
            f"6. 返回结构化的搜索结果摘要"
        )
        
        self.logger.info(f"开始搜索深圳图书馆图书: {book_name}")
        
        return await self.browser_navigate(
            url=site_url,
            task=task,
            use_vision=use_vision,
            headless=headless,
            max_actions=max_actions
        )
