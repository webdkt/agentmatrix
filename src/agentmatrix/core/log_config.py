"""
日志配置类

用于统一管理 Agent 各组件的日志行为
"""
import logging
from dataclasses import dataclass
from typing import Optional


@dataclass
class LogConfig:
    """日志配置类

    Attributes:
        enabled: 是否启用日志（默认 True）
        level: 日志级别（默认 DEBUG）
        prefix: 日志前缀模板，支持 {label} 等变量替换
    """
    enabled: bool = True
    level: int = logging.DEBUG
    prefix: str = ""

    @classmethod
    def from_dict(cls, config_dict: Optional[dict] = None) -> 'LogConfig':
        """从字典创建 LogConfig

        Args:
            config_dict: 配置字典，如果为 None 则返回默认配置

        Returns:
            LogConfig 实例
        """
        if config_dict is None:
            return cls()

        return cls(
            enabled=config_dict.get("enabled", True),
            level=cls._parse_level(config_dict.get("level", "DEBUG")),
            prefix=config_dict.get("prefix", "")
        )

    @staticmethod
    def _parse_level(level_str: str) -> int:
        """解析日志级别字符串

        Args:
            level_str: 日志级别字符串（如 "DEBUG", "INFO"）

        Returns:
            日志级别整数值
        """
        return getattr(logging, level_str.upper(), logging.DEBUG)

    def format_prefix(self, **kwargs) -> str:
        """格式化前缀，支持动态变量替换

        Args:
            **kwargs: 用于替换前缀模板中的变量

        Returns:
            格式化后的前缀字符串

        Example:
            >>> config = LogConfig(prefix="[MICRO-{label}]")
            >>> config.format_prefix(label="read_file")
            '[MICRO-read_file]'
        """
        if not self.prefix:
            return ""
        return self.prefix.format(**kwargs)
