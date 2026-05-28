"""
Configuration Sections - 配置数据类

职责：
1. 提供类型安全的配置访问
2. 支持 from_dict / to_dict 序列化
3. 纯数据类，不知道文件路径
"""

from .container_config import ContainerConfigSection
from typing import Any, Dict, List, Optional


class LLMConfigSection:
    """LLM配置 — 包装 llm_config.json 的数据"""

    def __init__(self, llm_config: Dict[str, Any]):
        self._config = llm_config

    # ── 读取 ──

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

    # ── 写入 ──

    def set_model_config(self, name: str, config: Dict[str, Any]) -> None:
        self._config[name] = config

    def remove_model(self, name: str) -> None:
        self._config.pop(name, None)

    # ── 序列化 ──

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMConfigSection":
        return cls(dict(data))

    def __repr__(self) -> str:
        return f"LLMConfigSection(models={self.list_models()})"


class EmailProxyConfigSection:
    """Email Proxy配置"""

    def __init__(self, email_proxy_config: Dict[str, Any]):
        self._config = email_proxy_config or {}

    @property
    def enabled(self) -> bool:
        return self._config.get("enabled", False)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._config["enabled"] = value

    @property
    def matrix_mailbox(self) -> str:
        return self._config.get("matrix_mailbox", "")

    @matrix_mailbox.setter
    def matrix_mailbox(self, value: str) -> None:
        self._config["matrix_mailbox"] = value

    @property
    def user_mailbox(self) -> str:
        return self._config.get("user_mailbox", "")

    @user_mailbox.setter
    def user_mailbox(self, value: str) -> None:
        self._config["user_mailbox"] = value

    @property
    def imap_config(self) -> Dict[str, Any]:
        return self._config.get("imap", {})

    @imap_config.setter
    def imap_config(self, value: Dict[str, Any]) -> None:
        self._config["imap"] = value

    @property
    def smtp_config(self) -> Dict[str, Any]:
        return self._config.get("smtp", {})

    @smtp_config.setter
    def smtp_config(self, value: Dict[str, Any]) -> None:
        self._config["smtp"] = value

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

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EmailProxyConfigSection":
        return cls(dict(data))

    def __repr__(self) -> str:
        return f"EmailProxyConfigSection(enabled={self.enabled}, configured={self.is_configured()})"


class MatrixConfigSection:
    """系统配置（system_config.yml）"""

    def __init__(self, matrix_config: Dict[str, Any]):
        self._config = matrix_config

    @property
    def user_agent_name(self) -> str:
        return self._config.get("user_agent_name", "User")

    @user_agent_name.setter
    def user_agent_name(self, value: str) -> None:
        self._config["user_agent_name"] = value

    @property
    def matrix_version(self) -> str:
        return self._config.get("matrix_version", "1.0.0")

    @property
    def description(self) -> str:
        return self._config.get("description", "")

    @property
    def timezone(self) -> str:
        return self._config.get("timezone", "UTC")

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatrixConfigSection":
        return cls(dict(data))

    def __repr__(self) -> str:
        return f"MatrixConfigSection(user_agent='{self.user_agent_name}', version='{self.matrix_version}')"


class ProxyConfigSection:
    """HTTP Proxy 配置"""

    def __init__(self, proxy_config: Dict[str, Any]):
        self._config = proxy_config or {}

    @property
    def enabled(self) -> bool:
        return self._config.get("enabled", False)

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._config["enabled"] = value

    @property
    def host(self) -> str:
        return self._config.get("host", "")

    @host.setter
    def host(self, value: str) -> None:
        self._config["host"] = value

    @property
    def port(self) -> int:
        return self._config.get("port", 0)

    @port.setter
    def port(self, value: int) -> None:
        self._config["port"] = value

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

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProxyConfigSection":
        return cls(dict(data))

    def __repr__(self) -> str:
        return f"ProxyConfigSection(enabled={self.enabled}, host='{self.host}', port={self.port})"