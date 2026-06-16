"""
Knowledge Base Maintenance Skill — Wiki 维护服务使用的 skill

提供后台 ingest 所需的 action，由 WikiMaintenanceService 的 worker MicroAgent 使用。
"""

import logging

logger = logging.getLogger(__name__)


class MaintenanceSkillMixin:
    """Wiki 维护服务 skill — 后台自主 ingest 使用。"""

    _skill_description = "知识库后台维护（wiki ingest）"
    _skill_dependencies = ["file", "basic_planning"]
