# MicroAgent 架构修复总结

## 🐛 发现的问题

### 问题 1：`missing 1 required positional argument: 'self'`

**错误信息**：
```
Error executing web_search: Web_searchSkillMixin.web_search() missing 1 required positional argument: 'self'
```

**根本原因**：
`_scan_all_actions()` 存储的是**未绑定函数**（raw function），调用时缺少 `self` 参数。

**修复**：
```python
# 旧代码（错误）
self.action_registry[name] = method  # 未绑定函数

# 新代码（正确）
bound_method = getattr(self, name)  # 绑定方法
self.action_registry[name] = bound_method
```

**文件**：`src/agentmatrix/agents/micro_agent.py:218-221`

---

### 问题 2：Mark Agent 拥有不该有的 skills

**现象**：
- Mark 只配置了 `web_search`
- 但却拥有了 `file` 和 `browser` 的 actions

**分析**：
这是**正常行为**！因为：
1. `web_search` 声明了依赖：`_skill_dependencies = ["browser", "file"]`
2. 系统自动加载了依赖的 skills
3. 符合**依赖自动解析**的设计

**正确理解**：
```yaml
# Mark 的配置
skills:
  - web_search  # 只配置了一个 skill

# 但 web_search 内部需要 browser 和 file
# 所以系统自动加载了它们
```

---

### 问题 3：web_search 内部创建 MicroAgent 时 `available_skills` 位置错误

**错误代码**：
```python
micro_agent = MicroAgent(
    parent=self,
    working_context=working_context
)

result = await micro_agent.execute(
    available_skills=["browser", "file"],  # ❌ 错误位置
    ...
)
```

**问题分析**：
- 我们已经删除了 `execute()` 的 `available_skills` 参数
- 应该在 **MicroAgent 初始化时**设置 skills

**修复**：
```python
micro_agent = MicroAgent(
    parent=self,
    working_context=working_context,
    available_skills=["browser", "file"]  # ✅ 正确位置：初始化时
)

result = await micro_agent.execute(
    # 不再传递 available_skills
    ...
)
```

**文件**：`src/agentmatrix/skills/web_search_skill.py:349-362`

---

## 🔧 架构澄清

### `available_skills` 的正确使用

**初始化时设置**（✅ 正确）：
```python
# BaseAgent 创建 MicroAgent
micro_agent = MicroAgent(
    parent=self,
    available_skills=["file", "browser"]  # ← 在这里
)

result = await micro_agent.execute(
    run_label="...",
    persona="...",
    task="..."
    # 不需要 available_skills
)
```

**错误的用法**（❌ 不要这样）：
```python
# 不要在 execute() 时传递
result = await micro_agent.execute(
    available_skills=["file", "browser"]  # ❌ 参数已删除
)
```

### 依赖自动解析机制

**Skill 依赖声明**：
```python
class Web_searchSkillMixin:
    # 声明依赖
    _skill_dependencies = ["browser", "file"]
```

**自动加载流程**：
```python
# 用户配置
skills: ["web_search"]

# 系统自动处理
1. 加载 web_search
2. 检测到 _skill_dependencies
3. 自动加载 browser
4. 自动加载 file
5. 按照 file → browser → web_search 顺序加载（依赖优先）
```

**验证**：
```python
# Mark Agent 最终拥有的 skills
skills_configured = ["web_search"]  # 配置的
skills_loaded = ["file", "browser", "web_search"]  # 实际加载的（包括依赖）
```

---

### 问题 3：MicroAgent 缺少 `workspace_root` 属性

**错误信息**：
```
ValueError: workspace_root 未设置，无法确定 llm_config.json 路径
```

**根本原因**：
1. BaseAgent 有 `workspace_root` 属性，由 `runtime.py:247` 设置：
   ```python
   agent.workspace_root = self.matrix_path
   ```

2. MicroAgent 从 parent 继承了 `brain`、`cerebellum`，但**没有继承 `workspace_root`**

3. 当 web_search 创建内部 MicroAgent 时：
   - MicroAgent 混入了 BrowserSkillMixin
   - BrowserSkillMixin 的方法（如 `_get_browser()` line 437）访问 `self.workspace_root`
   - 但 `self` 是 MicroAgent，没有这个属性
   - 报错：`workspace_root 未设置`

**修复**：
在 MicroAgent 的 `__init__` 中，从 parent 继承 `workspace_root` 属性：

```python
# ========== 继承 workspace_root（如果 parent 有）==========
# 这样 BrowserSkillMixin 等技能可以访问到配置文件路径
if hasattr(parent, 'workspace_root') and parent.workspace_root:
    self.workspace_root = parent.workspace_root
```

**文件**：`src/agentmatrix/agents/micro_agent.py:98-101`

**影响范围**：
此修复确保所有使用 `self.workspace_root` 的 skills 都能正常工作：
- `browser_skill.py`（新架构）- 3 处使用
- `old_skills/` 中的多个 skills（旧架构）

---

## 📊 修复总结

### 修改的文件

1. **`src/agentmatrix/agents/micro_agent.py`**
   - 修复 `_scan_all_actions()` 存储绑定方法（line 218-221）
   - 添加 `workspace_root` 继承逻辑（line 98-101）

2. **`src/agentmatrix/skills/web_search_skill.py`**
   - 将 `available_skills` 从 `execute()` 移到 `MicroAgent()` 初始化
   - 更新注释，说明新架构用法

### 关键要点

1. **`available_skills` 在初始化时设置**：
   - BaseAgent → MicroAgent
   - 传递给 `MicroAgent(available_skills=...)`

2. **`execute()` 不再接收 `available_skills`**：
   - 直接使用 `action_registry` 中的所有 actions
   - 这些 actions 来自初始化时指定的 skills

3. **依赖自动解析正常工作**：
   - Mark 配置 `web_search` → 自动获得 `file` 和 `browser`
   - 这是设计行为，不是 bug

4. **MicroAgent 从 parent 继承关键属性**：
   - `brain`、`cerebellum` - 已有
   - `workspace_root` - 🆕 新增
   - 确保 skills 可以访问配置文件路径

---

**修复完成时间**：2025-02-21
**状态**：✅ 已修复（全部 3 个问题）
