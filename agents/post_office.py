import asyncio
from typing import Dict
from db.database import AgentDB
import os

class PostOffice:
    def __init__(self, matrix_path):
        self.directory = {}
        self.queue = asyncio.Queue()
        db_file_path = os.path.join(matrix_path,".matrix" , "matrix.db")
        self.db = AgentDB(db_file_path) # 初始化数据库连接
        self._paused = False

    def register(self, agent):
        self.directory[agent.name] = agent
        agent.post_office = self

    def pause(self):
        self._paused = True

    def resume(self):
        self._paused = False

    async def dispatch(self, email):
        self.db.log_email(email)
        await self.queue.put(email)

    async def run(self):
        print("[PostOffice] Service Started")
        while True:
            if not self._paused:
                email = await self.queue.get()
                if email.recipient in self.directory:
                    target = self.directory[email.recipient]
                    await target.inbox.put(email)
                else:
                    print(f"Dropped mail to {email.recipient}")
                self.queue.task_done()
            else:
                await asyncio.sleep(0.1)