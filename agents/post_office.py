import asyncio
from typing import Dict
from db.database import AgentDB

class PostOffice:
    def __init__(self):
        self.directory = {}
        self.queue = asyncio.Queue()
        self.db = AgentDB() # 初始化数据库连接

    def register(self, agent):
        self.directory[agent.name] = agent
        agent.post_office = self

    async def dispatch(self, email):
        self.db.log_email(email)
        await self.queue.put(email)

    async def run(self):
        print("[PostOffice] Service Started")
        while True:
            email = await self.queue.get()
            if email.recipient in self.directory:
                target = self.directory[email.recipient]
                await target.inbox.put(email)
            else:
                print(f"Dropped mail to {email.recipient}")
            self.queue.task_done()