# AgentMatrix 构建脚本使用指南

## 目录结构

```
agentmatrix-desktop/
├── scripts/
│   ├── setup_cache.sh      # ⭐ 准备缓存资源（按需运行）
│   ├── build_all.sh        # 🔨 完整构建（使用缓存）
│   ├── build_server.sh     # 🐍 仅构建 Python 后端
│   └── build_app.sh        # 📱 仅构建 Tauri App
│
└── src-tauri/
    ├── build-cache/        # 💾 持久化缓存（不打包）
    │   ├── docker/
    │   │   └── image.tar.gz
    │   └── podman/
    │       ├── podman-installer-arm64.pkg
    │       └── podman-installer-x64.pkg
    │
    └── resources/          # 📦 构建时临时资源（会打包进 .app）
        ├── python_dist/
        ├── docker/
        └── podman/
```

## 快速开始

### 首次构建

```bash
cd agentmatrix-desktop

# 1️⃣ 准备缓存资源（首次必须运行，耗时 5-10 分钟）
./scripts/setup_cache.sh

# 2️⃣ 完整构建（使用缓存，耗时 2-3 分钟）
./scripts/build_all.sh
```

### 日常开发

```bash
# Python 代码修改后
./scripts/build_server.sh

# 前端代码修改后（需先构建过后端）
./scripts/build_app.sh

# 完整构建
./scripts/build_all.sh
```

## 脚本说明

### 1. setup_cache.sh - 准备缓存资源

**用途：** 下载/构建持久化缓存资源

**运行时机：**
- ✅ 首次设置
- ✅ Podman 版本更新
- ✅ Dockerfile 更新

**运行时间：** 5-10 分钟

**输出：**
- `build-cache/docker/image.tar.gz` - 容器镜像
- `build-cache/podman/*.pkg` - Podman 安装包

```bash
./scripts/setup_cache.sh
```

### 2. build_all.sh - 完整构建

**用途：** 完整构建流程（使用缓存）

**运行时机：**
- ✅ 日常开发
- ✅ 发版构建

**运行时间：** 2-3 分钟

**前提条件：** 已运行 `setup_cache.sh`

**输出：**
- `target/release/bundle/macos/AgentMatrix.dmg`

```bash
./scripts/build_all.sh
```

### 3. build_server.sh - 仅构建后端

**用途：** 只构建 Python 后端

**运行时机：**
- ✅ Python 代码修改
- ✅ `src/` 目录修改

**运行时间：** 1-2 分钟

**输出：**
- `resources/python_dist/` (已更新)

```bash
./scripts/build_server.sh
```

### 4. build_app.sh - 仅构建 App

**用途：** 只构建 Tauri App（复用已有资源）

**运行时机：**
- ✅ 前端代码修改
- ✅ `src/` Vue 文件修改

**运行时间：** 1-2 分钟

**前提条件：** 已有 `resources/` 资源

**输出：**
- `target/release/bundle/macos/AgentMatrix.dmg`

```bash
./scripts/build_app.sh
```

## 前置要求

### 必需

```bash
# Python 3.12+
brew install python@3.12

# Node.js 20+
brew install node
```

### 可选（用于 setup_cache.sh）

```bash
# Docker（用于构建容器镜像）
brew install docker docker-compose

# jq（用于解析 GitHub API）
brew install jq
```

## 工作流程示例

### 场景 1：首次构建

```bash
# 1. 准备缓存（仅首次）
./scripts/setup_cache.sh

# 2. 完整构建
./scripts/build_all.sh

# 3. 测试 .app
open target/release/bundle/macos/AgentMatrix.app
```

### 场景 2：修改 Python 代码

```bash
# 编辑 Python 代码...
vim src/agentmatrix/some_file.py

# 重新构建后端
./scripts/build_server.sh

# 如需测试完整 .app
./scripts/build_app.sh
```

### 场景 3：修改前端代码

```bash
# 编辑 Vue 代码...
vim src/components/some_component.vue

# 重新构建 App（复用已有后端）
./scripts/build_app.sh
```

### 场景 4：更新 Dockerfile

```bash
# 编辑 Dockerfile...
vim Dockerfile

# 更新缓存中的 Docker 镜像
./scripts/setup_cache.sh

# 完整构建
./scripts/build_all.sh
```

## 故障排查

### 缓存不完整

```bash
❌ 构建缓存不完整！
请先运行: ./scripts/setup_cache.sh
```

**解决：** 运行 `./scripts/setup_cache.sh` 准备缓存

### Docker 未安装

```bash
⚠️ Docker 未安装，跳过 Docker 镜像构建
```

**解决（可选）：**
```bash
brew install docker docker-compose
```

### 权限错误

```bash
Permission denied: ./scripts/xxx.sh
```

**解决：**
```bash
chmod +x ./scripts/*.sh
```

## 性能对比

| 方式 | 时间 | 说明 |
|------|------|------|
| 旧方式（每次全构建） | 8-12 分钟 | 包含 Docker 构建、下载 Podman |
| 新方式（首次） | 8-12 分钟 | setup_cache.sh + build_all.sh |
| 新方式（日常） | 2-3 分钟 | 仅 build_all.sh（使用缓存） |
| 仅后端 | 1-2 分钟 | build_server.sh |
| 仅前端 | 1-2 分钟 | build_app.sh |

## 高级技巧

### 1. 并行开发

如果你同时修改前端和后端，可以：

```bash
# 终端 1：构建后端
./scripts/build_server.sh

# 终端 2：构建前端（等后端完成）
./scripts/build_app.sh
```

### 2. 清理缓存

```bash
# 清理所有缓存
rm -rf src-tauri/build-cache

# 清理构建产物
rm -rf src-tauri/target
rm -rf dist-server
```

### 3. 查看缓存大小

```bash
du -sh src-tauri/build-cache
```

## 常见问题

**Q: 可以跳过 setup_cache.sh 吗？**
A: 不可以。首次构建必须运行，后续可以按需更新。

**Q: build_cache 需要提交到 Git 吗？**
A: 建议使用 Git LFS，或者作为构建产物在 CI 中生成。

**Q: 可以手动下载 Podman 安装包吗？**
A: 可以。下载后放到 `src-tauri/build-cache/podman/` 目录。

**Q: Docker 镜像可以手动构建吗？**
A: 可以。运行 `docker build -t agentmatrix:latest .` 然后
   `docker save agentmatrix:latest | gzip > src-tauri/build-cache/docker/image.tar.gz`

---

如有问题，请查看项目文档或提交 Issue。
