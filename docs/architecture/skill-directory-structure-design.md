# Skill 目录结构设计

**文档版本**: v2.0.0 | **最后更新**: 2026-02-26 | **状态**: ✅ 已实现

## 概述

### 核心功能

AgentMatrix 支持**两种类型的 Skills**，都可以通过目录结构组织：

1. **Python Skills**：用 Python 编程实现的技能（使用 `skill.py`）
2. **MD Document Skills**：用 Markdown 编写的文档技能（使用 `skill.md`）

### 技能发现机制

```
搜索优先级（从高到低）：
1. workspace/skills/           # Workspace 级（自动发现）
2. agentmatrix.skills         # 内置 skills
```

**特性**：
- ✅ 支持**目录结构**（`skill_name/skill.py` 或 `skill_name/skill.md`）
- ✅ 支持**扁平结构**（`skill_name_skill.py`，向后兼容）
- ✅ Workspace 级技能**优先于内置技能
- ✅ 完全向后兼容

---

## Python Skills

### 目录结构

**推荐的目录结构**：

```
my_app/
├── skills/                       # 应用级 skills 目录
│   └── my_custom_skill/          # Skill 名称（目录名）
│       ├── skill.py              # ✅ 必须：技能入口
│       ├── helpers.py            # 可选：辅助函数
│       └── config.py             # 可选：配置
```

**命名约定**：
- **目录名** → Skill 名称：`my_custom_skill/` → `my_custom_skill`
- **类名**：`My_custom_skillSkillMixin`（自动首字母大写 + 下划线）
- **入口文件**：`skill.py`（固定名称）

### skill.py 结构

**完整的 skill.py 示例**：

```python
# skills/my_custom_skill/skill.py
from agentmatrix.core.action import register_action

class My_custom_skillSkillMixin:
    """我的自定义技能"""

    # 声明依赖的其他 skills（可选）
    _skill_dependencies = ["file", "browser"]

    @register_action(
        description="执行我的自定义操作",
        param_infos={
            "input_data": "输入数据"
        }
    )
    async def my_custom_action(self, input_data: str) -> str:
        """自定义 action"""
        # 实现代码
        return f"处理完成: {input_data}"
```

**关键点**：
1. **类名**：必须是 `{SkillName}SkillMixin` 格式
2. **装饰器**：用 `@register_action` 标记 action
3. **依赖声明**：`_skill_dependencies` 列表（自动加载）

### 多文件 Skill

Skill 可以包含多个文件：

```
skills/
└── data_processor/
    ├── skill.py              # 入口：包含 Mixin 类
    ├── helpers.py            # 辅助函数
    ├── models.py             # 数据模型
    └── utils.py              # 工具函数
```

**在 skill.py 中导入**：

```python
# skill.py
from .helpers import process_data
from .models import DataModel

class Data_processorSkillMixin:
    @register_action(description="处理数据")
    async def process(self, data: str) -> str:
        # 使用辅助函数
        return process_data(data)
```

### 完整示例

**示例：数据库操作 Skill**

```
my_app/
└── skills/
    └── database_ops/
        ├── skill.py
        └── connection.py
```

```python
# skill.py
from agentmatrix.core.action import register_action
from .connection import get_connection

class Database_opsSkillMixin:
    """数据库操作技能"""

    _skill_dependencies = ["file"]

    @register_action(
        description="查询数据库",
        param_infos={
            "query": "SQL 查询语句"
        }
    )
    async def query_db(self, query: str) -> str:
        """执行查询"""
        conn = get_connection()
        results = conn.execute(query)
        return str(results)

    @register_action(
        description="执行数据库事务"
    )
    async def execute_transaction(self, operations: list) -> str:
        """执行事务"""
        conn = get_connection()
        with conn.transaction():
            for op in operations:
                conn.execute(op)
        return "事务执行成功"
```

```python
# connection.py
import sqlite3

def get_connection():
    """获取数据库连接"""
    return sqlite3.connect("my_database.db")
```

---

## MD Document Skills

### 概述

