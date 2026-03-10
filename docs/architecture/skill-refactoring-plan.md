# Skill 提示词重构方案

> **版本**: v1.0
> **日期**: 2026-03-10
> **状态**: 待审核

---

## 一、重构目标

### 1.1 核心改进

**当前问题**：
- ❌ System prompt 塞入所有 action 的详细参数，信息冗长
- ❌ Actions 平铺展示，没有按 skill 分组
- ❌ 缺少 skill 级别的使用指南
- ❌ 不支持命名空间调用（`skill.action`）

**改进目标**：
- ✅ System prompt 只显示 skill 概览 + action 名字列表
- ✅ Actions 按 skill 分组展示
- ✅ 增加 skill 级别的描述和使用指南
- ✅ 支持 `skill.action` 调用方式
- ✅ 新增 help action 查询详细参数

### 1.2 预期效果

**System Prompt 变化**：
```diff
- list_dir: 列出目录内容。支持单层或递归列出
- read: 读取文件内容。支持指定行范围（默认前200行）
- write: 写入文件内容。默认覆盖模式。
- web_search: 针对特定目的上网搜索，提供明确的搜索目的...

+ ### 可用 Skills
+
+ file:
+   文件操作技能：读取、写入、搜索文件和目录
+   可用 actions: list_dir, read, write, search, bash
+
+ simple_web_search:
+   网络搜索技能：搜索最新信息、访问网页、提取内容
+   可用 actions: web_search, visit_url
+
+ 使用 help(skill="xxx", action="yyy") 查看详细参数
```

**调用方式变化**：
```python
# 方式1：命名空间（推荐）
await file.read("test.txt")
await simple_web_search.web_search(purpose="查找AI资讯")

# 方式2：简写（如果不冲突）
await read("test.txt")
```

---

## 二、技术方案

### 2.1 数据结构变化

#### action_registry 结构

**当前**：
```python
self.action_registry = {
    "read": <method>,
    "write": <method>
}
```

**改为**：
```python
self.action_registry = {
    "_by_skill": {
        "file": {
            "read": <method>,
            "write": <method>
        },
        "browser": {
            "open_page": <method>
        }
    },
    "_flat": {
        "read": <method>,
        "file.read": <method>,
        "write": <method>
    },
    "_aliases": {
        # 自动重命名的映射
        "read": "file.read"  # 如果只有一个 read
    }
}
```

#### Skill 元数据

**Python Skill 新增**：
```python
class FileSkillMixin:
    """文件操作技能"""

    # 🆕 Skill 级别元数据
    _skill_description = "文件操作技能：读取、写入、搜索文件和目录"
    _skill_usage_guide = """
使用场景：
- 需要读取或写入文件
- 需要列出目录内容
- 需要在文件中搜索内容

使用建议：
- 使用 list_dir 查看目录结构
- 使用 read 读取文件（支持行范围）
- 使用 write 写入文件（默认覆盖模式）
"""

    _skill_dependencies = []  # 已有

    @register_action(...)
    async def read(self): pass
```

**MD Skill 已有**：
- `MDSkillMetadata` 已包含 `description`, `brief_summary` 等

### 2.2 自动冲突检测与重命名

#### 重命名规则

```python
# 场景：两个 skill 都有 read
class FileSkillMixin:
    async def read(self): pass  # 优先级高（MRO 顺序）

class BrowserSkillMixin:
    async def read(self): pass  # 冲突！自动重命名

# 扫描结果：
# - FileSkillMixin.read → 保持 read
# - BrowserSkillMixin.read → 重命名为 browser_read
```

#### 实现位置

**文件**：`src/agentmatrix/agents/micro_agent.py`

**修改**：`_scan_all_actions()` 方法

**新增**：`_detect_action_conflict()`, `_rename_conflicted_action()`

### 2.3 System Prompt 生成

#### 新格式

```
### 可用 Skills

file:
  文件操作技能：读取、写入、搜索文件和目录
  可用 actions: list_dir, read, write, search_file, bash

simple_web_search:
  网络搜索技能：搜索最新信息、访问网页、提取内容
  依赖: browser
  可用 actions: web_search, visit_url

markdown:
  Markdown 文档编辑技能
  可用 actions: get_toc, search_keywords, modify_node, save_markdown

使用 help(skill="skill_name", action="action_name") 查看详细参数
```

