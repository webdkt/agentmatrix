"""
Services Package - 系统服务包

包含：
- AgentService: Agent 生命周期和配置管理
- LLMService: LLM 配置管理和监控
- ProxyService: HTTP 代理配置和连通性测试
- EmailProxyService: 邮件代理服务
- EmailProxyConfigService: 邮件代理配置管理（始终可用）
- PromptRegistry: Prompt 注册中心
"""

from .agent_service import AgentService
from .llm_service import LLMService
from .proxy_service import ProxyService
from .email_proxy_service import EmailProxyService
from .email_proxy_config_service import EmailProxyConfigService
from .prompt_registry import PromptRegistry

__all__ = [
    "AgentService",
    "LLMService",
    "ProxyService",
    "EmailProxyService",
    "EmailProxyConfigService",
    "PromptRegistry",
]