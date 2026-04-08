# runtime.py
import json

from datetime import datetime
from ..core.message import Email
from ..core.loader import AgentLoader
import asyncio


from ..agents.post_office import PostOffice
from ..core.log_util import LogFactory, AutoLoggerMixin
from .system_status_collector import SystemStatusCollector


# all event format:
# Who(event source)
# Status(the status of the event source)
# Even Type
# Even Time
# Event Content
# Event Payload


async def default_event_printer(event):
    pass
    # self.echo(event)


class AgentMatrix(AutoLoggerMixin):
    def __init__(
        self,
        matrix_root: str,
        async_event_callback=default_event_printer,
        user_agent_name: str = None,
    ):
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

        # === 初始化 Prompt 注册中心 ===
        from ..services.prompt_registry import PromptRegistry

        self.prompt_registry = PromptRegistry(self.paths.prompts_dir)

        # 从配置获取user_agent_name（如果未提供）
        if user_agent_name is None:
            user_agent_name = self.config.matrix.user_agent_name

        self.async_event_callback = async_event_callback
        # self.matrix_path = matrix_root  # 保留向后兼容

        # Store user agent name
        self.user_agent_name = user_agent_name

        self.agents = None
        self.post_office = None
        self.post_office_task = None
        self.running_agent_tasks = []
        self.running = False
        self.agent_name_set = set()  # Agent 名字快速查找集合

        # 🆕 系统配置（向后兼容）
        self.system_config = None
        self.email_proxy = None

        # 🆕 后台服务任务引用（用于关闭时取消）
        self.scheduler_task = None
        self.email_proxy_task = None
        self.monitor_task = None

        self.echo(">>> 初始化世界资源...")
        self._prepare_world_resource()
        self.echo(">>> 初始化Agents...")
        self._prepare_agents()
        # 构建 Agent 名字快速查找集合
        self.agent_name_set = set(self.agents.keys())
        self.echo(f">>> Agent 名字集合: {self.agent_name_set}")

        # 🔧 广播回调接口（由 server 注入）- 必须在 startup 之前初始化
        self._broadcast_message_callback = None

        self.echo(">>> 初始化系统配置...")
        self._init_system_config()

        # 🆕 初始化单容器管理器
        self.echo(">>> 初始化单容器管理器...")
        self._init_container_manager()

        self.echo(">>> 广播回调接口已初始化（事件驱动模式）")

        # 🆕 电源管理器（防止系统休眠，默认启用）
        from ..core.power_manager import PowerManager

        self.power_manager = PowerManager(enabled=True, parent_logger=self.logger)
        self.echo(">>> PowerManager initialized (防止系统休眠已启用)")

        self.echo(">>> 启动系统...")
        self.startup()
        self.echo(">>> 启动 LLM 服务监控...")
        self._start_llm_monitor()

        # 🆕 系统状态收集器
        self.status_collector = SystemStatusCollector(self)
        self.echo(">>> 系统状态收集器已初始化")

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

    def json_serializer(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        try:
            if isinstance(obj, (datetime,)):
                return obj.isoformat()
            # 尝试获取对象的详细信息
            obj_info = f"Type: {type(obj)}, Value: {str(obj)[:100]}, Dir: {[attr for attr in dir(obj) if not attr.startswith('_')][:5]}"
            raise TypeError(
                f"Object of type {obj.__class__.__name__} is not JSON serializable\nObject info: {obj_info}"
            )
        except Exception as e:
            raise TypeError(
                f"Error serializing object: {str(e)}\nObject info: {obj_info}"
            )

    # 准备世界资源，如向量数据库等
    def _prepare_world_resource(self):

        # 🐳 确保容器运行时已启动（全局资源初始化）
        self.echo(">>> 检查容器运行时状态...")
        from ..core.container.runtime_factory import ContainerRuntimeFactory

        self._container_adapter = ContainerRuntimeFactory.ensure_running(logger=self.logger)
        if not self._container_adapter:
            raise RuntimeError(
                "容器运行时启动失败。AgentMatrix 依赖 Docker 或 Podman 运行，请确保已安装并启动。\n"
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
            logger=self.logger,
        )
        self.echo(">>> TaskScheduler Loaded.")

    def _prepare_agents(self):
        # 使用新的agent配置目录
        loader = AgentLoader(
            str(self.paths.agent_config_dir), str(self.paths.llm_config_path)
        )

        # 3. 自动加载所有 Agent
        self.agents = loader.load_all()
        for agent in self.agents.values():
            agent.async_event_callback = self.async_event_callback

        # 保存 loader 以获取 llm_config（用于创建监控器）
        self.loader = loader
        self.llm_monitor = None

    def _start_llm_monitor(self):
        """启动 LLM 服务监控器 (Lazy模式)"""
        from .service_monitor import LLMServiceMonitor

        # 获取 llm_config
        llm_config = self.loader.llm_config

        # 创建监控器
        self.llm_monitor = LLMServiceMonitor(
            llm_config=llm_config,
            check_interval=5,  # Lazy模式，按需检查间隔5秒
            parent_logger=self.logger,
        )

        # 启动监控任务
        self.monitor_task = asyncio.create_task(self.llm_monitor.start())

        self.echo(f">>> LLM Service Monitor started (lazy mode)")

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

        # 🆕 确保容器用户已创建
        if self.container_manager:
            try:
                self.container_manager.ensure_user(agent_name)
                self.echo(f">>> 容器用户已创建: {agent_name}")
            except Exception as e:
                self.echo(f">>> 容器用户创建失败: {e}")

        # 添加到agents字典
        self.agents[agent_name] = agent

        # 更新快速查找集合
        self.agent_name_set.add(agent_name)

        # 注册到PostOffice
        self.post_office.register(agent)

        # 启动Agent任务
        agent_task = asyncio.create_task(agent.run())
        self.running_agent_tasks.append(agent_task)

        self.echo(f">>> Agent '{agent_name}' 已成功加载并注册到系统")

        return agent

    def _init_system_config(self):
        """初始化系统配置"""
        # 检查是否启用EmailProxy
        if self.config.email_proxy.is_configured():
            self._init_email_proxy()
        else:
            self.echo(">>> EmailProxy未启用")

    def _init_container_manager(self):
        """初始化单容器管理器（共享容器架构）"""
        from ..core.container.single_container_manager import SingleContainerManager

        self.container_manager = SingleContainerManager(
            workspace_root=self.paths.workspace_dir,
            parent_logger=self.logger,
            adapter=self._container_adapter,
        )
        # 确保容器已启动
        self.container_manager.wakeup()
        self.echo(">>> 单容器管理器初始化成功")

    def _init_email_proxy(self):
        """初始化EmailProxy服务"""
        from ..services.email_proxy_service import EmailProxyService

        email_config = self.config.get_email_proxy_config()
        self.logger.info(f"📧 EmailProxy原始配置: {email_config}")

        if not email_config:
            self.logger.info("⚠️ EmailProxy配置为空")
            return

        email_proxy_inner = email_config.get("email_proxy", {})
        if not email_proxy_inner:
            self.logger.info("⚠️ EmailProxy内层配置为空")
            return

        if not email_proxy_inner.get("enabled", False):
            self.logger.info(
                f"⚠️ EmailProxy未启用 (enabled={email_proxy_inner.get('enabled')})"
            )
            return

        self.logger.info(
            f"✅ 初始化EmailProxy: {email_proxy_inner.get('matrix_mailbox')} → {email_proxy_inner.get('user_mailbox')}"
        )
        self.email_proxy = EmailProxyService(
            paths=self.paths,
            config=email_proxy_inner,
            post_office=self.post_office,
            db_path=str(self.paths.database_path),
            parent_logger=self.logger,
        )

        # 注入到UserProxyAgent
        user_agent = self.agents.get(self.user_agent_name)
        if user_agent and hasattr(user_agent, "set_email_proxy"):
            user_agent.set_email_proxy(self.email_proxy)

        self.echo(">>> EmailProxy服务已初始化")

    async def shutdown(self):
        """关闭系统 - 停止所有服务和任务"""
        self.echo(">>> 正在冻结世界...")

        # 0. 停止电源管理（最先停止，恢复系统默认行为）
        await self.power_manager.stop()

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

        if hasattr(self, "task_scheduler"):
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
                    timeout=5.0,
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

        # 6. 停止单容器管理器
        if hasattr(self, "container_manager") and self.container_manager:
            try:
                self.container_manager.stop()
                self.echo(">>> 单容器管理器已停止")
            except Exception as e:
                self.echo(f">>> 单容器管理器停止失败: {e}")

        # 7. 清理资源
        self.running = False

        # 7. 取消未完成的任务（避免hang）
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

    def startup(self):
        """启动系统 - 注册Agent、启动服务、恢复未投递邮件"""
        self.echo(">>> 正在启动系统...")

        # 启动电源管理（防止系统休眠）
        self.power_manager.start_sync()

        # 1. 注册 Agent 到邮局并启动
        self.running_agent_tasks = []
        for agent in self.agents.values():
            # 注入 runtime 引用（setter 会自动初始化 SessionManager 等资源）
            agent.runtime = self
            self.post_office.register(agent)

            self.running_agent_tasks.append(asyncio.create_task(agent.run()))
            self.echo(f">>> Agent {agent.name} 已注册到邮局！")

        # 2. 启动 EmailProxy（hook 注册立即完成，IMAP 拉取延迟 60s）
        if self.email_proxy:
            self.echo(f">>> 启动 EmailProxy 服务...")
            self.email_proxy_task = asyncio.ensure_future(self.email_proxy.start())
            self.echo(">>> EmailProxy service started")
        else:
            self.echo(">>> EmailProxy 未配置，跳过启动")

        # 3. 从数据库恢复未投递的邮件
        undelivered = self.post_office.email_db.get_undelivered_emails()
        if undelivered:
            self.echo(f">>> 恢复 {len(undelivered)} 封未投递邮件...")
            for email_dict in undelivered:
                try:
                    email = Email(**email_dict)
                    self.post_office.queue.put_nowait(email)
                except Exception as e:
                    self.logger.warning(f"恢复邮件失败: {e}")

        # 3b. 恢复已投递但未处理的邮件（crash 在 inbox → route 之间）
        for agent_name, agent in self.agents.items():
            unprocessed = self.post_office.email_db.get_unprocessed_emails(recipient=agent_name)
            if unprocessed:
                self.echo(f">>> 恢复 {len(unprocessed)} 封 {agent_name} 未处理邮件...")
                for email_dict in unprocessed:
                    try:
                        email = Email(**email_dict)
                        self.post_office.queue.put_nowait(email)
                    except Exception as e:
                        self.logger.warning(f"恢复未处理邮件失败: {e}")

        # 4. 恢复投递
        self.post_office.resume()

        # 5. 启动 TaskScheduler
        if hasattr(self, "task_scheduler"):
            self.scheduler_task = asyncio.ensure_future(self.task_scheduler.start())

        self.echo(">>> 系统启动完成，继续运行！")
        yellow_page = self.post_office.yellow_page()
        self.echo(f">>> 当前世界中的 Agent 有：\n{yellow_page}")

        # 启动运行时（事件驱动模式，无需定时广播）
        self.running = True

        # 注入广播回调给所有 Agent
        for agent in self.agents.values():
            agent._broadcast_message_callback = self.get_broadcast_callback()
        self.logger.info("✅ 广播回调已注入到所有 Agent")
