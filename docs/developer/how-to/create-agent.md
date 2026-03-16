# How-To: Create Agent

创建新 Agent 的步骤。

## 步骤

### 1. 创建配置目录

```bash
mkdir -p .matrix/configs/agents/{agent_name}
```

### 2. 编写 Profile

创建 `.matrix/configs/agents/{agent_name}/profile.yml`:

```yaml
name: {agent_name}
description: "Agent 描述"
class_name: "agentmatrix.agents.micro_agent.MicroAgent"
backend_model: default_llm

skills:
  - base
  - browser
  - file

persona:
  base: |
    你是 {agent_name}，一个专业的助手。
    
    你的职责：
    1. 职责1
    2. 职责2
    
    工作原则：
    - 原则1
    - 原则2

prompts:
  task_prompt: |
    任务上下文：{context}
    请处理此任务。
```

### 3. 配置 LLM

确保 `.matrix/configs/agents/llm_config.json` 包含指定后端：

```json
{
  "default_llm": {
    "type": "openai",
    "model": "gpt-4o",
    "api_key": "${OPENAI_API_KEY}"
  }
}
```

### 4. 重启系统

Agent 在系统启动时自动加载。

## 验证

通过 Web UI 或 API 验证：

```bash
curl http://localhost:8000/api/agents
# 应返回包含新 Agent 的列表
```

## 使用 SystemAdmin 创建

让 SystemAdmin Agent 帮你创建：

```
请创建一个名为 DataAnalyzer 的 Agent，
需要文件处理和数据分析能力。
```

SystemAdmin 会：
1. 创建配置文件
2. 设置合适的 skills
3. 编写 persona
4. 自动加载 Agent