#### 实现位置

**修改**：`_build_system_prompt()`, `_format_actions_list()`

**新增**：`_format_skills_overview()`, `_format_skill_actions()`

### 2.4 Action 调用解析

#### 支持两种格式

```python
# 格式1：skill.action
await file.read("test.txt")

# 格式2：action (如果唯一)
await read("test.txt")

# 格式3：重命名的 action
await browser_read("https://example.com")
```

#### 实现位置

**修改**：`_execute_action()`, `_parse_actions_from_thought()`

**新增**：`_resolve_action_call()`

### 2.5 Help Action

#### 功能

```python
# 查看所有 skills
await help()

# 查看某个 skill 的详细说明
await help(skill="file")

# 查看某个 action 的参数
await help(skill="file", action="read")
```

#### 返回格式

```
=== File Skill ===
文件操作技能：读取、写入、搜索文件和目录

使用场景：
- 需要读取或写入文件
- 需要列出目录内容

可用 actions:
- read: 读取文件内容
- write: 写入文件内容
- ...

=== read Action 参数 ===
file_path: 文件路径（相对于 /work_files）
start_line: 起始行号（从1开始，默认1）
end_line: 结束行号（默认200）
```

#### 实现位置

**新增**：`help()` action in `MicroAgent`

---

## 三、向后兼容性

### 3.1 兼容策略

#### 渐进式迁移

**阶段1**：同时支持新旧格式
- 新格式：`file.read("test.txt")`
- 旧格式：`read("test.txt")`（自动解析）

**阶段2**：警告旧格式
- 如果检测到旧格式调用，输出 warning
- 提示使用新格式

**阶段3**：完全迁移
- 移除旧格式支持

#### Action Registry 访问

**旧代码**：
```python
if action_name in self.action_registry:
    method = self.action_registry[action_name]
```

**新代码**：
```python
method = self._resolve_action(action_name)
```

**兼容层**：
```python
def __getitem__(self, key):
    """保持字典式访问兼容"""
    return self._resolve_action(key)
```

### 3.2 测试兼容性

#### 测试矩阵

| 测试场景 | 新格式 | 旧格式 | 预期结果 |
|---------|-------|-------|---------|
| 单个 skill，无冲突 | ✅ | ✅ | 两者都工作 |
| 多个 skill，有冲突 | ✅ | ❌ | 新格式工作，旧格式报错 |
| MD skill | ✅ | N/A | 新格式工作 |

---

## 四、测试策略

### 4.1 单元测试

#### 测试文件

**新增**：
- `tests/test_skill_registry.py` - 测试分组结构
- `tests/test_action_resolution.py` - 测试调用解析
- `tests/test_conflict_detection.py` - 测试冲突检测

**修改**：
- `tests/test_micro_agent.py` - 更新现有测试

#### 测试用例

```python
# test_conflict_detection.py
def test_single_skill_no_conflict():
    """单个 skill，无冲突"""
    agent = MicroAgent(available_skills=["file"])
    assert "read" in agent.action_registry["_flat"]
    assert agent.action_registry["_flat"]["read"].__name__ == "read"

def test_multiple_skills_with_conflict():
    """多个 skill，有同名 action"""
    agent = MicroAgent(available_skills=["file", "browser"])
    # 假设都有 read
    assert "file.read" in agent.action_registry["_flat"]
    assert "browser.read" in agent.action_registry["_flat"]
    # 第一个保持原名
    assert "read" in agent.action_registry["_flat"]

def test_action_resolution():
    """测试 action 解析"""
    agent = MicroAgent(available_skills=["file", "browser"])

    # 完整命名
    method1 = agent._resolve_action("file.read")
    assert method1.__name__ == "read"

    # 简写（如果唯一）
    method2 = agent._resolve_action("read")
    assert method2.__name__ == "read"
```

### 4.2 集成测试

#### 测试场景

1. **创建带 skills 的 MicroAgent**
   - 验证 action_registry 结构正确
   - 验证 system prompt 格式正确

2. **执行 action（新格式）**
   - `await file.read("test.txt")`
   - 验证正确调用

3. **执行 action（旧格式）**
   - `await read("test.txt")`
   - 验证向后兼容

4. **冲突场景**
   - 两个 skill 都有 `read`
   - 验证自动重命名
   - 验证 `skill.action` 调用

