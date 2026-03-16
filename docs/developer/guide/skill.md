# Skill Development

Skill 开发指南。

## Skill 架构

Skill 是基于 Mixin 模式的可复用 Action 集合。

```
MicroAgent
    └── SkillMixins (组合)
            ├── BaseSkillMixin
            ├── BrowserSkillMixin
            └── CustomSkillMixin
```

## 创建 Skill

### 1. Skill 目录结构

```
my_skill/
├── __init__.py      # 暴露 Mixin
└── skill.py         # Skill 实现
```

### 2. 实现 Skill Mixin

```python
from agentmatrix.core.action import register_action

class MySkillMixin:
    """Skill 描述"""
    
    _skill_description = "我的 Skill"
    _skill_dependencies = ["file"]  # 可选：声明依赖
    
    @register_action(
        short_desc="简短描述",
        description="详细描述（给 LLM 看）",
        param_infos={
            "param1": "参数1说明",
            "param2": "参数2说明 (optional)"
        }
    )
    async def my_action(self, param1: str, param2: str = "default") -> str:
        """
        Action 实现。
        
        self 指向 MicroAgent 实例，可以访问：
        - self.brain: LLM 客户端
        - self.working_context: 工作上下文
        - self.logger: 日志
        """
        result = await self._do_something(param1)
        return f"Result: {result}"
```

### 3. 注册 Skill

`__init__.py`:

```python
from .skill import MySkillMixin

__all__ = ["MySkillMixin"]
```

### 4. 使用 Skill

Agent profile:

```yaml
skills:
  - my_skill
```

## Skill 存放位置

| 位置 | 用途 |
|------|------|
| `src/agentmatrix/skills/` | 内置 Skills |
| `workspace/SKILLS/` | 用户自定义 Skills |

### 加载优先级

1. 先搜索 `workspace/SKILLS/`
2. 再搜索 `src/agentmatrix/skills/`
3. 同名时用户版本优先

## Action 注册

### @register_action 参数

| 参数 | 说明 |
|------|------|
| `short_desc` | 简短描述（给开发者看） |
| `description` | 详细描述（给 LLM 看） |
| `param_infos` | 参数字典 `{name: description}` |

### 参数类型规则

LLM 生成函数调用时，参数会作为字符串传递。定义明确的类型注解：

```python
# 好的示例
async def search(self, query: str, limit: int = 10) -> str:

# 避免复杂类型
async def bad(self, config: dict) -> str:  # 不推荐
```

## Skill 依赖

声明依赖确保加载顺序：

```python
class AdvancedSkillMixin:
    _skill_dependencies = ["browser", "file"]
```

特性：
- 自动解析依赖链
- 检测循环依赖
- 去重加载

## 内置 Skills

| Skill | 功能 | Actions |
|-------|------|---------|
| `base` | 基础功能 | `get_current_datetime`, `ask_user` |
| `browser` | 浏览器控制 | `browser_navigate`, `browser_click` |
| `file` | 文件操作 | `file_read`, `file_write` |
| `email` | 邮件发送 | `send_email` |
| `memory` | 知识库 | `memory_query`, `memory_add` |
| `scheduler` | 定时任务 | `schedule_task` |

## 最佳实践

1. **单一职责**：一个 Skill 只做一件事
2. **依赖声明**：显式声明依赖的 Skills
3. **参数简化**：Action 参数用基础类型（str, int, bool）
4. **返回字符串**：Action 返回人类可读的字符串结果
5. **错误处理**：内部捕获异常，返回错误描述
