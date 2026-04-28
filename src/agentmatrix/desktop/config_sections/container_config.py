"""
Container Configuration Section - 容器运行时配置节

提供容器运行时配置的类型安全访问。
"""

from typing import Dict, Any
import os


class ContainerConfigSection:
    """
    容器运行时配置节

    提供容器运行时配置的访问接口。

    配置项：
    - runtime: 运行时类型（auto, docker, podman）
    - auto_start: 是否自动启动运行时
    - fallback_strategy: 降级策略（fallback, error）

    Examples:
        >>> config.container.runtime_type
        'auto'
        >>> config.container.auto_start
        True
    """

    def __init__(self, container_config: Dict[str, Any]):
        """
        初始化容器运行时配置节

        Args:
            container_config: 容器运行时配置字典
        """
        self._config = container_config

    @property
    def runtime_type(self) -> str:
        """
        获取运行时类型

        优先级：
        1. 环境变量 CONTAINER_RUNTIME
        2. 配置文件中的 runtime 值
        3. 默认值 'auto'

        Returns:
            str: 运行时类型 ('auto', 'docker', 'podman')
        """
        # 优先使用环境变量
        env_runtime = os.getenv('CONTAINER_RUNTIME')
        if env_runtime:
            return env_runtime.lower()

        # 其次使用配置文件
        return self._config.get('runtime', 'auto').lower()

    @property
    def auto_start(self) -> bool:
        """
        是否自动启动运行时

        优先级：
        1. 环境变量 CONTAINER_AUTO_START
        2. 配置文件中的 auto_start 值
        3. 默认值 True

        Returns:
            bool: 是否自动启动
        """
        # 优先使用环境变量
        env_auto_start = os.getenv('CONTAINER_AUTO_START')
        if env_auto_start:
            return env_auto_start.lower() in ('true', '1', 'yes', 'on')

        # 其次使用配置文件
        return self._config.get('auto_start', True)

    @property
    def fallback_strategy(self) -> str:
        """
        获取降级策略

        当首选运行时不可用时的处理方式：
        - fallback: 尝试使用其他可用运行时
        - error: 直接抛出错误

        Returns:
            str: 降级策略 ('fallback', 'error')
        """
        return self._config.get('fallback_strategy', 'fallback').lower()

    def is_runtime_specified(self) -> bool:
        """
        检查是否明确指定了运行时类型

        Returns:
            bool: 如果用户明确指定了运行时（非 auto）返回 True
        """
        return self.runtime_type != 'auto'

    def get_full_config(self) -> Dict[str, Any]:
        """
        获取完整的容器运行时配置

        Returns:
            Dict: 完整配置字典
        """
        return {
            'runtime': self.runtime_type,
            'auto_start': self.auto_start,
            'fallback_strategy': self.fallback_strategy,
        }

    def __repr__(self) -> str:
        return (
            f"ContainerConfigSection("
            f"runtime='{self.runtime_type}', "
            f"auto_start={self.auto_start}, "
            f"fallback_strategy='{self.fallback_strategy}')"
        )
