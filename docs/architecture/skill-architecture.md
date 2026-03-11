# AgentMatrix Skill 架构文档

> **目标读者**: 项目开发人员
> **文档目的**: 快速理解 Skill 机制、加载流程和命名规范
> **最后更新**: 2026-03-10

---

## 一、Skill 是什么？

### 1.1 核心概念

**Skill** 是 AgentMatrix 中给 Agent 注入能力的机制。通过 Skill，Agent 可以获得执行特定任务的能力（如文件操作、网页浏览、Markdown 编辑等）。

**关键特性**：
- ✅ **可插拔**: Agent 可以动态加载不同的 Skills
- ✅ **懒加载**: 按需加载，不使用不加载
- ✅ **依赖管理**: 自动解析和加载 Skill 依赖
- ✅ **多路径搜索**: 支持内置技能、工作区技能、自定义路径

### 1.2 两种 Skill 类型

| 类型 | 实现方式 | 适用场景 | 示例 |
|------|---------|---------|------|
| **Python Skill** | Python Mixin 类 | 复杂逻辑、API 调用、数据处理 | `file`, `browser`, `markdown` |
| **MD Document Skill** | Markdown 文档 | 操作指南、教程、流程指南 | `git-workflow` |

---

## 二、Skill 加载机制

### 2.1 整体架构流程

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Agent 创建时指定 available_skills                       │
│    MicroAgent(available_skills=["file", "browser"])        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. SKILL_REGISTRY.get_skills() - Lazy Load                │
│    - 检查缓存                                               │
│    - 按优先级搜索路径                                       │
│    - 自动解析依赖                                           │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. 动态类组合 (_create_dynamic_class)                      │
│    type('DynamicAgent', (MicroAgent, FileSkillMixin, ...)) │
└─────────────────────────────────────────────────────────────┐
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Action 扫描 (_scan_all_actions)                         │
│    遍历 MRO，收集所有 @register_action 方法                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Agent 可以直接调用 Skill 的方法                         │
│    await agent.list_dir()                                  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Lazy Load 核心代码

**位置**: `src/agentmatrix/skills/registry.py:118`

```python
def get_skills(self, skill_names: List[str]) -> SkillLoadResult:
    """
    统一入口：Lazy Load + 自动依赖解析

    流程：
    1. 检查缓存 (_python_mixins, _md_skills)
    2. 如果未缓存，自动发现并加载
    3. 递归解析 _skill_dependencies
    4. 循环依赖检测 (loaded + loading 双队列)
    """
    result = SkillLoadResult()
    loaded = set()
    loading = set()

    def load_skill_recursive(name: str) -> bool:
        # 1. 跳过已加载
        if name in loaded:
            return True

        # 2. 循环依赖检测
        if name in loading:
            logger.warning(f"检测到循环依赖: {name}")
            return True

        # 3. 标记正在加载
        loading.add(name)

        # 4. 先加载依赖
        deps = self._get_dependencies(name)
        for dep in deps:
            load_skill_recursive(dep)

        # 5. 加载当前 skill
        success = self._load_skill(name)
        if success:
            loaded.add(name)
        loading.remove(name)
        return success

    for name in skill_names:
        load_skill_recursive(name)

    return result
```

### 2.3 动态类组合

**位置**: `src/agentmatrix/agents/micro_agent.py:148`

```python
def _create_dynamic_class(self, available_skills: List[str]) -> type:
    """
    动态创建包含 Skill Mixins 的类

    工作原理：
    1. 调用 SKILL_REGISTRY.get_skills() 获取 Mixin 类
    2. 使用 type() 动态创建新类
    3. 新类继承 MicroAgent 和所有 Skill Mixins
    4. 替换 self.__class__
    """
    from ..skills.registry import SKILL_REGISTRY

    # Lazy Load 获取 Skills
    result = SKILL_REGISTRY.get_skills(available_skills)
    mixin_classes = result.python_mixins

    # 动态创建类
    # type(name, bases, dict)
    dynamic_class = type(
        f'DynamicAgent_{self.name}',
        (self.__class__,) + tuple(mixin_classes),  # 继承链
        {}
    )

    return dynamic_class
```

