NEED UPDATE
# AgentMatrix Skill 单独测试标准流程

## 适用场景

- 需要测试完整的 Skill 方法（如 `writing_loop`）
- 需要真实的 LLM 调用
- 需要加载真实的测试数据（context.json, notebook.json 等）

## 核心原理（5分钟理解）

### 为什么这样设计？

```
BaseAgent (完整基础平台)
  ↓ 提供基础能力
TestAgent (测试外壳)
  ↓ 继承 SkillMixin
SkillMixin (目标功能模块)
```

- **BaseAgent**：提供完整的基础平台（session 管理、action 注册、工具方法）
- **SkillMixin**：可插拔的功能模块（如 DeepResearcherMixin）
- **TestAgent**：最小化依赖注入，只提供测试需要的数据

### 关键架构规则

#### 1. 继承顺序

```python
class MinimalTestAgent(BaseAgent, DeepResearcherMixin):
    #                  ^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^^
    #                  基础框架       目标功能
```

**为什么 BaseAgent 在前？**
- BaseAgent 提供完整的 session 管理、action 注册、工具方法
- 测试场景不需要 Mixin 覆盖 BaseAgent 的方法（如 `all_finished`）
- 这样设计：测试 Agent 获得基础能力 + Skill 功能

**与 Loader 的区别**：
- Loader 创建：`type("Agent", (*mixins, BaseAgent), {})` → Mixin 在前，允许覆盖
- 手动定义：`class Agent(BaseAgent, Mixin)` → BaseAgent 在前，Mixin 不覆盖

#### 2. 接口实现的真相

**BaseAgent 已经提供了这些方法**：
- ✅ `get_session_context()` - 从 `self.current_session` 读取
- ✅ `update_session_context(**kwargs)` - 更新并持久化到文件
- ✅ `get_transient(key)` - 从 `self.transient_context` 读取
- ✅ `set_transient(key, value)` - 写入 `self.transient_context`
- ✅ `get_session_folder()` - 从 session 配置读取

**测试 Agent 为什么需要重新实现？**
- BaseAgent 的方法依赖完整的 session 管理机制（`self.current_session`）
- 测试场景是**静态注入**，直接提供数据即可
- 重新实现是为了返回**测试数据**，而不是触发完整的 session 加载流程

## 完整代码模板（可复制）

```python
"""
测试 [Skill名称] 的 [具体功能]

设计原则：
1. 继承 BaseAgent 获得基础框架
2. 继承 SkillMixin 获得目标功能
3. 只注入测试数据，不实现业务逻辑
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from agentmatrix.core.loader import AgentLoader
from agentmatrix.skills.[skill_module] import [TargetSkillMixin]
from agentmatrix.agents.base import BaseAgent


class MinimalTestAgent(BaseAgent, [TargetSkillMixin]):
    """最小化测试 Agent"""

    def __init__(self, context: dict, brain, session_folder: str, cerebellum=None, **kwargs):
        # 1. 调用 BaseAgent 最小初始化
        minimal_profile = {
            "name": "TestAgent",
            "description": "测试功能",
            "system_prompt": context.get("persona", "")
        }
        super().__init__(minimal_profile)

        # 2. 注入测试数据（关键！）
        self._session_context = context  # 替代 current_session
        self.brain = brain
        self.cerebellum = cerebellum  # 可选：使用 MicroAgent 的 Skill 需要
        self.current_session_folder = session_folder

        # 3. 注入 Skill 需要的数据
        for key, value in kwargs.items():
            if key == "notebook":
                self._transient_context = {"notebook": value}
            else:
                setattr(self, key, value)

        # 4. 设置 workspace_root（如果 Skill 需要文件操作）
        self.workspace_root = str(Path(session_folder).parent.parent)

    # 接口实现：返回测试数据（而不是真实 session）
    def get_session_context(self):
        """返回测试 context"""
        return self._session_context

    async def update_session_context(self, **kwargs):
        """更新测试 context（内存，不持久化）"""
        self._session_context.update(kwargs)


async def main():
    """主测试流程"""

    # 1. 配置路径
    test_session_folder = "/path/to/test/data"
    llm_config_path = "/path/to/llm_config.json"
    profile_path = "/path/to/profiles"  # 用于加载环境变量

    # 2. 加载测试数据
    import json
    with open(f"{test_session_folder}/context.json", 'r') as f:
        context = json.load(f)

    # 3. 加载 Brain
    loader = AgentLoader(profile_path=profile_path, llm_config_path=llm_config_path)
    brain = loader._create_llm_client("default_llm")

    # 可选：加载 Cerebellum（Skill 使用 MicroAgent 时需要）
    cerebellum = None
    # from agentmatrix.core.cerebellum import Cerebellum
    # cerebellum_client = loader._create_llm_client("default_slm")
    # cerebellum = Cerebellum(backend_client=cerebellum_client, agent_name="TestAgent")

    # 4. 创建测试 Agent
    test_agent = MinimalTestAgent(
        context=context,
        brain=brain,
        session_folder=test_session_folder,
        cerebellum=cerebellum,  # 可选
        # Skill 特定数据
        notebook=Notebook(file_path=f"{test_session_folder}/notebook.json")
    )

    # 5. 执行测试
    result = await test_agent.[目标方法]()

    print(f"✅ 测试完成，结果: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

## 关键步骤详解

### 步骤1：配置路径

```python
test_session_folder  # 测试数据目录（包含 context.json, notebook.json 等）
llm_config_path      # LLM 配置文件
profile_path         # Agent profiles 目录（用于加载环境变量）
```

### 步骤2：加载数据

```python
# Session context（必须）
context = json.load(open("context.json"))

