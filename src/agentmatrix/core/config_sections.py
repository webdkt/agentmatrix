"""
Configuration Sections - 配置节类

职责：
1. 提供类型安全的配置访问
2. 封装配置验证逻辑
3. 提供清晰的配置接口
"""

from typing import Dict, Any, Optional
from pathlib import Path


class LLMConfigSection:
    """
    LLM配置节

    提供LLM配置的访问接口
    """

    def __init__(self, llm_config: Dict[str, Any]):
        """
        初始化LLM配置节

        Args:
            llm_config: LLM配置字典
        """
        self._config = llm_config

    def get_model_config(self, model_name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定模型的配置

        Args:
            model_name: 模型名称（如 'default_llm', 'default_slm'）

        Returns:
            模型配置字典，如果不存在返回None
        """
        return self._config.get(model_name)

    @property
    def default_llm(self) -> Dict[str, Any]:
        """获取默认LLM配置"""
        config = self.get_model_config('default_llm')
        if not config:
            raise ValueError("default_llm 配置不存在")
        return config

    @property
    def default_slm(self) -> Dict[str, Any]:
        """获取默认SLM配置"""
        config = self.get_model_config('default_slm')
        if not config:
            raise ValueError("default_slm 配置不存在")
        return config

    @property
    def default_vision(self) -> Optional[Dict[str, Any]]:
        """获取默认Vision配置（可选）"""
        return self.get_model_config('default_vision')

    def get_model_url(self, model_name: str) -> Optional[str]:
        """获取模型的URL"""
        config = self.get_model_config(model_name)
        return config.get('url') if config else None

    def get_model_api_key(self, model_name: str) -> Optional[str]:
        """获取模型的API Key"""
        config = self.get_model_config(model_name)
        return config.get('API_KEY') if config else None

    def get_model_name(self, model_name: str) -> Optional[str]:
        """获取模型的名称"""
        config = self.get_model_config(model_name)
        return config.get('model_name') if config else None

    def list_models(self) -> list:
        """列出所有可用的模型"""
        return list(self._config.keys())

    def __repr__(self) -> str:
        return f"LLMConfigSection(models={self.list_models()})"


class EmailProxyConfigSection:
    """
    Email Proxy配置节

    提供Email Proxy配置的访问接口
    """

    def __init__(self, email_proxy_config: Dict[str, Any]):
        """
        初始化Email Proxy配置节

        Args:
            email_proxy_config: Email Proxy配置字典
        """
        self._config = email_proxy_config

    @property
    def enabled(self) -> bool:
        """是否启用Email Proxy"""
        return self._config.get('enabled', False)

    @property
    def matrix_mailbox(self) -> str:
        """Matrix邮箱地址"""
        return self._config.get('matrix_mailbox', '')

    @property
    def user_mailbox(self) -> str:
        """用户邮箱地址"""
        return self._config.get('user_mailbox', '')

    @property
    def imap_config(self) -> Dict[str, Any]:
        """IMAP配置"""
        return self._config.get('imap', {})

    @property
    def smtp_config(self) -> Dict[str, Any]:
        """SMTP配置"""
        return self._config.get('smtp', {})

    def is_configured(self) -> bool:
        """
        检查Email Proxy是否已正确配置

        Returns:
            True如果已配置，否则False
        """
        if not self.enabled:
            return False

        required_fields = [
            self.matrix_mailbox,
            self.user_mailbox,
            self.imap_config.get('host'),
            self.imap_config.get('port'),
            self.imap_config.get('user'),
            self.imap_config.get('password'),
            self.smtp_config.get('host'),
            self.smtp_config.get('port'),
            self.smtp_config.get('user'),
            self.smtp_config.get('password'),
        ]

        return all(field for field in required_fields)

    def get_full_config(self) -> Optional[Dict[str, Any]]:
        """
        获取完整的Email Proxy配置

        Returns:
            完整配置字典，如果未配置返回None
        """
        if not self.is_configured():
            return None

        return {
            'matrix_mailbox': self.matrix_mailbox,
            'user_mailbox': self.user_mailbox,
            'imap': self.imap_config,
            'smtp': self.smtp_config,
        }

    def __repr__(self) -> str:
        return f"EmailProxyConfigSection(enabled={self.enabled}, configured={self.is_configured()})"


class MatrixConfigSection:
    """
    Matrix配置节

    提供Matrix全局配置的访问接口
    """

    def __init__(self, matrix_config: Dict[str, Any]):
        """
        初始化Matrix配置节

        Args:
            matrix_config: Matrix配置字典
        """
        self._config = matrix_config

    @property
    def user_agent_name(self) -> str:
        """用户Agent名称"""
        return self._config.get('user_agent_name', 'User')

    @property
    def matrix_version(self) -> str:
        """Matrix版本"""
        return self._config.get('matrix_version', '1.0.0')

    @property
    def description(self) -> str:
        """Matrix描述"""
        return self._config.get('description', '')

    @property
    def timezone(self) -> str:
        """时区"""
        return self._config.get('timezone', 'UTC')

    def __repr__(self) -> str:
        return f"MatrixConfigSection(user_agent='{self.user_agent_name}', version='{self.matrix_version}')"
