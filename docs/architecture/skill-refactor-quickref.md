# Skill 重构快速参考

> **实施时快速查阅的参考卡片**

---

## 目标效果

### System Prompt (Before)
```
- list_dir: 列出目录内容。支持单层或递归列出
- read: 读取文件内容。支持指定行范围（默认前200行）
- write: 写入文件内容。默认覆盖模式。
- web_search: 针对特定目的上网搜索...
[100+ lines...]
```

### System Prompt (After)
```
### 可用 Skills

file:
  文件操作技能：读取、写入、搜索文件和目录
  可用 actions: list_dir, read, write, search_file, bash

simple_web_search:
  网络搜索技能：搜索最新信息、访问网页
  可用 actions: web_search, visit_url

使用 help(skill="xxx", action="yyy") 查看详细参数
```

---

## 数据结构变化

### Before
```python
self.action_registry = {
    "read": <method>,
    "write": <method>
}
```

### After
```python
self.action_registry = {
    "_by_skill": {
        "file": {"read": ..., "write": ...},
        "browser": {"open_page": ...}
    },
    "_flat": {
        "read": ...,           # 第一个
        "file.read": ...,      # 完整命名
        "browser_read": ...    # 重命名的
    },
    "_aliases": {
        "read": "file.read"    # 解析映射
    }
}
```

---

## 修改文件清单

### Phase 1: 准备
- [ ] `src/agentmatrix/skills/file_skill.py` - 添加元数据
- [ ] `src/agentmatrix/skills/browser_skill.py` - 添加元数据
- [ ] `src/agentmatrix/skills/email/skill.py` - 添加元数据
- [ ] `src/agentmatrix/skills/markdown/skill.py` - 添加元数据
- [ ] `src/agentmatrix/skills/memory/skill.py` - 添加元数据
- [ ] `src/agentmatrix/skills/simple_web_search/skill.py` - 添加元数据

### Phase 2: 重构
- [ ] `src/agentmatrix/agents/micro_agent.py`
  - [ ] 修改 `__init__` - action_registry 结构
  - [ ] 修改 `_scan_all_actions` - 实现分组和重命名
  - [ ] 新增 `_infer_skill_name` - 推断 skill 名称
  - [ ] 新增 `_detect_action_conflict` - 检测冲突
  - [ ] 新增 `_rename_conflicted_action` - 重命名方法
  - [ ] 新增 `_resolve_action` - 解析 action 调用
  - [ ] 修改 `_execute_action` - 使用新解析
  - [ ] 修改 `_build_system_prompt` - 新格式
  - [ ] 新增 `_format_skills_overview` - 格式化概览
  - [ ] 新增 `help` action - 查询功能

### Phase 3: 测试
- [ ] `tests/test_skill_registry.py` - 新建
- [ ] `tests/test_action_resolution.py` - 新建
- [ ] `tests/test_conflict_detection.py` - 新建
- [ ] `tests/test_micro_agent.py` - 更新

### Phase 4: 文档
- [ ] `docs/architecture/skill-architecture.md` - 更新
- [ ] `docs/architecture/skill-refactoring-plan.md` - 标记完成

---

## 代码模板

### 添加 Skill 元数据
```python
class FileSkillMixin:
    """文件操作技能"""

    # 🆕 Skill 级别元数据
    _skill_description = "文件操作技能：读取、写入、搜索文件和目录"

    _skill_usage_guide = """
使用场景：
- 需要读取或写入文件
- 需要列出目录内容

使用建议：
- 使用 list_dir 查看目录结构
- 使用 read 读取文件（支持行范围）
"""

    _skill_dependencies = []  # 已有

    @register_action(...)
    async def read(self): pass
```

### 解析 Action 调用
```python
def _resolve_action(self, action_call: str):
    """解析 action 调用

    支持：
    - "file.read" → 完整命名
    - "read" → 简写（如果不冲突）
    """
    if '.' in action_call:
        skill_name, action_name = action_call.split('.', 1)
        return self.action_registry["_by_skill"][skill_name][action_name]
    else:
        # 从 _flat 查找
        if action_call in self.action_registry["_flat"]:
            return self.action_registry["_flat"][action_call]
        raise ValueError(f"Action '{action_call}' not found")
```

