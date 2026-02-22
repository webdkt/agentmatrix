# Skill 目录结构支持 - 设计文档

## 1. 概述

### 目标
支持应用级和 workspace 级的自定义 Skills，使用目录结构组织代码。

### 当前限制
- ❌ Skills 硬编码在 `agentmatrix.skills` 包内
- ❌ 应用无法添加自己的 skills
- ❌ 只支持单文件 `{name}_skill.py`

### 改进后
- ✅ 支持多路径搜索（内置 + 应用 + workspace）
- ✅ 支持目录结构 `{skill_name}/__init__.py`
- ✅ 应用 skill 优先级高于内置 skill
- ✅ 完全向后兼容

---

## 2. 目录结构规范

### 2.1 完整的应用结构

```
my_app/                           # 应用根目录
├── skills/                       # 应用级 skills 目录（位置1）
│   ├── my_custom_skill/          # Skill 名称（目录名）
│   │   ├── __init__.py           # 必须：包含 Mixin 类
│   │   ├── helpers.py            # 可选：辅助函数
│   │   └── config.py             # 可选：配置
│   └── company_tool/
│       ├── __init__.py
│       └── api_client.py
├── agents/
├── workspace/                    # Workspace 根目录
│   ├── skills/                   # Workspace 级 skills（位置2，自动发现）
│   │   └── research_tool/
│   │       ├── __init__.py
│   │       └── data_models.py
│   └── {user_session_id}/
└── config.yml
```

### 2.2 Skill 命名规范

**目录名 → Skill 名称**：
```
my_custom_skill/     → "my_custom_skill"
company_tool/        → "company_tool"
web_search/          → "web_search"
```

**Mixin 类命名**（在 `__init__.py` 中）：
```python
# my_custom_skill/__init__.py
class My_custom_skillSkillMixin:
    _skill_dependencies = ["browser", "file"]

    @register_action(...)
    async def my_action(self, ...):
        pass
```

### 2.3 平级结构（可选）

仍支持旧的单文件结构（向后兼容）：
```
skills/
├── browser_skill.py    # BrowserSkillMixin
├── file_skill.py       # FileSkillMixin
└── web_search/         # Web_searchSkillMixin (新)
    ├── __init__.py
    └── helpers.py
```

---

## 3. API 设计

### 3.1 SkillRegistry 初始化

**新增参数**：
```python
class SkillRegistry:
    def __init__(
        self,
        workspace_root: Optional[str] = None,      # 🆕 Workspace 根目录
        skill_search_paths: Optional[List[str]] = None  # 🆕 额外搜索路径
    ):
        # 默认路径（向后兼容）
        self.search_paths = ["agentmatrix.skills"]

        # 🆕 自动添加 workspace/skills/
        if workspace_root:
            workspace_skills_dir = Path(workspace_root) / "skills"
            if workspace_skills_dir.exists():
                self.search_paths.append(str(workspace_skills_dir))

        # 🆕 添加用户配置的路径
        if skill_search_paths:
            self.search_paths.extend(skill_search_paths)
```

### 3.2 配置方式

**在 matrix_world.yml 中配置**：
```yaml
# 应用配置
skill_search_paths:
  - /path/to/my_app/skills        # 应用级 skills
  - /opt/company_shared_skills    # 企业级共享
# workspace/skills/ 会自动添加，无需配置
```

**或通过代码配置**：
```python
from agentmatrix.core.runtime import AgentMatrix

matrix = AgentMatrix(
    agent_profile_path="./profiles",
    matrix_path="./workspace",
    skill_search_paths=[         # 🆕 新参数
        "./skills",              # 应用 skills
        "/opt/shared_skills"     # 共享 skills
    ]
)
```

### 3.3 路径优先级

**搜索顺序**（从高到低）：
```
1. 用户配置的 skill_search_paths（最后配置的最优先）
2. workspace_root/skills/（自动）
3. agentmatrix.skills（默认）
```

**冲突处理**：
```python
# 如果应用和内置都有 "browser" skill
# 优先使用应用的（覆盖内置）
```

---

## 4. 加载机制

### 4.1 新的加载流程

