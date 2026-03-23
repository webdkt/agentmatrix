# 容器镜像使用工作流程

## 📌 重要概念

### Git 中有什么？
- ✅ `Dockerfile` - 镜像构建配方
- ✅ `requirements-docker.txt` - Python 包列表
- ✅ `build_image.sh` - 构建脚本

### Git 中没有什么？
- ❌ Docker 镜像文件（~350MB，太大）
- ❌ 容器文件系统
- ❌ 构建缓存

## 🔄 标准工作流程

### 场景1：首次设置项目

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd agentmatrix

# 2. 构建镜像（本地）
./build_image.sh

# 3. 验证镜像
docker images | grep agentmatrix
# 或
podman images | grep agentmatrix
```

### 场景2：更新代码后

```bash
# 1. 拉取最新代码
git pull

# 2. 检查镜像相关文件是否有变化
git diff HEAD~1 Dockerfile
git diff HEAD~1 requirements-docker.txt

# 3. 如果有变化，重新构建镜像
./build_image.sh

# 4. 镜像会自动更新（同名标签会覆盖）
```

### 场景3：团队协作

#### 方案A：每个人本地构建（推荐用于开发）

```bash
# 每个开发者自己构建
./build_image.sh
```

**优点：**
- ✅ 不需要镜像仓库
- ✅ 完全离线可用
- ✅ 可以自定义修改

**缺点：**
- ❌ 每个人都要构建（5-10分钟）
- ❌ 网络慢时会慢

#### 方案B：使用镜像仓库（推荐用于生产/团队）

```bash
# 管理员：构建并推送
docker build -t your-registry/agentmatrix:latest .
docker push your-registry/agentmatrix:latest

# 其他成员：直接拉取
docker pull your-registry/agentmatrix:latest
```

**优点：**
- ✅ 快速（只需拉取）
- ✅ 统一的镜像版本
- ✅ 适合CI/CD

**缺点：**
- ❌ 需要镜像仓库账号
- ❌ 需要网络连接

### 场景4：CI/CD 自动化

```yaml
# .github/workflows/docker.yml
name: Build Docker Image

on:
  push:
    paths:
      - 'Dockerfile'
      - 'requirements-docker.txt'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Build image
        run: ./build_image.sh --runtime docker

      - name: Push to registry
        run: |
          echo "${{ secrets.REGISTRY_PASSWORD }}" | docker login -u "${{ secrets.REGISTRY_USER }}" --password-stdin
          docker push ${{ secrets.REGISTRY_URL }}/agentmatrix:latest
```

## 🚫 错误做法

### ❌ 不要这样做

```bash
# 错误1：导出镜像到Git
docker save agentmatrix:latest > agentmatrix.tar
git add agentmatrix.tar  # ❌ 不要这样做！

# 错误2：把镜像文件放在项目目录
cp /var/lib/docker/.../image.tar .  # ❌ 不要这样做！
```

**为什么？**
- 会让仓库变得巨大
- 克隆会非常慢
- Git无法有效diff二进制文件

## 📝 推荐的 Git 提交消息

```bash
# 更新Python包
git commit -m "feat: add pandas and openpyxl to container image"

# 更新系统依赖
git commit -m "feat: add PDF processing libraries to Dockerfile"

# 更新构建脚本
git commit -m "feat: improve build script with better error handling"
```

## 🏷️ 镜像版本管理

### 开发阶段

```bash
# 使用 latest 标签
./build_image.sh --tag latest
```

### 生产环境

```bash
# 使用语义化版本
./build_image.sh --tag v1.0.0
./build_image.sh --tag v1.0.1
./build_image.sh --tag v2.0.0
```

### 推送到仓库

```bash
# 推送多个标签
docker tag agentmatrix:latest registry/agentmatrix:v1.0.0
docker tag agentmatrix:latest registry/agentmatrix:stable
docker push registry/agentmatrix:v1.0.0
docker push registry/agentmatrix:stable
```

## 🔍 验证镜像

```bash
# 检查镜像信息
docker inspect agentmatrix:latest

# 查看镜像历史
docker history agentmatrix:latest

# 测试镜像
docker run --rm agentmatrix:latest python -c "import pandas; print('OK')"
```

## 📊 镜像仓库选项

### 公共仓库（免费）
- **Docker Hub** - https://hub.docker.com/
- **GitHub Container Registry** - https://ghcr.io/
- **GitLab Container Registry** - 包含在GitLab中

### 私有仓库（付费或有限免费）
- **阿里云容器镜像服务** - 中国速度快
- **腾讯云容器镜像服务**
- **AWS ECR**
- **Google GCR**

## 🎯 最佳实践

1. **开发环境**：本地构建（`./build_image.sh`）
2. **测试环境**：CI/CD 自动构建
3. **生产环境**：从镜像仓库拉取
4. **版本标签**：生产环境使用固定版本（如 v1.0.0），不用 latest

## 💡 提示

- 首次构建需要 5-10 分钟
- 后续构建会使用缓存，更快
- 可以使用 `--no-cache` 强制重新构建
- 定期清理旧镜像节省空间：`docker system prune -a`

## 📚 相关文档

- [容器镜像构建指南](container-image.md)
- [容器运行时抽象层](container-runtime.md)
