# 06 — 数据持久化与状态管理

## 数据库能力

### AgentMatrix: 原始 SQLite

`src/agentmatrix/db/agent_matrix_db.py`（~31KB）使用手动建表的 SQLite：

| 表 | 用途 |
|---|---|
| `emails` | 邮件归档 |
| `email_to_deliver` | 待投递队列 |
| `email_to_process` | 待处理队列 |
| `sessions` | 会话元数据 |
| `scheduled_tasks` | 定时任务 |

提供同步和异步（aiosqlite）两种实现。没有全文搜索能力，查询依赖 SQL WHERE 条件。

### Hermes Agent: SQLite + FTS5

`hermes_state.py` 实现了更丰富的数据库层：

- **WAL 模式**：支持并发读 + 单写（gateway 多平台场景关键）
- **FTS5 虚拟表**：跨所有会话消息的全文搜索
- **丰富元数据**：message_count、tool_call_count、input/output tokens、cache tokens、reasoning tokens、cost tracking（estimated_cost_usd、actual_cost_usd）
- **Schema 版本管理**：`SCHEMA_VERSION = 6`，支持升级迁移
- **parent_session_id 链**：压缩触发的会话拆分追踪

### 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **全文搜索** | 无 | FTS5 虚拟表 |
| **并发模式** | aiosqlite（异步） | WAL 模式（并发读+单写） |
| **Token 追踪** | 无 | 完整（input/output/cache/reasoning） |
| **成本追踪** | 无 | estimated + actual cost USD |
| **Schema 版本** | 无 | SCHEMA_VERSION + 迁移 |
| **优势** | 简单、多表分工明确 | 搜索强大、元数据丰富 |
| **劣势** | 查询能力有限 | 单表存储所有消息（大体积风险） |

## 会话管理

### AgentMatrix: SessionManager

AgentMatrix 有显式的会话管理层：

- **内存缓存**：活跃会话保持在内存中
- **邮件-会话映射**：通过 `email_id → session_id` 映射追踪
- **懒加载**：非活跃会话从磁盘加载
- **自动压缩**：基于 token 阈值（默认 32000）和 scratchpad 累积（默认 8 条）触发
- **双视角 Session**：`sender_session_id` 和 `recipient_session_id` 维护各自 Agent 的会话上下文

### Hermes Agent: 对话历史在 Agent Loop 内管理

Hermes 的会话管理嵌入在 `AIAgent` 的对话循环中：

- `messages` 列表在内存中维护当前对话
- 上下文压缩通过 `ContextCompressor` 处理
- 会话通过 `parent_session_id` 链实现拆分
- 没有独立的 SessionManager 抽象

## 配置存储

### AgentMatrix: Content-First 设计

`src/agentmatrix/services/config_service.py`（~50KB）实现了"内容优先"的配置管理：

- **配置类型**：Agent（YAML）、LLM（JSON）、System（YAML）、Email Proxy（YAML）
- **多层验证**：格式 → Schema → 内容 → 运行时
- **自动备份**：保留 5 个版本
- **动态重载**：修改配置后无需重启
- **JSON Schema 发现**：自动从 Pydantic 模型生成 Schema

### Hermes Agent: 多实例 Profile 系统

Hermes 通过 `HERMES_HOME` 环境变量支持多实例隔离：

- 每个 profile 拥有独立的 `~/.hermes/` 目录
- `config.yaml`（~45KB 示例）管理所有设置
- `.env` 管理 API 密钥
- `hermes_cli/config.py`（~138KB）提供配置管理、环境变量、迁移系统
- `hermes_cli/setup.py`（~127KB）提供交互式首次运行配置向导

## 崩溃恢复

### AgentMatrix

- **email_to_deliver / email_to_process 队列**：持久化在数据库中，重启后继续处理
- **TaskScheduler 的 `_check_missed_tasks()`**：检测并补发宕机期间错过的定时任务
- 邮件投递是幂等的，重复投递不会产生副作用

### Hermes Agent

- Hermes 的工具调用在 agent loop 内同步执行，没有显式的崩溃恢复队列
- Gateway 的 SessionStore 可以恢复会话状态
- 没有文档化的 missed-task 恢复机制

## 对比总结

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **数据库能力** | 基础 CRUD | FTS5 搜索 + 丰富元数据 |
| **会话管理** | 显式 SessionManager + 懒加载 | 内嵌于 agent loop |
| **配置管理** | Content-first + 多层验证 + 自动备份 | 多实例 profile + 交互式向导 |
| **崩溃恢复** | 持久化投递/处理队列 | 有限（gateway session 恢复） |
| **优势** | 配置管理成熟、崩溃恢复完整 | 搜索和分析能力强 |
| **劣势** | 缺乏全文搜索和成本追踪 | 配置管理和崩溃恢复较弱 |
