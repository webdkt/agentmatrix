# runtime.py 或 snapshot_manager.py
import json
from agents.base import BaseAgent
from typing import List
from datetime import datetime
from core.message import Email
from dataclasses import asdict

class WorldManager:
    def __init__(self, agents: List[BaseAgent], post_office):
        self.agents = agents
        self.post_office = post_office

    def save_world(self, filepath="world_snapshot.json"):
        """一键休眠"""
        print(">>> 正在冻结世界...")
        
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

        # 3. 写入磁盘
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(world_state, f, indent=2, ensure_ascii=False)
            
        print(f">>> 世界已保存至 {filepath}")

    def load_world(self, filepath="world_snapshot.json"):
        """一键复活"""
        print(f">>> 正在从 {filepath} 恢复世界...")
        
        with open(filepath, "r", encoding='utf-8') as f:
            world_state = json.load(f)

        # 1. 恢复 Agent 状态
        for agent in self.agents:
            if agent.name in world_state["agents"]:
                agent_data = world_state["agents"][agent.name]
                agent.load_state(agent_data)

        # 2. 恢复邮局
        for email_dict in world_state["post_office"]:
            self.post_office.queue.put_nowait(Email(**email_dict))
            
        print(">>> 世界已恢复，系统继续运行！")