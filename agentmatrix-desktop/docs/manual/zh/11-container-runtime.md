# 容器运行时

AgentMatrix 使用容器技术在隔离环境中运行 AI 智能体。这确保了安全性、一致性和适当的资源管理。

## 支持的运行时

| 运行时 | 状态 | 说明 |
|--------|------|------|
| **Podman** | 首选 | 默认无根模式，安全性能更好 |
| **Docker** | 支持 | 广泛可用，完全兼容 |

## 自动检测

启动时，AgentMatrix 自动检测系统上可用的容器运行时：

1. 首先检查 **Podman**
2. 如果未找到 Podman，回退到 **Docker**
3. 如果两者都未找到，显示通知

检测顺序和回退行为可在 `matrix_config.yml` 中配置：

```yaml
container:
  runtime: "auto"        # "auto"、"podman" 或 "docker"
  auto_start: true
  fallback_strategy: "fallback"
```

## macOS 设置

在 macOS 上，AgentMatrix 包含捆绑的 Podman 安装程序资源：

- 位于应用的资源目录中
- 当系统未安装 Podman 时使用
- 首次运行时应用可能会提示您安装 Podman

### 手动安装 Podman (macOS)

```bash
# 使用 Homebrew
brew install podman

# 初始化并启动 Podman 虚拟机
podman machine init
podman machine start
```

## Windows 设置

在 Windows 上，AgentMatrix 可以捆绑 Podman MSI 安装程序。手动安装：

1. 从 [官方网站](https://podman.io/) 下载 Podman
2. 运行安装程序
3. 打开终端运行 `podman machine init` 然后 `podman machine start`

Docker Desktop 在 Windows 上也完全支持。

## Linux 设置

在 Linux 上，通过包管理器安装：

```bash
# Debian/Ubuntu
sudo apt install podman

# Fedora
sudo dnf install podman

# Arch
sudo pacman -S podman
```

Docker 在 Linux 发行版上也可广泛使用。

## 验证容器运行时

验证您的容器运行时是否正常工作：

```bash
# 检查 Podman
podman run hello-world

# 检查 Docker
docker run hello-world
```

如果 hello-world 容器成功运行，说明您的运行时配置正确。

## 为什么使用容器？

AgentMatrix 在容器中运行智能体有几个原因：

- **隔离** —— 每个智能体在自己的环境中运行，防止相互干扰
- **安全** —— 智能体不能直接访问宿主文件系统（只能通过配置的挂载）
- **可复现** —— 每个智能体获得一致的运行时环境
- **资源控制** —— 容器资源限制防止失控进程
