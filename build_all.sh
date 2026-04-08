#!/bin/bash
# 完整的本地构建脚本（包含 PyInstaller）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
DESKTOP_DIR="$PROJECT_ROOT/agentmatrix-desktop"

echo "============================================"
echo "  AgentMatrix 完整本地构建"
echo "============================================"
echo ""

# 步骤 0: 安装本地 agentmatrix 包
echo "📦 步骤 0: 安装本地 agentmatrix 包..."
cd "$PROJECT_ROOT"
pip install -e . > /dev/null 2>&1 || echo "  (已安装)"
echo "✅ 本地包已安装"
echo ""

# 步骤 1: PyInstaller 构建 server
echo "📦 步骤 1: PyInstaller 构建 server..."
python -m PyInstaller server.spec --distpath dist-server
echo "✅ PyInstaller 构建完成"
ls -lh dist-server/server
echo ""

# 步骤 2: 复制到 Tauri binaries 和 target/release
echo "📋 步骤 2: 复制 server 到 Tauri..."
mkdir -p "$DESKTOP_DIR/src-tauri/binaries"
mkdir -p "$DESKTOP_DIR/src-tauri/target/release"

# 复制到 binaries（用于 externalBin）
cp dist-server/server "$DESKTOP_DIR/src-tauri/binaries/server"
chmod +x "$DESKTOP_DIR/src-tauri/binaries/server"
echo "  → binaries/server: $(ls -lh "$DESKTOP_DIR/src-tauri/binaries/server" | awk '{print $5}')"

# 复制到 target/release（覆盖占位符）
cp dist-server/server "$DESKTOP_DIR/src-tauri/target/release/server"
chmod +x "$DESKTOP_DIR/src-tauri/target/release/server"
echo "  → target/release/server: $(ls -lh "$DESKTOP_DIR/src-tauri/target/release/server" | awk '{print $5}')"
echo ""

# 步骤 3: Tauri 构建
echo "🏗️  步骤 3: Tauri 构建 .app..."
cd "$DESKTOP_DIR"
npm run tauri:build
echo ""
echo "============================================"
echo "✅ 构建完成！"
echo "============================================"
echo ""
echo "📍 最终 .app 中的 server:"
ls -lh "$DESKTOP_DIR/src-tauri/target/release/bundle/macos/AgentMatrix.app/Contents/MacOS/server"
echo ""