```python
def _try_load_python_mixin(self, name: str) -> bool:
    """
    尝试加载 Python Mixin

    按优先级尝试所有搜索路径和两种结构
    """
    for base_path in self.search_paths:
        # 方式1: 目录结构（新）
        if self._try_load_from_directory(base_path, name):
            logger.info(f"✅ 从目录加载: {base_path}/{name}/")
            return True

        # 方式2: 扁平结构（旧，向后兼容）
        if self._try_load_from_flat_file(base_path, name):
            logger.info(f"✅ 从文件加载: {base_path}/{name}_skill.py")
            return True

    logger.warning(f"⚠️  未找到 Skill: {name}")
    return False
```

### 4.2 目录结构加载

```python
def _try_load_from_directory(self, base_path: str, name: str) -> bool:
    """
    从目录结构加载 Skill

    结构: {base_path}/{name}/__init__.py
    """
    skill_dir = Path(base_path) / name

    # 检查目录存在
    if not skill_dir.exists():
        return False

    # 检查 __init__.py
    init_file = skill_dir / "__init__.py"
    if not init_file.exists():
        logger.warning(f"  ⚠️  缺少 __init__.py: {skill_dir}")
        return False

    try:
        # 动态导入
        # 例如: my_app.skills.my_custom_skill
        module_name = self._path_to_module_name(skill_dir)
        module = importlib.import_module(module_name)

        # 获取 Mixin 类
        class_name = f"{name.capitalize()}SkillMixin"
        mixin_class = getattr(module, class_name)

        # 缓存
        self._python_mixins[name] = mixin_class
        logger.debug(f"  ✅ 缓存 Skill: {name} -> {class_name}")
        return True

    except ImportError as e:
        logger.debug(f"  ⚠️  导入失败: {e}")
        return False
    except AttributeError as e:
        logger.warning(f"  ⚠️  未找到类 {class_name}: {e}")
        return False
```

### 4.3 扁平文件加载（向后兼容）

```python
def _try_load_from_flat_file(self, base_path: str, name: str) -> bool:
    """
    从扁平文件加载 Skill（旧方式，向后兼容）

    结构: {base_path}/{name}_skill.py
    """
    # 检查是否为 Python 包路径
    if "." in base_path:
        module_name = f"{base_path}.{name}_skill"
    else:
        module_name = f"{base_path}.{name}_skill"

    try:
        module = importlib.import_module(module_name)
        class_name = f"{name.capitalize()}SkillMixin"
        mixin_class = getattr(module, class_name)

        self._python_mixins[name] = mixin_class
        return True

    except (ImportError, AttributeError):
        return False
```

---

## 5. 路径处理工具

### 5.1 路径到模块名转换

```python
def _path_to_module_name(self, path: Path) -> str:
    """
    将文件路径转换为 Python 模块名

    Examples:
        /Users/.../my_app/skills/my_skill → my_app.skills.my_skill
        /opt/skills/company_tool → company_tool
    """
    # 添加到 sys.path（如果需要）
    path_str = str(path.parent)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

    # 提取相对路径部分
    # 例如: my_app/skills/my_skill
    parts = path.parts

    # 查找 'skills' 目录
    try:
        skills_index = parts.index('skills')
        module_parts = parts[skills_index:]
    except ValueError:
        # 没有 'skills' 目录，使用最后两部分
        module_parts = parts[-2:] if len(parts) >= 2 else parts

    # 转换为模块名
    module_name = ".".join(module_parts)
    return module_name
```

---

## 6. 使用示例

### 6.1 应用开发者

**步骤 1: 创建 Skill 目录**
```bash
cd my_app/
mkdir -p skills/my_custom_skill
```

**步骤 2: 编写 `__init__.py`**
```python
# skills/my_custom_skill/__init__.py
from ..core.action import register_action

class My_custom_skillSkillMixin:
    """我的自定义技能"""

    _skill_dependencies = ["file"]  # 声明依赖

    @register_action(
        description="执行我的自定义操作",
        param_infos={
            "input_data": "输入数据"
        }
    )
    async def my_custom_action(self, input_data: str) -> str:
        # 实现代码
        return f"处理完成: {input_data}"
```

