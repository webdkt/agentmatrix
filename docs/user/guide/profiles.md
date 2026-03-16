# Profile Configuration

Agent Profile 配置说明。

## Profile 结构

每个 Agent 一个目录：

```
.matrix/configs/agents/{agent_name}/
└── profile.yml
```

## 配置字段

```yaml
name: AgentName
description: "Agent 描述"
class_name: "agentmatrix.agents.micro_agent.MicroAgent"
backend_model: default_llm

skills:
  - base
  - browser
  - file

persona:
  base: |
    你是 {name}...

prompts:
  task_prompt: "..."
```

## 字段说明

### name

Agent 唯一标识符。

### class_name

Agent 类的完整 Python 路径：
- 标准：`agentmatrix.agents.micro_agent.MicroAgent`
- 自定义：`my_package.MyAgent`

### backend_model

LLM 后端名称，对应 `llm_config.json` 中的 key。

### skills

Skill 列表。常用 Skills：

| Skill | 功能 |
|-------|------|
| base | 基础功能（时间、提问） |
| browser | 浏览器控制 |
| file | 文件操作 |
| email | 发送邮件 |
| memory | 知识库查询 |
| scheduler | 定时任务 |

### persona.base

定义 Agent 的角色和行为准则。支持多角色：

```yaml
persona:
  base: |
    你是助手...
  expert: |
    你是专家...
```

Agent 通过 `set_persona(role)` 切换角色。

### prompts.task_prompt

任务提示模板，可用变量：
- `{context}`: 任务上下文
- `{history}`: 对话历史

## 示例

```yaml
name: DataAnalyst
description: "数据分析专家"
class_name: "agentmatrix.agents.micro_agent.MicroAgent"
backend_model: default_llm

skills:
  - base
  - file
  - simple_web_search

persona:
  base: |
    你是 DataAnalyst，专业的数据分析助手。
    
    职责：
    1. 分析 CSV/Excel 数据
    2. 生成数据报告
    3. 提供数据洞察
    
    原则：
    - 先检查数据质量
    - 提供可验证的结论
    - 用清晰的格式呈现结果
```
