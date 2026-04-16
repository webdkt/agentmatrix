# 05 — 执行环境与隔离

## 容器化策略

### AgentMatrix: 共享单容器模型

AgentMatrix 采用 **"所有 Agent 共享一个 Docker 容器"** 的架构（`docs/core/10-*.md`）：

- 容器内所有 Agent 是独立的 Linux 用户
- 每个 Agent 有独立的 home 目录：`/data/agents/{name}/`
- `~/current_task` 符号链接用于工作空间切换
- 宿主机-容器通过 volume 映射共享文件

容器管理通过 `ContainerAdapter` 抽象层（`src/agentmatrix/core/container/`）：
- `DockerHandle`：Docker 实现
- `PodmanHandle`：Podman 实现
- `ContainerCompat`：兼容性层

File Skill 的操作在容器内执行，每个 Agent 只能访问自己的 home 目录和共享的工作空间。

### Hermes Agent: 6 种执行后端

Hermes 在 `tools/environments/` 下实现了 6 种终端执行后端：

| 后端 | 文件 | 适用场景 |
|------|------|----------|
| Local | `local.py` | 本地 shell 直接执行 |
| Docker | `docker.py` | Docker 容器内执行 |
| SSH | `ssh.py` | 远程 SSH 执行 |
| Modal | `modal.py` | Modal serverless 执行 |
| Daytona | `daytona.py` | Daytona 开发环境 |
| Singularity | `singularity.py` | Singularity 容器（HPC 场景） |

用户可以根据场景选择后端，同一个 Agent 可以在不同后端之间切换。

## 对比

| 维度 | AgentMatrix | Hermes Agent |
|------|-------------|--------------|
| **隔离粒度** | 容器内按 Linux 用户隔离 | 按执行后端隔离（整个容器/环境） |
| **容器数量** | 1 个共享容器 | 每个后端独立 |
| **多后端支持** | Docker + Podman | 6 种（含 serverless、HPC） |
| **文件系统隔离** | 共享容器 FS + 按用户 home 目录 | 按后端决定（local 无隔离，Docker 完全隔离） |
| **Agent 切换工作空间** | `~/current_task` 符号链接 | 不适用（单 Agent） |
| **优势** | 轻量（一个容器）、Agent 间可共享文件 | 灵活（多种环境可选） |
| **劣势** | 隔离不如多容器彻底 | 多后端增加运维复杂度 |

## 资源管理

### AgentMatrix

- **PowerManager**：管理 Agent 的启动/停止/重启
- **ServiceMonitor**：监控后台服务健康状态
- 容器资源限制通过 Docker 配置（CPU/内存限制）

### Hermes Agent

- 终端工具支持环境持久化（`is_persistent_env()` 检查）
- `cleanup_vm()` 清理执行环境
- `cleanup_browser()` 清理浏览器资源
- 没有统一的资源管理抽象层

## 对比总结

AgentMatrix 选择了**简单但统一**的执行模型——一个容器、按用户隔离，适合"数字办公室"的多 Agent 场景。Hermes 选择了**灵活但分散**的执行模型——多种后端可选，适合需要适配不同部署环境的单一 Agent 场景。

如果 AgentMatrix 要扩展执行环境选择，可以参考 Hermes 的 `ContainerAdapter` 模式扩展更多后端。如果 Hermes 要支持多 Agent 共享执行环境，可以参考 AgentMatrix 的按用户隔离方案。