**MD Document Skills** 是用 Markdown 编写的文档技能，提供结构化的操作指南。

**特点**：
- 无需编程
- 易于维护和更新
- 支持版本控制
- 适合操作指南、教程类技能

### 目录结构

```
workspace/
└── skills/
    └── git-workflow/          # Skill 名称
        └── skill.md           # ✅ 必须：技能文档
```

### skill.md 结构

**完整的 skill.md 示例**：

```markdown
---
name: git-workflow
description: Git 工作流指南，包括初始化、提交、分支等常见操作
license: MIT
---

# Git 工作流指南

## 概述

本技能指导你如何正确使用 Git 进行版本控制。

## 前置条件

- 已安装 Git
- 拥有 terminal 访问权限

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

---

## Action: 提交更改

**使用场景**：当代码需要保存快照时

**步骤**：
...
```

**关键部分**：
1. **YAML Front Matter**（开头）：
   ```yaml
   ---
   name: skill-name
   description: 技能描述
   license: MIT
   ---
   ```
2. **Action 章节**：
   ```markdown
   ## Action: 操作名称

   **使用场景**：...
   **步骤**：...
   ```

### MD Skill 加载机制

**代码位置**：`src/agentmatrix/skills/registry.py`

MD Skills 通过 `MDSkillMetadata` 解析：

```python
@dataclass
class MDSkillMetadata:
    """MD Document Skill 元数据"""
    name: str                  # Skill 名称
    description: str           # 描述
    license: Optional[str]     # 许可证
    file_path: Path            # skill.md 文件路径
    actions: List[str]         # Action 列表
```

**识别规则**：
1. 读取 `skill.md` 文件
2. 解析 YAML Front Matter
3. 提取所有 `## Action:` 章节
4. 缓存元数据

### 使用 MD Skill

**在 Agent Profile 中配置**：

```yaml
# agents/git_helper.yml
name: GitHelper
description: Git 操作助手

skills:
  - git-workflow  # MD Skill
```

**在代码中使用**：

```python
from agentmatrix.skills.registry import SKILL_REGISTRY

# 获取 skill
skill_metadata = SKILL_REGISTRY.get_md_skill("git-workflow")

# 获取可用的 actions
actions = skill_metadata.actions
# ["初始化 Git 仓库", "提交更改", "创建分支", ...]
```

---

## 加载机制

### SkillRegistry 初始化

**代码位置**：`src/agentmatrix/skills/registry.py`

```python
class SkillRegistry:
    def __init__(self):
        # Python Mixin 注册表
        self._python_mixins: Dict[str, Type] = {}

        # MD Document Metadata 注册表
        self._md_skills: Dict[str, MDSkillMetadata] = {}

        # Workspace SKILLS 目录路径（由 BaseAgent 设置）
        self._workspace_skills_dir: Optional[Path] = None

        # Skill 搜索路径列表（优先级从高到低）
        self.search_paths: List[str] = ["agentmatrix.skills"]
```

### 添加 Workspace Skills

**自动添加 workspace/skills/ 目录**：

```python
# 在 AgentMatrix.__init__() 中调用
SKILL_REGISTRY.add_workspace_skills(matrix_path)

# 代码位置：skills/registry.py
def add_workspace_skills(self, matrix_path: str):
    """
    自动添加 workspace/skills/ 目录到搜索路径

    Args:
        matrix_path: Workspace 根目录（例如 "./MyWorld"）
    """
    skills_dir = Path(matrix_path) / "skills"
    if skills_dir.exists():
        # 添加到搜索路径（位置1，优先级高于默认）
        self.search_paths.insert(1, str(skills_dir))
        logger.info(f"✅ 添加 Skill 搜索路径: {skills_dir}")
```

### 加载流程

**Python Skills 加载**：

```python
def _try_load_python_mixin(self, name: str) -> bool:
    """
    按优先级尝试所有搜索路径和两种结构

    优先级：
    1. workspace/skills/（如果配置）
    2. agentmatrix.skills/（内置）

    结构：
    1. 目录结构（新）：skill_name/skill.py
    2. 扁平结构（旧）：skill_name_skill.py
    """
    for base_path in self.search_paths:
        # 方式1: 目录结构
        if self._try_load_from_directory(base_path, name):
            return True

        # 方式2: 扁平文件（向后兼容）
        if self._try_load_from_flat_file(base_path, name):
            return True

    return False
```

