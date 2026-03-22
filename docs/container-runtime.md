# Container Runtime Abstraction - 容器运行时抽象层

## 概述

AgentMatrix 现在支持多种容器运行时，包括 Docker 和 Podman。通过统一的抽象层，系统可以自动检测并使用可用的运行时，无需修改现有代码。

## 特性

- ✅ **多运行时支持**：支持 Docker 和 Podman
- ✅ **自动检测**：自动检测可用的运行时（Podman 优先）
- ✅ **向后兼容**：现有代码无需修改
- ✅ **配置驱动**：通过配置文件或环境变量控制
- ✅ **统一接口**：屏蔽不同运行时的 API 差异

## 快速开始

### 1. 安装依赖

#### 使用 Docker（默认）

```bash
# Docker SDK 已包含在主依赖中
pip install -r requirements.txt
```

#### 使用 Podman

```bash
# 安装 Podman Python SDK
pip install -r requirements-podman.txt

# 或手动安装
pip install podman
```

### 2. 安装容器运行时

#### macOS

```bash
# 安装 Podman（推荐）
brew install podman

# 或安装 Docker Desktop
# 下载：https://www.docker.com/products/docker-desktop/
```

#### Linux

```bash
# Debian/Ubuntu
sudo apt update
sudo apt install podman

# Fedora
sudo dnf install podman

# 或安装 Docker
curl -fsSL https://get.docker.com | sh
```

#### Windows

```bash
# 安装 Podman（推荐）
# 下载：https://podman.io/getting-started/installation

# 或安装 Docker Desktop
# 下载：https://www.docker.com/products/docker-desktop/
```

### 3. 配置

编辑 `workspace/config/matrix_config.yml`：

```yaml
container:
  # 运行时类型：auto（自动检测）、docker、podman
  runtime: "auto"

  # 是否自动启动运行时
  auto_start: true

  # 降级策略：fallback（尝试其他运行时）、error（直接报错）
  fallback_strategy: "fallback"
```

### 4. 使用

#### 自动检测（推荐）

```python
from agentmatrix.core.container import ContainerRuntimeFactory

# 自动检测可用运行时（Podman 优先）
adapter = ContainerRuntimeFactory.create()
```

#### 指定运行时

```python
# 强制使用 Docker
adapter = ContainerRuntimeFactory.create(runtime_type='docker')

# 强制使用 Podman
adapter = ContainerRuntimeFactory.create(runtime_type='podman')
```

#### 通过环境变量

```bash
# 设置环境变量
export CONTAINER_RUNTIME=podman

# 代码中自动使用
adapter = ContainerRuntimeFactory.create()
```

## 配置选项

### 运行时类型（runtime）

- `auto`：自动检测（Podman 优先，Docker 次之）
- `docker`：强制使用 Docker
- `podman`：强制使用 Podman

### 自动启动（auto_start）

- `true`：运行时未启动时自动尝试启动
- `false`：不自动启动，手动启动运行时

### 降级策略（fallback_strategy）

- `fallback`：首选运行时不可用时，尝试使用其他运行时
- `error`：首选运行时不可用时，直接抛出错误

## 环境变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `CONTAINER_RUNTIME` | 指定运行时类型 | `docker`, `podman`, `auto` |
| `CONTAINER_AUTO_START` | 是否自动启动 | `true`, `false` |

## API 参考

### ContainerRuntimeFactory

运行时工厂，负责创建适配器实例。

```python
class ContainerRuntimeFactory:
    PRIORITY = ['podman', 'docker']  # 优先级顺序

    @staticmethod
    def create(runtime_type: str = None, logger: Logger = None) -> ContainerAdapter:
        """创建容器运行时适配器"""

    @staticmethod
    def is_docker_available(logger: Logger = None) -> bool:
        """检查 Docker 是否可用"""

    @staticmethod
    def is_podman_available(logger: Logger = None) -> bool:
        """检查 Podman 是否可用"""

    @staticmethod
    def get_available_runtimes(logger: Logger = None) -> list:
        """获取所有可用的运行时列表"""
```

### ContainerAdapter

容器运行时统一接口。

