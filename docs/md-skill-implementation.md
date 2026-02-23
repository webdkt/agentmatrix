# Markdown Skill 系统实现文档

## 概述

AgentMatrix 现在支持两种类型的技能：

1. **Python Mixin Skills**：提供底层能力的 Python 类（如 `file`、`browser`）
2. **Markdown Document Skills**：操作指南/流程文档，LLM 阅读后通过 Python skill 执行

## 核心设计

### 目录结构

```
skills/
├── git_workflow/                # MD Skill 示例
│   ├── skill.md                 # 技能主文档
│   ├── scripts/                 # 可执行脚本（可选）
│   ├── templates/               # 模板文件（可选）
│   └── resources/               # 其他资源（可选）
└── file/                        # Python Skill
    └── skill.py
```

### Workspace 结构

```
workspace_root/
├── SKILLS/                      # MD Skill 副本目录
│   └── git_workflow/
│       └── skill.md
└── {user_session_id}/
    └── ...
```

## MD Skill 文件格式

### skill.md 结构（行业标准：Claude Code / OpenSkills）

```markdown
---
name: git-workflow
description: Git 工作流指南，包括初始化仓库、提交更改、创建分支、合并代码、查看历史、撤销更改等常见操作
license: MIT
---

# Git 工作流指南

## 概述
本技能的简要描述...

## 前置条件
- 需要 Python skills: file
- 其他环境要求...

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

...

---

## Action: 创建新分支

...
```

### Frontmatter 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 技能唯一标识符（小写字母+连字符，如 `git-workflow`） |
| `description` | string | ✅ | 技能描述（用于显示和匹配，1-1024字符） |
| `license` | string | ❌ | 许可证（如 `MIT`, `Apache-2.0`） |
| `version` | string | ❌ | 版本号 |
| `compatibility` | string | ❌ | 环境要求 |
| `allowed-tools` | list | ❌ | 预授权工具列表 |

**重要变更**：
- ❌ **不再支持** `dependencies` 字段：file skill 等基础能力由手工配置
- ❌ **不再支持** `tags` 字段：简化元数据
- ✅ **符合行业标准**：与 Claude Code / OpenSkills 格式一致

### Action 定义规范

- **格式**：`## Action: 操作名称`
- **使用场景**：描述何时使用该操作
- **步骤**：详细的执行步骤（LLM 会按步骤执行）
- **注意事项**：重要的提醒信息

## 核心组件

### 1. MD Parser（`md_parser.py`）

**功能**：
- 解析 Frontmatter 元数据
- 提取 Action 定义
- 生成渐进式披露内容（摘要 + 完整文档）

**主要类**：
- `MDSkillMetadata`：MD skill 元数据
- `MDActionDescriptor`：Action 描述符
- `MDSkillParser`：解析器

### 2. SKILL_REGISTRY 扩展

**新增方法**：
- `set_workspace_skills_dir(skills_dir)`：设置 workspace SKILLS 目录
- `_get_skill_directory(name)`：定位 skill 目录
- `_copy_skill_to_workspace(src, dst)`：复制 skill 到 workspace
- `_try_load_md_document(name)`：加载 MD skill

**修改的方法**：
- `get_skills()`：同时返回 Python mixins 和 MD skills
- `_load_skill()`：优先尝试 Python，然后 MD
- `_get_dependencies(name)`：MD skill 返回空列表（不再支持 dependencies）

### 3. BaseAgent 初始化

**新增功能**：
```python
# workspace_root setter 中自动创建 SKILLS 目录
skills_dir = Path(workspace_root) / "SKILLS"
skills_dir.mkdir(parents=True, exist_ok=True)
SKILL_REGISTRY.set_workspace_skills_dir(skills_dir)
```

### 4. MicroAgent 增强

**新增功能**：
- `_format_md_skills_summary()`：生成 MD skills 摘要
- `_build_system_prompt()`：注入 MD skills 摘要
- `_create_dynamic_class()`：存储 MD skills 元数据到实例

## 工作流程

### 1. 加载流程