5. **Help action**
   - 验证 help 返回正确信息

### 4.3 现有功能回归测试

#### 测试清单

- [ ] File Skill 所有功能
- [ ] Browser Skill 所有功能
- [ ] Markdown Skill 所有功能
- [ ] Email Skill 所有功能
- [ ] Web Search Skill 所有功能
- [ ] Memory Skill 所有功能

---

## 五、回滚方案

### 5.1 版本管理

#### Git 分支策略

```bash
# 1. 创建功能分支
git checkout -b feature/skill-refactor

# 2. 创建安全点（commit）
git commit -am " refactor: start skill refactoring - safe point"

# 记录这个 commit hash
SAFE_POINT_HASH=$(git rev-parse HEAD)

# 3. 开始重构
# ... 做改动 ...

# 4. 如果有问题，立即回滚
git reset --hard $SAFE_POINT_HASH
```

#### Tag 策略

```bash
# 创建 pre-refactor tag
git tag pre-skill-refactor -m "Before skill refactoring"

# 重构完成后
git tag post-skill-refactor -m "After skill refactoring"
```

### 5.2 回滚检查清单

- [ ] 确认所有测试通过
- [ ] 确认现有功能正常
- [ ] 确认 system prompt 格式正确
- [ ] 确认 action 调用正常
- [ ] 确认 help action 工作
- [ ] 确认日志输出正常
- [ ] 确认性能无退化

---

## 六、实施步骤

### Phase 1: 准备阶段（1-2天）

#### 步骤 1.1: 创建安全点

```bash
# 确认当前状态
git status
git log --oneline -5

# 确认所有测试通过
pytest tests/ -v

# 创建安全点
git checkout -b feature/skill-refactor
git commit -am "refactor: safe point before skill refactoring" --allow-empty

# 记录 commit hash
SAFE_POINT=$(git rev-parse HEAD)
echo $SAFE_POINT > .safe_point
```

#### 步骤 1.2: 更新现有 Skill

**任务**：为所有 Python Skills 添加元数据

**文件**：
- `src/agentmatrix/skills/file_skill.py`
- `src/agentmatrix/skills/browser_skill.py`
- `src/agentmatrix/skills/email/skill.py`
- `src/agentmatrix/skills/markdown/skill.py`
- `src/agentmatrix/skills/memory/skill.py`
- `src/agentmatrix/skills/simple_web_search/skill.py`

**改动**：
```python
class FileSkillMixin:
    """文件操作技能"""

    # 🆕 添加
    _skill_description = "文件操作技能：读取、写入、搜索文件和目录"
    _skill_usage_guide = """
使用场景：
- 需要读取或写入文件
- 需要列出目录内容
- 需要在文件中搜索内容

使用建议：
- 使用 list_dir 查看目录结构
- 使用 read 读取文件（支持行范围）
- 使用 write 写入文件（默认覆盖模式）
"""
```

**验收**：
- [ ] 所有 skill 都有 `_skill_description`
- [ ] 所有 skill 都有 `_skill_usage_guide`
- [ ] 现有测试仍然通过

### Phase 2: 核心重构（3-5天）

#### 步骤 2.1: 修改 action_registry 结构

**文件**：`src/agentmatrix/agents/micro_agent.py`

**改动**：
```python
# __init__
self.action_registry = {
    "_by_skill": {},
    "_flat": {},
    "_aliases": {}
}
```

**验收**：
- [ ] 代码可以编译
- [ ] 现有测试失败（预期，因为结构变了）

#### 步骤 2.2: 实现 _scan_all_actions 重构

**文件**：`src/agentmatrix/agents/micro_agent.py`

**新增方法**：
- `_infer_skill_name(class_name)` - 推断 skill 名称
- `_detect_action_conflict(action_name)` - 检测冲突
- `_rename_conflicted_action(method, new_name)` - 重命名方法
- `_register_action_grouped(skill_name, action_name, method)` - 分组注册

**修改方法**：
- `_scan_all_actions()` - 实现新的扫描逻辑

**验收**：
- [ ] 单个 skill 无冲突场景测试通过
- [ ] 多个 skill 有冲突场景测试通过
- [ ] action_registry 结构正确

#### 步骤 2.3: 实现 action 解析

