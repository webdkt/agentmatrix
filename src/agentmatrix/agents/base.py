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

        # 加载其他 prompts（如 task_prompt）
        self.other_prompts = profile.get("prompts", {})

        # Prompt 模板缓存
        self._prompt_cache = {}

        self.profile = profile
        self.instruction_to_caller = profile.get("instruction_to_caller","")
        self.backend_model = profile.get("backend_model", "default_llm")

        # 🆕 新架构：读取 skills 配置
        self.skills = profile.get("skills", [])
        self.brain = None
        self.cerebellum = None
        self.vision_brain = None  # 🆕 视觉大模型（支持图片理解的LLM）

        self.status = "IDLE"
        self.last_received_email = None #最后收到的信
        self._workspace_root = None
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
        self.current_user_session_id = None

        # 扫描 BaseAgent 自身的 actions（不包含 skills）
        self._scan_all_actions()

        # working_context（指向 private_workspace）
        # 注意：此时 private_workspace 可能还是 None（因为没有 user_session_id）
        # 会在 process_email 中更新
        self.working_context = None

        self.logger.info(f"Agent {self.name} 初始化完成")

        # ✨ 新架构：Skills 改为 Lazy Load（通过 SKILL_REGISTRY 自动发现）
        # 不再需要手动注册，移除 _register_new_skills() 方法

    def _update_working_context(self):
        """
        更新 working_context，指向 private_workspace

        应该在 process_email 开始时调用，因为 private_workspace 依赖 current_user_session_id
        """
        from ..core.working_context import WorkingContext

        if self.private_workspace:
            self.working_context = WorkingContext(
                base_dir=str(self.private_workspace),
                current_dir=str(self.private_workspace)
            )
            self.logger.debug(f"Updated working_context: {self.working_context.base_dir}")
        else:
            self.working_context = None

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
        return template.format(**kwargs)

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
                workspace_root=value
            )

            # 🆕 初始化 SKILLS 目录（用于 MD Document Skills）
            from ..skills.registry import SKILL_REGISTRY
            from pathlib import Path

            skills_dir = Path(value) / "SKILLS"
            skills_dir.mkdir(parents=True, exist_ok=True)

            # 设置到 SKILL_REGISTRY（供 MD skill 加载使用）
            SKILL_REGISTRY.set_workspace_skills_dir(skills_dir)

            self.logger.info(f"✅ SKILLS 目录已初始化: {skills_dir}")



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
            Path: 个人工作目录路径，格式为 workspace_root / user_session_id / agents / agent_name
        """
        if not self.workspace_root:
            #raise ValueError("workspace_root is not set")
            return None

        user_session_id = self.current_user_session_id or "default"
        workspace = Path(self.workspace_root) / user_session_id / "agents" / self.name

        # 如果目录不存在，创建目录
        workspace.mkdir(parents=True, exist_ok=True)

        return workspace

    @property
    def current_workspace(self) -> Path:
        """
        获取当前 session 的共享工作目录（如果不存在则自动创建）

        Returns:
            Path: 共享工作目录路径，格式为 workspace_root / user_session_id / shared
        """
        if not self.workspace_root:
            #raise ValueError("workspace_root is not set")
            return None

        user_session_id = self.current_user_session_id or "default"
        workspace = Path(self.workspace_root) / user_session_id / "shared"

        # 如果目录不存在，创建目录
        workspace.mkdir(parents=True, exist_ok=True)

        return workspace



    def _generate_tools_prompt(self):
        """生成给 SLM 看的 Prompt"""
        prompt = ""
        for name, meta in self.actions_meta.items():
            # 这里直接把 Schema dump 成 json 字符串
            # 这种格式是目前开源模型微调 Function Calling 最常用的格式
            schema_str = json.dumps(meta["params"], ensure_ascii=False)
            prompt += textwrap.dedent(f"""
                ### Action name: {name} ###
                Description:
                    {meta['description']}

                ACTION JSON DEFINITION: 
                    {schema_str}

            """)
            
        return prompt

    
    
    def get_introduction(self):
        """
        生成给其他 Agent 看的说明书 (Protocol Description)
        这是之前 AgentManifest.to_prompt() 的逻辑
        """
        
        return (
            f"--- Agent: {self.name} ---\n"
            f"Description: {self.description}\n"
            f"Instruction: {self.instruction_to_caller}\n"
            f"--------------------------\n"
        )
    
    
        
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
        await self.emit("SYSTEM", f"{self.name} Started")
        while True:
            try:
                email = await asyncio.wait_for(self.inbox.get(), timeout=3)
                try:
                    self.last_received_email = email
                    self.last_email_processed = False
                    await self.process_email(email)
                    # 只在正常完成后标记为 True
                    self.last_email_processed = True
                except asyncio.CancelledError:
                    # 任务被取消，保持 last_email_processed = False
                    self.logger.warning(f"Task cancelled, email {self.last_received_email.id if self.last_received_email else 'None'} not completed")
                except Exception as e:
                    self.logger.exception(f"Failed to process email in {self.name}")
                finally:
                    # 无论成功、失败还是取消，都要标记任务完成
                    self.inbox.task_done()
            except asyncio.TimeoutError:
                # 可选：定期任务、健康检查等
                continue
            except asyncio.CancelledError:
                # 主循环被取消，退出
                self.logger.info(f"{self.name} main loop cancelled")
                break
            except RuntimeError as e:
                # Event loop 已关闭，优雅退出
                if "Event loop is closed" in str(e) or "no running event loop" in str(e):
                    self.logger.info(f"{self.name} event loop closed, exiting")
                    break
                self.logger.exception(f"Runtime error in {self.name} main loop")
            except Exception as e:
                self.logger.exception(f"Unexpected error in {self.name} main loop")
                try:
                    await asyncio.sleep(1)  # 防止异常风暴
                except RuntimeError:
                    # Event loop 可能已关闭
                    break

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
        self.current_user_session_id = session["user_session_id"]

        # 更新 working_context（指向 private_workspace）
        self._update_working_context()

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
                session["user_session_id"] /
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

        # 自动注入 base skill（BaseAgent 必备）
        # 确保 BaseAgent 始终拥有基础 actions（send_email, rest_n_wait, take_a_break, get_current_datetime）
        if "base" not in available_skills:
            available_skills = ["base"] + available_skills

        # 4. 执行 Micro Agent
        # 每次创建新的 MicroAgent（使用最新的 working_context）
        micro_core = MicroAgent(
            parent=self,
            working_context=self.working_context,  # ← 传入最新的 working_context
            name=self.name,
            available_skills=available_skills  # 🆕 传递可用技能列表
        )
        persona = self.get_persona()


        result = await micro_core.execute(
            run_label= 'Process Email',
            persona=persona,
            task=task,
            max_steps=100,
            # initial_history=session["history"],  # ← 不再需要，session 会传递
            session=session,  # ← 传递 session
            session_manager=self.session_manager,  # ← 传递 session_manager
            yellow_pages=self.post_office.yellow_page_exclude_me(self.name),
            exit_actions=["rest_n_wait"]  # rest_n_wait 会直接退出，不执行 action 逻辑
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

    def _get_llm_context(self, session: dict) -> List[Dict]:
        """
        [多态的关键]
        Worker: 返回完整的 history。
        Planner: 将重写此方法，返回 State + Latest Message。
        """
        return session["history"]






    def get_snapshot(self):
        """
        核心可观察性方法：返回 Agent 当前的完整状态快照
        """
        return {
            "name": self.name,
            "is_alive": True,
            "inbox_depth": self.inbox.qsize()
        }
    
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

    @register_action(
        description="所有任务都已完成。当你觉得没有其他要做的，就必须调用此 action。",
        param_infos={
            "result": "最终结果的描述（可选）"
        }
    )
    async def all_finished(self, result: str = None) -> Any:
        """
        [TERMINAL ACTION] 完成任务并返回最终结果

        这是 BaseAgent 提供的通用 all_finished action。
        子类可以覆盖此方法以实现自定义的完成逻辑。

        Args:
            result: 任务结果描述（可选）

        Returns:
            Any: 返回给调用者的结果
                 - 如果提供 result：返回字符串
                 - 如果不提供：返回空字典
        """
        if result:
            return result
        return {}
