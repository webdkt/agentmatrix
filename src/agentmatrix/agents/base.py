import asyncio
from typing import Dict, Optional, Callable, List, Any
from ..core.message import Email
from ..core.events import AgentEvent
from ..core.action import register_action
from ..core.session_manager import SessionManager
from ..core.session_context import SessionContext
import traceback
from dataclasses import asdict
import inspect
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
import logging
from pathlib import Path
from .micro_agent import MicroAgent

class BaseAgent(AutoLoggerMixin):
    _log_from_attr = "name" # 日志名字来自 self.name 属性

    _custom_log_level = logging.DEBUG

    def __init__(self, profile):
        self.name = profile["name"]
        self.description = profile["description"]

        # 加载 persona 配置（多个 persona，按阶段或功能分类）
        self.persona_config = profile.get("persona", {"base":""})
        self.persona = self.get_persona()

        # 加载其他 prompts（如 task_prompt）
        self.other_prompts = profile.get("prompts", {})

        # Prompt 模板缓存
        self._prompt_cache = {}

        self.profile = profile
        self.backend_model = profile.get("backend_model", "default_llm")

        # 🆕 新架构：读取 skills 配置
        self.skills = profile.get("skills", [])
        self.brain = None
        self.cerebellum = None
        self.vision_brain = None  # 🆕 视觉大模型（支持图片理解的LLM）

        self.status = "IDLE"
        
        # 📊 状态历史（最近 3 条，用于前端查询）
        self.status_history = []
        self._max_status_history = 3
        
        self.last_received_email = None #最后收到的信
        self._workspace_root = None
        self._matrix_path = None
        self.post_office = None
        self.last_email_processed = True

        # Session Manager（延迟初始化）
        self.session_manager = None

        # 标准组件
        self.inbox = asyncio.Queue()

        # 事件回调 (Server 注入)
        self.async_event_callback: Optional[Callable] = None

        # Runtime 引用 (由 AgentMatrix 注入)
        self.runtime = None

        # ✨ 新架构：使用 action_registry 代替 actions_map
        self.action_registry = {}  # name -> bound_method (新架构)
        self.actions_meta = {}  # name -> metadata (给小脑看)
        self.current_session = None
        self.current_task_id = None

        # 扫描 BaseAgent 自身的 actions（不包含 skills）
        self._scan_all_actions()


        # 🔀 暂停/恢复机制
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始状态为已设置（不阻塞）

        # 📊 执行栈追踪（用于状态查询）
        self._execution_stack = []  # List[FrameInfo]

        # 💬 ask_user 机制（等待用户输入）
        self._pending_user_question = None  # 当前等待用户回答的问题
        self._user_input_future = None  # 用于等待用户输入的 Future

        # 🆕 双 Worker 模型（email_worker + history_worker）
        self.pending_summaries_queue = []  # 待总结的消息块队列
        self.email_worker_task = None  # email worker 引用
        self.history_worker_task = None  # history worker 引用

        # 🐳 Docker 容器管理器（延迟初始化，在 workspace_root setter 中初始化）
        self.docker_manager = None

        self.logger.info(f"Agent {self.name} 初始化完成")

        # ✨ 新架构：Skills 改为 Lazy Load（通过 SKILL_REGISTRY 自动发现）
        # 不再需要手动注册，移除 _register_new_skills() 方法


    def get_persona(self, persona_name: str = "base", **kwargs) -> str:
        """
        获取并渲染 persona

        Args:
            persona_name: persona 名称（如 "planner", "researcher"）
            **kwargs: 模板变量（如 round_count=1, blueprint_content="..."）

        Returns:
            渲染后的 persona 字符串

        Raises:
            ValueError: persona 不存在
            KeyError: 缺少必需的变量
        """
        template = self.persona_config.get(persona_name.lower(), "")

        # 直接渲染，缺变量会抛出 KeyError
        return f"你的名字叫{self.name}.\n" + template.format(**kwargs)

    def _init_docker_manager(self):
        """初始化 Docker 容器管理器"""
        from ..core.docker_manager import DockerContainerManager

        if not self._workspace_root:
            raise RuntimeError("workspace_root 未设置，无法初始化 Docker")

        try:
            self.docker_manager = DockerContainerManager(
                agent_name=self.name,
                workspace_root=self._workspace_root,
                parent_logger=self.logger
            )

            # 初始化目录结构
            self.docker_manager.initialize_directories()

            self.logger.info("✅ Docker 容器管理器初始化成功")

        except Exception as e:
            self.logger.error(f"Docker 初始化失败: {e}")
            raise  # 不降级，直接抛出异常

    def get_skill_prompt(self, skill_name: str, prompt_name: str, **kwargs) -> str:
        """
        获取并渲染 skill prompt

        Args:
            skill_name: skill 名称（如 "browser_use"）
            prompt_name: prompt 名称（如 "task_optimization"）
            **kwargs: 模板变量

        Returns:
            渲染后的 prompt 字符串

        Raises:
            FileNotFoundError: prompt 文件不存在
            KeyError: 缺少必需的变量
        """
        # 从文件加载（带缓存）
        return self._load_skill_prompt(skill_name, prompt_name, **kwargs)

    def _load_skill_prompt(self, skill_name: str, prompt_name: str, **kwargs) -> str:
        """
        从文件加载 skill prompt

        文件路径：src/agentmatrix/prompts/skills/{skill_name}/{prompt_name}.txt

        Args:
            skill_name: skill 名称
            prompt_name: prompt 名称
            **kwargs: 模板变量

        Returns:
            渲染后的 prompt 字符串

        Raises:
            FileNotFoundError: prompt 文件不存在
            KeyError: 缺少必需的变量
        """
        from pathlib import Path

        # 确定 prompts 目录
        current_file = Path(__file__)
        agentmatrix_root = current_file.parent.parent
        prompts_dir = agentmatrix_root / "prompts" / "skills" / skill_name
        prompt_file = prompts_dir / f"{prompt_name}.txt"

        # 检查文件存在
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        # 读取模板（带缓存）
        cache_key = f"{skill_name}/{prompt_name}"
        if cache_key not in self._prompt_cache:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                self._prompt_cache[cache_key] = f.read()

        template = self._prompt_cache[cache_key]

        # 直接渲染，缺变量会抛出 KeyError
        return template.format(**kwargs)



    @property
    def workspace_root(self):
        return self._workspace_root

    @workspace_root.setter
    def workspace_root(self, value):
        self._workspace_root = value
        if value is not None:
            self.session_manager = SessionManager(
                agent_name=self.name,
                workspace_root=value,
                matrix_path=self._matrix_path
            )

            # 🆕 初始化 SKILLS 目录（用于 MD Document Skills）
            from ..skills.registry import SKILL_REGISTRY
            from pathlib import Path

            skills_dir = Path(value) / "SKILLS"
            skills_dir.mkdir(parents=True, exist_ok=True)

            # 设置到 SKILL_REGISTRY（供 MD skill 加载使用）
            SKILL_REGISTRY.set_workspace_skills_dir(skills_dir)

            self.logger.info(f"✅ SKILLS 目录已初始化: {skills_dir}")

            # 🐳 初始化 Docker 容器管理器（在 workspace_root 设置后）
            if self.docker_manager is None:
                self._init_docker_manager()

    @property
    def matrix_path(self):
        return self._matrix_path

    @matrix_path.setter
    def matrix_path(self, value):
        self._matrix_path = value
        # 如果 session_manager 已经存在，需要更新它的 matrix_path
        if self.session_manager is not None:
            self.session_manager.matrix_path = value

    # ========== 暂停/恢复机制 ==========

    async def pause(self):
        """暂停 Agent 执行"""
        if self._paused:
            self.logger.warning(f"Agent {self.name} 已经是暂停状态")
            return

        self._paused = True
        self._pause_event.clear()  # 清除事件，导致 await 会阻塞
        self.logger.info(f"⏸️ Agent {self.name} 已暂停")

    async def resume(self):
        """恢复 Agent 执行"""
        if not self._paused:
            self.logger.warning(f"Agent {self.name} 未暂停，无需恢复")
            return

        self._paused = False
        self._pause_event.set()  # 设置事件，唤醒所有等待的协程
        self.logger.info(f"▶️ Agent {self.name} 已恢复")

    async def _checkpoint(self):
        """
        检查点：在 MicroAgent 的关键位置调用

        如果 Agent 处于暂停状态，会挂起当前协程，直到恢复。
        """
        if self._paused:
            self.logger.debug(f"🛑 Agent {self.name} 检查到暂停，等待恢复...")
            await self._pause_event.wait()  # 挂起，等待 resume()
            self.logger.debug(f"✅ Agent {self.name} 已恢复执行")

    @property
    def is_paused(self) -> bool:
        """返回 Agent 是否暂停"""
        return self._paused

    # ========== ask_user 机制 ==========

    async def ask_user(self, question: str) -> str:
        """
        等待用户输入（特殊 action）

        此方法会挂起当前 MicroAgent 的执行，等待用户通过 submit_user_input 提供答案。
        同时支持全局暂停机制。

        Args:
            question: 向用户提出的问题

        Returns:
            str: 用户的回答

        Example:
            # 在 MicroAgent._execute_action 中
            answer = await self.root_agent.ask_user("请确认预算范围")
            # 返回: "5万-10万"
        """
        # ✅ 1. 发送事件（通知前端）
        task_id = self.current_task_id or self.current_session.get("task_id") if self.current_session else None
        await self.emit("ASK_USER", question, {
            "agent_name": self.name,
            "task_id": task_id,
            "session_id": self.current_session.get("session_id") if self.current_session else None
        })
        
        # 2. 记录问题（给 API 查询）
        self._pending_user_question = question

        # 3. 创建 Future 并挂起
        self._user_input_future = asyncio.Future()

        self.logger.info(f"💬 向用户提问: {question[:50]}{'...' if len(question) > 50 else ''}")

        try:
            # 发起提问前，先确保当前没有被暂停
            await self._checkpoint()

            # 🔧 修复：直接 await Future，不使用 wait_for（避免 Future 被取消）
            # 无限期挂起，直到前端调用 submit_user_input(answer) 触发 set_result(answer)
            answer = await self._user_input_future
            
            # 拿到答案后，再次检查是否在等待期间系统被暂停了
            await self._checkpoint()

            self.logger.info(f"✅ 收到用户回答: {answer[:50]}{'...' if len(answer) > 50 else ''}")
            return answer
            
        finally:
            # 🔧 修复：状态清理（避免内存泄漏）
            self._user_input_future = None
            self._pending_user_question = None

    async def submit_user_input(self, answer: str):
        """
        提交用户输入（由 Server API 调用）

        此方法会唤醒正在等待的 ask_user 调用，并传入用户的回答。

        Args:
            answer: 用户的回答

        Raises:
            RuntimeError: 如果 Agent 当前没有在等待用户输入

        Example:
            # 在 Server API 中
            await agent.submit_user_input("5万-10万")
        """
        if not self._user_input_future or self._user_input_future.done():
            raise RuntimeError(f"Agent {self.name} is not waiting for user input")

        self.logger.debug(f"📥 提交用户回答: {answer[:50]}{'...' if len(answer) > 50 else ''}")

        # 设置结果，唤醒 Future
        self._user_input_future.set_result(answer)

    # ========== 状态查询 ==========

    @property
    def current_status(self) -> dict:
        """
        获取当前执行状态

        Returns:
            dict: 包含状态信息的字典
        """
        if not self._execution_stack:
            return {
                "agent_name": self.name,
                "status": "idle",
                "paused": self._paused,
                "stack_depth": 0,
                "message": "Agent is idle (no active MicroAgent)"
            }

        # 获取栈顶帧
        top_frame = self._execution_stack[-1]

        # 构建执行栈描述
        stack_desc = []
        for i, frame in enumerate(self._execution_stack):
            indent = "  " * i
            frame_info = {
                "level": i + 1,
                "micro_agent_id": frame.get("micro_agent_id", "unknown"),
                "task": frame.get("task", "unknown"),
                "action": frame.get("current_action"),
                "llm_thinking": frame.get("llm_thinking", False)
            }
            stack_desc.append(frame_info)

        return {
            "agent_name": self.name,
            "status": "paused" if self._paused else "running",
            "paused": self._paused,
            "stack_depth": len(self._execution_stack),
            "current_frame": top_frame,
            "execution_stack": stack_desc
        }

    def _scan_all_actions(self):
        """
        扫描所有 actions（新架构）

        扫描自身及其父类的所有 @register_action 方法，
        并存储到 action_registry（已绑定的方法）。
        """
        import inspect

        for cls in self.__class__.__mro__:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if hasattr(method, '_is_action') and method._is_action:
                    # 只存储第一次遇到的（避免重复）
                    if name not in self.action_registry:
                        # 存储已绑定的方法（直接可调用）
                        self.action_registry[name] = getattr(self, name)

                        # 提取元数据
                        desc = method._action_desc
                        param_infos = method._action_param_infos

                        self.actions_meta[name] = {
                            "action": name,
                            "description": desc,
                            "params": param_infos
                        }

    @property
    def private_workspace(self) -> Path:
        """
        获取当前 session 的个人工作目录（如果不存在则自动创建）

        Returns:
            Path: 个人工作目录路径，格式为 workspace_root / task_id / agents / agent_name
        """
        if not self.workspace_root:
            #raise ValueError("workspace_root is not set")
            return None

        task_id = self.current_task_id or "default"
        workspace = Path(self.workspace_root) / task_id / "agents" / self.name

        # 如果目录不存在，创建目录
        workspace.mkdir(parents=True, exist_ok=True)

        return workspace

    @property
    def current_workspace(self) -> Path:
        """
        获取当前 session 的共享工作目录（如果不存在则自动创建）

        Returns:
            Path: 共享工作目录路径，格式为 workspace_root / task_id / shared
        """
        if not self.workspace_root:
            #raise ValueError("workspace_root is not set")
            return None

        task_id = self.current_task_id or "default"
        workspace = Path(self.workspace_root) / task_id / "shared"

        # 如果目录不存在，创建目录
        workspace.mkdir(parents=True, exist_ok=True)

        return workspace



    async def emit(self, event_type, content, payload={}):
        """
        发送事件到注册的事件回调函数
        
        Args:
            event_type (str): 事件的类型，用于标识不同种类的事件,
            
            content (str): 事件的主要内容描述
            payload (dict, optional): 事件的附加数据，默认为None，当为None时会使用空字典
            
        Returns:
            None
            
        Raises:
            无显式抛出异常
        """
        # 检查是否存在事件回调函数
        if self.async_event_callback:
            # 创建新的事件对象，包含事件类型、发送者名称、内容和附加数据
            event = AgentEvent(event_type, self.name,self.status, content, payload)
            # 异步调用事件回调函数，将事件对象传递过去
            await self.async_event_callback(event)



    async def run(self):
        """主循环：启动并监控双 worker"""
        # 🆕 启动两个 worker
        self.email_worker_task = asyncio.create_task(self._email_worker())
        self.history_worker_task = asyncio.create_task(self._history_worker())

        await self.emit("SYSTEM", f"{self.name} Started")

        # 监控 email_worker（history_worker 由 email_worker 管理）
        try:
            await asyncio.gather(self.email_worker_task, return_exceptions=True)
        except asyncio.CancelledError:
            self.logger.info(f"{self.name} main loop cancelled")
            # 取消所有 worker
            if self.email_worker_task:
                self.email_worker_task.cancel()
            if self.history_worker_task:
                self.history_worker_task.cancel()
        except Exception as e:
            self.logger.exception(f"Unexpected error in {self.name} main loop")

    async def process_email(self, email: Email):
        """
        处理邮件 = 恢复记忆 + 执行 + 保存记忆

        使用内置 Micro Agent 执行 think-act 循环
        """
        # 1. Session Management (Routing)
        self.logger.debug(f"New Email")
        self.logger.debug(str(email))
        session = await self.session_manager.get_session(email)
        self.current_session = session
        self.current_task_id = session["task_id"]

        # 2. 更新 receiver_session_id（如果尚未设置）
        if email.receiver_session_id is None:
            await self.post_office.update_email_receiver_session(
                email_id=email.id,
                receiver_session_id=session["session_id"],
                receiver_name=self.name
            )

        # 🐳 容器模式：唤醒并切换工作区
        task_id = session["task_id"]

        # 检查 Docker 管理器是否已初始化
        if self.docker_manager is None:
            raise RuntimeError(
                "Docker 容器管理器未初始化。"
                "请确保 workspace_root 已正确设置。"
            )

        # 唤醒容器
        self.docker_manager.wakeup()

        # 切换工作区
        success = self.docker_manager.switch_workspace(task_id)
        if not success:
            raise RuntimeError(f"工作区切换失败: {task_id}")

        try:
            # 创建 SessionContext 对象（包装 session["context"]）
            self._session_context = SessionContext(
                persistent=True,
                session_manager=self.session_manager,
                session=session,
                initial_data=session.get("context", {})
            )

            # 设置当前 session 目录
            if self.workspace_root:
                from pathlib import Path
                self.current_session_folder = str(
                    Path(self.workspace_root) /
                    session["task_id"] /
                    "history" /
                    self.name /
                    session["session_id"]
                )
            else:
                self.current_session_folder = None

            # 2. 准备参数
            task = str(email)

            # 3. 准备 available_skills（🆕 新架构）
            available_skills = self.profile.get("skills", [])

            # 自动注入 base 和 email skills（Top-level MicroAgent 必备）
            # base: get_current_datetime, take_a_break, ask_user（所有 MicroAgent 必备）
            # email: send_email（Top-level MicroAgent 需要和用户通信）
            # 确保 Top-level MicroAgent 始终拥有这些基础 actions
            for required in ["base", "email"]:
                if required not in available_skills:
                    available_skills = [required] + available_skills

            # 4. 执行 Micro Agent
            # 每次创建新的 MicroAgent
            # 🆕 传入身份特征参数
            persona = self.get_persona()
            micro_core = MicroAgent(
                parent=self,
                name=self.name,
                
                available_skills=available_skills
            )

            result = await micro_core.execute(
                run_label='Process Email',
                task=task,
                max_steps=100,
                yellow_pages=self.post_office.yellow_page_exclude_me(self.name),
                session_manager=self.session_manager,
                session=session
            )

            # 5. 更新 session 元数据
            # 注意：session["history"] 已经在 MicroAgent 执行过程中自动保存了
            # 这里只更新其他元数据
            session["last_sender"] = self.name  # 更新最后发送者

            # 6. 最终保存到磁盘（保险起见，虽然 MicroAgent 已经自动保存）
            try:
                await self.session_manager.save_session(session)
                self.logger.debug(f"💾 Final save of session {session['session_id'][:8]}")
            except Exception as e:
                self.logger.warning(f"Failed to final-save session: {e}")

            # 只有当 result 是字符串且长度超过 100 时才切片
            if isinstance(result, str) and len(result) > 100:
                result_preview = f"{result[:100]}..."
            else:
                result_preview = result if result else 'No result'
            self.logger.debug(f"Email processing completed. Result: {result_preview}")
            self.logger.info(f"Session {session['session_id'][:8]} now has {len(session['history'])} messages")

        finally:
            # 🐳 容器模式：休眠容器
            self.docker_manager.hibernate()

    # ==================== 📊 状态管理 ====================
    
    def update_status(self, message: str):
        """
        更新状态（保存最近 3 条到历史记录）
        
        这个方法会被 MicroAgent 调用，将状态消息
        保存到 BaseAgent 的状态历史中。
        
        Args:
            message: 状态消息（简单文本）
        """
        from datetime import datetime
        
        status = {
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存最近 3 条
        self.status_history.append(status)
        if len(self.status_history) > self._max_status_history:
            self.status_history.pop(0)
        
        self.logger.debug(f"📊 Status: {message}")
    
    def get_current_status(self) -> dict:
        """
        获取当前状态（最新一条）
        
        Returns:
            dict: {"message": str, "timestamp": str}
        """
        if self.status_history:
            return self.status_history[-1]
        return {"message": "空闲", "timestamp": None}
    
    def get_status_history(self) -> list:
        """
        获取状态历史（最近 3 条）
        
        Returns:
            list: [{"message": str, "timestamp": str}, ...]
        """
        return self.status_history.copy()
    
        # ==================== 🆕 双 Worker 模型 ====================

    async def _email_worker(self):
        """
        邮件处理 Worker（独立任务）

        职责：
        - 监听 inbox，阻塞等待邮件
        - 来邮件时取消 history_worker
        - 处理邮件
        - 邮件处理完成后恢复 history_worker
        """
        self.logger.info("📧 Email worker 已启动")

        try:
            while True:
                try:
                    # 阻塞等待邮件
                    email = await self.inbox.get()

                    # ⚠️ 取消 history_worker（如果正在运行）
                    if self.history_worker_task and not self.history_worker_task.done():
                        self.logger.info("⏸️ 取消 history worker（开始处理邮件）")
                        self.history_worker_task.cancel()

                    # 处理邮件（现有逻辑）
                    self.last_received_email = email
                    self.last_email_processed = False

                    try:
                        await self.process_email(email)
                        self.last_email_processed = True
                    except asyncio.CancelledError:
                        # 任务被取消，保持 last_email_processed = False
                        self.logger.warning(
                            f"Task cancelled, email "
                            f"{self.last_received_email.id if self.last_received_email else 'None'} "
                            f"not completed"
                        )
                    except Exception as e:
                        self.logger.exception(f"Failed to process email in {self.name}")
                    finally:
                        # 标记任务完成
                        self.inbox.task_done()

                    # ✅ 邮件处理完成，恢复 history_worker
                    self.history_worker_task = asyncio.create_task(self._history_worker())
                    self.logger.info("✅ 邮件处理完成，恢复 history worker")

                except Exception as e:
                    self.logger.exception(f"Error in email_worker: {e}")
                    # 继续循环

        except asyncio.CancelledError:
            self.logger.info("📧 Email worker 已停止")
            raise

    async def _history_worker(self):
        """
        历史整理 Worker（独立任务，可被打断）

        职责：
        - 处理 pending_summaries_queue
        - 生成 event list（调用 LLM）
        - 持久化到数据库
        - 被 email_worker 打断时自动恢复

        特性：
        - 可被取消（CancelledError）
        - 被取消时放回当前 item 到队列头部
        - 每次处理完 sleep(1)（限流）
        """
        self.logger.info("🔄 History worker 已启动")

        try:
            while True:
                try:
                    # 🔄 检查队列
                    if not self.pending_summaries_queue:
                        await asyncio.sleep(2)  # 队列为空，等待
                        continue

                    # 获取待处理项
                    summary_item = self.pending_summaries_queue.pop(0)

                    try:
                        self.logger.info(
                            f"🔄 处理待总结项 "
                            f"(队列剩余: {len(self.pending_summaries_queue)})"
                        )

                        # 生成 event list（可能被取消）
                        events = await self._generate_event_list(summary_item)

                        # 持久化
                        if events:
                            await self._persist_event_list(events)

                        self.logger.info(f"✅ 已生成 {len(events)} 个事件")

                        # 限流：每次间隔1秒
                        await asyncio.sleep(1)

                    except asyncio.CancelledError:
                        # ⚠️ 被取消（email_worker 来邮件了）
                        self.logger.info("⚠️ History worker 被取消（邮件打断）")
                        # 把当前 item 放回队列头部
                        self.pending_summaries_queue.insert(0, summary_item)
                        raise  # 重新抛出，结束任务

                except Exception as e:
                    self.logger.warning(f"❌ 处理失败: {e}")
                    # 继续处理下一个

        except asyncio.CancelledError:
            # 最外层捕获（确保任务被正确取消）
            self.logger.info("🛑 History worker 已停止")
            raise

    async def _generate_event_list(self, summary_item: dict) -> List[Dict]:
        """
        生成事件列表

        Args:
            summary_item: 待总结的消息块
                - messages: List[Dict]
                - timestamp: float
                - agent_name: str
                - run_label: str

        Returns:
            List[Dict]: [{"event": str, "entities": List[str]}]
        """
        from datetime import datetime
        from ..skills.memory.parser_utils import events_list_parser
        from ..utils.token_utils import format_conversation_messages

        prompt = f"""
# Role
你是一个高维度的**对话事实提取者**。你的任务不是简单的总结，而是从对话历史中**提取独立的、自包含的原子事实**

# 核心原则

**自包含**：无代词，无指代，独立存在
**原子化**：描述一个实体的一个状态跃迁
**永久性**：有长期价值，不过时
**对话相关**: 甄别对话本身的事实和事件，而非对话所涉及讨论的事实事件 

# 提取流程

0. **相关性识别**: 只关注对话涉及的重要事实和事件
1. **识别实体**：提取对话涉及的主要实体名，即事件的“主语”和“宾语”,并且只保留主干，例如“财务经理张三”，应该识别为“张三”
2. **提取跃迁**：创建、变化、连接、属性获得
3. **消歧去噪**：还原代词，剔除过程性信息

# 输出格式

在 `[EVENTS]` section 下输出 Markdown 格式：

```
[EVENTS]
# 事件1描述文本（尽量包含who what when)
实体1, 实体2, 实体3

# 事件2描述文本（尽量包含who what when)
实体A, 实体B

# 事件3描述文本（尽量包含who what when)
实体X
```
如果没有事件，输出：
```
[EVENTS]
NO EVENTS
```


**规则**：
- 每个事件用标题（`# `）
- 事件描述：具体、客观、无代词
- 实体列表：标题下方，逗号或换行分隔
- 数量：由你判断，宁缺毋滥


# Conversation History
{format_conversation_messages(summary_item['messages'])}

Extract facts now.
"""

        # 使用 think_with_retry 获取 events
        result = await self.cerebellum.backend.think_with_retry(
            initial_messages=prompt,
            parser=events_list_parser,
            max_retries=2
        )

        return result  # List[Dict]: [{"event": str, "entities": List[str]}]

    async def _persist_event_list(self, events: List[Dict]):
        """
        持久化事件列表到 Timeline

        Args:
            events: List[Dict] with keys: {"event": str, "entities": List[str]}
        """
        if not events:
            return

        from ..skills.memory.storage import append_timeline_events

        # 获取上下文信息
        workspace_root = self._workspace_root
        agent_name = self.name
        
        try:
            await append_timeline_events(
                workspace_root=workspace_root,
                agent_name=agent_name,
                task_id= self.current_task_id,
                events=events  # 直接传递事件对象列表
            )
            self.logger.info(f"💾 成功持久化 {len(events)} 个事件到 Timeline")
        except Exception as e:
            self.logger.error(f"❌ 持久化事件失败: {e}", exc_info=True)

    # ==================== 🆕 双 Worker 模型结束 ====================






    
    def dump_state(self) -> Dict:
        """生成当前 Agent 的完整快照"""

        # 1. 提取收件箱里所有未读邮件
        # Queue 没法直接序列化，得把东西取出来变成 List
        inbox_content = []
        while not self.inbox.empty():
            email = self.inbox.get_nowait()
            inbox_content.append(asdict(email)) # Email 也需要 to_dict
            self.inbox.task_done()

        # 额外检查：如果保存时正在处理某封信，把它塞回 Inbox 的头部！
        # 这样下次启动时，Agent 会重新处理这封信，相当于"断点重试"
        if self.last_received_email and not self.last_email_processed:
             inbox_content.insert(0, asdict(self.last_received_email))

        return {
            "name": self.name,
            "inbox": inbox_content,
            # Session 数据已经在 SessionManager 中自动持久化，不需要在这里保存
            # 如果是 Planner，它会有额外的 project_state，
            # 可以通过 hasattr 检查或者子类覆盖 dump_state
            "extra_state": getattr(self, "project_state", None)
        }

    def load_state(self, snapshot: Dict):
        """从快照恢复现场（Lazy Load：不加载 sessions）"""
        # 1. 恢复收件箱
        for email_dict in snapshot["inbox"]:
            # 假设 Email 类有 from_dict
            email = Email(**email_dict)
            self.inbox.put_nowait(email)

        # 2. Lazy Load: Sessions 将在需要时从磁盘加载（通过 SessionManager）
        # 3. 恢复额外状态 (Planner)
        if snapshot.get("extra_state"):
            self.project_state = snapshot["extra_state"]


    def _resolve_real_path(self, filename: str) -> Path:
        """
        解析文件名并返回真实的绝对路径
        
        Args:
            filename: 可能是绝对路径、相对路径或单个文件名
            
        Returns:
            解析后的绝对路径
            
        Raises:
            FileNotFoundError: 文件未找到
            ValueError: 路径超出 workspace_root 范围
        """
        from pathlib import Path
        
        # 转换为 Path 对象
        input_path = Path(filename)
        
        # 情况1: 处理绝对路径
        if input_path.is_absolute():
            try:
                # 检查是否在 workspace_root 范围内
                resolved_path = input_path.resolve()
                workspace_root = Path(self.workspace_root).resolve()
                
                # 检查路径是否在 workspace_root 下
                if not str(resolved_path).startswith(str(workspace_root)):
                    raise ValueError(f"Path {filename} is outside workspace_root")
                    
                # 检查文件是否存在
                if not resolved_path.exists():
                    raise FileNotFoundError(f"File not found: {filename}")
                    
                return resolved_path
                
            except Exception as e:
                raise ValueError(f"Invalid absolute path: {filename}") from e
        
        # 情况2: 处理相对路径
        # 判断是否是单个文件名（不包含路径分隔符）
        is_single_filename = '/' not in str(input_path) and '\\' not in str(input_path)
    
        # 定义搜索顺序的函数
        def try_resolve_in_workspace(workspace: Path) -> Optional[Path]:
            """在指定工作区中解析路径"""
            if not workspace:
                return None
                
            try:
                # 对于单个文件名，需要递归搜索
                if is_single_filename:
                    # 在工作区中递归搜索文件
                    for found_file in workspace.rglob(filename):
                        if found_file.is_file():
                            return found_file.resolve()
                else:
                    # 对于带路径的相对路径，直接解析
                    candidate = (workspace / input_path).resolve()
                    if candidate.exists() and candidate.is_file():
                        return candidate
                        
            except Exception:
                pass
                
            return None
        
        # 按优先级顺序尝试解析
        # 1. 先尝试共享工作区
        resolved = try_resolve_in_workspace(self.current_workspace)
        if resolved:
            return resolved
        
        # 2. 再尝试私有工作区
        resolved = try_resolve_in_workspace(self.private_workspace)
        if resolved:
            return resolved
        
        # 3. 如果都没找到，抛出异常
        raise FileNotFoundError(f"File not found in any workspace: {filename}")

    # ==========================================
    # Session Context 管理
    # ==========================================

    def get_session_context(self):
        """
        获取当前session的context

        Returns:
            SessionContext: session context 对象（可持久化）
        """
        return self._session_context

    async def set_session_context(self, context: dict):
        """
        设置当前session的context（完全替换）

        Args:
            context: 要设置的context字典
        """
        # 清空并更新
        self._session_context.clear()
        await self._session_context.update(**context)

    async def update_session_context(self, **kwargs):
        """
        更新当前session的context（部分更新/合并）

        注意：此方法会自动保存context到磁盘（通过 SessionContext 自动持久化）

        Args:
            **kwargs: 要更新的context字段

        Example:
            await self.update_session_context(
                research_title="AI Safety",
                current_step="planning"
            )
        """
        # 委托给 SessionContext.update()（会自动持久化）
        await self._session_context.update(**kwargs)
        self.logger.debug(f"💾 Updated session context: {list(kwargs.keys())}")

    async def clear_session_context(self):
        """清除当前session的context"""
        # 清空并持久化
        self._session_context.clear()
        await self._session_context.update()  # 触发持久化
        self.logger.debug(f"💾 Cleared session context")

    def get_session_folder(self) -> Optional[str]:
        """
        获取当前session的文件夹路径

        Returns:
            str: session 文件夹的绝对路径，如果不存在返回 None
        """
        return getattr(self, 'current_session_folder', None)

    # ==========================================
    # Transient Context（非持久化内存数据）
    # ==========================================

    def get_transient(self, key: str, default=None):
        """
        从transient context获取值（非持久化）

        Transient context存储在session中，但不会保存到磁盘。
        适合存储复杂对象、临时数据等不需要持久化的内容。

        Args:
            key: 键名
            default: 默认值（如果键不存在）

        Returns:
            存储的值，或默认值

        Example:
            # 获取复杂对象
            notebook = self.get_transient("notebook")
            if not notebook:
                notebook = Notebook()
                self.set_transient("notebook", notebook)
        """
        if not self.current_session:
            return default

        transient_ctx = self.current_session.get("transient_context", {})
        return transient_ctx.get(key, default)

    def set_transient(self, key: str, value: any):
        """
        设置transient context中的值（非持久化）

        用途：
        - 存储复杂对象（class实例）
        - 临时计算结果
        - 缓存数据
        - 任何不需要持久化的数据

        Args:
            key: 键名
            value: 值（可以是任意Python对象）

        Example:
            # 存储复杂对象
            parser = CustomParser()
            self.set_transient("parser", parser)

            # 存储缓存
            self.set_transient("cache", {})

        Note:
            - 数据不会保存到磁盘
            - 跟随session自动切换
            - agent重启后数据丢失
        """
        if not self.current_session:
            self.logger.warning("No active session to set transient data")
            return

        if "transient_context" not in self.current_session:
            self.current_session["transient_context"] = {}

        self.current_session["transient_context"][key] = value
        self.logger.debug(f"💾 Set transient: {key}")

    # ==========================================
    # 通用 Actions
    # ==========================================


    @classmethod
    def shutdown_all_docker_containers(cls):
        """系统退出时停止所有 Agent 容器"""
        import docker
        from docker.errors import DockerException

        try:
            client = docker.from_env()
            containers = client.containers.list(filters={"name": "agent_"})

            for container in containers:
                try:
                    container.stop(timeout=3)
                    print(f"🛑 已停止容器: {container.name}")
                except Exception as e:
                    print(f"⚠️ 停止容器失败 {container.name}: {e}")

        except DockerException as e:
            print(f"⚠️ Docker 连接失败: {e}")
        except Exception as e:
            print(f"⚠️ 清理容器时出错: {e}")
