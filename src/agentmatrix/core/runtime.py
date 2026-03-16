# runtime.py 或 snapshot_manager.py
import json

from datetime import datetime
from ..core.message import Email
from dataclasses import asdict
from ..core.loader import AgentLoader
import asyncio
import os


from ..agents.post_office import PostOffice
from ..core.log_util import LogFactory, AutoLoggerMixin
from .system_status_collector import SystemStatusCollector


from ..core.message import Email


# all event format:
# Who(event source)
# Status(the status of the event source)
# Even Type
# Even Time
# Event Content
# Event Payload



async def default_event_printer(event):
    pass
    #self.echo(event)

class AgentMatrix(AutoLoggerMixin):
    def __init__(self, matrix_root: str, async_event_callback = default_event_printer, user_agent_name: str = None):
        """
        初始化AgentMatrix

        Args:
            matrix_root: Matrix World根目录（唯一必需的参数）
            async_event_callback: 异步事件回调函数
            user_agent_name: 用户Agent名称（可选，默认从配置读取）
        """
        # === 初始化路径管理器 ===
        from ..core.paths import MatrixPaths
        self.paths = MatrixPaths(matrix_root)

        # 确保所有必需的目录存在
        self.paths.ensure_directories()

        # === 全局实例 ===
        # ⚠️ 重要：必须在创建任何 logger 之前设置日志目录
        from ..core.log_util import LogFactory
        LogFactory.set_log_dir(str(self.paths.logs_dir))

        # === 初始化配置管理器 ===
        from ..core.config import MatrixConfig
        self.config = MatrixConfig(self.paths)

        # 从配置获取user_agent_name（如果未提供）
        if user_agent_name is None:
            user_agent_name = self.config.matrix.user_agent_name

        self.async_event_callback = async_event_callback
        self.matrix_path = matrix_root  # 保留向后兼容

        # 🆕 配置 SKILL_REGISTRY，自动添加 workspace/skills/ 目录
        # 导入在这里，避免循环依赖
        from ..skills.registry import SKILL_REGISTRY
        SKILL_REGISTRY.add_workspace_skills(self.paths)

        # Store user agent name
        self.user_agent_name = user_agent_name

        self.agents = None
        self.post_office = None
        self.post_office_task = None
        self.running_agent_tasks = []
        self.running = False

        # 🆕 系统配置（向后兼容）
        self.system_config = None
        self.email_proxy = None
        
        # 🆕 后台服务任务引用（用于关闭时取消）
        self.scheduler_task = None
        self.email_proxy_task = None

        self.echo(">>> 初始化世界资源...")
        self._prepare_world_resource()
        self.echo(">>> 初始化Agents...")
        self._prepare_agents()

        # 🔧 广播回调接口（由 server 注入）- 必须在 load_matrix 之前初始化
        self._broadcast_message_callback = None

        self.echo(">>> 加载世界状态...")
        self.load_matrix()
        self.echo(">>> 启动 LLM 服务监控...")
        self._start_llm_monitor()
        self.echo(">>> 初始化系统配置...")
        self._init_system_config()

        # 🆕 系统状态收集器
        self.status_collector = SystemStatusCollector(self)
        self.echo(">>> 系统状态收集器已初始化")
        self.echo(">>> 广播回调接口已初始化（事件驱动模式）")

    def get_user_agent_name(self) -> str:
        """Get the configured user agent name"""
        return self.user_agent_name

    def set_broadcast_callback(self, callback):
        """设置广播消息的回调（由 server 注入）"""
        self._broadcast_message_callback = callback
        self.logger.info("✅ 广播回调已设置")

    def get_broadcast_callback(self):
        """获取广播回调（给 BaseAgent 使用）"""
        return self._broadcast_message_callback

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

        # 🐳 确保 Docker 运行（全局资源初始化）
        self.echo(">>> 检查 Docker 状态...")
        from ..core.docker_manager import ensure_docker_running
        if not ensure_docker_running(logger=self.logger):
            raise RuntimeError(
                "Docker 启动失败。AgentMatrix 依赖 Docker 运行，请确保 Docker Desktop 已安装并可以启动。\n"
                "下载地址: https://www.docker.com/products/docker-desktop/"
            )

        # 初始化 PostOffice
        self.post_office = PostOffice(self.paths, self.user_agent_name)

        self.post_office_task = asyncio.create_task(self.post_office.run())
        self.echo(">>> PostOffice Loaded and Running.")

        # 🆕 初始化 TaskScheduler（全局服务）
        from ..core.scheduler_service import TaskScheduler
        self.task_scheduler = TaskScheduler(
            db_path=str(self.paths.database_path),
            post_office=self.post_office,
            logger=self.logger
        )
        self.echo(">>> TaskScheduler Loaded.")

    def _prepare_agents(self):
        # 使用新的agent配置目录
        loader = AgentLoader(str(self.paths.agent_config_dir), str(self.paths.llm_config_path))

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

        self.echo(f">>> LLM Service Monitor started (interval: 60s)")

    # ❌ 移除定时广播循环（改为事件驱动）
    # 每个 Agent 的 update_status() 会触发增量推送
    # 新连接时会发送全量状态

    async def load_and_register_agent(self, agent_name: str):
        """
        动态加载并注册一个新的Agent

        Args:
            agent_name: 要加载的Agent名称

        Returns:
            加载的Agent实例

        Raises:
            ValueError: 如果Agent已存在或加载失败
        """
        # 检查Agent是否已存在
        if agent_name in self.agents:
            raise ValueError(f"Agent '{agent_name}' already exists in runtime")

        self.echo(f">>> 动态加载Agent: {agent_name}")

        # 使用保存的loader加载Agent
        agent_yml_path = self.paths.agent_config_dir / f"{agent_name}.yml"
        if not agent_yml_path.exists():
            raise FileNotFoundError(f"Agent配置文件不存在: {agent_yml_path}")

        # 加载Agent
        try:
            agent = self.loader.load_from_file(str(agent_yml_path))
        except Exception as e:
            raise RuntimeError(f"加载Agent失败: {e}")

        # ⚠️ 重要：必须先设置 runtime，再启动 agent.run()
        # 因为 agent.run() 内部会访问 self.runtime
        agent.async_event_callback = self.async_event_callback
        agent.runtime = self  # 这会触发 SessionManager 和其他资源的初始化

        # 添加到agents字典
        self.agents[agent_name] = agent

        # 注册到PostOffice
        self.post_office.register(agent)

        # 启动Agent任务
        agent_task = asyncio.create_task(agent.run())
        self.running_agent_tasks.append(agent_task)

        self.echo(f">>> Agent '{agent_name}' 已成功加载并注册到系统")

        return agent

    def _init_system_config(self):
        """初始化系统配置"""
        from ..core.config import MatrixConfig
        self.system_config = MatrixConfig(self.paths)

        # 检查是否启用EmailProxy
        if self.system_config.is_email_proxy_enabled():
            self._init_email_proxy()
        else:
            self.echo(">>> EmailProxy未启用")

    def _init_email_proxy(self):
        """初始化EmailProxy服务"""
        from ..services.email_proxy_service import EmailProxyService

        email_config = self.system_config.get_email_proxy_config()
        if not email_config:
            self.echo(">>> EmailProxy配置不完整，跳过初始化")
            return

        self.email_proxy = EmailProxyService(
            paths=self.paths,
            config=email_config,
            post_office=self.post_office,
            db_path=str(self.paths.database_path),
            parent_logger=self.logger
        )

        # 注入到UserProxyAgent
        user_agent = self.agents.get(self.user_agent_name)
        if user_agent and hasattr(user_agent, 'set_email_proxy'):
            user_agent.set_email_proxy(self.email_proxy)

        self.echo(">>> EmailProxy服务已初始化")



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

        # 🆕 停止调度器

        # 🆕 停止后台服务任务
        if self.scheduler_task and not self.scheduler_task.done():
            self.scheduler_task.cancel()
            try:
                await asyncio.wait_for(self.scheduler_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            self.echo(">>> TaskScheduler task cancelled")
        
        if self.email_proxy_task and not self.email_proxy_task.done():
            self.email_proxy_task.cancel()
            try:
                await asyncio.wait_for(self.email_proxy_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            self.echo(">>> EmailProxy task cancelled")
        
        # 🆕 停止服务
        if self.email_proxy:
            try:
                await self.email_proxy.stop()
                self.echo(">>> EmailProxy stopped")
            except Exception as e:
                self.echo(f">>> EmailProxy stop error: {e}")

        # 🔧 事件驱动模式：无需停止广播任务

        if hasattr(self, 'task_scheduler'):
            await self.task_scheduler.stop()
        
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
        
        # 5. 关闭 PostOffice 数据库连接
        if self.post_office:
            self.post_office.close()
        
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
        filepath = str(self.paths.snapshot_path)
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

        # 10. 取消未完成的任务（避免hang）
        try:
            loop = asyncio.get_event_loop()
            pending = asyncio.all_tasks(loop)

            # 只保留当前任务，取消所有其他任务
            current_task = asyncio.current_task(loop)
            for task in pending:
                if task is not current_task and not task.done():
                    task.cancel()

            self.echo(">>> Tasks cancelled")
        except Exception as e:
            self.echo(f">>> Cleanup error: {e}")

    def load_matrix(self):

        """一键复活"""
        self.echo(f">>> 正在从 {self.matrix_path} 恢复世界...")

        matrix_snapshot_path = str(self.paths.snapshot_path)
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
            # 注入 runtime 引用（setter 会自动初始化 SessionManager 等资源）
            agent.runtime = self
            self.post_office.register(agent)

            self.running_agent_tasks.append(asyncio.create_task(agent.run()))
            self.echo(f">>> Agent {agent.name} 已注册到邮局！")
            
        
    
        # 4. 恢复投递
        self.post_office.resume()
        if world_state and 'post_office' in world_state:
            for email_dict in world_state["post_office"]:
                self.post_office.queue.put_nowait(Email(**email_dict))
        
        
        # 🆕 启动TaskScheduler
        if hasattr(self, 'task_scheduler'):
            self.scheduler_task = asyncio.ensure_future(self.task_scheduler.start())

        # 🆕 启动EmailProxy
        if self.email_proxy:
            self.email_proxy_task = asyncio.ensure_future(self.email_proxy.start())
            self.echo(">>> EmailProxy service started")
        self.echo(">>> 世界已恢复，系统继续运行！")
        yellow_page = self.post_office.yellow_page()
        self.echo(f">>> 当前世界中的 Agent 有：\n{yellow_page}")

        # 🔧 启动运行时（事件驱动模式，无需定时广播）
        self.running = True

        # ✅ 注入广播回调给所有 Agent
        for agent in self.agents.values():
            agent._broadcast_message_callback = self.get_broadcast_callback()
        self.logger.info("✅ 广播回调已注入到所有 Agent")