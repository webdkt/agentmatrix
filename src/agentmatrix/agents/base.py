import asyncio
from typing import Dict, Optional, Callable, List, Any, Tuple
from dataclasses import asdict
from ..core.message import Email
from ..core.events import AgentEvent
from ..core.action import register_action
from ..core.session_manager import SessionManager
import traceback
import inspect
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
import logging
from pathlib import Path
from .micro_agent import MicroAgent, Signal


# Agent 状态常量
class AgentStatus:
    IDLE = "IDLE"
    THINKING = "THINKING"
    WORKING = "WORKING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class BaseAgent(AutoLoggerMixin):
    _log_from_attr = "name"  # 日志名字来自 self.name 属性

    _custom_log_level = logging.DEBUG

    def __init__(self, profile, profile_path: str = None):
        self.name = profile["name"]
        self.description = profile["description"]
        self.profile_path = profile_path  # 配置文件路径（用于 ConfigService 定位）

        # persona 直接是字符串
        self.persona = profile.get("persona", "")

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

        self._status = AgentStatus.IDLE  # 🔧 私有变量，只能通过 update_status 修改
        from datetime import datetime

        self._status_since = datetime.now()  # 状态变化的时间

        # 📊 状态历史（最近 10 条，用于前端查询）
        self.status_history = []
        self._max_status_history = 10  # 🔧 扩展到 10 条

        self.last_received_email = None  # 最后收到的信
        self.post_office = None

        # Session Manager（延迟初始化）
        self.session_manager = None

        # 标准组件
        self.inbox = asyncio.Queue()

        # 事件回调 (Server 注入)
        self.async_event_callback: Optional[Callable] = None

        # Runtime 引用 (由 AgentMatrix 注入)
        self._runtime = None

        # ✨ 新架构：使用 action_registry 代替 actions_map
        self.action_registry = {}  # name -> bound_method (新架构)
        self.actions_meta = {}  # name -> metadata (给小脑看)
        self.current_session = None
        self.current_task_id = None
        self.current_user_session_id = None  # 🆕 当前用户会话ID（如果邮件来自User）

        # 🔧 广播消息的回调（由 runtime 注入）
        self._broadcast_message_callback = None

        # 扫描 BaseAgent 自身的 actions（不包含 skills）
        self._scan_all_actions()

        # 🔀 暂停/恢复机制
        self._paused = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # 初始状态为已设置（不阻塞）

        # 🛑 停止机制
        self._stopped = False
        self._stop_event = asyncio.Event()
        self._stop_event.set()  # 初始状态为已设置（不阻塞）

        # 💬 ask_user 机制（等待用户输入）
        self._pending_user_question = None  # 当前等待用户回答的问题
        self._user_input_future = None  # 用于等待用户输入的 Future

        # 🆕 双 Worker 模型（email_worker + history_worker）
        self.pending_summaries_queue = []  # 待总结的消息块队列
        self.email_worker_task = None  # email worker 引用
        self.history_worker_task = None  # history worker 引用

        # 🆕 Stop 机制
        self._execute_task = None  # 当前正在运行的 execute task
        self._is_stopping = False  # 是否正在停止

        # 🆕 信号驱动架构 — session 管理
        self.active_session_id: Optional[str] = None
        self.active_micro_agent: Optional[MicroAgent] = None
        self._session_task: Optional[asyncio.Task] = None
        self.waiting_emails: List[Email] = []  # 非 active session 的邮件暂存

        # 🐳 Container Session（延迟初始化）
        self.container_session = None

        # 🌐 浏览器适配器（懒启动，Agent 级共享资源）
        self._browser_adapter = None

        # 🆕 记录最后一次 top-level MicroAgent 执行的 system prompt
        self.last_system_prompt = None

        self.logger.info(f"Agent {self.name} 初始化完成")

        # ✨ 新架构：Skills 改为 Lazy Load（通过 SKILL_REGISTRY 自动发现）
        # 不再需要手动注册，移除 _register_new_skills() 方法

    def _init_container_session(self):
        """初始化 Container Session"""
        if self.runtime is None:
            raise RuntimeError("runtime 未注入，无法初始化 Container Session")

        if (
            not hasattr(self.runtime, "container_manager")
            or not self.runtime.container_manager
        ):
            raise RuntimeError("container_manager 未初始化，无法获取 Container Session")

        cm = self.runtime.container_manager

        # 确保用户存在（创建 Linux 用户和目录）
        cm.ensure_user(self.name)

        # 获取或创建 container session
        self.container_session = cm.get_container_session(self.name)
        self.logger.info(
            f"Container Session 初始化成功 (session_id: {self.container_session.session_id})"
        )

    async def switch_workspace(self, task_id: str) -> bool:
        """切换工作目录（通过 container session 执行命令）"""
        if self.container_session is None:
            raise RuntimeError("Container Session 未初始化")

        # 1. 在宿主机创建目录（使用 runtime.paths）
        task_dir = self.runtime.paths.get_agent_work_files_dir(self.name, task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        # 2. 在容器内更新软链接（Agent 用户可以操作自己的软链接，不需要 root）
        # ~/current_task 是固定的软链接，指向当前任务目录
        # ln -sf 会自动覆盖已存在的软链接，不会删除目标目录内容
        cmd = f"ln -sf /data/agents/{self.name}/work_files/{task_id} ~/current_task && cd ~/current_task && readlink -f ~/current_task"
        self.logger.info(f"🔧 switch_workspace 命令: {cmd}")
        self.logger.info(f"🔧 宿主机目录存在: {task_dir.exists()}")
        exit_code, stdout, stderr = await asyncio.to_thread(
            self.container_session.execute, cmd
        )
        if exit_code != 0:
            self.logger.warning(f"switch_workspace 命令失败: exit={exit_code}, stderr={stderr}")
            return False

        self.logger.info(f"工作目录已切换: {self.name} -> {task_id}")
        self.logger.info(f"🔍 symlink 实际指向: {stdout.strip() if stdout else 'unknown'}")
        return True

    # ==================== 浏览器管理 ====================

    def get_browser(self):
        """
        获取浏览器适配器（懒创建，不启动浏览器进程）

        浏览器进程在首次 ensure_browser_started() 时启动。
        返回的 adapter 是 Agent 级共享资源，所有 MicroAgent 共用同一个 Chrome 实例。

        Returns:
            DrissionPageAdapter: 浏览器适配器实例
        """
        if self._browser_adapter is not None:
            return self._browser_adapter

        from ..core.browser.drission_page_adapter import DrissionPageAdapter

        profile_path = str(self.runtime.paths.get_browser_profile_dir(self.name))
        self._browser_adapter = DrissionPageAdapter(profile_path=profile_path)
        self.logger.info(f"🌐 浏览器适配器已创建 (profile: {profile_path})")
        return self._browser_adapter

    async def ensure_browser_started(self):
        """确保浏览器进程已启动（仅首次调用时实际启动）"""
        adapter = self.get_browser()
        if adapter.browser is None:
            await adapter.start(headless=False)
            self.logger.info("🌐 浏览器进程已启动")

    def deprecated_get_skill_prompt(
        self, skill_name: str, prompt_name: str, **kwargs
    ) -> str:
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
        return self.deprecated_load_skill_prompt(skill_name, prompt_name, **kwargs)

    def deprecated_load_skill_prompt(
        self, skill_name: str, prompt_name: str, **kwargs
    ) -> str:
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
            with open(prompt_file, "r", encoding="utf-8") as f:
                self._prompt_cache[cache_key] = f.read()

        template = self._prompt_cache[cache_key]

        # 直接渲染，缺变量会抛出 KeyError
        return template.format(**kwargs)

    @property
    def runtime(self):
        return self._runtime

    @runtime.setter
    def runtime(self, value):
        self._runtime = value  # 注意：必须用 _runtime，否则会递归
        if value is not None:
            # 初始化SessionManager（使用 runtime.paths）
            self.session_manager = SessionManager(
                agent_name=self.name, matrixpath=self.runtime.paths
            )

            # 🐳 初始化 Container Session（在 workspace_root 设置后）
            if self.container_session is None:
                self._init_container_session()

    @property
    def status(self):
        """只读属性：必须通过 update_status() 方法来修改"""
        return self._status

    # ========== 暂停/恢复机制 ==========

    async def pause(self):
        """暂停 Agent 执行"""
        if self._paused:
            self.logger.warning(f"Agent {self.name} 已经是暂停状态")
            return

        self._paused = True
        self._pause_event.clear()  # 清除事件，导致 await 会阻塞
        self.logger.info(f"⏸️ Agent {self.name} 已暂停")

        # 🔧 更新状态并推送
        self.update_status(new_status=AgentStatus.PAUSED, new_message="⏸️ Agent已暂停")

    async def resume(self):
        """恢复 Agent 执行（智能区分 stop / pause）"""
        if self._stopped:
            self._stopped = False
            self._stop_event.set()
            self.logger.info(f"▶️ Agent {self.name} 从停止状态恢复")
            self.update_status(new_status=AgentStatus.IDLE, new_message="▶️ Agent已从停止状态恢复")
        elif self._paused:
            self._paused = False
            self._pause_event.set()
            self.logger.info(f"▶️ Agent {self.name} 从暂停状态恢复")
            self.update_status(new_status=AgentStatus.IDLE, new_message="▶️ Agent已从暂停状态恢复")
        else:
            self.logger.warning(f"Agent {self.name} 未停止也未暂停")

    async def _checkpoint(self):
        """
        检查点：在 MicroAgent 的关键位置调用

        如果 Agent 处于停止或暂停状态，会挂起当前协程，直到恢复。
        """
        if self._stopped:
            self.logger.debug(f"🛑 Agent {self.name} 检查到停止，等待恢复...")
            await self._stop_event.wait()
            self.logger.debug(f"✅ Agent {self.name} 从停止状态恢复")
        if self._paused:
            self.logger.debug(f"🛑 Agent {self.name} 检查到暂停，等待恢复...")
            await self._pause_event.wait()
            self.logger.debug(f"✅ Agent {self.name} 已恢复执行")

    @property
    def is_paused(self) -> bool:
        """返回 Agent 是否暂停"""
        return self._paused

    # ========== Stop 机制 ==========

    def stop(self):
        """
        停止 Agent：停止当前 session，并且不再处理新邮件。

        需要调用 resume() 恢复。
        """
        self._stopped = True
        self._stop_event.clear()
        self._is_stopping = True

        # 取消所有 running action tasks
        if self.active_micro_agent:
            entries = dict(self.active_micro_agent._running_actions)
            self.active_micro_agent._running_actions.clear()
            for aid, info in entries.items():
                task = info["task"] if isinstance(info, dict) else info
                task.cancel()

        # 取消 session task
        if self._session_task and not self._session_task.done():
            self._session_task.cancel()
            self.logger.info(f"🛑 Agent {self.name} 已停止当前 session")

        self.update_status(new_status=AgentStatus.STOPPED, new_message="🛑 Agent已停止")

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
        from datetime import datetime

        # 🔧 记录旧状态并设置新状态
        old_status = self._status  # 保存旧状态
        # 3. 记录问题（给 API 查询）
        self._pending_user_question = question
        # 确保 current_user_session_id 不为 None（用于前端匹配会话）
        if not self.current_user_session_id and self.current_task_id:
            self.current_user_session_id = self.current_task_id
        # 🔧 更新状态会触发 AGENT_STATUS_UPDATE 增量推送（包含 pending_question）
        self.update_status(new_status=AgentStatus.WAITING_FOR_USER)

        # ✅ 发送邮件通知（如果 runtime 可用）
        task_id = self.current_task_id
        session_id = (
            self.current_session.get("session_id")
            if self.current_session
            else self.current_task_id
        )
        await self._send_ask_user_email(question, task_id, session_id)

        # 4. 创建 Future 并挂起
        self._user_input_future = asyncio.Future()

        self.logger.info(
            f"💬 向用户提问: {question[:50]}{'...' if len(question) > 50 else ''}"
        )

        try:
            # 发起提问前，先确保当前没有被暂停
            await self._checkpoint()

            # 🔧 修复：直接 await Future，不使用 wait_for（避免 Future 被取消）
            # 无限期挂起，直到前端调用 submit_user_input(answer) 触发 set_result(answer)
            answer = await self._user_input_future

            # 拿到答案后，再次检查是否在等待期间系统被暂停了
            await self._checkpoint()

            self.logger.info(
                f"✅ 收到用户回答: {answer[:50]}{'...' if len(answer) > 50 else ''}"
            )
            return answer

        finally:
            # 🔧 恢复状态
            self.update_status(new_status=old_status)
            self._pending_user_question = None
            self._user_input_future = None
            # 🔧 移除：状态清理（避免内存泄漏）
            # 注：不再需要显式清理，因为 finally 已经处理

    async def _send_ask_user_email(self, question: str, task_id: str, session_id):
        """
        发送 ask_user 邮件通知

        当 Agent 调用 ask_user 时，发送一封特殊邮件给用户，
        用户可以直接回复邮件来回答问题。

        Subject 格式：{agent_name}问：{question} #ASK_USER#{agent_name}#{agent_session_id}#

        Args:
            question: 问题内容
            task_id: 任务ID
        """
        if not self.runtime:
            self.logger.warning("⚠️ runtime 未注入，跳过 ask_user 邮件发送")
            return

        try:
            # 获取 Email Proxy Service
            email_proxy = self.runtime.email_proxy
            if not email_proxy:
                self.logger.warning(
                    "⚠️ Email Proxy Service 未找到，跳过 ask_user 邮件发送"
                )
                return

            # 直接调用 EmailProxyService 的专用方法
            await email_proxy.send_ask_user_email(
                agent_name=self.name, agent_session_id=session_id, question=question
            )

            self.logger.info(f"✅ 已发送 ask_user 邮件通知: {question[:50]}...")
        except Exception as e:
            self.logger.error(f"❌ 发送 ask_user 邮件失败: {e}", exc_info=True)

    async def submit_user_input(self, answer: str, session_id: str):
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
        if (
            not self.current_session
            or self.current_session.get("session_id") != session_id
        ):
            # not for this session
            return
        if not self._user_input_future or self._user_input_future.done():
            return

        self.logger.debug(
            f"📥 提交用户回答: {answer[:50]}{'...' if len(answer) > 50 else ''}"
        )

        # 设置结果，唤醒 Future
        self._user_input_future.set_result(answer)

    def get_status_snapshot(self) -> dict:
        """
        获取当前 Agent 的完整状态快照

        Returns:
            dict: Agent 完整状态，包含：
                - status: Agent 状态
                - pending_question: 等待中的用户问题
                - current_session_id: 当前会话 ID
                - current_task_id: 当前任务 ID
                - current_user_session_id: 当前用户会话 ID
                - status_history: 状态历史（最近 10 条）
        """
        user_session_id = self.current_user_session_id
        if not user_session_id and self.current_task_id:
            user_session_id = self.current_task_id

        return {
            "status": self._status,
            "pending_question": self._pending_user_question
            if hasattr(self, "_pending_user_question")
            else None,
            "current_session_id": self.current_session.get("session_id")
            if self.current_session
            else None,
            "current_task_id": self.current_task_id,
            "current_user_session_id": user_session_id,
            "status_history": self.status_history.copy(),
        }

    def update_status(self, new_status=None, new_message=None):
        """
        统一的状态更新接口（唯一修改 Agent 状态的方式）

        Args:
            new_status (str, optional): 新的 Agent 状态
            new_message (str, optional): 添加到状态历史的消息

        注意：此方法会触发增量状态推送
        """
        if new_status is not None:
            self._status = new_status
            from datetime import datetime

            self._status_since = datetime.now()
            self.logger.debug(f"📊 Status: {new_status}")

        if new_message is not None:
            from datetime import datetime

            entry = {
                "message": new_message,
                "timestamp": datetime.now().isoformat(),
                "user_session_id": self.current_user_session_id,
            }
            self.status_history.append(entry)
            if len(self.status_history) > self._max_status_history:
                self.status_history.pop(0)
            self.logger.debug(f"📊 Status history: {new_message}")

        if self._broadcast_message_callback:
            agent_info = self.get_status_snapshot()
            message = {
                "type": "AGENT_STATUS_UPDATE",
                "agent_name": self.name,
                "data": agent_info,
            }
            asyncio.create_task(self._send_message(message))

    async def _send_message(self, message):
        """异步发送消息（数据已经在调用方准备好）"""
        try:
            await self._broadcast_message_callback(message)
        except Exception as e:
            self.logger.warning(f"Failed to send status update: {e}")

    def get_current_status(self) -> dict:
        """获取当前状态（最新一条）"""
        if self.status_history:
            return self.status_history[-1]
        return {"message": "空闲", "timestamp": None}

    def get_status_history(self) -> list:
        """获取状态历史（最近 10 条）"""
        return self.status_history.copy()

    def _scan_all_actions(self):
        """
        扫描所有 actions（新架构）

        扫描自身及其父类的所有 @register_action 方法，
        并存储到 action_registry（已绑定的方法）。
        """
        import inspect

        for cls in self.__class__.__mro__:
            for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                if hasattr(method, "_is_action") and method._is_action:
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
                            "params": param_infos,
                        }

    @property
    def private_workspace(self) -> Path:
        """
        获取当前 session 的个人工作目录（如果不存在则自动创建）

        Returns:
            Path: 个人工作目录路径
        """
        if self.runtime is None:
            return None

        task_id = self.current_task_id or "default"
        # 通过 runtime.paths 获取路径
        workspace = self.runtime.paths.get_agent_work_files_dir(self.name, task_id)

        # 如果目录不存在，创建目录
        workspace.mkdir(parents=True, exist_ok=True)

        return workspace

    @property
    def current_workspace(self) -> Path:
        """
        获取当前 session 的共享工作目录（如果不存在则自动创建）

        Returns:
            Path: 共享工作目录路径
        """
        if self.runtime is None:
            return None

        task_id = self.current_task_id or "default"
        # 通过 runtime.paths 获取路径
        workspace = self.runtime.paths.workspace_dir / task_id / "shared"

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
            event = AgentEvent(event_type, self.name, self.status, content, payload)
            # 异步调用事件回调函数，将事件对象传递过去
            await self.async_event_callback(event)

    async def run(self):
        """主循环：启动 _main_loop + history_worker"""
        self.email_worker_task = asyncio.create_task(self._main_loop())
        self.history_worker_task = asyncio.create_task(self._history_worker())

        await self.emit("SYSTEM", f"{self.name} Started")

        try:
            await asyncio.gather(self.email_worker_task, return_exceptions=True)
        except asyncio.CancelledError:
            self.logger.info(f"{self.name} main loop cancelled")
            if self.email_worker_task:
                self.email_worker_task.cancel()
            if self.history_worker_task:
                self.history_worker_task.cancel()
            try:
                await asyncio.gather(
                    self.email_worker_task,
                    self.history_worker_task,
                    return_exceptions=True,
                )
            except Exception:
                pass
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error in {self.name} main loop")

    async def _main_loop(self):
        """
        主循环：收邮件 + 路由 + session 管理

        替代旧的 _email_worker + process_email。
        邮件不再阻塞处理，而是路由到 active session 的 signal_queue，
        或暂存到 waiting_emails 等待后续 session 处理。
        """
        self.logger.info("🔄 Main loop 已启动")

        try:
            while True:
                # 🛑 停止状态：阻塞等待 resume
                if self._stopped:
                    self.logger.info("🛑 Main loop 已停止，等待恢复...")
                    await self._stop_event.wait()
                    self.logger.info("▶️ Main loop 从停止状态恢复")

                # 暂停状态：阻塞等待 resume
                if self._paused:
                    self.logger.info("⏸️ Main loop 已暂停，等待恢复...")
                    await self._pause_event.wait()
                    self.logger.info("▶️ Main loop 已恢复")

                # 阻塞等待邮件
                email = await self.inbox.get()

                try:
                    self.last_received_email = email
                    await self._route_email(email)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.exception(f"Error routing email in {self.name}")
                finally:
                    self.inbox.task_done()

        except asyncio.CancelledError:
            # 取消 session task
            if self._session_task and not self._session_task.done():
                # 取消所有 running action tasks
                if self.active_micro_agent:
                    for aid, task in self.active_micro_agent._running_actions.items():
                        task.cancel()
                self._session_task.cancel()
                try:
                    await self._session_task
                except (asyncio.CancelledError, Exception):
                    pass
            self.logger.info("🔄 Main loop 已停止")
            raise

    async def _route_email(self, email: Email):
        """
        路由邮件到正确的 session。

        三种情况：
        1. 无 active session → activate session 并投递邮件
        2. active session + 邮件属于同一 session → 投递到 signal_queue
        3. active session + 邮件属于不同 session → 暂存到 waiting_emails
        """
        # 解析 session
        session = await self.session_manager.get_session(email)
        session_id = session["session_id"]

        # 更新 recipient_session_id
        if email.recipient_session_id is None:
            await self.post_office.update_email_receiver_session(
                email_id=email.id,
                recipient_session_id=session_id,
                receiver_name=self.name,
            )

        if self.active_session_id is None:
            # 情况 1：无 active session → activate
            await self._activate_session(session, email)
        elif self.active_session_id == session_id:
            # 情况 2：同一 session → 投递 batch 信号
            if self.active_micro_agent:
                email_text = f"[新邮件] 来自 {email.sender}: {email.subject}\n{email.body}"
                self.active_micro_agent.signal_queue.put_nowait(
                    Signal(type="email", payload={
                        "text": email_text,
                        "email_ids": [email.id]
                    })
                )
            self.logger.debug(f"📧 邮件路由到 active session {session_id[:8]}")
        else:
            # 情况 3：不同 session → 暂存
            self.waiting_emails.append(email)
            self.logger.debug(
                f"📧 邮件暂存 (session {session_id[:8]} != active {self.active_session_id[:8]})"
            )

    async def _activate_session(self, session: dict, first_email: Email):
        """
        激活 session：创建 MicroAgent，投递首封邮件，启动 session task。
        """
        session_id = session["session_id"]
        self.active_session_id = session_id
        self.current_session = session
        self.current_task_id = session["task_id"]

        # 设置 current_user_session_id
        if self.runtime and first_email.sender == self.runtime.get_user_agent_name():
            self.current_user_session_id = first_email.sender_session_id
        else:
            self.current_user_session_id = None

        # 切换工作区
        if self.container_session is None:
            raise RuntimeError("Container Session 未初始化。")
        # 重建 container shell（deactivate 时已 stop，这里按需 start）
        if not self.container_session.is_alive():
            self.logger.info(f"🔌 重建 container shell: {self.container_session.session_id}")
            self.container_session.start()
        success = await self.switch_workspace(session["task_id"])
        if not success:
            raise RuntimeError(f"工作区切换失败: {session['task_id']}")

        # 准备 available_skills
        available_skills = self.profile.get("skills", [])
        for required in ["base", "email"]:
            if required not in available_skills:
                available_skills = [required] + available_skills

        # 创建 MicroAgent
        micro_agent = MicroAgent(
            parent=self, name=self.name, available_skills=available_skills
        )
        self.active_micro_agent = micro_agent

        # 首封邮件作为 batch signal 放入 queue（取代旧的 task 参数 + signal 双重路径）
        email_text = f"[新邮件] 来自 {first_email.sender}: {first_email.subject}\n{first_email.body}"
        micro_agent.signal_queue.put_nowait(Signal(
            type="email",
            payload={"text": email_text, "email_ids": [first_email.id]}
        ))

        # 启动 session task — task 为空，邮件通过 signal 进入
        self._session_task = asyncio.create_task(
            self._run_session(micro_agent, session)
        )
        self.logger.info(f"🚀 Session {session_id[:8]} 已激活")

    async def _run_session(self, micro_agent: MicroAgent, session: dict):
        """
        运行 session 的 MicroAgent，处理完成后的清理。
        """
        session_id = session["session_id"]
        try:
            result = await micro_agent.execute(
                run_label="Process Email",
                task="",  # 邮件通过 signal 进入，不再通过 task
                yellow_pages=self.post_office.yellow_page_exclude_me(self.name),
                session_manager=self.session_manager,
                session=session,
            )
        except asyncio.CancelledError:
            if self._is_stopping:
                self.logger.info(f"🛑 Session {session_id[:8]} 被 stop() 中断")
                if session.get("history"):
                    history = session["history"]
                    if history:
                        last = history[-1]
                        if last.get("role") == "assistant":
                            last["content"] = (
                                last.get("content", "").strip()
                                + "\n\n**执行中，用户要求中止**"
                            )
                        else:
                            history.append(
                                {"role": "assistant", "content": "**执行中，用户要求中止**"}
                            )
                try:
                    await self.session_manager.save_session(session)
                except Exception as e:
                    self.logger.warning(f"Failed to save session on stop: {e}")
                self._is_stopping = False
            else:
                raise
        except Exception as e:
            self.logger.error(f"❌ Session {session_id[:8]} 出错: {e}")
            user_name = self.runtime.get_user_agent_name() if self.runtime else "User"
            try:
                await micro_agent.send_internal_mail(
                    to=user_name,
                    subject=f"⚠️ {self.name} 执行出错",
                    body=f"在处理您的邮件时发生错误：\n\n{str(e)}\n\n请检查后回复「继续」以便继续执行。",
                )
            except Exception as e2:
                self.logger.error(f"发送错误通知邮件失败: {e2}")
        finally:
            await self._deactivate_session(session)

    async def _deactivate_session(self, session: dict):
        """
        停用 session：保存 session，清理 active 状态，处理下一个 waiting email。
        """
        session_id = session.get("session_id", "unknown")

        # 保存 session
        session["last_sender"] = self.name
        try:
            await self.session_manager.save_session(session)
        except Exception as e:
            self.logger.warning(f"Failed to save session on deactivate: {e}")

        # 断开 container shell（下次 activate 时重建，避免残留命令跨 session 干扰）
        if self.container_session and self.container_session.is_alive():
            self.logger.debug(f"🔌 断开 container shell: {self.container_session.session_id}")
            self.container_session.stop()

        # 清理 active 状态
        self.active_session_id = None
        self.active_micro_agent = None
        self._session_task = None
        self._execute_task = None
        if not self._is_stopping:
            self.update_status(new_status=AgentStatus.IDLE)

        self.logger.info(f"✅ Session {session_id[:8]} 已停用")

        # 非 stop 状态：自动处理 waiting emails
        # stop 状态下不 pick，等 resume 后 _main_loop 自然恢复
        if not self._stopped and self.waiting_emails:
            next_email = self.waiting_emails.pop(0)
            self.logger.info(f"📬 处理下一个 waiting email")
            try:
                await self._route_email(next_email)
            except Exception as e:
                self.logger.exception(f"Error routing waiting email: {e}")

    async def _history_worker(self):
        """
        历史整理 Worker（已暂停，等待后续改造）
        """
        try:
            while True:
                await asyncio.sleep(2)
                continue
        except asyncio.CancelledError:
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
        from ..utils.token_utils import format_session_messages

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


