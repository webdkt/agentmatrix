# 配置文件

AgentMatrix Desktop 使用多个配置文件存储设置。了解它们的位置和格式有助于排查问题和进行高级自定义。

## 应用级配置

### `~/.agentmatrix/settings.json`

此文件存储桌面应用的核心设置。首次运行向导完成时会自动创建。

**位置**：`~/.agentmatrix/settings.json`（在您的主目录中）

**格式**：JSON

**字段**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `matrix_world_path` | string | `"~/MatrixWorld"` | Matrix World 工作空间目录路径 |
| `auto_start_backend` | boolean | `true` | 是否在应用启动时自动启动 Python 后端 |
| `enable_notifications` | boolean | `true` | 是否显示桌面通知 |
| `log_level` | string | `"INFO"` | 日志详细级别（DEBUG, INFO, WARNING, ERROR） |

**示例**：

```json
{
  "matrix_world_path": "~/MatrixWorld",
  "auto_start_backend": true,
  "enable_notifications": true,
  "log_level": "INFO"
}
```

## Matrix World 配置

以下所有文件位于您的 Matrix World 目录下的 `.matrix/configs/` 中。

### `system_config.yml`

基本系统身份设置。

**位置**：`.matrix/configs/system_config.yml`

**格式**：YAML

**字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_agent_name` | string | 您在系统中的显示名称 |
| `matrix_version` | string | Matrix World 格式版本 |
| `description` | string | 此 Matrix World 实例的描述 |
| `timezone` | string | 时间戳的时区（如 "UTC"、"Asia/Shanghai"） |

**示例**：

```yaml
user_agent_name: "Alice"
matrix_version: "1.0.0"
description: "AgentMatrix World"
timezone: "Asia/Shanghai"

proxy:
  enabled: false
  host: "127.0.0.1"
  port: 7890
```

**代理字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `proxy.enabled` | boolean | 是否通过代理路由 HTTP 流量 |
| `proxy.host` | string | 代理服务器主机名或 IP 地址 |
| `proxy.port` | number | 代理服务器端口号 |

启用后，代理设置会影响：
- LLM API 调用（通过 `HTTP_PROXY` / `HTTPS_PROXY` 环境变量）
- LLM 连接验证测试
- 智能体容器（使用容器特定的主机名映射：Podman 用 `host.containers.internal`，Docker 用 `host.docker.internal`）

### `matrix_config.yml`

系统级操作设置，包括容器运行时和邮件代理。

**位置**：`.matrix/configs/matrix_config.yml`

**格式**：YAML

**字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_agent_name` | string | 您的显示名称 |
| `matrix_version` | string | Matrix 版本标识符 |
| `container.runtime` | string | 容器运行时："auto"、"podman" 或 "docker" |
| `container.auto_start` | boolean | 启动时自动启动容器 |
| `container.fallback_strategy` | string | 首选运行时不可用时的策略（"fallback"） |
| `email_proxy.enabled` | boolean | 启用邮件代理桥接 |
| `email_proxy.matrix_mailbox` | string | Matrix 系统邮箱地址 |
| `email_proxy.user_mailbox` | string | 您的邮箱地址 |

**示例**：

```yaml
user_agent_name: "Alice"
matrix_version: "1.0.0"
description: "AgentMatrix World"
timezone: "UTC"

container:
  runtime: "auto"
  auto_start: true
  fallback_strategy: "fallback"

email_proxy:
  enabled: false
  matrix_mailbox: ""
  user_mailbox: ""
```

### `email_proxy_config.yml`

专用的邮件代理 IMAP/SMTP 设置。

**位置**：`.matrix/configs/email_proxy_config.yml`

**格式**：YAML

**字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | boolean | 启用邮件代理 |
| `matrix_mailbox` | string | Matrix 系统邮箱地址 |
| `user_mailbox` | string | 您的邮箱地址 |
| `imap.host` | string | IMAP 服务器主机名 |
| `imap.port` | number | IMAP 服务器端口（通常为 993） |
| `imap.user` | string | IMAP 登录用户名 |
| `imap.password` | string | IMAP 登录密码 |
| `smtp.host` | string | SMTP 服务器主机名 |
| `smtp.port` | number | SMTP 服务器端口（通常为 587） |
| `smtp.user` | string | SMTP 登录用户名 |
| `smtp.password` | string | SMTP 登录密码 |

**示例**：

```yaml
enabled: false
matrix_mailbox: "matrix@example.com"
user_mailbox: "alice@example.com"
imap:
  host: "imap.gmail.com"
  port: 993
  user: "alice@gmail.com"
  password: "your-app-password"
smtp:
  host: "smtp.gmail.com"
  port: 587
  user: "alice@gmail.com"
  password: "your-app-password"
```

### `llm_config.json`

AI 模型端点配置。

**位置**：`.matrix/configs/llm_config.json`

**格式**：JSON

包含每个已配置 LLM/SLM 的条目。每个条目包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 配置名称（如 "default_llm"） |
| `model_name` | string | 模型标识符 |
| `api_key` | string | 提供商 API 密钥 |
| `base_url` | string | API 端点 URL |
| `description` | string | 人类可读的描述 |

### 智能体配置文件

各个智能体的定义存储为 `.matrix/configs/agents/` 中的 YAML 文件。

**位置**：`.matrix/configs/agents/<agent_name>.yml`

**格式**：YAML

**字段**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 智能体显示名称 |
| `description` | string | 智能体的功能 |
| `class_name` | string | 智能体类（决定行为模式） |
| `backend_model` | string | 使用的 LLM 配置（如 "default_llm"） |
| `skills` | list | 智能体可以使用的技能名称列表 |
| `persona` | string | 智能体的性格和角色定义 |

**示例**（`mark.yml`）：

```yaml
name: "mark"
description: "网络研究和 OSINT 专家"
class_name: agentmatrix.agents.base.BaseAgent
backend_model: default_llm
skills:
  - file
  - web_search
persona: |
  你是一位专业的 OSINT 研究员。你的工作是从网络上
  找到准确、来源可靠的信息。
```

### 系统提示词模板

**位置**：`.matrix/configs/prompts/system_prompt.md`

定义所有智能体运行时提示词的模板文件。它使用模板变量如 `$persona`、`$agent_name`、`$user_name` 和 `$actions_list`，在运行时填充。

除非您想更改所有智能体处理信息的基本行为，否则通常不需要修改此文件。

## 文件总览

| 文件 | 位置 | 用途 |
|------|------|------|
| 应用设置 | `~/.agentmatrix/settings.json` | 桌面应用配置 |
| 系统配置 | `.matrix/configs/system_config.yml` | 系统身份和代理设置 |
| Matrix 配置 | `.matrix/configs/matrix_config.yml` | 操作设置 |
| 邮件代理配置 | `.matrix/configs/email_proxy_config.yml` | IMAP/SMTP 设置 |
| LLM 配置 | `.matrix/configs/llm_config.json` | AI 模型端点 |
| 智能体配置 | `.matrix/configs/agents/*.yml` | 智能体定义 |
| 系统提示词 | `.matrix/configs/prompts/system_prompt.md` | 运行时提示词模板 |
