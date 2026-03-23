# AgentMatrix 容器镜像快速构建指南

## 🚀 一分钟快速开始

### 前置条件

确保已安装 Docker 或 Podman：

```bash
# 检查 Docker
docker --version

# 检查 Podman
podman --version
```

### 构建镜像

```bash
# 方式1：使用构建脚本（推荐）
./build_image.sh

# 方式2：手动构建
docker build -t agentmatrix:latest .
# 或
podman build -t agentmatrix:latest .
```

### 验证镜像

```bash
# 查看镜像
docker images | grep agentmatrix
# 或
podman images | grep agentmatrix

# 测试镜像
docker run -it agentmatrix:latest /bin/bash
# 或
podman run -it agentmatrix:latest /bin/bash

# 在容器内测试
python -c "import pandas; import openpyxl; import pptx; print('✓ 所有包导入成功')"
```

## 📦 镜像内容

镜像包含以下常用 Python 包：

### 数据处理
- pandas, numpy, openpyxl, xlsxwriter, xlrd

### Office 文档
- python-pptx, python-docx

### 网络请求
- requests, httpx, aiohttp

### 文本处理
- markdown, beautifulsoup4, lxml

### 实用工具
- python-dateutil, pytz, tqdm, rich

### 图像处理
- pillow

### PDF 处理
- pdfplumber

完整列表请查看：[容器镜像构建指南](docs/container-image.md)

## 🔧 高级用法

### 指定运行时

```bash
# 使用 Docker
./build_image.sh --runtime docker

# 使用 Podman
./build_image.sh --runtime podman
```

### 自定义镜像名称和标签

```bash
./build_image.sh --name myagent --tag v1.0
```

### 强制重新构建

```bash
# Docker
docker build --no-cache -t agentmatrix:latest .

# Podman
podman build --no-cache -t agentmatrix:latest .
```

## ❓ 常见问题

### 构建失败

**问题**: 网络错误导致包下载失败

**解决方案**: 使用国内镜像源
```bash
docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t agentmatrix:latest .
```

### Podman 问题

**问题**: Podman 虚拟机未启动（macOS）

**解决方案**:
```bash
podman machine start
```

### Docker 问题

**问题**: Docker 未运行（macOS）

**解决方案**:
```bash
open -a Docker
```

## 📚 更多文档

- [容器镜像构建指南](docs/container-image.md) - 完整的构建文档
- [容器运行时抽象层](docs/container-runtime.md) - Docker/Podman 支持
- [容器运行时快速参考](docs/container-runtime-quick-reference.md)

## 🆘 获取帮助

如果遇到问题：

1. 查看 [容器镜像构建指南](docs/container-image.md) 的故障排除部分
2. 检查 [GitHub Issues](https://github.com/webdkt/agentmatrix/issues)
3. 提交新的 Issue

---

**提示**: 首次构建可能需要 5-10 分钟，取决于网络速度。
