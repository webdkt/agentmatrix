"""
Skill Registry - 统一的技能注册中心

只支持 Python Method Skills（提供 Python 实现的 Mixin 类）。

Lazy Load 机制：
- 根据 skill_name 自动发现并加载技能
- Python Mixin: 查找 {name}_skill.py 中的 {Name}SkillMixin
"""

from typing import Dict, List, Optional, Type
import logging
import importlib
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillLoadResult:
    """技能加载结果"""

    def __init__(self):
        # Python Mixin 类列表
        self.python_mixins: List[Type] = []
        # 加载失败的技能名称
        self.failed_skills: List[str] = []

    def __repr__(self):
        return (
            f"SkillLoadResult(mixins={[m.__name__ for m in self.python_mixins]}, "
            f"failed={self.failed_skills})"
        )


class SkillRegistry:
    """Skill 注册中心（Lazy Load 机制 + 多路径支持）"""

    def __init__(self):
        # Python Mixin 注册表: skill_name -> mixin_class
        self._python_mixins: Dict[str, Type] = {}

        # Skill 搜索路径列表（优先级从高到低）
        # 默认只包含内置路径
        self.search_paths: List[str] = []

    def add_search_path(self, path: str):
        """
        手动添加额外的搜索路径

        Args:
            path: 搜索路径（可以是绝对路径或相对路径）

        示例:
            SKILL_REGISTRY.add_search_path("/opt/company_skills")
            SKILL_REGISTRY.add_search_path("./my_app/skills")
        """
        if path not in self.search_paths:
            # 添加到最前面（最高优先级）
            self.search_paths.insert(0, path)
            logger.info(f"✅ 添加 Skill 搜索路径: {path}")

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
        根据技能名称列表获取技能（Lazy Load + 统一接口 + 自动依赖解析）

        Lazy Load 流程：
        1. 检查缓存 (_python_mixins)
        2. 如果未缓存，自动发现并加载 Python Mixin

        自动依赖解析：
        - 如果 skill 声明了 _skill_dependencies，自动加载依赖
        - 循环检测：使用 loaded + loading 双队列避免循环依赖导致的无限递归
        - 去重：同一个 skill 只加载一次（即使被多个 skill 依赖）
        - 顺序：依赖优先于被依赖者加载

        Args:
            skill_names: 技能名称列表（如 ["file", "browser", "web_search"]）

        Returns:
            SkillLoadResult: 包含 python_mixins, failed_skills
        """
        result = SkillLoadResult()

        # 双队列用于循环依赖检测和去重
        loaded = set()  # 已成功加载的 skills
        loading = set()  # 正在加载中的 skills（用于循环检测）

        # 递归加载函数
        def load_skill_recursive(name: str) -> bool:
            """
            递归加载 skill 及其依赖

            Args:
                name: skill 名称

            Returns:
                bool: 是否加载成功
            """
            # 情况1：已经加载过，跳过
            if name in loaded:
                logger.debug(f"  ↺ 跳过已加载: {name}")
                return True

            # 情况2：正在加载中，检测到循环依赖
            if name in loading:
                logger.warning(f"  🔁 检测到循环依赖，跳过: {name}")
                return True  # 返回 True，因为外层的调用会继续加载

            # 标记为正在加载
            loading.add(name)
            logger.debug(f"  📥 开始加载: {name}")

            # 步骤1：先加载依赖（递归）
            deps = self._get_dependencies(name)
            if deps:
                logger.debug(f"  🔗 {name} 依赖: {deps}")
                for dep in deps:
                    load_skill_recursive(dep)

            # 步骤2：加载当前 skill
            if self._load_skill(name):
                loaded.add(name)
                if name in self._python_mixins:
                    result.python_mixins.append(self._python_mixins[name])
                    logger.info(
                        f"  ✅ 加载成功: {name} -> {self._python_mixins[name].__name__}"
                    )
                loading.remove(name)
                return True
            else:
                # 加载失败
                result.failed_skills.append(name)
                logger.warning(f"  ❌ 加载失败: {name}")
                loading.remove(name)
                return False

        # 按顺序加载所有请求的 skills
        for name in skill_names:
            load_skill_recursive(name)

        # 日志汇总
        if result.python_mixins:
            logger.info(
                f"✅ 成功加载 {len(result.python_mixins)} 个 skills: {[m.__name__ for m in result.python_mixins]}"
            )
        if result.failed_skills:
            logger.warning(
                f"⚠️  {len(result.failed_skills)} 个 skills 加载失败: {result.failed_skills}"
            )

        return result

    def list_registered_skills(self) -> List[str]:
        """
        列出所有已注册的 Python Mixin 技能

        Returns:
            List[str]: 技能名称列表
        """
        return list(self._python_mixins.keys())

    def _get_dependencies(self, name: str) -> List[str]:
        """
        获取 skill 的依赖声明

        读取 Python Mixin 的 _skill_dependencies 类属性

        Args:
            name: skill 名称（如 "browser", "file"）

        Returns:
            List[str]: 依赖的 skill 名称列表（如 ["browser", "file"]）
        """
        if name in self._python_mixins:
            mixin_class = self._python_mixins[name]
            deps = getattr(mixin_class, "_skill_dependencies", [])
            if not isinstance(deps, list):
                logger.warning(
                    f"  ⚠️  Skill '{name}' 的 _skill_dependencies 不是列表，已忽略: {deps}"
                )
                return []
            logger.debug(f"  🔗 Skill '{name}' (Python) 声明的依赖: {deps}")
            return deps

        # 未加载，先尝试加载
        if self._load_skill(name) and name in self._python_mixins:
            mixin_class = self._python_mixins[name]
            deps = getattr(mixin_class, "_skill_dependencies", [])
            if not isinstance(deps, list):
                logger.warning(
                    f"  ⚠️  Skill '{name}' 的 _skill_dependencies 不是列表，已忽略: {deps}"
                )
                return []
            logger.debug(f"  🔗 Skill '{name}' (Python) 声明的依赖: {deps}")
            return deps

        # 加载失败
        return []

    def _load_from_file_location(
        self, skill_file: Path, name: str, base_module: str = None
    ) -> bool:
        """
        使用 spec_from_file_location 直接加载文件

        优点：
        - 不需要 __init__.py
        - 不修改 sys.path（更安全）
        - 支持 skill.py 中使用相对导入同目录文件

        Args:
            skill_file: Skill 文件路径（例如 /path/to/skills/my_skill/skill.py）
            name: Skill 名称（例如 "my_skill"）
            base_module: 基础模块名（例如 "agentmatrix.skills"），用于支持相对导入

        Returns:
            bool: 是否加载成功
        """
        import importlib.util
        import sys

        try:
            # 🔥 构造正确的模块层级以支持相对导入
            if base_module:
                # 使用完整模块路径：agentmatrix.skills.simple_web_search.skill
                package_name = f"{base_module}.{name}"
                module_name = f"{package_name}.skill"
            else:
                # 降级到简单模式（不支持相对导入）
                module_name = f"{name}_skill"
                package_name = module_name

            # 创建模块规范
            spec = importlib.util.spec_from_file_location(
                module_name,  # 模块名
                skill_file,
            )

            if spec is None or spec.loader is None:
                logger.debug(f"  ⚠️  无法创建模块规范: {skill_file}")
                return False

            # 创建模块
            module = importlib.util.module_from_spec(spec)

            # 🔑 关键：设置模块属性以支持相对导入
            module.__package__ = package_name  # 包名（用于相对导入）
            module.__path__ = [
                str(skill_file.parent)
            ]  # 包路径（指向 skill.py 所在目录）

            # 🔑 将模块添加到 sys.modules（关键！）
            # 这样相对导入 `from .utils import xxx` 才能找到
            sys.modules[module_name] = module

            # 🔑 如果是目录结构，还需要注册包本身
            if base_module:
                package_key = package_name
                if package_key not in sys.modules:
                    # 创建一个虚拟的包模块
                    import types

                    package_module = types.ModuleType(package_key)
                    package_module.__path__ = [str(skill_file.parent)]
                    sys.modules[package_key] = package_module

            # 执行模块
            spec.loader.exec_module(module)

            # 获取 Mixin 类
            class_name = f"{name.capitalize()}SkillMixin"
            mixin_class = getattr(module, class_name)

            # 缓存
            self._python_mixins[name] = mixin_class
            logger.info(f"  ✅ 从文件加载 Skill: {name} -> {class_name} ({skill_file})")
            return True

        except FileNotFoundError:
            logger.debug(f"  📂 文件不存在: {skill_file}")
            return False
        except AttributeError as e:
            logger.warning(f"  ⚠️  文件 {skill_file} 中未找到类 {class_name}: {e}")
            return False
        except Exception as e:
            logger.warning(f"  ⚠️  加载文件 {skill_file} 时出错: {e}")
            return False

    def _try_load_from_directory(self, base_path: str, name: str) -> bool:
        """
        从目录结构加载 Skill（新方式：skill.py）

        目录结构: {base_path}/{name}/skill.py
        类名约定: {Name}SkillMixin (在 skill.py 中)

        优点：
        - 不需要 __init__.py
        - 不修改 sys.path
        - 支持多文件（通过相对导入）

        Args:
            base_path: 基础路径（例如 "MyWorld/skills" 或 "agentmatrix.skills"）
            name: Skill 名称（例如 "my_custom_skill"）

        Returns:
            bool: 是否加载成功
        """
        # 🔥 处理 Python 模块路径（如 "agentmatrix.skills"）
        # 需要转换为文件系统路径
        base_module = None  # 用于支持相对导入
        if "." in base_path:
            try:
                # 尝试导入模块以获取实际路径
                module = importlib.import_module(base_path)
                module_path = Path(module.__file__).parent
                base_module = base_path  # 保存原始模块名用于相对导入
            except (ImportError, AttributeError):
                # 模块不存在或没有 __file__ 属性
                logger.debug(f"  📂 无法找到模块路径: {base_path}")
                return False
        else:
            # 普通文件系统路径（如 "MyWorld/skills"）
            module_path = Path(base_path)

        skill_dir = module_path / name

        # 检查目录存在
        if not skill_dir.exists() or not skill_dir.is_dir():
            return False

        # 检查 skill.py（新约定的入口文件）
        skill_file = skill_dir / "skill.py"
        if not skill_file.exists():
            logger.debug(f"  📂 目录存在但缺少 skill.py: {skill_dir}")
            return False

        # 使用 spec_from_file_location 加载（传递 base_module 以支持相对导入）
        return self._load_from_file_location(skill_file, name, base_module)

    def _try_load_from_flat_file(self, base_path: str, name: str) -> bool:
        """
        从扁平文件结构加载 Skill（向后兼容）

        文件结构: {base_path}/{name}_skill.py
        类名约定: {Name}SkillMixin

        Args:
            base_path: 基础路径（例如 "agentmatrix.skills"）
            name: Skill 名称（例如 "browser"）

        Returns:
            bool: 是否加载成功
        """
        # 构造模块路径
        module_name = f"{base_path}.{name}_skill"

        try:
            logger.debug(f"  🔍 尝试从文件加载: {module_name}")
            module = importlib.import_module(module_name)

            # 获取 Mixin 类
            class_name = f"{name.capitalize()}SkillMixin"
            mixin_class = getattr(module, class_name)

            # 缓存
            self._python_mixins[name] = mixin_class
            logger.info(
                f"  ✅ 从文件加载 Skill: {name} -> {class_name} (来自 {base_path})"
            )
            return True

        except ImportError:
            return False
        except AttributeError as e:
            logger.warning(f"  ⚠️  模块 {module_name} 中未找到类 {class_name}: {e}")
            return False

    def _load_skill(self, name: str) -> bool:
        """
        Lazy Load: 根据名字自动发现并加载技能

        只尝试加载 Python Mixin

        Args:
            name: 技能名称（如 "file", "browser"）

        Returns:
            bool: 是否加载成功
        """
        # 1. 检查缓存
        if name in self._python_mixins:
            return True

        # 2. 尝试加载 Python Mixin
        if self._try_load_python_mixin(name):
            return True

        # 全部失败
        logger.warning(f"  ⚠️  未找到 Skill: {name}")
        return False

    def _try_load_python_mixin(self, name: str) -> bool:
        """
        尝试加载 Python Mixin（支持多路径 + 两种结构 + 嵌套 skill）

        按优先级尝试所有搜索路径：
        1. 用户配置的路径（最优先）
        2. agentmatrix.skills（默认）

        对于每个路径，尝试两种结构：
        a) 目录结构: {path}/{name}/skill.py（用户 skills）
        b) 扁平文件: {path}/{name}_skill.py（内置 skills）

        对于 dotted name（如 "new_web_search.deep_reader"）：
        c) 嵌套目录: {path}/new_web_search/deep_reader/skill.py

        Args:
            name: 技能名称（如 "browser", "my_custom_skill", "a.b.c"）

        Returns:
            bool: 是否加载成功
        """
        logger.debug(f"  🔍 搜索 Skill: {name}")

        # dotted name → 嵌套 skill
        if "." in name:
            return self._load_nested_skill(name)

        # 按优先级尝试所有搜索路径
        for base_path in self.search_paths:
            logger.debug(f"    搜索路径: {base_path}")

            # 方式1: 目录结构（用户 skills，使用 skill.py）
            if self._try_load_from_directory(base_path, name):
                return True

            # 方式2: 扁平文件（内置 skills，使用 {name}_skill.py）
            if self._try_load_from_flat_file(base_path, name):
                return True

        # 所有路径都失败
        return False

    def _load_nested_skill(self, dotted_name: str) -> bool:
        """
        加载嵌套 skill（如 "new_web_search.deep_reader"）

        目录结构: {base_path}/new_web_search/deep_reader/skill.py
        类名: Deep_readerSkillMixin（取 dotted name 最后一段 capitalize）

        Args:
            dotted_name: 点分隔的 skill 名称，如 "new_web_search.deep_reader"

        Returns:
            bool: 是否加载成功
        """
        import sys
        import types
        import importlib.util

        # 检查缓存
        if dotted_name in self._python_mixins:
            return True

        parts = dotted_name.split(".")
        parent_name = ".".join(parts[:-1])  # "new_web_search"
        child_name = parts[-1]  # "deep_reader"

        for base_path in self.search_paths:
            # 解析基础目录
            if "." in base_path:
                try:
                    mod = importlib.import_module(base_path)
                    base_dir = Path(mod.__file__).parent
                except (ImportError, AttributeError):
                    continue
            else:
                base_dir = Path(base_path)
                if not base_dir.exists():
                    continue

            # 确保 parent 已加载（注册到 sys.modules）
            if parent_name not in self._python_mixins:
                self._load_skill(parent_name)

            # 从 sys.modules 找 parent 的目录
            parent_package_key = f"{base_path}.{parent_name}"
            parent_mod = sys.modules.get(parent_package_key)

            if parent_mod and hasattr(parent_mod, "__path__"):
                parent_dir = Path(parent_mod.__path__[0])
            else:
                # parent 没有找到，尝试从文件系统推断
                # 逐层解析 dotted parent_name
                current_dir = base_dir
                found = True
                for part in parent_name.split("."):
                    candidate = current_dir / part
                    if candidate.is_dir() and (candidate / "skill.py").exists():
                        current_dir = candidate
                    else:
                        found = False
                        break
                if not found:
                    continue
                parent_dir = current_dir

            # 检查 child 目录下的 skill.py
            child_dir = parent_dir / child_name
            skill_file = child_dir / "skill.py"
            if not skill_file.exists():
                continue

            # 加载 child skill
            return self._load_child_skill(skill_file, dotted_name, base_path, child_dir)

        logger.warning(f"  ⚠️  嵌套 Skill 未找到: {dotted_name}")
        return False

    def _load_child_skill(
        self, skill_file: Path, dotted_name: str, base_module: str, child_dir: Path
    ) -> bool:
        """
        加载嵌套 child skill，正确设置 sys.modules 层级以支持相对导入

        Args:
            skill_file: child 的 skill.py 路径
            dotted_name: 完整名称，如 "new_web_search.deep_reader"
            base_module: 基础模块名，如 "agentmatrix.skills"
            child_dir: child 的目录路径

        Returns:
            bool: 是否加载成功
        """
        import sys
        import types
        import importlib.util

        parts = dotted_name.split(".")
        package_name = f"{base_module}.{dotted_name}"
        module_name = f"{package_name}.skill"

        try:
            # 创建模块规范
            spec = importlib.util.spec_from_file_location(module_name, skill_file)
            if spec is None or spec.loader is None:
                logger.debug(f"  ⚠️  无法创建模块规范: {skill_file}")
                return False

            # 创建模块
            module = importlib.util.module_from_spec(spec)

            # 设置模块属性以支持相对导入
            module.__package__ = package_name
            module.__path__ = [str(child_dir)]
            sys.modules[module_name] = module

            # 注册所有中间层级的虚拟包（支持相对导入）
            # 例如 dotted_name = "a.b.c"，需要注册:
            #   agentmatrix.skills.a (with __path__)
            #   agentmatrix.skills.a.b (with __path__)
            #   agentmatrix.skills.a.b.c (with __path__)
            pkg = base_module
            for i, part in enumerate(parts):
                pkg = f"{pkg}.{part}"
                if pkg not in sys.modules:
                    # 计算该层级对应的目录
                    level_dir = child_dir.parents[len(parts) - i - 1]
                    pm = types.ModuleType(pkg)
                    pm.__path__ = [str(level_dir)]
                    sys.modules[pkg] = pm
                elif not hasattr(sys.modules[pkg], "__path__"):
                    sys.modules[pkg].__path__ = [str(child_dir)]

            # 执行模块
            spec.loader.exec_module(module)

            # 获取 Mixin 类（取 dotted name 最后一段）
            class_name = f"{parts[-1].capitalize()}SkillMixin"
            mixin_class = getattr(module, class_name)

            # 缓存
            self._python_mixins[dotted_name] = mixin_class
            logger.info(
                f"  ✅ 加载嵌套 Skill: {dotted_name} -> {class_name} ({skill_file})"
            )
            return True

        except AttributeError as e:
            logger.warning(f"  ⚠️  未找到类 {parts[-1].capitalize()}SkillMixin: {e}")
            return False
        except Exception as e:
            logger.warning(f"  ⚠️  加载嵌套 Skill {dotted_name} 失败: {e}")
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