**新增方法**：
- `_resolve_action(action_call)` - 解析 action 调用
- `_resolve_action_name(action_call)` - 解析 action 名称

**修改方法**：
- `_execute_action()` - 使用新的解析逻辑
- `_parse_actions_from_thought()` - 支持新格式

**验收**：
- [ ] `file.read` 格式调用成功
- [ ] `read` 简写格式调用成功（不冲突时）
- [ ] 冲突时简写报错，提示使用完整格式

#### 步骤 2.4: 修改 System Prompt 生成

**新增方法**：
- `_format_skills_overview()` - 格式化 skills 概览
- `_format_skill_actions(skill_name)` - 格式化 skill 的 actions
- `_get_skill_metadata(skill_name)` - 获取 skill 元数据

**修改方法**：
- `_build_system_prompt()` - 使用新的格式
- `_format_actions_list()` - 改为按 skill 分组

**验收**：
- [ ] System prompt 格式符合预期
- [ ] Skills 按分组展示
- [ ] 只显示 action 名字列表

#### 步骤 2.5: 实现 Help Action

**新增方法**：
- `help(skill=None, action=None)` - help action

**验收**：
- [ ] `help()` 返回所有 skills 列表
- [ ] `help(skill="file")` 返回 skill 详细说明
- [ ] `help(skill="file", action="read")` 返回 action 参数

### Phase 3: 测试阶段（2-3天）

#### 步骤 3.1: 单元测试

**新增测试文件**：
- `tests/test_skill_registry.py`
- `tests/test_action_resolution.py`
- `tests/test_conflict_detection.py`

**验收**：
- [ ] 所有单元测试通过
- [ ] 代码覆盖率 > 80%

#### 步骤 3.2: 集成测试

**修改测试文件**：
- `tests/test_micro_agent.py`
- `tests/integration/test_skills.py`

**验收**：
- [ ] 所有集成测试通过
- [ ] 现有功能回归测试通过

#### 步骤 3.3: 手动测试

**测试场景**：
1. 创建带 skills 的 Agent
2. 执行各种 action 调用
3. 验证 system prompt 格式
4. 验证 help action

**验收**：
- [ ] 所有场景测试通过
- [ ] 无明显 bug

### Phase 4: 文档更新（1天）

#### 步骤 4.1: 更新架构文档

**文件**：
- `docs/architecture/skill-architecture.md`

**改动**：
- 更新 action_registry 结构说明
- 更新调用方式说明
- 添加冲突检测说明

#### 步骤 4.2: 更新开发者指南

**文件**：
- `docs/agent-developer-guide.md`

**改动**：
- 更新 skill 开发指南
- 添加 `_skill_description` 说明
- 更新调用示例

### Phase 5: 发布准备（1天）

#### 步骤 5.1: 代码审查

**检查清单**：
- [ ] 代码符合规范
- [ ] 注释完整
- [ ] 文档完整

#### 步骤 5.2: 性能测试

**测试指标**：
- [ ] Action 调用延迟无明显增加
- [ ] Memory footprint 无明显增加
- [ ] System prompt 长度合理

#### 步骤 5.3: 发布

```bash
# 合并到主分支
git checkout main
git merge feature/skill-refactor

# 创建 tag
git tag v2.0.0 -m "Skill refactoring: namespace and grouped actions"
```

---

## 七、风险与缓解

### 7.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Python 方法重命名失败 | 中 | 高 | 充分测试，准备回滚方案 |
| Action 解析错误 | 中 | 高 | 单元测试覆盖各种场景 |
| 性能退化 | 低 | 中 | 性能测试，优化热点 |
| 向后兼容性破坏 | 中 | 高 | 兼容层，渐进式迁移 |

### 7.2 项目风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 工期延误 | 中 | 中 | 分阶段实施，每个阶段有验收标准 |
| 测试覆盖不足 | 中 | 高 | 强制测试覆盖率 > 80% |
| 文档不完整 | 低 | 低 | 文档作为验收标准之一 |

---

## 八、成功标准

### 8.1 功能标准

- [ ] System prompt 按 skill 分组展示
- [ ] 只显示 action 名字列表，不显示详细参数
- [ ] 支持 `skill.action` 调用格式
- [ ] 自动检测并重命名冲突的 action
- [ ] Help action 正常工作
- [ ] 向后兼容旧格式（不冲突时）