**效果**：
```python
# 之前
agent = MicroAgent()  # 只有基础方法

# 之后
agent = MicroAgent(available_skills=["file", "browser"])
agent.__class__.__mro__
# (DynamicAgent_Agent, MicroAgent, FileSkillMixin, BrowserSkillMixin, ...)

# 直接调用
await agent.list_dir()  # 来自 FileSkillMixin
```

### 2.4 Action 扫描

**位置**: `src/agentmatrix/agents/micro_agent.py:217`

```python
def _scan_all_actions(self):
    """
    扫描所有 @register_action 方法

    工作原理：
    1. 遍历 self.__class__.__mro__ (继承链)
    2. 检查每个方法的 _is_action 属性
    3. 存储已绑定的方法到 action_registry
    """
    import inspect

    for cls in self.__class__.__mro__:
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if hasattr(method, '_is_action') and method._is_action:
                # 存储绑定方法
                bound_method = getattr(self, name)
                self.action_registry[name] = bound_method
```

---

## 三、Python Skill 实现

### 3.1 目录结构

```
src/agentmatrix/skills/
├── file_skill.py              # 扁平结构（旧，向后兼容）
├── browser_skill.py           # 扁平结构（旧，向后兼容）
├── markdown/                  # 目录结构（新）
│   ├── __init__.py
│   ├── skill.py              # ✅ 入口文件
│   ├── parser.py             # 辅助模块
│   ├── renderer.py
│   └── ast.py
└── simple_web_search/         # 目录结构（新）
    ├── skill.py
    ├── utils.py
    └── crawler_helpers.py
```

### 3.2 命名规范

| 组件 | 命名规则 | 示例 |
|------|---------|------|
| **目录名** | 小写，下划线分隔 | `simple_web_search/` |
| **文件名** | `skill.py` (固定) | `skill.py` |
| **类名** | `{SkillName}SkillMixin` | `Simple_web_searchSkillMixin` |
| **Skill 名称** | 小写，下划线分隔 | `"simple_web_search"` |
| **Action 方法** | 小写，下划线分隔 | `async def search_web()` |

**注意**: 类名是 `Simple_web_searchSkillMixin`（保留下划线），不是 `SimpleWebSearchSkillMixin`

### 3.3 最小 Skill 模板

```python
# src/agentmatrix/skills/my_skill/skill.py

from ...core.action import register_action

class My_skillSkillMixin:  # 注意：保留下划线
    """我的自定义技能"""

    # 可选：声明依赖
    _skill_dependencies = ["file", "browser"]

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
        return f"完成操作: {param1}"
```

### 3.4 依赖声明

```python
class AdvancedSkillMixin:
    # 声明依赖：系统会自动加载这些 skills
    _skill_dependencies = ["file", "browser", "markdown"]

    @register_action(description="复合操作")
    async def complex_action(self, data: str) -> str:
        # 可以使用依赖的 skills 的 actions
        file_path = await self.write(data)  # 来自 file skill
        content = await self.get_toc(file_path)  # 来自 markdown skill
        return content
```

**依赖解析特性**：
- ✅ 自动递归加载依赖
- ✅ 依赖优先于被依赖者加载
- ✅ 自动去重（同一个 skill 只加载一次）
- ✅ 循环依赖检测（不会崩溃）

---

## 四、MD Document Skill

### 4.1 结构

```
skills/
└── git-workflow/
    └── skill.md              # ✅ Markdown 文档
```

### 4.2 skill.md 格式

```markdown
---
name: git-workflow
description: Git 工作流指南，包括初始化、提交、分支等常见操作
license: MIT
---

# Git 工作流指南

## 概述

本技能指导你如何正确使用 Git 进行版本控制。

---

## Action: 初始化 Git 仓库

**使用场景**：当项目需要开始版本控制时

**步骤**：

1. 进入项目目录：
   ```bash
   cd /path/to/project
   ```

2. 执行初始化：
   ```bash
   git init
   ```

3. 添加所有文件到暂存区：
   ```bash
   git add .
   ```

4. 首次提交：
   ```bash
   git commit -m "Initial commit"
   ```

**注意事项**：
- 确保项目目录中不需要跟踪的文件已添加到 `.gitignore`
- 提交信息应清晰描述本次提交的内容
```

