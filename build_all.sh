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
# 清理之前的构建输出，避免冲突
rm -rf dist-server/server
python -m PyInstaller server.spec --distpath dist-server
echo "✅ PyInstaller 构建完成"
ls -lh dist-server/server
echo ""

# 步骤 2: 复制 Python distribution 到 Tauri resources
echo "📋 步骤 2: 复制 Python distribution 到 Tauri resources..."
mkdir -p "$DESKTOP_DIR/src-tauri/resources"

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

# 步骤 3: Tauri 构建
echo "🏗️  步骤 3: Tauri 构建 .app..."
cd "$DESKTOP_DIR"
npm run tauri:build
echo ""
echo "============================================"
echo "✅ 构建完成！"
echo "============================================"
echo ""
echo "📍 最终 .app 中的 Python distribution:"
ls -lh "$DESKTOP_DIR/src-tauri/target/release/bundle/macos/AgentMatrix.app/Contents/resources/python_dist/server"
echo ""
echo "📁 Python distribution 在 .app 中的结构:"
ls -la "$DESKTOP_DIR/src-tauri/target/release/bundle/macos/AgentMatrix.app/Contents/resources/python_dist" | head -20
echo ""

