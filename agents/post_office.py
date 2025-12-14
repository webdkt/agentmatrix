import asyncio
from typing import Dict
from db.database import AgentDB
import os
import textwrap
import logging

class PostOffice:
    def __init__(self, matrix_path):
        self.directory = {}
        self.queue = asyncio.Queue()
        email_db_path = os.path.join(matrix_path,".matrix" , "matrix_mails.db")
        self.email_db = AgentDB(email_db_path) # 初始化数据库连接
        self._paused = False
        self.logger = logging.getLogger(__name__)

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