**关键部分**：
1. **YAML Front Matter**（开头）：元数据
2. **Action 章节**：`## Action: 操作名称`

### 4.3 加载机制

**位置**: `src/agentmatrix/skills/md_parser.py`（解析）+ `registry.py:640`（加载）

```python
def _try_load_md_document(self, name: str) -> bool:
    """
    加载 MD Document Skill

    流程：
    1. 定位 skill 目录（查找 skill.md）
    2. 解析 Frontmatter 和 Actions
    3. 复制到 workspace/SKILLS/
    4. 缓存元数据到 _md_skills
    """
    skill_dir = self._get_skill_directory(name)
    skill_md_path = skill_dir / "skill.md"
    metadata = MDSkillParser.parse(skill_md_path)

    # 复制到 workspace
    target_dir = self._workspace_skills_dir / name
    self._copy_skill_to_workspace(skill_dir, target_dir)

    # 缓存
    self._md_skills[name] = metadata
    return True
```

---

## 五、搜索路径与优先级

### 5.1 默认搜索路径

```python
SKILL_REGISTRY.search_paths = [
    "agentmatrix.skills",  # 内置 skills（默认）
]
```

### 5.2 添加工作区技能

**位置**: `src/agentmatrix/skills/registry.py:57`

```python
# 自动添加 workspace/skills/
SKILL_REGISTRY.add_workspace_skills("./MyWorld")

# 结果：
# search_paths = [
#     "./MyWorld/skills",      # 优先级高
#     "agentmatrix.skills",     # 优先级低
# ]
```

### 5.3 手动添加路径

```python
SKILL_REGISTRY.add_search_path("/opt/company_skills")
SKILL_REGISTRY.add_search_path("./my_app/skills")
```

### 5.4 搜索优先级

```
1. 用户配置的路径（最优先）
   ↓
2. workspace/skills/（自动）
   ↓
3. agentmatrix.skills（默认）

对于每个路径：
   a) 目录结构: {path}/{name}/skill.py
   b) 扁平文件: {path}/{name}_skill.py
```

---

## 六、使用示例

### 6.1 在 Profile 中配置

```yaml
# agents/my_agent.yml
name: MyAgent
module: agentmatrix.agents.base
class_name: BaseAgent

skills:
  - file
  - browser
  - markdown
  - simple_web_search  # 自动加载依赖
```

### 6.2 在代码中使用

```python
from agentmatrix.agents.micro_agent import MicroAgent

# 创建带 Skills 的 MicroAgent
agent = MicroAgent(
    parent=parent_agent,
    name="Worker",
    available_skills=["file", "markdown"]  # 🆕 指定 skills
)

# 直接调用
result = await agent.list_dir()
content = await agent.get_toc(file_path="test.md")
```

### 6.3 验证 Skill 加载

```python
# 检查继承链
from agentmatrix.skills.file_skill import FileSkillMixin
assert isinstance(agent, FileSkillMixin)

# 查看 MRO
print(agent.__class__.__mro__)
# (DynamicAgent_Worker, MicroAgent, FileSkillMixin, MarkdownSkillMixin, ...)

# 查看可用的 actions
print(list(agent.action_registry.keys()))
# ['list_dir', 'read', 'write', 'get_toc', 'search_keywords', ...]
```

---

## 七、关键代码位置

