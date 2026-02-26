# AgentMatrix Skill 单独测试标准流程（新架构）

## 适用场景

- 需要测试完整的 Skill 方法（如 FileSkill, BrowserSkill）
- 需要验证 Skill 的所有 actions
- 需要测试 Skill 与其他组件的集成

## 核心原理（5分钟理解）

### 新架构设计

```
SKILL_REGISTRY (统一注册中心)
  ↓ Lazy Load by Name
MicroAgent (动态类组合)
  ↓ 继承 Skill Mixins
FileSkillMixin / BrowserSkillMixin (可插拔功能模块)
```

**关键特性：**
- **Lazy Load**：根据名字自动发现并加载 `{name}_skill.py`
- **动态类组合**：MicroAgent 在运行时动态继承 Skill Mixins
- **无 Hardcode**：添加新 skill 无需修改 BaseAgent 或 MicroAgent
- **统一接口**：`SKILL_REGISTRY.get_skills(skill_names)`

### 名字约定

```
skill_name: "file"
  ↓
模块: agentmatrix.skills.file_skill
类名: FileSkillMixin
```

### 关键架构规则

#### 1. Lazy Load 机制

**注册表初始为空：**
```python
# 开始时注册表为空
SKILL_REGISTRY._python_mixins = {}  # 空
```

**首次请求时自动导入：**
```python
# 用户请求 "file" skill
result = SKILL_REGISTRY.get_skills(["file"])

# 自动执行：
# 1. import agentmatrix.skills.file_skill
# 2. 获取 FileSkillMixin 类
# 3. 缓存到 _python_mixins["file"]
```

**后续请求直接使用缓存：**
```python
# 第二次请求直接从缓存获取
result = SKILL_REGISTRY.get_skills(["file"])  # 无需重新导入
```

#### 2. MicroAgent 动态类组合

```python
# micro_agent.py
def _create_dynamic_class(self, available_skills: List[str]) -> type:
    from ..skills.registry import SKILL_REGISTRY

    # 1. Lazy Load 获取 Mixins
    result = SKILL_REGISTRY.get_skills(available_skills)
    mixin_classes = result.python_mixins

    # 2. 动态创建类
    dynamic_class = type(
        f'DynamicAgent_{self.name}',
        (self.__class__,) + tuple(mixin_classes),  # (MicroAgent, FileSkillMixin, ...)
        {}
    )

    # 3. 替换当前实例的类
    self.__class__ = dynamic_class
```

**效果：**
```python
# 之前
agent = MicroAgent()  # 只有基础方法

# 之后
agent = MicroAgent(available_skills=["file", "browser"])
agent.__class__.__mro__
# (DynamicAgent_Agent, MicroAgent, FileSkillMixin, BrowserSkillMixin, ...)
```

#### 3. Action 扫描（新架构）

**BaseAgent 和 MicroAgent 都使用相同机制：**

```python
def _scan_all_actions(self):
    """扫描所有 @register_action 方法"""
    import inspect

    for cls in self.__class__.__mro__:  # 遍历继承链
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(method, '_is_action') and method._is_action:
                # 存储已绑定的方法（直接可调用）
                self.action_registry[name] = getattr(self, name)
```

**关键改进：**
- ✅ 使用 `action_registry` 代替 `actions_map`
- ✅ 存储已绑定的方法（直接调用），无需动态绑定
- ✅ 统一扫描机制（BaseAgent 和 MicroAgent 相同）
- ✅ `self` 始终指向最终实例

## 测试方法

### 方法 1：集成测试（推荐）

**适用场景：** 测试 Skill 与 MicroAgent 的集成