```
Profile 声明 skills: ["file", "git-workflow"]
    ↓
SKILL_REGISTRY.get_skills()
    ↓
加载 skills（无依赖自动加载）：
  - 加载 file（Python skill）
  - 加载 git-workflow（MD skill）
    ↓
MD Skill 加载步骤：
  1. 定位目录：agentmatrix/skills/git-workflow/
  2. 解析 skill.md（name, description 字段）
  3. 复制到 workspace/SKILLS/git-workflow/
  4. 缓存元数据到 _md_skills
    ↓
返回结果：
  - python_mixins: [FileSkillMixin]
  - md_skills: [git_workflow_metadata]
```

### 2. Prompt 注入流程

```
MicroAgent 创建时
    ↓
_create_dynamic_class(available_skills)
    ↓
type('DynamicAgent_Mark',
     (MicroAgent, FileSkillMixin),
     {'_md_skills': [git_workflow_metadata]})
    ↓
_build_system_prompt()
    ↓
生成 System Prompt：
  - Persona
  - Python actions（来自 action_registry）
  - MD skills 摘要
    - **git-workflow**: ...
      完整文档: SKILLS/git-workflow/skill.md
  - 黄页
```

### 3. LLM 使用流程

```
User: "帮我初始化一个 Git 仓库"
    ↓
LLM 思考：
  - 回忆 system prompt 中的 "Git 工作流指南"
  - 需要 "初始化 Git 仓库" 操作
    ↓
LLM 执行：
  1. 读取完整文档：
     file.read("SKILLS/git-workflow/skill.md")
    ↓
  2. 阅读步骤：
     - git init
     - git add .
     - git commit -m "..."
    ↓
  3. 通过 file skill 执行：
     file.bash("git init")
     file.bash("git add .")
     file.bash('git commit -m "Initial commit"')
```

## 使用示例

### 创建 MD Skill

1. **创建 skill 目录**（使用小写+连字符）：
   ```bash
   mkdir -p src/agentmatrix/skills/my-guide
   ```

2. **编写 skill.md**（使用行业标准格式）：
   ```markdown
   ---
   name: my-guide
   description: 我的操作指南，帮助完成 XXX 任务
   license: MIT
   ---

   # 我的操作指南

   ## Action: 第一步

   **使用场景**：...

   **步骤**：
   1. 执行命令：`xxx`
   ```

3. **在 Profile 中声明**（同时声明 Python 和 MD skills）：
   ```yaml
   name: MyAgent
   skills:
     - file
     - my-guide
   ```

### 依赖管理

**重要变更**：MD skill **不再支持** `dependencies` 字段。

所有依赖的 Python skills（如 `file`, `browser`）需要在 Profile 中**手工配置**：

```yaml
# Profile 配置
name: MyAgent
skills:
  - file        # 手工声明依赖的 Python skill
  - my-guide    # MD skill（不再自动加载依赖）
```

**优势**：
- ✅ 更简单：无需复杂的依赖解析
- ✅ 更明确：Profile 中清晰展示所有可用能力
- ✅ 符合行业标准：与 Claude Code / OpenSkills 一致

## 测试

运行测试验证功能：

```bash
python tests/test_md_skill.py
```

测试覆盖：
1. ✅ MD Parser 解析功能（name, description 字段）
2. ✅ SKILL_REGISTRY 加载（无依赖自动加载）
3. ✅ System Prompt 注入
4. ✅ 目录命名规范（小写+连字符）

## 关键实现细节

### 1. YAML 解析

**不依赖 PyYAML**，使用简化解析器：
- 支持单行列表：`allowed-tools: [Read, Bash]`
- 支持多行列表：
  ```yaml
  allowed-tools:
    - Read
    - Bash
  ```
- 支持字符串引号：`"value"` 或 `'value'`

### 2. 文件复制优化

**缓存机制**：
```python
# 检查修改时间
if dst_mtime >= src_mtime:
    return  # 跳过复制
```

**优势**：
- 避免重复复制
- 加载速度更快
- 支持热更新（删除旧版本即可触发重新复制）

### 3. 渐进式披露（Progressive Disclosure）

