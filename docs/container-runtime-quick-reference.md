# Container Runtime Quick Reference - 容器运行时快速参考

## 快速开始

### 安装

```bash
# Docker（默认）
pip install -r requirements.txt

# Podman（可选）
pip install -r requirements-podman.txt
```

### 配置

```yaml
# workspace/config/matrix_config.yml
container:
  runtime: auto  # auto, docker, podman
  auto_start: true
```

### 使用

```python
# 自动检测（推荐）
from agentmatrix.core.container import ContainerRuntimeFactory
adapter = ContainerRuntimeFactory.create()

# 或使用兼容层（现有代码）
from agentmatrix.core.docker_manager import DockerContainerManager
manager = DockerContainerManager(...)
```

## 常用命令

### 检查运行时状态

```bash
# Docker
docker ps

# Podman
podman ps

# 启动 Docker（macOS）
open -a Docker

# 启动 Podman（macOS）
podman machine start

# 启动 Podman（Linux）
sudo systemctl start podman
```

### 环境变量

```bash
# 指定运行时
export CONTAINER_RUNTIME=podman

# 禁用自动启动
export CONTAINER_AUTO_START=false

# 临时使用特定运行时
CONTAINER_RUNTIME=docker python your_script.py
```

## API 速查

### ContainerRuntimeFactory

```python
# 创建适配器
adapter = ContainerRuntimeFactory.create(runtime_type='auto')

# 检查可用性
is_docker = ContainerRuntimeFactory.is_docker_available()
is_podman = ContainerRuntimeFactory.is_podman_available()

# 获取所有可用运行时
runtimes = ContainerRuntimeFactory.get_available_runtimes()
```

### ContainerAdapter

```python
# 连接测试
adapter.ping()

# 确保运行
adapter.ensure_running()

# 创建容器
container = adapter.create_container(
    name="my_container",
    image="agentmatrix:latest",
    volumes={'/host': {'bind': '/container', 'mode': 'rw'}}
)

# 获取容器
container = adapter.get_container("my_container")

# 关闭连接
adapter.close()
```

### ContainerHandle

```python
# 生命周期
container.start()
container.stop(timeout=5)
container.pause()
container.unpause()
container.remove()

# 执行命令
exit_code, output = container.exec_run("ls -la", demux=True)

# 状态
status = container.status  # 'running', 'paused', etc.
short_id = container.short_id  # 'abc123def456'
attrs = container.attrs  # 完整属性
```

### ContainerManager

```python
from agentmatrix.core.container import ContainerManager

manager = ContainerManager(
    agent_name="my_agent",
    workspace_root=Path("/workspace"),
    runtime_type='auto'
)

# 初始化
manager.initialize_directories()

# 生命周期
manager.wakeup()  # 启动/恢复
manager.hibernate()  # 暂停
manager.stop()  # 停止
manager.remove()  # 删除

# 工作区
manager.switch_workspace("task_123")

# 执行命令
exit_code, stdout, stderr = await manager.exec_command("ls -la")

# 状态
status = manager.get_status()
```

## 故障排除

### 问题：找不到运行时

```python
# 错误：ContainerRuntimeNotFoundError
# 解决：

# 1. 检查安装
docker --version
podman --version

# 2. 检查运行
docker ps
podman ps

# 3. 启动运行时
# macOS
open -a Docker
podman machine start

# Linux
sudo systemctl start docker
sudo systemctl start podman
```

### 问题：SDK 未安装

```python
# 错误：Podman Python SDK 未安装
# 解决：
pip install podman
```

### 问题：权限错误

```bash
# Linux 上 Podman/Docker 权限问题
# 解决：将用户添加到对应组
sudo usermod -aG docker $USER
sudo usermod -aG podman $USER

# 或使用 sudo（不推荐）
sudo python your_script.py
```

## 配置示例

### 开发环境（Podman）

```yaml
container:
  runtime: podman
  auto_start: true
```

### 生产环境（Docker）

```yaml
container:
  runtime: docker
  auto_start: true
```

### 自动检测（推荐）

```yaml
container:
  runtime: auto
  auto_start: true
  fallback_strategy: fallback
```

### 调试模式（手动启动）

```yaml
container:
  runtime: auto
  auto_start: false  # 手动启动运行时
```

## 最佳实践

1. **使用 `runtime: auto`** - 让系统自动选择最佳运行时
2. **启用 `auto_start`** - 减少手动操作
3. **使用 `fallback_strategy: fallback`** - 提高可用性
4. **环境变量用于临时覆盖** - 不要硬编码运行时类型

## 迁移检查清单

从旧代码迁移到新抽象层：

- [ ] 现有测试通过
- [ ] 配置文件更新
- [ ] 环境变量设置（如需要）
- [ ] 文档更新
- [ ] 团队培训

## 参考链接

- [完整文档](container-runtime.md)
- [实施总结](container-runtime-implementation.md)
- [API 参考](../src/agentmatrix/core/container/)
- [测试示例](../tests/)
