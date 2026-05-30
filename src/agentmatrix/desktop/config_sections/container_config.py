"""
Container Configuration Section - 容器运行时配置数据类

提供容器运行时配置的读写访问和序列化。
"""

import os
from typing import Dict, Any


class ContainerConfigSection:
    """容器运行时配置数据类"""

    def __init__(self, container_config: Dict[str, Any]):
        self._config = container_config

    @property
    def runtime_type(self) -> str:
        env_runtime = os.getenv('CONTAINER_RUNTIME')
        if env_runtime:
            return env_runtime.lower()
        return self._config.get('runtime', 'auto').lower()

    @property
    def auto_start(self) -> bool:
        env_auto_start = os.getenv('CONTAINER_AUTO_START')
        if env_auto_start:
            return env_auto_start.lower() in ('true', '1', 'yes', 'on')
        return self._config.get('auto_start', True)

    @property
    def fallback_strategy(self) -> str:
        return self._config.get('fallback_strategy', 'fallback').lower()

    def is_runtime_specified(self) -> bool:
        return self.runtime_type != 'auto'

    def get_full_config(self) -> Dict[str, Any]:
        return {
            'runtime': self.runtime_type,
            'auto_start': self.auto_start,
            'fallback_strategy': self.fallback_strategy,
        }

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContainerConfigSection":
        return cls(dict(data))

    def __repr__(self) -> str:
        return (
            f"ContainerConfigSection("
            f"runtime='{self.runtime_type}', "
            f"auto_start={self.auto_start}, "
            f"fallback_strategy='{self.fallback_strategy}')"
        )