### 8.2 质量标准

- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 代码覆盖率 > 80%
- [ ] 现有功能回归测试 100% 通过
- [ ] 性能无明显退化

### 8.3 文档标准

- [ ] 架构文档更新
- [ ] 开发者指南更新
- [ ] API 文档更新
- [ ] 变更日志更新

---

## 九、时间估算

| 阶段 | 工作量 | 里程碑 |
|------|-------|--------|
| Phase 1: 准备 | 1-2天 | 所有 skill 添加元数据 |
| Phase 2: 重构 | 3-5天 | 核心功能实现 |
| Phase 3: 测试 | 2-3天 | 所有测试通过 |
| Phase 4: 文档 | 1天 | 文档更新完成 |
| Phase 5: 发布 | 1天 | 发布完成 |
| **总计** | **8-12天** | **功能上线** |

---

## 十、决策记录

### 10.1 为什么选择自动重命名？

**选项 A**: 禁止重名
- ✅ 简单
- ❌ 限制开发者

**选项 B**: 手动重命名
- ✅ 灵活
- ❌ 增加开发负担

**选项 C**: 自动重命名 ✅
- ✅ 不限制开发者
- ✅ 不增加负担
- ✅ 向后兼容

**决策**: 选择选项 C

### 10.2 为什么使用嵌套的 action_registry？

**选项 A**: 扁平结构 + 前缀
```python
{"file_read": ..., "browser_read": ...}
```
- ❌ 失去 skill 分组信息

**选项 B**: 嵌套结构 ✅
```python
{"file": {"read": ...}, "browser": {"read": ...}}
```
- ✅ 保留分组信息
- ✅ 支持快速查找

**决策**: 选择选项 B

---

## 十一、参考资料

### 11.1 相关文档

- [Skill Architecture](./skill-architecture.md)
- [Agent Developer Guide](../user-guide/agent-developer-guide.md)
- [Micro Agent Design](./agent-and-micro-agent-design.md)

### 11.2 相关代码

- `src/agentmatrix/agents/micro_agent.py` - MicroAgent 实现
- `src/agentmatrix/skills/registry.py` - Skill Registry
- `src/agentmatrix/core/action.py` - Action 装饰器

---

## 十二、附录

### 12.1 示例：完整的 System Prompt

```
你是一个运行在 AgentMatrix 架构中的智能体。

### 可用 Skills

file:
  文件操作技能：读取、写入、搜索文件和目录
  使用场景：需要读写文件、列出目录、搜索内容
  可用 actions: list_dir, read, write, search_file, bash

simple_web_search:
  网络搜索技能：搜索最新信息、访问网页、提取内容
  依赖: browser
  使用场景：需要查找最新信息、访问网页
  可用 actions: web_search, visit_url

markdown:
  Markdown 文档编辑技能：编辑、总结、搜索 Markdown 文档
  使用场景：需要编辑 Markdown 文档、总结内容
  可用 actions: get_toc, search_keywords, modify_node, save_markdown

使用 help(skill="xxx", action="yyy") 查看详细参数信息

### 响应协议

[THOUGHTS]
你的思考...

[ACTIONS]
1. file.read(file_path="test.txt")
2. markdown.get_toc(file_path="doc.md")
```

### 12.2 示例：Help Action 输出

```python
await help(skill="file", action="read")
```

输出：
```
=== File Skill ===
文件操作技能：读取、写入、搜索文件和目录

使用场景：
- 需要读取或写入文件
- 需要列出目录内容
- 需要在文件中搜索内容

使用建议：
- 使用 list_dir 查看目录结构
- 使用 read 读取文件（支持行范围）
- 使用 write 写入文件（默认覆盖模式）

可用 actions:
- list_dir: 列出目录内容
- read: 读取文件内容
- write: 写入文件内容
- search_file: 搜索文件或内容
- bash: 执行 bash 命令

=== read Action 参数 ===
file_path: 文件路径（相对于 /work_files）
start_line: 起始行号（从1开始，默认1）
end_line: 结束行号（默认200）

示例：
  await file.read(file_path="test.txt")
  await file.read(file_path="test.txt", start_line=1, end_line=100)
```

---

**文档版本**: v1.0
**最后更新**: 2026-03-10
**审核状态**: 待审核