| 功能 | 文件路径 | 关键类/函数 |
|------|---------|-----------|
| **Skill Registry** | `src/agentmatrix/skills/registry.py` | `SkillRegistry.get_skills()` |
| **Lazy Load** | `src/agentmatrix/skills/registry.py:469` | `_load_skill()` |
| **依赖解析** | `src/agentmatrix/skills/registry.py:233` | `_get_dependencies()` |
| **动态类组合** | `src/agentmatrix/agents/micro_agent.py:148` | `_create_dynamic_class()` |
| **Action 扫描** | `src/agentmatrix/agents/micro_agent.py:217` | `_scan_all_actions()` |
| **Action 装饰器** | `src/agentmatrix/core/action.py:24` | `@register_action()` |
| **MD Parser** | `src/agentmatrix/skills/md_parser.py` | `MDSkillParser.parse()` |

---

## 八、调试技巧

### 8.1 查看已注册的 Skills

```python
from agentmatrix.skills.registry import SKILL_REGISTRY

# 查看所有已注册的 skills
registered = SKILL_REGISTRY.list_registered_skills()
print(registered)
# {'python': ['file', 'browser', 'markdown', ...], 'md': ['git-workflow', ...]}
```

### 8.2 测试 Skill 加载

```python
from agentmatrix.skills.registry import SKILL_REGISTRY

# 测试加载
result = SKILL_REGISTRY.get_skills(["file", "browser"])
print(result)
# SkillLoadResult(mixins=[FileSkillMixin, BrowserSkillMixin], ...)

# 检查失败
if result.failed_skills:
    print(f"加载失败: {result.failed_skills}")
```

### 8.3 查看 Agent 的 Actions

```python
# 查看所有可用的 actions
for name, action in agent.action_registry.items():
    print(f"{name}: {action._action_desc}")
```

### 8.4 检查继承链

```python
# 查看 Agent 的 MRO
for cls in agent.__class__.__mro__:
    print(cls.__name__)
```

---

## 九、常见问题

### Q1: Skill 未找到？

**症状**: `⚠️ 未找到 Skill: my_skill`

**排查**:
1. 检查目录结构是否正确
2. 检查类名是否符合命名规范
3. 检查是否在搜索路径中

### Q2: 类名错误？

**症状**: `⚠️ 未找到类 My_skillSkillMixin`

**原因**: 类名不匹配命名约定

**解决**:
```python
# ❌ 错误
class MySkill:  # 缺少 SkillMixin 后缀
    pass

# ✅ 正确
class My_skillSkillMixin:  # 注意：保留下划线
    pass
```

### Q3: 如何测试依赖加载？

```python
# 测试依赖自动加载
result = SKILL_REGISTRY.get_skills(["web_search"])
# web_search 依赖 ["browser", "file"]
# 应该返回: [WebSearchSkillMixin, BrowserSkillMixin, FileSkillMixin]
```

---

## 十、总结

### 核心机制

1. **Lazy Load**: 按需加载，首次请求时自动导入
2. **动态组合**: 运行时动态继承 Skill Mixins
3. **依赖管理**: 自动递归解析依赖
4. **统一接口**: `SKILL_REGISTRY.get_skills()` 统一入口

### 开发流程

1. **创建 Skill**: 按命名规范创建 `skill.py`
2. **定义 Actions**: 使用 `@register_action` 装饰器
3. **声明依赖**: `_skill_dependencies = [...]`
4. **配置 Agent**: `available_skills=["my_skill"]`
5. **直接调用**: `await agent.my_action()`

### 设计优势

- ✅ **解耦**: Skill 和 Agent 独立开发
- ✅ **可扩展**: 添加新 Skill 无需修改核心代码
- ✅ **灵活**: Agent 可以动态组合不同的 Skills
- ✅ **类型安全**: Mixin 机制保证代码可读性和 IDE 支持

---

## 🆕 十一、新架构特性（2026-03-10 更新）

### 11.1 嵌套 action_registry 结构

**背景**: 旧版本使用扁平结构 `{"action_name": method}`，无法支持命名空间和冲突检测。

**新结构**:
```python
self.action_registry = {
    "_by_skill": {},      # {skill_name: {action_name: bound_method}}
    "_flat": {},          # {action_name: method, "skill.action": method}
    "_aliases": {},       # {alias_name: "skill.action"}
    "_metadata": {}       # {action_name: {skill_name, original_name, is_renamed}}
}
```

