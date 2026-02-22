# Web Search Skill 迁移指南

## 概述

已成功将 `web_searcher_v2.py` 从旧架构迁移到新架构。

## 主要变化

### 1. 文件和类命名（符合 Lazy Load 规范）

**旧架构:**
- 文件: `src/agentmatrix/skills/old_skills/web_searcher_v2.py`
- 类: `WebSearcherV2Mixin`

**新架构:**
- 文件: `src/agentmatrix/skills/web_search_skill.py`
- 类: `Web_searchSkillMixin`

**命名规则:**
- 文件名: `{name}_skill.py` → `web_search_skill.py`
- 类名: `{Name}SkillMixin` → `Web_searchSkillMixin` (使用 `name.capitalize()`)
  - 注意: 对于下划线分隔的名称，只大写首字母: `web_search` → `Web_search`

### 2. 继承关系变化

**旧架构:**
```python
class WebSearcherV2Mixin(BrowserUseSkillMixin, FileOperationSkillMixin):
    # 继承其他 Skill Mixins，直接获得其方法
```

**新架构:**
```python
class Web_searchSkillMixin:
    # 不再继承其他 Skill Mixins
    # 在创建 MicroAgent 时通过 available_skills 声明依赖
```

### 3. 依赖声明方式变化

**旧架构:**
```python
# 通过继承获得依赖
class WebSearcherV2Mixin(BrowserUseSkillMixin, FileOperationSkillMixin):
    pass

# 创建 MicroAgent 时
available_actions=[
    "use_browser",      # 来自 BrowserUseSkillMixin
    "update_dashboard", # 来自 WebSearcherV2Mixin
    "read", "write",    # 来自 FileOperationSkillMixin
    # ...
]
```

**新架构:**
```python
# 不继承，通过 available_skills 声明
result = await micro_agent.execute(
    # ... 其他参数
    available_skills=["browser", "file"],  # 声明需要的技能
)
```

## 核心功能保留

以下核心逻辑完全保持不变：

1. **主入口**: `web_search(purpose)` - 执行网络搜索
2. **Dashboard 管理**:
   - `_init_dashboard()` - 初始化白板
   - `_get_dashboard()` - 获取白板内容
   - `update_dashboard()` - 更新白板
3. **搜索循环**: `_do_search_task()` - 永久循环，每轮 30 分钟
4. **退出条件**: `_should_stop()` - 检查是否创建 final_result.md

## 使用方式

### 加载 Skill

```python
from agentmatrix.skills.registry import SKILL_REGISTRY

# 方式 1: 直接加载
result = SKILL_REGISTRY.get_skills(['web_search'])
mixin_class = result.python_mixins[0]  # Web_searchSkillMixin

# 方式 2: 通过 MicroAgent 的 available_skills（推荐）
micro_agent = MicroAgent(
    parent=agent,
    working_context=context
)
await micro_agent.execute(
    # ... 其他参数
    available_skills=["web_search"],  # Lazy Load
)
```

### 在 BaseAgent 中使用

```python
from agentmatrix.agents.base import BaseAgent
from agentmatrix.skills.registry import SKILL_REGISTRY

# 创建 Agent 并混入 web_search skill
result = SKILL_REGISTRY.get_skills(['web_search'])
agent_class = type(
    'MyAgent',
    (BaseAgent,) + tuple(result.python_mixins),
    {}
)
agent = agent_class(...)
```

## 验证

测试命令：

```bash
python3 -c "
from agentmatrix.skills.registry import SKILL_REGISTRY
result = SKILL_REGISTRY.get_skills(['web_search'])
print('✅ 加载成功')
print(f'Mixins: {[m.__name__ for m in result.python_mixins]}')
"
```

期望输出：
```
✅ 加载成功
Mixins: ['Web_searchSkillMixin']
```

## Actions

新 `web_search` skill 提供以下 actions：

1. **web_search**
   - 描述: 使用浏览器来查找需要的信息
   - 参数:
     - `purpose`: 使用浏览器的目的

2. **update_dashboard**
   - 描述: 更新白板内容
   - 参数:
     - `new_content`: （可选）完整的白板内容
     - `modification_feedback`: （可选）对白板的修改意见

## 依赖关系

新 `web_search` skill 内部创建的 MicroAgent 依赖以下 skills：

- `browser` - 提供 `use_browser` action
- `file` - 提供 `read`, `write`, `list_dir` 等文件操作 actions

这些依赖在 `_do_search_task()` 方法中通过 `available_skills` 声明：

```python
result = await micro_agent.execute(
    # ...
    available_skills=["browser", "file"],  # 声明依赖
    # ...
)
```

## 注意事项

1. **类名命名**: 对于下划线分隔的 skill 名称，类名只大写首字母
   - `"web_search"` → `"Web_searchSkillMixin"`
   - 不是 `"WebSearchSkillMixin"`

2. **不再继承**: 新架构的 Skill Mixins 不再继承其他 Skill Mixins
   - 避免复杂的继承链
   - 通过 `available_skills` 声明依赖更清晰

3. **Lazy Load**: 使用 `SKILL_REGISTRY.get_skills()` 自动发现和加载
   - 不需要手动导入和注册
   - 符合命名规范即可自动发现

## 迁移清单

- [x] 创建 `web_search_skill.py`
- [x] 重命名类为 `Web_searchSkillMixin`
- [x] 移除旧继承 (BrowserUseSkillMixin, FileOperationSkillMixin)
- [x] 更新导入语句
- [x] 修改 MicroAgent 创建，使用 `available_skills`
- [x] 保留核心逻辑不变
- [x] 验证加载成功
- [x] 验证 actions 注册

## 后续步骤

1. 旧文件 `web_searcher_v2.py` 保留在 `old_skills/` 目录作为参考
2. 更新相关文档引用
3. 更新测试用例
4. 考虑删除 `old_skills/` 中的旧实现（确认无问题后）
