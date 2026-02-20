# Mixin Skills 重构计划

**目标**: 将 BaseAgent 注入 actions 的架构改为 MicroAgent 动态继承 Skill Mixins

**原则**: 渐进式重构，每个阶段可独立回滚

**分支策略**: `refactor/mixin-skills`

---

## 回滚策略

### Git 版本管理

```bash
# 1. 创建重构分支
git checkout -b refactor/mixin-skills

# 2. 在关键里程碑打 tag
git tag -a phase1-foundation -m "阶段1完成：基础设施"
git tag -a phase2-migration -m "阶段2完成：Skill 迁移"
git tag -a phase3-microagent -m "阶段3完成：MicroAgent 改造"
git tag -a phase4-testing -m "阶段4完成：兼容性测试"

# 3. 回滚到任意阶段
git checkout tags/phase1-foundation

# 4. 回滚到重构前
git checkout main
git branch -D refactor/mixin-skills
```

### 代码级回滚

每个阶段保留旧代码，通过特性开关控制：

```python
# 使用环境变量或配置控制
USE_NEW_SKILL_ARCH = os.getenv("USE_NEW_SKILL_ARCH", "false") == "true"

if USE_NEW_SKILL_ARCH:
    # 新架构
    self._load_skills_new()
else:
    # 旧架构
    self._scan_methods()
```

---

## 阶段1：基础设施（Foundation）

**目标**: 建立新的 Skill 架构基础设施，不影响现有代码

### 1.1 扩展 `core/action.py`

```python
# 新增内容（向后兼容）
class SkillType(Enum):
    PYTHON_METHOD = "python_method"
    MD_DOCUMENT = "md_document"

# 修改 register_action，添加默认参数
def register_action(
    description: str,
    param_infos: Dict[str, str] = None,
    skill_type: SkillType = SkillType.PYTHON_METHOD,  # 🆕
):
    # ...
```

**验证**: 运行现有测试，确保旧代码不受影响

**回滚**: 删除 `SkillType` 枚举和 `skill_type` 参数

---

### 1.2 创建 `skills/registry.py`

**新建文件**: `src/agentmatrix/skills/registry.py`

```python
class SkillRegistry:
    """统一的 Skill 注册中心"""
    _python_mixins: Dict[str, type] = {}
    _md_actions: Dict[str, List] = {}

SKILL_REGISTRY = SkillRegistry()
```

**验证**: 导入测试

```bash
python -c "from agentmatrix.skills.registry import SKILL_REGISTRY; print('OK')"
```

**回滚**: 删除 `skills/registry.py`

---

### 1.3 创建 `skills/base.py`

**新建文件**: `src/agentmatrix/skills/base.py`

```python
class SkillMixinInterface:
    """Skill Mixin 接口定义"""

    def get_working_context(self):
        """获取 working_context（必须由 MicroAgent 提供）"""
        raise NotImplementedError
```

**验证**: 导入测试

**回滚**: 删除 `skills/base.py`

---

## 阶段2：Skill 迁移（Migration）

**目标**: 将现有 Skills 迁移为新格式，与旧代码共存

### 2.1 创建 `skills/file_skill.py`

**新建文件**: `src/agentmatrix/skills/file_skill.py`

```python
from .base import SkillMixinInterface
from ..core.action import register_action
from .registry import register_skill

@register_skill("file")
class FileSkillMixin(SkillMixinInterface):
    @register_action(...)
    async def list_dir(self, directory, recursive):
        # 直接访问 self.working_context（由 MicroAgent 提供）
        pass
```

**验证**: 单元测试

```python
# tests/skills/test_file_skill.py
def test_file_skill_mixin():
    from agentmatrix.skills.file_skill import FileSkillMixin
    assert hasattr(FileSkillMixin, 'list_dir')
```

**回滚**: 删除 `skills/file_skill.py`

---

### 2.2 创建 `skills/browser_skill.py`

**新建文件**: `src/agentmatrix/skills/browser_skill.py`

类似 file_skill.py 的结构

**回滚**: 删除 `skills/browser_skill.py`

---

### 2.3 在 BaseAgent 中注册 Mixins

**修改文件**: `src/agentmatrix/agents/base.py`

