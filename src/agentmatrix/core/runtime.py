# runtime.py 或 snapshot_manager.py
import json

from datetime import datetime
from ..core.message import Email
from dataclasses import asdict
from ..core.loader import AgentLoader
import asyncio
import os

import chromadb

from chromadb.config import Settings
from ..agents.post_office import PostOffice
from ..core.log_util import LogFactory, AutoLoggerMixin
from ..db.vector_db import VectorDB


from ..core.message import Email


# all event format:
# Who(event source)
# Status(the status of the event source)
# Even Type
# Even Time
# Event Content
# Event Payload


VECTOR_DB_COLLECTIONS_NAMES =["email", "notebook"]

async def default_event_printer(event):
    pass
    #self.echo(event)

class AgentMatrix(AutoLoggerMixin):
    def __init__(self, agent_profile_path, matrix_path, async_event_callback = default_event_printer, user_agent_name: str = "User"):
        # === 全局实例 ===
        log_path = os.path.join(matrix_path,".matrix", "logs")
        LogFactory.set_log_dir(log_path)

        self.async_event_callback = async_event_callback
        self.agent_profile_path= agent_profile_path

        self.matrix_path = matrix_path

        # 🆕 配置 SKILL_REGISTRY，自动添加 workspace/skills/ 目录
        # 导入在这里，避免循环依赖
        from ..skills.registry import SKILL_REGISTRY
        SKILL_REGISTRY.add_workspace_skills(self.matrix_path)

        # Store user agent name
        self.user_agent_name = user_agent_name

        self.agents = None
        self.post_office = None
        self.post_office_task = None
        self.running_agent_tasks = []
        self.running = False
        self.echo(">>> 初始化世界资源...")
        self._prepare_world_resource()
        self.echo(">>> 初始化Agents...")
        self._prepare_agents()
        self.echo(">>> 加载世界状态...")
        self.load_matrix()
        self.echo(">>> 启动 LLM 服务监控...")
        self._start_llm_monitor()

    def get_user_agent_name(self) -> str:
        """Get the configured user agent name"""
        return self.user_agent_name
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


    #准备世界资源，如向量数据库等
    def _prepare_world_resource(self):
        
        self.echo(">>> Loading Vector Database...")
        chroma_path = os.path.join(self.matrix_path, ".matrix", "chroma_db")
        self.vector_db = VectorDB(chroma_path, VECTOR_DB_COLLECTIONS_NAMES)
        self.echo(">>> Vector Database Loaded.")
        # 恢复 PostOffice 状态
        self.post_office = PostOffice(self.matrix_path, self.user_agent_name)
        self.post_office.vector_db = self.vector_db
        self.post_office_task = asyncio.create_task(self.post_office.run())
        self.echo(">>> PostOffice Loaded and Running.")
        
    def _prepare_agents(self):
        loader = AgentLoader(self.agent_profile_path)

        # 3. 自动加载所有 Agent
        self.agents = loader.load_all()
        for agent in self.agents.values():
            agent.async_event_callback = self.async_event_callback

        # 保存 loader 以获取 llm_config（用于创建监控器）
        self.loader = loader
        self.llm_monitor = None
        self.monitor_task = None

    def _start_llm_monitor(self):
        """启动 LLM 服务监控器"""
        from .service_monitor import LLMServiceMonitor

        # 获取 llm_config
        llm_config = self.loader.llm_config

        # 创建监控器
        self.llm_monitor = LLMServiceMonitor(
            llm_config=llm_config,
            check_interval=60,  # 每分钟检查一次
            parent_logger=self.logger
        )

        # 启动监控任务
        self.monitor_task = asyncio.create_task(self.llm_monitor.start())

        # 为每个 Agent 注入 runtime 引用
        for agent in self.agents.values():
            agent.runtime = self

        self.echo(f">>> LLM Service Monitor started (interval: 60s)")



    async def save_matrix(self):
        """一键休眠 - 修复了任务等待和异常处理问题"""
        self.echo(">>> 正在冻结世界...")

        # 1. 先停止 LLM 监控器
        if self.llm_monitor:
            try:
                await asyncio.wait_for(self.llm_monitor.stop(), timeout=5.0)
                self.echo(">>> LLM monitor stopped")
            except asyncio.TimeoutError:
                self.echo(">>> LLM monitor stop timed out")

        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await asyncio.wait_for(self.monitor_task, timeout=5.0)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                pass
            self.monitor_task = None

        # 2. 暂停邮局
        self.post_office.pause()
        
        # 3. 取消所有正在运行的agent任务
        if self.running_agent_tasks:
            for task in self.running_agent_tasks:
                if not task.done():
                    task.cancel()
            
            # 等待所有任务完成（带超时）
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.running_agent_tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                self.echo(">>> Some agent tasks did not complete in time")
            self.running_agent_tasks.clear()

        # 4. 停止邮局任务
        if self.post_office_task:
            self.post_office_task.cancel()
            try:
                await asyncio.wait_for(self.post_office_task, timeout=5.0)
            except asyncio.TimeoutError:
                pass
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
            
        self.echo(f">>> 世界已保存至 {filepath}")
        # 9. 清理资源
        self.running = False

    def load_matrix(self):
        
        """一键复活"""
        self.echo(f">>> 正在从 {self.matrix_path} 恢复世界...")
        
        matrix_snapshot_path = os.path.join(self.matrix_path,".matrix" , "matrix_snapshot.json")
        os.makedirs(os.path.dirname(matrix_snapshot_path), exist_ok=True)
        #加载向量数据库
        
        try:
            with open(matrix_snapshot_path, "r", encoding='utf-8') as f:
                content = f.read().strip()
                if not content:  # 文件为空
                    self.echo(f">>> {matrix_snapshot_path} 为空，创建新的世界状态...")
                    world_state = {}
                    with open(matrix_snapshot_path, "w", encoding='utf-8') as f:
                        json.dump(world_state, f, ensure_ascii=False, indent=2)
                else:
                    world_state = json.loads(content)  # 使用 json.loads 而不是 json.load
        except FileNotFoundError:
            self.echo(f">>> 未找到 {matrix_snapshot_path}，创建新的世界状态...")
            world_state = {}
            with open(matrix_snapshot_path, "w", encoding='utf-8') as f:
                json.dump(world_state, f, ensure_ascii=False, indent=2)

        # 1. 恢复 Agent 状态
        if world_state and "agents" in world_state:

            for agent in self.agents.values():
                if agent.name in world_state["agents"]:
                    agent_data = world_state["agents"][agent.name]
                    agent.load_state(agent_data)
                    self.echo(f">>> 恢复 Agent {agent.name} 状态成功！" )
        

        

        self.running_agent_tasks =[]
        # 3. 注册到邮局
        for agent in self.agents.values():
            agent.workspace_root = self.matrix_path #设置root path
            self.post_office.register(agent)
            if hasattr(agent, 'vector_db'):
                agent.vector_db = self.vector_db

            self.running_agent_tasks.append(asyncio.create_task(agent.run()))
            self.echo(f">>> Agent {agent.name} 已注册到邮局！")
            
        
    
        # 4. 恢复投递
        self.post_office.resume()
        if world_state and 'post_office' in world_state:
            for email_dict in world_state["post_office"]:
                self.post_office.queue.put_nowait(Email(**email_dict))
        
        
        self.running = True
        self.echo(">>> 世界已恢复，系统继续运行！")
        yellow_page = self.post_office.yellow_page()
        self.echo(f">>> 当前世界中的 Agent 有：\n{yellow_page}")