**代码位置**: `src/agentmatrix/agents/micro_agent.py:96-108`

**各部分说明**:

| 字段 | 类型 | 用途 |
|------|------|------|
| `_by_skill` | `Dict[str, Dict[str, Method]]` | 按 skill 分组的 actions，支持 `file.list_dir` 调用 |
| `_flat` | `Dict[str, Method]` | 扁平化索引，同时支持 `list_dir` 和 `file.list_dir` |
| `_aliases` | `Dict[str, str]` | 存储别名映射（用于冲突重命名） |
| `_metadata` | `Dict[str, Dict]` | 存储 action 的元数据（因为绑定方法无法设置属性） |

### 11.2 命名空间支持

**功能**: 支持两种 action 调用格式

```python
# 格式 1: 简写格式（向后兼容）
await agent.list_dir()

# 格式 2: 完整命名（新特性）
await agent._execute_action("file.list_dir", path="/tmp")
```

**解析逻辑** (`_resolve_action` 方法):
```python
def _resolve_action(self, action_call: str):
    """
    解析 action 调用，支持两种格式：
    
    1. "skill.action" → 从 _by_skill[skill][action] 获取
    2. "action" → 从 _flat[action] 获取
    """
    if '.' in action_call:
        skill_name, action_name = action_call.split('.', 1)
        return self.action_registry["_by_skill"][skill_name][action_name]
    else:
        return self.action_registry["_flat"][action_call]
```

**代码位置**: `src/agentmatrix/agents/micro_agent.py:333-390`

### 11.3 冲突检测与自动重命名

**问题**: 不同 skills 可能有同名 actions（如 `file.read` 和 `markdown.read`）

**解决方案**: 自动检测冲突并重命名

```python
# 示例：两个 skills 都有 read 方法
file_skill:     async def read(...)
markdown_skill: async def read(...)

# 冲突检测逻辑
if action_name in registered_actions:
    # 自动重命名
    new_name = f"{skill_name}_{action_name}"
    # file.read → file_read
    # markdown.read → markdown_read
```

**元数据记录**:
```python
self.action_registry["_metadata"]["file_read"] = {
    "skill_name": "file",
    "action_name": "file_read",
    "original_name": "read",
    "is_renamed": True
}
```

**代码位置**: `src/agentmatrix/agents/micro_agent.py:225-350`

**使用建议**:
- ✅ 优先使用完整命名：`file.read`, `markdown.read`
- ⚠️  简写格式有歧义时使用完整命名

### 11.4 Skill 级别元数据

**新特性**: 每个 Python Skill 可以声明自己的元数据

```python
class FileSkillMixin:
    # 🆕 Skill 级别描述
    _skill_description = "文件操作技能：读取、写入、搜索文件和目录，执行 shell 命令"
    
    # 🆕 使用指南
    _skill_usage_guide = """
使用场景：
- 需要读取或写入文件
- 需要列出目录内容
- 需要在文件中搜索内容

使用建议：
- 使用 list_dir 查看目录结构
- 使用 read 读取文件内容
- 使用 write 写入文件

注意事项：
- 所有路径都是相对于 workspace_root
- shell 命令在容器内执行（如果是 Docker 环境）
"""
```

**元数据用途**:
1. **System Prompt**: 生成 Skill 分组描述
2. **Help Action**: 提供详细的使用说明

**示例 Skills 已添加元数据**:
- ✅ `file` - 文件操作
- ✅ `email` - 邮件发送
- ✅ `memory` - 记忆管理
- ✅ `markdown` - Markdown 编辑
- ✅ `simple_web_search` - 网页搜索
- ✅ `browser` - 浏览器自动化

### 11.5 Help Action 系统

**功能**: 提供可查询的在线帮助系统

**三种调用模式**:

#### 模式 1: 列出所有 Skills
```python
result = await agent.help()
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
```

#### 模式 2: 查看单个 Skill 详情
```python
result = await agent.help(skill="file")
```

