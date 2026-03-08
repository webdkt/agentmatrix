"""
Markdown Skill - Markdown 文档编辑能力

提供超大 Markdown 文件的编辑、查找、总结等功能。
"""

from ..registry import SKILL_REGISTRY
from .skill import MarkdownSkillMixin

# 注册 skill
SKILL_REGISTRY.register_python_mixin("markdown", MarkdownSkillMixin)

__all__ = ["MarkdownSkillMixin"]
