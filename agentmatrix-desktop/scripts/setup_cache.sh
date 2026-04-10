#!/bin/bash
# 准备构建缓存资源
# 运行时机：首次设置、Podman 版本更新、Dockerfile 更新
# 运行时间：5-10 分钟

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(dirname "$SCRIPT_DIR")"
CACHE_DIR="$DESKTOP_DIR/src-tauri/build-cache"
PROJECT_ROOT="$(dirname "$DESKTOP_DIR")"

echo "============================================"
echo "  AgentMatrix 构建缓存准备"
echo "============================================"
echo ""

# 检测系统架构
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    PODMAN_ARCH="arm64"
    echo "🔍 检测到 ARM64 架构"
else
    PODMAN_ARCH="x64"
    echo "🔍 检测到 x86_64 架构"
fi
echo ""

# 创建缓存目录
echo "📁 创建缓存目录..."
mkdir -p "$CACHE_DIR/docker"
mkdir -p "$CACHE_DIR/podman"
echo "✅ 缓存目录: $CACHE_DIR"
echo ""

# ========================================
# 步骤 1: 构建 Docker 镜像
# ========================================
echo "============================================"
echo "步骤 1/2: 构建 Docker 镜像"
echo "============================================"
echo ""

if command -v docker &> /dev/null; then
    echo "🐳 构建 Docker 镜像..."
    cd "$PROJECT_ROOT"
    docker build -t agentmatrix:latest .

    echo ""
    echo "📦 导出镜像到缓存..."
    docker save agentmatrix:latest | gzip > "$CACHE_DIR/docker/image.tar.gz"

    IMAGE_SIZE=$(du -h "$CACHE_DIR/docker/image.tar.gz" | cut -f1)
    echo "✅ Docker 镜像已缓存: $IMAGE_SIZE"
    echo "   路径: $CACHE_DIR/docker/image.tar.gz"
else
    echo "⚠️  Docker 未安装，跳过 Docker 镜像构建"
    echo "   如需构建容器镜像，请先安装 Docker:"
    echo "   brew install docker docker-compose"
fi
echo ""

# ========================================
# 步骤 2: 下载 Podman 安装包
# ========================================
echo "============================================"
echo "步骤 2/2: 下载 Podman 安装包"
echo "============================================"
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    PODMAN_PKG="podman-installer-macos-${PODMAN_ARCH}.pkg"

    # 检查是否已存在
    if [ -f "$CACHE_DIR/podman/$PODMAN_PKG" ]; then
        echo "✓ Podman 安装包已存在:"
        ls -lh "$CACHE_DIR/podman/$PODMAN_PKG"
        echo ""
        read -p "是否重新下载? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "跳过下载，使用现有文件"
        else
            rm -f "$CACHE_DIR/podman/$PODMAN_PKG"
            echo "继续下载..."
        fi
    fi

    if [ ! -f "$CACHE_DIR/podman/$PODMAN_PKG" ]; then
        echo "📥 下载 $PODMAN_PKG..."

        # 获取最新版本信息
        RELEASE_INFO=$(curl -s https://api.github.com/repos/containers/podman/releases/latest)
        PACKAGE_URL=$(echo "$RELEASE_INFO" | jq -r ".assets[] | select(.name == \"$PODMAN_PKG\") | .browser_download_url")

        if [ -z "$PACKAGE_URL" ] || [ "$PACKAGE_URL" = "null" ]; then
            echo "❌ 无法找到 Podman 安装包下载链接"
            echo "   请手动下载并放置到: $CACHE_DIR/podman/"
            exit 1
        fi

        echo "   从 GitHub releases 下载..."
        curl -L -o "$CACHE_DIR/podman/$PODMAN_PKG" "$PACKAGE_URL"

        PKG_SIZE=$(du -h "$CACHE_DIR/podman/$PODMAN_PKG" | cut -f1)
        echo "✅ Podman 安装包已缓存: $PKG_SIZE"
        echo "   路径: $CACHE_DIR/podman/$PODMAN_PKG"
    fi
else
    echo "⚠️  当前系统不是 macOS，跳过 Podman 安装包下载"
fi
echo ""

# ========================================
# 总结
# ========================================
echo "============================================"
echo "✅ 构建缓存准备完成！"
echo "============================================"
echo ""
echo "📦 缓存内容:"
find "$CACHE_DIR" -type f -exec ls -lh {} \; | awk '{print "  " $9 ": " $5}'
echo ""
echo "💡 提示:"
echo "  - 缓存已准备好，可以运行 ./build_all.sh 进行快速构建"
echo "  - 下次更新缓存时再运行此脚本"
echo ""
