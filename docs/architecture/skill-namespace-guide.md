# Skill 命名空间与 Help 系统快速参考

> **最后更新**: 2026-03-10
> **相关文档**: [skill-architecture.md](./skill-architecture.md)

---

## 📚 目录

1. [快速开始](#快速开始)
2. [命名空间调用](#命名空间调用)
3. [Help 系统](#help-系统)
4. [冲突处理](#冲突处理)
5. [开发 Skill](#开发-skill)
6. [常见问题](#常见问题)

---

## 快速开始

### 旧代码仍然可用

```python
# ✅ 这些调用方式仍然支持
await agent.list_dir()
await agent.read(file_path="test.txt")
await agent.write(file_path="output.txt", content="Hello")
```

### 推荐使用新格式

```python
# ✅ 更明确（推荐）
await agent._execute_action("file.list_dir", path="/tmp")
await agent._execute_action("file.read", file_path="test.txt")
await agent._execute_action("markdown.get_toc", file_path="test.md")
```

---

## 命名空间调用

### 两种格式对比

| 格式 | 示例 | 优势 | 劣势 |
|------|------|------|------|
| **简写** | `list_dir()` | 简洁，向后兼容 | 可能有歧义 |
| **完整** | `file.list_dir()` | 明确，无冲突 | 较长 |

### 完整命名语法

```python
await agent._execute_action(
    "skill.action",  # 格式：skill名称.action名称
    param1=value1,   # action 参数
    param2=value2
)
```

### 示例

```python
# File Skill
await agent._execute_action("file.list_dir", path="/tmp")
await agent._execute_action("file.read", file_path="test.txt")
await agent._execute_action("file.write", file_path="out.txt", content="Hello")

# Markdown Skill
await agent._execute_action("markdown.get_toc", file_path="doc.md", depth=2)
await agent._execute_action("markdown.search_keywords", file_path="doc.md", query="TODO")

# Email Skill
await agent._execute_action("email.send_email", to="User", body="Hello")

# Memory Skill
await agent._execute_action("memory.recall", entity_name="张三", question="他的职位是什么？")
await agent._execute_action("memory.update_memory", focus_hint="重点关注决策")
```

---

## Help 系统

### 三种查询模式

#### 模式 1: 列出所有 Skills

```python
result = await agent.help()
print(result)
```

**输出示例**:
```
=== 可用的 Skills ===

**file**
  文件操作技能：读取、写入、搜索文件和目录，执行 shell 命令

**email**
  邮件发送技能：向其他 Agent 发送邮件，支持附件传输

**markdown**
  Markdown 文档编辑技能：编辑、总结、搜索 Markdown 文档内容

💡 提示：使用 help(skill="xxx") 查看详细参数说明
```

#### 模式 2: 查看 Skill 详情

```python
result = await agent.help(skill="file")
print(result)
```

**输出示例**:
```
=== File Skill ===

文件操作技能：读取、写入、搜索文件和目录，执行 shell 命令

使用场景：
- 需要读取或写入文件
- 需要列出目录内容
- 需要在文件中搜索内容

使用建议：
- 使用 list_dir 查看目录结构
- 使用 read 读取文件内容
- 使用 write 写入文件

可用 actions:

- **file_list_dir**: 列出目录内容
  参数:
    - path: 目录路径

- **file_read**: 读取文件内容
  参数:
    - file_path: 文件路径
    - start_line: 起始行（可选，默认 0）
    - end_line: 结束行（可选，默认 None）

- **file_write**: 写入文件内容
  参数:
    - file_path: 文件路径
    - content: 文件内容
```

#### 模式 3: 查看 Action 详情

```python
result = await agent.help(skill="file", action="read")
print(result)
```

**输出示例**:
```
=== file.read Action ===

读取文件内容

参数：
- file_path: 文件路径
- start_line: 起始行（可选，默认 0）
- end_line: 结束行（可选，默认 None）

使用场景：
需要查看文件内容时

返回值：
文件内容（字符串）
```

### 在代码中使用 Help

```python
# 场景 1: 开发时查看可用功能
print(await agent.help())

# 场景 2: 运行时动态查询
user_input = "我想用 file skill"
skill_name = user_input.split()[2]  # "file"
print(await agent.help(skill=skill_name))

# 场景 3: 错误处理时提供帮助
try:
    await agent._execute_action("unknown.action")
except ValueError as e:
    print(f"错误: {e}")
    print("\n可用的 skills:")
    print(await agent.help())
```

---

## 冲突处理

### 什么情况会冲突？

```python
# 两个 skills 都有 read 方法
file_skill:     async def read(...)
markdown_skill: async def read(...)

# 系统会自动重命名
file.read     → file_read
markdown.read → markdown_read
```

### 检测冲突

```python
# 查看重命名的 actions
for name, meta in agent.action_registry["_metadata"].items():
    if meta["is_renamed"]:
        print(f"⚠️  {meta['original_name']} → {name}")
        print(f"   来自 skill: {meta['skill_name']}")
```

### 解决冲突的三种方法

#### 方法 1: 使用完整命名（推荐）

```python
await agent._execute_action("file.read", file_path="test.txt")
await agent._execute_action("markdown.read", file_path="doc.md")
```

#### 方法 2: 使用重命名后的方法

```python
await agent.file_read(file_path="test.txt")
await agent.markdown_read(file_path="doc.md")
```

#### 方法 3: 避免 conflict（开发时）

```python
# 开发 skill 时使用更具体的名称
# ❌ async def read(...)
# ✅ async def read_file(...)
# ✅ async def read_markdown(...)
```

---

## 开发 Skill

### 最小模板

```python
# src/agentmatrix/skills/my_skill/skill.py

from ...core.action import register_action

class My_skillSkillMixin:
    """我的技能"""

    # 🆕 添加元数据
    _skill_description = "我的技能描述"

    _skill_usage_guide = """
使用场景：
- 场景 1
- 场景 2

使用建议：
- 建议 1
- 建议 2

注意事项：
- 注意 1
- 注意 2
"""

    @register_action(
        description="执行某个操作",
        param_infos={
            "param1": "参数1说明",
            "param2": "参数2说明（可选）"
        }
    )
    async def my_action(self, param1: str, param2: str = None) -> str:
        """
        执行某个操作

        Args:
            param1: 必需参数
            param2: 可选参数

        Returns:
            操作结果
        """
        # 实现代码
        return f"完成: {param1}"
```

### 命名规范

| 组件 | 规范 | 示例 |
|------|------|------|
| **目录名** | 小写，下划线 | `my_skill/` |
| **文件名** | `skill.py` | `skill.py` |
| **类名** | `{Name}SkillMixin` | `My_skillSkillMixin` |
| **skill 名称** | 小写，下划线 | `"my_skill"` |
| **action 名称** | 动词开头，小写 | `my_action`, `read_file` |

### 检查清单

开发新 skill 时，确保：

- [ ] 目录结构正确: `my_skill/skill.py`
- [ ] 类名符合规范: `My_skillSkillMixin`
- [ ] 添加 `_skill_description`
- [ ] 添加 `_skill_usage_guide`
- [ ] 所有 actions 有 `@register_action` 装饰器
- [ ] action 名称明确（避免冲突）
- [ ] 测试 `help()` 功能
- [ ] 测试命名空间调用

---

## 常见问题

### Q1: 为什么要用命名空间？

**A**:
- ✅ 避免命名冲突
- ✅ 代码更清晰
- ✅ 更好的 IDE 支持

### Q2: 旧代码需要修改吗？

**A**: 不需要。简写格式仍然支持：

```python
# ✅ 仍然可用
await agent.list_dir()
```

但建议逐步迁移到新格式：

```python
# ✅ 推荐（更明确）
await agent._execute_action("file.list_dir", path="/tmp")
```

### Q3: 如何查看有哪些 actions？

**A**: 使用 help 系统：

```python
# 查看所有 skills
await agent.help()

# 查看特定 skill
await agent.help(skill="file")

# 查看特定 action
await agent.help(skill="file", action="read")
```

### Q4: 如何调试 action 调用？

**A**:

```python
# 1. 检查 action 是否存在
try:
    method = agent._resolve_action("file.read")
    print("✅ Action 存在")
except ValueError as e:
    print(f"❌ Action 不存在: {e}")

# 2. 查看参数
import inspect
sig = inspect.signature(method)
print(f"参数: {sig}")

# 3. 查看 metadata
meta = agent.action_registry["_metadata"]["file_read"]
print(f"原始名称: {meta['original_name']}")
print(f"来自 skill: {meta['skill_name']}")
```

### Q5: Help 输出太长怎么办？

**A**: Help 系统支持分页查询：

```python
# 先看有哪些 skills
overview = await agent.help()

# 再看感兴趣的 skill
detail = await agent.help(skill="file")

# 最后看具体的 action
action_detail = await agent.help(skill="file", action="read")
```

### Q6: 如何测试我的 skill？

**A**:

```python
# 1. 创建测试 agent
from agentmatrix.agents.micro_agent import MicroAgent

agent = MicroAgent(
    parent=parent,
    available_skills=["my_skill"]
)

# 2. 测试 help
print(await agent.help(skill="my_skill"))

# 3. 测试 action
result = await agent._execute_action(
    "my_skill.my_action",
    param1="test"
)
print(result)

# 4. 检查冲突
for name, meta in agent.action_registry["_metadata"].items():
    if meta["is_renamed"]:
        print(f"冲突: {meta['original_name']} → {name}")
```

---

## 参考资源

### 文档

- [Skill 架构文档](./skill-architecture.md) - 完整的架构说明
- [Skill 重构计划](./skill-refactoring-plan.md) - 重构的技术细节
- [开发者指南](../agent-developer-guide-cn.md) - Agent 开发指南

### 代码位置

| 功能 | 文件 | 行号 |
|------|------|------|
| **Action Registry** | `src/agentmatrix/agents/micro_agent.py` | 96-108 |
| **Action 解析** | `src/agentmatrix/agents/micro_agent.py` | 333-390 |
| **冲突检测** | `src/agentmatrix/agents/micro_agent.py` | 225-350 |
| **Help Action** | `src/agentmatrix/agents/micro_agent.py` | 500-700 |
| **System Prompt** | `src/agentmatrix/agents/micro_agent.py` | 950-1100 |

### 测试

```bash
# 运行测试套件
python tests/test_skill_refactoring.py

# 测试输出
✅ PASS action_registry 结构
✅ PASS action 解析
✅ PASS System Prompt 格式
✅ PASS Help Action
```

---

## 快速命令参考

```python
# === Help 系统 ===
await agent.help()                                    # 列出所有 skills
await agent.help(skill="file")                        # 查看 skill 详情
await agent.help(skill="file", action="read")         # 查看 action 详情

# === 命名空间调用 ===
await agent._execute_action("file.list_dir", path="/tmp")
await agent._execute_action("markdown.get_toc", file_path="doc.md")

# === 调试 ===
agent.action_registry["_by_skill"].keys()             # 所有 skills
agent.action_registry["_by_skill"]["file"].keys()     # file skill 的 actions
agent._resolve_action("file.read")                    # 解析 action

# === 检查冲突 ===
for name, meta in agent.action_registry["_metadata"].items():
    if meta["is_renamed"]:
        print(f"{meta['original_name']} → {name}")
```

---

**文档版本**: v2.0 (2026-03-10)
**作者**: AgentMatrix Team
**反馈**: 请在 GitHub Issues 提出问题或建议
