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
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class SkillLoadResult:
    """技能加载结果"""

    def __init__(self):
        # Python Mixin 类列表
        self.python_mixins: List[Type] = []
        # MD Document 元数据列表
        self.md_skills: List['MDSkillMetadata'] = []
        # 加载失败的技能名称
        self.failed_skills: List[str] = []

    def __repr__(self):
        return (f"SkillLoadResult(mixins={[m.__name__ for m in self.python_mixins]}, "
                f"md_skills={[s.name for s in self.md_skills]}, "
                f"failed={self.failed_skills})")


class SkillRegistry:
    """统一的 Skill 注册中心（Lazy Load 机制 + 多路径支持）"""

    def __init__(self):
        # Python Mixin 注册表: skill_name -> mixin_class
        self._python_mixins: Dict[str, Type] = {}

        # MD Document Metadata 注册表: skill_name -> MDSkillMetadata
        self._md_skills: Dict[str, 'MDSkillMetadata'] = {}

        # 🆕 Workspace SKILLS 目录路径（由 BaseAgent 设置）
        self._workspace_skills_dir: Optional[Path] = None

        # 🆕 Skill 搜索路径列表（优先级从高到低）
        # 默认只包含内置路径
        self.search_paths: List[str] = ["agentmatrix.skills"]

    def add_workspace_skills(self, paths):
        """
        自动添加 workspace/SKILLS/ 目录到搜索路径

        由 AgentMatrix.__init__() 调用，自动发现应用级 skills。

        Args:
            paths: MatrixPaths 对象

        示例:
            SKILL_REGISTRY.add_workspace_skills(runtime.paths)
            # 自动添加 "./MyWorld/workspace/SKILLS/" 到搜索路径
        """
        skills_dir = paths.get_skills_dir()

        if skills_dir.exists():
            # 添加到搜索路径（位置1，在默认路径之后）
            self.search_paths.insert(1, str(skills_dir))
            logger.info(f"✅ 添加 Skill 搜索路径: {skills_dir}")
        else:
            logger.debug(f"  📭 workspace/skills/ 不存在: {skills_dir}")

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

    def set_workspace_skills_dir(self, skills_dir: Path):
        """
        设置 Workspace SKILLS 目录（用于复制 MD Document Skills）

        由 BaseAgent 在初始化时调用。

        Args:
            skills_dir: Workspace 中的 SKILLS 目录路径（例如 Path("/workspace/SKILLS")）
        """
        self._workspace_skills_dir = skills_dir
        logger.info(f"✅ 设置 Workspace SKILLS 目录: {skills_dir}")

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

        这是主要接口，同时支持 Python Mixin 和 MD Document Skills。

        Lazy Load 流程：
        1. 检查缓存（_python_mixins, _md_actions）
        2. 如果未缓存，自动发现并加载：
           - 优先尝试 Python Mixin: {name}_skill.py
           - 如果失败，未来尝试 MD Document: skills/{name}.md
        3. 🆕 自动解析依赖：如果 skill 声明了 _skill_dependencies，自动加载依赖

        Args:
            skill_names: 技能名称列表（如 ["file", "browser", "web_search"]）

        Returns:
            SkillLoadResult: 包含 python_mixins, md_actions, failed_skills

        依赖解析规则：
        - 自动加载：声明了 _skill_dependencies 的 skill 会自动加载其依赖
        - 循环检测：使用 loaded + loading 双队列避免循环依赖导致的无限递归
        - 去重：同一个 skill 只加载一次（即使被多个 skill 依赖）
        - 顺序：依赖优先于被依赖者加载
        """
        result = SkillLoadResult()

        # 双队列用于循环依赖检测和去重
        loaded = set()      # 已成功加载的 skills
        loading = set()     # 正在加载中的 skills（用于循环检测）

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
            success = self._load_skill(name)

            if success == "python":
                # Python Mixin 加载成功
                loaded.add(name)
                if name in self._python_mixins:
                    result.python_mixins.append(self._python_mixins[name])
                    logger.info(f"  ✅ 加载成功: {name} -> {self._python_mixins[name].__name__}")
                loading.remove(name)
                return True

            elif success == "md":
                # MD Document 加载成功
                loaded.add(name)
                if name in self._md_skills:
                    result.md_skills.append(self._md_skills[name])
                    logger.info(f"  ✅ 加载成功: {name} -> {self._md_skills[name].description}")
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
            logger.info(f"✅ 成功加载 {len(result.python_mixins)} 个 skills: {[m.__name__ for m in result.python_mixins]}")
        if result.failed_skills:
            logger.warning(f"⚠️  {len(result.failed_skills)} 个 skills 加载失败: {result.failed_skills}")

        return result

    def list_registered_skills(self) -> Dict[str, List[str]]:
        """
        列出所有已注册的技能

        Returns:
            Dict: {"python": [...], "md": [...]}
        """
        return {
            "python": list(self._python_mixins.keys()),
            "md": list(self._md_skills.keys())
        }

    def _get_dependencies(self, name: str) -> List[str]:
        """
        获取 skill 的依赖声明

        支持：
        - Python Mixin: 读取 _skill_dependencies 类属性
        - MD Document: 读取 Frontmatter 中的 dependencies 字段

        Args:
            name: skill 名称（如 "web_search", "git_workflow"）

        Returns:
            List[str]: 依赖的 skill 名称列表（如 ["browser", "file"]）
        """
        # 情况1：Python Mixin
        if name in self._python_mixins:
            mixin_class = self._python_mixins[name]
            deps = getattr(mixin_class, '_skill_dependencies', [])
            if not isinstance(deps, list):
                logger.warning(f"  ⚠️  Skill '{name}' 的 _skill_dependencies 不是列表，已忽略: {deps}")
                return []
            logger.debug(f"  🔗 Skill '{name}' (Python) 声明的依赖: {deps}")
            return deps

        # 情况2：MD Document（不再支持 dependencies 字段）
        if name in self._md_skills:
            logger.debug(f"  🔗 Skill '{name}' (MD) 无需依赖")
            return []

        # 情况3：未加载，先尝试加载
        load_result = self._load_skill(name)

        if load_result == "python":
            mixin_class = self._python_mixins[name]
            deps = getattr(mixin_class, '_skill_dependencies', [])
            if not isinstance(deps, list):
                logger.warning(f"  ⚠️  Skill '{name}' 的 _skill_dependencies 不是列表，已忽略: {deps}")
                return []
            logger.debug(f"  🔗 Skill '{name}' (Python) 声明的依赖: {deps}")
            return deps

        elif load_result == "md":
            # MD skill 不再支持 dependencies
            logger.debug(f"  🔗 Skill '{name}' (MD) 无需依赖")
            return []

        else:
            # 加载失败
            return []

    def _load_from_file_location(self, skill_file: Path, name: str, base_module: str = None) -> bool:
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
                skill_file
            )

            if spec is None or spec.loader is None:
                logger.debug(f"  ⚠️  无法创建模块规范: {skill_file}")
                return False

            # 创建模块
            module = importlib.util.module_from_spec(spec)

            # 🔑 关键：设置模块属性以支持相对导入
            module.__package__ = package_name        # 包名（用于相对导入）
            module.__path__ = [str(skill_file.parent)] # 包路径（指向 skill.py 所在目录）

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

        Examples:
            base_path="MyWorld/skills", name="my_tool"
            → 加载 MyWorld/skills/my_tool/skill.py
            → 类名: My_toolSkillMixin

            base_path="agentmatrix.skills", name="simple_web_search"
            → 加载 agentmatrix.skills/simple_web_search/skill.py
            → 类名: Simple_web_searchSkillMixin
        """
        # 🔥 处理 Python 模块路径（如 "agentmatrix.skills"）
        # 需要转换为文件系统路径
        base_module = None  # 用于支持相对导入
        if '.' in base_path:
            try:
                # 尝试导入模块以获取实际路径
                import importlib
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

        Examples:
            base_path="agentmatrix.skills", name="browser"
            → 加载 agentmatrix.skills.browser_skill
            → 类名: BrowserSkillMixin
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
            logger.info(f"  ✅ 从文件加载 Skill: {name} -> {class_name} (来自 {base_path})")
            return True

        except ImportError:
            return False
        except AttributeError as e:
            logger.warning(f"  ⚠️  模块 {module_name} 中未找到类 {class_name}: {e}")
            return False

    def _load_skill(self, name: str) -> Optional[str]:
        """
        Lazy Load: 根据名字自动发现并加载技能

        优先级：
        1. 检查缓存（_python_mixins, _md_skills）
        2. 尝试加载 Python Mixin: {name}_skill.py
        3. 尝试加载 MD Document: skills/{name}/skill.md

        Args:
            name: 技能名称（如 "file", "browser", "git_workflow"）

        Returns:
            Optional[str]: "python" | "md" | None（失败）
        """
        # 1. 检查缓存
        if name in self._python_mixins:
            return "python"
        if name in self._md_skills:
            return "md"

        # 2. 尝试加载 Python Mixin
        if self._try_load_python_mixin(name):
            return "python"

        # 3. 尝试加载 MD Document
        if self._try_load_md_document(name):
            return "md"

        # 全部失败
        logger.warning(f"  ⚠️  未找到 Skill: {name}（既不是 Python Mixin 也不是 MD Document）")
        return None

    def _try_load_python_mixin(self, name: str) -> bool:
        """
        尝试加载 Python Mixin（支持多路径 + 两种结构）

        按优先级尝试所有搜索路径：
        1. 用户配置的路径（最优先）
        2. workspace/skills/（自动）
        3. agentmatrix.skills（默认）

        对于每个路径，尝试两种结构：
        a) 目录结构: {path}/{name}/skill.py（用户 skills）
        b) 扁平文件: {path}/{name}_skill.py（内置 skills）

        Args:
            name: 技能名称（如 "browser", "my_custom_skill"）

        Returns:
            bool: 是否加载成功

        Examples:
            get_skills(["browser"])
            → 1. 尝试用户路径/skills/browser/skill.py
            → 2. 尝试 workspace/skills/browser/skill.py
            → 3. 尝试 agentmatrix.skills.browser_skill
        """
        logger.debug(f"  🔍 搜索 Skill: {name}")

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

    def _get_skill_directory(self, name: str) -> Optional[Path]:
        """
        定位 skill 目录（用于 MD Document Skills）

        按优先级搜索所有路径，查找 {base_path}/{name}/skill.md 文件。

        Args:
            name: skill 名称（如 "git_workflow"）

        Returns:
            Optional[Path]: skill 目录路径，如果未找到则返回 None

        Examples:
            _get_skill_directory("git_workflow")
            → 可能返回 Path("agentmatrix/skills/git_workflow")
        """
        logger.debug(f"  🔍 搜索 MD Skill 目录: {name}")

        for base_path in self.search_paths:
            logger.debug(f"    搜索路径: {base_path}")

            # 处理 Python 模块路径（如 "agentmatrix.skills"）
            if '.' in base_path:
                try:
                    import importlib
                    module = importlib.import_module(base_path)
                    module_path = Path(module.__file__).parent
                except (ImportError, AttributeError):
                    logger.debug(f"    📂 无法找到模块路径: {base_path}")
                    continue
            else:
                module_path = Path(base_path)

            skill_dir = module_path / name

            # 检查目录存在
            if not skill_dir.exists() or not skill_dir.is_dir():
                continue

            # 检查 skill.md（MD Document Skill 的标识文件）
            skill_md = skill_dir / "skill.md"
            if skill_md.exists():
                logger.info(f"  ✅ 找到 MD Skill 目录: {skill_dir}")
                return skill_dir
            else:
                logger.debug(f"    📂 目录存在但缺少 skill.md: {skill_dir}")

        # 所有路径都失败
        return None

    def _copy_skill_to_workspace(self, skill_dir: Path, target_dir: Path) -> bool:
        """
        复制整个 skill 目录到 workspace（带缓存检查）

        复制内容：
        - skill.md（主文档）
        - scripts/（可执行脚本）
        - templates/（模板文件）
        - resources/（其他资源）

        缓存策略：
        - 如果目标目录已存在且修改时间较新，则跳过复制
        - 否则执行完整复制

        Args:
            skill_dir: 源 skill 目录（例如 agentmatrix/skills/git_workflow）
            target_dir: 目标目录（例如 workspace/SKILLS/git_workflow）

        Returns:
            bool: 是否复制成功（或跳过）
        """
        try:
            # 检查是否需要复制（缓存机制）
            if target_dir.exists():
                src_mtime = skill_dir.stat().st_mtime
                dst_mtime = target_dir.stat().st_mtime
                if dst_mtime >= src_mtime:
                    logger.debug(f"  ↺ Skill 目录已是最新，跳过复制: {target_dir}")
                    return True

            # 创建目标目录
            target_dir.parent.mkdir(parents=True, exist_ok=True)

            # 如果目标已存在，先删除（确保干净复制）
            if target_dir.exists():
                shutil.rmtree(target_dir)

            # 执行复制
            shutil.copytree(skill_dir, target_dir)
            logger.info(f"  ✅ 复制 Skill 到 workspace: {skill_dir} → {target_dir}")
            return True

        except Exception as e:
            logger.error(f"  ❌ 复制 Skill 目录失败: {skill_dir} → {target_dir}, 错误: {e}")
            return False

    def _try_load_md_document(self, name: str) -> bool:
        """
        尝试加载 MD Document Skill

        步骤：
        1. 定位 skill 目录（查找 skill.md）
        2. 解析 Frontmatter 和 Actions
        3. 复制 skill 目录到 workspace/SKILLS/
        4. 缓存元数据到 _md_skills

        Args:
            name: 技能名称（如 "git_workflow"）

        Returns:
            bool: 是否加载成功
        """
        from .md_parser import MDSkillParser

        # 步骤1：定位 skill 目录
        skill_dir = self._get_skill_directory(name)
        if not skill_dir:
            return False

        # 步骤2：解析 skill.md
        skill_md_path = skill_dir / "skill.md"
        metadata = MDSkillParser.parse(skill_md_path)
        if not metadata:
            logger.warning(f"  ⚠️  解析 MD Skill 失败: {skill_md_path}")
            return False

        # 步骤3：复制到 workspace
        if self._workspace_skills_dir is None:
            logger.error(f"  ❌ Workspace SKILLS 目录未设置，无法复制 MD Skill")
            logger.error(f"     请在 BaseAgent 初始化时调用 SKILL_REGISTRY.set_workspace_skills_dir()")
            return False

        target_dir = self._workspace_skills_dir / name
        if not self._copy_skill_to_workspace(skill_dir, target_dir):
            logger.warning(f"  ⚠️  复制 MD Skill 失败: {skill_dir}")
            return False

        # 更新元数据中的 workspace 路径
        metadata.workspace_path = target_dir

        # 步骤4：缓存元数据
        self._md_skills[name] = metadata
        logger.info(f"  ✅ 加载 MD Skill 成功: {name} -> {metadata.description}")
        return True


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
