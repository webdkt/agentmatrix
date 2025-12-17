import asyncio
from typing import Dict
from db.database import AgentMailDB
import os
import textwrap
from core.message import Email
from core.log_util import AutoLoggerMixin
class PostOffice(AutoLoggerMixin):
    def __init__(self, matrix_path):
        self.directory = {}
        self.queue = asyncio.Queue()
        email_db_path = os.path.join(matrix_path,".matrix" , "matrix_mails.db")
        self.email_db = AgentMailDB(email_db_path) # 初始化数据库连接
        self._paused = False
        self.vector_db = None




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