```python
# 在 __init__ 中添加
def __init__(self, profile):
    # ... 现有代码

    # 🆕 注册新架构的 Skills（向后兼容）
    self._register_new_skills()

def _register_new_skills(self):
    """注册新架构的 Skill Mixins"""
    from ..skills.registry import SKILL_REGISTRY

    # 导入并注册（触发 @register_skill 装饰器）
    try:
        from ..skills.file_skill import FileSkillMixin
        from ..skills.browser_skill import BrowserSkillMixin
        # 注册由装饰器自动完成
        self.logger.debug(f"New architecture skills registered")
    except ImportError as e:
        self.logger.warning(f"Failed to register new skills: {e}")
```

**验证**: 检查日志，确认 Skills 被注册

**回滚**: 删除 `_register_new_skills()` 方法和调用

---

## 阶段3：MicroAgent 改造

**目标**: 让 MicroAgent 动态组合 Mixins，移除动态绑定逻辑

### 3.1 添加 `available_skills` 参数

**修改文件**: `src/agentmatrix/agents/micro_agent.py`

```python
def __init__(
    self,
    parent,
    working_context=None,
    name=None,
    available_skills=None,  # 🆕
    **kwargs
):
    # ... 现有代码
```

**回滚**: 删除 `available_skills` 参数

---

### 3.2 实现动态类组合

**添加方法**: `MicroAgent._create_dynamic_class()`

```python
def _create_dynamic_class(self, available_skills):
    """动态创建包含 Skill Mixins 的类"""
    from ..skills.registry import SKILL_REGISTRY

    mixin_classes = SKILL_REGISTRY.get_python_mixins(available_skills)

    # 动态创建类
    dynamic_class = type(
        f'DynamicAgent_{self.name}',
        (self.__class__,) + tuple(mixin_classes),
        {}
    )

    return dynamic_class
```

**验证**: 单元测试

```python
def test_dynamic_class_creation():
    from agentmatrix.skills.file_skill import FileSkillMixin
    from agentmatrix.agents.micro_agent import MicroAgent

    # 创建测试实例
    micro = MicroAgent(parent=..., available_skills=['file'])

    # 验证继承了 FileSkillMixin
    assert hasattr(micro, 'list_dir')
    assert isinstance(micro, MicroAgent)
```

**回滚**: 删除 `_create_dynamic_class()` 方法

---

### 3.3 实现新扫描逻辑

**添加方法**: `MicroAgent._scan_all_actions()`

```python
def _scan_all_actions(self):
    """扫描自身（包括继承链）的所有 actions"""
    import inspect

    self.action_registry = {}

    for cls in self.__class__.__mro__:
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(method, '_is_action') and method._is_action:
                if name not in self.action_registry:
                    self.action_registry[name] = method
```

**验证**: 检查 `action_registry` 包含预期的 actions

**回滚**: 删除 `_scan_all_actions()` 方法

---

### 3.4 移除动态绑定逻辑

**修改方法**: `MicroAgent._execute_action()`

```python
# ❌ 旧代码
raw_method = self.action_registry[action_name]
bound_method = types.MethodType(raw_method, self)
result = await bound_method(**params)

# ✅ 新代码
method = self.action_registry[action_name]
result = await method(**params)  # 直接调用，不需要绑定
```

**验证**: 执行测试用例

**回滚**: 恢复动态绑定代码

---

### 3.5 在 BaseAgent.process_email 中传递 available_skills

**修改文件**: `src/agentmatrix/agents/base.py`

```python
async def process_email(self, email):
    # ... 现有代码

    # 🆕 从 profile 读取 skills
    available_skills = self.profile.get("skills", [])

    # 创建 MicroAgent
    micro_core = MicroAgent(
        parent=self,
        working_context=self.working_context,
        name=self.name,
        available_skills=available_skills  # 🆕
    )
```

**验证**: 检查 MicroAgent 接收到正确的 skills

**回滚**: 移除 `available_skills` 参数传递

---

## 阶段4：兼容性测试

**目标**: 确保所有现有功能正常工作

### 4.1 运行现有测试用例

```bash
# 运行所有测试
pytest tests/

# 运行特定测试
pytest tests/agents/
pytest tests/skills/
```

**验证**: 所有测试通过

**回滚**: 如果测试失败，检查阶段3的代码

---

### 4.2 创建测试 Agent

**新建文件**: `tests/integration/test_new_skill_arch.py`

```python
import pytest
from agentmatrix.agents.base import BaseAgent
from agentmatrix.skills.registry import SKILL_REGISTRY

def test_file_skill_with_new_arch():
    """测试新架构下的 FileSkill"""
    profile = {
        "name": "TestAgent",
        "description": "测试",
        "skills": ["file"]  # 🆕 使用新配置
    }

    agent = BaseAgent(profile)
    # ...
```

