import asyncio
from typing import Dict, Optional, Callable, List
from core.message import Email
from core.session import TaskSession
from core.events import AgentEvent
from core.action import register_action
import traceback
from dataclasses import asdict
import inspect
import json
import textwrap
from skills.filesystem import FileSkillMixin
from core.log_util import AutoLoggerMixin
import logging
from pathlib import Path

class BaseAgent(FileSkillMixin,AutoLoggerMixin):
    _log_from_attr = "name" # 日志名字来自 self.name 属性

    _custom_log_level = logging.DEBUG 
    def __init__(self, profile):
        self.name = profile["name"]
        self.description = profile["description"]
        self.prompt_template = profile.get("prompt_template", "base")
        self.full_prompt = profile["full_prompt"] 
        # full_prompt是 prompte loaded from prompate_template, 
        # 后面会和system_prompt合并，然后再替换其他变量生成最终的system prompt
        self.system_prompt = profile["system_prompt"] #system_prompt is actually persona prompt
        self.profile = profile
        self.instruction_to_caller = profile["instruction_to_caller"]
        self.backend_model = profile.get("backend_model", "default_llm")
        self.brain = None
        self.status = "IDLE"
        self.last_received_email = None #最后收到的信
        self.cerebellum = None 
        self.workspace_root = None
        self.post_office = None
        self.last_email_processed = True
    
        
        

        
        # 标准组件
        self.inbox = asyncio.Queue()
        #self.sessions = {}
        self.sessions: Dict[str, TaskSession] = {} # Key: Original Msg ID
        self.reply_mapping: Dict[str, str] = {}    # Key: Outgoing Msg ID -> Value: Session ID
        
        # 事件回调 (Server 注入)
        self.async_event_callback: Optional[Callable] = None

        self.actions_map = {} # name -> method
        self.actions_meta = {} # name -> metadata (给小脑看)
        self.current_session = None
        self.current_user_session_id = None

        self._scan_methods()
        
        self.logger.info(f"Agent {self.name} 初始化完成")
        

        

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
    def current_private_workspace(self) -> Path:
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

    def get_prompt(self):
        """生成给 LLM 的完整 Prompt"""
        prompt = self.full_prompt
        prompt =prompt.replace("{{ name }}", self.name)
        prompt =prompt.replace("{{ description }}", self.description)
        prompt =prompt.replace("{{ system_prompt }}", self.system_prompt)
        yellow_page = self.post_office.yellow_page_exclude_me(self.name)
        prompt =prompt.replace("{{ yellow_page }}", yellow_page)
        capabilities_menu = self.get_capabilities_summary()
        prompt = prompt.replace("{{ capabilities }}", capabilities_menu)
        return prompt

        

    def get_capabilities_summary(self) -> str:
        """
        生成给 Brain 看的能力清单 (Menu)。
        只包含 Action Name 和 Description，不包含 JSON 参数细节。
        """
        lines = []
        if not self.actions_meta:
            return "(No capabilities registered)"

        for name, meta in self.actions_meta.items():
            # 格式示例: - read_file: 读取文件内容。只读取文本文件。
            lines.append(f"- {name}: {meta['description']}")
            
        return "\n".join(lines)

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
                except Exception as e:
                    self.logger.exception(f"Failed to process email in {self.name}")
                finally:
                    self.inbox.task_done()
                    self.last_email_processed = True
            except asyncio.TimeoutError:
                # 可选：定期任务、健康检查等
                continue
            except Exception as e:
                self.logger.exception(f"Unexpected error in {self.name} main loop")
                await asyncio.sleep(1)  # 防止异常风暴

    async def process_email(self, email: Email):
        # 1. Session Management (Routing)
        self.logger.debug(f"New Email")
        self.logger.debug(str(email))
        session = self._resolve_session(email)
        self.current_session = session
        self.current_user_session_id = session.user_session_id
        #print(f"Prcessing email from {email.sender} , {email.subject}")
        
        
        # 2. Add incoming message to history (Input)
        self._add_message_to_history(email)
        
        # 3. The "Think-Act" Loop
        # 设置一个最大步数，防止 LLM 死循环自言自语
        MAX_STEPS = 100 
        step_count = 0

        async def ask_brain_clarification(question: str) -> str:
            # 1. 构造一个临时的 Context
            # 我们不希望把 Cerebellum 的琐碎问题污染到主 History 里
            # 所以我们 copy 一份当前的 history，附加上问题
            temp_messages = session.history.copy()
            
            # 2. 注入 System Prompt，告诉 Brain 现在是在回答小脑的质询
            
            
            temp_messages.append({"role": "user", "content": f"[INTERNAL QUERY]  {question} "})
            
            # 3. Brain 思考
            response = await self.brain.think(temp_messages)
            return response['reply']
        
        while step_count < MAX_STEPS:
            step_count += 1
            
            # A. Brain: Think (Context -> Intention)
            context = self._get_llm_context(session)
            
            intention = await self.brain.think(context)
            self.logger.debug(intention)
            
            intention = intention['reply']
            
            

            action_signal = None  
            #check if there's [ACTION SIGNAL] format in intention
            if "[ACTION SIGNAL]:" in intention:
                action_signal = intention.split("[ACTION SIGNAL]:",1)[1].strip()
            else:
                # 没有遵守格式，强制要求重写
                self._add_brain_intention_to_history(intention)
                self._add_question_to_brain("Action signal should begin with  `[ACTION SIGNAL]:`")
                continue
            
            
            
            # 2. Cerebellum 翻译
            manifest_str = self._generate_tools_prompt()
            contacts = self.post_office.get_contact_list(exclude = self.name)
            contacts = "\n".join(contacts)

            action_json = await self.cerebellum.negotiate(
                initial_intent=action_signal, 
                tools_manifest=manifest_str,
                contacts = contacts,
                brain_callback=ask_brain_clarification
            )
            
            
            
            
            action_name = action_json.get("action")
            self.logger.debug(f"{self.name} will do action: \n{action_name}")
            params = action_json.get("params", {})

            

            # 4. 查找方法
            method = self.actions_map.get(action_name)
            if not method:
                # 幻觉处理：Brain 编造了一个不存在的动作
                self._add_intention_feedback_to_history(intention, "Body is tired, need to take a break") #希望Brain会选择“Take a Break"!
                self.logger.error(f"Tried to do an unknown action: {action_name}")
                continue

            # 5. 执行方法 (Execution)
            try:
                # 获取动作类型
                
                
                if action_name != "rest_n_wait":
                    result = await method(**params)
                    self.logger.debug(f"{self.name} did action: \n{result}")
                    # 同步动作：把结果喂回给 Brain，继续循环
                    self._add_intention_feedback_to_history(intention, action_name, result)
                    #self.logger.debug(f"{self.current_session.history[:-2]}")
                    continue 
                    
                else:
                    #如果大脑输出了 rest_n_wait 的意图，我们就结束本次循环了，不用回答了，只要记录下它最后说的
                    self._add_brain_intention_to_history(intention)
                    self.logger.debug(f"{self.name} will rest and wait")
                    self.status = "WAITING" #wait for email reply
                    break
                                        
            except Exception as e:
                # 执行报错：把 Python 异常喂回给 Brain
                # Brain 看到报错后，可能会决定 "google search error" 或者 "ask coder"
                self.logger.exception("Body执行错误")
                self._add_intention_feedback_to_history(intention, action_name, f"Something wrong happened : {e}")
                continue

    

    def _resolve_session(self, email: Email) -> TaskSession:
        # Case A: Reply
        if email.in_reply_to and email.in_reply_to in self.reply_mapping:
            session_id = self.reply_mapping.pop(email.in_reply_to)
            return self.sessions[session_id]
        
        # Case B: New Task
        session = TaskSession(
            session_id=email.id,
            original_sender=email.sender,
            history=[],
            status="RUNNING",
            user_session_id=email.user_session_id
        )
        self.sessions[email.id] = session
        return session

    def _add_message_to_history(self, email: Email):
        # 如果是新 Session，注入 System Prompt
        session = self.current_session
        if len(session.history) == 0:
            session.history.append({"role": "system", "content": self.get_prompt()})
        
        # 注入用户/同事的邮件
        
        content =  "[INCOMING MAIL]\n"
        content+= f"From: {email.sender}\n"
        content+= f"Subject: {email.subject}\n"
        content+= textwrap.dedent(f"""Body: 
            {email.body}
        """)
        
        session.history.append({"role": "user", "content": content})

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
        session.history.append({"role": "assistant", "content": intention})
        session.history.append({"role": "user", "content": msg_body})

    


    def _add_brain_intention_to_history(self, intention):
        session = self.current_session
        session.history.append({"role": "assistant", "content": intention})

    def _add_question_to_brain(self, question):
        session = self.current_session
        
        session.history.append({"role": "user", "content": f"[INTERNAL QUERY]: {question}\n"})



    def _get_llm_context(self, session: TaskSession) -> List[Dict]:
        """
        [多态的关键]
        Worker: 返回完整的 history。
        Planner: 将重写此方法，返回 State + Latest Message。
        """
        return session.history

    
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
        in_reply_to = session.session_id
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
            user_session_id=session.user_session_id
        )
        
        

        await self.post_office.dispatch(msg)
        self.reply_mapping[msg.id] = self.current_session.session_id
        return f"Email sent to {to}"

    

    


    def get_snapshot(self):
        """
        核心可观察性方法：返回 Agent 当前的完整状态快照
        """
        # 1. 统计当前正在进行的会话
        active_sessions_data = []
        for sess_id, session in self.sessions.items():
            active_sessions_data.append({
                "session_id": sess_id,
                "original_sender": session.original_sender,
                "status": session.status,
                "history_length": len(session.history),
                # 这里甚至可以把最后一条对话内容截取出来展示
                "last_message": session.history[-1]['content'][:50] + "..." if session.history else ""
            })

        # 2. 统计正在等待的外部请求
        waiting_for = []
        for msg_id, sess_id in self.reply_mapping.items():
            waiting_for.append({
                "waiting_msg_id": msg_id,
                "belongs_to_session": sess_id
            })

        return {
            "name": self.name,
            "is_alive": True, # 这里可以加心跳检查
            "inbox_depth": self.inbox.qsize(), # 还有多少信没读
            "sessions_count": len(self.sessions),
            "sessions": active_sessions_data,  # 详细上下文
            "waiting_map": waiting_for         # 依赖关系
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
        
        # 2. 提取 Session
        sessions_dump = {k: v.to_dict() for k, v in self.sessions.items()}

        # 额外检查：如果保存时正在处理某封信，把它塞回 Inbox 的头部！
        # 这样下次启动时，Agent 会重新处理这封信，相当于“断点重试”
        if self.last_received_email and not self.last_email_processed:
             inbox_content.insert(0, asdict(self.last_received_email))

        return {
            "name": self.name,
            "inbox": inbox_content,
            "sessions": sessions_dump,
            "reply_mapping": self.reply_mapping,
            # 如果是 Planner，它会有额外的 project_state，
            # 可以通过 hasattr 检查或者子类覆盖 dump_state
            "extra_state": getattr(self, "project_state", None) 
        }

    def load_state(self, snapshot: Dict):
        """从快照恢复现场"""
        # 1. 恢复收件箱
        for email_dict in snapshot["inbox"]:
            # 假设 Email 类有 from_dict
            email = Email(**email_dict)
            self.inbox.put_nowait(email)
            
        # 2. 恢复 Sessions
        self.sessions = {
            k: TaskSession.from_dict(v) 
            for k, v in snapshot["sessions"].items()
        }
        
        # 3. 恢复路由表
        self.reply_mapping = snapshot["reply_mapping"]
        
        # 4. 恢复额外状态 (Planner)
        if snapshot.get("extra_state"):
            self.project_state = snapshot["extra_state"]


    
    