# Skill v2.0 迁移指南

> **快速上手**: 5 分钟了解如何使用新的 Skill 架构
> **阅读时间**: 5 分钟
> **难度**: ⭐ 简单

---

## 🎯 一句话总结

**新架构 = 命名空间 + Help 系统 + 更好的提示词**

**重要**: 旧代码无需修改，仍然可以正常工作！ ✅

---

## 🚀 快速开始

### 1. 旧代码仍然可用

```python
# ✅ 这些代码不需要任何修改
await agent.list_dir()
await agent.read(file_path="test.txt")
await agent.write(file_path="output.txt", content="Hello")
```

### 2. 推荐使用新格式（可选）

```python
# ✅ 新格式（更明确）
await agent._execute_action("file.list_dir", path="/tmp")
await agent._execute_action("file.read", file_path="test.txt")
await agent._execute_action("markdown.get_toc", file_path="test.md")
```

### 3. 使用 Help 系统

```python
# 查看所有可用的 skills
print(await agent.help())

# 查看特定 skill 的详情
print(await agent.help(skill="file"))

# 查看特定 action 的详情
print(await agent.help(skill="file", action="read"))
```

---

## 💡 三个新特性

### 特性 1: 命名空间调用

**问题**: 不同 skills 可能有同名 actions

**解决**: 使用 `skill.action` 格式

```python
# 明确指定使用哪个 skill 的 action
await agent._execute_action("file.read", file_path="test.txt")
await agent._execute_action("markdown.read", file_path="doc.md")
```

### 特性 2: Help 系统

**问题**: 不清楚有哪些 actions 可以用

**解决**: 使用 `help()` 查询

```python
# 列出所有 skills
await agent.help()

# 查看 skill 详情
await agent.help(skill="file")

# 查看 action 详情
await agent.help(skill="file", action="read")
```

### 特性 3: 更好的提示词

**问题**: System Prompt 太长，LLM 难以理解

**解决**: 按 skill 分组，减少 75% 长度

**旧格式** (~2000 tokens):
```
可用工具：
- list_dir(path): 列出目录内容
- read(file_path, start_line, end_line): 读取文件
- write(file_path, content): 写入文件
- get_toc(file_path, depth): 获取目录
... (50+ 行)
```

**新格式** (~500 tokens):
```
#### 文件操作 (file)
文件操作技能：读取、写入、搜索文件和目录
可用 actions: list_dir, read, write, search_file

#### Markdown 编辑 (markdown)
Markdown 文档编辑技能：编辑、总结、搜索文档
可用 actions: get_toc, search_keywords, modify_node

💡 提示：使用 help(skill="xxx") 查看详细参数说明
```

---

## 🔧 实战示例

### 示例 1: 文件操作

```python
# 旧方式（仍然支持）
files = await agent.list_dir(path="/tmp")

# 新方式（推荐）
files = await agent._execute_action("file.list_dir", path="/tmp")
```

### 示例 2: Markdown 编辑

```python
# 旧方式
toc = await agent.get_toc(file_path="doc.md")

# 新方式
toc = await agent._execute_action("markdown.get_toc", file_path="doc.md", depth=2)
```

### 示例 3: 查看帮助

```python
# 开发时查看可用功能
print(await agent.help())

# 输出示例：
# === 可用的 Skills ===
#
# **file**
#   文件操作技能：读取、写入、搜索文件和目录
#
# **markdown**
#   Markdown 文档编辑技能：编辑、总结、搜索文档
#
# 💡 提示：使用 help(skill="xxx") 查看详细参数说明
```

### 示例 4: 处理冲突

```python
# 如果 action 被重命名（冲突检测）
# 原始名称: read
# 重命名后: file_read, markdown_read

# 方式 1: 使用完整命名（推荐）
await agent._execute_action("file.read", file_path="test.txt")

# 方式 2: 使用重命名后的方法
await agent.file_read(file_path="test.txt")
```

---

