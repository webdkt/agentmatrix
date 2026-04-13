# Python Skill 机制

## 技能的概念

技能（Skill）是智能体能力的扩展单位。一个技能定义了一组相关的动作（Actions），给智能体增加特定的能力。

技能是 Python 的 Mixin 类。通过继承机制，技能的方法被动态混入 MicroAgent。每个技能是独立的模块，可以被多个智能体重用。

## 技能的命名规范

- **技能名称**：小写字母和下划线，如 `file`、`email`、`deep_researcher`
- **技能类名**：大驼峰 + `SkillMixin` 后缀，如 `FileSkillMixin`
- **动作名称**：动词或动词短语，如 `read_file`、`search_conversations`

这些命名约定让系统能自动发现和加载技能。

## 文件结构

技能支持两种文件结构。

### 目录结构（推荐）

适用于需要多个文件的复杂技能：

```
my_skill/
├── skill.py          # 必需：技能入口，包含 MySkillMixin 类
├── __init__.py       # 可选：让目录成为 Python 包
├── helper.py         # 可选：辅助函数
└── config.json       # 可选：配置文件
```

### 扁平文件结构（向后兼容）

适用于简单的单文件技能：

```
my_skill_skill.py     # 单个文件，包含 My_skillSkillMixin 类
```

## 如何创建新技能

让我们通过一个简化示例学习核心概念。

### 步骤 1：定义技能类

创建文件（目录结构或扁平文件），定义 Mixin 类：

```python
from agentmatrix.core.action import register_action

class CalculatorSkillMixin:
    """计算器技能"""

    # 技能级别描述（会出现在 System Prompt 中）
    _skill_description = "计算器技能。提供基本的数学计算功能。"
```

### 步骤 2：使用装饰器注册动作

每个动作用 `@register_action` 装饰器注册：

```python
    @register_action(
        short_desc="加法运算[a, b]",
        description="计算两个数的和。支持整数和浮点数。",
        param_infos={
            "a": "第一个数",
            "b": "第二个数",
        },
    )
    async def add(self, a: float, b: float) -> str:
        """计算两个数的和"""
        result = a + b
        return f"{a} + {b} = {result}"
```

这就是你需要知道的核心代码。装饰器标记了这是一个动作，并提供了元数据。

### 步骤 3：在 Agent 配置中使用

在 Agent 的 YAML 配置中引用技能：

```yaml
name: "CalculatorBot"
persona: "你是一个计算器助手。"
skills: ["base", "calculator"]
```

系统会自动发现并加载 `calculator` 技能。

## 装饰器参数说明

`@register_action` 装饰器的参数会被系统自动提取和使用：

- `short_desc`：简短描述，出现在 System Prompt 的动作列表中，格式为 `action_name[params]`
- `description`：详细描述，帮助大语言模型理解动作的用途
- `param_infos`：参数说明字典，告诉模型每个参数的含义

装饰器会在函数上设置特殊属性（如 `_is_action`、`_action_short_desc` 等），后续被用于扫描和注册。

## 技能加载流程

技能的加载是自动的。当创建 MicroAgent 时：

```
用户指定 available_skills
       ↓
SKILL_REGISTRY 检查缓存
       ↓
未缓存 → 递归加载技能及依赖
       ↓
按优先级搜索（目录结构 → 扁平文件）
       ↓
导入模块，提取 Mixin 类
       ↓
动态创建类，混入技能方法
       ↓
扫描并注册所有动作
```

这个过程中，系统会自动：
- 检测和解决循环依赖
- 处理命名冲突
- 去重（每个技能只加载一次）

## 方法如何绑定到 MicroAgent

方法绑定通过 Python 的动态类创建实现。

系统创建一个新类，继承自 `MicroAgent` 和所有技能的 Mixin 类。然后替换当前实例的类，让实例立即获得所有技能的方法。

绑定后，系统扫描所有带 `@register_action` 装饰器的方法，注册到 `action_registry`。

## 命名冲突处理

如果多个技能定义了同名动作，系统会自动重命名：

- `file.read` → 注册为 `file.read`（完整命名）
- `custom.read` → 注册为 `custom.read`（完整命名）
- 在 `_flat` 注册表中，两者都可用
- 智能体可以使用完整命名避免歧义

## System Prompt 生成

动作的元数据被自动提取到 System Prompt 中。

生成过程：

```
遍历 action_registry["_by_skill"]
       ↓
对每个技能：
  - 获取 _skill_description
  - 遍历该技能的所有动作
  - 提取 _action_short_desc
       ↓
格式化为 Markdown
       ↓
注入到 System Prompt 模板
```

生成的格式：

```markdown
**calculator**: 计算器技能。提供基本的数学计算功能。
  • add: 加法运算[a, b]
  • divide: 除法运算[a, b]
```

智能体看到这个列表，就知道可以调用哪些动作以及如何使用。

## 技能上下文和生命周期

每个技能有独立的上下文空间（`skill_context`），用于存储状态：

```python
# 在技能方法中
ns = self.skill_context.setdefault("my_skill", {})
ns["counter"] = ns.get("counter", 0) + 1
```

技能可以定义 `skill_cleanup` 方法，在 MicroAgent 销毁时被调用，用于释放资源（如关闭连接、清理临时文件）。

## 技能依赖

技能可以声明依赖：

```python
class AdvancedSkillMixin:
    _skill_dependencies = ["base", "file"]  # 声明依赖
    ...
```

系统会自动加载依赖，确保依赖在使用前已经可用。

## 总结

Python Skill 机制通过装饰器注册、Lazy Load 加载、动态类创建等机制，实现了一个灵活的技能系统。

核心要点：
1. 用 `@register_action` 装饰器定义动作
2. 遵循命名约定（类名、文件名）
3. 系统自动发现、加载、绑定
4. 元数据自动进入 System Prompt

理解这些，你就能轻松扩展智能体的能力。