**步骤 3: 配置（可选）**
```yaml
# config.yml
skill_search_paths:
  - ./skills          # 应用 skills
  - /opt/shared_skills  # 可选：共享技能库
```

**步骤 4: 使用**
```python
from agentmatrix.skills.registry import SKILL_REGISTRY

# 自动搜索并加载
result = SKILL_REGISTRY.get_skills(["my_custom_skill"])
# 结果: [My_custom_skillSkillMixin, FileSkillMixin]
```

### 6.2 Profile 配置

**在 Agent Profile 中使用**：
```yaml
# agents/my_agent.yml
name: MyAgent
module: agentmatrix.agents.base
class_name: BaseAgent

skills:
  - my_custom_skill  # 自动加载应用 skill + 依赖
```

---

## 7. 向后兼容性

### 7.1 保证兼容

```python
# 默认行为不变
SKILL_REGISTRY = SkillRegistry()
# search_paths = ["agentmatrix.skills"]

# 旧代码继续工作
result = SKILL_REGISTRY.get_skills(["browser", "file"])
```

### 7.2 迁移路径

**阶段 1: 单文件（当前）**
```
skills/
└── browser_skill.py
```

**阶段 2: 目录（推荐）**
```
skills/
└── browser/
    ├── __init__.py
    └── helpers.py
```

**两者共存**：系统同时支持两种结构

---

## 8. 测试策略

### 8.1 单元测试

```python
def test_load_from_directory():
    """测试从目录加载"""
    SKILL_REGISTRY = SkillRegistry(
        skill_search_paths=["tests.fixtures.test_skills"]
    )
    result = SKILL_REGISTRY.get_skills(["test_skill"])
    assert len(result.python_mixins) == 1

def test_application_override_builtin():
    """测试应用覆盖内置 skill"""
    # 应用定义了 "browser" skill
    # 应该优先使用应用的，而非内置的
    ...

def test_workspace_auto_discovery():
    """测试 workspace 自动发现"""
    # workspace/skills/ 目录下的 skill
    # 应该被自动发现
    ...
```

### 8.2 集成测试

```python
def test_end_to_end_custom_skill():
    """端到端测试：自定义 skill"""
    # 1. 创建应用 skill
    # 2. 配置搜索路径
    # 3. 创建 Agent 使用 skill
    # 4. 验证功能正常
    ...
```

---

## 9. 实现步骤

### 阶段 1: 核心功能（必须）
1. ✅ 修改 `SkillRegistry.__init__()` 支持多路径
2. ✅ 实现 `_try_load_from_directory()`
3. ✅ 实现 `_path_to_module_name()`
4. ✅ 修改 `_try_load_python_mixin()` 支持两种结构
5. ✅ 添加路径优先级逻辑

### 阶段 2: Runtime 集成
1. ✅ 修改 `AgentMatrix.__init__()` 接受 `skill_search_paths`
2. ✅ 传递 `workspace_root` 到 `SKILL_REGISTRY`
3. ✅ 自动添加 `workspace/skills/` 到搜索路径

### 阶段 3: 文档和测试
1. ✅ 编写使用文档
2. ✅ 编写迁移指南
3. ✅ 添加单元测试
4. ✅ 添加集成测试

### 阶段 4: 工具和优化（可选）
1. 🔄 Skill 生成脚手架工具
2. 🔄 Skill 验证工具
3. 🔄 热加载支持
4. 🔄 详细的错误提示

---

## 10. 风险和缓解

### 10.1 安全性

**风险**: 路径遍历攻击
```python
# 恶意输入
skills = ["../../../etc/malicious"]
```

**缓解**:
```python
def _validate_skill_name(self, name: str):
    """验证 skill 名称"""
    # 只允许字母、数字、下划线
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(f"无效的 skill 名称: {name}")
```

### 10.2 性能

**风险**: 多路径搜索增加加载时间

**缓解**:
- 使用缓存（已实现）
- 延迟加载（已实现）
- 并行导入（可选优化）

### 10.3 兼容性

**风险**: 破坏现有代码

