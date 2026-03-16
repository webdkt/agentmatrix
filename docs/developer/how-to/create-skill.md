# How-To: Create Skill

创建新 Skill 的步骤。

## 步骤

### 1. 创建目录

```bash
mkdir -p workspace/SKILLS/my_skill
```

### 2. 实现 Skill

创建 `workspace/SKILLS/my_skill/skill.py`:

```python
from agentmatrix.core.action import register_action

class MySkillMixin:
    """My Skill 描述"""
    
    _skill_description = "我的自定义 Skill"
    
    @register_action(
        short_desc="执行操作",
        description="执行具体操作并返回结果",
        param_infos={
            "input": "输入参数"
        }
    )
    async def my_action(self, input: str) -> str:
        # 实现逻辑
        result = f"Processed: {input}"
        return result
```

### 3. 创建 __init__.py

创建 `workspace/SKILLS/my_skill/__init__.py`:

```python
from .skill import MySkillMixin

__all__ = ["MySkillMixin"]
```

### 4. 在 Agent 中使用

修改 Agent profile:

```yaml
skills:
  - base
  - my_skill  # 添加新 skill
```

### 5. 重启生效

重启系统加载新 Skill。

## 依赖其他 Skills

如果依赖其他 skills：

```python
class MySkillMixin:
    _skill_dependencies = ["browser", "file"]
    
    @register_action(...)
    async def my_action(self, url: str) -> str:
        # 可以调用依赖 skill 的 actions
        await self.browser_navigate(url=url)
        content = await self.browser_get_text_content()
        return content
```

## 测试 Skill

创建测试对话验证：

```
请执行 my_action，输入 "test"
```

检查返回结果是否符合预期。
