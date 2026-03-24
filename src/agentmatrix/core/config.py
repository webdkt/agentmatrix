"""
Matrix Configuration Manager - 统一的配置管理器

职责：
1. 加载所有配置文件
2. 提供统一的配置访问接口
3. 管理配置验证
4. 支持环境变量解析
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from .log_util import AutoLoggerMixin
from .paths import MatrixPaths
from .config_sections import (
    LLMConfigSection,
    EmailProxyConfigSection,
    MatrixConfigSection,
    ContainerConfigSection,
)


class MatrixConfig(AutoLoggerMixin):
    """
    统一的配置管理器

    管理所有Matrix配置，包括LLM、Email Proxy、Matrix等配置
    """

    def __init__(self, paths: MatrixPaths):
        """
        初始化配置管理器

        Args:
            paths: MatrixPaths实例
        """
        self.paths = paths
        self._load_configs()

    def _load_configs(self):
        """加载所有配置"""
        self._load_llm_config()
        self._load_email_proxy_config()
        self._load_matrix_config()
        self._load_container_config()

    def _load_llm_config(self):
        """加载LLM配置"""
        llm_config_path = self.paths.llm_config_path

        if llm_config_path.exists():
            self.logger.info(f"📄 加载LLM配置: {llm_config_path}")
            with open(llm_config_path, "r", encoding="utf-8") as f:
                self._llm_config = json.load(f)
        else:
            self.logger.warning(f"⚠️ LLM配置文件不存在: {llm_config_path}")
            self._llm_config = self._get_default_llm_config()

        # 验证必需的配置
        if "default_slm" not in self._llm_config:
            raise ValueError("llm_config.json 中必须包含 'default_slm' 配置")

    def _load_email_proxy_config(self):
        """加载Email Proxy配置 - 从 email_proxy_config.yml 中读取"""
        email_proxy_path = self.paths.email_proxy_config_path

        if email_proxy_path.exists():
            self.logger.info(f"📄 加载Email Proxy配置: {email_proxy_path}")
            with open(email_proxy_path, "r", encoding="utf-8") as f:
                ep_data = yaml.safe_load(f) or {}
            self._email_proxy_config = {"email_proxy": ep_data}
            self._email_proxy_config = self._resolve_env_vars(self._email_proxy_config)
        else:
            # 向后兼容：尝试从 matrix_config.yml 读取
            matrix_config_path = self.paths.matrix_config_path
            if matrix_config_path.exists():
                self.logger.info(
                    f"📄 向后兼容：从 matrix_config.yml 加载 Email Proxy 配置"
                )
                with open(matrix_config_path, "r", encoding="utf-8") as f:
                    full_config = yaml.safe_load(f) or {}
                self._email_proxy_config = {
                    "email_proxy": full_config.get("email_proxy", {})
                }
                self._email_proxy_config = self._resolve_env_vars(
                    self._email_proxy_config
                )
            else:
                self._email_proxy_config = self._get_default_email_proxy_config()

    def _load_matrix_config(self):
        """加载系统配置 - 从 system_config.yml 中读取"""
        system_config_path = self.paths.system_config_path

        if system_config_path.exists():
            self.logger.info(f"📄 加载系统配置: {system_config_path}")
            with open(system_config_path, "r", encoding="utf-8") as f:
                self._matrix_config = yaml.safe_load(f) or {}
        else:
            # 向后兼容：尝试从 matrix_config.yml 读取
            matrix_config_path = self.paths.matrix_config_path
            if matrix_config_path.exists():
                self.logger.info(f"📄 向后兼容：从 matrix_config.yml 加载系统配置")
                with open(matrix_config_path, "r", encoding="utf-8") as f:
                    full_config = yaml.safe_load(f) or {}
                # 只提取系统配置字段，排除 email_proxy 和 container
                self._matrix_config = {
                    k: v
                    for k, v in full_config.items()
                    if k not in ("email_proxy", "container")
                }
            else:
                self.logger.info(f"📄 使用默认系统配置")
                self._matrix_config = self._get_default_matrix_config()

    def _load_container_config(self):
        """加载容器运行时配置"""
        # 容器配置包含在 matrix_config.yml 中
        # 从已加载的 matrix_config 中提取 container 部分
        container_config = self._matrix_config.get("container", {})

        # 如果配置为空，使用默认值
        if not container_config:
            self.logger.info("📄 使用默认容器运行时配置")
            container_config = self._get_default_container_config()

        self._container_config = container_config

    def _get_default_llm_config(self) -> Dict[str, Any]:
        """获取默认LLM配置"""
        return {
            "default_llm": {
                "url": "https://api.anthropic.com/v1/messages",
                "API_KEY": "ANTHROPIC_API_KEY",
                "model_name": "claude-sonnet-4-20250514",
            },
            "default_slm": {
                "url": "https://api.anthropic.com/v1/messages",
                "API_KEY": "ANTHROPIC_API_KEY",
                "model_name": "claude-haiku-4-20250514",
            },
        }

    def _get_default_email_proxy_config(self) -> Dict[str, Any]:
        """获取默认Email Proxy配置"""
        return {
            "email_proxy": {
                "enabled": False,
                "matrix_mailbox": "",
                "user_mailbox": "",
                "imap": {
                    "host": "imap.gmail.com",
                    "port": 993,
                    "user": "",
                    "password": "",
                },
                "smtp": {
                    "host": "smtp.gmail.com",
                    "port": 587,
                    "user": "",
                    "password": "",
                },
            }
        }

    def _get_default_matrix_config(self) -> Dict[str, Any]:
        """获取默认Matrix配置"""
        return {
            "user_agent_name": "User",
            "matrix_version": "1.0.0",
            "description": "AgentMatrix World",
            "timezone": "UTC",
        }

    def _get_default_container_config(self) -> Dict[str, Any]:
        """获取默认容器运行时配置"""
        return {
            "runtime": "auto",  # 自动检测（Podman 优先）
            "auto_start": True,
            "fallback_strategy": "fallback",
        }

    def _resolve_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        递归解析配置中的环境变量

        支持格式：
        - ${ENV_VAR}
        - $ENV_VAR

        Args:
            config: 配置字典

        Returns:
            解析后的配置字典
        """

        def resolve_value(value):
            if isinstance(value, str):
                # 优先匹配 ${ENV_VAR} 格式
                if value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    return os.environ.get(env_var, value)
                # 其次匹配 $ENV_VAR 格式
                elif value.startswith("$") and not value.startswith("${"):
                    env_var = value[1:]
                    return os.environ.get(env_var, value)
                return value
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(item) for item in value]
            return value

        return resolve_value(config)

    def _save_llm_config(self):
        """保存LLM配置到文件"""
        self.paths.llm_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.paths.llm_config_path, "w", encoding="utf-8") as f:
            json.dump(self._llm_config, f, ensure_ascii=False, indent=2)

    def _save_email_proxy_config(self):
        """保存Email Proxy配置到 email_proxy_config.yml"""
        email_proxy_path = self.paths.email_proxy_config_path
        email_proxy_path.parent.mkdir(parents=True, exist_ok=True)
        ep_data = self._email_proxy_config.get("email_proxy", {})
        with open(email_proxy_path, "w", encoding="utf-8") as f:
            yaml.dump(ep_data, f, allow_unicode=True, default_flow_style=False)

    def _save_matrix_config(self):
        """保存系统配置到 system_config.yml"""
        self.paths.system_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.paths.system_config_path, "w", encoding="utf-8") as f:
            yaml.dump(
                self._matrix_config, f, allow_unicode=True, default_flow_style=False
            )

    @property
    def llm(self) -> LLMConfigSection:
        """
        LLM配置节

        提供对LLM配置的类型安全访问

        Examples:
            >>> config.llm.default_llm['url']
            'https://api.anthropic.com/v1/messages'
            >>> config.llm.get_model_url('default_llm')
            'https://api.anthropic.com/v1/messages'
        """
        return LLMConfigSection(self._llm_config)

    @property
    def email_proxy(self) -> EmailProxyConfigSection:
        """
        Email Proxy配置节

        提供对Email Proxy配置的类型安全访问

        Examples:
            >>> config.email_proxy.enabled
            False
            >>> config.email_proxy.is_configured()
            True
        """
        email_proxy_config = self._email_proxy_config.get("email_proxy", {})
        return EmailProxyConfigSection(email_proxy_config)

    @property
    def matrix(self) -> MatrixConfigSection:
        """
        Matrix配置节

        提供对Matrix全局配置的类型安全访问

        Examples:
            >>> config.matrix.user_agent_name
            'User'
            >>> config.matrix.matrix_version
            '1.0.0'
        """
        return MatrixConfigSection(self._matrix_config)

    @property
    def container(self) -> ContainerConfigSection:
        """
        容器运行时配置节

        提供对容器运行时配置的类型安全访问

        Examples:
            >>> config.container.runtime_type
            'auto'
            >>> config.container.auto_start
            True
        """
        return ContainerConfigSection(self._container_config)

    def get(self, key: str, default=None) -> Any:
        """
        获取配置项（支持点号分隔的路径）

        Args:
            key: 配置键，支持点号分隔，如 'email_proxy.enabled'
            default: 默认值

        Returns:
            配置值，如果不存在返回默认值

        Examples:
            >>> config.get('email_proxy.enabled', False)
            False
            >>> config.get('matrix.user_agent_name', 'User')
            'User'
        """
        keys = key.split(".")
        value = self._matrix_config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def reload(self):
        """重新加载所有配置文件"""
        self.logger.info("🔄 重新加载配置...")
        self._load_configs()
        self.logger.info("✅ 配置已重新加载")

    def is_email_proxy_enabled(self) -> bool:
        """
        检查Email Proxy是否启用

        Returns:
            True如果Email Proxy已启用且配置完整，否则False
        """
        return self.email_proxy.is_configured()

    def get_email_proxy_config(self) -> Dict[str, Any]:
        """
        获取Email Proxy配置

        Returns:
            Email Proxy配置字典（包含 email_proxy 外层）
        """
        return self._email_proxy_config

    def __repr__(self) -> str:
        return f"MatrixConfig(paths='{self.paths}')"
