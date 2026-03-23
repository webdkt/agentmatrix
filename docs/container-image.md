# AgentMatrix 容器镜像构建指南

## 概述

AgentMatrix 为每个 Agent 提供独立的容器环境，所有 Agent 共享同一个基础镜像 `agentmatrix:latest`。

## 镜像包含的 Python 包

### 数据处理
- `pandas` - 数据分析和处理
- `numpy` - 数值计算
- `openpyxl` - Excel 读写
- `xlsxwriter` - Excel 写入
- `xlrd` - Excel 读取

### Office 文档处理
- `python-pptx` - PowerPoint 操作
- `python-docx` - Word 操作

### 配置文件
- `pyyaml` - YAML 配置文件
- `toml` - TOML 配置文件

### 网络请求
- `requests` - HTTP 请求
- `httpx` - 异步 HTTP
- `aiohttp` - 异步网络库

### 文本/HTML 处理
- `markdown` - Markdown 解析
- `beautifulsoup4` - HTML 解析
- `lxml` - XML/HTML 处理

### 实用工具
- `python-dateutil` - 日期处理
- `pytz` - 时区支持
- `tqdm` - 进度条
- `rich` - 终端美化输出

### 图像处理
- `pillow` - 图像处理

### PDF 处理
- `pdfplumber` - PDF 解析

### 其他工具
- `pydantic` - 数据验证
- `python-multipart` - 多部分表单数据

## 快速开始

### 前置条件

安装 Docker 或 Podman：

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

### 构建镜像

使用提供的构建脚本：

```bash
# 自动检测运行时（Podman 优先）
./build_image.sh

# 指定使用 Docker
./build_image.sh --runtime docker

# 指定使用 Podman
./build_image.sh --runtime podman

# 自定义镜像名称和标签
./build_image.sh --name myagentmatrix --tag v1.0
```

### 手动构建

如果你想手动构建：

```bash
# 使用 Docker
docker build -t agentmatrix:latest .

# 使用 Podman
podman build -t agentmatrix:latest .
```

## 验证镜像

构建完成后，验证镜像：

```bash
# Docker
docker images | grep agentmatrix

# Podman
podman images | grep agentmatrix
```

测试镜像：

```bash
# Docker
docker run -it agentmatrix:latest /bin/bash

# Podman
podman run -it agentmatrix:latest /bin/bash

# 在容器内测试 Python 包
python -c "import pandas; import openpyxl; import pptx; print('✓ 所有包导入成功')"
```

## 镜像使用

镜像会在创建 Agent 容器时自动使用。在配置中指定镜像名称：

```yaml
# workspace/config/matrix_config.yml
container:
  runtime: "auto"  # auto, docker, podman
  auto_start: true
```

## 更新镜像

当 `requirements-docker.txt` 或 `Dockerfile` 更新后，重新构建镜像：

```bash
./build_image.sh

# 如果需要强制重新构建（不使用缓存）
./build_image.sh --runtime docker
docker build --no-cache -t agentmatrix:latest .
```

## 镜像大小优化

当前镜像大小约为：

- **基础镜像**: python:3.12-slim (~100MB)
- **Python 包**: ~200MB
- **系统依赖**: ~50MB
- **总计**: ~350MB

如需进一步优化：

1. 使用 `python:3.12-alpine` 基础镜像（更小但可能有兼容性问题）
2. 清理不必要的包
3. 使用多阶段构建

## 故障排除

### 构建失败

**问题**: 构建过程中网络错误

**解决方案**:
```bash
# 使用国内镜像源
docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t agentmatrix:latest .
```

**问题**: 某些包安装失败

**解决方案**:
- 检查 `requirements-docker.txt` 中的版本兼容性
- 查看错误日志，可能是系统依赖缺失
- 在 Dockerfile 中添加必要的系统包

### Podman 问题

**问题**: Podman 虚拟机未启动（macOS）

**解决方案**:
```bash
podman machine start
```

**问题**: Podman 无法连接

**解决方案**:
```bash
# 重启 Podman 服务
podman machine stop
podman machine start
```

### Docker 问题

**问题**: Docker 未运行（macOS）

**解决方案**:
```bash
open -a Docker
```

**问题**: 权限错误（Linux）

**解决方案**:
```bash
# 将用户添加到 docker 组
sudo usermod -aG docker $USER
newgrp docker
```

## 添加新的 Python 包

编辑 `requirements-docker.txt`:

```bash
# 添加新的包
vim requirements-docker.txt

# 重新构建镜像
./build_image.sh
```

## 多运行时支持

AgentMatrix 支持在同一个系统中使用不同的容器运行时：

```bash
# 使用 Docker 构建
./build_image.sh --runtime docker --name agentmatrix-docker

# 使用 Podman 构建
./build_image.sh --runtime podman --name agentmatrix-podman
```

在运行时，AgentMatrix 会根据配置自动选择合适的运行时。

## 最佳实践

1. **开发环境**: 使用 Podman（更轻量、更安全）
2. **生产环境**: 使用 Docker（更成熟、更广泛）
3. **Windows 环境**: 优先使用 Podman（更好的原生支持）
4. **CI/CD**: 使用 `runtime: auto` 实现运行时无关构建

## 相关文档

- [容器运行时抽象层](container-runtime.md)
- [容器运行时快速参考](container-runtime-quick-reference.md)
- [容器运行时实现细节](container-runtime-implementation.md)

## 许可证

MIT License - 详见项目根目录 LICENSE 文件
