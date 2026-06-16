"""
Knowledge Base Agent Skill — 知识管家 Agent 使用的 skill

提供知识库管理、查询、维护等面向用户的 action。
由 KnowledgeBaseAgent 在对话中使用。
"""

import logging

logger = logging.getLogger(__name__)


class AgentSkillMixin:
    """知识管家 Agent skill — 面向用户的知识库操作。"""

    _skill_description = "知识库管理与查询（面向用户）"
    _skill_dependencies = ["file", "markdown"]