**MD Skills 加载**：

```python
def _scan_md_skills(self):
    """
    扫描所有搜索路径，发现 MD Document Skills

    规则：
    - 查找 skill.md 文件
    - 提取 YAML Front Matter
    - 提取 ## Action: 章节
    """
    for base_path in self.search_paths:
        # 递归查找 skill.md
        for skill_file in Path(base_path).rglob("*/skill.md"):
            # 解析元数据
            metadata = self._parse_md_skill(skill_file)
            if metadata:
                self._md_skills[metadata.name] = metadata
```

---

## 使用方法

### 创建 Python Skill

**步骤 1: 创建目录结构**

```bash
cd my_app/
mkdir -p skills/my_custom_skill
```

**步骤 2: 编写 skill.py**

```python
# skills/my_custom_skill/skill.py
from agentmatrix.core.action import register_action

class My_custom_skillSkillMixin:
    """我的自定义技能"""

    _skill_dependencies = ["file"]

    @register_action(
        description="处理数据",
        param_infos={
            "input": "输入数据"
        }
    )
    async def process(self, input: str) -> str:
        return f"处理: {input}"
```

**步骤 3: 在 Profile 中使用**

```yaml
# agents/my_agent.yml
name: MyAgent
module: agentmatrix.agents.base
class_name: BaseAgent

skills:
  - my_custom_skill  # 自动加载
```

### 创建 MD Document Skill

**步骤 1: 创建目录**

```bash
mkdir -p workspace/skills/git-guide
```

**步骤 2: 编写 skill.md**

```markdown
---
name: git-guide
description: Git 使用指南
---

# Git 使用指南

## Action: 克隆仓库

**使用场景**：获取远程代码

**步骤**：
1. 打开终端
2. 执行：`git clone <url>`
```

**步骤 3: 在 Profile 中使用**

```yaml
skills:
  - git-guide
```

### Workspace Skills 自动发现

**创建 workspace skills**：

```bash
# 在 workspace 目录下
cd MyWorld/
mkdir -p skills/company_tools
```

**添加技能文件**：

```python
# MyWorld/skills/company_tools/skill.py
from agentmatrix.core.action import register_action

class Company_toolsSkillMixin:
    """公司内部工具"""

    @register_action(description="访问内部系统")
    async def access_internal(self, api: str) -> str:
        # 实现
        pass
```

**自动发现**：

```python
# AgentMatrix 初始化时自动添加
matrix = AgentMatrix(
    agent_profile_path="./profiles",
    matrix_path="./MyWorld"  # 自动发现 MyWorld/skills/
)
```

---

## 技能依赖

### _skill_dependencies

Python Skills 可以声明依赖的其他 skills：

```python
class My_advanced_skillSkillMixin:
    """高级技能"""

    # 声明依赖
    _skill_dependencies = ["file", "browser", "database"]

    @register_action(description="复合操作")
    async def complex_action(self, data: str) -> str:
        # 可以使用依赖的 skills 的 actions
        file_path = await self.write(data)
        browser_result = await self.open_page(file_path)
        db_result = await self.query_db(f"SELECT * FROM {data}")
        return db_result
```

**自动加载**：

当 Agent 使用 `my_advanced_skill` 时：
```python
skills = ["my_advanced_skill"]

# 系统自动加载：
result = SKILL_REGISTRY.get_skills(skills)
# 返回：
# [
#   My_advanced_skillSkillMixin,
#   FileSkillMixin,          # 依赖
#   BrowserSkillMixin,        # 依赖
#   Database_opsSkillMixin   # 依赖
# ]
```

---

## 配置方式

### 方式1: 自动发现（推荐）

**Workspace Skills** 自动发现：

