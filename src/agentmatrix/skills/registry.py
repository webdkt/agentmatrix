"""
Skill Registry - 统一的技能注册中心

支持两种类型的技能：
1. Python Method Skills: 提供 Python 实现的 Mixin 类
2. MD Document Skills: 从 skills.md 加载的文档技能（TODO）
"""

from typing import Dict, List, Optional, Type
import logging

logger = logging.getLogger(__name__)


class SkillRegistry:
    """统一的 Skill 注册中心"""

    def __init__(self):
        # Python Mixin 注册表: skill_name -> mixin_class
        self._python_mixins: Dict[str, Type] = {}

        # MD Document Action 注册表: skill_name -> List[ActionMetadata] (TODO)
        self._md_actions: Dict[str, List] = {}

    def register_python_mixin(self, name: str, mixin_class: Type):
        """
        注册 Python Mixin Skill

        Args:
            name: Skill 名称（如 "file", "browser"）
            mixin_class: Mixin 类
        """
        self._python_mixins[name] = mixin_class
        logger.debug(f"  ✅ 注册 Python Mixin: {name} -> {mixin_class.__name__}")

    def get_python_mixins(self, skill_names: List[str]) -> List[Type]:
        """
        获取指定的 Python Mixin 类

        Args:
            skill_names: Skill 名称列表

        Returns:
            List[Type]: Mixin 类列表
        """
        mixins = []
        for name in skill_names:
            if name in self._python_mixins:
                mixins.append(self._python_mixins[name])
            else:
                logger.warning(f"  ⚠️  未找到 Skill: {name}")
        return mixins

    def get_md_actions(self, skill_names: List[str]) -> List:
        """
        获取指定的 MD Document Actions

        TODO: 实现 MD Document 加载
        """
        actions = []
        for name in skill_names:
            if name in self._md_actions:
                actions.extend(self._md_actions[name])
        return actions

    def list_registered_skills(self) -> Dict[str, List[str]]:
        """
        列出所有已注册的技能

        Returns:
            Dict: {"python": [...], "md": [...]}
        """
        return {
            "python": list(self._python_mixins.keys()),
            "md": list(self._md_actions.keys())
        }


# 全局单例
SKILL_REGISTRY = SkillRegistry()


def register_skill(name: str):
    """
    Skill 注册装饰器

    用法：
        @register_skill("file")
        class FileSkillMixin:
            pass

    Args:
        name: Skill 名称
    """
    def decorator(mixin_class):
        SKILL_REGISTRY.register_python_mixin(name, mixin_class)
        return mixin_class
    return decorator
