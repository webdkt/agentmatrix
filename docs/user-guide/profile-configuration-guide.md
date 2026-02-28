# Agent Profile YML 配置指南

## 📋 配置属性分类

### ✅ 必需属性 (Required)

这些属性是 Agent 正常工作所必需的，**必须配置**：

```yaml
name: DeepResearcher              # Agent 名称（必需）
description: 深度研究 Agent        # Agent 描述（必需）
module: agentmatrix.agents.deep_researcher  # 模块路径（必需）
class_name: DeepResearcher         # 类名（必需）
```

### ⭐ 重要可选属性 (Important Optional)

这些属性虽然没有默认值，但对 Agent 功能非常重要，**强烈建议配置**：

```yaml
# 1. Persona 配置（核心！）
persona:                           # Agent 的角色/身份描述（核心配置）
  base: |                          # 基础 persona
    你是谁...
  planner: |                       # 计划阶段的 persona
    你如何规划...
  # 可以定义多个阶段的 persona

# 2. Skills 配置（核心！）
skills:                            # 技能列表（新架构）
  - browser                        # 浏览器技能
  - file                           # 文件操作技能
  - web_search                     # 网络搜索技能

# 3. 后端模型配置
backend_model: default_llm         # 使用的 LLM 模型

# 4. 小脑配置
cerebellum:
  backend_model: mimo              # 小脑模型（用于 action 优化）
```

### 🛠️ 实用可选属性 (Useful Optional)

这些属性根据需要配置，提供额外的功能：

```yaml
# 1. 其他 prompts 配置
prompts:
  task_prompt: |                   # 自定义任务 prompt 模板
    你需要完成以下任务：{task}
  summary_prompt: |                # 自定义总结 prompt
    请总结你的工作

# 2. 视觉大脑（如果需要图片理解）
vision_brain:
  backend_model: gpt-4-vision      # 视觉模型

# 4. 日志配置（调试用）
logging:
  level: DEBUG                     # 日志级别
```

### 🔍 可能冗余的配置 (Potentially Redundant)

这些属性配置了但可能不被使用，**建议清理**：

```yaml
# 以下属性配置了但代码中未读取
system_prompt: |                   # ⚠️ 代码中未使用，实际读取 persona.base
  你是一个助手...

attribute_initializations:         # ⚠️ 某些配置可能不需要
  browser_adapter: null            # 例如：如果已有 browser skill，可能不需要

class_attributes:                  # ⚠️ 某些配置可能不需要
  _custom_log_level: 10            # 例如：可以通过 logging 配置替代
```

## 📝 标准配置模板

### 基础 Agent 模板（BaseAgent）

```yaml
# === 必需配置 ===
name: MyAgent
description: 我的 Agent
module: agentmatrix.agents.base
class_name: BaseAgent

# === 核心配置 ===
persona:
  base: |
    你是一个专业的助手，擅长...

skills:
  - file                          # 文件操作

# === 可选配置 ===
backend_model: default_llm
```

### 深度研究 Agent 模板（DeepResearcher）

```yaml
# === 必需配置 ===
name: DeepResearcher
description: 深度研究 Agent
module: agentmatrix.agents.deep_researcher
class_name: DeepResearcher

# === 核心配置 ===
persona:
  base: |
    # 你是谁
    你是深度研究员，擅长自主探索、分析和综合信息。

  planner: |
    # 计划阶段 persona
    你需要制定详细的研究计划...

  researcher: |
    # 研究阶段 persona
    你需要执行深度研究...

  writer: |
    # 写作阶段 persona
    你需要撰写研究报告...

skills:
  - browser                       # 浏览器技能
  - file                          # 文件操作技能
  - web_search                    # 网络搜索技能

# === 可选配置 ===
backend_model: default_llm
cerebellum:
  backend_model: mimo
```

## 🎯 配置决策指南

### 何时使用 `attribute_initializations`？

仅在以下情况使用：
- 需要在初始化时设置特定的实例属性
- 属性值不能通过其他方式配置

大多数情况下不需要，例如：
- ❌ `browser_adapter: null` - 如果已有 browser skill，不需要
- ❌ `default_search_engine` - 如果通过 browser skill 配置，不需要

### 何时使用 `class_attributes`？

仅在以下情况使用：
- 需要修改类的行为（如日志级别）

大多数情况下可以通过 `logging` 配置替代：
```yaml
# 推荐方式
logging:
  level: DEBUG

# 而不是
class_attributes:
  _custom_log_level: 10
```

## 🔧 配置清理建议

### 检查并清理

1. **检查 `attribute_initializations`**：
   - 如果配置了 `browser_adapter: null`，考虑删除（已有 browser skill）
   - 如果配置了 `default_search_engine`，检查是否确实需要

2. **检查 `class_attributes`**：
   - 如果是 `_custom_log_level`，改用 `logging.level`

### 保留（低优先级）

1. **`cerebellum` 配置** - 如果需要 action 优化，保留
2. **`vision_brain` 配置** - 如果需要图片理解，保留

## 📊 配置对照表

| 配置项 | 状态 | 推荐使用 | 默认值 | 说明 |
|--------|------|----------|--------|------|
| `name` | ✅ 必需 | - | - | Agent 名称 |
| `description` | ✅ 必需 | - | - | Agent 描述 |
| `module` | ✅ 必需 | - | - | 模块路径 |
| `class_name` | ✅ 必需 | - | - | 类名 |
| `persona` | ⭐ 重要 | ✅ 使用 | `{"base":""}` | Agent 角色 |
| `skills` | ⭐ 重要 | ✅ 使用 | `[]` | 技能列表 |
| `backend_model` | 🛠️ 可选 | ✅ 使用 | `"default_llm"` | 后端模型 |
| `cerebellum` | 🛠️ 可选 | ✅ 使用 | - | 小脑配置 |
| `prompts` | 🛠️ 可选 | ✅ 使用 | `{}` | 其他 prompts |
| `vision_brain` | 🛠️ 可选 | 按需 | - | 视觉模型 |
| `logging` | 🛠️ 可选 | 按需 | - | 日志配置 |
| `attribute_initializations` | ⚠️ 冗余 | 检查 | - | 可能不需要 |
| `class_attributes` | ⚠️ 冗余 | 检查 | - | 可用 logging 替代 |

## ✅ 最佳实践

1. **使用简洁的配置**：只配置需要的属性
2. **使用 `skills`**：指定要加载的技能
3. **使用 `persona`**：定义 Agent 的角色和行为
4. **参考模板**：使用标准模板作为起点

---

**文档版本**: 1.0
**最后更新**: 2025-02-21
**状态**: ✅ 当前有效
