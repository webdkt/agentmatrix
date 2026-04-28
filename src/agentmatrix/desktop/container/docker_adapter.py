"""
Docker Runtime Adapter - Docker 运行时适配器

实现 Docker 容器运行时的具体功能。
"""

import docker
from docker.errors import DockerException, APIError
from docker.models.containers import Container
from typing import Tuple, Dict, Optional, Any
from pathlib import Path
import logging

from .runtime_adapter import ContainerAdapter, ContainerHandle
from .compat import ContainerCompat


class DockerHandle(ContainerHandle):
    """
    Docker 容器句柄

    封装 Docker Container 对象，实现统一的容器接口。
    """

    def __init__(self, container: Container, logger: logging.Logger = None):
        """
        初始化 Docker 容器句柄

        Args:
            container: Docker Container 对象
            logger: 日志记录器（可选）
        """
        self._container = container
        self._logger = logger or logging.getLogger(__name__)

    def start(self):
        """启动容器"""
        try:
            self._container.start()
            self._logger.info(f"▶️ 容器已启动: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器启动失败: {e}") from e

    def stop(self, timeout: int = 5):
        """停止容器"""
        try:
            self._container.stop(timeout=timeout)
            self._logger.info(f"🛑 容器已停止: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器停止失败: {e}") from e

    def pause(self):
        """暂停容器"""
        try:
            self._container.pause()
            self._logger.info(f"⏸️ 容器已暂停: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器暂停失败: {e}") from e

    def unpause(self):
        """恢复暂停的容器"""
        try:
            self._container.unpause()
            self._logger.info(f"▶️ 容器已恢复: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器恢复失败: {e}") from e

    def reload(self):
        """刷新容器状态"""
        try:
            self._container.reload()
        except APIError as e:
            raise RuntimeError(f"容器状态刷新失败: {e}") from e

    def remove(self):
        """删除容器"""
        try:
            self._container.remove()
            self._logger.info(f"🗑️ 容器已删除: {self._container.name}")
        except APIError as e:
            raise RuntimeError(f"容器删除失败: {e}") from e

    def exec_run(self, cmd: str, **kwargs) -> Tuple[int, bytes]:
        """在容器内执行命令"""
        try:
            return self._container.exec_run(cmd, **kwargs)
        except APIError as e:
            raise RuntimeError(f"命令执行失败: {e}") from e

    @property
    def status(self) -> str:
        """获取容器状态"""
        return ContainerCompat.get_container_status(self._container)

    @property
    def short_id(self) -> str:
        """获取容器短ID"""
        return ContainerCompat.get_short_id(self._container)

    @property
    def attrs(self) -> Dict[str, Any]:
        """获取容器完整属性"""
        return self._container.attrs

    def get_attribute(self, key: str, default: Any = None) -> Any:
        """获取容器指定属性"""
        return self._container.attrs.get(key, default)


class DockerAdapter(ContainerAdapter):
    """
    Docker 运行时适配器

    实现 Docker 的具体功能，遵循 ContainerAdapter 接口。
    """

    def __init__(self, logger: logging.Logger = None):
        """
        初始化 Docker 适配器

        Args:
            logger: 日志记录器（可选）

        Raises:
            RuntimeError: Docker 连接失败
        """
        self._logger = logger or logging.getLogger(__name__)

        try:
            self.client = docker.from_env()
            self._logger.info("✅ Docker 客户端初始化成功")
        except DockerException as e:
            raise RuntimeError(f"Docker 连接失败: {e}") from e

    def ping(self) -> bool:
        """测试与 Docker 的连接"""
        try:
            self.client.ping()
            self._logger.info("✅ Docker 连接正常")
            return True
        except DockerException as e:
            self._logger.error(f"❌ Docker 连接失败: {e}")
            raise

    def ensure_running(self) -> bool:
        """
        确保 Docker 正在运行

        注意：Docker 的启动逻辑应该在系统初始化时完成，
        这里只负责连接测试。

        Returns:
            bool: 成功返回 True
        """
        return self.ping()

    def create_container(
        self,
        name: str,
        image: str,
        volumes: Dict[str, Dict[str, str]],
        **kwargs
    ) -> DockerHandle:
        """创建容器"""
        try:
            # 标准化卷配置
            normalized_volumes = ContainerCompat.normalize_volume_config(volumes)

            # 创建容器
            container = self.client.containers.create(
                image=image,
                name=name,
                volumes=normalized_volumes,
                **kwargs
            )

            self._logger.info(f"✅ 容器创建成功: {name} ({container.short_id})")
            return DockerHandle(container, self._logger)

        except APIError as e:
            raise RuntimeError(f"容器创建失败: {e}") from e

    def get_container(self, name: str) -> Optional[DockerHandle]:
        """获取已存在的容器"""
        try:
            container = self.client.containers.get(name)
            self._logger.info(f"📦 找到已存在的容器: {name}")
            return DockerHandle(container, self._logger)
        except APIError:
            return None

    def close(self):
        """关闭 Docker 连接"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
                self._logger.info("✅ Docker 连接已关闭")
        except Exception as e:
            self._logger.warning(f"关闭 Docker 连接时出错: {e}")
