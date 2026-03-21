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
    MatrixConfigSection
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

    def _load_llm_config(self):
        """加载LLM配置"""
        llm_config_path = self.paths.llm_config_path

        if llm_config_path.exists():
            self.logger.info(f"📄 加载LLM配置: {llm_config_path}")
            with open(llm_config_path, 'r', encoding='utf-8') as f:
                self._llm_config = json.load(f)
        else:
            self.logger.info(f"📄 创建默认LLM配置: {llm_config_path}")
            self._llm_config = self._get_default_llm_config()
            self._save_llm_config()

        # 验证必需的配置
        if "default_slm" not in self._llm_config:
            raise ValueError("llm_config.json 中必须包含 'default_slm' 配置")

    def _load_email_proxy_config(self):
        """加载Email Proxy配置"""
        email_proxy_config_path = self.paths.email_proxy_config_path

        if email_proxy_config_path.exists():
            self.logger.info(f"📄 加载Email Proxy配置: {email_proxy_config_path}")
            with open(email_proxy_config_path, 'r', encoding='utf-8') as f:
                self._email_proxy_config = yaml.safe_load(f) or {}
            # 解析环境变量
            self._email_proxy_config = self._resolve_env_vars(self._email_proxy_config)
        else:
            self.logger.info(f"📄 创建默认Email Proxy配置: {email_proxy_config_path}")
            self._email_proxy_config = self._get_default_email_proxy_config()
            self._save_email_proxy_config()

    def _load_matrix_config(self):
        """加载Matrix配置"""
        matrix_config_path = self.paths.matrix_config_path

        if matrix_config_path.exists():
            self.logger.info(f"📄 加载Matrix配置: {matrix_config_path}")
            with open(matrix_config_path, 'r', encoding='utf-8') as f:
                self._matrix_config = yaml.safe_load(f) or {}
        else:
            self.logger.info(f"📄 创建默认Matrix配置: {matrix_config_path}")
            self._matrix_config = self._get_default_matrix_config()
            self._save_matrix_config()

    def _get_default_llm_config(self) -> Dict[str, Any]:
        """获取默认LLM配置"""
        return {
            "default_llm": {
                "url": "https://api.anthropic.com/v1/messages",
                "API_KEY": "ANTHROPIC_API_KEY",
                "model_name": "claude-sonnet-4-20250514"
            },
            "default_slm": {
                "url": "https://api.anthropic.com/v1/messages",
                "API_KEY": "ANTHROPIC_API_KEY",
                "model_name": "claude-haiku-4-20250514"
            }
        }

    def _get_default_email_proxy_config(self) -> Dict[str, Any]:
        """获取默认Email Proxy配置"""
        return {
            'email_proxy': {
                'enabled': False,
                'matrix_mailbox': '',
                'user_mailbox': '',
                'imap': {
                    'host': 'imap.gmail.com',
                    'port': 993,
                    'user': '',
                    'password': ''
                },
                'smtp': {
                    'host': 'smtp.gmail.com',
                    'port': 587,
                    'user': '',
                    'password': ''
                }
            }
        }

    def _get_default_matrix_config(self) -> Dict[str, Any]:
        """获取默认Matrix配置"""
        return {
            'user_agent_name': 'User',
            'matrix_version': '1.0.0',
            'description': 'AgentMatrix World',
            'timezone': 'UTC'
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
                if value.startswith('${') and value.endswith('}'):
                    env_var = value[2:-1]
                    return os.environ.get(env_var, value)
                # 其次匹配 $ENV_VAR 格式
                elif value.startswith('$') and not value.startswith('${'):
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
        with open(self.paths.llm_config_path, 'w', encoding='utf-8') as f:
            json.dump(self._llm_config, f, ensure_ascii=False, indent=2)

    def _save_email_proxy_config(self):
        """保存Email Proxy配置到文件"""
        self.paths.email_proxy_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.paths.email_proxy_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._email_proxy_config, f, allow_unicode=True, default_flow_style=False)

    def _save_matrix_config(self):
        """保存Matrix配置到文件"""
        self.paths.matrix_config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.paths.matrix_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._matrix_config, f, allow_unicode=True, default_flow_style=False)

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
        email_proxy_config = self._email_proxy_config.get('email_proxy', {})
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
        keys = key.split('.')
        value = self._system_config

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
