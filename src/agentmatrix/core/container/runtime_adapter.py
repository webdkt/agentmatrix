"""
Container Runtime Adapter - 容器运行时适配器接口

定义了容器运行时的统一抽象接口，支持多种容器运行时（Docker、Podman）。
参考 BrowserAdapter 模式实现。
"""

from abc import ABC, abstractmethod
from typing import Tuple, Dict, Optional, Any
from pathlib import Path


class ContainerAdapter(ABC):
    """
    容器运行时统一接口

    职责：
    - 屏蔽不同容器运行时（Docker/Podman）的实现差异
    - 提供统一的容器管理接口
    - 支持容器生命周期管理

    类似 BrowserAdapter 模式，将逻辑层与执行层解耦。
    """

    # --- 连接管理 (Connection Management) ---

    @abstractmethod
    def ping(self) -> bool:
        """
        测试与容器运行时的连接

        Returns:
            bool: 连接成功返回 True

        Raises:
            ContainerRuntimeConnectionError: 连接失败
        """
        pass

    @abstractmethod
    def ensure_running(self) -> bool:
        """
        确保容器运行时已启动

        如果运行时未运行，尝试自动启动。

        Returns:
            bool: 成功返回 True

        Raises:
            ContainerRuntimeNotAvailableError: 运行时不可用
        """
        pass

    # --- 容器管理 (Container Management) ---

    @abstractmethod
    def create_container(
        self,
        name: str,
        image: str,
        volumes: Dict[str, Dict[str, str]],
        **kwargs
    ) -> 'ContainerHandle':
        """
        创建容器

        Args:
            name: 容器名称
            image: 镜像名称
            volumes: 卷挂载配置，格式：{宿主机路径: {'bind': 容器路径, 'mode': 'rw/ro'}}
            **kwargs: 其他容器创建参数

        Returns:
            ContainerHandle: 容器句柄

        Raises:
            ContainerRuntimeError: 容器创建失败
        """
        pass

    @abstractmethod
    def get_container(self, name: str) -> Optional['ContainerHandle']:
        """
        获取已存在的容器

        Args:
            name: 容器名称

        Returns:
            ContainerHandle: 容器句柄，如果不存在返回 None
        """
        pass

    @abstractmethod
    def close(self):
        """
        关闭运行时连接并清理资源
        """
        pass


class ContainerHandle(ABC):
    """
    容器对象抽象

    封装具体容器对象（Docker Container / Podman Container），
    提供统一的操作接口。

    类似 TabHandle，逻辑层不需要知道具体实现类型。
    """

    # --- 生命周期管理 (Lifecycle Management) ---

    @abstractmethod
    def start(self):
        """
        启动容器

        Raises:
            ContainerRuntimeError: 启动失败
        """
        pass

    @abstractmethod
    def stop(self, timeout: int = 5):
        """
        停止容器

        Args:
            timeout: 超时时间（秒）

        Raises:
            ContainerRuntimeError: 停止失败
        """
        pass

    @abstractmethod
    def pause(self):
        """
        暂停容器

        Raises:
            ContainerRuntimeError: 暂停失败
        """
        pass

    @abstractmethod
    def unpause(self):
        """
        恢复暂停的容器

        Raises:
            ContainerRuntimeError: 恢复失败
        """
        pass

    @abstractmethod
    def reload(self):
        """
        刷新容器状态

        从运行时重新加载容器状态信息。
        """
        pass

    @abstractmethod
    def remove(self):
        """
        删除容器

        Raises:
            ContainerRuntimeError: 删除失败
        """
        pass

    # --- 命令执行 (Command Execution) ---

    @abstractmethod
    def exec_run(
        self,
        cmd: str,
        **kwargs
    ) -> Tuple[int, bytes]:
        """
        在容器内执行命令

        Args:
            cmd: 要执行的命令
            **kwargs: 其他参数（demux, workdir 等）

        Returns:
            Tuple[int, bytes]: (退出码, 输出)
                如果 demux=True，返回 (exit_code, (stdout, stderr))
                如果 demux=False，返回 (exit_code, combined_output)

        Raises:
            ContainerExecutionError: 命令执行失败
        """
        pass

    # --- 属性访问 (Properties) ---

    @property
    @abstractmethod
    def status(self) -> str:
        """
        获取容器状态

        Returns:
            str: 容器状态（created, running, paused, exited, etc.）
        """
        pass

    @property
    @abstractmethod
    def short_id(self) -> str:
        """
        获取容器短ID

        兼容性说明：
        - Docker: container.short_id
        - Podman: container.attrs['Id'][:12]

        Returns:
            str: 容器短ID（12字符）
        """
        pass

    @property
    @abstractmethod
    def attrs(self) -> Dict[str, Any]:
        """
        获取容器完整属性

        Returns:
            Dict: 容器属性字典
        """
        pass

    @abstractmethod
    def get_attribute(self, key: str, default: Any = None) -> Any:
        """
        获取容器指定属性

        Args:
            key: 属性键
            default: 默认值

        Returns:
            属性值，如果不存在返回默认值
        """
        pass
