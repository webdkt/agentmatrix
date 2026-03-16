# ConfigService

统一的配置管理服务。

## 概述

ConfigService 是 AgentMatrix 配置管理的统一入口，提供类型安全的 CRUD 操作和自动备份机制。

**职责**：
- Agent Profile 管理
- LLM 配置管理
- Email Proxy 配置管理
- 配置验证和自动备份

## 初始化

```python
from agentmatrix.services.config_service import ConfigService
from agentmatrix.core.paths import MatrixPaths

paths = MatrixPaths(matrix_path="./MatrixWorld")
config_service = ConfigService(paths, max_backups=5)
```

**参数**：
- `paths`: MatrixPaths 实例
- `max_backups`: 保留的最大备份数量（默认 5）

## 配置文件路径

| 配置类型 | 路径 | 格式 |
|---------|------|------|
| Agent Profile | `.matrix/configs/agents/{name}.yml` | YAML |
| LLM Config | `.matrix/configs/agents/llm_config.json` | JSON |
| Email Proxy | `.matrix/configs/email_proxy_config.yml` | YAML |

## API 参考

### Agent Profile 管理

**列出所有 Agent**
```python
agents = config_service.list_agents()
# 返回: [{"name": "agent1", "description": "...", "file_path": "..."}]
```

**获取 Agent Profile**
```python
profile = config_service.get_agent_profile("agent_name")
# 返回: 完整的 agent profile 字典
```

**创建 Agent Profile**
```python
profile = {
    "name": "new_agent",
    "description": "Agent 描述",
    "class_name": "agentmatrix.agents.micro_agent.MicroAgent",
    "backend_model": "default_llm",
    "skills": ["base"],
    "persona": {"base": "你是..."},
    "prompts": {"task_prompt": "..."}
}
config_service.create_agent_profile("new_agent", profile)
```

**更新 Agent Profile**
```python
config_service.update_agent_profile("agent_name", updated_profile)
```

**删除 Agent Profile**
```python
config_service.delete_agent_profile("agent_name")
```

### LLM 配置管理

**列出所有 LLM 配置**
```python
models = config_service.list_llm_models()
# 返回: {"default_llm": {...}, "local_llm": {...}}
```

**获取 LLM 配置**
```python
config = config_service.get_llm_model("default_llm")
```

**添加 LLM 配置**
```python
llm_config = {
    "type": "openai",
    "model": "gpt-4o",
    "api_key": "${OPENAI_API_KEY}",
    "temperature": 0.7,
    "max_tokens": 4096
}
config_service.add_llm_model("my_llm", llm_config)
```

**更新 LLM 配置**
```python
config_service.update_llm_model("my_llm", updated_config)
```

**删除 LLM 配置**
```python
config_service.delete_llm_model("my_llm")
# 注意: default_llm 和 default_slm 不能删除
```

**设置默认 LLM**
```python
config_service.set_default_llm("my_llm")
# 将 my_llm 的配置交换到 default_llm
```

**设置默认 SLM**
```python
config_service.set_default_slm("my_slm")
```

### Email Proxy 管理

**获取 Email Proxy 配置**
```python
config = config_service.get_email_proxy_config()
```

**启用 Email Proxy**
```python
config_service.enable_email_proxy()
```

**禁用 Email Proxy**
```python
config_service.disable_email_proxy()
```

**添加用户邮箱**
```python
config_service.add_user_mailbox("user@example.com")
```

**移除用户邮箱**
```python
config_service.remove_user_mailbox("user@example.com")
```

**更新 Email Proxy 配置**
```python
config = {
    "email_proxy": {
        "enabled": True,
        "host": "smtp.example.com",
        "port": 587,
        "username": "user@example.com",
        "password": "${EMAIL_PASSWORD}",
        "user_mailbox": "inbox@example.com"
    }
}
config_service.update_email_proxy_config(config)
```

## 备份机制

ConfigService 在修改配置文件前自动备份：

**备份规则**：
- 自动在修改前备份
- 备份文件命名：`{filename}.bak.{timestamp}.{ext}`
- 时间戳格式：`YYYYMMDD_HHMMSS`
- 保留最近 5 个备份（可通过 `max_backups` 配置）
- 自动清理旧备份

**备份示例**：
```
llm_config.json
llm_config.json.bak.20250316_143022.json
llm_config.json.bak.20250316_135815.json
```

## 使用示例

### 创建新 Agent

```python
from agentmatrix.services.config_service import ConfigService
from agentmatrix.core.paths import MatrixPaths

paths = MatrixPaths(matrix_path="./MatrixWorld")
config_service = ConfigService(paths)

# 创建新 agent profile
profile = {
    "name": "researcher",
    "description": "Research assistant",
    "class_name": "agentmatrix.agents.micro_agent.MicroAgent",
    "backend_model": "default_llm",
    "skills": ["base", "browser"],
    "persona": {
        "base": "你是一个专业的研究助理，擅长信息检索和分析。"
    }
}

config_service.create_agent_profile("researcher", profile)
```

### 管理 LLM 配置

```python
# 添加新的 LLM
local_llm = {
    "type": "openai",
    "model": "qwen2.5",
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama"
}
config_service.add_llm_model("local", local_llm)

# 设置为默认
config_service.set_default_llm("local")
```

### 配置 Email Proxy

```python
# 启用并配置
config_service.enable_email_proxy()
config_service.add_user_mailbox("inbox@example.com")

# 或完整配置
email_config = {
    "email_proxy": {
        "enabled": True,
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "user@gmail.com",
        "password": "${GMAIL_APP_PASSWORD}",
        "user_mailbox": "inbox@gmail.com"
    }
}
config_service.update_email_proxy_config(email_config)
```

## 异常处理

所有方法在失败时抛出标准异常：

- `FileNotFoundError`: 配置文件不存在
- `FileExistsError`: 配置文件已存在
- `KeyError`: LLM 配置不存在
- `ValueError`: 尝试删除必需配置

建议在调用时进行异常处理以确保程序稳定性。