```python
matrix = AgentMatrix(
    agent_profile_path="./profiles",
    matrix_path="./MyWorld"  # 自动发现 MyWorld/skills/
)
```

### 方式2: 代码配置

**手动配置搜索路径**：

```python
from agentmatrix.core.runtime import AgentMatrix

matrix = AgentMatrix(
    agent_profile_path="./profiles",
    matrix_path="./MyWorld",
    skill_search_paths=[          # 额外搜索路径
        "./skills",              # 应用 skills
        "/opt/shared_skills"     # 共享 skills
    ]
)
```

### 方式3: YAML 配置

**在 matrix_world.yml 中配置**（如果支持）：

```yaml
skill_search_paths:
  - /path/to/my_app/skills
  - /opt/company_shared_skills
```

---

## 完整示例

### 示例1: 爬虫 Skill

**目录结构**：

```
skills/
└── web_crawler/
    ├── skill.py
    ├── parser.py
    └── storage.py
```

**skill.py**：

```python
from agentmatrix.core.action import register_action
from .parser import extract_content
from .storage import save_to_db

class Web_crawlerSkillMixin:
    """网页爬虫技能"""

    _skill_dependencies = ["browser"]

    @register_action(
        description="爬取网页内容",
        param_infos={
            "url": "目标URL"
        }
    )
    async def crawl(self, url: str) -> str:
        """爬取网页"""
        # 1. 打开页面
        html = await self.open_page(url)

        # 2. 提取内容
        content = extract_content(html)

        # 3. 保存到数据库
        save_to_db(content)

        return f"爬取完成，提取 {len(content)} 条数据"
```

**使用**：

```yaml
# agents/crawler_agent.yml
name: CrawlerAgent
skills:
  - web_crawler
```

### 示例2: MD Skill - 文档助手

**skill.md**：

```markdown
---
name: doc-helper
description: 文档编写助手，提供 Markdown 文档模板和编写规范
---

# 文档编写助手

## Action: 创建 API 文档模板

**使用场景**：需要为新 API 编写文档时

**模板**：

```markdown
# API 文档：{API_NAME}

## 概述

简要描述 API 的功能和用途。

## 请求

### 方法
- GET /api/resource

### 参数
| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | int | 是 | 资源ID |

## 响应

### 成功响应
```json
{
  "status": "success",
  "data": {...}
}
```
```

**步骤**：
1. 复制上述模板
2. 填写 {API_NAME} 等变量
3. 根据实际情况调整内容
```

### 示例3: Workspace Skill

**创建 workspace skill**：

```bash
# 在 MyWorld/ 下
mkdir -p skills/research_tools
```

**skill.py**：

```python
# MyWorld/skills/research_tools/skill.py
from agentmatrix.core.action import register_action

class Research_toolsSkillMixin:
    """研究工具"""

    _skill_dependencies = ["file", "web_search"]

    @register_action(description="保存研究笔记")
    async def save_note(self, topic: str, content: str) -> str:
        """保存笔记"""
        filename = f"{topic}.md"
        await self.write(filename, content)
        return f"笔记已保存: {filename}"
```

**自动发现**：

```python
# 只需初始化 AgentMatrix
matrix = AgentMatrix(
    agent_profile_path="./profiles",
    matrix_path="./MyWorld"  # 自动发现 MyWorld/skills/
)

# 配置 Agent 使用
result = SKILL_REGISTRY.get_skills(["research_tools"])
```

---

## 向后兼容性

### 支持的格式

**优先级**（从高到低）：

1. **目录结构**（新）：
   ```
   my_skill/skill.py
   ```

2. **扁平文件**（旧，向后兼容）：
   ```
   browser_skill.py
   file_skill.py
   ```

**加载逻辑**：

```python
# 先尝试目录结构
if not _try_load_from_directory(...):
    # 再尝试扁平文件
    _try_load_from_flat_file(...)
```

### 迁移指南

**从扁平文件迁移到目录结构**：

**旧结构**（仍可用）：
```
skills/
├── browser_skill.py      # BrowserSkillMixin
└── file_skill.py         # FileSkillMixin
```