# Skill 特定数据（如 Notebook）
from agentmatrix.skills.deep_researcher_helper import Notebook
notebook = Notebook(file_path="notebook.json")
```

### 步骤3：加载 Brain

```python
loader = AgentLoader(profile_path=profile_path, llm_config_path=llm_config_path)
brain = loader._create_llm_client("default_llm")

# 可选：加载 Cerebellum（Skill 使用 MicroAgent 时需要）
cerebellum = None
# from agentmatrix.core.cerebellum import Cerebellum
# cerebellum_client = loader._create_llm_client("default_slm")
# cerebellum = Cerebellum(backend_client=cerebellum_client, agent_name="TestAgent")
```

**LLM 配置选择**：
- `default_llm` - 大语言模型（推理用）
- `default_slm` - 小语言模型（快速任务、参数协商）
- `default_vision` - 视觉模型

### 步骤4：创建 Agent

```python
test_agent = MinimalTestAgent(
    context=context,
    brain=brain,
    session_folder=test_session_folder,
    notebook=notebook  # Skill 特定数据
)
```

### 步骤5：执行测试

```python
result = await test_agent.[目标方法]()
```

## 最小化实现清单

测试 Agent **必须实现**的方法：

```python
def get_session_context(self):
    """返回测试 context（必须）"""
    return self._session_context
```

**可选实现**：

```python
async def update_session_context(self, **kwargs):
    """更新测试 context（如果 Skill 会更新 context）"""
    self._session_context.update(kwargs)
```

**BaseAgent 已提供，无需实现**：
- ✅ `get_transient(key)` - 从 `self.transient_context` 读取
- ✅ `set_transient(key, value)` - 写入 `self.transient_context`
- ✅ `get_session_folder()` - 返回 session 文件夹

## 实战案例：test_writing_loop.py

### 测试目标
测试 `DeepResearcherMixin._writing_loop()` 方法

### 完整实现

```python
class MinimalTestAgent(BaseAgent, DeepResearcherMixin):
    def __init__(self, context, notebook, brain, session_folder, cerebellum=None):
        # 调用 BaseAgent 最小初始化
        minimal_profile = {
            "name": "TestWriter",
            "description": "测试 writing loop",
            "system_prompt": context.get("researcher_persona", "")
        }
        super().__init__(minimal_profile)

        # 注入测试数据
        self._session_context = context
        self._notebook = notebook
        self.brain = brain
        self.cerebellum = cerebellum  # DeepResearcher 暂不需要，但保留接口
        self._session_folder = session_folder
        self._transient_context = {"notebook": notebook}
        self.workspace_root = str(Path(session_folder).parent.parent)

    def get_session_context(self):
        return self._session_context

    async def update_session_context(self, **kwargs):
        self._session_context.update(kwargs)
        self.logger.info(f"✓ Session context updated: {list(kwargs.keys())}")

    def get_session_folder(self):
        return self._session_folder
```

### 执行测试

```python
# 加载数据
context = json.load(open("context.json"))
notebook = Notebook(file_path="notebook.json")

# 加载 Brain
loader = AgentLoader(profile_path="/path/to/profiles", llm_config_path="/path/to/llm_config.json")
brain = loader._create_llm_client("default_llm")

# 创建测试 Agent
test_agent = MinimalTestAgent(context, notebook, brain, test_session_folder)

