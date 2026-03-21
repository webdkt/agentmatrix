# 技能系统详解

**版本**: v1.0
**最后更新**: 2026-03-19

---

## 📋 目录

- [Skill概念](#skill概念)
- [Action机制](#action机制)
- [内置Skills](#内置skills)
- [自定义Skill](#自定义skill)
- [最佳实践](#最佳实践)

---

## Skill概念

### 什么是Skill

Skill（技能）是Agent的功能模块，提供一组相关的Actions。

**特点**:
- Mixin模式设计
- 可插拔组合
- 统一的Action注册
- 独立开发和测试

### Skill vs Action

| 维度 | Skill | Action |
|------|-------|--------|
| 粒度 | 粗粒度（模块） | 细粒度（函数） |
| 职责 | 提供相关功能组 | 执行具体操作 |
| 组合 | Agent组合多个Skill | Skill包含多个Action |
| 示例 | FileSkill | read_file, write_file |

### Skill架构

```
Agent
├── Skill1 (e.g., BaseSkill)
│   ├── Action1.1
│   ├── Action1.2
│   └── Action1.3
├── Skill2 (e.g., FileSkill)
│   ├── Action2.1
│   └── Action2.2
└── Skill3 (e.g., BrowserSkill)
    ├── Action3.1
    └── Action3.2
```

---

## Action机制

### Action定义

Action是Skill中的具体功能，是一个可调用的函数。

**特点**:
- 统一的签名
- 参数验证
- 返回值规范
- 错误处理

### Action签名

```python
def action(self, **params) -> Any:
    """
    Action函数签名

    Args:
        **params: Action参数

    Returns:
        Any: Action结果

    Raises:
        Exception: Action执行失败
    """
    # 实现逻辑
    pass
```

### Action注册

```python
class BaseSkill:
    def __init__(self):
        super().__init__()
        # 注册Action
        self.register_action("action_name", self.action_method)

    def action_method(self, **params):
        # Action实现
        pass
```

### Action调用

```python
# Agent内部调用
result = agent.execute_action("action_name", param1=value1, param2=value2)

# 通过Brain调用
brain.think("I need to action_name with param1=value1")
# Brain会解析并调用相应的Action
```

---

## 内置Skills

### BaseSkill

**位置**: `src/agentmatrix/skills/base/`

**描述**: 基础技能，提供基本功能

**Actions**:
- `get_current_time`: 获取当前时间
- `ask_user`: 向用户提问
- `wait_for_user`: 等待用户输入

**使用示例**:
```python
from agentmatrix.skills import BaseSkill

agent = BaseAgent(agent_name="MyAgent")
agent.add_skill(BaseSkill())

# 调用Action
result = agent.execute_action("get_current_time")
```

---

### FileSkill

**位置**: `src/agentmatrix/skills/file_skill.py`

**描述**: 文件操作技能

**Actions**:
- `read_file`: 读取文件
- `write_file`: 写入文件
- `list_files`: 列出目录文件
- `search_files`: 搜索文件

**使用示例**:
```python
from agentmatrix.skills import FileSkill

agent.add_skill(FileSkill())

# 读取文件
content = agent.execute_action("read_file", path="/path/to/file.txt")

# 写入文件
agent.execute_action("write_file", path="/path/to/file.txt", content="Hello")

# 列出文件
files = agent.execute_action("list_files", path="/path/to/dir")
```

---

### BrowserSkill

**位置**: `src/agentmatrix/skills/browser_skill.py`

**描述**: 浏览器自动化技能

**Actions**:
- `open_page`: 打开网页
- `click`: 点击元素
- `input`: 输入文本
- `extract_text`: 提取文本
- `screenshot`: 截图

**使用示例**:
```python
from agentmatrix.skills import BrowserSkill

agent.add_skill(BrowserSkill())

# 打开网页
agent.execute_action("open_page", url="https://example.com")

# 点击元素
agent.execute_action("click", selector="#button")

# 提取文本
text = agent.execute_action("extract_text", selector="#content")
```

---

### MarkdownSkill

**位置**: `src/agentmatrix/skills/markdown/`

**描述**: Markdown处理技能

**Actions**:
- `render_markdown`: 渲染Markdown
- `convert_to_html`: 转换为HTML
- `extract_headers`: 提取标题

**使用示例**:
```python
from agentmatrix.skills import MarkdownSkill

agent.add_skill(MarkdownSkill())

# 渲染Markdown
html = agent.execute_action("render_markdown", markdown="# Hello")
```

---

### SchedulerSkill

**位置**: `src/agentmatrix/skills/scheduler/`

**描述**: 调度技能

**Actions**:
- `schedule_task`: 调度任务
- `cancel_task`: 取消任务
- `list_tasks`: 列出任务

**使用示例**:
```python
from agentmatrix.skills import SchedulerSkill

agent.add_skill(SchedulerSkill())

# 调度任务
agent.execute_action("schedule_task", task_id="task1", delay=60)
```

---

## 自定义Skill

### 创建Skill

#### 1. 继承BaseSkill

```python
from agentmatrix.skills.base import BaseSkill

class MySkill(BaseSkill):
    """自定义技能"""

    def __init__(self):
        super().__init__()
        # 注册Actions
        self.register_action("my_action", self.my_action)

    def my_action(self, **params):
        """Action实现"""
        # 获取参数
        param1 = params.get("param1", "default")

        # 执行逻辑
        result = do_something(param1)

        # 返回结果
        return result
```

#### 2. 添加多个Actions

```python
class MySkill(BaseSkill):
    def __init__(self):
        super().__init__()
        # 注册多个Actions
        self.register_action("action1", self.action1)
        self.register_action("action2", self.action2)
        self.register_action("action3", self.action3)

    def action1(self, **params):
        """Action1实现"""
        pass

    def action2(self, **params):
        """Action2实现"""
        pass

    def action3(self, **params):
        """Action3实现"""
        pass
```

#### 3. 添加依赖

```python
class MySkill(BaseSkill):
    def __init__(self, dependency=None):
        super().__init__()
        self.dependency = dependency
        self.register_action("my_action", self.my_action)

    def my_action(self, **params):
        """使用依赖"""
        if self.dependency:
            return self.dependency.do_something(params)
        return None
```

### 使用自定义Skill

```python
# 创建Agent
agent = BaseAgent(agent_name="MyAgent")

# 添加自定义Skill
agent.add_skill(MySkill())

# 调用Action
result = agent.execute_action("my_action", param1="value1")
```

### Skill组合

```python
# 组合多个Skills
agent = BaseAgent(agent_name="MyAgent")
agent.add_skill(BaseSkill())      # 基础技能
agent.add_skill(FileSkill())      # 文件技能
agent.add_skill(BrowserSkill())   # 浏览器技能
agent.add_skill(MySkill())        # 自定义技能
```

---

## 最佳实践

### 1. Skill设计

```python
# 好的Skill设计
class GoodSkill(BaseSkill):
    """清晰的单职责"""

    def __init__(self):
        super().__init__()
        self.register_action("read", self.read)
        self.register_action("write", self.write)

    def read(self, **params):
        """读取操作"""
        pass

    def write(self, **params):
        """写入操作"""
        pass

# 不好的Skill设计
class BadSkill(BaseSkill):
    """职责不清"""

    def __init__(self):
        super().__init__()
        self.register_action("read", self.read)
        self.register_action("write", self.write)
        self.register_action("browse", self.browse)  # 不相关
        self.register_action("calculate", self.calculate)  # 不相关
```

### 2. Action命名

```python
# 好的Action命名
self.register_action("read_file", self.read_file)
self.register_action("write_file", self.write_file)
self.register_action("list_files", self.list_files)

# 不好的Action命名
self.register_action("do_it", self.do_it)
self.register_action("action1", self.action1)
```

### 3. 参数验证

```python
def my_action(self, **params):
    """参数验证"""
    # 必需参数
    if "required_param" not in params:
        raise ValueError("required_param is required")

    # 类型验证
    count = params.get("count", 0)
    if not isinstance(count, int):
        raise TypeError("count must be an integer")

    # 范围验证
    if count < 0 or count > 100:
        raise ValueError("count must be between 0 and 100")

    # 执行逻辑
    return do_something(count)
```

### 4. 错误处理

```python
def my_action(self, **params):
    """错误处理"""
    try:
        result = do_something(params)
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        logger.error(f"Action failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
```

### 5. 文档字符串

```python
def my_action(self, **params):
    """
    我的Action

    Args:
        param1 (str): 参数1的说明
        param2 (int): 参数2的说明

    Returns:
        dict: 结果说明

    Raises:
        ValueError: 参数无效时
        Exception: 其他错误
    """
    pass
```

### 6. 测试

```python
import unittest

class TestMySkill(unittest.TestCase):
    def setUp(self):
        self.skill = MySkill()

    def test_my_action(self):
        """测试Action"""
        result = self.skill.my_action(param1="value1")
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")

    def test_my_action_with_invalid_params(self):
        """测试参数验证"""
        with self.assertRaises(ValueError):
            self.skill.my_action(invalid_param="value")
```

---

## Skill开发流程

### 1. 设计Skill

```python
# 确定Skill职责
# - 需要提供哪些功能？
# - 需要哪些Actions？
# - 需要哪些依赖？

# 设计Action接口
# - Action名称
# - 参数列表
# - 返回值
```

### 2. 实现Skill

```python
class MySkill(BaseSkill):
    def __init__(self):
        super().__init__()
        # 注册Actions
        self.register_action("action1", self.action1)

    def action1(self, **params):
        # 参数验证
        # 执行逻辑
        # 返回结果
        pass
```

### 3. 测试Skill

```python
# 单元测试
# - 测试每个Action
# - 测试参数验证
# - 测试错误处理

# 集成测试
# - 测试与Agent的集成
# - 测试与其他Skill的交互
```

### 4. 文档

```python
# 编写文档
# - Skill描述
# - Action说明
# - 使用示例
# - 参数说明
```

### 5. 发布

```python
# 打包Skill
# - 创建setup.py
# - 编写README
# - 发布到PyPI（可选）
```

---

## 相关文档

- **[架构概览](./architecture.md)** - 系统架构
- **[组件参考](./component-reference.md)** - Skill API
- **[Agent系统](./agent-system.md)** - Agent技能组合
- **[核心概念](../concepts/CONCEPTS.md)** - 核心概念定义

---

**维护者**: AgentMatrix Team
**下次审查**: 每季度
