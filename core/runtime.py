# runtime.py 或 snapshot_manager.py
import json

from datetime import datetime
from core.message import Email
from dataclasses import asdict
from core.loader import AgentLoader
import asyncio
import os
import logging
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings
from agents.post_office import PostOffice


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
    pass
    #self.logger.info(event)

class AgentMatrix:
    def __init__(self, agent_profile_path="./profiles", event_call_back = default_event_printer):
        # === 全局实例 ===
        self.post_office = None
        self.event_call_back = event_call_back

        self.post_office_task = None
        self.agent_profile_path= agent_profile_path

        # 2. 初始化 Loader
        self.loader = AgentLoader(agent_profile_path)

        # 3. 自动加载所有 Agent
        self.agents = self.loader.load_all()
        for agent in self.agents.values():
            agent.event_call_back = event_call_back
                
        
            
                         
        self.running_agent_tasks = []
        self.running = False
        self.matrix_path = None
        self.logger = logging.getLogger("AgentMatrix")
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(">>> 初始化向量数据库...")
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-zh-v1.5")
        self.logger.info(">>> 向量数据库初始化完成.")
        self.vector_db = None
        self.notebook_collection = None
    def json_serializer(self,obj):
        """JSON serializer for objects not serializable by default json code"""
        try:
            if isinstance(obj, (datetime,)):
                return obj.isoformat()
            # 尝试获取对象的详细信息
            obj_info = f"Type: {type(obj)}, Value: {str(obj)[:100]}, Dir: {[attr for attr in dir(obj) if not attr.startswith('_')][:5]}"
            raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable\nObject info: {obj_info}")
        except Exception as e:
            raise TypeError(f"Error serializing object: {str(e)}\nObject info: {obj_info}")




    async def save_matrix(self):
        """一键休眠"""
        self.logger.info(">>> 正在冻结世界...")
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
                await self.post_office_task
                #asyncio.get_event_loop().run_until_complete(self.post_office_task)
            except asyncio.CancelledError:
                pass
            self.post_office_task = None
        
        world_state = {
            "timestamp": str(datetime.now()),
            "agents": {},
            "post_office": []
        }

        # 1. 冻结所有 Agent
        for agent in self.agents.values():
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
        try:
            with open(filepath, "w", encoding='utf-8') as f:
                json.dump(world_state, f, indent=2, ensure_ascii=False, default=self.json_serializer)
        except TypeError as e:
            self.logger.error(f"JSON序列化错误: {str(e)}")
            # 打印world_state的结构，帮助定位问题
            self.logger.debug("World state structure:")
            self.logger.debug(world_state)
            raise
            
        self.logger.info(f">>> 世界已保存至 {filepath}")
        # 9. 清理资源
        self.running = False

    def load_matrix(self, matrix_path):
        
        """一键复活"""
        self.logger.info(f">>> 正在从 {matrix_path} 恢复世界...")
        self.matrix_path = matrix_path
        matrix_snapshot_path = os.path.join(matrix_path,".matrix" , "matrix_snapshot.json")
        os.makedirs(os.path.dirname(matrix_snapshot_path), exist_ok=True)
        #加载向量数据库
        self.vector_db = chromadb.Client(Settings(
            persist_directory=os.path.join(self.matrix_path, ".matrix", "chroma_db")
        ))
        try:
            with open(matrix_snapshot_path, "r", encoding='utf-8') as f:
                content = f.read().strip()
                if not content:  # 文件为空
                    self.logger.info(f">>> {matrix_snapshot_path} 为空，创建新的世界状态...")
                    world_state = {}
                    with open(matrix_snapshot_path, "w", encoding='utf-8') as f:
                        json.dump(world_state, f, ensure_ascii=False, indent=2)
                else:
                    world_state = json.loads(content)  # 使用 json.loads 而不是 json.load
        except FileNotFoundError:
            self.logger.info(f">>> 未找到 {matrix_snapshot_path}，创建新的世界状态...")
            world_state = {}
            with open(matrix_snapshot_path, "w", encoding='utf-8') as f:
                json.dump(world_state, f, ensure_ascii=False, indent=2)

        # 1. 恢复 Agent 状态
        if world_state and "agents" in world_state:

            for agent in self.agents.values():
                if agent.name in world_state["agents"]:
                    agent_data = world_state["agents"][agent.name]
                    agent.load_state(agent_data)
                    self.logger.info(f">>> 恢复 Agent {agent.name} 状态成功！" )
        else:
            self.logger.info(">>> 未找到 Agent 状态.")

        
        
        
        # 3. 获取全局唯一的 Collection (笔记本)
        self.notebook_collection = self.vector_db.get_or_create_collection(
            name="matrix_notebook",
            embedding_function=self.embedding_function
        )
            

        


        # 2. 恢复 PostOffice 状态
        self.post_office = PostOffice(matrix_path)
        self.post_office_task = asyncio.create_task(self.post_office.run())

        self.running_agent_tasks =[]
        # 3. 注册到邮局
        for agent in self.agents.values():
            agent.workspace_root = matrix_path #设置root path
            self.post_office.register(agent)
            if hasattr(agent, 'notebook_collection'):
                agent.notebook_collection = self.notebook_collection

            self.running_agent_tasks.append(asyncio.create_task(agent.run()))
        
        

        # 4 注入prompt, 如果prompt 模版没找到，就unregister from post office



        prompts_path = os.path.join(self.agent_profile_path, "prompts")
        prompts = {}
        for prompt_txt in os.listdir(prompts_path):
            
            if prompt_txt.endswith(".txt"):
                self.logger.debug(f">>> 加载Prompt模板 {prompt_txt}...")
                with open(os.path.join(prompts_path, prompt_txt), "r", encoding='utf-8') as f:
                    prompts[prompt_txt[:-4]] = f.read()

        
        self.logger.debug(prompts)
        for agent in self.agents.values():
            template_name = "base"
            if 'prompt_template' in agent.profile:
                template_name = agent.profile['prompt_template']
            self.logger.debug(f">>> {agent.name} 使用Prompt模板 {template_name}...")
            if template_name in prompts:
                prompt = prompts[template_name]
                prompt =prompt.replace("{{ name }}", agent.name)
                prompt =prompt.replace("{{ description }}", agent.description)
                prompt =prompt.replace("{{ system_prompt }}", agent.system_prompt)
                yellow_page = self.post_office.yellow_page_exclude_me(agent.name)
                prompt =prompt.replace("{{ yellow_page }}", yellow_page)
                capabilities_menu = agent.get_capabilities_summary()
                prompt = prompt.replace("{{ capabilities }}", capabilities_menu)
                self.logger.debug(f">>> {agent.name} prompts 是：\n{prompt}" )
                agent.system_prompt = prompt
                

            else:
                self.post_office.unregister(agent)
                self.logger.info(f">>> {agent.name} 未找到Prompt模板 {template_name}，跳过注册.")




        

        # 4. 恢复投递
        self.post_office.resume()
        if world_state and 'post_office' in world_state:
            for email_dict in world_state["post_office"]:
                self.post_office.queue.put_nowait(Email(**email_dict))
        else:
            self.logger.info(">>> 未找到 PostOffice 状态.")
        
        self.running = True
        self.logger.info(">>> 世界已恢复，系统继续运行！")
        yellow_page = self.post_office.yellow_page()
        self.logger.info(f">>> 当前世界中的 Agent 有：\n{yellow_page}")