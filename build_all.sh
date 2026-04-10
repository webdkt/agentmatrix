#!/bin/bash
# 完整的本地构建脚本（包含 PyInstaller、Docker 镜像、Podman 安装包）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
DESKTOP_DIR="$PROJECT_ROOT/agentmatrix-desktop"

echo "============================================"
echo "  AgentMatrix 完整本地构建"
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

# 步骤 0: 安装本地 agentmatrix 包
echo "📦 步骤 0: 安装本地 agentmatrix 包..."
cd "$PROJECT_ROOT"
pip install -e . > /dev/null 2>&1 || echo "  (已安装)"
echo "✅ 本地包已安装"
echo ""

# 步骤 1: 构建 Docker 镜像
echo "🐳 步骤 1: 构建 Docker 镜像..."
cd "$PROJECT_ROOT"
if command -v docker &> /dev/null; then
    docker build -t agentmatrix:latest .
    echo "✅ Docker 镜像构建完成"
else
    echo "⚠️  Docker 未安装，跳过 Docker 镜像构建"
    echo "   如果需要打包 Docker 镜像，请先安装 Docker"
fi
echo ""

# 步骤 2: 导出 Docker 镜像
echo "📦 步骤 2: 导出 Docker 镜像..."
if command -v docker &> /dev/null; then
    mkdir -p "$DESKTOP_DIR/src-tauri/resources/docker"
    docker save agentmatrix:latest | gzip > "$DESKTOP_DIR/src-tauri/resources/docker/image.tar.gz"
    echo "✅ Docker 镜像已导出"
    ls -lh "$DESKTOP_DIR/src-tauri/resources/docker/image.tar.gz"
else
    echo "⚠️  跳过 Docker 镜像导出（Docker 未安装）"
fi
echo ""

# 步骤 3: 下载 Podman 安装包
echo "📥 步骤 3: 下载 Podman 安装包..."
mkdir -p "$DESKTOP_DIR/src-tauri/resources/podman"

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    PODMAN_PKG="podman-installer-macos-${PODMAN_ARCH}.pkg"
    echo "  → 下载 $PODMAN_PKG"

    # 获取最新版本信息
    RELEASE_INFO=$(curl -s https://api.github.com/repos/containers/podman/releases/latest)
    PACKAGE_URL=$(echo "$RELEASE_INFO" | jq -r ".assets[] | select(.name == \"$PODMAN_PKG\") | .browser_download_url")

    if [ -z "$PACKAGE_URL" ] || [ "$PACKAGE_URL" = "null" ]; then
        echo "❌ 无法找到 Podman 安装包下载链接"
        echo "   请手动下载并放置到: $DESKTOP_DIR/src-tauri/resources/podman/"
        exit 1
    fi

    echo "  → 从 $PACKAGE_URL 下载..."
    curl -L -o "$DESKTOP_DIR/src-tauri/resources/podman/$PODMAN_PKG" "$PACKAGE_URL"
    echo "✅ Podman 安装包下载完成"
    ls -lh "$DESKTOP_DIR/src-tauri/resources/podman/$PODMAN_PKG"
else
    echo "⚠️  当前系统不是 macOS，跳过 Podman 安装包下载"
fi
echo ""

# 步骤 4: PyInstaller 构建 server
echo "🐍 步骤 4: PyInstaller 构建 server..."
cd "$PROJECT_ROOT"
# 清理之前的构建输出，避免冲突
rm -rf dist-server/server
python -m PyInstaller server.spec --distpath dist-server
echo "✅ PyInstaller 构建完成"
ls -lh dist-server/server
echo ""

# 步骤 5: 复制 Python distribution 到 Tauri resources
echo "📋 步骤 5: 复制 Python distribution 到 Tauri resources..."
mkdir -p "$DESKTOP_DIR/src-tauri/resources"

# 清理旧的 python_dist，避免复制冲突
rm -rf "$DESKTOP_DIR/src-tauri/resources/python_dist"

# 复制整个 python_dist 文件夹（onedir 模式输出）
echo "  → 复制 dist-server/server → resources/python_dist"
cp -r dist-server/server "$DESKTOP_DIR/src-tauri/resources/python_dist"

# 验证可执行文件存在
if [ ! -f "$DESKTOP_DIR/src-tauri/resources/python_dist/server" ]; then
    echo "❌ Error: Python executable not found!"
    echo "   Expected: $DESKTOP_DIR/src-tauri/resources/python_dist/server"
    exit 1
fi

chmod +x "$DESKTOP_DIR/src-tauri/resources/python_dist/server"
echo "  ✅ resources/python_dist/server: $(ls -lh "$DESKTOP_DIR/src-tauri/resources/python_dist/server" | awk '{print $5}')"
echo "  📁 Python distribution folder contents:"
ls -la "$DESKTOP_DIR/src-tauri/resources/python_dist" | head -20
echo ""

# 步骤 6: 验证所有资源
echo "🔍 步骤 6: 验证所有资源..."
echo "📁 resources 目录结构:"
find "$DESKTOP_DIR/src-tauri/resources" -type f -exec ls -lh {} \; | awk '{print "  " $9 ": " $5}'
echo ""

# 步骤 7: Tauri 构建
echo "🏗️  步骤 7: Tauri 构建 .app..."
cd "$DESKTOP_DIR"
npm run tauri:build
echo ""
echo "============================================"
echo "✅ 构建完成！"
echo "============================================"
echo ""

# 显示最终构建结果
BUNDLE_DIR="$DESKTOP_DIR/src-tauri/target/release/bundle"
if [ -d "$BUNDLE_DIR/macos" ]; then
    echo "📦 macOS 安装包:"
    ls -lh "$BUNDLE_DIR/macos/"*.dmg 2>/dev/null || echo "  未找到 .dmg 文件"
    echo ""

    APP_PATH="$BUNDLE_DIR/macos/AgentMatrix.app"
    if [ -d "$APP_PATH" ]; then
        echo "📍 .app 中的资源文件:"
        echo "  Python distribution:"
        ls -lh "$APP_PATH/Contents/resources/python_dist/server" 2>/dev/null || echo "    未找到"
        echo "  Docker 镜像:"
        ls -lh "$APP_PATH/Contents/resources/docker/image.tar.gz" 2>/dev/null || echo "    未找到"
        echo "  Podman 安装包:"
        ls -lh "$APP_PATH/Contents/resources/podman/"*pkg 2>/dev/null || echo "    未找到"
        echo ""
    fi
fi
echo "🎉 所有步骤完成！"