```python
"""
测试 FileSkill（新架构）

集成测试：验证 Skill 与 MicroAgent 的完整集成
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agentmatrix.agents.micro_agent import MicroAgent
from agentmatrix.core.working_context import WorkingContext
from agentmatrix.core.log_util import AutoLoggerMixin


class MockParent(AutoLoggerMixin):
    """模拟 parent Agent（BaseAgent）"""

    _log_from_attr = "name"

    def __init__(self):
        self.name = "MockParent"
        self._init_logger()

        # 模拟 BaseAgent 的属性
        self.brain = None
        self.cerebellum = None
        self.working_context = None

        # 注册 Skill（测试环境需要手动注册）
        from agentmatrix.skills.file_skill import FileSkillMixin
        from agentmatrix.skills.registry import SKILL_REGISTRY
        SKILL_REGISTRY.register_python_mixin("file", FileSkillMixin)

    def _get_log_context(self):
        return {"name": self.name}


async def test_file_skill():
    """测试 FileSkill 功能"""

    # 1. 创建临时工作目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 创建测试文件
        test_file = temp_path / "test.txt"
        test_file.write_text("Hello, World!")

        # 创建 WorkingContext
        working_context = WorkingContext(
            base_dir=str(temp_path),
            current_dir=str(temp_path)
        )

        # 2. 创建 Mock Parent
        mock_parent = MockParent()

        # 3. 创建 MicroAgent（新架构：动态继承 FileSkillMixin）
        micro_agent = MicroAgent(
            parent=mock_parent,
            working_context=working_context,
            name="TestAgent",
            available_skills=["file"]  # 🆕 新架构参数
        )

        # 4. 验证继承链
        from agentmatrix.skills.file_skill import FileSkillMixin
        assert isinstance(micro_agent, FileSkillMixin)

        # 5. 测试 actions
        result = await micro_agent.list_dir()
        assert "test.txt" in result

        result = await micro_agent.read("test.txt")
        assert "Hello, World!" in result

        print("✅ 所有测试通过！")


if __name__ == "__main__":
    asyncio.run(test_file_skill())
```

### 方法 2：单元测试（Skill 独立测试）

**适用场景：** 只测试 Skill 的单个方法

```python
"""
测试 FileSkill 单元功能
"""

import asyncio
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agentmatrix.skills.file_skill import FileSkillMixin
from agentmatrix.core.working_context import WorkingContext
from agentmatrix.core.log_util import AutoLoggerMixin


class TestAgent(AutoLoggerMixin, FileSkillMixin):
    """测试 Agent：直接继承 Skill Mixin"""

    _log_from_attr = "name"

    def __init__(self, working_context):
        self.name = "TestAgent"
        self._init_logger()
        self.working_context = working_context

    def _get_log_context(self):
        return {"name": self.name}


async def test_file_read():
    """测试文件读取"""

    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建测试文件
        test_file = Path(temp_dir) / "test.txt"
        test_file.write_text("Test Content")

        # 创建 WorkingContext
        working_context = WorkingContext(
            base_dir=temp_dir,
            current_dir=temp_dir
        )

        # 创建测试 Agent
        agent = TestAgent(working_context)

        # 测试 read action
        result = await agent.read("test.txt")
        assert "Test Content" in result

        print("✅ 单元测试通过！")


if __name__ == "__main__":
    asyncio.run(test_file_read())
```

### 方法 3：验证 Lazy Load

**适用场景：** 验证 Lazy Load 机制工作正常

```python
"""
测试 Lazy Load 机制
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agentmatrix.skills.registry import SKILL_REGISTRY


def test_lazy_load():
    """测试 Lazy Load 机制"""

    print("=" * 60)
    print("测试 Lazy Load 机制")
    print("=" * 60)

    # 1. 初始状态为空
    print("\n1️⃣ 初始状态（应该为空）:")
    print(f"   Python Mixins: {list(SKILL_REGISTRY._python_mixins.keys())}")
    assert len(SKILL_REGISTRY._python_mixins) == 0

    # 2. Lazy load "file" skill
    print("\n2️⃣ Lazy load \"file\" skill:")
    result = SKILL_REGISTRY.get_skills(["file"])
    print(f"   结果: {result}")
    assert "file" in SKILL_REGISTRY._python_mixins
    assert len(result.python_mixins) == 1

    # 3. Lazy load "browser" skill
    print("\n3️⃣ Lazy load \"browser\" skill:")
    result = SKILL_REGISTRY.get_skills(["browser"])
    print(f"   结果: {result}")
    assert "browser" in SKILL_REGISTRY._python_mixins

    # 4. 缓存测试（第二次加载应该使用缓存）
    print("\n4️⃣ 缓存测试（第二次加载 \"file\"）:")
    result = SKILL_REGISTRY.get_skills(["file"])
    print(f"   结果: {result} (应该直接从缓存获取)")

    # 5. 加载不存在的 skill
    print("\n5️⃣ 加载不存在的 skill (\"nonexistent\"):")
    result = SKILL_REGISTRY.get_skills(["nonexistent"])
    print(f"   结果: {result}")
    assert len(result.failed_skills) == 1
    assert "nonexistent" in result.failed_skills

    print("\n" + "=" * 60)
    print("✅ Lazy Load 机制测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_lazy_load()
```


