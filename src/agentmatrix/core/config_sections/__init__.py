"""
Configuration Sections - 配置节类

职责：
1. 提供类型安全的配置访问
2. 封装配置验证逻辑
3. 提供清晰的配置接口
"""

from typing import Dict, Any, Optional
import os

from .container_config import ContainerConfigSection


class LLMConfigSection:
    """
    LLM配置节
    提供LLM配置的访问接口
    """

    def __init__(self, llm_config: Dict[str, Any]):
        self._config = llm_config

    def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        return self._config.get(model_name)

    @property
    def default_llm(self) -> Dict[str, Any]:
        config = self.get_model_config("default_llm")
        if not config:
            raise ValueError("default_llm 配置不存在")
        return config

    @property
    def default_slm(self) -> Dict[str, Any]:
        config = self.get_model_config("default_slm")
        if not config:
            raise ValueError("default_slm 配置不存在")
        return config

    @property
    def default_vision(self) -> Optional[Dict[str, Any]]:
        return self.get_model_config("default_vision")

    def get_model_url(self, model_name: str) -> Optional[str]:
        config = self.get_model_config(model_name)
        return config.get("url") if config else None

    def get_model_api_key(self, model_name: str) -> Optional[str]:
        config = self.get_model_config(model_name)
        return config.get("API_KEY") if config else None

    def get_model_name(self, model_name: str) -> Optional[str]:
        config = self.get_model_config(model_name)
        return config.get("model_name") if config else None

    def list_models(self) -> list:
        return list(self._config.keys())

    def __repr__(self) -> str:
        return f"LLMConfigSection(models={self.list_models()})"


class EmailProxyConfigSection:
    """
    Email Proxy配置节
    提供Email Proxy配置的访问接口
    """

    def __init__(self, email_proxy_config: Dict[str, Any]):
        self._config = email_proxy_config

    @property
    def enabled(self) -> bool:
        return self._config.get("enabled", False)

    @property
    def matrix_mailbox(self) -> str:
        return self._config.get("matrix_mailbox", "")

    @property
    def user_mailbox(self) -> str:
        return self._config.get("user_mailbox", "")

    @property
    def imap_config(self) -> Dict[str, Any]:
        return self._config.get("imap", {})

    @property
    def smtp_config(self) -> Dict[str, Any]:
        return self._config.get("smtp", {})

    def is_configured(self) -> bool:
        if not self.enabled:
            return False
        required_fields = [
            self.matrix_mailbox,
            self.user_mailbox,
            self.imap_config.get("host"),
            self.imap_config.get("port"),
            self.imap_config.get("user"),
            self.imap_config.get("password"),
            self.smtp_config.get("host"),
            self.smtp_config.get("port"),
            self.smtp_config.get("user"),
            self.smtp_config.get("password"),
        ]
        return all(field for field in required_fields)

    def get_full_config(self) -> Optional[Dict[str, Any]]:
        if not self.is_configured():
            return None
        return {
            "matrix_mailbox": self.matrix_mailbox,
            "user_mailbox": self.user_mailbox,
            "imap": self.imap_config,
            "smtp": self.smtp_config,
        }

    def __repr__(self) -> str:
        return f"EmailProxyConfigSection(enabled={self.enabled}, configured={self.is_configured()})"


class MatrixConfigSection:
    """
    Matrix配置节
    提供Matrix全局配置的访问接口
    """

    def __init__(self, matrix_config: Dict[str, Any]):
        self._config = matrix_config

    @property
    def user_agent_name(self) -> str:
        return self._config.get("user_agent_name", "User")

    @property
    def matrix_version(self) -> str:
        return self._config.get("matrix_version", "1.0.0")

    @property
    def description(self) -> str:
        return self._config.get("description", "")

    @property
    def timezone(self) -> str:
        return self._config.get("timezone", "UTC")

    def __repr__(self) -> str:
        return f"MatrixConfigSection(user_agent='{self.user_agent_name}', version='{self.matrix_version}')"


class ProxyConfigSection:
    """
    HTTP Proxy 配置节
    提供 HTTP Proxy 配置的访问接口
    """

    def __init__(self, proxy_config: Dict[str, Any]):
        self._config = proxy_config or {}

    @property
    def enabled(self) -> bool:
        return self._config.get("enabled", False)

    @property
    def host(self) -> str:
        return self._config.get("host", "")

    @property
    def port(self) -> int:
        return self._config.get("port", 0)

    @property
    def http_proxy_url(self) -> str:
        if not self.enabled or not self.host or not self.port:
            return ""
        return f"http://{self.host}:{self.port}"

    def is_configured(self) -> bool:
        if not self.enabled:
            return False
        return bool(self.host and self.port)

    def get_container_proxy_url(self, runtime_type: str) -> str:
        if not self.enabled or not self.port:
            return ""
        if runtime_type == "podman":
            proxy_host = "host.containers.internal"
        else:
            proxy_host = "host.docker.internal"
        return f"http://{proxy_host}:{self.port}"

    def get_full_config(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "host": self.host,
            "port": self.port,
        }

    def __repr__(self) -> str:
        return f"ProxyConfigSection(enabled={self.enabled}, host='{self.host}', port={self.port})"
