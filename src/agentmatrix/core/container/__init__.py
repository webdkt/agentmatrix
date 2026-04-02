"""
Container Runtime Abstraction Layer - 容器运行时抽象层

提供统一的容器运行时接口，支持 Docker 和 Podman。

主要组件：
- ContainerAdapter: 容器运行时统一接口
- ContainerHandle: 容器对象抽象
- ContainerRuntimeFactory: 运行时工厂（自动检测）
- ContainerCompat: 兼容性工具
- SingleContainerManager: 单容器多用户管理器（新架构）

使用示例：
    from agentmatrix.core.container import ContainerRuntimeFactory

    # 自动检测可用运行时（Podman 优先）
    adapter = ContainerRuntimeFactory.create()

    # 指定运行时类型
    adapter = ContainerRuntimeFactory.create('docker')

    # 通过环境变量配置
    # export CONTAINER_RUNTIME=podman
    adapter = ContainerRuntimeFactory.create()
"""

from .runtime_adapter import ContainerAdapter, ContainerHandle
from .runtime_factory import ContainerRuntimeFactory
from .compat import ContainerCompat
from .single_container_manager import SingleContainerManager

__all__ = [
    "ContainerAdapter",
    "ContainerHandle",
    "ContainerRuntimeFactory",
    "ContainerCompat",
    "SingleContainerManager",
]