# Session History
{format_session_messages(summary_item["messages"])}

Extract facts now.
"""

        # 使用 think_with_retry 获取 events
        result = await self.cerebellum.backend.think_with_retry(
            initial_messages=prompt, parser=events_list_parser, max_retries=2
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

        if self.runtime is None:
            self.logger.error("❌ runtime 未注入，无法持久化事件")
            return

        # 获取上下文信息
        agent_name = self.name

        try:
            await append_timeline_events(
                workspace_root=str(self.runtime.paths.workspace_dir),
                agent_name=agent_name,
                task_id=self.current_task_id,
                events=events,  # 直接传递事件对象列表
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
            inbox_content.append(asdict(email))  # Email 也需要 to_dict
            self.inbox.task_done()

        return {
            "name": self.name,
            "inbox": inbox_content,
            # Session 数据已经在 SessionManager 中自动持久化，不需要在这里保存
            # 如果是 Planner，它会有额外的 project_state，
            # 可以通过 hasattr 检查或者子类覆盖 dump_state
            "extra_state": getattr(self, "project_state", None),
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

    def deprecated_resolve_real_path(self, filename: str) -> Path:
        """
        解析文件名并返回真实的绝对路径

        Args:
            filename: 可能是绝对路径、相对路径或单个文件名

        Returns:
            解析后的绝对路径

        Raises:
            FileNotFoundError: 文件未找到
            ValueError: 路径超出 workspace 范围
        """
        from pathlib import Path

        if self.runtime is None:
            raise RuntimeError("runtime 未注入，无法解析路径")

        # 转换为 Path 对象
        input_path = Path(filename)

        # 获取 workspace 路径
        workspace_root = self.runtime.paths.workspace_dir.resolve()

        # 情况1: 处理绝对路径
        if input_path.is_absolute():
            try:
                # 检查是否在 workspace 范围内
                resolved_path = input_path.resolve()

                # 检查路径是否在 workspace 下
                if not str(resolved_path).startswith(str(workspace_root)):
                    raise ValueError(f"Path {filename} is outside workspace")

                # 检查文件是否存在
                if not resolved_path.exists():
                    raise FileNotFoundError(f"File not found: {filename}")

                return resolved_path

            except Exception as e:
                raise ValueError(f"Invalid absolute path: {filename}") from e

        # 情况2: 处理相对路径
        # 判断是否是单个文件名（不包含路径分隔符）
        is_single_filename = "/" not in str(input_path) and "\\" not in str(input_path)

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

    def preview_system_prompt(
        self,
        yellow_pages: Optional[str] = None,
        available_skills: Optional[List[str]] = None,
    ) -> str:
        """
        预览 System Prompt（不执行任务）

        用于调试或查看 Agent 配置后的完整 prompt，
        不需要实际运行任务就能看到 prompt 长什么样。

        Args:
            yellow_pages: 黄页信息（其他 Agent 列表）。
                如果为 None，使用默认空字符串。
            available_skills: 可用的 skill 列表。
                如果为 None，使用 profile 中的 skills 配置。

        Returns:
            str: 完整的 system prompt 文本

        Example:
            >>> agent = get_agent("alice")
            >>> # 预览默认配置的 prompt
            >>> prompt = agent.preview_system_prompt()
            >>> print(prompt)
            >>> # 预览指定黄页的 prompt
            >>> yellow_pages = "Bob - 邮件专家\\nCharlie - 数据分析师"
            >>> prompt = agent.preview_system_prompt(yellow_pages=yellow_pages)
        """
        # 准备 available_skills
        if available_skills is None:
            available_skills = self.profile.get("skills", [])

        # 自动注入基础 skills（与 process_email 逻辑一致）
        for required in ["base", "email"]:
            if required not in available_skills:
                available_skills = [required] + available_skills

        # 创建临时 MicroAgent
        temp_micro = MicroAgent(
            parent=self, name=self.name, available_skills=available_skills
        )

        # 设置 yellow_pages（如果提供）
        if yellow_pages is not None:
            temp_micro.yellow_pages = yellow_pages

        # 构建 prompt（会自动同步到 temp_micro.system_prompt）
        temp_micro._build_system_prompt()

        # 返回构建的 prompt
        return temp_micro.system_prompt

    # ==========================================
    # 通用 Actions
    # ==========================================