**缓解**:
- 默认行为不变
- 渐进式迁移
- 详细的向后兼容测试

---

## 11. 成功标准

✅ **功能完整**:
- 支持目录结构 `{skill_name}/__init__.py`
- 支持多路径搜索
- 应用 skill 覆盖内置 skill

✅ **向后兼容**:
- 所有现有代码无需修改
- 单文件结构继续工作

✅ **易于使用**:
- 零配置自动发现 workspace/skills/
- 清晰的错误提示
- 完善的文档

✅ **可扩展**:
- 支持未来增强（版本管理、冲突检测等）

---

## 附录 A: 关键文件

| 文件 | 修改内容 |
|------|---------|
| `skills/registry.py` | 核心加载逻辑，添加多路径支持 |
| `core/runtime.py` | 在 `__init__()` 中配置 SKILL_REGISTRY |
| `agents/base.py` | ❌ 不需要修改（不传递 workspace_root） |

### 初始化流程（正确方式）

```python
# runtime.py
from ..skills.registry import SKILL_REGISTRY

class AgentMatrix:
    def __init__(self, agent_profile_path, matrix_path, ...):
        self.matrix_path = matrix_path              # Workspace 根目录
        self.agent_profile_path = agent_profile_path  # Agent profiles 目录

        # 🆕 配置 SKILL_REGISTRY（类似 AgentLoader）
        # 自动添加 {matrix_path}/skills/ 到搜索路径
        SKILL_REGISTRY.add_workspace_skills(self.matrix_path)
```

### SKILL_REGISTRY 配置

```python
# skills/registry.py
class SkillRegistry:
    def __init__(self):
        self.search_paths = ["agentmatrix.skills"]  # 默认路径

    def add_workspace_skills(self, matrix_path: str):
        """
        自动添加 workspace/skills/ 目录

        由 AgentMatrix.__init__() 调用
        """
        skills_dir = Path(matrix_path) / "skills"
        if skills_dir.exists():
            # 添加到搜索路径（优先级高于默认）
            self.search_paths.insert(1, str(skills_dir))  # 位置1，在默认之后
            logger.info(f"✅ 添加 Skill 搜索路径: {skills_dir}")
```

### 流程图

```
应用代码：
  matrix = AgentMatrix(
      agent_profile_path="./agents",
      matrix_path="./MyWorld"       # ← Workspace 根
  )

      ↓

AgentMatrix.__init__():
  self.matrix_path = "./MyWorld"

  # 配置 SKILL_REGISTRY
  SKILL_REGISTRY.add_workspace_skills("./MyWorld")

      ↓

SKILL_REGISTRY:
  search_paths = [
    "agentmatrix.skills",            # 默认
    "MyWorld.skills",                # 🆕 自动添加
  ]

      ↓

自动发现：
  MyWorld/skills/my_custom_skill/   # ✅ 自动发现
```

### 与 AgentLoader 对比

**AgentLoader（现有）**：
```python
# runtime.py
loader = AgentLoader(self.agent_profile_path)
# 从 ./agents/ 加载 Agent profiles
```

**SKILL_REGISTRY（新设计）**：
```python
# runtime.py
SKILL_REGISTRY.add_workspace_skills(self.matrix_path)
# 从 ./MyWorld/skills/ 加载 Skills
```

两者设计一致：都在 AgentMatrix 初始化时配置。

## 附录 B: 示例代码

**完整的应用 skill 示例**：
```python
# my_app/skills/data_processor/__init__.py
from ..core.action import register_action
from .helpers import process_data

class Data_processorSkillMixin:
    """数据处理技能"""

    _skill_dependencies = ["file"]

    @register_action(
        description="处理 CSV 数据",
        param_infos={
            "file_path": "CSV 文件路径"
        }
    )
    async def process_csv(self, file_path: str) -> str:
        data = await self.read(file_path)
        result = process_data(data)
        await self.write("output.json", result)
        return "处理完成"
```

**使用方式**：
```python
# agents/data_analyst.yml
skills:
  - data_processor  # 自动加载 file 依赖
```

---

**文档版本**: 1.0
**创建日期**: 2025-02-21
**状态**: 设计阶段
