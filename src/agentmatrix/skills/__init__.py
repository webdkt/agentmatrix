"""
Skills Module

统一的技能管理模块
"""

from .registry import SKILL_REGISTRY, register_skill

__all__ = [
    "SKILL_REGISTRY",
    "register_skill",
]
