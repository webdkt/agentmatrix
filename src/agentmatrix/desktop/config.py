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
from dotenv import load_dotenv
from ..core.log_util import AutoLoggerMixin
from .paths import MatrixPaths
from .config_sections import (
    LLMConfigSection,
    EmailProxyConfigSection,
    MatrixConfigSection,
    ContainerConfigSection,
    ProxyConfigSection,
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
        self._load_dotenv()
        self._load_llm_config()
        self._load_email_proxy_config()
        self._load_matrix_config()
        self._load_container_config()
        self._load_proxy_config()
        self._apply_proxy_env_vars()

    def _load_dotenv(self):
        """加载 .env 文件中的环境变量

        优先级：Shell 环境变量 > .env 文件 > 配置文件原始值
        使用 override=False 确保不会覆盖已有的 shell 环境变量
        """
        env_path = self.paths.env_path
        if env_path.exists():
            self.logger.info(f"📄 加载环境变量文件: {env_path}")
            load_dotenv(env_path, override=False)
        else:
            self.logger.debug(f"📄 环境变量文件不存在，跳过: {env_path}")

    def _load_llm_config(self):
        """加载LLM配置"""
        llm_config_path = self.paths.llm_config_path

        if llm_config_path.exists():
            self.logger.info(f"📄 加载LLM配置: {llm_config_path}")
            with open(llm_config_path, "r", encoding="utf-8") as f:
                self._llm_config = json.load(f)
        else:
            self.logger.error(f"⚠️ LLM配置文件不存在: {llm_config_path}")
            raise ValueError("LLM Config 缺失")

        # 验证必需的配置
        if "default_slm" not in self._llm_config:
            raise ValueError("llm_config.json 中必须包含 'default_slm' 配置")
        if "default_llm" not in self._llm_config:
            raise ValueError("llm_config.json 中必须包含 'default_llm' 配置")

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
            return {}

    def _load_matrix_config(self):
        """加载系统配置 - 从 system_config.yml 中读取"""
        system_config_path = self.paths.system_config_path

        if system_config_path.exists():
            self.logger.info(f"📄 加载系统配置: {system_config_path}")
            with open(system_config_path, "r", encoding="utf-8") as f:
                self._matrix_config = yaml.safe_load(f) or {}
        else:
            self.logger.warning(f"⚠️ system_config.yml not found at {system_config_path}, using empty config")
            self._matrix_config = {}

    def _load_container_config(self):
        """加载容器运行时配置"""
        # 容器配置包含在 matrix_config.yml 中
        # 从已加载的 matrix_config 中提取 container 部分
        container_config = self._matrix_config.get("container", {})

        # 如果配置为空，使用默认值
        if not container_config:
            self.logger.info("📄 使用默认容器运行时配置")
            container_config = {
                "runtime": "auto",  # 自动检测（Podman 优先）
                "auto_start": True,
                "fallback_strategy": "fallback",
            }

        self._container_config = container_config

    def _load_proxy_config(self):
        """从 system_config.yml 中提取 proxy 配置"""
        self._proxy_config = self._matrix_config.get("proxy", {})
        if self._proxy_config:
            self.logger.info(
                f"📄 加载 HTTP Proxy 配置: {self._proxy_config.get('host', '')}:{self._proxy_config.get('port', '')}"
            )

    def _apply_proxy_env_vars(self):
        """设置 HTTP_PROXY/HTTPS_PROXY 环境变量

        优先级策略：
        1. App proxy 启用且配置完整 → 覆盖为 app 配置的代理
        2. App proxy 未启用 → 保留系统环境变量不动（不删除）
        """
        proxy = self._proxy_config
        if proxy and proxy.get("enabled") and proxy.get("host") and proxy.get("port"):
            proxy_url = f"http://{proxy['host']}:{proxy['port']}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            self.logger.info(f"✅ HTTP Proxy 已启用: {proxy_url}")
        else:
            # 不删除系统环境变量，让用户配置的代理继续生效
            existing = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
            if existing:
                self.logger.info(f"ℹ️ App proxy 未启用，使用系统代理: {existing}")
            else:
                self.logger.info("ℹ️ App proxy 未启用，无系统代理，直连")

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

    @property
    def proxy(self) -> ProxyConfigSection:
        """
        HTTP Proxy 配置节
        """
        return ProxyConfigSection(self._proxy_config)

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
