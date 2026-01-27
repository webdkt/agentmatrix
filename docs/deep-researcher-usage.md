# Deep Researcher 使用指南

## 概述

Deep Researcher 是一个深度研究技能，可以自动进行网络研究并生成完整的研究报告。

## 核心特性

1. **智能人设生成**：自动生成研究导师和研究员人设
2. **研究计划制定**：使用think-with-retry模式制定详细的研究计划和章节大纲
3. **番茄笔记法**：使用番茄笔记法组织和记录研究发现
4. **MicroAgent架构**：使用MicroAgent递归调用来组织研究流程
5. **自动报告生成**：基于笔记自动生成结构化的研究报告

## 主流程

```
用户输入研究目的
  ↓
1. 初始化研究上下文
  ↓
2. 生成人设（研究导师 + 研究员）
  ↓
3. 制定研究计划（Planning Stage）
   - 研究员起草初步计划
   - 导师review并提供建议
   - 研究员综合意见制定最终计划
  ↓
4. 执行研究循环（Research Loop）
   - 搜索相关信息
   - 浏览网页内容
   - 记录笔记到笔记本
   - 生成页面摘要
  ↓
5. 撰写报告（Writing Loop）
   - 为每个章节撰写草稿
   - 汇总生成完整报告
  ↓
生成最终研究报告文件
```

## 使用方法

### 1. 配置Agent

在agent的profile YAML文件中添加Deep ResearcherMixin：

```yaml
name: MyResearchAgent
description: 一个专业的研究助手
module: agentmatrix.agents.base
class_name: BaseAgent

mixins:
  - agentmatrix.skills.filesystem.FileSkillMixin
  - agentmatrix.skills.web_searcher.WebSearcherMixin
  - agentmatrix.skills.deep_researcher.DeepResearcherMixin

system_prompt: |
  你是一个专业的研究助手。

backend_model: gpt-4
cerebellum_model: gpt-3.5-turbo
```

### 2. 调用研究功能

```python
# 通过Email调用
email = Email(
    sender="user@example.com",
    recipient="MyResearchAgent",
    subject="深度研究请求",
    body="请帮我研究：AI安全领域的最新进展，目的是了解当前的技术挑战和解决方案",
    user_session_id="session_123"
)

await matrix.post_office.send_email(email)
```

### 3. 或直接使用action

```python
result = await agent.deep_research(
    research_title="AI安全研究",
    research_purpose="了解AI安全领域的技术挑战、最新进展和解决方案"
)
```

## 研究输出

研究完成后，会生成以下文件：

```
.matrix/
└── AI安全研究/
    ├── .crawler_assessment.db      # 爬虫评估数据库
    ├── AI安全研究_report.md         # 最终研究报告
    └── downloads/                    # 下载的文件
```

## 报告结构

生成的报告包含：

1. **研究目的**：用户指定的研究需求
2. **章节内容**：根据研究计划自动生成
   - 每个章节基于相关的笔记和摘要
   - 使用番茄笔记法组织信息
3. **Markdown格式**：易于阅读和编辑

## 核心组件

### 1. ResearchContext（研究上下文）

包含研究的所有信息：
- 研究标题和目的
- 人设（导师、研究员）
- 研究计划、章节大纲、关键问题
- 笔记本（Notebook）

### 2. Notebook（笔记本）

使用番茄笔记法：
- 按页组织笔记
- 每页包含多条笔记
- 每条笔记关联到特定章节
- 每页有摘要

### 3. Actions

Deep Researcher提供以下actions：

- `deep_research`：主入口，启动研究
- `take_note`：记录笔记
- `summarize_page`：总结页面
- `check_notebook`：查看笔记本状态

## 配置参数

### Notebook配置

```python
ctx.notebook = Notebook(page_size_limit=2000)  # 每页最大字符数
```

### 研究循环配置

```python
max_steps=20  # 研究循环最大步骤数
```

## 最佳实践

1. **明确研究目的**：提供清晰、具体的研究目的
2. **合理设置步骤**：根据研究复杂度调整max_steps
3. **利用web_searcher**：确保agent配置了web_searcher skill
4. **检查笔记**：定期使用check_notebook查看研究进展

## 技术架构

### 双层架构

- **Planning Stage**：使用MicroAgent制定计划
- **Research Loop**：MicroAgent自主选择action进行研究
- **Writing Loop**：基于笔记生成报告

### Think-With-Retry模式

用于确保输出格式正确：
- 人设生成
- 研究计划制定
- 结构化数据提取

### 文本解析器

- `_simple_section_parser`：单section解析
- `_multi_section_parser`：多section解析

## 依赖关系

Deep Researcher依赖以下模块：

- `agentmatrix.agents.base.BaseAgent`
- `agentmatrix.skills.web_searcher.WebSearcherMixin`
- `agentmatrix.skills.filesystem.FileSkillMixin`

## 注意事项

1. **需要配置backend_model**：确保LLM配置正确
2. **需要web_searcher**：研究功能依赖web_searcher skill
3. **研究时间**：复杂研究可能需要较长时间
4. **步骤限制**：注意max_steps配置，避免无限循环

## 未来改进

- [ ] 支持增量研究（基于已有笔记继续）
- [ ] 支持多源信息聚合
- [ ] 支持自定义报告模板
- [ ] 支持研究过程可视化
- [ ] 支持导出多种格式（PDF、HTML等）

## 相关文档

- [Agent开发指南](agent-developer-guide-cn.md)
- [Agent和Micro Agent设计](agent-and-micro-agent-design-cn.md)
- [Think-With-Retry模式](think-with-retry-pattern-cn.md)
