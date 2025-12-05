import asyncio
from typing import Dict, Optional, Callable
from core.message import Email
from core.session import TaskSession
from core.events import AgentEvent

import traceback
from dataclasses import asdict

class BaseAgent:
    def __init__(self, profile):
        self.name = profile["name"]
        self.description = profile["description"]
        
        self.system_prompt = profile["system_prompt"]
        self.profile = profile
        self.instruction_to_caller = profile["instruction_to_caller"]
        self.backend = profile["backend_model"]
        

        
        # 标准组件
        self.inbox = asyncio.Queue()
        #self.sessions = {}
        self.sessions: Dict[str, TaskSession] = {} # Key: Original Msg ID
        self.reply_mapping: Dict[str, str] = {}    # Key: Outgoing Msg ID -> Value: Session ID
        
        # 事件回调 (Server 注入)
        self.event_callback: Optional[Callable] = None
        print(f"Agent {self.name} 初始化完成")
    
    def get_introduction(self):
        """
        生成给其他 Agent 看的说明书 (Protocol Description)
        这是之前 AgentManifest.to_prompt() 的逻辑
        """
        
        return (
            f"--- Agent: {self.name} ---\n"
            f"Description: {self.description}\n"
            f"Instruction: {self.instructions}\n"
            f"--------------------------\n"
        )
    
    def configure(self, config: dict):
        #用config 来配置agent
        if 'description' in config:
            self.description = config['description']    
        if 'instructions' in config:
            self.instructions = config['instructions']
        if 'system_prompt' in config:
            self.system_prompt = config['system_prompt']
        if 'instruction_to_caller' in config:
            self.instruction_to_caller = config['instruction_to_caller']
        #use config to update self.profile
        self.profile = {**self.profile, **config}
        
    async def emit(self, event_type, content, payload=None):
        """
        发送事件到注册的事件回调函数
        
        Args:
            event_type (str): 事件的类型，用于标识不同种类的事件
            content (str): 事件的主要内容描述
            payload (dict, optional): 事件的附加数据，默认为None，当为None时会使用空字典
            
        Returns:
            None
            
        Raises:
            无显式抛出异常
        """
        # 检查是否存在事件回调函数
        if self.event_callback:
            # 创建新的事件对象，包含事件类型、发送者名称、内容和附加数据
            event = AgentEvent(event_type, self.name, content, payload or {})
            # 异步调用事件回调函数，将事件对象传递过去
            await self.event_callback(event)

    async def run(self):
        await self.emit("SYSTEM", f"{self.name} 启动")
        while True:
            email = await self.inbox.get()
            self.current_processing_msg = email 
            try:
                await self.process_email(email)
                self.current_processing_msg = None 
            except Exception as e:
                print(f"Error in {self.name}: {e}")
                traceback.print_exc()
            finally:
                self.inbox.task_done()

    async def process_email(self, email: Email):
        session = None
        
        # Case A: 这是一个我正在等待的回复 (Routing)
        if email.in_reply_to and email.in_reply_to in self.reply_mapping:
            session_id = self.reply_mapping.pop(email.in_reply_to)
            if session_id in self.sessions:
                session = self.sessions[session_id]
                await self.emit("INFO", f"收到回复，唤醒会话: {session_id[:8]}...")
                # 追加历史
                session.history.append({"role": "user", "content": f"Reply from {email.sender}: {email.body}"})
                session.status = "RUNNING"

        # Case B: 这是一个新任务
        elif not email.in_reply_to or email.in_reply_to not in self.reply_mapping:
            await self.emit("INFO", f"收到新任务: {email.subject}")
            session = TaskSession(
                session_id=email.id,
                original_sender=email.sender,
                history=[{"role": "user", "content": email.body}]
            )
            self.sessions[email.id] = session

        # 执行思考步骤
        if session:
            await self.step(session)

    async def step(self, session: TaskSession):
        """子类需实现具体的思考逻辑"""
        pass

    async def send_email(self, to, subject, body, session: TaskSession, expect_reply=False):
        # 构造邮件
        # 如果是中间步骤(问秘书)，in_reply_to 指向当前 Session 的最新状态
        # 如果是最终回复，in_reply_to 指向 Session ID (即最初的那封信)
        
        # 这里为了简化，统一指向 session_id，保持归属关系
        msg = Email(
            sender=self.name,
            recipient=to,
            subject=subject,
            body=body,
            in_reply_to=session.session_id
        )
        
        if expect_reply:
            # 关键：注册路由
            self.reply_mapping[msg.id] = session.session_id
            session.status = "WAITING"
            await self.emit("MAIL_SENT", f"去问 {to}: {subject}", payload={"wait_for": msg.id})
        else:
            # 任务结束，清理 Session
            if session.session_id in self.sessions:
                del self.sessions[session.session_id]
            await self.emit("MAIL_SENT", f"回复 {to}: {subject} (任务完成)")

        await self.post_office.dispatch(msg)


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
        if self.current_processing_msg:
             inbox_content.insert(0, asdict(self.current_processing_msg))

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