### 自动重命名
```python
def _rename_conflicted_action(self, method, new_name):
    """重命名冲突的 action

    Python 方法层面：
    - BrowserSkillMixin.read → browser_read
    - 在实例上设置新方法
    - 更新元数据
    """
    # 创建新的绑定方法
    bound_method = getattr(self, method.__name__)
    bound_method.__name__ = new_name

    # 在实例上设置
    setattr(self, new_name, bound_method)

    # 更新元数据
    bound_method._action_name = new_name
    bound_method._is_renamed = True

    return bound_method
```

---

## 测试用例模板

### 测试冲突检测
```python
def test_action_conflict_resolution():
    """测试自动冲突处理"""
    # 创建有两个 read action 的 agent
    agent = MicroAgent(
        parent=mock_parent,
        available_skills=["file", "browser"]
    )

    # 验证：两个 read 都存在
    assert "file.read" in agent.action_registry["_flat"]
    assert "browser.read" in agent.action_registry["_flat"]

    # 验证：第一个保持原名
    assert agent.action_registry["_flat"]["read"].__name__ == "read"

    # 验证：第二个被重命名
    assert hasattr(agent, "browser_read")
    assert agent.browser_read.__name__ == "browser_read"
```

### 测试 Action 解析
```python
def test_action_resolution():
    """测试 action 调用解析"""
    agent = MicroAgent(available_skills=["file"])

    # 完整命名
    method1 = agent._resolve_action("file.read")
    assert method1.__name__ == "read"

    # 简写（唯一）
    method2 = agent._resolve_action("read")
    assert method2 == method1

    # 不存在
    with pytest.raises(ValueError):
        agent._resolve_action("nonexistent")
```

---

## 回滚命令

### 紧急回滚
```bash
# 回到安全点
git reset --hard $(cat .safe_point)
git checkout main

# 删除功能分支
git branch -D feature/skill-refactor
```

### 保留代码回滚
```bash
# 创建 backup 分支
git branch backup-skill-refactor

# 回到安全点
git reset --hard $(cat .safe_point)
git checkout main
```

---

## 常见问题

### Q1: 为什么要自动重命名？
**A**: Python 不允许同一个类有同名方法。动态组合时，后加载的 Mixin 的方法会覆盖前面的。自动重命名保留了两个方法的功能。

### Q2: 重命名会影响调用吗？
**A**: 不会。用户用 `skill.action` 格式调用，内部自动解析到正确的方法。

### Q3: 旧代码会受影响吗？
**A**: 不会。简写格式（`read`）在不冲突时仍然支持。

### Q4: 如何知道一个 action 被重命名了？
**A**: 查看日志，重命名时会有 INFO 级别的日志输出。

---

## 验收清单

### Phase 1: 准备
- [ ] 所有 skill 都有 `_skill_description`
- [ ] 所有 skill 都有 `_skill_usage_guide`
- [ ] 现有测试仍然通过

### Phase 2: 重构
- [ ] action_registry 结构正确
- [ ] 冲突检测工作正常
- [ ] 自动重命名工作正常
- [ ] action 解析工作正常
- [ ] system prompt 格式正确
- [ ] help action 工作正常

### Phase 3: 测试
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 回归测试 100% 通过

### Phase 4: 文档
- [ ] 架构文档更新
- [ ] 开发者指南更新
- [ ] 变更日志更新

---

## 进度追踪

| 阶段 | 任务 | 状态 | 完成时间 |
|------|------|------|---------|
| Phase 1 | 添加 skill 元数据 | ⬜ 待开始 | - |
| Phase 2.1 | 修改 action_registry 结构 | ⬜ 待开始 | - |
| Phase 2.2 | 实现 _scan_all_actions 重构 | ⬜ 待开始 | - |
| Phase 2.3 | 实现 action 解析 | ⬜ 待开始 | - |
| Phase 2.4 | 修改 System Prompt 生成 | ⬜ 待开始 | - |
| Phase 2.5 | 实现 Help Action | ⬜ 待开始 | - |
| Phase 3 | 单元测试 + 集成测试 | ⬜ 待开始 | - |
| Phase 4 | 文档更新 | ⬜ 待开始 | - |
| Phase 5 | 发布 | ⬜ 待开始 | - |

---

**最后更新**: 2026-03-10
