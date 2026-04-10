#!/bin/bash
# 完整构建（使用缓存资源）
# 运行时机：日常开发、发版
# 运行时间：2-3 分钟

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESKTOP_DIR="$(dirname "$SCRIPT_DIR")"
CACHE_DIR="$DESKTOP_DIR/src-tauri/build-cache"
RESOURCES_DIR="$DESKTOP_DIR/src-tauri/resources"
PROJECT_ROOT="$(dirname "$DESKTOP_DIR")"

echo "============================================"
echo "  AgentMatrix 快速构建"
echo "============================================"
echo ""

# 检测系统架构
ARCH=$(uname -m)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
    PODMAN_ARCH="arm64"
else
    PODMAN_ARCH="x64"
fi

# ========================================
# 步骤 0: 检查缓存
# ========================================
echo "🔍 检查构建缓存..."
CACHE_OK=true

if [ ! -f "$CACHE_DIR/docker/image.tar.gz" ]; then
    echo "⚠️  Docker 镜像缓存不存在: $CACHE_DIR/docker/image.tar.gz"
    CACHE_OK=false
fi

PODMAN_PKG="podman-installer-macos-${PODMAN_ARCH}.pkg"
if [ ! -f "$CACHE_DIR/podman/$PODMAN_PKG" ]; then
    echo "⚠️  Podman 安装包缓存不存在: $CACHE_DIR/podman/$PODMAN_PKG"
    CACHE_OK=false
fi

if [ "$CACHE_OK" = false ]; then
    echo ""
    echo "❌ 构建缓存不完整！"
    echo ""
    echo "请先运行: ./scripts/setup_cache.sh"
    echo "准备构建缓存资源"
    exit 1
fi

echo "✅ 构建缓存完整"
echo ""

# ========================================
# 步骤 1: 复制缓存资源
# ========================================
echo "📋 步骤 1/4: 复制缓存资源..."
echo ""

mkdir -p "$RESOURCES_DIR/docker"
mkdir -p "$RESOURCES_DIR/podman"

# 复制 Docker 镜像
echo "  → 复制 Docker 镜像..."
cp "$CACHE_DIR/docker/image.tar.gz" "$RESOURCES_DIR/docker/image.tar.gz"
ls -lh "$RESOURCES_DIR/docker/image.tar.gz"

# 复制 Podman 安装包
echo "  → 复制 Podman 安装包..."
cp "$CACHE_DIR/podman/$PODMAN_PKG" "$RESOURCES_DIR/podman/"
ls -lh "$RESOURCES_DIR/podman/$PODMAN_PKG"

echo "✅ 资源复制完成"
echo ""

# ========================================
# 步骤 2: 安装本地包
# ========================================
echo "📦 步骤 2/4: 安装本地 agentmatrix 包..."
cd "$PROJECT_ROOT"
pip install -e . > /dev/null 2>&1 || echo "  (已安装)"
echo "✅ 本地包已安装"
echo ""

# ========================================
# 步骤 3: PyInstaller 构建
# ========================================
echo "🐍 步骤 3/4: PyInstaller 构建 server..."
cd "$PROJECT_ROOT"

# 清理之前的构建输出
rm -rf dist-server/server

# 构建
python -m PyInstaller server.spec --distpath dist-server

echo "✅ PyInstaller 构建完成"
ls -lh dist-server/server
echo ""

# ========================================
# 步骤 4: 复制 Python distribution
# ========================================
echo "📋 步骤 4/4: 复制 Python distribution..."
mkdir -p "$RESOURCES_DIR"

# 清理旧的 python_dist
rm -rf "$RESOURCES_DIR/python_dist"

# 复制
echo "  → 复制 dist-server/server → resources/python_dist"
cp -r dist-server/server "$RESOURCES_DIR/python_dist"

# 验证
if [ ! -f "$RESOURCES_DIR/python_dist/server" ]; then
    echo "❌ Error: Python executable not found!"
    exit 1
fi

chmod +x "$RESOURCES_DIR/python_dist/server"
echo "✅ Python distribution 已复制"
echo ""

# ========================================
# 步骤 5: 验证所有资源
# ========================================
echo "🔍 验证所有资源..."
echo "📁 resources 目录结构:"
find "$RESOURCES_DIR" -type f | head -20
echo ""

# ========================================
# 步骤 6: Tauri 构建
# ========================================
echo "🏗️  步骤 6/6: Tauri 构建 .app..."
cd "$DESKTOP_DIR"
npm run tauri:build
echo ""

# ========================================
# 总结
# ========================================
echo "============================================"
echo "✅ 构建完成！"
echo "============================================"
echo ""

BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/release/bundle"
if [ -d "$BUNDLE_DIR/macos" ]; then
    echo "📦 macOS 安装包:"
    ls -lh "$BUNDLE_DIR/macos/"*.dmg 2>/dev/null | awk '{print "  " $9 ": " $5}'
    echo ""

    APP_PATH="$BUNDLE_DIR/macos/AgentMatrix.app"
    if [ -d "$APP_PATH" ]; then
        echo "📍 .app 中的资源文件:"
        echo "  Python distribution:"
        ls -lh "$APP_PATH/Contents/resources/python_dist/server" 2>/dev/null | awk '{print "    " $9 ": " $5}'
        echo "  Docker 镜像:"
        ls -lh "$APP_PATH/Contents/resources/docker/image.tar.gz" 2>/dev/null | awk '{print "    " $9 ": " $5}'
        echo "  Podman 安装包:"
        ls -lh "$APP_PATH/Contents/resources/podman/"*pkg 2>/dev/null | awk '{print "    " $9 ": " $5}'
        echo ""
    fi
fi

echo "🎉 所有步骤完成！"
echo "⏱️  总耗时: 约 2-3 分钟"
echo ""