**验证**: 测试通过

**回滚**: 删除测试文件

---

## 阶段5：清理旧代码

**目标**: 移除不再需要的旧代码

### 5.1 移除 BaseAgent._scan_methods()

```python
# ❌ 删除
def _scan_methods(self):
    """扫描并生成元数据"""
    # ...
```

**回滚**: 从 git 恢复 `base.py`

---

### 5.2 移除 BaseAgent.actions_map 和 actions_meta

```python
# ❌ 删除
self.actions_map = {}
self.actions_meta = {}
```

**回滚**: 从 git 恢复

---

### 5.3 重命名旧 skill 文件（作为备份）

```bash
# 不直接删除，先重命名
mv src/agentmatrix/skills/file_operations_skill.py \
   src/agentmatrix/skills/file_operations_skill.py.old

mv src/agentmatrix/skills/browser_use_skill.py \
   src/agentmatrix/skills/browser_use_skill.py.old
```

**验证**: 运行测试，确认不再依赖旧文件

**回滚**: 恢复文件名

---

## 阶段6：文档更新

**目标**: 更新文档反映新架构

### 6.1 更新 README.md

添加新架构说明

**回滚**: 从 git 恢复 README.md

---

### 6.2 创建架构文档

**新建文件**: `docs/architecture/skill_system.md`

```markdown
# Skill System Architecture

## Python Method Skills
...

## MD Document Skills
...
```

**回滚**: 删除文档文件

---

## 阶段7：合并分支

**目标**: 合并到主分支

### 7.1 最后测试

```bash
# 切换到 main
git checkout main

# 合并 refactor 分支
git merge refactor/mixin-skills

# 运行完整测试
pytest tests/ -v
```

### 7.2 打 Tag

```bash
git tag -a v2.0.0-mixin-skills -m "新架构：Mixin Skills"
git push origin v2.0.0-mixin-skills
```

### 7.3 推送到远程

```bash
git push origin main
```

---

## 应急预案

### 如果阶段1-3出现问题

```bash
# 立即回滚到上一个 tag
git checkout tags/phase1-foundation

# 或回滚到 main
git checkout main
git branch -D refactor/mixin-skills
```

### 如果阶段4测试失败

1. 查看失败日志
2. 定位问题阶段
3. 回滚到该阶段之前
4. 修复问题后重新开始

```bash
# 回滚到阶段3
git checkout tags/phase3-microagent

# 修复代码
# ...

# 重新执行阶段4
```

---

## 时间估算

| 阶段 | 预计时间 | 缓冲时间 |
|------|---------|---------|
| 阶段1：基础设施 | 2小时 | 1小时 |
| 阶段2：Skill 迁移 | 4小时 | 2小时 |
| 阶段3：MicroAgent 改造 | 6小时 | 3小时 |
| 阶段4：兼容性测试 | 4小时 | 2小时 |
| 阶段5：清理旧代码 | 2小时 | 1小时 |
| 阶段6：文档更新 | 2小时 | 1小时 |
| 阶段7：合并分支 | 1小时 | 0.5小时 |
| **总计** | **21小时** | **10.5小时** |

---

## 检查清单

每个阶段完成后：

- [ ] 代码通过 linter 检查
- [ ] 单元测试通过
- [ ] 日志输出正常
- [ ] 创建 git tag
- [ ] 更新 todo list
- [ ] 记录遇到的问题和解决方案

---

## 附录：关键文件清单

### 新建文件

- `src/agentmatrix/skills/registry.py`
- `src/agentmatrix/skills/base.py`
- `src/agentmatrix/skills/file_skill.py`
- `src/agentmatrix/skills/browser_skill.py`
- `docs/architecture/skill_system.md`

### 修改文件

- `src/agentmatrix/core/action.py` (扩展)
- `src/agentmatrix/agents/base.py` (添加注册逻辑，移除扫描逻辑)
- `src/agentmatrix/agents/micro_agent.py` (动态组合，移除动态绑定)

### 备份文件

- `src/agentmatrix/skills/file_operations_skill.py.old`
- `src/agentmatrix/skills/browser_use_skill.py.old`

---

**最后更新**: 2025-02-21
**负责人**: Claude
**审核状态**: 待审核