**输出示例**:
```
=== File Skill ===

文件操作技能：读取、写入、搜索文件和目录，执行 shell 命令

使用场景：
- 需要读取或写入文件
- 需要列出目录内容
- 需要在文件中搜索内容

可用 actions:

- **file_bash**: 执行 bash 命令或脚本（在容器内执行）
  参数:
    - command: bash 命令或脚本（多行脚本用 \n 分隔）

- **file_list_dir**: 列出目录内容
  参数:
    - path: 目录路径

- **file_read**: 读取文件内容
  参数:
    - file_path: 文件路径
    - start_line: 起始行（可选，默认 0）
    - end_line: 结束行（可选，默认 None）
```

#### 模式 3: 查看单个 Action 详情
```python
result = await agent.help(skill="file", action="read")
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

**代码位置**: `src/agentmatrix/agents/micro_agent.py:500-700`

### 11.6 System Prompt 改进

**旧格式**: 扁平列出所有 actions（包含完整参数）

```text
可用工具：
- list_dir(path): 列出目录内容
- read(file_path, start_line, end_line): 读取文件
- write(file_path, content): 写入文件
- get_toc(file_path, depth): 获取目录
... (可能有 50+ 行)
```

**新格式**: 按 Skill 分组，只显示 action 名称

```text
### 🧰 可用工具箱 (Toolbox)

#### A. 核心指令 (Native Actions)
这些是你原本就具备的能力：
- all_finished: 任务完成通知
- help: 查看帮助信息

#### B. 文件操作 (file)
文件操作技能：读取、写入、搜索文件和目录，执行 shell 命令
可用 actions: list_dir, read, write, search_file, bash

#### C. 邮件发送 (email)
邮件发送技能：向其他 Agent 发送邮件，支持附件传输
可用 actions: send_email

#### D. 记忆管理 (memory)
记忆管理技能：存储、查询、更新实体和事件的记忆
可用 actions: recall, update_memory

💡 提示：使用 help(skill="xxx") 查看详细参数说明
```

**优势**:
1. ✅ **更清晰**: 按功能分组，易于理解
2. ✅ **更简洁**: 只显示 action 名称，不显示完整参数
3. ✅ **可扩展**: 新增 skill 不会让 prompt 过长
4. ✅ **引导查询**: 提示使用 help() 查看详情

**代码位置**: `src/agentmatrix/agents/micro_agent.py:950-1100`

---

## 十二、迁移指南

### 12.1 从旧版本迁移

**无需改动的情况**:
```python
# ✅ 简写格式仍然支持
await agent.list_dir()
await agent.read(file_path="test.txt")
```

**建议改用新格式**:
```python
# ✅ 更明确（推荐）
await agent._execute_action("file.list_dir", path="/tmp")
await agent._execute_action("markdown.get_toc", file_path="test.md")
```

### 12.2 处理冲突重命名

**检测冲突**:
```python
# 检查 action 是否被重命名
metadata = agent.action_registry["_metadata"]
for name, meta in metadata.items():
    if meta["is_renamed"]:
        print(f"⚠️  {meta['original_name']} → {name}")
        print(f"   来自 skill: {meta['skill_name']}")
```

**使用重命名后的 action**:
```python
# 原始名称: read
# 重命名后: file_read, markdown_read

# 方式 1: 使用完整命名（推荐）
await agent._execute_action("file.read", ...)

# 方式 2: 使用重命名后的简写
await agent.file_read(...)
```

### 12.3 添加 Skill 元数据

**步骤**:
1. 打开你的 skill 文件（如 `my_skill/skill.py`）
2. 添加类属性 `_skill_description` 和 `_skill_usage_guide`
3. 测试 help 功能

**示例**:
```python
class My_skillSkillMixin:
    # 添加这两行
    _skill_description = "我的技能描述"
    _skill_usage_guide = "使用指南..."
    
    @register_action(...)
    async def my_action(self, ...):
        pass
