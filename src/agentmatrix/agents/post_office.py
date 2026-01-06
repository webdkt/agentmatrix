import asyncio
from typing import Dict, Optional
from ..db.database import AgentMailDB
import os
import json
import textwrap
from pathlib import Path
from ..core.message import Email
from ..core.log_util import AutoLoggerMixin
class PostOffice(AutoLoggerMixin):
    def __init__(self, matrix_path, user_agent_name: str = "User"):
        self.directory = {}
        self.queue = asyncio.Queue()
        email_db_path = os.path.join(matrix_path,".matrix" , "matrix_mails.db")
        self.email_db = AgentMailDB(email_db_path) # 初始化数据库连接
        self._paused = False
        self.vector_db = None

        # Store user agent name
        self.user_agent_name = user_agent_name

        # 初始化 user_sessions 管理
        self.user_sessions = {}
        self.user_sessions_file = os.path.join(matrix_path, ".matrix", "user_sessions.json")
        self._load_user_sessions()

    def _load_user_sessions(self):
        """从文件加载 user_sessions 数据"""
        try:
            file_path = Path(self.user_sessions_file)
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.user_sessions = json.load(f)
                self.logger.info(f"Loaded {len(self.user_sessions)} user sessions from {self.user_sessions_file}")
            else:
                # 文件不存在，确保目录存在
                file_path.parent.mkdir(parents=True, exist_ok=True)
                self.user_sessions = {}
                self.logger.info(f"User sessions file not found. Starting with empty sessions.")
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse user sessions file: {e}. Starting with empty sessions.")
            self.user_sessions = {}
        except Exception as e:
            self.logger.exception(f"Error loading user sessions: {e}. Starting with empty sessions.")
            self.user_sessions = {}

    def _save_user_sessions(self):
        """保存 user_sessions 数据到文件（使用原子写入）"""
        try:
            file_path = Path(self.user_sessions_file)
            # 确保目录存在
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用原子写入：先写临时文件，再重命名
            temp_file = file_path.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_sessions, f, ensure_ascii=False, indent=2)

            # 原子重命名
            temp_file.replace(file_path)

            self.logger.debug(f"Saved {len(self.user_sessions)} user sessions to {self.user_sessions_file}")
        except Exception as e:
            self.logger.exception(f"Failed to save user sessions: {e}")




    def register(self, agent):
        self.directory[agent.name] = agent
        agent.post_office = self

    def unregister(self, agent):
        del self.directory[agent.name]

    def yellow_page(self):
        yellow_page = ""
        for name, agent in self.directory.items():
            # 给 description 添加 2 个空格的缩进
            
            description = textwrap.indent(agent.description, "  ")
            
            # 给 instruction 添加 4 个空格的缩进
            instruction = textwrap.indent(agent.instruction_to_caller, "    ")
            
            yellow_page += f"- {name}: \n"
            yellow_page += f"{description} \n"
            
            yellow_page += f"  [How to talk to {agent.name}]\n"
            yellow_page += f"{instruction}\n\n"
        return yellow_page

    def yellow_page_exclude_me(self, myname):
        yellow_page = ""
        for name, agent in self.directory.items():
            # 给 description 添加 2 个空格的缩进
            if name == myname:
                continue
            description = textwrap.indent(agent.description, "  ")
            
            # 给 instruction 添加 4 个空格的缩进
            instruction = textwrap.indent(agent.instruction_to_caller, "    ")
            
            yellow_page += f"- {name}: \n"
            yellow_page += f"{description} \n"
            
            yellow_page += f"  [How to talk to {agent.name}]\n"
            yellow_page += f"{instruction}\n\n"
        return yellow_page

    def get_contact_list(self, exclude =None):
        contact_list = []
        for name, agent in self.directory.items():
            if name == exclude:
                continue
            contact_list.append(name)
        return contact_list





    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    async def dispatch(self, email):
        self.email_db.log_email(email)
        self.vector_db.add_documents("email", [str(email)],
            metadatas={"created_at": email.timestamp,
                       "sender": email.sender,
                       "recipient": email.recipient,
                       "user_session_id": email.user_session_id
                },
            ids=[email.id]
        )

        # 维护 user_sessions
        if email.user_session_id:
            if email.user_session_id not in self.user_sessions:
                # 新的 session，添加记录
                self.user_sessions[email.user_session_id] = {
                    "name": email.subject,
                    "last_email_time": str(email.timestamp)
                }
                self.logger.info(f"New user session created: {email.user_session_id} - {email.subject}")
            else:
                # 已存在的 session，更新时间戳
                self.user_sessions[email.user_session_id]["last_email_time"] = str(email.timestamp)
                self.logger.debug(f"User session updated: {email.user_session_id}")

            # 同步到磁盘
            self._save_user_sessions()

        self.logger.debug(f"Sending email from {email.sender} to {email.recipient} ")
        await self.queue.put(email)
        self.logger.debug("Mail delivered")

    async def run(self):
        self.logger.info("[PostOffice] Service Started")
        while True:
            if not self._paused:
                email = await self.queue.get()
                if email.recipient in self.directory:
                    target = self.directory[email.recipient]
                    await target.inbox.put(email)
                else:
                    self.logger.warning(f"Dropped mail to {email.recipient}")
                self.queue.task_done()
            else:
                await asyncio.sleep(0.1)

    def get_mails_by_range(self, user_session_id, agent_name, start=0, end=1):
        """查询某个Agent的指定Range的邮件
        Args:
            agent_name: Agent名称
            start: 起始索引（0表示最新邮件）
            end: 结束索引
        Returns:
            指定范围内的邮件列表
        """
        email_records = self.email_db.get_mails_by_range(user_session_id, agent_name, start, end)
        emails = []
        for record in email_records:
            email = Email(
                id=record['id'],
                timestamp=record['timestamp'],
                sender=record['sender'],
                recipient=record['recipient'],
                subject=record['subject'],
                body=record['body'],
                in_reply_to=record['in_reply_to'],
                user_session_id=record.get('user_session_id', None)
            )
            emails.append(email)
        return emails

    def get_user_sessions(self, user_session_id: Optional[str] = None) -> Dict:
        """
        获取 user_sessions 数据

        Args:
            user_session_id: 可选，如果提供则返回指定 session 的数据，否则返回所有 sessions

        Returns:
            如果提供了 user_session_id：返回该 session 的信息字典，不存在则返回 None
            如果未提供：返回所有 sessions 的副本（避免外部修改）
        """
        if user_session_id:
            return self.user_sessions.get(user_session_id)
        else:
            # 返回深拷贝，避免外部修改影响内部数据
            return json.loads(json.dumps(self.user_sessions))

    def get_session_emails_for_user(self, user_session_id):
        """获取某个用户会话中所有与User相关的邮件
        Args:
            user_session_id: 用户会话ID
        Returns:
            Email对象列表，每个Email包含额外的 is_from_user 布尔字段
        """
        email_records = self.email_db.get_user_session_emails(user_session_id, self.user_agent_name)
        emails = []
        for record in email_records:
            email = Email(
                id=record['id'],
                timestamp=record['timestamp'],
                sender=record['sender'],
                recipient=record['recipient'],
                subject=record['subject'],
                body=record['body'],
                in_reply_to=record['in_reply_to'],
                user_session_id=record.get('user_session_id', None)
            )
            # Add is_from_user flag
            email.is_from_user = (email.sender == self.user_agent_name)
            emails.append(email)
        return emails
