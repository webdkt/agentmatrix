"""
Skill Registry - 统一的技能注册中心

支持两种类型的技能：
1. Python Method Skills: 提供 Python 实现的 Mixin 类
2. MD Document Skills: 从 skills.md 加载的文档技能（TODO）

Lazy Load 机制：
- 根据 skill_name 自动发现并加载技能
- Python Mixin: 查找 {name}_skill.py 中的 {Name}SkillMixin
- MD Document: 查找 skills/{name}.md（未来实现）
"""

from typing import Dict, List, Optional, Type, Tuple
import logging
import importlib
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillLoadResult:
    """技能加载结果"""

    def __init__(self):
        # Python Mixin 类列表
        self.python_mixins: List[Type] = []
        # MD Document Actions（未来实现）
        self.md_actions: List = []
        # 加载失败的技能名称
        self.failed_skills: List[str] = []

    def __repr__(self):
        return (f"SkillLoadResult(mixins={[m.__name__ for m in self.python_mixins]}, "
                f"md_actions={len(self.md_actions)}, "
                f"failed={self.failed_skills})")


class SkillRegistry:
    """统一的 Skill 注册中心（Lazy Load 机制）"""

    def __init__(self):
        # Python Mixin 注册表: skill_name -> mixin_class
        self._python_mixins: Dict[str, Type] = {}

        # MD Document Action 注册表: skill_name -> List[ActionMetadata] (TODO)
        self._md_actions: Dict[str, List] = {}

    def register_python_mixin(self, name: str, mixin_class: Type):
        """
        注册 Python Mixin Skill（手动注册，用于向后兼容）

        Args:
            name: Skill 名称（如 "file", "browser"）
            mixin_class: Mixin 类
        """
        self._python_mixins[name] = mixin_class
        logger.debug(f"  ✅ 注册 Python Mixin: {name} -> {mixin_class.__name__}")

    def get_skills(self, skill_names: List[str]) -> SkillLoadResult:
        """
        根据技能名称列表获取技能（Lazy Load + 统一接口）

        这是新的主要接口，同时支持 Python Mixin 和 MD Document Skills。

        Lazy Load 流程：
        1. 检查缓存（_python_mixins, _md_actions）
        2. 如果未缓存，自动发现并加载：
           - 优先尝试 Python Mixin: {name}_skill.py
           - 如果失败，未来尝试 MD Document: skills/{name}.md

        Args:
            skill_names: 技能名称列表（如 ["file", "browser", "custom_md_skill"]）

        Returns:
            SkillLoadResult: 包含 python_mixins, md_actions, failed_skills
        """
        result = SkillLoadResult()

        for name in skill_names:
            # 尝试加载技能（会自动处理 Python Mixin 和 MD Document）
            success = self._load_skill(name)

            if success == "python":
                # Python Mixin 加载成功
                if name in self._python_mixins:
                    result.python_mixins.append(self._python_mixins[name])
            elif success == "md":
                # MD Document 加载成功
                if name in self._md_actions:
                    result.md_actions.extend(self._md_actions[name])
            else:
                # 加载失败
                result.failed_skills.append(name)

        return result

    def get_python_mixins(self, skill_names: List[str]) -> List[Type]:
        """
        获取指定的 Python Mixin 类（向后兼容接口）

        Args:
            skill_names: Skill 名称列表

        Returns:
            List[Type]: Mixin 类列表
        """
        result = self.get_skills(skill_names)
        return result.python_mixins

    def get_md_actions(self, skill_names: List[str]) -> List:
        """
        获取指定的 MD Document Actions（向后兼容接口）

        TODO: 实现 MD Document 加载
        """
        result = self.get_skills(skill_names)
        return result.md_actions

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

    def _load_skill(self, name: str) -> Optional[str]:
        """
        Lazy Load: 根据名字自动发现并加载技能

        优先级：
        1. 检查缓存（_python_mixins, _md_actions）
        2. 尝试加载 Python Mixin: {name}_skill.py
        3. 尝试加载 MD Document: skills/{name}.md（TODO）

        Args:
            name: 技能名称（如 "file", "browser"）

        Returns:
            Optional[str]: "python" | "md" | None（失败）
        """
        # 1. 检查缓存
        if name in self._python_mixins:
            return "python"
        if name in self._md_actions:
            return "md"

        # 2. 尝试加载 Python Mixin
        if self._try_load_python_mixin(name):
            return "python"

        # 3. 尝试加载 MD Document（未来实现）
        # if self._try_load_md_document(name):
        #     return "md"

        # 全部失败
        logger.warning(f"  ⚠️  未找到 Skill: {name}（既不是 Python Mixin 也不是 MD Document）")
        return None

    def _try_load_python_mixin(self, name: str) -> bool:
        """
        尝试加载 Python Mixin

        名字约定：
        - 模块路径: agentmatrix.skills.{name}_skill
        - 类名: {Name}SkillMixin（首字母大写）

        Examples:
            "file" -> agentmatrix.skills.file_skill.FileSkillMixin
            "browser" -> agentmatrix.skills.browser_skill.BrowserSkillMixin

        Args:
            name: 技能名称

        Returns:
            bool: 是否加载成功
        """
        try:
            # 构造模块路径和类名
            module_name = f"agentmatrix.skills.{name}_skill"
            class_name = f"{name.capitalize()}SkillMixin"

            # 动态导入模块
            module = importlib.import_module(module_name)

            # 获取 Mixin 类
            mixin_class = getattr(module, class_name)

            # 缓存到注册表
            self._python_mixins[name] = mixin_class

            logger.info(f"  ✅ Lazy Load Python Mixin: {name} -> {class_name}")
            return True

        except ImportError as e:
            logger.debug(f"  ⚠️  无法导入模块 {name}_skill: {e}")
            return False
        except AttributeError as e:
            logger.warning(f"  ⚠️  模块 {name}_skill 存在，但未找到类 {name.capitalize()}SkillMixin: {e}")
            return False
        except Exception as e:
            logger.warning(f"  ⚠️  加载 Python Mixin {name} 时发生错误: {e}")
            return False

    def _try_load_md_document(self, name: str) -> bool:
        """
        尝试加载 MD Document Skill（TODO）

        路径约定：
        - 查找路径: agentmatrix/skills/{name}.md

        Args:
            name: 技能名称

        Returns:
            bool: 是否加载成功
        """
        # TODO: 实现 MD Document 解析
        # 1. 查找文件: Path(__file__).parent / f"{name}.md"
        # 2. 解析 Markdown，提取 actions
        # 3. 创建 ActionMetadata 对象
        # 4. 缓存到 _md_actions
        logger.debug(f"  📄 MD Document 加载尚未实现: {name}")
        return False


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