## 完整示例：创建新 Skill

### 1. 创建 Skill 文件

```python
# src/agentmatrix/skills/my_custom_skill.py

from ..core.action import register_action

class MyCustomSkillMixin:
    """自定义技能 Mixin"""

    @register_action(
        description="做一个自定义操作",
        param_infos={
            "param1": "参数1说明",
            "param2": "参数2说明（可选）"
        }
    )
    async def custom_action(self, param1: str, param2: str = None) -> str:
        """
        执行自定义操作

        Args:
            param1: 必需参数
            param2: 可选参数

        Returns:
            操作结果
        """
        # 实现你的逻辑
        result = f"执行了自定义操作：{param1}"
        if param2:
            result += f"，{param2}"

        return result
```

### 2. 使用新 Skill

```python
# 在 profile.yml 中配置
skills:
  - file
  - browser
  - my_custom  # 🆕 添加你的 skill
```

```python
# 在代码中使用
agent = MicroAgent(
    parent=parent,
    working_context=working_context,
    name="MyAgent",
    available_skills=["file", "browser", "my_custom"]  # 🆕 自动发现并加载
)

# 直接调用
result = await agent.custom_action(param1="test")
```

### 3. 测试新 Skill

```python
# tests/integration/test_my_custom_skill.py

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from agentmatrix.agents.micro_agent import MicroAgent
from agentmatrix.core.working_context import WorkingContext
from agentmatrix.core.log_util import AutoLoggerMixin


class MockParent(AutoLoggerMixin):
    def __init__(self):
        self.name = "MockParent"
        self._init_logger()
        self.brain = None
        self.cerebellum = None
        self.working_context = None

        # 注册新 skill
        from agentmatrix.skills.my_custom_skill import MyCustomSkillMixin
        from agentmatrix.skills.registry import SKILL_REGISTRY
        SKILL_REGISTRY.register_python_mixin("my_custom", MyCustomSkillMixin)


async def test_my_custom_skill():
    """测试自定义 Skill"""

    # 创建 WorkingContext
    working_context = WorkingContext(base_dir="/tmp", current_dir="/tmp")

    # 创建 Mock Parent
    mock_parent = MockParent()

    # 创建 MicroAgent（包含自定义 skill）
    agent = MicroAgent(
        parent=mock_parent,
        working_context=working_context,
        name="TestAgent",
        available_skills=["my_custom"]
    )

    # 测试自定义 action
    result = await agent.custom_action(param1="test", param2="extra")
    assert "test" in result
    assert "extra" in result

    print("✅ 自定义 Skill 测试通过！")


if __name__ == "__main__":
    asyncio.run(test_my_custom_skill())
```

## 常见问题

### Q1: 为什么测试环境需要手动注册 Skill？

**A:** 测试环境不经过完整的 BaseAgent 初始化流程，所以需要手动注册。生产环境中，SKILL_REGISTRY 会自动 Lazy Load。

### Q2: 如何确认 Skill 被正确加载？

**A:** 检查继承链：

```python
from agentmatrix.skills.file_skill import FileSkillMixin

assert isinstance(agent, FileSkillMixin)
print(agent.__class__.__mro__)
# (DynamicAgent_Agent, MicroAgent, FileSkillMixin, ...)
```

### Q3: 如何测试加载失败的 Skill？

**A:** 检查 `failed_skills`：

```python
result = SKILL_REGISTRY.get_skills(["nonexistent"])
assert "nonexistent" in result.failed_skills
```

### Q4: 如何同时测试多个 Skills？

**A:** 在 `available_skills` 中指定多个：

```python
agent = MicroAgent(
    parent=mock_parent,
    working_context=working_context,
    name="TestAgent",
    available_skills=["file", "browser"]  # 多个 skills
)
```

## 总结

**新架构核心优势：**
1. **Lazy Load**：按需加载，无需 hardcode
2. **动态组合**：运行时动态继承 Skill Mixins
3. **统一机制**：BaseAgent 和 MicroAgent 使用相同的 action 扫描
4. **简化调用**：直接调用已绑定方法，无需动态绑定
5. **易于扩展**：添加新 skill 只需创建文件，无需修改现有代码

**测试要点：**
1. 集成测试：验证 Skill 与 MicroAgent 的集成
2. 单元测试：直接继承 Skill Mixin 进行测试
3. Lazy Load 测试：验证按名字自动发现机制
