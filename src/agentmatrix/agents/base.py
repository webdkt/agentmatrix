import asyncio
from typing import Dict, Optional, Callable, List, Any
from ..core.message import Email
from ..core.events import AgentEvent
from ..core.action import register_action
from ..core.session_manager import SessionManager
import traceback
from dataclasses import asdict
import inspect
import json
import textwrap
from ..core.log_util import AutoLoggerMixin
import logging
from pathlib import Path

class BaseAgent(AutoLoggerMixin):
    _log_from_attr = "name" # 日志名字来自 self.name 属性

    _custom_log_level = logging.DEBUG 
    
    # 默认在 process_email 中始终可用的 actions（不需要在 YAML 中配置）
    DEFAULT_TOP_LEVEL_ACTIONS = ["rest_n_wait", "send_email"]
    
    def __init__(self, profile):
        self.name = profile["name"]
        self.description = profile["description"]
        self.system_prompt = profile["system_prompt"]  # 基本人设，从 YAML 加载
        self.profile = profile
        self.instruction_to_caller = profile.get("instruction_to_caller","")
        self.backend_model = profile.get("backend_model", "default_llm")

        # 配置 process_email 时可用的 top level actions
        # 如果不配置，则使用所有 actions（向后兼容）
        self.top_level_actions = profile.get("top_level_actions", None)
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

        self.actions_map = {} # name -> method
        self.actions_meta = {} # name -> metadata (给小脑看)
        self.current_session = None
        self.current_user_session_id = None

        self._scan_methods()

        # 创建内置 Micro Agent（用于执行）
        # 注意：brain 和 cerebellum 是外部注入的，所以这里先不创建
        # 会在第一次使用时延迟初始化
        self._micro_core = None

        self.logger.info(f"Agent {self.name} 初始化完成")

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

    def _get_micro_core(self):
        """
        获取或创建内置 Micro Agent

        Returns:
            MicroAgent: Micro Agent 实例
        """
        if self._micro_core is None:
            from .micro_agent import MicroAgent
            self._micro_core = MicroAgent(
                brain=self.brain,
                cerebellum=self.cerebellum,
                action_registry=self.actions_map,
                name=f"{self.name}",
                default_max_steps=100
            )
            self.logger.info(f"Micro Agent {self._micro_core.name} created")
        return self._micro_core
        

        

    def _scan_methods(self):
        """扫描并生成元数据"""
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if getattr(method, "_is_action", False):
                
                # 1. 提取基础信息
                desc = method._action_desc
                param_infos = method._action_param_infos
                
                
                
                self.actions_map[name] = method
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
            except Exception as e:
                self.logger.exception(f"Unexpected error in {self.name} main loop")
                await asyncio.sleep(1)  # 防止异常风暴

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

        # 3. 准备 available actions
        # 如果配置了 top_level_actions，则使用配置 + 默认 actions
        # 否则使用所有 actions（向后兼容）
        if self.top_level_actions is not None:
            # 合并配置的 actions 和默认 actions
            available_actions = list(set(self.top_level_actions + self.DEFAULT_TOP_LEVEL_ACTIONS))
            # 过滤掉实际不存在的 actions
            available_actions = [a for a in available_actions if a in self.actions_map]
            self.logger.debug(f"Using configured top_level_actions: {available_actions}")
        else:
            # 向后兼容：使用所有 actions
            available_actions = list(self.actions_map.keys())
            self.logger.debug(f"Using all actions (backward compatible): {available_actions}")

        # 4. 执行 Micro Agent
        # 传入 session（MicroAgent 会自动保存 history）
        micro_core = self._get_micro_core()

        result = await micro_core.execute(
            persona=self.system_prompt,
            task=task,
            available_actions=available_actions,
            max_steps=100,
            # initial_history=session["history"],  # ← 不再需要，session 会传递
            session=session,  # ← 传递 session
            session_manager=self.session_manager,  # ← 传递 session_manager
            yellow_pages=self.post_office.yellow_page_exclude_me(self.name)
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

    def _add_message_to_history(self, email: Email):
        # 如果是新 Session，注入 System Prompt
        session = self.current_session
        if len(session["history"]) == 0:
            session["history"].append({"role": "system", "content": self.get_prompt()})

        # 注入用户/同事的邮件

        content =  "[INCOMING MAIL]\n"
        content+= f"{email}"
        session["history"].append({"role": "user", "content": content})

    def _add_intention_feedback_to_history(self, intention, action_name,  result=None):
        session = self.current_session
        # 把动作执行结果反馈给 LLM
        msg_body =  "[BODY FEEDBACK]\n"
        if result:

            msg_body +=f"Action: '{action_name}'\n"
            msg_body +=textwrap.dedent(f"""Result:
                {result}
            """)
        else:
            msg_body +=f" '{action_name}'\n"
        session["history"].append({"role": "assistant", "content": intention})
        session["history"].append({"role": "user", "content": msg_body})

    


    def _add_brain_intention_to_history(self, intention):
        session = self.current_session
        session["history"].append({"role": "assistant", "content": intention})

    def _add_question_to_brain(self, question):
        session = self.current_session

        session["history"].append({"role": "user", "content": f"[INTERNAL QUERY]: {question}\n"})



    def _get_llm_context(self, session: dict) -> List[Dict]:
        """
        [多态的关键]
        Worker: 返回完整的 history。
        Planner: 将重写此方法，返回 State + Latest Message。
        """
        return session["history"]

    @register_action(
        "检查当前日期和时间，你不知道日期和时间，如果需要日期时间信息必须调用此action", param_infos={}
    )
    async def get_current_datetime(self):
        from datetime import datetime
        now = datetime.now()
        return now.strftime("%Y-%m-%d %H:%M:%S")

    
    @register_action(
        "休息一下，工作做完了，或者需要等待回信才能继续", 
        param_infos={
            
        }
    )
    async def rest_n_wait(self):
        # 什么都不做，直接返回
        pass

    @register_action(
        "Take a break，让身体恢复一下", 
        param_infos={
            
        }
    )
    async def take_a_break(self):
        # 什么都不做，直接返回
        await asyncio.sleep(60)
        return "Return from Break"
    

    

    @register_action(
        "发邮件给同事，这是和其他人沟通的唯一方式", 
        param_infos={
            "to": "收件人 (e.g. 'User', 'Planner', 'Coder')",
            "body": "邮件内容",
            "subject": "邮件主题 (可选，如果不填，系统会自动截取 body 的前20个字)"
        }
    )
    async def send_email(self, to, body, subject=None):
        # 构造邮件
        # 如果 发给 session 的 original_sender，则 in_reply_to = session.session_id
        # 如果 发给 其他同事，则检查 是不是 to 是不是 等于 self.last_email.sender
        # 如果是，则 in_reply_to = self.last_email.id
        # 否则，in_reply_to = session.session_id
        session = self.current_session
        last_email = self.last_received_email
        in_reply_to = session["session_id"]
        if to == last_email.sender:
            in_reply_to = last_email.id
        if not subject:
            # 如果 body 很短，直接用 body 做 subject
            # 如果 body 很长，截取前 20 个字 + ...
            clean_body = body.strip().replace('\n', ' ')
            subject = clean_body[:20] + "..." if len(clean_body) > 20 else clean_body
        msg = Email(
            sender=self.name,
            recipient=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
            user_session_id=session["user_session_id"]
        )

        await self.post_office.dispatch(msg)

        # 更新 reply_mapping（自动保存到磁盘）
        await self.session_manager.update_reply_mapping(
            msg_id=msg.id,
            session_id=self.current_session["session_id"],
            user_session_id=session["user_session_id"]
        )

        return f"Email sent to {to}"

    

    


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

    async def _run_micro_agent(
        self,
        persona: str,
        task: str,
        available_actions: Optional[List[str]] = None,
        max_steps = None,
        max_time = None,
        exclude_actions: Optional[List[str]] = None,
        result_params: Optional[Dict[str, str]] = None,
        yellow_pages: Optional[str] = None
    ) -> Any:
        """
        运行一个 Micro Agent 来处理子任务

        这是 BaseAgent 中使用 Micro Agent 的便捷方法
        Micro Agent 继承 BaseAgent 的所有 actions（默认），是 BaseAgent 的临时"人格"

        Args:
            persona: 角色/身份描述（覆盖 BaseAgent 的 persona）
            task: 任务描述
            available_actions: 可用的 action 名称列表（None = 使用所有 BaseAgent 的 actions）
            max_steps: 最大步数
            exclude_actions: 要排除的 actions（默认排除等待类 actions）
            result_params: 返回值参数描述（可选），用于指定 finish_task 的参数结构
            yellow_pages: 黄页信息（可选），包含其他agent的描述和如何调用它们

        Returns:
            Any: Micro Agent 的执行结果
                 - 如果 result_params 为 None，返回字符串（向后兼容）
                 - 如果有 result_params，返回 Dict[str, Any]
                 - 如果出错或超时，返回 None 或 {"error": str}

        Example:
            # 使用所有 actions（默认）
            result = await self._run_micro_agent(
                persona="You are a code analysis expert...",
                task="Analyze the project structure",
                max_steps=30
            )

            # 指定部分 actions
            result = await self._run_micro_agent(
                persona="You are a researcher...",
                task="Research this topic",
                available_actions=["web_search", "read_file", "finish_task"],
                max_steps=20
            )

            # 使用结构化返回（新功能）
            result = await self._run_micro_agent(
                persona="You are a code reviewer...",
                task="Review this code",
                result_params={
                    "summary": "审查总结",
                    "issues": "问题列表",
                    "score": "评分 (0-100)"
                }
            )
            # result = {"summary": "...", "issues": [...], "score": 85}
        """
        from .micro_agent import MicroAgent

        # 默认排除等待类 actions（这些会导致 Micro Agent 无法正常返回）
        default_exclude = ["rest_n_wait", "take_a_break"]
        if exclude_actions:
            default_exclude.extend(exclude_actions)

        # 如果没有指定 available_actions，使用 BaseAgent 的所有 actions（排除等待类）
        if available_actions is None:
            available_actions = [
                action_name for action_name in self.actions_map.keys()
                if action_name not in default_exclude
            ]

        # 确保 all_finished 在列表中
        if "all_finished" not in available_actions:
            available_actions.append("all_finished")

        # 使用内置 Micro Agent（共享 _micro_core）
        # 子任务不需要恢复记忆，所以 initial_history=None
        result = await self._get_micro_core().execute(
            persona=persona,
            task=task,
            available_actions=available_actions,
            max_steps=max_steps,
            max_time = max_time,
            initial_history=None,  # 新对话，不需要恢复记忆
            result_params=result_params,  # 传递 result_params
            yellow_pages=yellow_pages  # 传递 yellow_pages
        )

        return result

    # ==========================================
    # Session Context 管理
    # ==========================================

    def get_session_context(self) -> dict:
        """
        获取当前session的context

        Returns:
            dict: session context字典，如果不存在返回空字典
        """
        if not hasattr(self, 'current_session') or not self.current_session:
            return {}
        return self.current_session.get("context", {})

    async def set_session_context(self, context: dict):
        """
        设置当前session的context（完全替换）

        Args:
            context: 要设置的context字典
        """
        if not hasattr(self, 'current_session') or not self.current_session:
            self.logger.warning("No active session to set context")
            return

        self.current_session["context"] = context

        # 自动保存到磁盘
        try:
            await self.session_manager.save_session(self.current_session)
            self.logger.debug(f"💾 Saved session context")
        except Exception as e:
            self.logger.warning(f"Failed to save session context: {e}")

    async def update_session_context(self, **kwargs):
        """
        更新当前session的context（部分更新/合并）

        注意：此方法会自动保存context到磁盘，但不保存history（性能优化）

        Args:
            **kwargs: 要更新的context字段

        Example:
            await self.update_session_context(
                research_title="AI Safety",
                current_step="planning"
            )
        """
        if not hasattr(self, 'current_session') or not self.current_session:
            self.logger.warning("No active session to update context")
            return

        if "context" not in self.current_session:
            self.current_session["context"] = {}

        # 合并更新
        self.current_session["context"].update(kwargs)

        # 只保存 context（不保存 history，性能优化）
        try:
            await self.session_manager.save_session_context_only(self.current_session)
            self.logger.debug(f"💾 Saved session context: {list(kwargs.keys())}")
        except Exception as e:
            self.logger.warning(f"Failed to save session context: {e}")

    async def clear_session_context(self):
        """清除当前session的context"""
        if not hasattr(self, 'current_session') or not self.current_session:
            self.logger.warning("No active session to clear context")
            return

        self.current_session["context"] = {}

        # 自动保存到磁盘
        try:
            await self.session_manager.save_session_context_only(self.current_session)
            self.logger.debug(f"💾 Cleared session context")
        except Exception as e:
            self.logger.warning(f"Failed to clear session context: {e}")

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

        这是 BaseAgent 提供的通用 finish_task action。
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
