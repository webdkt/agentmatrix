"""
Docker 容器管理器 - 向后兼容层

⚠️  这是一个向后兼容的包装器，内部使用新的容器运行时抽象层。

为了保持向后兼容性，这个类保留原有的接口名称和实现方式，
但内部委托给新的 ContainerManager（支持 Docker 和 Podman）。

新的代码应该使用 ContainerManager 或直接使用 ContainerRuntimeFactory。
"""

import logging
from pathlib import Path
from typing import Tuple, Dict, Optional

# 导入新的容器运行时抽象层
from .container.container_manager import ContainerManager
from .container.runtime_factory import ContainerRuntimeFactory


def ensure_docker_running(logger: Optional[logging.Logger] = None) -> bool:
    """
    确保容器运行时已启动（兼容名称）

    ⚠️ 注意：这个函数名称保留是为了向后兼容。
    实际上会自动检测并启动可用的容器运行时（Podman 优先，Docker 次之）。

    这是一个全局初始化函数，应该在系统启动时调用一次，
    而不是在每个 Agent 初始化时调用。

    Args:
        logger: 日志记录器（可选）

    Returns:
        bool: 容器运行时是否成功运行
    """
    def log(msg: str, level: int = logging.INFO):
        if logger:
            logger.log(level, msg)
        else:
            print(msg)

    # 尝试使用新的抽象层
    try:
        adapter = ContainerRuntimeFactory._auto_detect(logger=logger)
        return adapter.ensure_running()
    except Exception as e:
        log(f"⚠️ 容器运行时启动失败: {e}", logging.WARNING)
        return False


class DockerContainerManager:
    """
    Docker 容器管理器 - 向后兼容包装器

    ⚠️ 这是一个向后兼容的包装器，内部使用新的容器运行时抽象层。

    职责：
    - 容器生命周期管理（创建、唤醒、休眠、停止）
    - 符号链接动态切换（switch_workspace）
    - 容器内命令执行接口（exec_command）
    - 目录初始化（initialize_directories）

    支持的运行时：
    - Docker（默认）
    - Podman（自动检测或通过环境变量 CONTAINER_RUNTIME=podman）

    迁移说明：
    新代码应该使用 ContainerManager 而不是这个类。
    """

    def __init__(
        self,
        agent_name: str,
        workspace_root: Path,
        image_name: str = "agentmatrix:latest",
        parent_logger: Optional[logging.Logger] = None
    ):
        """
        初始化 Docker 容器管理器（向后兼容）

        Args:
            agent_name: Agent 名称
            workspace_root: 工作区根目录
            image_name: 镜像名称
            parent_logger: 父级 logger（可选）

        Raises:
            RuntimeError: 容器运行时不可用
        """
        # 使用新的容器管理器
        self._manager = ContainerManager(
            agent_name=agent_name,
            workspace_root=workspace_root,
            image_name=image_name,
            runtime_type=None,  # 自动检测
            parent_logger=parent_logger
        )

        # 暴露相同的属性（保持向后兼容性）
        self.agent_name = self._manager.agent_name
        self.workspace_root = self._manager.workspace_root
        self.image_name = self._manager.image_name
        self.logger = self._manager.logger

        # 兼容旧代码中可能访问的属性
        self.skills_dir = self._manager.skills_dir
        self.agent_files_dir = self._manager.agent_files_dir
        self.agent_home = self._manager.agent_home
        self.work_files_base = self._manager.work_files_base
        self.container_name = self._manager.container_name

        # 容器对象（动态代理）
        self._container_proxy = None

    @property
    def container(self):
        """
        获取容器对象（向后兼容）

        Returns:
            容器句柄的代理对象
        """
        if self._manager.container is None:
            return None

        # 创建代理对象，透明转发所有属性访问
        if self._container_proxy is None or self._container_proxy._target != self._manager.container:
            self._container_proxy = _ContainerHandleProxy(self._manager.container)

        return self._container_proxy

    @container.setter
    def container(self, value):
        """设置容器对象（向后兼容）"""
        # 这个 setter 主要是为了兼容旧代码中的赋值操作
        # 实际的容器对象由 _manager 管理
        pass

    def initialize_directories(self) -> None:
        """初始化目录结构"""
        return self._manager.initialize_directories()

    def wakeup(self) -> bool:
        """唤醒容器（unpause 或 start）"""
        return self._manager.wakeup()

    def hibernate(self) -> bool:
        """休眠容器（pause）"""
        return self._manager.hibernate()

    def switch_workspace(self, task_id: str) -> bool:
        """切换工作区符号链接"""
        return self._manager.switch_workspace(task_id)

    async def exec_command(
        self,
        command: str,
        timeout: int = 30
    ) -> Tuple[int, str, str]:
        """在容器内执行命令（async 版本）"""
        return await self._manager.exec_command(command, timeout)

    def get_status(self) -> Dict:
        """获取容器状态"""
        return self._manager.get_status()

    def stop(self) -> bool:
        """停止容器"""
        return self._manager.stop()

    def remove(self) -> bool:
        """删除容器"""
        return self._manager.remove()

    def __del__(self):
        """析构函数：清理资源"""
        if hasattr(self, '_manager'):
            try:
                # 清理管理器资源
                if hasattr(self._manager, '__del__'):
                    self._manager.__del__()
            except Exception:
                pass


class _ContainerHandleProxy:
    """
    容器句柄代理

    透明转发所有属性访问到底层的容器句柄。
    用于保持向后兼容性。
    """

    def __init__(self, target):
        self._target = target

    def __getattr__(self, name):
        """转发所有属性访问到目标对象"""
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        return getattr(self._target, name)

    def __setattr__(self, name, value):
        """转发所有属性设置到目标对象"""
        if name == '_target' or name.startswith('_'):
            super().__setattr__(name, value)
        else:
            setattr(self._target, name, value)
