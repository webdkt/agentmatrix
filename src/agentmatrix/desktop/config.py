"""
Matrix Configuration Manager - 统一的配置管理器

职责：
1. 加载所有配置文件
2. 提供统一的配置访问接口（通过 Section 类）
3. 支持环境变量解析
4. 支持重新加载（reload）

注意：持久化和业务逻辑由 Service 层负责，不在 Config 层。
"""

import os
import yaml
import json
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

    管理所有Matrix配置，包括LLM、Email Proxy、Matrix等配置。
    通过 Section 类提供读写访问，持久化由 Service 层负责。
    """

    def __init__(self, paths: MatrixPaths):
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
        """加载 .env 文件中的环境变量"""
        env_path = self.paths.env_path
        if env_path.exists():
            self.logger.info(f"Loading env file: {env_path}")
            load_dotenv(env_path, override=False)
        else:
            self.logger.debug(f"Env file not found, skipping: {env_path}")

    def _load_llm_config(self):
        """加载LLM配置"""
        llm_config_path = self.paths.llm_config_path
        if llm_config_path.exists():
            self.logger.info(f"Loading LLM config: {llm_config_path}")
            with open(llm_config_path, "r", encoding="utf-8") as f:
                self._llm_config = json.load(f)
        else:
            self.logger.error(f"LLM config missing: {llm_config_path}")
            raise ValueError("LLM Config 缺失")

        if "default_slm" not in self._llm_config:
            raise ValueError("llm_config.json 中必须包含 'default_slm' 配置")
        if "default_llm" not in self._llm_config:
            raise ValueError("llm_config.json 中必须包含 'default_llm' 配置")

    def _load_email_proxy_config(self):
        """加载Email Proxy配置"""
        email_proxy_path = self.paths.email_proxy_config_path
        if email_proxy_path.exists():
            self.logger.info(f"Loading Email Proxy config: {email_proxy_path}")
            with open(email_proxy_path, "r", encoding="utf-8") as f:
                ep_data = yaml.safe_load(f) or {}
            self._email_proxy_config = {"email_proxy": ep_data}
            self._email_proxy_config = self._resolve_env_vars(self._email_proxy_config)
        else:
            self._email_proxy_config = {"email_proxy": {}}

    def _load_matrix_config(self):
        """加载系统配置"""
        system_config_path = self.paths.system_config_path
        if system_config_path.exists():
            self.logger.info(f"Loading system config: {system_config_path}")
            with open(system_config_path, "r", encoding="utf-8") as f:
                self._matrix_config = yaml.safe_load(f) or {}
        else:
            self.logger.warning(f"system_config.yml not found at {system_config_path}, using empty config")
            self._matrix_config = {}

    def _load_container_config(self):
        """加载容器运行时配置"""
        container_config = self._matrix_config.get("container", {})
        if not container_config:
            self.logger.info("Using default container config")
            container_config = {
                "runtime": "auto",
                "auto_start": True,
                "fallback_strategy": "fallback",
            }
        self._container_config = container_config

    def _load_proxy_config(self):
        """从 system_config.yml 中提取 proxy 配置"""
        self._proxy_config = self._matrix_config.get("proxy", {})
        if self._proxy_config:
            self.logger.info(
                f"HTTP Proxy config loaded: {self._proxy_config.get('host', '')}:{self._proxy_config.get('port', '')}"
            )

    def _apply_proxy_env_vars(self):
        """设置 HTTP_PROXY/HTTPS_PROXY 环境变量"""
        proxy = self._proxy_config
        if proxy and proxy.get("enabled") and proxy.get("host") and proxy.get("port"):
            proxy_url = f"http://{proxy['host']}:{proxy['port']}"
            os.environ["HTTP_PROXY"] = proxy_url
            os.environ["HTTPS_PROXY"] = proxy_url
            self.logger.info(f"HTTP Proxy enabled: {proxy_url}")
        else:
            existing = os.environ.get("HTTP_PROXY") or os.environ.get("HTTPS_PROXY")
            if existing:
                self.logger.info(f"App proxy not enabled, using system proxy: {existing}")
            else:
                self.logger.info("App proxy not enabled, no system proxy, direct connection")

    def _resolve_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """递归解析配置中的环境变量（${ENV_VAR} 或 $ENV_VAR 格式）"""
        def resolve_value(value):
            if isinstance(value, str):
                if value.startswith("${") and value.endswith("}"):
                    env_var = value[2:-1]
                    return os.environ.get(env_var, value)
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

    # ── Section 属性（读写，修改会反映到内部 dict）──

    @property
    def llm(self) -> LLMConfigSection:
        """LLM配置节 — 读写访问"""
        return LLMConfigSection(self._llm_config)

    @property
    def email_proxy(self) -> EmailProxyConfigSection:
        """Email Proxy配置节 — 读写访问"""
        email_proxy_config = self._email_proxy_config.get("email_proxy", {})
        return EmailProxyConfigSection(email_proxy_config)

    @property
    def matrix(self) -> MatrixConfigSection:
        """系统配置节 — 读写访问"""
        return MatrixConfigSection(self._matrix_config)

    @property
    def container(self) -> ContainerConfigSection:
        """容器运行时配置节 — 读写访问"""
        return ContainerConfigSection(self._container_config)

    @property
    def proxy(self) -> ProxyConfigSection:
        """HTTP Proxy 配置节 — 读写访问"""
        return ProxyConfigSection(self._proxy_config)

    # ── 便捷方法 ──

    def get(self, key: str, default=None) -> Any:
        """获取配置项（支持点号分隔的路径，基于 matrix_config）"""
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
        self.logger.info("Reloading configs...")
        self._load_configs()
        self.logger.info("Configs reloaded")

    def is_email_proxy_enabled(self) -> bool:
        """检查Email Proxy是否启用且配置完整"""
        return self.email_proxy.is_configured()

    def get_email_proxy_config(self) -> Dict[str, Any]:
        """获取Email Proxy配置（包含 email_proxy 外层键）"""
        return self._email_proxy_config

    def get_default_llm_config(self) -> Dict[str, Any]:
        """获取默认LLM配置（用于 reset）"""
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

    def __repr__(self) -> str:
        return f"MatrixConfig(paths='{self.paths}')"