**System Prompt 中只包含摘要**：
```
### 文档化技能（操作指南）

- **git-workflow**: Git 工作流指南，包括初始化仓库、提交更改...
  完整文档: SKILLS/git-workflow/skill.md
  包含操作: 初始化 Git 仓库, 创建新分支, 提交更改...
```

**LLM 按需读取**：
```
LLM: "需要初始化 Git 仓库"
  → file.read("SKILLS/git-workflow/skill.md")
  → 阅读完整文档
  → 执行操作
```

**优势**：
- 节省 token（摘要 < 100 字符，完整文档可能 > 5000 字符）
- LLM 只在需要时读取详细内容
- 支持大型技能库（不会让 prompt 爆炸）

### 4. 目录命名规范

**行业标准**：小写字母 + 连字符（kebab-case）

```
✅ 正确：
  git-workflow
  pdf-processing
  code-review

❌ 错误：
  git_workflow    # 下划线
  GitWorkflow     # 大写
  git workflow    # 空格
```

**原因**：
- 符合 Claude Code / OpenSkills 标准
- 与 URL、Docker 镜像命名一致
- 避免跨平台路径问题

## 已知限制和未来改进

### 当前限制

1. **LLM 理解准确性**：LLM 可能误解操作步骤（需要清晰的文档编写）
2. **版本管理**：复制后如何更新（目前通过修改时间检测）
3. **无依赖验证**：MD skill 依赖 Python skill（如 file），但不会自动验证是否加载

### 未来改进

1. **依赖验证（可选）**：
   ```yaml
   # skill.md
   ---
   name: my-guide
   description: ...
   requires: [file, browser]  # 可选：声明依赖，仅作提示
   ---
   ```

   ```python
   # 在 Profile 加载时验证
   profile_skills = ["file", "my-guide"]
   required = my_guide_metadata.requires
   for dep in required:
       if dep not in profile_skills:
           logger.warning(f"⚠️  缺少依赖: {dep}")
   ```

2. **技能更新机制**：
   ```python
   # 添加 --refresh-skills 命令
   async def refresh_skills():
       """强制重新复制所有 skills"""
       for skill_name in md_skills:
           src = locate_skill(skill_name)
           dst = workspace / "SKILLS" / skill_name
           shutil.rmtree(dst)
           shutil.copytree(src, dst)
   ```

3. **技能搜索和索引**：
   ```python
   # 基于标签和描述搜索技能
   def search_skills(query: str, tags: List[str] = None):
       """搜索相关的 MD skills"""
       results = []
       for skill in md_skills:
           if query.lower() in skill.display_name.lower():
               results.append(skill)
       return results
   ```

## 示例：完整的 Git Workflow Skill

参考文件：`src/agentmatrix/skills/git-workflow/skill.md`

**Frontmatter**：
```yaml
---
name: git-workflow
description: Git 工作流指南，包括初始化仓库、提交更改、创建分支、合并代码、查看历史、撤销更改等常见操作
license: MIT
---
```

**包含的操作**：
1. 初始化 Git 仓库
2. 创建新分支
3. 提交更改
4. 合并分支
5. 查看历史记录
6. 撤销更改

**使用场景**：
- Agent 需要管理代码版本
- 多人协作开发
- 代码审查流程

## 总结

Markdown Skill 系统为 AgentMatrix 提供了一种灵活的方式来扩展 Agent 能力：

**优势**：
- ✅ 无需编写代码
- ✅ 易于维护和更新
- ✅ 渐进式披露节省 token
- ✅ 符合行业标准（Claude Code / OpenSkills）
- ✅ 统一的加载机制

**适用场景**：
- 操作指南（如 Git 工作流）
- 流程文档（如 CI/CD 流程）
- 最佳实践（如代码审查）
- 工具使用（如 Docker 命令）

**Python vs MD Skills**：
- **Python Skills**：底层能力（bash、file、browser）
- **MD Skills**：操作指南（如何使用底层能力完成复杂任务）

**行业标准对齐**：
- ✅ 使用 `name` + `description` 格式
- ✅ 目录命名使用 kebab-case（小写+连字符）
- ✅ 不再支持 `dependencies` 字段（由手工配置）
- ✅ 简化元数据，只保留核心字段
