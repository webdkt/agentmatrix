"""
Agent-Matrix: An intelligent agent framework.

Agent-Matrix is a flexible framework for building and managing AI agents
with pluggable skills, backend LLM integrations, and message-based communication.
"""

__version__ = "0.7.0.6"

# Core imports
from .desktop.runtime import AgentMatrix
from .core.message import Email
from .desktop.post_office import PostOffice

__all__ = [
    "AgentMatrix",
    "Email",
    "PostOffice",
    "__version__",
]
