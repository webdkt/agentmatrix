# Skill 架构清理总结

## ✅ 完成时间
2025-02-21

## 🎯 清理目标

**旧架构**（已废弃）：
- MicroAgent 需要手动指定 `available_actions` 列表
- BaseAgent 使用 `top_level_actions` 配置限制可用 actions
- 需要在配置中列举具体的 action 名称（如 `"read"`, `"write"`, `"use_browser"`）

**新架构**（已实现）：
- MicroAgent 自动使用所有来自 skills 的 actions
- BaseAgent 使用 `skills` 配置指定 skill 名称
- 系统自动从 skills 中提取所有 `@register_action` 方法

## 📝 修改的文件

### 1. `src/agentmatrix/agents/micro_agent.py`

#### 删除的内容
- `execute()` 方法的 `available_actions` 参数（第253行）
- `self.available_actions = available_actions` 赋值（第309行）
- `"all_finished" not in available_actions` 检查（第345-346行）
- `_format_actions_list()` 中对 `self.available_actions` 的遍历（第456行）
- `_extract_tool_calls()` 中对 `self.available_actions` 的验证（第742行）
- `_parse_and_validate_actions()` 中对 `self.available_actions` 的验证（第807-816行）

#### 新增的内容
- `_format_actions_list()` 直接遍历 `self.action_registry`（第457行）
- 日志改为使用 `list(self.action_registry.keys())`（第367行）

#### 关键改动
```python
# 旧方式
async def execute(
    self,
    available_actions: List[str],  # ❌ 已删除
    ...
):
    self.available_actions = available_actions  # ❌ 已删除

# 新方式
async def execute(
    self,
    # available_actions 参数已删除
    ...
):
    # 自动使用 action_registry 中的所有 actions
```

### 2. `src/agentmatrix/agents/base.py`

#### 删除的内容
- `DEFAULT_TOP_LEVEL_ACTIONS` 常量（第24行）
- `self.top_level_actions = profile.get("top_level_actions", None)`（第45行）
- `_get_top_level_actions()` 方法（第104-116行）

#### 新增的内容
- `self.skills = profile.get("skills", [])`（第41行）

#### 关键改动
```python
# 旧方式
self.top_level_actions = profile.get("top_level_actions", None)  # ❌ 已删除
available_actions = self._get_top_level_actions()  # ❌ 已删除

# 新方式
self.skills = profile.get("skills", [])  # ✅ 新增
available_skills = self.profile.get("skills", [])  # ✅ 新增
```

### 3. `src/agentmatrix/profiles/deep_researcher.yml`

#### 删除的内容
```yaml
top_level_actions:  # ❌ 已删除
  - "use_browser"
  - "update_whiteboard"
  - "read_whiteboard"
  - "read"
  - "write"
  - "search_file"
  - "shell_cmd"
  - "replace_string_in_file"
  - "send_email"
  - "rest_n_wait"
  - "take_a_break"
  - "get_current_datetime"
```

#### 新增的内容
```yaml
# Skills 配置（🆕 新架构）
skills:
  - browser       # use_browser
  - file          # read, write, search_file, replace_string_in_file
  - web_search    # web_search（如果需要网络搜索功能）
```

### 4. `src/agentmatrix/profiles/researcher.yml`

#### 删除的内容
```yaml
top_level_actions:  # ❌ 已删除
  # TODO: deep_research 还不可用
#   - deep_research
```

#### 保留的内容
```yaml
# Skills 配置（🆕 新架构）
skills:
  - file  # 文件操作技能
```

### 5. `src/agentmatrix/agents/deep_researcher.py`

#### 删除的内容
- `available_actions = self._get_top_level_actions()`（第74行）
- `available_actions=available_actions,` 参数（第137行）

## 🔄 架构变化

### 数据流向对比

#### 旧架构
```
Profile (top_level_actions)
    ↓
BaseAgent._get_top_level_actions()
    ↓
available_actions (List[str])
    ↓
MicroAgent.execute(available_actions=...)
    ↓
_format_actions_list() 遍历 available_actions
```

#### 新架构
```
Profile (skills)
    ↓
BaseAgent.skills
    ↓
MicroAgent(available_skills=...)
    ↓
_scan_all_actions() 扫描所有 @register_action
    ↓
action_registry (Dict[name, method])
    ↓
_format_actions_list() 遍历 action_registry
```

### System Prompt 生成

#### 旧方式
```python
# 需要手动指定可用 actions
available_actions = ["read", "write", "use_browser"]
format_actions_list(available_actions)
```

#### 新方式
```python
# 自动从 action_registry 提取
for action_name, method in self.action_registry.items():
    desc = getattr(method, "_action_desc", "No description")
    lines.append(f"- {action_name}: {desc}")
```

## ✅ 验证结果

- ✅ 所有 Python 文件语法检查通过
- ✅ MicroAgent 不再需要 `available_actions` 参数
- ✅ BaseAgent 不再使用 `top_level_actions`
- ✅ Profile 文件使用 `skills` 配置
- ✅ DeepResearcher 已更新

## 🎁 好处

1. **简化配置**：不再需要列举具体的 action 名称
2. **自动发现**：自动从 skills 中提取所有 actions
3. **类型安全**：通过 `_scan_all_actions()` 确保 actions 存在
4. **易于扩展**：添加新的 action 只需在 skill 中添加 `@register_action` 方法
5. **统一接口**：所有 agent 都使用 `skills` 配置

## 📚 示例

### 配置示例

```yaml
# profile.yml
skills:
  - browser    # 提供 use_browser action
  - file       # 提供 read, write, search_file, replace_string_in_file actions
  - web_search # 提供 web_search action
```

### 代码示例

```python
# BaseAgent 初始化
agent = BaseAgent(profile)
# agent.skills = ["browser", "file"]

# MicroAgent 初始化
micro_agent = MicroAgent(
    parent=agent,
    available_skills=agent.skills
)
# micro_agent.action_registry 自动包含所有来自 browser 和 file 的 actions

# MicroAgent 执行
result = await micro_agent.execute(
    run_label="test",
    persona="...",
    task="..."
    # 不再需要 available_actions 参数
)
```

## 🔧 迁移指南

如果你有自定义的 agent profile：

1. **找到 `top_level_actions` 配置**
2. **根据 action 名称推断它们来自哪些 skills**：
   - `use_browser` → `browser` skill
   - `read`, `write`, `search_file` → `file` skill
   - `web_search` → `web_search` skill
3. **创建 `skills` 配置**
4. **删除 `top_level_actions` 配置**

### 迁移示例

**旧配置**：
```yaml
top_level_actions:
  - "read"
  - "write"
  - "use_browser"
```

**新配置**：
```yaml
skills:
  - file
  - browser
```

---

**清理完成！架构升级成功！** 🎉
