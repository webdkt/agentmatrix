"""
Container Runtime Compatibility Utilities - 容器运行时兼容性工具

处理 Docker 和 Podman 之间的 API 差异。
"""

from typing import Any


class ContainerCompat:
    """
    容器运行时兼容性工具

    提供统一的接口来处理 Docker 和 Podman 之间的 API 差异。
    """

    @staticmethod
    def get_short_id(container: Any) -> str:
        """
        获取容器短ID（兼容 Docker 和 Podman）

        差异处理：
        - Docker: container.short_id (直接属性)
        - Podman: container.attrs['Id'][:12] (需要从 attrs 获取)

        Args:
            container: 容器对象（Docker Container 或 Podman Container）

        Returns:
            str: 容器短ID（12字符）

        Examples:
            >>> short_id = ContainerCompat.get_short_id(container)
            >>> print(short_id)
            'a1b2c3d4e5f6'
        """
        try:
            # 尝试直接访问 short_id（Docker 方式）
            return container.short_id
        except AttributeError:
            # 回退到从 attrs 获取（Podman 方式）
            if hasattr(container, 'attrs') and 'Id' in container.attrs:
                return container.attrs['Id'][:12]
            # 最后的回退：尝试 id 属性并截取
            if hasattr(container, 'id'):
                return str(container.id)[:12]
            raise ValueError(f"无法获取容器短ID: {type(container)}")

    @staticmethod
    def get_container_status(container: Any) -> str:
        """
        获取容器状态（统一格式）

        确保 Docker 和 Podman 返回一致的状态字符串。

        Args:
            container: 容器对象

        Returns:
            str: 容器状态（小写）

        Examples:
            >>> status = ContainerCompat.get_container_status(container)
            >>> print(status)
            'running'
        """
        status = container.status
        if isinstance(status, str):
            return status.lower()
        return str(status).lower()

    @staticmethod
    def normalize_volume_config(
        volumes: dict
    ) -> dict:
        """
        标准化卷挂载配置

        确保 Docker 和 Podman 使用相同的卷挂载格式。

        Args:
            volumes: 卷挂载配置

        Returns:
            dict: 标准化后的卷挂载配置

        Examples:
            >>> volumes = {
            ...     '/host/path': {'bind': '/container/path', 'mode': 'rw'}
            ... }
            >>> normalized = ContainerCompat.normalize_volume_config(volumes)
        """
        # 确保所有路径都是字符串
        normalized = {}
        for host_path, config in volumes.items():
            if isinstance(config, dict):
                normalized[str(host_path)] = {
                    'bind': str(config.get('bind', host_path)),
                    'mode': config.get('mode', 'rw')
                }
            else:
                # 简写字符串格式: '/host/path': '/container/path:rw'
                normalized[str(host_path)] = {
                    'bind': str(config),
                    'mode': 'rw'
                }
        return normalized

    @staticmethod
    def detect_runtime_type(client: Any) -> str:
        """
        检测运行时类型

        Args:
            client: 客户端对象

        Returns:
            str: 'docker' 或 'podman'

        Examples:
            >>> runtime_type = ContainerCompat.detect_runtime_type(client)
            >>> print(runtime_type)
            'podman'
        """
        # 通过类名或属性检测
        class_name = client.__class__.__name__.lower()

        if 'podman' in class_name:
            return 'podman'
        elif 'docker' in class_name:
            return 'docker'

        # 尝试通过版本信息检测
        try:
            version = client.version()
            if 'Podman' in str(version):
                return 'podman'
            elif 'Docker' in str(version):
                return 'docker'
        except Exception:
            pass

        # 默认返回 docker
        return 'docker'
