#!/bin/bash
# 完整的本地构建脚本（PyInstaller + Tauri）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
DESKTOP_DIR="$PROJECT_ROOT/agentmatrix-desktop"

echo "============================================"
echo "  AgentMatrix 完整本地构建"
echo "============================================"
echo ""

# 步骤 0: 安装本地 agentmatrix 包
echo "📦 步骤 1: 安装本地 agentmatrix 包..."
cd "$PROJECT_ROOT"
pip install -e . > /dev/null 2>&1 || echo "  (已安装)"
echo "✅ 本地包已安装"
echo ""

# 步骤 1: PyInstaller 构建 server
echo "🐍 步骤 2: PyInstaller 构建 server..."
cd "$PROJECT_ROOT"
rm -rf dist-server/server
python -m PyInstaller server.spec --distpath dist-server
echo "✅ PyInstaller 构建完成"
ls -lh dist-server/server
echo ""

# 步骤 2: 复制 Python distribution 到 Tauri resources
echo "📋 步骤 3: 复制 Python distribution 到 Tauri resources..."
mkdir -p "$DESKTOP_DIR/src-tauri/resources"
rm -rf "$DESKTOP_DIR/src-tauri/resources/python_dist"
echo "  → 复制 dist-server/server → resources/python_dist"
cp -r dist-server/server "$DESKTOP_DIR/src-tauri/resources/python_dist"

if [ ! -f "$DESKTOP_DIR/src-tauri/resources/python_dist/server" ]; then
    echo "❌ Error: Python executable not found!"
    echo "   Expected: $DESKTOP_DIR/src-tauri/resources/python_dist/server"
    exit 1
fi

chmod +x "$DESKTOP_DIR/src-tauri/resources/python_dist/server"
echo "  ✅ resources/python_dist/server: $(ls -lh "$DESKTOP_DIR/src-tauri/resources/python_dist/server" | awk '{print $5}')"
echo ""

# 步骤 3: Tauri 构建
echo "🏗️  步骤 4: Tauri 构建..."
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
fi
echo "🎉 所有步骤完成！"
