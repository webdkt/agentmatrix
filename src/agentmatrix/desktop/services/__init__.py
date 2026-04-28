"""
Services Package - 系统服务包

包含：
- EmailProxyService: 邮件代理服务
- PromptRegistry: Prompt 注册中心
"""

from .email_proxy_service import EmailProxyService
from .prompt_registry import PromptRegistry

__all__ = ["EmailProxyService", "PromptRegistry"]
