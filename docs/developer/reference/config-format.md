# Config Format

配置文件格式规范。

## Agent Profile

路径：`.matrix/configs/agents/{agent_name}/profile.yml`

```yaml
name: AgentName                      # Agent 唯一标识
description: "Agent 描述"             # 简短描述
class_name: "完整类路径"               # MicroAgent 类路径
backend_model: default_llm           # LLM 后端名称

skills:                              # Skill 列表
  - base
  - browser
  - file

persona:                             # 角色定义
  base: |
    你是 {name}...

prompts:                             # 提示模板
  task_prompt: "..."
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | str | Yes | Agent 名称，唯一标识 |
| `description` | str | Yes | Agent 描述 |
| `class_name` | str | Yes | 完整 Python 类路径 |
| `backend_model` | str | No | LLM 配置名称，默认 default_llm |
| `skills` | list | No | Skill 名称列表 |
| `persona.base` | str | Yes | 系统角色定义 |
| `prompts.task_prompt` | str | No | 任务提示模板 |

## LLM Config

路径：`.matrix/configs/agents/llm_config.json`

```json
{
  "default_llm": {
    "type": "openai",
    "model": "gpt-4o",
    "api_key": "${OPENAI_API_KEY}",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "local_llm": {
    "type": "openai",
    "model": "qwen2.5",
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama"
  }
}
```

### 字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `type` | str | Yes | 后端类型: openai, anthropic |
| `model` | str | Yes | 模型名称 |
| `api_key` | str | Yes | API key，支持 `${ENV_VAR}` 格式 |
| `base_url` | str | No | 自定义 API 地址 |
| `temperature` | float | No | 采样温度 |
| `max_tokens` | int | No | 最大 token 数 |

## System Config

路径：`.matrix/configs/system_config.yml`

```yaml
email_proxy:
  enabled: true
  host: smtp.example.com
  port: 587
  username: user@example.com
  password: "${EMAIL_PASSWORD}"
```