```python
class ContainerAdapter(ABC):
    def ping(self) -> bool:
        """测试连接"""

    def ensure_running(self) -> bool:
        """确保运行时已启动"""

    def create_container(self, name, image, volumes, **kwargs) -> ContainerHandle:
        """创建容器"""

    def get_container(self, name) -> Optional[ContainerHandle]:
        """获取已存在的容器"""

    def close(self):
        """关闭连接"""
```

### ContainerHandle

容器对象抽象。

```python
class ContainerHandle(ABC):
    def start(self):
        """启动容器"""

    def stop(self, timeout: int = 5):
        """停止容器"""

    def pause(self):
        """暂停容器"""

    def unpause(self):
        """恢复容器"""

    def reload(self):
        """刷新状态"""

    def exec_run(self, cmd: str, **kwargs) -> Tuple[int, bytes]:
        """执行命令"""

    @property
    def status(self) -> str:
        """获取状态"""

    @property
    def short_id(self) -> str:
        """获取短ID"""

    def remove(self):
        """删除容器"""
```

## 兼容性说明

### API 差异处理

| 特性 | Docker | Podman | 兼容性处理 |
|------|--------|--------|-----------|
| `short_id` | `container.short_id` | `container.attrs['Id'][:12]` | `ContainerCompat.get_short_id()` |
| 自动启动 | `open -a Docker` | `podman machine start` | `ensure_running()` 方法 |
| 连接测试 | `client.ping()` | `client.ping()` 或 `client.version()` | 统一 `ping()` 方法 |

### 卷挂载格式

两种运行时使用相同的卷挂载格式：

```python
volumes = {
    '/host/path': {
        'bind': '/container/path',
        'mode': 'rw'  # 或 'ro'
    }
}
```

## 迁移指南

### 从旧代码迁移

现有代码无需修改！`DockerContainerManager` 现在是兼容层，内部使用新的抽象层。

```python
# 旧代码（仍然有效）
from agentmatrix.core.docker_manager import DockerContainerManager

manager = DockerContainerManager(
    agent_name="my_agent",
    workspace_root=Path("/workspace")
)
```

### 使用新 API（推荐）

```python
# 新代码（推荐）
from agentmatrix.core.container import ContainerManager

manager = ContainerManager(
    agent_name="my_agent",
    workspace_root=Path("/workspace"),
    runtime_type='auto'  # 或 'docker', 'podman'
)
```

## 故障排除

### 问题：找不到可用的运行时

**错误信息**：`ContainerRuntimeNotFoundError: 未找到可用的容器运行时`

**解决方案**：

1. 检查是否安装了 Docker 或 Podman
2. 确保运行时已启动
3. 检查环境变量 `CONTAINER_RUNTIME`

```bash
# 检查 Docker
docker ps

# 检查 Podman
podman ps

# 启动 Docker（macOS）
open -a Docker

# 启动 Podman（macOS）
podman machine start
```

### 问题：Podman SDK 未安装

**错误信息**：`Podman Python SDK 未安装`

**解决方案**：

```bash
pip install podman
```

### 问题：Docker 连接失败

**错误信息**：`Docker 连接失败`

**解决方案**：

1. 确保 Docker Desktop 已启动
2. 检查 Docker daemon 是否运行
3. 尝试使用 Podman 作为替代

## 性能对比

| 特性 | Docker | Podman |
|------|--------|--------|
| 启动速度 | 较慢 | 较快 |
| 内存占用 | 较高 | 较低 |
| Windows 支持 | 需要 WSL2 | 原生支持 |
| 安全性 | 需要 daemon | 无守护进程 |
| 兼容性 | 广泛 | 90%+ 兼容 Docker API |

## 最佳实践

1. **开发环境**：使用 Podman（更轻量、更安全）
2. **生产环境**：使用 Docker（更成熟、更广泛）
3. **Windows 环境**：优先使用 Podman（更好的原生支持）
4. **自动化测试**：使用 `runtime: auto` 实现运行时无关测试

## 贡献

如需添加对其他容器运行时的支持（如 containerd、CRI-O），请参考现有的适配器实现：

1. 继承 `ContainerAdapter` 和 `ContainerHandle`
2. 实现抽象方法
3. 在 `ContainerRuntimeFactory` 中注册
4. 添加兼容性处理（如需要）

## 许可证

MIT License - 详见项目根目录 LICENSE 文件