**新结构**（推荐）：
```
skills/
├── browser/
│   ├── skill.py          # BrowserSkillMixin
│   └── helpers.py
└── file/
    ├── skill.py          # FileSkillMixin
    └── utils.py
```

**迁移步骤**：
1. 创建目录：`mkdir -p browser/`
2. 移动并重命名：`mv browser_skill.py browser/skill.py`
3. 更新类名（如果需要）
4. 删除旧文件（或保留两者共存）

---

## 最佳实践

### Python Skills

#### ✅ 命名规范

```python
# 目录名：小写，下划线分隔
my_custom_skill/

# 类名：首字母大写，下划线保留
My_custom_skillSkillMixin

# Action 名：小写，下划线分隔
async def my_custom_action()
```

#### ✅ 依赖声明

```python
class MySkillMixin:
    # 明确声明依赖
    _skill_dependencies = ["file", "browser"]
```

#### ✅ 辅助函数分离

```python
# skill.py - 只包含 Mixin 类和 actions
class MySkillMixin:
    async def main_action(self):
        helper_result = helper_function(...)

# helpers.py - 辅助函数
def helper_function(...):
    ...
```

### MD Skills

#### ✅ 清晰的章节结构

```markdown
## Action: 操作名称

**使用场景**：...
**步骤**：...
```

#### ✅ 代码示例

```markdown
**步骤**：
1. 执行命令：
   ```bash
   git commit -m "message"
   ```
```

#### ✅ 注意事项

```markdown
**注意事项**：
- 确保已安装依赖
- 检查权限设置
```

---

## 故障排查

### Python Skills

#### 问题1: Skill 未找到

**症状**：
```
⚠️  未找到 Skill: my_skill
```

**排查**：
1. 检查目录结构：
   ```bash
   ls -la skills/my_skill/skill.py
   ```
2. 检查类名是否正确
3. 检查是否在搜索路径中

#### 问题2: 类名错误

**症状**：
```
⚠️  未找到类 My_skillSkillMixin
```

**原因**：类名不匹配命名约定

**解决**：
```python
# 错误
class MySkill:  # 缺少 SkillMixin 后缀
    pass

# 正确
class My_skillSkillMixin:
    pass
```

### MD Skills

#### 问题1: Front Matter 解析失败

**症状**：
```
⚠️  解析 skill.md 失败
```

**排查**：
1. 检查 YAML 格式：
   ```markdown
   ---
   name: skill-name
   ---
   ```

2. 确保使用正确的 YAML 分隔符（`---`）

#### 问题2: Action 未识别

**症状**：Action 没有被识别

**原因**：章节标题格式不对

**解决**：
```markdown
# ❌ 错误
### Action: 初始化仓库

# ✅ 正确
## Action: 初始化仓库
```

---

## 总结

### 两种 Skill 类型

| 类型 | 入口文件 | 适用场景 | 示例 |
|------|---------|---------|------|
| **Python Skills** | `skill.py` | 编程实现的复杂逻辑 | 数据库操作、API调用 |
| **MD Document Skills** | `skill.md` | 文档、教程类技能 | 操作指南、指南 |

### 目录结构

```
workspace/
├── skills/                       # 自动发现
│   ├── python_skill/            # Python Skill
│   │   └── skill.py
│   └── doc_guide/               # MD Skill
│       └── skill.md
└── ...
```

### API 参考

```python
# 初始化 AgentMatrix（自动添加 workspace skills）
matrix = AgentMatrix(
    agent_profile_path="./profiles",
    matrix_path="./MyWorld"
)

# 手动添加搜索路径
SKILL_REGISTRY.add_workspace_skills("./MyWorld")

# 获取 skills（自动加载依赖）
result = SKILL_REGISTRY.get_skills(["my_skill"])
```

### 参见

- **实现代码**：`src/agentmatrix/skills/registry.py`
- **Python Skill 示例**：`src/agentmatrix/skills/file_skill.py`
- **MD Skill 示例**：`src/agentmatrix/skills/git-workflow/skill.md`
- **Agent 配置**：`profiles/*.yml`