# 执行测试
result = await test_agent._writing_loop()
```

## 数据注入模式

### 模式 A：基础数据注入

```python
def __init__(self, context, brain, session_folder, cerebellum=None):
    super().__init__(minimal_profile)

    self._session_context = context
    self.brain = brain
    self.cerebellum = cerebellum  # 可选
    self._session_folder = session_folder
    self.workspace_root = str(Path(session_folder).parent.parent)
```

### 模式 B：Skill 数据注入（transient_context）

```python
def __init__(self, context, notebook, brain, session_folder, cerebellum=None):
    # ... 基础初始化 ...

    # Skill 需要的数据放入 transient_context
    self._transient_context = {"notebook": notebook}
```

### 模式 C：混合注入（推荐）

```python
def __init__(self, context, notebook, brain, session_folder, cerebellum=None, **kwargs):
    super().__init__(minimal_profile)

    # 基础数据
    self._session_context = context
    self.brain = brain
    self.cerebellum = cerebellum  # 可选
    self._session_folder = session_folder
    self.workspace_root = str(Path(session_folder).parent.parent)

    # Skill 特定数据（通过 kwargs）
    for key, value in kwargs.items():
        if key == "notebook":
            self._transient_context = {"notebook": value}
        else:
            setattr(self, key, value)
```

## 快速检查清单

测试代码编写完成后，检查：

- [ ] 是否继承了 `BaseAgent` 和目标 `SkillMixin`？
- [ ] 是否调用了 `super().__init__(minimal_profile)`？
- [ ] 是否注入了 `brain`？
- [ ] **是否注入了 `cerebellum`（Skill 使用 MicroAgent 时需要）？**
- [ ] 是否注入了 `_session_context` 或 `current_session_folder`？
- [ ] 是否实现了 `get_session_context()`？
- [ ] 是否设置了 `workspace_root`（如果 Skill 需要文件操作）？
- [ ] Skill 需要的数据（如 notebook）是否已注入？

## 调试技巧

### 1. 打印章节映射（验证数据加载）

```python
# 在 Skill 方法中添加日志
self.logger.info(f"📋 章节映射：")
for name, heading in chapter_heading_map.items():
    self.logger.info(f"  {heading:40s} <- {name}")
```

### 2. 检查方法是否被调用

```python
def get_session_context(self):
    print(f"DEBUG: get_session_context called, returning {len(self._session_context)} keys")
    return self._session_context
```

### 3. 验证继承关系

```python
# 打印 MRO（Method Resolution Order）
print(MinimalTestAgent.__mro__)
# 应该看到：(MinimalTestAgent, BaseAgent, DeepResearcherMixin, ...)
```

### 4. 检查数据注入

```python
# 在 __init__ 后打印
print(f"DEBUG: _session_context has {len(self._session_context)} keys")
print(f"DEBUG: _transient_context has {len(self._transient_context)} keys")
print(f"DEBUG: brain = {self.brain}")
print(f"DEBUG: _session_folder = {self._session_folder}")
```

## 常见问题 FAQ

### Q: 如何处理环境变量？

A: 使用 `AgentLoader` 加载 profile_path，它会自动加载 `.env` 文件：

```python
loader = AgentLoader(profile_path="/path/to/profiles", llm_config_path="/path/to/llm_config.json")
```

### Q: 如何复用现有测试数据？

A: 直接使用已存在的 session 文件夹：

```python
test_session_folder = "/path/to/existing/session"
context = json.load(open(f"{test_session_folder}/context.json"))
```


### Q: 如何 Mock Brain 响应？

A: 创建 Mock LLMClient（适用于单元测试）：

```python
class MockLLMClient:
    async def think(self, messages):
        return {"reply": "测试响应"}
```

## 总结

### 核心原则

1. **继承 BaseAgent**：获得完整的基础框架
2. **继承 SkillMixin**：获得目标功能
3. **注入测试数据**：通过属性注入，不实现业务逻辑
4. **最小化实现**：只实现 `get_session_context()` 等必要接口

### 设计优势

- ✅ **避免复制代码**：直接使用现有实现
- ✅ **自动同步改进**：原代码优化自动受益
- ✅ **维护简单**：无需两边修改
- ✅ **测试真实**：最接近实际使用场景

### 使用流程

1. 复制本文档的代码模板
2. 修改 Skill 模块和类名
3. 修改测试数据路径
4. 运行测试

**不再需要**：从头研究如何加载 LLM、如何创建 Agent、如何实现接口等。
