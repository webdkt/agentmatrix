"""
Container Runtime Factory - 容器运行时工厂

自动检测并创建可用的容器运行时适配器。
"""

import os
import logging
from typing import Optional

from .runtime_adapter import ContainerAdapter
from .docker_adapter import DockerAdapter
from .podman_adapter import PodmanAdapter, PODMAN_AVAILABLE


class ContainerRuntimeNotFoundError(Exception):
    """找不到可用的容器运行时"""
    pass


class ContainerRuntimeFactory:
    """
    容器运行时工厂

    职责：
    - 自动检测可用的容器运行时
    - 创建对应的适配器实例
    - 支持手动指定运行时类型

    优先级（从高到低）：
    1. 用户指定的运行时类型
    2. 环境变量 CONTAINER_RUNTIME
    3. 自动检测（Podman 优先，Docker 次之）
    """

    # ⭐ Podman 为默认选项（更好的 Windows 支持、更轻量、更安全）
    # 如果同时有 Podman 和 Docker，优先使用 Podman
    PRIORITY = ['podman', 'docker']

    @staticmethod
    def create(runtime_type: str = None, logger: logging.Logger = None) -> ContainerAdapter:
        """
        创建容器运行时适配器

        Args:
            runtime_type: 运行时类型 ('docker', 'podman', 'auto')
                         如果为 None，从环境变量读取
            logger: 日志记录器（可选）

        Returns:
            ContainerAdapter: 容器运行时适配器实例

        Raises:
            ContainerRuntimeNotFoundError: 找不到可用的运行时
            ValueError: 无效的运行时类型

        Examples:
            >>> # 自动检测
            >>> adapter = ContainerRuntimeFactory.create()

            >>> # 指定运行时
            >>> adapter = ContainerRuntimeFactory.create('docker')

            >>> # 通过环境变量
            >>> # export CONTAINER_RUNTIME=podman
            >>> adapter = ContainerRuntimeFactory.create()
        """
        if runtime_type is None:
            runtime_type = os.getenv('CONTAINER_RUNTIME', 'auto')

        runtime_type = runtime_type.lower().strip()

        if runtime_type == 'auto':
            return ContainerRuntimeFactory._auto_detect(logger)

        if runtime_type == 'docker':
            adapter = DockerAdapter(logger=logger)
            if adapter.ping():
                return adapter
            raise ContainerRuntimeNotFoundError(
                "Docker 不可用。请确保 Docker 已安装并运行。"
            )

        if runtime_type == 'podman':
            if not PODMAN_AVAILABLE:
                raise ContainerRuntimeNotFoundError(
                    "Podman Python SDK 未安装。\n"
                    "请安装: pip install podman\n"
                    "或使用: pip install -r requirements-podman.txt"
                )
            adapter = PodmanAdapter(logger=logger)
            if adapter.ensure_running():
                return adapter
            raise ContainerRuntimeNotFoundError(
                "Podman 不可用。请确保 Podman 已安装并运行。"
            )

        raise ValueError(
            f"无效的运行时类型: '{runtime_type}'。\n"
            f"支持的类型: 'auto', 'docker', 'podman'"
        )

    @staticmethod
    def _auto_detect(logger: logging.Logger = None) -> ContainerAdapter:
        """
        按优先级自动检测可用运行时

        Args:
            logger: 日志记录器（可选）

        Returns:
            ContainerAdapter: 第一个可用的运行时适配器

        Raises:
            ContainerRuntimeNotFoundError: 所有运行时都不可用
        """
        def log(msg: str, level: int = logging.INFO):
            if logger:
                logger.log(level, msg)

        last_error = None

        for runtime in ContainerRuntimeFactory.PRIORITY:
            try:
                log(f"🔍 检测运行时: {runtime}...")

                if runtime == 'podman':
                    if not PODMAN_AVAILABLE:
                        log("⏭️ Podman SDK 未安装，跳过", logging.DEBUG)
                        continue
                    adapter = PodmanAdapter(logger=logger)
                    if adapter.ensure_running():
                        log(f"✅ 检测到运行时: {runtime}")
                        return adapter

                elif runtime == 'docker':
                    adapter = DockerAdapter(logger=logger)
                    if adapter.ping():
                        log(f"✅ 检测到运行时: {runtime}")
                        return adapter

            except Exception as e:
                last_error = e
                log(f"⏭️ {runtime} 不可用: {e}", logging.DEBUG)
                continue

        # 所有运行时都不可用
        error_msg = (
            "未找到可用的容器运行时。\n\n"
            "请确保以下之一已安装并运行：\n"
            "  1. Podman (推荐): brew install podman  # macOS\n"
            "     或访问: https://podman.io/getting-started/installation\n"
            "  2. Docker: 访问 https://www.docker.com/products/docker-desktop/\n\n"
            "安装后，请确保运行时已启动。"
        )

        if last_error:
            error_msg += f"\n\n最后错误: {last_error}"

        raise ContainerRuntimeNotFoundError(error_msg)

    @staticmethod
    def is_docker_available(logger: logging.Logger = None) -> bool:
        """
        检查 Docker 是否可用

        Args:
            logger: 日志记录器（可选）

        Returns:
            bool: Docker 可用返回 True
        """
        try:
            adapter = DockerAdapter(logger=logger)
            return adapter.ping()
        except Exception:
            return False

    @staticmethod
    def is_podman_available(logger: logging.Logger = None) -> bool:
        """
        检查 Podman 是否可用

        Args:
            logger: 日志记录器（可选）

        Returns:
            bool: Podman 可用返回 True
        """
        if not PODMAN_AVAILABLE:
            return False

        try:
            adapter = PodmanAdapter(logger=logger)
            return adapter.ensure_running()
        except Exception:
            return False

    @staticmethod
    def ensure_running(logger: logging.Logger = None) -> ContainerAdapter:
        """
        确保容器运行时已启动。

        自动检测并启动可用的容器运行时（Podman 优先，Docker 次之）。
        这是一个全局初始化函数，应该在系统启动时调用一次。

        Args:
            logger: 日志记录器（可选）

        Returns:
            ContainerAdapter: 可用的容器运行时适配器，失败返回 None
        """
        try:
            adapter = ContainerRuntimeFactory._auto_detect(logger=logger)
            adapter.ensure_running()
            return adapter
        except Exception as e:
            if logger:
                logger.log(logging.WARNING, f"容器运行时启动失败: {e}")
            else:
                print(f"容器运行时启动失败: {e}")
            return None

    @staticmethod
    def get_available_runtimes(logger: logging.Logger = None) -> list:
        """
        获取所有可用的运行时列表

        Args:
            logger: 日志记录器（可选）

        Returns:
            list: 可用的运行时类型列表
        """
        available = []

        if ContainerRuntimeFactory.is_podman_available(logger):
            available.append('podman')

        if ContainerRuntimeFactory.is_docker_available(logger):
            available.append('docker')

        return available