```

---

## 十三、最佳实践

### 13.1 命名规范

**Skill 命名**:
- ✅ 小写，下划线分隔: `simple_web_search`
- ❌ 避免驼峰: `SimpleWebSearch`
- ❌ 避免连字符: `simple-web-search`

**Action 命名**:
- ✅ 动词开头: `read_file`, `search_keywords`
- ✅ 小写，下划线分隔
- ❌ 避免过于通用: `process`, `handle` → `process_order`, `handle_request`

### 13.2 避免冲突

**检查现有 actions**:
```python
# 在开发新 skill 前，先检查是否已有同名 action
existing_actions = set()
for name, meta in agent.action_registry["_metadata"].items():
    existing_actions.add(meta["original_name"])

# 如果冲突，考虑使用更具体的名称
# ❌ read() → ✅ read_file(), read_config()
```

**使用完整命名**:
```python
# 即使有冲突，也可以用完整命名区分
await agent._execute_action("file.read", ...)
await agent._execute_action("markdown.read", ...)
```

### 13.3 文档建议

**添加元数据**:
```python
_skill_description = "简洁的一句话描述"

_skill_usage_guide = """
## 使用场景
- 场景 1
- 场景 2

## 使用建议
- 建议 1
- 建议 2

## 注意事项
- 注意 1
- 注意 2
"""
```

**Action 文档**:
```python
@register_action(
    description="清晰的一句话说明",
    param_infos={
        "param1": "参数1说明（包括类型、是否可选、默认值）",
        "param2": "参数2说明"
    }
)
async def my_action(self, param1: str, param2: int = 10) -> str:
    """
    可选：更详细的实现说明
    """
    pass
```

---

## 十四、性能优化

### 14.1 Action 扫描优化

**现状**: 每次创建 Agent 都扫描整个 MRO

**优化建议**:
```python
# 考虑缓存 action_registry
class MicroAgent:
    _action_registry_cache = {}  # 类级别缓存
    
    def _scan_all_actions(self):
        cache_key = tuple(self.__class__.__mro__)
        if cache_key in self._action_registry_cache:
            self.action_registry = self._action_registry_cache[cache_key]
            return
        # ... 扫描逻辑
        self._action_registry_cache[cache_key] = self.action_registry
```

### 14.2 Help 查询优化

**现状**: 每次 help() 都重新格式化

**优化建议**:
```python
# 缓存 help 结果
class MicroAgent:
    _help_cache = {}
    
    async def help(self, skill: str = None, action: str = None):
        cache_key = f"{skill}:{action}" if skill else "all"
        if cache_key in self._help_cache:
            return self._help_cache[cache_key]
        # ... 生成 help
        self._help_cache[cache_key] = result
        return result
```

---

## 十五、故障排查

### 15.1 Help 不显示 Skill？

**症状**: `help()` 没有列出我的 skill

**排查**:
```python
# 1. 检查 skill 是否加载
print(list(agent.action_registry["_by_skill"].keys()))

# 2. 检查元数据
my_skill = agent.action_registry["_by_skill"].get("my_skill")
if my_skill:
    print("Skill 已加载")
else:
    print("Skill 未加载")

# 3. 检查 _skill_description
from agentmatrix.skills.my_skill.skill import My_skillSkillMixin
print(hasattr(My_skillSkillMixin, '_skill_description'))
```

### 15.2 Action 调用失败？

**症状**: `_execute_action()` 报错

**排查**:
```python
# 1. 检查 action 是否存在
try:
    method = agent._resolve_action("file.read")
    print("Action 存在")
except ValueError as e:
    print(f"Action 不存在: {e}")

# 2. 检查参数是否正确
import inspect
sig = inspect.signature(method)
print(f"参数: {sig}")
```

### 15.3 冲突重命名导致调用失败？

**症状**: 调用 `agent.read()` 失败

**解决**:
```python
# 1. 查看重命名映射
for name, meta in agent.action_registry["_metadata"].items():
    if meta["original_name"] == "read":
        print(f"read → {name} (来自 {meta['skill_name']})")

# 2. 使用完整命名
await agent._execute_action("file.read", ...)

# 3. 或使用重命名后的方法
await agent.file_read(...)
```

---