## 📚 开发新 Skill

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
"""

    @register_action(
        description="执行某个操作",
        param_infos={
            "param1": "参数1说明",
            "param2": "参数2说明（可选）"
        }
    )
    async def my_action(self, param1: str, param2: str = None) -> str:
        """实现"""
        return f"完成: {param1}"
```

### 检查清单

开发新 skill 时，确保：

- [ ] 添加 `_skill_description`
- [ ] 添加 `_skill_usage_guide`
- [ ] 使用明确的 action 名称（避免冲突）
- [ ] 测试 `help()` 功能
- [ ] 测试命名空间调用

---

## 🐛 常见问题

### Q1: 我需要修改现有代码吗？

**A**: 不需要！旧代码仍然可以正常工作。

```python
# ✅ 这些调用继续工作
await agent.list_dir()
await agent.read(file_path="test.txt")
```

### Q2: 为什么要用新格式？

**A**:
- ✅ 更明确（知道使用哪个 skill）
- ✅ 避免冲突（不同 skills 的同名 actions）
- ✅ 更好的代码可读性

### Q3: 如何查看有哪些 actions？

**A**: 使用 help 系统

```python
# 查看所有 skills
await agent.help()

# 查看特定 skill
await agent.help(skill="file")

# 查看特定 action
await agent.help(skill="file", action="read")
```

### Q4: 如果 action 被重命名了怎么办？

**A**: 使用完整命名

```python
# 原始名称: read
# 重命名后: file_read

# 方式 1: 使用完整命名（推荐）
await agent._execute_action("file.read", ...)

# 方式 2: 使用重命名后的方法
await agent.file_read(...)
```

### Q5: 如何测试我的 skill？

**A**:

```python
# 1. 创建测试 agent
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
```

---

## 📖 进一步阅读

### 文档

- **[Skill 架构文档](./skill-architecture.md)** - 完整的架构说明
- **[命名空间快速参考](./skill-namespace-guide.md)** - 快速查询手册
- **[更新日志](./skill-refactoring-changelog.md)** - 详细的变更记录

### 代码位置

| 功能 | 文件 | 说明 |
|------|------|------|
| **Action Registry** | `src/agentmatrix/agents/micro_agent.py` | 96-108 行 |
| **Action 解析** | `src/agentmatrix/agents/micro_agent.py` | 333-390 行 |
| **Help Action** | `src/agentmatrix/agents/micro_agent.py` | 500-700 行 |
| **System Prompt** | `src/agentmatrix/agents/micro_agent.py` | 950-1100 行 |

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

## ✅ 迁移检查清单

### 阅读文档

- [x] 了解新特性（命名空间、Help 系统）
- [x] 了解向后兼容性
- [x] 了解如何使用 Help 系统

### 测试现有代码

- [ ] 运行现有测试套件
- [ ] 验证旧代码仍然工作
- [ ] 检查是否有冲突重命名

### 可选：采用新格式

- [ ] 逐步改用 `skill.action` 格式
- [ ] 使用 `help()` 查看功能
- [ ] 更新文档和示例

### 开发新 Skill

- [ ] 添加 `_skill_description`
- [ ] 添加 `_skill_usage_guide`
- [ ] 使用明确的 action 名称
- [ ] 测试 Help 功能

---

## 🎓 关键要点

1. **向后兼容**: 旧代码无需修改 ✅
2. **命名空间**: 使用 `skill.action` 格式更明确
3. **Help 系统**: 使用 `help()` 查询功能
4. **更好的提示词**: System Prompt 减少 75% 长度
5. **冲突检测**: 自动重命名同名 actions

---

**版本**: v2.0
**最后更新**: 2026-03-10
**作者**: AgentMatrix Team

---

## 🚀 立即开始

```python
# 1. 查看可用功能
print(await agent.help())

# 2. 查看感兴趣的 skill
print(await agent.help(skill="file"))

# 3. 使用新格式调用
await agent._execute_action("file.read", file_path="test.txt")

# 4. 查看帮助
print(await agent.help(skill="file", action="read"))
```

**就这么简单！** 🎉
