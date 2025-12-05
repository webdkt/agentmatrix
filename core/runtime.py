# runtime.py 或 snapshot_manager.py
import json
from agents.base import BaseAgent
from typing import List
from datetime import datetime
from core.message import Email
from dataclasses import asdict
from core.loader import AgentLoader
import asyncio
import os

from agents.post_office import PostOffice

from backends.mock_llm import MockLLM
from core.message import Email


# all event format:
# Who(event source)
# Status(the status of the event source)
# Even Type
# Even Time
# Event Content
# Event Payload
'''
{
 event_source: agent_name,
 source_status: "running",
 event_type: "inbox",
 event_time: "2023-10-10 10:10:10",
 event_content: "agent received a new email",
 event_payload: {}
}


'''
async def default_event_printer(event):
    print(event)

class AgentMatrix:
    def __init__(self, agent_profile_path="./profiles", event_call_back = default_event_printer):
        # === 全局实例 ===
        self.post_office = None
        self.event_call_back = event_call_back
        self.backend_llm = MockLLM()
        self.backend_slm = MockLLM()
        self.post_office_task = None


        # 2. 初始化 Loader
        self.loader = AgentLoader(backend_llm=self.backend_llm, backend_slm=self.backend_slm)

        # 3. 魔法发生的地方：自动加载所有 Agent
        self.agents = self.loader.load_all(agent_profile_path)
        for agent in self.agents:
            agent.event_call_back = event_call_back
                
        
            
                         
        self.running_agent_tasks = []
        self.running = False
        self.matrix_path = None
    
        



    def save_matrix(self):
        """一键休眠"""
        print(">>> 正在冻结世界...")
        self.post_office.pause()
        # 2. 取消所有正在运行的agent任务
        for task in self.running_agent_tasks:
            task.cancel()
        # 3. 等待所有任务完成
        if self.running_agent_tasks:
            asyncio.gather(*self.running_agent_tasks, return_exceptions=True)
        self.running_agent_tasks.clear()

        # 4. 停止邮局任务
        if self.post_office_task:
            self.post_office_task.cancel()
            try:
                asyncio.get_event_loop().run_until_complete(self.post_office_task)
            except asyncio.CancelledError:
                pass
            self.post_office_task = None
        
        world_state = {
            "timestamp": str(datetime.now()),
            "agents": {},
            "post_office": []
        }

        # 1. 冻结所有 Agent
        for agent in self.agents:
            world_state["agents"][agent.name] = agent.dump_state()

        # 2. 冻结邮局 (如果有还在路由的信)
        # 逻辑同 Agent Inbox
        po_queue = []
        while not self.post_office.queue.empty():
            email = self.post_office.queue.get_nowait()
            po_queue.append(asdict(email))
            self.post_office.queue.task_done()
        world_state["post_office"] = po_queue
        filepath = os.path.join(self.matrix_path, ".matrix", "matrix_snapshot.json")
        # 3. 写入磁盘
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(world_state, f, indent=2, ensure_ascii=False)
            
        print(f">>> 世界已保存至 {filepath}")
        # 9. 清理资源
        self.running = False

    def load_matrix(self, matrix_path):
        
        """一键复活"""
        print(f">>> 正在从 {matrix_path} 恢复世界...")
        self.matrix_path = matrix_path
        matrix_snapshot_path = os.path.join(matrix_path,".matrix" , "matrix_snapshot.json")
        os.makedirs(os.path.dirname(matrix_snapshot_path), exist_ok=True)
        
        try:
            with open(matrix_snapshot_path, "r", encoding='utf-8') as f:
                world_state = json.load(f)
        except FileNotFoundError:
            print(f">>> 未找到 {matrix_snapshot_path}，创建新的世界状态...")
            world_state = {}
            with open(matrix_snapshot_path, "w", encoding='utf-8') as f:
                json.dump(world_state, f, ensure_ascii=False, indent=2)

        # 1. 恢复 Agent 状态
        if world_state and "agents" in world_state:
            for agent in self.agents:
                if agent.name in world_state["agents"]:

                    agent_data = world_state["agents"][agent.name]
                    agent.load_state(agent_data)
                    print(f">>> 恢复 Agent {agent.name} 状态成功！" )
        else:
            print(">>> 未找到 Agent 状态.")
            

        


        # 2. 恢复 PostOffice 状态
        self.post_office = PostOffice(matrix_path)
        self.post_office_task = asyncio.create_task(self.post_office.run())

        self.running_agent_tasks =[]
        # 3. 注册到邮局
        for agent in self.agents:
            self.post_office.register(agent)
            self.running_agent_tasks.append(asyncio.create_task(agent.run()))


        

        # 4. 恢复投递
        self.post_office.resume()
        if world_state and 'post_office' in world_state:
            for email_dict in world_state["post_office"]:
                self.post_office.queue.put_nowait(Email(**email_dict))
        else:
            print(">>> 未找到 PostOffice 状态.")
        
        self.running = True
        print(">>> 世界已恢复，系统继续运行！")