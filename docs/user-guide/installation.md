# AgentMatrix 安装指南

## 前置要求

- Docker Desktop（Mac/Windows）或 Docker Engine（Linux）
- Python 3.12+
- 4GB+ 可用内存

## 步骤 1：安装 Docker

### Mac

1. 下载 [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
2. 安装并启动 Docker Desktop

### Linux

```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker
```

## 步骤 2：克隆项目

```bash
git clone https://github.com/your-org/agentmatrix.git
cd agentmatrix
```

## 步骤 3：构建镜像

```bash
docker build -t agentmatrix:latest .
```

这一步会：
- 拉取 Python 3.12 基础镜像
- 安装 bash, curl, git 等基础工具
- 安装 Docker SDK
- 创建必要的目录结构（/skills, /home, /workspace）

## 步骤 4：验证安装

```bash
# 检查镜像
docker images | grep agentmatrix

# 测试容器
docker run --rm agentmatrix:latest python --version
docker run --rm agentmatrix:latest bash -c "which bash curl git"
```

预期输出：
```
Python 3.12.x
/bin/bash
/usr/bin/curl
/usr/bin/git
```

## 步骤 5：安装 Python 依赖（宿主机）

```bash
pip install -e .
```

这会安装宿主机需要的依赖（如 Playwright、marker-pdf 等）。

## 故障排除

### Docker 未启动

**Mac**：启动 Docker Desktop 应用

**Linux**：
```bash
sudo systemctl start docker
```

### 构建失败

```bash
# 清理 Docker 缓存
docker system prune -a

# 重新构建
docker build --no-cache -t agentmatrix:latest .
```

### 权限问题（Linux）

```bash
# 添加当前用户到 docker 组
sudo usermod -aG docker $USER

# 重新登录或执行
newgrp docker
```

### 内存不足

**Mac**：Docker Desktop → Settings → Resources → 增加 Memory

**Linux**：调整 Docker 守护进程内存限制

### 验证 Docker 安装

```bash
docker --version
docker info
docker run hello-world
```

如果以上命令都能正常执行，说明 Docker 已正确安装。
